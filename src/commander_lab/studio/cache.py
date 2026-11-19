"""In-process cache of derived Studio figures, valid exactly as long as the store is unchanged.

A request opens its own connection, so a result cannot be kept on the connection. A cached
value is keyed by the store file's *stamp* — its path, SQLite's file change counter (bumped by
every committed write transaction), size and modification time — plus the caller's own key, so
any import, profile write or mark change that commits makes the next request recompute. An
open transaction (uncommitted changes of this very connection) and an in-memory store bypass
the cache: nothing stale can be served. ``invalidate`` drops everything explicitly (used after
profile writes, where the stamp would catch it anyway).

Concurrent identical requests share one computation: per key one caller computes while the
others wait for it (``_KeyLock``), so a page that fires two routes needing the same figure
pays for it once. A failed computation caches nothing; the next waiter computes itself.

Carried over a known user-state write (#1561). A favourite click commits and so changes the
stamp, which used to drop everything, also figures that only count imported data (seconds to
rebuild). A write route of the Owner's own state (marks, labels, drafts, revisions, primers, new
decks) runs inside ``user_state_write``; afterwards the entries whose kind is declared in
``IMPORT_ONLY`` move from the stamp before the write to the stamp after it, and only when the
origin of the change is beyond doubt:

- before the write: a file store in rollback-journal mode (no ``-wal``, no ``-journal`` file),
  no open transaction;
- after it: no open transaction, still no ``-wal``/``-journal`` file, ``PRAGMA data_version`` of
  the writing connection unchanged (no other connection committed in between) and the file
  change counter risen by exactly the number of ``COMMIT`` statements of this write that
  committed changed rows (at least one).

In every other case (another writer, an import, a failed write, a WAL store, a counter that does
not add up) nothing is carried and everything is dropped as before. A kind that is not declared
behaves as before: a forgotten declaration costs time, never correctness. Each declared kind is
proven: ``tests/unit/test_studio_perf_equivalence.py`` traces the tables its computation reads
(SQLite authorizer) and the tables every wrapped write route writes, and fails when the two
meet or a write route writes a table outside ``USER_STATE_TABLES``. ``strength`` and the
``/api/evidence`` answer are not declared: they read ``card_mark`` and ``card_label`` (through
``builder.pool_cards``), so they stay bound to the stamp. The data epoch of ``memo.py`` is no
substitute (see ``builder._corpus_hits``).
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from . import memo
from .store import StudioStore

MAX_ENTRIES = 48
_lock = threading.Lock()
_entries: OrderedDict[tuple[Hashable, ...], object] = OrderedDict()


class _KeyLock:
    """The lock of one key in flight and how many callers hold or wait for it."""

    __slots__ = ("lock", "users")

    def __init__(self) -> None:
        self.lock = threading.RLock()  # re-entrant: a computation may ask for its own key
        self.users = 0


_flights: dict[tuple[Hashable, ...], _KeyLock] = {}
_local = threading.local()


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


def store_stamp(store: StudioStore) -> tuple[str, int, int, int, int, int] | None:
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


def cached[T](store: StudioStore, key: tuple[Hashable, ...], compute: Callable[[], T]) -> T:
    """``compute()``, remembered per store state and ``key``. The caller must treat the
    returned value as read-only. Concurrent calls for the same state and key wait for the
    first computation instead of repeating it.

    Lock order: a computation may ask for other keys (lower levels) but must never be asked for
    back by those (no callback to a higher level), so the key locks form a strict hierarchy and
    two calls cannot wait for each other. Today: ``strength``/``layer_overview``/package sets
    call ``corpus_hits``/``corpus_deck_sets``/``cohort_shapes``, never the other way round."""
    stamp = store_stamp(store)
    if stamp is None:
        return compute()
    full = (stamp, *key)
    with _lock:
        if full in _entries:
            _entries.move_to_end(full)
            return cast("T", _entries[full])
        flight = _flights.get(full)
        if flight is None:
            flight = _flights[full] = _KeyLock()
        flight.users += 1
    try:
        with flight.lock:
            with _lock:
                if full in _entries:  # the caller we waited for has filled it
                    _entries.move_to_end(full)
                    return cast("T", _entries[full])
            value = compute()
            if getattr(_local, "read_only", False):
                return value
            # The state may have changed while computing; remember only if it is still the same.
            if store_stamp(store) == stamp:
                with _lock:
                    # Entries of another state of this very file are not served for the
                    # current one: drop them now instead of letting large values wait for
                    # the size limit.
                    for old in [
                        k
                        for k in _entries
                        if isinstance(k[0], tuple) and k[0][:1] == stamp[:1] and k[0] != stamp
                    ]:
                        del _entries[old]
                    _entries[full] = value
                    while len(_entries) > MAX_ENTRIES:
                        _entries.popitem(last=False)
            return value
    finally:
        with _lock:
            flight.users -= 1
            if flight.users == 0 and _flights.get(full) is flight:
                del _flights[full]


def invalidate() -> None:
    """Forget every cached figure, this module's and the data-epoch memo's (``memo.py``)."""
    with _lock:
        _entries.clear()
    memo.clear()


# The kinds of entry (first element of the caller's key) whose computation reads imported data
# only, never the Owner's state: carried over a known user-state write. Every kind here needs a
# traced proof in the tests (see the module docstring). ``land_source_groups``: the land figures
# of the commander's source-deck groups (``land_advisor.source_deck_groups``).
IMPORT_ONLY: frozenset[str] = frozenset({"land_source_groups"})

# The tables holding the Owner's state. A wrapped write route may write only these, and an
# ``IMPORT_ONLY`` computation may read none of them (both proven by the tests).
USER_STATE_TABLES: frozenset[str] = frozenset(
    {
        "card_label", "card_mark", "deck", "deck_branch", "deck_draft", "deck_label",
        "deck_module", "deck_module_card", "deck_primer", "deck_revision", "deck_revision_card",
        "strength_profile", "tier_snapshot", "universe_profile",
    }
)  # fmt: skip


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
def user_state_write(store: StudioStore) -> Iterator[None]:
    """Run one write of the Owner's own state (the block) and afterwards carry the
    ``IMPORT_ONLY`` entries of the state before it over to the state after it, when the change
    is provably this block's alone (module docstring). On an error inside the block nothing is
    carried."""
    path = store.path
    origin: tuple[tuple[str, int, int, int, int, int], int] | None = None
    if path is not None and not store.connection.in_transaction and _rollback_journal_file(path):
        version = _data_version(store)  # first: a commit by others after this point is seen
        before = store_stamp(store)
        if before is not None:
            origin = (before, version)
    commits = 0
    changes_at_begin = store.connection.total_changes

    def count(statement: str) -> None:
        # A COMMIT counts when its transaction changed rows: a transaction without changes
        # does not move the file counter (a mismatch only drops everything, never more).
        nonlocal commits, changes_at_begin
        word = statement.strip().upper()
        if word.startswith("BEGIN"):
            changes_at_begin = store.connection.total_changes
        elif word == "COMMIT" and store.connection.total_changes > changes_at_begin:
            commits += 1

    if origin is not None:
        store.connection.set_trace_callback(count)
    try:
        yield
    finally:
        if origin is not None:
            store.connection.set_trace_callback(None)
    if origin is None or path is None:
        return
    before, version = origin
    after = store_stamp(store)  # first the stamp, then the version: nothing slips in between
    if (
        after is None
        or _data_version(store) != version
        or not _journal_files_absent(path)
        or commits < 1
        or after[0] != before[0]
        or after[1] - before[1] != commits
        or after[4:] != (0, 0)
    ):
        return
    _carry(before, after)


def _carry(before: tuple[Hashable, ...], after: tuple[Hashable, ...]) -> None:
    """Re-key the ``IMPORT_ONLY`` entries of stamp ``before`` to stamp ``after``."""
    with _lock:
        for key in [k for k in _entries if k[0] == before and len(k) > 1 and k[1] in IMPORT_ONLY]:
            value = _entries.pop(key)
            _entries[(after, *key[1:])] = value


__all__ = [
    "IMPORT_ONLY",
    "USER_STATE_TABLES",
    "cached",
    "invalidate",
    "store_stamp",
    "user_state_write",
]
