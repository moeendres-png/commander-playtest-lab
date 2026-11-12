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
SCHEMA_VERSION = 9
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
CREATE TABLE IF NOT EXISTS scryfall_card (
    oracle_id TEXT PRIMARY KEY,
    scryfall_id TEXT NOT NULL,
    name TEXT NOT NULL,
    front_name TEXT NOT NULL,
    layout TEXT NOT NULL,
    mana_cost TEXT,
    mana_value REAL,
    type_line TEXT,
    oracle_text TEXT,
    color_identity TEXT NOT NULL,
    commander_legality TEXT NOT NULL,
    edhrec_rank INTEGER,
    keywords TEXT NOT NULL,
    produced_mana TEXT NOT NULL,
    power TEXT,
    toughness TEXT,
    game_changer INTEGER,
    released_at TEXT,
    image_front TEXT,
    image_back TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE INDEX IF NOT EXISTS scryfall_name ON scryfall_card(name);
CREATE INDEX IF NOT EXISTS scryfall_front_name ON scryfall_card(front_name);
CREATE TABLE IF NOT EXISTS card_mark (
    card_id TEXT PRIMARY KEY REFERENCES card(card_id),
    favorite INTEGER NOT NULL DEFAULT 0,
    excluded INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deck_draft (
    deck_id TEXT NOT NULL REFERENCES deck(deck_id),
    branch TEXT NOT NULL,
    cards TEXT NOT NULL,
    base_revision_id TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (deck_id, branch)
);
CREATE TABLE IF NOT EXISTS corpus_cohort (
    cohort TEXT NOT NULL,
    deck_id TEXT NOT NULL REFERENCES corpus_deck(deck_id),
    PRIMARY KEY (cohort, deck_id)
);
CREATE TABLE IF NOT EXISTS universe_profile (
    profile_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    spec TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS corpus_deck_part (
    deck_id TEXT PRIMARY KEY REFERENCES corpus_deck(deck_id) DEFERRABLE INITIALLY DEFERRED,
    part_name TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS corpus_deck_stat (
    deck_id TEXT PRIMARY KEY REFERENCES corpus_deck(deck_id),
    cards INTEGER NOT NULL,
    resolved INTEGER NOT NULL,
    lands INTEGER NOT NULL,
    creatures INTEGER NOT NULL,
    nonland_mana_value REAL NOT NULL,
    nonland_cards INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS card_role (
    oracle_id TEXT NOT NULL,
    role TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (oracle_id, role)
);
CREATE TABLE IF NOT EXISTS card_role_claim (
    oracle_id TEXT NOT NULL,
    role TEXT NOT NULL,
    role_origin TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    original_tag TEXT,
    mapping_rule TEXT,
    PRIMARY KEY (oracle_id, role, role_origin, scope_key, source_id)
);
CREATE INDEX IF NOT EXISTS card_role_claim_scope ON card_role_claim(role_origin, scope_key, role);
CREATE TABLE IF NOT EXISTS corpus_deck_role (
    deck_id TEXT NOT NULL REFERENCES corpus_deck(deck_id),
    role TEXT NOT NULL,
    cards INTEGER NOT NULL,
    PRIMARY KEY (deck_id, role)
);
CREATE TABLE IF NOT EXISTS neutral_board_row (
    source_key TEXT NOT NULL,
    batch TEXT NOT NULL,
    section TEXT NOT NULL,
    card_name TEXT NOT NULL,
    oracle_id TEXT,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    PRIMARY KEY (source_key, section, card_name)
);
CREATE INDEX IF NOT EXISTS neutral_board_oracle ON neutral_board_row(oracle_id);
CREATE INDEX IF NOT EXISTS neutral_board_name ON neutral_board_row(card_name);
CREATE TABLE IF NOT EXISTS simulation_run (
    run_id TEXT PRIMARY KEY,
    deck_id TEXT NOT NULL,
    pod TEXT NOT NULL,
    engine_pin TEXT NOT NULL,
    pilot_policy TEXT NOT NULL,
    seeds TEXT NOT NULL,
    games_planned INTEGER NOT NULL,
    games_completed INTEGER NOT NULL,
    games_failed INTEGER NOT NULL,
    wins_fractional REAL NOT NULL,
    win_rate REAL,
    mean_rounds REAL,
    hand_dwell_status TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS simulation_card (
    run_id TEXT NOT NULL REFERENCES simulation_run(run_id),
    card_id TEXT REFERENCES card(card_id),
    card_name TEXT NOT NULL,
    games_completed INTEGER NOT NULL,
    games_offered INTEGER NOT NULL,
    games_cast_after_offer INTEGER NOT NULL,
    games_rotted INTEGER NOT NULL,
    offered_castable INTEGER NOT NULL,
    cast_count INTEGER NOT NULL,
    mean_first_cast_round REAL,
    PRIMARY KEY (run_id, card_name)
);
CREATE INDEX IF NOT EXISTS simulation_card_id ON simulation_card(card_id);
CREATE TABLE IF NOT EXISTS source_capture_event (
    event_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    request_start_utc TEXT NOT NULL,
    response_complete_utc TEXT NOT NULL,
    raw_response_sha256 TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    provenance_class TEXT NOT NULL,
    raw_size_bytes INTEGER NOT NULL,
    cardlists_count INTEGER NOT NULL,
    automatic_import INTEGER NOT NULL DEFAULT 0,
    source_id TEXT REFERENCES source(source_id)
);
CREATE TABLE IF NOT EXISTS playgroup_card_atlas (
    oracle_id TEXT NOT NULL,
    format_mode TEXT NOT NULL DEFAULT 'multiplayer',
    card_id TEXT REFERENCES card(card_id),
    card_name TEXT NOT NULL,
    slug TEXT NOT NULL,
    card_type TEXT,
    set_name TEXT,
    live_inclusion_pct REAL,
    deck_inclusion_pct REAL,
    times_brought INTEGER,
    decks_running INTEGER,
    unique_players INTEGER,
    median_cast_turn REAL,
    drawn_to_played_pct REAL,
    first_cast_n INTEGER,
    turn_1_pct REAL,
    turn_2_pct REAL,
    turn_3_pct REAL,
    turn_4_pct REAL,
    turn_5_pct REAL,
    turn_6_to_9_pct REAL,
    turn_10_plus_pct REAL,
    p25_cast_turn REAL,
    p75_cast_turn REAL,
    max_cast_turn REAL,
    on_curve_pct REAL,
    on_curve_count INTEGER,
    on_curve_denominator INTEGER,
    on_curve_turn TEXT,
    cast_same_turn_as_drawn_pct REAL,
    turns_in_hand REAL,
    funnel_brought_n INTEGER,
    funnel_players_n INTEGER,
    ever_drawn_n INTEGER,
    reached_battlefield_n INTEGER,
    still_on_board_at_end_n INTEGER,
    battlefield_survival_pct REAL,
    winrate_when_cast_pct REAL,
    winrate_when_cast_n INTEGER,
    winrate_when_in_library_pct REAL,
    winrate_when_in_library_n INTEGER,
    winrate_when_in_hand_pct REAL,
    winrate_when_in_hand_n INTEGER,
    observed_winrate_gap_pp REAL,
    ci_95_lower_pp REAL,
    ci_95_upper_pp REAL,
    conservative_ranking_indicator TEXT,
    final_zones_instances_n INTEGER,
    fetch_status TEXT NOT NULL DEFAULT 'OK',
    quality_warnings_json TEXT NOT NULL DEFAULT '[]',
    insufficient_sample INTEGER NOT NULL DEFAULT 0,
    retrieved_at_utc TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (oracle_id, format_mode)
);
CREATE INDEX IF NOT EXISTS idx_playgroup_card_atlas_card_id ON playgroup_card_atlas(card_id);
CREATE INDEX IF NOT EXISTS idx_playgroup_card_atlas_slug ON playgroup_card_atlas(slug);
CREATE INDEX IF NOT EXISTS idx_playgroup_card_atlas_status ON playgroup_card_atlas(fetch_status);
CREATE INDEX IF NOT EXISTS idx_playgroup_card_atlas_name ON playgroup_card_atlas(card_name);
CREATE TABLE IF NOT EXISTS playgroup_top_commander (
    oracle_id TEXT NOT NULL,
    format_mode TEXT NOT NULL DEFAULT 'multiplayer',
    rank INTEGER NOT NULL,
    commander_name TEXT NOT NULL,
    commander_slug TEXT NOT NULL,
    color_identity TEXT NOT NULL,
    decks_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (oracle_id, format_mode, rank)
);
CREATE TABLE IF NOT EXISTS playgroup_final_zone (
    oracle_id TEXT NOT NULL,
    format_mode TEXT NOT NULL DEFAULT 'multiplayer',
    zone_name TEXT NOT NULL,
    pct REAL NOT NULL,
    instances_n INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (oracle_id, format_mode, zone_name)
);
CREATE VIEW IF NOT EXISTS card_fact AS
SELECT c.card_id,
       c.oracle_name,
       COALESCE(s.oracle_id, c.oracle_id) AS oracle_id,
       CASE WHEN s.oracle_id IS NULL THEN c.oracle_name
            WHEN s.layout = 'split' THEN s.name ELSE s.front_name END AS engine_name,
       COALESCE(s.color_identity, REPLACE(c.color_identity, 'C', '')) AS color_identity,
       COALESCE(s.mana_cost, c.mana_cost) AS mana_cost,
       COALESCE(s.mana_value, c.mana_value) AS mana_value,
       COALESCE(s.type_line, c.type_line) AS type_line,
       COALESCE(s.oracle_text, c.oracle_text) AS oracle_text,
       CASE WHEN COALESCE(s.type_line, c.type_line) LIKE 'Basic %Land%' THEN 1
            ELSE c.is_basic_land END AS is_basic_land,
       CASE WHEN s.oracle_id IS NULL THEN c.commander_legal
            WHEN s.commander_legality = 'legal' THEN 1 ELSE 0 END AS commander_legal,
       CASE WHEN s.oracle_id IS NULL THEN 'workbook' ELSE 'scryfall' END AS fact_source,
       s.layout, s.edhrec_rank, s.keywords, s.produced_mana, s.power, s.toughness,
       s.game_changer, s.image_front, s.image_back
FROM card c LEFT JOIN scryfall_card s ON s.oracle_id = c.oracle_id;
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


def rebuild_corpus_deck_role(db: sqlite3.Connection) -> None:
    """Count roles per source deck again from ``card_role``.

    The table is derived: it holds the number of main-deck cards of each deck that carry a
    role, never more than ``corpus_deck_card`` and ``card_role`` say. Callers run it inside
    their own transaction, once, after they changed either input.
    """
    db.execute("DELETE FROM corpus_deck_role")
    db.execute(
        "INSERT INTO corpus_deck_role "
        "SELECT k.deck_id, r.role, SUM(k.quantity) FROM corpus_deck_card k "
        "JOIN card_role r ON r.oracle_id = k.oracle_id "
        "WHERE k.section != 'sideboard' GROUP BY k.deck_id, r.role"
    )


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
        elif int(row["value"]) > SCHEMA_VERSION:
            raise RuntimeError(
                f"Studio store has schema {row['value']}, this code needs {SCHEMA_VERSION}"
            )
        elif int(row["value"]) < SCHEMA_VERSION:
            # Every schema step so far only adds tables and views (created above).
            connection.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(SCHEMA_VERSION),)
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

    def card_id_by_oracle_or_name(
        self, oracle_id: str | None, card_name: str | None = None
    ) -> str | None:
        """Resolve a collection card by its oracle_id first, then by exact or front face name."""
        if oracle_id:
            rows = self.connection.execute(
                "SELECT card_id FROM card WHERE oracle_id = ?", (oracle_id,)
            ).fetchall()
            if len(rows) == 1:
                return str(rows[0]["card_id"])
        if card_name:
            by_name = self.card_id_by_name(card_name)
            if by_name is not None:
                return by_name
            front = card_name.split(" // ")[0].strip()
            rows = self.connection.execute(
                "SELECT card_id FROM card_fact WHERE engine_name = ? OR oracle_name = ?",
                (front, front),
            ).fetchall()
            if len(rows) == 1:
                return str(rows[0]["card_id"])
        return None

    def count(self, table: str) -> int:
        if table not in {
            "source", "card", "inventory", "deck", "deck_revision", "deck_revision_card",
            "deck_branch", "corpus_deck", "corpus_deck_card", "observation", "scryfall_card",
            "card_mark", "deck_draft", "corpus_cohort", "corpus_deck_stat", "corpus_deck_part", "card_role",
            "card_role_claim", "corpus_deck_role", "neutral_board_row", "simulation_run", "simulation_card",
            "source_capture_event", "playgroup_card_atlas", "playgroup_top_commander", "playgroup_final_zone",
        }:  # fmt: skip
            raise ValueError(table)
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
