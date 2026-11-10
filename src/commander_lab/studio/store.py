"""SQLite store of the Studio. It lives in the Owner data folder, never in the Git tree."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from commander_lab.owner_data import owner_data_root

STUDIO_DATA_ENV = "COMMANDER_LAB_STUDIO_DATA"
SCHEMA_VERSION = 1
DATABASE_NAME = "studio.sqlite3"


class DataClass(StrEnum):
    """Where a value comes from. Every stored value carries one of these."""

    ORIGINAL_SOURCE = "ORIGINAL_SOURCE"
    NORMALIZED_SOURCE = "NORMALIZED_SOURCE"
    DERIVED_DESCRIPTIVE = "DERIVED_DESCRIPTIVE"
    HEURISTIC_MODEL = "HEURISTIC_MODEL"
    SIMULATED_RESULT = "SIMULATED_RESULT"
    UNKNOWN = "UNKNOWN"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source (
    source_id TEXT PRIMARY KEY,
    data_class TEXT NOT NULL,
    title TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    snapshot_date TEXT,
    url TEXT,
    imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card (
    card_id TEXT PRIMARY KEY,
    oracle_id TEXT,
    oracle_name TEXT NOT NULL,
    color_identity TEXT NOT NULL,
    mana_cost TEXT,
    mana_value REAL,
    type_line TEXT,
    oracle_text TEXT,
    is_basic_land INTEGER NOT NULL DEFAULT 0,
    commander_legal INTEGER,
    legality_verified_at TEXT,
    identity_evidence TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE INDEX IF NOT EXISTS card_name ON card(oracle_name);
CREATE TABLE IF NOT EXISTS inventory (
    card_id TEXT PRIMARY KEY REFERENCES card(card_id),
    observed INTEGER NOT NULL,
    owned_lower_bound INTEGER NOT NULL,
    reserved INTEGER NOT NULL,
    available_lower_bound INTEGER NOT NULL,
    quantity_exact INTEGER NOT NULL,
    lots INTEGER,
    last_verified_at TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS deck (
    deck_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deck_revision (
    revision_id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL REFERENCES deck(deck_id),
    parent_revision_id TEXT REFERENCES deck_revision(revision_id),
    deck_hash TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    source_id TEXT REFERENCES source(source_id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deck_revision_card (
    revision_id TEXT NOT NULL REFERENCES deck_revision(revision_id),
    card_id TEXT NOT NULL REFERENCES card(card_id),
    zone TEXT NOT NULL CHECK (zone IN ('commander', 'main')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (revision_id, card_id, zone)
);
CREATE TABLE IF NOT EXISTS deck_branch (
    deck_id TEXT NOT NULL REFERENCES deck(deck_id),
    branch TEXT NOT NULL,
    revision_id TEXT NOT NULL REFERENCES deck_revision(revision_id),
    PRIMARY KEY (deck_id, branch)
);
CREATE TABLE IF NOT EXISTS corpus_deck (
    deck_id TEXT PRIMARY KEY,
    cohort TEXT NOT NULL,
    url TEXT NOT NULL,
    platform TEXT NOT NULL,
    play_group TEXT NOT NULL,
    deck_date TEXT,
    tags TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    duplicate_of TEXT,
    legality_audit TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS corpus_deck_card (
    deck_id TEXT NOT NULL REFERENCES corpus_deck(deck_id),
    card_name TEXT NOT NULL,
    oracle_id TEXT,
    quantity INTEGER NOT NULL,
    section TEXT NOT NULL,
    normalization_status TEXT NOT NULL,
    PRIMARY KEY (deck_id, card_name, section)
);
CREATE INDEX IF NOT EXISTS corpus_card_name ON corpus_deck_card(card_name);
CREATE TABLE IF NOT EXISTS observation (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT REFERENCES card(card_id),
    card_name TEXT NOT NULL,
    metric TEXT NOT NULL,
    cohort TEXT NOT NULL,
    value REAL,
    numerator INTEGER,
    denominator INTEGER,
    data_class TEXT NOT NULL,
    url TEXT,
    snapshot TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE INDEX IF NOT EXISTS observation_card ON observation(card_name, metric);
"""


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def studio_data_dir() -> Path:
    """The folder that holds the Studio store.

    ``COMMANDER_LAB_STUDIO_DATA`` names it directly; otherwise it is ``studio/`` below the
    Owner data folder. There is no default inside the repository: collection and deck data
    must not land in the Git tree.
    """
    explicit = os.environ.get(STUDIO_DATA_ENV, "").strip()
    if explicit:
        folder = Path(explicit).expanduser()
    else:
        owner = owner_data_root()
        if owner is None:
            raise RuntimeError(
                f"set {STUDIO_DATA_ENV} or COMMANDER_LAB_OWNER_DATA: the Studio store has no "
                "default location inside the repository"
            )
        folder = owner / "studio"
    resolved = folder.resolve()
    if resolved.is_relative_to(_repository_root()):
        raise RuntimeError(f"the Studio store must be outside the repository: {resolved}")
    return resolved


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class StudioStore:
    """One open Studio database."""

    def __init__(self, connection: sqlite3.Connection, path: Path | None) -> None:
        self.connection = connection
        self.path = path

    @classmethod
    def open(cls, folder: str | Path | None = None) -> StudioStore:
        directory = Path(folder).resolve() if folder is not None else studio_data_dir()
        if directory.is_relative_to(_repository_root()):
            raise RuntimeError(f"the Studio store must be outside the repository: {directory}")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / DATABASE_NAME
        return cls(cls._prepare(sqlite3.connect(path, timeout=30)), path)

    @classmethod
    def in_memory(cls) -> StudioStore:
        return cls(cls._prepare(sqlite3.connect(":memory:")), None)

    @staticmethod
    def _prepare(connection: sqlite3.Connection) -> sqlite3.Connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(_SCHEMA)
        row = connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )
        elif int(row["value"]) != SCHEMA_VERSION:
            raise RuntimeError(
                f"Studio store has schema {row['value']}, this code needs {SCHEMA_VERSION}"
            )
        connection.commit()
        return connection

    def close(self) -> None:
        self.connection.close()

    def register_source(
        self,
        *,
        data_class: DataClass,
        title: str,
        sha256: str,
        snapshot_date: str | None = None,
        url: str | None = None,
    ) -> str:
        """Record a source file once; the id is bound to its content hash."""
        source_id = f"src:{sha256[:16]}"
        self.connection.execute(
            "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, snapshot_date, "
            "url, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source_id, data_class.value, title, sha256, snapshot_date, url, now_utc()),
        )
        return source_id

    def card_id_by_name(self, oracle_name: str) -> str | None:
        rows = self.connection.execute(
            "SELECT card_id FROM card WHERE oracle_name = ?", (oracle_name,)
        ).fetchall()
        return str(rows[0]["card_id"]) if len(rows) == 1 else None

    def count(self, table: str) -> int:
        if table not in {
            "source", "card", "inventory", "deck", "deck_revision", "deck_revision_card",
            "deck_branch", "corpus_deck", "corpus_deck_card", "observation",
        }:  # fmt: skip
            raise ValueError(table)
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
