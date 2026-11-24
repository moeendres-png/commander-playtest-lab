"""Export and import of the Studio user state, format ``studio-user-state-1`` (#1668, K-2a).

The file is a gzip-compressed JSON envelope::

    {"format": "studio-user-state-1", "source_schema_version": 21, "created_at": "...",
     "content_sha256": "<hex>", "content": {"tables": {...}, "not_in_schema": [...]}}

``content`` holds the user tables of the store (decks, revisions with their cards, branches,
drafts, labels, primers, modules, marks, profiles) as rows, every card reference written as
``card_id`` plus ``oracle_id`` plus ``name``. ``content_sha256`` is the SHA-256 of the canonical
JSON of ``content`` alone, so the creation time does not change it. Import tables (the card
catalogue, corpus, observations, ...) are never part of it. A card that is referenced but has no
``oracle_id`` stops the export with the list; nothing is guessed. The specification is
``docs/STUDIO_STATE_EXPORT_FORMAT.md``.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import cache
from .instance_lock import resolve_data_folder
from .store import DataClass, StudioStore, _repository_root

FORMAT_V1 = "studio-user-state-1"
FORMAT = "studio-user-state-2"
SUPPORTED_FORMATS = (FORMAT_V1, FORMAT)
EXPORT_SUBFOLDER = "state-exports"
COPY_PREFIX = "studio-state-"
COPY_SUFFIX = ".json.gz"
KEEP_COPIES = 14
STUB_EVIDENCE = "state_import_stub"
META_IMPORT_KEY = "user_state_import_sha256"
# Sections the target model names for later (the Owner's decision E15) that schema 21 has no
# table for: they are listed, never written as an empty section (absent is unknown, not zero).
NOT_IN_SCHEMA = ("setting", "table_preset")
BLOCKED_SHOWN = 50
# Tables that hold user-produced or index rows not part of the format
# (``docs/STUDIO_STATE_EXPORT_FORMAT.md`` §2.3, #1668, #1703 K-2a2): ``simulation_run`` and
# ``simulation_card`` are SIMULATE legacy results; ``experiment`` and ``experiment_arm`` are
# rebuildable indices over ``games/experiments/<id>/plan.json`` (``experiments.rebuild_index``).
# Export, import and the start copy name how many rows they leave out.
NOT_EXPORTED = ("simulation_run", "simulation_card", "experiment", "experiment_arm")

_COPY_NAME = re.compile(r"^studio-state-(\d{8}-\d{6})(?:-(\d+))?\.json\.gz$")


class StateFileError(ValueError):
    """The file is not a usable ``studio-user-state-1``/``-2`` file, or the target cannot take it."""


class ExportBlocked(ValueError):
    """The export stops: ``blocked`` lists what cannot be written without guessing."""

    def __init__(self, blocked: list[dict[str, object]]) -> None:
        super().__init__(f"{len(blocked)} Verweis(e) ohne belegte Karten-Identität")
        self.blocked = blocked


@dataclass(frozen=True, slots=True)
class _Table:
    name: str
    cards: bool = False  # rows carry a ``card_id`` column
    draft: bool = False  # the ``cards`` column is a JSON list of card entries
    source: bool = False  # only rows referenced by ``deck_revision.source_id``


# Dependency order; foreign keys are checked at commit on import.
_TABLES_V1: tuple[_Table, ...] = (
    _Table("source", source=True),
    _Table("deck"),
    _Table("deck_revision"),
    _Table("deck_revision_card", cards=True),
    _Table("deck_branch"),
    _Table("deck_draft", draft=True),
    _Table("deck_label"),
    _Table("deck_primer"),
    _Table("deck_module"),
    _Table("deck_module_card", cards=True),
    _Table("card_mark", cards=True),
    _Table("card_label", cards=True),
    _Table("strength_profile"),
    _Table("universe_profile"),
)
# studio-user-state-2 (#1703 K-2a2): adds manual TAM guide prices (keyed directly by oracle_id).
_TABLES: tuple[_Table, ...] = (
    *_TABLES_V1,
    _Table("tam_cardmarket_price"),
)
_TABLE_NAMES_V1 = frozenset(table.name for table in _TABLES_V1)
_TABLE_NAMES = frozenset(table.name for table in _TABLES)
_USER_ONLY = tuple(table for table in _TABLES if not table.source)
_CARD_KEYS = ("oracle_id", "name")
_DEFAULT_DRAFT_KEYS = ("card_id", "quantity", "zone")


# -- canonical form ----------------------------------------------------------------------------


def canonical_bytes(content: object) -> bytes:
    """The bytes the content hash is taken over: sorted keys, no spaces, UTF-8, no NaN."""
    return json.dumps(
        content, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def content_sha256(content: object) -> str:
    return hashlib.sha256(canonical_bytes(content)).hexdigest()


def _as_dict(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise StateFileError(f"{what}: Objekt erwartet")
    return {str(key): item for key, item in value.items()}


def _as_list(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise StateFileError(f"{what}: Liste erwartet")
    return list(value)


# -- reading the store -------------------------------------------------------------------------


def _columns(db: sqlite3.Connection, table: str) -> tuple[list[str], list[str]]:
    """All column names and the primary-key columns (in key order) of a known table."""
    if table not in _TABLE_NAMES:
        raise StateFileError(f"unbekannte Tabelle: {table}")
    info = db.execute(f"PRAGMA table_info({table})").fetchall()
    names = [str(row[1]) for row in info]
    keys = [str(row[1]) for row in sorted((r for r in info if r[5] > 0), key=lambda r: r[5])]
    return names, keys


def _card_refs(db: sqlite3.Connection, card_ids: set[str]) -> dict[str, tuple[str | None, str]]:
    refs: dict[str, tuple[str | None, str]] = {}
    ordered = sorted(card_ids)
    for start in range(0, len(ordered), 400):
        chunk = ordered[start : start + 400]
        marks = ",".join("?" for _ in chunk)
        for row in db.execute(
            f"SELECT card_id, oracle_id, oracle_name FROM card WHERE card_id IN ({marks})", chunk
        ):
            oracle = str(row[1]) if row[1] else None
            refs[str(row[0])] = (oracle, str(row[2]))
    return refs


def _sort_key(row: dict[str, object], keys: list[str]) -> str:
    return json.dumps([row.get(key) for key in keys], sort_keys=True, ensure_ascii=False)


def _fetch_rows(db: sqlite3.Connection, table: _Table) -> tuple[list[dict[str, object]], list[str]]:
    names, keys = _columns(db, table.name)
    if table.source:
        query = (
            "SELECT * FROM source WHERE source_id IN "
            "(SELECT source_id FROM deck_revision WHERE source_id IS NOT NULL)"
        )
    else:
        query = f"SELECT * FROM {table.name}"
    return [dict(zip(names, row, strict=True)) for row in db.execute(query)], keys


def _draft_entries(raw: object) -> list[dict[str, object]] | None:
    try:
        loaded = json.loads(str(raw))
    except (TypeError, ValueError):
        return None
    if not isinstance(loaded, list) or not all(isinstance(e, dict) for e in loaded):
        return None
    return [{str(k): v for k, v in entry.items()} for entry in loaded]


@contextlib.contextmanager
def _read_snapshot(db: sqlite3.Connection) -> Iterator[None]:
    """One read transaction around every table read, so a commit of a running server between two
    reads cannot give a file with a valid SHA but an inconsistent content. Inside an open
    transaction (the import's re-export) it changes nothing."""
    if db.in_transaction:
        yield
        return
    db.execute("BEGIN")
    try:
        yield
    finally:
        db.execute("ROLLBACK")


def not_exported_rows(db: sqlite3.Connection) -> dict[str, int | None]:
    """Rows per table that the format leaves out; ``None`` (unknown, never 0) if not countable."""
    counted: dict[str, int | None] = {}
    for name in NOT_EXPORTED:
        try:
            counted[name] = int(db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
        except (sqlite3.Error, TypeError, ValueError):
            counted[name] = None
    return counted


def not_exported_line(value: object) -> str:
    """The one report line; a missing or uncountable number reads ``unbekannt``."""
    numbers = [value.get(name) if isinstance(value, dict) else None for name in NOT_EXPORTED]
    known = all(isinstance(n, int) and not isinstance(n, bool) for n in numbers)
    shown = str(sum(n for n in numbers if isinstance(n, int))) if known else "unbekannt"
    return f"Nicht exportierte Zeilen aus {'/'.join(NOT_EXPORTED)}: {shown}"


def build_content(
    db: sqlite3.Connection,
    *,
    tables_spec: tuple[_Table, ...] = _TABLES,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """The content of the export and the list of references that block it (one read snapshot)."""
    with _read_snapshot(db):
        return _build_content(db, tables_spec=tables_spec)


def _build_content(
    db: sqlite3.Connection,
    *,
    tables_spec: tuple[_Table, ...] = _TABLES,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    blocked: list[dict[str, object]] = []
    fetched: dict[str, tuple[list[dict[str, object]], list[str]]] = {}
    wanted: set[str] = set()
    for table in tables_spec:
        rows, keys = _fetch_rows(db, table)
        fetched[table.name] = (rows, keys)
        if table.cards:
            wanted.update(str(row["card_id"]) for row in rows)
        if table.draft:
            for row in rows:
                for entry in _draft_entries(row["cards"]) or []:
                    if isinstance(entry.get("card_id"), str):
                        wanted.add(str(entry["card_id"]))
    refs = _card_refs(db, wanted)

    def resolve(card_id: str, where: dict[str, object]) -> tuple[str, str] | None:
        found = refs.get(card_id)
        if found is None:
            blocked.append({**where, "card_id": card_id, "reason": "no_card_row"})
            return None
        oracle, name = found
        if oracle is None:
            blocked.append({**where, "card_id": card_id, "name": name, "reason": "no_oracle_id"})
            return None
        return oracle, name

    tables: dict[str, object] = {}
    for table in tables_spec:
        rows, keys = fetched[table.name]
        out: list[dict[str, object]] = []
        for row in rows:
            where: dict[str, object] = {
                "table": table.name,
                "key": [row.get(key) for key in keys],
            }
            if any(isinstance(value, bytes) for value in row.values()):
                blocked.append({**where, "reason": "blob_value"})
                continue
            if table.cards:
                resolved = resolve(str(row["card_id"]), where)
                if resolved is None:
                    continue
                row = {**row, "oracle_id": resolved[0], "name": resolved[1]}
            if table.draft:
                entries = _draft_entries(row["cards"])
                if entries is None:
                    blocked.append({**where, "reason": "draft_unreadable"})
                    continue
                enriched: list[dict[str, object]] = []
                for entry in entries:
                    card_id = entry.get("card_id")
                    if not isinstance(card_id, str) or any(key in entry for key in _CARD_KEYS):
                        blocked.append({**where, "reason": "draft_entry_unreadable"})
                        continue
                    resolved = resolve(card_id, where)
                    if resolved is not None:
                        enriched.append({**entry, "oracle_id": resolved[0], "name": resolved[1]})
                row = {**row, "cards": enriched}
            out.append(row)
        out.sort(key=lambda r: _sort_key(r, keys))
        tables[table.name] = out
    return {"tables": tables, "not_in_schema": list(NOT_IN_SCHEMA)}, blocked


@dataclass(frozen=True, slots=True)
class Preflight:
    """What the export would stop on, and the collection cards without ``oracle_id``."""

    blocked: list[dict[str, object]]
    collection_total: int
    collection_missing: list[dict[str, object]]
    not_exported: dict[str, int | None]

    @property
    def ok(self) -> bool:
        return not self.blocked


def preflight(store: StudioStore) -> Preflight:
    """Report before exporting. Collection cards (a row in ``inventory``) without
    ``oracle_id`` are counted n of N; they block only when the user state references them."""
    db = store.connection
    with _read_snapshot(db):
        _content, blocked = build_content(db)
        total = int(db.execute("SELECT COUNT(*) FROM inventory").fetchone()[0])
        missing: list[dict[str, object]] = [
            {"card_id": str(row[0]), "name": str(row[1])}
            for row in db.execute(
                "SELECT c.card_id, c.oracle_name FROM card c JOIN inventory i USING (card_id) "
                "WHERE c.oracle_id IS NULL OR c.oracle_id = '' ORDER BY c.card_id"
            )
        ]
        not_exported = not_exported_rows(db)
    return Preflight(blocked, total, missing, not_exported)


def counts(content: dict[str, object]) -> dict[str, int]:
    tables = _as_dict(content.get("tables"), "content.tables")
    return {name: len(_as_list(rows, name)) for name, rows in sorted(tables.items())}


# -- writing the file --------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _write_gzip(path: Path, envelope: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    data = json.dumps(envelope, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    try:
        with temporary.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            gz.write(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def export_state(store: StudioStore, path: Path) -> dict[str, object]:
    """Write the user state to ``path`` (atomically) and return the header facts.

    Raises ``ExportBlocked`` with the list when a referenced card has no ``oracle_id``."""
    db = store.connection
    with _read_snapshot(db):
        content, blocked = build_content(db)
        if blocked:
            raise ExportBlocked(blocked)
        version_row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        not_exported = not_exported_rows(db)
    sha = content_sha256(content)
    envelope: dict[str, object] = {
        "format": FORMAT,
        "source_schema_version": int(version_row[0]) if version_row else None,
        "created_at": _now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "content_sha256": sha,
        "not_exported_rows": not_exported,
        "content": content,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_gzip(path, envelope)
    return {
        "path": str(path),
        "content_sha256": sha,
        "rows": counts(content),
        "not_exported_rows": not_exported,
    }


# -- reading the file --------------------------------------------------------------------------


def _tables_for_format(fmt: str) -> tuple[_Table, ...]:
    if fmt == FORMAT_V1:
        return _TABLES_V1
    if fmt == FORMAT:
        return _TABLES
    raise StateFileError(
        f"unbekanntes Format {fmt!r}, erwartet eines von {', '.join(SUPPORTED_FORMATS)}"
    )


@dataclass(frozen=True, slots=True)
class StateFile:
    declared_sha256: str
    source_schema_version: object
    created_at: object
    content: dict[str, object]
    not_exported_rows: object = None
    format: str = FORMAT

    @property
    def computed_sha256(self) -> str:
        return content_sha256(self.content)


def _check_sha(state: StateFile) -> None:
    if state.declared_sha256 != state.computed_sha256:
        raise StateFileError(
            "Die Prüfsumme der Datei stimmt nicht mit dem Inhalt überein "
            f"(angegeben {state.declared_sha256[:12]}…, berechnet {state.computed_sha256[:12]}…): "
            "die Datei ist verändert oder beschädigt, nichts wurde importiert."
        )


def read_state(path: Path, *, verify: bool = True) -> StateFile:
    """Read and validate the envelope; ``verify`` checks the SHA-256 over the content."""
    try:
        with gzip.open(path, "rb") as handle:
            loaded = json.loads(handle.read().decode("utf-8"))
    except (OSError, EOFError, ValueError) as error:
        raise StateFileError(f"{path}: keine lesbare gz-JSON-Datei ({error})") from error
    envelope = _as_dict(loaded, "Datei")
    fmt = envelope.get("format")
    if not isinstance(fmt, str) or fmt not in SUPPORTED_FORMATS:
        raise StateFileError(
            f"unbekanntes Format {fmt!r}, erwartet eines von {', '.join(SUPPORTED_FORMATS)}"
        )
    declared = envelope.get("content_sha256")
    if not isinstance(declared, str) or not re.fullmatch(r"[0-9a-f]{64}", declared):
        raise StateFileError("content_sha256 fehlt oder ist keine SHA-256")
    state = StateFile(
        declared,
        envelope.get("source_schema_version"),
        envelope.get("created_at"),
        _as_dict(envelope.get("content"), "content"),
        envelope.get("not_exported_rows"),
        fmt,
    )
    if verify:
        _check_sha(state)
    return state


def verify_state_file(path: Path) -> dict[str, object]:
    """The ``--verify`` report: SHA checked, rows per table, nothing written."""
    state = read_state(path)
    allowed_names = frozenset(table.name for table in _tables_for_format(state.format))
    tables = _as_dict(state.content.get("tables"), "content.tables")
    unknown = sorted(set(tables) - allowed_names)
    if unknown:
        raise StateFileError(f"Tabellen ohne Ziel in diesem Schema: {unknown}")
    return {
        "format": state.format,
        "content_sha256": state.declared_sha256,
        "sha_ok": True,
        "source_schema_version": state.source_schema_version,
        "rows": counts(state.content),
        "not_in_schema": state.content.get("not_in_schema"),
        "not_exported_rows": state.not_exported_rows,
    }


# -- import ------------------------------------------------------------------------------------


def _user_row_counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        table.name: int(db.execute(f"SELECT COUNT(*) FROM {table.name}").fetchone()[0])
        for table in _USER_ONLY
    }


def _insert(db: sqlite3.Connection, table: str, row: dict[str, object], allowed: set[str]) -> None:
    columns = sorted(row)
    extra = [column for column in columns if column not in allowed]
    if extra:
        raise StateFileError(f"{table}: Spalten ohne Ziel im Schema: {extra}")
    marks = ",".join("?" for _ in columns)
    verb = "INSERT OR IGNORE" if table == "source" else "INSERT"
    try:
        db.execute(
            f"{verb} INTO {table}({','.join(columns)}) VALUES ({marks})",
            [row[column] for column in columns],
        )
    except sqlite3.IntegrityError as error:
        raise StateFileError(f"{table}: Zeile nicht einfügbar ({error})") from error


def _plan_cards(
    tables: dict[str, object],
    *,
    tables_spec: tuple[_Table, ...] = _TABLES,
) -> dict[str, tuple[str, str]]:
    """Every referenced card of the file as card_id -> (oracle_id, name)."""
    found: dict[str, tuple[str, str]] = {}

    def note(entry: dict[str, object], where: str) -> None:
        card_id, oracle, name = entry.get("card_id"), entry.get("oracle_id"), entry.get("name")
        if not (isinstance(card_id, str) and isinstance(oracle, str) and isinstance(name, str)):
            raise StateFileError(f"{where}: Karte ohne card_id, oracle_id und name")
        if found.setdefault(card_id, (oracle, name)) != (oracle, name):
            raise StateFileError(f"{where}: {card_id} nennt zwei verschiedene Identitäten")

    for table in tables_spec:
        for raw in _as_list(tables.get(table.name, []), table.name):
            row = _as_dict(raw, table.name)
            if table.cards:
                note(row, table.name)
            if table.draft:
                for item in _as_list(row.get("cards"), "deck_draft.cards"):
                    note(_as_dict(item, "deck_draft.cards"), table.name)
    return found


def _row_for_table(table: _Table, row: dict[str, object]) -> dict[str, object]:
    if table.cards:
        return {k: v for k, v in row.items() if k not in _CARD_KEYS}
    if table.draft:
        entries = [
            {k: v for k, v in _as_dict(entry, "deck_draft.cards").items() if k not in _CARD_KEYS}
            for entry in _as_list(row.get("cards"), "deck_draft.cards")
        ]
        return {**row, "cards": json.dumps(entries)}
    return row


def import_state(store: StudioStore, path: Path) -> dict[str, object]:
    """Read ``path`` into the user tables of ``store``, which must hold no user state yet.

    Accepts both ``studio-user-state-1`` and ``studio-user-state-2``. The SHA is checked before
    any write. Inside one transaction the rows are inserted, cards the target does not know get a
    stub row (``identity_evidence`` ``state_import_stub``, facts come from the next card-data
    import), and the result is exported again in memory using the input file's table spec: it
    must hash like the file's content, otherwise everything is rolled back."""
    state = read_state(path)
    tables_spec = _tables_for_format(state.format)
    allowed_names = frozenset(table.name for table in tables_spec)
    tables = _as_dict(state.content.get("tables"), "content.tables")
    unknown = sorted(set(tables) - allowed_names)
    if unknown:
        raise StateFileError(f"Tabellen ohne Ziel in diesem Schema: {unknown}")
    db = store.connection
    present = {name: n for name, n in _user_row_counts(db).items() if n}
    if present:
        raise StateFileError(
            f"Der Zielspeicher hat schon Nutzerdaten ({present}); der Import braucht einen "
            "frischen Datenordner."
        )
    plan = _plan_cards(tables, tables_spec=tables_spec)
    expected = state.computed_sha256
    stubs = 0
    # ``defer_foreign_keys`` is a pragma with a value, which the cache window counts as a write
    # to every group: the import declares the whole file.
    with cache.write(store, cache.ALL):
        db.commit()  # the target is unused; end any open implicit transaction of the open
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("PRAGMA defer_foreign_keys=ON")
            stub_source: str | None = None
            for card_id, (oracle, name) in sorted(plan.items()):
                existing = db.execute(
                    "SELECT oracle_id FROM card WHERE card_id = ?", (card_id,)
                ).fetchone()
                if existing is None:
                    if stub_source is None:
                        stub_source = store.register_source(
                            data_class=DataClass.UNKNOWN,
                            title=f"{state.format} import (card stubs)",
                            sha256=expected,
                        )
                    db.execute(
                        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, "
                        "identity_evidence, source_id) VALUES (?, ?, ?, '', ?, ?)",
                        (card_id, oracle, name, STUB_EVIDENCE, stub_source),
                    )
                    stubs += 1
                elif existing[0] != oracle:
                    raise StateFileError(
                        f"Karte {card_id}: der Zielspeicher hat die oracle_id {existing[0]!r}, "
                        f"die Datei {oracle!r}; es wird nicht geraten."
                    )
            for table in tables_spec:
                allowed = set(_columns(db, table.name)[0])
                for raw in _as_list(tables.get(table.name, []), table.name):
                    row = _row_for_table(table, _as_dict(raw, table.name))
                    _insert(db, table.name, row, allowed)
            db.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (META_IMPORT_KEY, expected),
            )
            again, blocked = (
                build_content(db)
                if tables_spec == _TABLES
                else build_content(db, tables_spec=tables_spec)
            )
            if blocked or content_sha256(again) != expected:
                differing = sorted(
                    name
                    for name in allowed_names
                    if _as_dict(again.get("tables"), "content").get(name) != tables.get(name, [])
                )
                raise StateFileError(
                    "Der Import ist nicht verlustfrei (erneuter Export ≠ Datei); zurückgerollt. "
                    f"Abweichende Tabellen: {differing}"
                )
            try:
                db.execute("COMMIT")
            except sqlite3.IntegrityError as error:
                raise StateFileError(
                    "Die Datei ist in sich nicht schlüssig (Fremdschlüssel beim Abschluss: "
                    f"{error}); zurückgerollt, nichts importiert."
                ) from error
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    return {
        "format": state.format,
        "content_sha256": expected,
        "rows": counts(state.content),
        "card_stubs": stubs,
        "not_exported_rows": state.not_exported_rows,
    }


# -- copies at server start ---------------------------------------------------------------------


def _copy_order(name: str) -> tuple[str, int] | None:
    match = _COPY_NAME.match(name)
    if match is None:
        return None
    return match.group(1), int(match.group(2) or 1)


def rotate_copies(folder: Path, keep: int | None = None) -> list[Path]:
    """Delete the oldest copies beyond ``keep`` (default ``KEEP_COPIES``); other files stay."""
    limit = KEEP_COPIES if keep is None else keep
    copies = sorted(
        (path for path in folder.iterdir() if _copy_order(path.name) is not None),
        key=lambda path: _copy_order(path.name) or ("", 0),
    )
    removed = copies[: max(len(copies) - limit, 0)]
    for path in removed:
        path.unlink(missing_ok=True)
    return removed


def _new_copy_path(folder: Path) -> Path:
    """A name that sorts after every copy of the same second, even after rotation removed one."""
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    taken = [
        order[1]
        for order in (_copy_order(path.name) for path in folder.iterdir())
        if order is not None and order[0] == stamp
    ]
    number = max(taken) + 1 if taken else 1
    suffix = "" if number == 1 else f"-{number}"
    return folder / f"{COPY_PREFIX}{stamp}{suffix}{COPY_SUFFIX}"


def _start_copy(store: StudioStore, data_folder: Path) -> dict[str, object]:
    folder = data_folder / EXPORT_SUBFOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = _new_copy_path(folder)
    header = export_state(store, path)
    rotate_copies(folder)
    return header


def write_start_copy(store: StudioStore, data_folder: Path) -> Path:
    """One export copy in ``<data>/state-exports/``, then rotation to the last ``KEEP_COPIES``.

    A blocked export writes nothing and rotates nothing (``ExportBlocked``): the older copies stay."""
    return Path(str(_start_copy(store, data_folder)["path"]))


def start_copy_best_effort(data: str | Path | None) -> None:
    """The server start's copy: a failure is one line on stderr and never stops the server."""
    try:
        folder = resolve_data_folder(data)
        store = StudioStore.open(folder)
        try:
            header = _start_copy(store, folder)
        finally:
            store.close()
        print(f"Zustands-Kopie: {header['path']}")
        print(not_exported_line(header["not_exported_rows"]))
    except ExportBlocked as error:
        print(
            f"Zustands-Kopie nicht angelegt: {len(error.blocked)} Verweis(e) ohne oracle_id "
            "(Liste: studio export-state --check).",
            file=sys.stderr,
        )
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        print(f"Zustands-Kopie nicht angelegt: {type(error).__name__}", file=sys.stderr)


# -- commands ----------------------------------------------------------------------------------


def _print_blocked(blocked: list[dict[str, object]]) -> None:
    for item in blocked[:BLOCKED_SHOWN]:
        print("  " + json.dumps(item, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    if len(blocked) > BLOCKED_SHOWN:
        print(f"  … und {len(blocked) - BLOCKED_SHOWN} weitere", file=sys.stderr)


def _outside_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.is_relative_to(_repository_root()):
        raise StateFileError(f"Nutzerdaten gehören nicht ins Repository: {resolved}")
    return resolved


def run_export_command(args: argparse.Namespace) -> int:
    """``export-state``: write the file, or with ``--check`` only report what would block."""
    folder = resolve_data_folder(args.data)
    store = StudioStore.open(folder)
    try:
        if args.check:
            report = preflight(store)
            total = report.collection_total
            print(
                f"Sammlungskarten ohne oracle_id: {len(report.collection_missing)} von {total} "
                "(blockieren nur, wenn der Nutzerzustand sie nennt)"
            )
            if report.blocked:
                print(
                    f"Export blockiert: {len(report.blocked)} Verweis(e):",
                    file=sys.stderr,
                )
                _print_blocked(report.blocked)
                return 2
            print("Export möglich: keine Verweise ohne oracle_id.")
            print(not_exported_line(report.not_exported))
            return 0
        target = _outside_repository(Path(args.to) if args.to else folder / EXPORT_SUBFOLDER)
        if target.is_dir() or not target.suffix:
            target.mkdir(parents=True, exist_ok=True)
            target = _new_copy_path(target)
        try:
            header = export_state(store, target)
        except ExportBlocked as error:
            print(f"Export abgebrochen: {error}. Keine Datei geschrieben.", file=sys.stderr)
            _print_blocked(error.blocked)
            return 2
        if args.json:
            print(json.dumps(header, indent=2, ensure_ascii=False))
        else:
            print(f"{header['path']}\ncontent_sha256 {header['content_sha256']}")
            print(not_exported_line(header["not_exported_rows"]))
        return 0
    finally:
        store.close()


def run_import_command(args: argparse.Namespace) -> int:
    """``import-state``: ``--verify`` checks and reports only; otherwise import into the store."""
    path = Path(args.file)
    try:
        if args.verify:
            report = verify_state_file(path)
        else:
            store = StudioStore.open(resolve_data_folder(args.data))
            try:
                report = import_state(store, path)
            finally:
                store.close()
    except StateFileError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        rows = report["rows"]
        print(f"content_sha256 {report['content_sha256']}")
        if isinstance(rows, dict):
            for name, number in rows.items():
                print(f"  {name}: {number}")
        if "card_stubs" in report:
            print(f"Karten-Stubs angelegt: {report['card_stubs']}")
        print(not_exported_line(report.get("not_exported_rows")))
    return 0
