"""In-process cache of derived Studio figures, valid exactly as long as what they read is unchanged.

A request opens its own connection, so a result cannot be kept on the connection. A cached
value is kept per store file and the caller's own key; the first element of the key names its
*kind* (``answer`` keys: ``answer:<route>``). Each kind is declared in ``KINDS``: the table groups
its computation reads (``Group``, every table of the schema is in exactly one group, see
``TABLE_GROUP``), its value form, its size limit. A kind that is not declared reads every group,
as before: a missing declaration costs time, never correctness.

Validity (D-1, #1612; replaces the stamp key of #1609 and the re-keying of #1611):

- Per store file the cache keeps an *anchor*, the file's stamp (``store_stamp``: path, SQLite's
  file change counter, size, modification time, size and time of a ``-wal`` file), and one
  generation counter per group. An entry remembers the generations of the groups its kind
  reads and is served only while the current stamp equals the anchor and those generations are
  unchanged (I1). No stamp (in-memory store, open transaction, unreadable file) means compute
  without remembering, as before.
- Any stamp change that no finished, proven write window explains raises every generation and
  drops every entry of the file (I2, fail closed): another process, plain SQL, an import, a
  write route outside ``write``, ``VACUUM``, a migration on opening.
- A write of the Studio's own (``write(store, groups)``) is a *window* on one connection. It
  counts only when (a) the stamp before the window equals the anchor (otherwise everything is
  dropped first: a foreign commit before the window must not hide behind the window's proof),
  (b) the store is a file in rollback-journal mode (header bytes 18/19 are 1, no ``-wal`` or
  ``-journal`` file), there is no open transaction, ``PRAGMA data_version`` of the writing
  connection is the same before and after (no other connection committed in between) and the
  file change counter rose by exactly the number of ``COMMIT`` statements of the window that
  committed changed rows, and (c) the groups the window was *seen* to write (SQLite authorizer
  on the writing connection: also trigger and foreign-key cascade writes) are among the
  declared ones. Then only the written groups' generations rise and the anchor moves to the
  stamp after the window (I3). Order: ``data_version`` first and last, the stamps in between.
  A window that fails, cannot be proven or wrote an undeclared group drops everything; a
  window that left the file unchanged changes nothing.
- A computation that overlaps a change is remembered only if, after it, the generations of the
  groups it reads are still those of its start (I4). The writing thread never uses the cache
  while its window is open (I5): it computes directly.
- A reader that meets a stamp different from the anchor first waits for a running window of
  this process on that file (``_window_lock``) and looks again, so the Studio's own write is
  never mistaken for a foreign one.

Concurrent identical requests share one computation: per key and generations one caller
computes while the others wait for it (``_KeyLock``), so a page that fires two routes needing
the same figure pays for it once; a write to a group the figure does not read keeps the key, so
waiters keep sharing it. A failed computation caches nothing; the next waiter computes itself.

The declared reads are proven in the tests, not trusted: ``tests/unit/test_studio_perf_equivalence.py``
traces every narrowed kind's computation with the SQLite authorizer and fails when it reads a
table outside its groups, and runs every write route against the declared write groups (both
directions). The data epoch of ``memo.py`` is no substitute (see ``builder._corpus_hits``).

Check mode (``COMMANDER_LAB_CACHE_CHECK=1`` or ``CHECK = True``): every remembered value gets a
checksum, compared on every hit; a value changed by a caller raises ``CacheCheckError``, and so
does a window that writes an undeclared group. Counters per kind and event (``counters()``)
are kept in every mode.
"""

from __future__ import annotations

import enum
import hashlib
import itertools
import os
import pickle
import re
import sqlite3
import threading
from collections import Counter, OrderedDict
from collections.abc import Callable, Collection, Hashable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, cast

from . import memo
from .store import StudioStore


class Group(enum.Enum):
    """The table groups. A write raises the generation of the groups it wrote."""

    IMPORT = "import"
    MARKS = "marks"
    DECKS = "decks"
    PROFILES = "profiles"
    SIMULATION = "simulation"
    SNAPSHOT = "snapshot"
    META = "meta"


ALL: Final[frozenset[Group]] = frozenset(Group)

_IMPORT_TABLES = (
    "card", "inventory", "card_location", "scryfall_card", "card_printing", "scryfall_token",
    "scryfall_card_token", "card_ruling", "card_ruling_source", "corpus_deck", "corpus_deck_card",
    "corpus_cohort", "corpus_deck_part", "corpus_deck_stat", "corpus_deck_role",
    "commander_binding", "neutral_board_row", "observation", "card_signal", "card_role",
    "card_role_claim", "commander_combo", "playgroup_card_atlas", "playgroup_top_commander",
    "playgroup_final_zone", "source", "source_capture_event",
)  # fmt: skip
_DECK_TABLES = (
    "deck", "deck_revision", "deck_revision_card", "deck_branch", "deck_draft", "deck_label",
    "deck_primer", "deck_module", "deck_module_card",
)  # fmt: skip

# Every table of the schema in exactly one group (a test fails for a table without one).
TABLE_GROUP: Final[Mapping[str, Group]] = MappingProxyType(
    {
        **dict.fromkeys(_IMPORT_TABLES, Group.IMPORT),
        **dict.fromkeys(_DECK_TABLES, Group.DECKS),
        "card_mark": Group.MARKS,
        "card_label": Group.MARKS,
        "universe_profile": Group.PROFILES,
        "strength_profile": Group.PROFILES,
        "simulation_run": Group.SIMULATION,
        "simulation_card": Group.SIMULATION,
        "tier_snapshot": Group.SNAPSHOT,
        "meta": Group.META,
    }
)

type Seal = Literal["bytes", "frozen", "copy", "shared"]


@dataclass(frozen=True, slots=True)
class Kind:
    """What one kind of entry reads and how it is held.

    ``reads``: the groups its computation reads (default: all). ``seal``: the value form —
    ``bytes`` (immutable by construction), ``copy`` (the caller hands out a copy), ``shared``
    (the caller must treat it as read-only; today's form). ``limit``: the name of a
    ``KIND_LIMITS`` entry the kind counts against, besides ``MAX_ENTRIES``."""

    reads: frozenset[Group] = ALL
    seal: Seal = "shared"
    limit: str | None = None


MAX_ENTRIES = 64
# Limits of a group of kinds: at most so many entries and, for ``bytes`` values, so many bytes in
# total. ``answer``: the remembered JSON answers of the read routes (``answer_cache``, one kind
# per route), whose parameters can vary freely (a search query); they push out older answers,
# not the warm figures. ``slot_catalog``, ``cohort_sizes``: one entry per commander pair asked
# for, so a sweep over many commanders pushes out its own older entries, not the warm figures
# (#1615).
KIND_LIMITS: dict[str, tuple[int, int | None]] = {
    "answer": (16, 48 * 1024 * 1024),
    "slot_catalog": (8, None),
    "cohort_sizes": (8, None),
}

_ANSWER = Kind(seal="bytes", limit="answer")

# The register. Only ``land_source_groups`` is narrowed so far (#1561, proven by its tracer);
# every other kind reads all groups until its own declaration and tracer exist (P2).
KINDS: Final[Mapping[str, Kind]] = MappingProxyType(
    {
        "card_name_index": Kind(),
        "card_trend": Kind(),
        "cohort_deck_sets": Kind(),
        "cohort_shapes": Kind(),
        "cohort_sizes": Kind(seal="copy", limit="cohort_sizes"),
        "corpus_deck_ids": Kind(),
        "corpus_deck_sets": Kind(),
        "corpus_hits": Kind(),
        "data_report": Kind(seal="copy"),
        "deck_evidence_bundle": Kind(),
        "land_source_groups": Kind(reads=frozenset({Group.IMPORT})),
        "layer_overview": Kind(),
        "package_candidates": Kind(),
        "package_deck_sets": Kind(),
        "resolve": Kind(),
        "similar_decks_index": Kind(),
        "slot_catalog": Kind(limit="slot_catalog"),
        "spelling_owners": Kind(),
        "status_store_part": Kind(seal="copy"),
        "strength": Kind(),
        "strength_overall": Kind(),
        "universe_context": Kind(),
        # One kind per remembered route answer (``answer_cache.json_answer``): a shared kind
        # could never carry one declaration (``pool`` reads the marks, ``deck_browser`` the deck
        # labels). They share one size limit.
        "answer:deck_browser": _ANSWER,
        "answer:evidence": _ANSWER,
        "answer:pool": _ANSWER,
        "answer:rating_layers": _ANSWER,
        "answer:role_audit": _ANSWER,
        "answer:universe_counted": _ANSWER,
    }
)
_UNDECLARED = Kind()

CHECK = os.environ.get("COMMANDER_LAB_CACHE_CHECK", "") == "1"

type Stamp = tuple[str, int, int, int, int, int]


class CacheCheckError(RuntimeError):
    """Check mode: a remembered value was changed by a caller, or a window wrote a group it did
    not declare."""


def kind_name(key: tuple[Hashable, ...]) -> str:
    """The kind of ``key``: its first element; for a route answer ``answer:<route>``."""
    first = key[0] if key else ""
    if first == "answer" and len(key) > 1:
        return f"answer:{key[1]}"
    return str(first)


def kind_of(name: str) -> Kind:
    """The declared kind ``name``; undeclared kinds read every group."""
    found = KINDS.get(name)
    if found is not None:
        return found
    return _ANSWER if name.startswith("answer:") else _UNDECLARED


_ORDER: dict[frozenset[Group], tuple[Group, ...]] = {}


def _ordered(groups: frozenset[Group]) -> tuple[Group, ...]:
    found = _ORDER.get(groups)
    if found is None:
        found = _ORDER[groups] = tuple(group for group in Group if group in groups)
    return found


@dataclass(slots=True)
class _Entry:
    value: object
    kind: str
    gens: tuple[int, ...]
    size: int
    checksum: bytes | None = None


@dataclass(slots=True)
class _State:
    """The anchor stamp of one store file and its generation per group."""

    anchor: Stamp | None
    gen: dict[Group, int] = field(default_factory=dict)


class _KeyLock:
    """The lock of one key in flight and how many callers hold or wait for it."""

    __slots__ = ("lock", "users")

    def __init__(self) -> None:
        self.lock = threading.RLock()  # re-entrant: a computation may ask for its own key
        self.users = 0


_lock = threading.Lock()
_entries: OrderedDict[tuple[Hashable, ...], _Entry] = OrderedDict()
_states: dict[str, _State] = {}
_flights: dict[tuple[Hashable, ...], _KeyLock] = {}
_windows: dict[str, threading.Lock] = {}
_counters: Counter[tuple[str, str]] = Counter()
# Generations are drawn from one sequence that never restarts, so a value computed before an
# ``invalidate`` can never match a generation drawn after it.
_generation = itertools.count(1)
_local = threading.local()
_WINDOW_WAIT_S = 5.0


@contextmanager
def read_only() -> Iterator[None]:
    """Within this block of the calling thread ``cached`` still serves what is remembered, but
    remembers nothing new. For one-off sweeps (the data report counts every commander of the
    store) whose many entries would push the warm figures of the working commander out of the
    size limit."""
    before = getattr(_local, "read_only", False)
    _local.read_only = True
    try:
        yield
    finally:
        _local.read_only = before


def store_stamp(store: StudioStore) -> Stamp | None:
    """Identity of the committed state of the store file, or ``None`` when it cannot be
    vouched for (in-memory store, open transaction, unreadable file)."""
    path = store.path
    if path is None or store.connection.in_transaction:
        return None
    try:
        with Path(path).open("rb") as handle:
            header = handle.read(100)
        counter = int.from_bytes(header[24:28], "big")
        stat = os.stat(path)
        wal = Path(f"{path}-wal")
        try:
            wal_stat = wal.stat()
            wal_size, wal_mtime = wal_stat.st_size, wal_stat.st_mtime_ns
        except OSError:
            wal_size, wal_mtime = 0, 0
    except OSError:
        return None
    return (str(path), counter, stat.st_size, stat.st_mtime_ns, wal_size, wal_mtime)


def _writing() -> dict[str, _Window]:
    found = getattr(_local, "writing", None)
    if found is None:
        found = _local.writing = {}
    return cast("dict[str, _Window]", found)


def _window_lock(path: str) -> threading.Lock:
    with _lock:
        found = _windows.get(path)
        if found is None:
            found = _windows[path] = threading.Lock()
        return found


def _new_state(stamp: Stamp | None) -> _State:
    return _State(stamp, {group: next(_generation) for group in Group})


def _rebase_locked(path: str, stamp: Stamp | None, reason: str) -> None:
    """I2: every generation of ``path`` rises, every entry of it is dropped, the anchor becomes
    ``stamp``. Called with ``_lock`` held."""
    dropped = [key for key in _entries if key[0] == path]
    for key in dropped:
        _counters[(_entries.pop(key).kind, f"dropped_{reason}")] += 1
    _states[path] = _new_state(stamp)
    _counters[("*", f"rebase_{reason}")] += 1


def _bump_locked(path: str, groups: frozenset[Group], stamp: Stamp) -> None:
    """A proven window wrote ``groups``: only their generations rise, entries reading them are
    dropped at once, the anchor moves to ``stamp``. Called with ``_lock`` held."""
    state = _states[path]
    for group in groups:
        state.gen[group] = next(_generation)
    state.anchor = stamp
    for key in [k for k, entry in _entries.items() if k[0] == path]:
        entry = _entries[key]
        if kind_of(entry.kind).reads & groups:
            del _entries[key]
            _counters[(entry.kind, "dropped_written")] += 1


def _gens_locked(state: _State, kind: Kind) -> tuple[int, ...]:
    return tuple(state.gen[group] for group in _ordered(kind.reads))


def _generations(store: StudioStore, stamp: Stamp, kind: Kind) -> tuple[Stamp, tuple[int, ...]]:
    """The generations of ``kind``'s groups valid for the store's current state, reconciling a
    stamp that differs from the anchor first (wait for a running window, then I2)."""
    path = stamp[0]
    with _lock:
        state = _states.get(path)
        if state is None:
            state = _states[path] = _new_state(stamp)
        if state.anchor == stamp:
            return stamp, _gens_locked(state, kind)
    # A window of this process may be writing right now: wait for it, then look again. The wait
    # is bounded: a window that does not end in time is taken for a foreign change (fail closed).
    window = _window_lock(path)
    if window.acquire(timeout=_WINDOW_WAIT_S):
        window.release()
    again = store_stamp(store) or stamp
    with _lock:
        state = _states.get(path)
        if state is None or state.anchor != again:
            _rebase_locked(path, again, "foreign")
            state = _states[path]
        return again, _gens_locked(state, kind)


def _checksum(value: object) -> bytes | None:
    if isinstance(value, bytes):
        return hashlib.blake2b(value, digest_size=16).digest()
    try:
        return hashlib.blake2b(pickle.dumps(value, protocol=5), digest_size=16).digest()
    except Exception:  # a value that cannot be pickled is simply not checked
        return None


def _hit_locked(full: tuple[Hashable, ...], entry: _Entry) -> object:
    _entries.move_to_end(full)
    _counters[(entry.kind, "hit")] += 1
    if CHECK and entry.checksum is not None and _checksum(entry.value) != entry.checksum:
        _counters[(entry.kind, "mutated")] += 1
        raise CacheCheckError(f"a remembered {entry.kind!r} value was changed by a caller")
    return entry.value


def cached[T](store: StudioStore, key: tuple[Hashable, ...], compute: Callable[[], T]) -> T:
    """``compute()``, remembered per store file, ``key`` and the generations of the groups the
    key's kind reads. The caller must treat the returned value as read-only (or copy it, see
    ``Kind.seal``). Concurrent calls for the same key and state wait for the first computation
    instead of repeating it.

    Lock order: a computation may ask for other keys (lower levels) but must never be asked for
    back by those (no callback to a higher level), so the key locks form a strict hierarchy and
    two calls cannot wait for each other. Today: ``strength``/``layer_overview``/package sets
    call ``corpus_hits``/``corpus_deck_sets``/``cohort_shapes``, never the other way round. A
    write window never asks for a key (I5), so the window lock never waits for a key lock."""
    name = kind_name(key)
    writing = getattr(_local, "writing", None)
    if writing and store.path is not None and str(store.path) in writing:
        _count(name, "bypass_window")
        return compute()
    stamp = store_stamp(store)
    if stamp is None:
        return compute()
    kind = kind_of(name)
    with _lock:  # the common case in one step: anchor unchanged and the entry still valid
        state = _states.get(stamp[0])
        if state is not None and state.anchor == stamp:
            full = (stamp[0], *key)
            entry = _entries.get(full)
            if entry is not None and entry.gens == _gens_locked(state, kind):
                return cast("T", _hit_locked(full, entry))
    stamp, gens = _generations(store, stamp, kind)
    path = stamp[0]
    full = (path, *key)
    with _lock:
        entry = _entries.get(full)
        if entry is not None:
            if entry.gens == gens:
                return cast("T", _hit_locked(full, entry))
            del _entries[full]
        flight_key = (*full, gens)
        flight = _flights.get(flight_key)
        if flight is None:
            flight = _flights[flight_key] = _KeyLock()
        flight.users += 1
    try:
        with flight.lock:
            with _lock:
                entry = _entries.get(full)
                if entry is not None and entry.gens == gens:  # the caller we waited for
                    return cast("T", _hit_locked(full, entry))
            _count(name, "computed")
            value = compute()
            if getattr(_local, "read_only", False):
                return value
            after = store_stamp(store)
            if after is None or after[0] != path:
                return value
            _, now = _generations(store, after, kind)  # I4
            with _lock:
                state = _states.get(path)
                if now != gens or state is None or _gens_locked(state, kind) != gens:
                    _counters[(name, "not_kept_changed")] += 1
                    return value
                size = len(value) if isinstance(value, bytes) else 0
                checksum = _checksum(value) if CHECK else None
                _entries[full] = _Entry(value, name, gens, size, checksum)
                _apply_kind_limit(full, kind)
                while len(_entries) > MAX_ENTRIES:
                    _counters[(_entries.popitem(last=False)[1].kind, "dropped_limit")] += 1
            return value
    finally:
        with _lock:
            flight.users -= 1
            if flight.users == 0 and _flights.get(flight_key) is flight:
                del _flights[flight_key]


def _apply_kind_limit(full: tuple[Hashable, ...], kind: Kind) -> None:
    """Drop the oldest entries of ``kind``'s limit group beyond its ``KIND_LIMITS`` (never
    ``full`` itself). Called with ``_lock`` held."""
    if kind.limit is None or kind.limit not in KIND_LIMITS:
        return
    max_count, max_bytes = KIND_LIMITS[kind.limit]
    same = [k for k, entry in _entries.items() if kind_of(entry.kind).limit == kind.limit]
    total = sum(_entries[k].size for k in same)
    for old in same[:-1]:
        if len(same) <= max_count and (max_bytes is None or total <= max_bytes):
            break
        entry = _entries.pop(old)
        _counters[(entry.kind, "dropped_limit")] += 1
        same.remove(old)
        total -= entry.size


def invalidate() -> None:
    """Forget every cached figure, this module's (entries, anchors, generations, counters) and
    the data-epoch memo's (``memo.py``)."""
    with _lock:
        _entries.clear()
        _states.clear()
        _counters.clear()
    memo.clear()


def snapshot(store: StudioStore | None = None) -> list[tuple[tuple[Hashable, ...], object]]:
    """The remembered entries as (caller's key, value), oldest first; of ``store``'s file only
    when given. For tests and diagnostics: the values are the shared ones, not copies."""
    path = None if store is None else str(store.path)
    with _lock:
        return [
            (key[1:], entry.value)
            for key, entry in _entries.items()
            if path is None or key[0] == path
        ]


def counters() -> dict[str, int]:
    """Events per kind since the last ``invalidate``, as ``"<kind> <event>"``: ``hit``,
    ``computed``, ``not_kept_changed``, ``bypass_window``, ``dropped_<reason>`` (``written``,
    ``foreign``, ``unproven``, ``undeclared``, ``failed``, ``limit``), ``mutated``; ``*``:
    ``rebase_<reason>`` and ``window_<outcome>``."""
    with _lock:
        return {f"{kind} {event}": count for (kind, event), count in sorted(_counters.items())}


# -- the write side ------------------------------------------------------------------------

_READ_ACTIONS: Final = frozenset(
    {
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_SAVEPOINT,
        sqlite3.SQLITE_RECURSIVE,
    }
)
_ROW_WRITES: Final = frozenset(
    {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
)


# The target table of a row write in a traced statement (``INSERT``/``REPLACE``/``UPDATE``/
# ``DELETE``); only a table of the schema counts as a write to the file.
_ROW_WRITE_TARGET: Final = re.compile(
    r"\b(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|REPLACE\s+INTO|UPDATE(?:\s+OR\s+\w+)?|DELETE\s+FROM)"
    r"\s+(?:MAIN\.)?[\"`\[]?(\w+)"
)


class _Window:
    """One write window: the declared groups and what the authorizer saw written."""

    __slots__ = ("declared", "seen")

    def __init__(self, declared: frozenset[Group]) -> None:
        self.declared = declared
        self.seen: set[Group] = set()

    def authorize(
        self,
        action: int,
        first: str | None,
        second: str | None,
        database: str | None,
        _trigger: str | None,
    ) -> int:
        """Never denies; records the group of every row write, everything else that changes
        the file (DDL, a pragma with a value, ``ATTACH``, ``VACUUM``) as all groups."""
        if action in _READ_ACTIONS:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and second is None:
            return sqlite3.SQLITE_OK  # a pragma read (``data_version``, ``table_info``)
        if database == "temp":
            return sqlite3.SQLITE_OK  # the connection's own temporary tables, not the file
        if action in _ROW_WRITES and database == "main" and first == "sqlite_sequence":
            return sqlite3.SQLITE_OK  # the AUTOINCREMENT bookkeeping of a written table
        group = TABLE_GROUP.get(first or "") if action in _ROW_WRITES else None
        if group is not None and database == "main":
            self.seen.add(group)
        else:
            self.seen.update(Group)
        return sqlite3.SQLITE_OK


def _install_observer(
    connection: sqlite3.Connection,
    observer: Callable[[int, str | None, str | None, str | None, str | None], int] | None,
) -> None:
    """Install (or with ``None`` remove) the window's authorizer. Installing expires every
    statement prepared before, so each statement of the window is seen."""
    connection.set_authorizer(observer)


def _journal_files_absent(path: Path) -> bool:
    return not Path(f"{path}-wal").exists() and not Path(f"{path}-journal").exists()


def _rollback_journal_file(path: Path) -> bool:
    """True for a database file in rollback-journal mode (header bytes 18/19 are 1, not WAL's 2)
    with neither a ``-wal`` nor a ``-journal`` file next to it."""
    try:
        with path.open("rb") as handle:
            header = handle.read(20)
    except OSError:
        return False
    return len(header) == 20 and header[18] == 1 and header[19] == 1 and _journal_files_absent(path)


def _data_version(store: StudioStore) -> int:
    return int(store.connection.execute("PRAGMA data_version").fetchone()[0])


@contextmanager
def write(store: StudioStore, groups: Collection[Group]) -> Iterator[None]:
    """Run one write of the Studio's own (the block) as a window declared to write ``groups``
    (module docstring, I3). Afterwards only the written groups' generations rise when the change
    is provably the block's alone; otherwise everything of the file is dropped. Nested windows
    on the same file join the outer one."""
    declared = frozenset(groups)
    if store.path is None:
        yield
        return
    path = str(store.path)
    open_windows = _writing()
    outer = open_windows.get(path)
    if outer is not None:
        outer.declared = outer.declared | declared
        yield
        return
    with _window_lock(path):
        window = _Window(declared)
        open_windows[path] = window
        try:
            with _window(store, path, window):
                yield
        finally:
            del open_windows[path]


@contextmanager
def _window(store: StudioStore, path: str, window: _Window) -> Iterator[None]:
    connection = store.connection
    provable = not connection.in_transaction and _rollback_journal_file(Path(path))
    version = _data_version(store) if provable else None  # first: later commits are seen
    before = store_stamp(store)
    if before is not None:
        with _lock:
            state = _states.get(path)
            if state is not None and state.anchor != before:
                _rebase_locked(path, before, "foreign")  # I3 (a): a commit before the window
    commits = 0
    changes_at_begin = connection.total_changes
    file_rows = False

    def count(statement: str) -> None:
        # A COMMIT counts when its transaction changed rows of the file: a transaction without
        # such changes (none at all, or only the connection's temporary tables, which
        # ``total_changes`` counts too) does not move the file counter. Either way a miscount
        # only makes the window unproven, which drops everything, never more.
        nonlocal commits, changes_at_begin, file_rows
        word = statement.strip().upper()
        if word.startswith("BEGIN"):
            changes_at_begin = connection.total_changes
            file_rows = False
        elif word == "COMMIT":
            if file_rows and connection.total_changes > changes_at_begin:
                commits += 1
        elif any(table.lower() in TABLE_GROUP for table in _ROW_WRITE_TARGET.findall(word)):
            file_rows = True

    _install_observer(connection, window.authorize)
    connection.set_trace_callback(count)
    failed = True
    try:
        yield
        failed = False
    finally:
        connection.set_trace_callback(None)
        _install_observer(connection, None)
        after = store_stamp(store)  # first the stamp, then the version: nothing slips in between
        same_version = provable and _data_version(store) == version
        _settle(path, window, before, after, failed, same_version, commits)


def _settle(
    path: str,
    window: _Window,
    before: Stamp | None,
    after: Stamp | None,
    failed: bool,
    same_version: bool,
    commits: int,
) -> None:
    """Book a finished window (I3): unchanged file → nothing; proven and declared → the written
    groups rise; anything else → everything of the file is dropped."""
    if before is not None and after == before:
        _count("*", "window_unchanged")
        return
    seen = frozenset(window.seen) if window.seen else ALL  # rows changed, nothing seen: all
    if failed:
        outcome = "failed"
    elif (
        before is None
        or after is None
        or not same_version
        or not _journal_files_absent(Path(path))
        or commits < 1
        or after[0] != before[0]
        or after[1] - before[1] != commits
        or after[4:] != (0, 0)
    ):
        outcome = "unproven"
    elif not seen <= window.declared:
        outcome = "undeclared"
    else:
        outcome = "proven"
    with _lock:
        _counters[("*", f"window_{outcome}")] += 1
        state = _states.get(path)
        if outcome == "proven" and after is not None:
            if state is None:
                _states[path] = _new_state(after)  # nothing remembered for this file yet
            elif state.anchor != before:
                _rebase_locked(path, after, "foreign")
            else:
                _bump_locked(path, seen, after)
        elif state is not None:
            _rebase_locked(path, after, outcome)
    if outcome == "undeclared" and CHECK:
        undeclared = sorted(group.value for group in seen - window.declared)
        raise CacheCheckError(f"a write window wrote undeclared groups {undeclared}")


def _count(kind: str, event: str) -> None:
    with _lock:
        _counters[(kind, event)] += 1


__all__ = [
    "ALL",
    "KINDS",
    "KIND_LIMITS",
    "MAX_ENTRIES",
    "TABLE_GROUP",
    "CacheCheckError",
    "Group",
    "Kind",
    "cached",
    "counters",
    "invalidate",
    "kind_name",
    "kind_of",
    "read_only",
    "snapshot",
    "store_stamp",
    "write",
]
