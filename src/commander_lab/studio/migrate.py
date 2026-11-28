"""``migrate --dry-run``: what the next open would do to a Studio store, shown on a copy.

Schema 22a (#1703, #1856; Owner decision 2026-11-28). The real store is only read (a read-only
connection and the SQLite backup API); the migration runs on a copy in a temporary folder that
is removed afterwards. A real migration happens on the next ``StudioStore.open``, after the
mandatory backup (``store._backup_before_migration``).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from .state_export import StateFileError, build_content, content_sha256
from .store import DATABASE_NAME, SCHEMA_VERSION, StudioStore, stored_schema_version

REAL_MIGRATION_NOTE = (
    "A real migration happens on the next open of the store, after a mandatory backup into "
    "<data folder>-backups/pre-schema-<N>-<utc>. Nothing was changed. "
    "Use `migrate --dry-run` to preview it on a copy."
)


def _tables(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        name: int(connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
        for name in _tables(connection)
    }


def _column_names(connection: sqlite3.Connection) -> dict[str, list[str]]:
    return {
        name: [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{name}")')]
        for name in _tables(connection)
    }


def _state_export_sha256(connection: sqlite3.Connection) -> str | None:
    """SHA-256 of the state export content; ``None`` (unknown) if it cannot be built."""
    try:
        content, blocked = build_content(connection)
    except (sqlite3.Error, StateFileError):
        return None
    return None if blocked else content_sha256(content)


def dry_run(data_folder: str | Path) -> dict[str, object]:
    """Migrate a copy of the store and report; the real store is never written."""
    source = Path(data_folder).expanduser().resolve() / DATABASE_NAME
    if not source.is_file():
        raise FileNotFoundError(f"Studio store not found: {source}")
    current = stored_schema_version(source)
    if current is None:
        raise ValueError(f"{source} has no schema version: nothing to migrate")
    if current > SCHEMA_VERSION:
        raise ValueError(f"Studio store has schema {current}, this code needs {SCHEMA_VERSION}")
    with tempfile.TemporaryDirectory(prefix="studio-migrate-dry-run-") as temporary:
        copy = Path(temporary) / DATABASE_NAME
        original = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=30)
        try:
            destination = sqlite3.connect(copy)
            try:
                original.backup(destination)
            finally:
                destination.close()
        finally:
            original.close()
        connection = sqlite3.connect(copy)
        try:
            before_counts = _row_counts(connection)
            before_columns = _column_names(connection)
            sha_before = _state_export_sha256(connection)
            connection.close()
            migrated = StudioStore._prepare(sqlite3.connect(copy))
            try:
                after_counts = _row_counts(migrated)
                after_columns = _column_names(migrated)
                integrity = str(migrated.execute("PRAGMA integrity_check").fetchone()[0])
                sha_after = _state_export_sha256(migrated)
            finally:
                migrated.close()
        finally:
            connection.close()
    tables = {
        name: {"before": before_counts.get(name), "after": after_counts.get(name)}
        for name in sorted({*before_counts, *after_counts})
    }
    columns_added = {
        name: [column for column in columns if column not in before_columns.get(name, [])]
        for name, columns in after_columns.items()
        if any(column not in before_columns.get(name, []) for column in columns)
    }
    return {
        "store": str(source),
        "current_version": current,
        "target_version": SCHEMA_VERSION,
        "tables": tables,
        "tables_created": sorted(set(after_counts) - set(before_counts)),
        "columns_added": columns_added,
        "integrity_check": integrity,
        "state_export_sha256": {"before": sha_before, "after": sha_after},
        "real_store_written": False,
    }


def format_report(report: dict[str, object]) -> str:
    """The human-readable form of ``dry_run``."""
    tables = report["tables"]
    added = report["columns_added"]
    sha = report["state_export_sha256"]
    lines = [
        f"migrate --dry-run: {report['store']}",
        f"schema version: {report['current_version']} -> {report['target_version']}",
        "rows per table (before -> after):",
    ]
    if isinstance(tables, dict):
        for name, counts in tables.items():
            if isinstance(counts, dict):
                lines.append(f"  {name}: {counts['before']} -> {counts['after']}")
    lines.append("columns added:")
    if isinstance(added, dict) and added:
        for name, columns in added.items():
            lines.append(f"  {name}: {', '.join(str(c) for c in columns)}")
    else:
        lines.append("  none")
    created = report["tables_created"]
    if isinstance(created, list) and created:
        lines.append(f"tables created: {', '.join(str(c) for c in created)}")
    lines.append(f"integrity_check on the migrated copy: {report['integrity_check']}")
    if isinstance(sha, dict):
        lines.append(f"state export sha256 before: {sha['before'] or 'unknown'}")
        lines.append(f"state export sha256 after:  {sha['after'] or 'unknown'}")
    lines.append("The real store was not written.")
    return "\n".join(lines)
