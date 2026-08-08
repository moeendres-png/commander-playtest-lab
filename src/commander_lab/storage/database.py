from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.storage.hashing import sha256_value

SCHEMA_VERSION = 2

LEGACY_MANUAL_PLAYTEST_TABLES = (
    "calibration_profiles",
    "local_opponent_profiles",
    "local_games",
    "playtest_games",
    "playtests",
)


def connect_database(path: str | Path) -> sqlite3.Connection:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    return connection


def migrate_database(path: str | Path) -> dict[str, Any]:
    """Migrate the active database and remove known manual-playtest-only tables.

    Historical Git artifacts are untouched. The database records whether legacy
    tables were removed so callers can distinguish a clean database from a migrated one.
    """
    removed: list[str] = []
    with closing(connect_database(path)) as connection, connection:
        existing = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in LEGACY_MANUAL_PLAYTEST_TABLES:
            if table in existing:
                connection.execute(f'DROP TABLE "{table}"')
                removed.append(table)
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                sealed_payload_json TEXT NOT NULL,
                sealed_payload_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                result_json TEXT,
                decision TEXT
            );
            CREATE TABLE IF NOT EXISTS run_registry (
                run_id TEXT PRIMARY KEY,
                manifest_path TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                validation_level TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_run_registry_status ON run_registry(status);
            """
        )
        migration_status = "removed_legacy_tables" if removed else "not_present"
        connection.execute(
            "INSERT INTO schema_meta(key,value) VALUES('schema_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        connection.execute(
            "INSERT INTO schema_meta(key,value) VALUES('manual_playtest_migration_status',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (migration_status,),
        )
        connection.execute(
            "INSERT INTO schema_meta(key,value) VALUES('manual_playtest_removed_tables',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(sorted(removed)),),
        )
    return check_database(path)


def check_database(path: str | Path) -> dict[str, Any]:
    database = Path(path)
    if not database.exists():
        return {
            "status": "missing",
            "integrity": False,
            "foreign_keys": False,
            "schema_version": None,
        }
    try:
        with closing(connect_database(database)) as connection, connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            row = connection.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            migration_row = connection.execute(
                "SELECT value FROM schema_meta WHERE key='manual_playtest_migration_status'"
            ).fetchone()
            removed_row = connection.execute(
                "SELECT value FROM schema_meta WHERE key='manual_playtest_removed_tables'"
            ).fetchone()
    except sqlite3.DatabaseError as exc:
        return {
            "status": "failed",
            "integrity": False,
            "foreign_keys": False,
            "schema_version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "status": "passed" if integrity == "ok" and not foreign_keys else "failed",
        "integrity": integrity == "ok",
        "foreign_keys": not foreign_keys,
        "schema_version": int(row[0]) if row else None,
        "manual_playtest_migration_status": (migration_row[0] if migration_row else "unknown"),
        "manual_playtest_removed_tables": (json.loads(removed_row[0]) if removed_row else []),
    }


def backup_database(path: str | Path, destination: str | Path) -> Path:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(source, timeout=30)
    dst = sqlite3.connect(target, timeout=30)
    try:
        src.execute("PRAGMA wal_checkpoint(FULL)")
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()
    return target


def _restore_integrity_ok(path: Path) -> bool:
    """Check a restore candidate without enabling WAL or mutating the file.

    The normal lab connection enables WAL. On Windows that can leave a transient
    filesystem lock around a candidate that must immediately be atomically replaced.
    Restore verification therefore uses a short-lived query-only connection.
    """
    connection = sqlite3.connect(path, timeout=30)
    try:
        connection.execute("PRAGMA query_only=ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        return integrity == "ok" and not foreign_keys
    finally:
        connection.close()


def restore_database(backup: str | Path, destination: str | Path) -> Path:
    source = Path(backup)
    if not source.is_file():
        raise FileNotFoundError(source)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".restore.tmp")
    temporary.unlink(missing_ok=True)
    shutil.copy2(source, temporary)
    if not _restore_integrity_ok(temporary):
        temporary.unlink(missing_ok=True)
        raise ValueError("backup database failed integrity check")
    temporary.replace(target)
    return target


def seal_experiment(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "experiment_id",
        "hypothesis",
        "baseline",
        "variant",
        "scenarios",
        "seeds",
        "acceptance_criteria",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"experiment payload missing fields: {missing}")
    sealed = {key: payload[key] for key in sorted(payload)}
    digest = sha256_value(sealed)
    with closing(connect_database(path)) as connection, connection:
        existing = connection.execute(
            "SELECT sealed_payload_hash FROM experiments WHERE experiment_id=?",
            (payload["experiment_id"],),
        ).fetchone()
        if existing and existing[0] != digest:
            raise ValueError("sealed experiment hypothesis or design cannot be changed")
        connection.execute(
            "INSERT OR IGNORE INTO experiments("
            "experiment_id,sealed_payload_json,sealed_payload_hash,created_at"
            ") VALUES(?,?,?,?)",
            (
                payload["experiment_id"],
                json.dumps(sealed, sort_keys=True),
                digest,
                datetime.now(UTC).isoformat(),
            ),
        )
    return {"experiment_id": payload["experiment_id"], "sealed_payload_hash": digest}
