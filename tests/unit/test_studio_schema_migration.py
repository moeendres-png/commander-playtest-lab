"""A real schema-13 database file is upgraded to schema 14 without losing a row.

All data here is synthetic.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, builder, create_revision
from commander_lab.studio.store import DATABASE_NAME, SCHEMA_VERSION
from tests.unit.test_studio_builder import _deck, _fill

COMBO_COLUMNS = ["commander_name", "ordinal", "cards", "num_decks", "source_id"]
TABLES = ["card", "inventory", "deck_revision", "card_mark", "corpus_deck_card"]


def _database(folder: Path) -> Path:
    return folder / DATABASE_NAME


def _snapshot(path: Path) -> dict[str, list[tuple[object, ...]]]:
    connection = sqlite3.connect(path)
    try:
        names = [
            str(r[0])
            for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'meta' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            name: sorted(connection.execute(f'SELECT * FROM "{name}"').fetchall(), key=repr)
            for name in names
        }
    finally:
        connection.close()


def _meta_version(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        return str(
            connection.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0]
        )
    finally:
        connection.close()


@pytest.fixture
def schema_13(tmp_path: Path) -> Path:
    """A database file made by the current code, then reduced to the schema-13 shape."""
    folder = tmp_path / "studio"
    store = StudioStore.open(folder)
    _fill(store, tmp_path)
    create_revision(store, deck_id="test", name="Test", cards=_deck())
    builder.set_mark(store, "card:project:0007", favorite=True, excluded=False, note="try it")
    store.close()
    connection = sqlite3.connect(_database(folder))
    connection.execute("DROP TABLE commander_combo")
    connection.execute("UPDATE meta SET value = '13' WHERE key = 'schema_version'")
    connection.commit()
    connection.close()
    return folder


def test_a_schema_13_file_is_upgraded_and_keeps_every_row(schema_13: Path) -> None:
    path = _database(schema_13)
    before = _snapshot(path)
    assert _meta_version(path) == "13"
    connection = sqlite3.connect(path)
    assert not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'commander_combo'"
    ).fetchone()
    connection.close()
    assert SCHEMA_VERSION == 14

    store = StudioStore.open(schema_13)
    try:
        assert _meta_version(path) == "14"
        columns = [
            r["name"] for r in store.connection.execute("PRAGMA table_info(commander_combo)")
        ]
        assert columns == COMBO_COLUMNS
        assert store.connection.execute("SELECT COUNT(*) FROM commander_combo").fetchone()[0] == 0

        # earlier rows: counts and a few values
        for table in TABLES:
            count = store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == len(before[table]) > 0, table
        mark = store.connection.execute(
            "SELECT favorite, excluded, note FROM card_mark WHERE card_id = 'card:project:0007'"
        ).fetchone()
        assert tuple(mark) == (1, 0, "try it")
        assert builder.history(store, "test")[0]["cards"] == 100
        rat = store.connection.execute(
            "SELECT oracle_id FROM card_fact WHERE card_id = 'card:project:0007'"
        ).fetchone()
        assert rat["oracle_id"] == "oracle-swarm-rat"
    finally:
        store.close()

    after = _snapshot(path)
    assert after.pop("commander_combo") == []
    assert after == before


def test_opening_the_upgraded_file_again_changes_nothing(schema_13: Path) -> None:
    StudioStore.open(schema_13).close()
    path = _database(schema_13)
    first = _snapshot(path)
    StudioStore.open(schema_13).close()
    assert _meta_version(path) == "14"
    assert _snapshot(path) == first


def test_a_store_newer_than_the_code_is_refused_and_left_untouched(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    StudioStore.open(folder).close()
    path = _database(folder)
    newer = str(SCHEMA_VERSION + 1)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (newer,))
    connection.commit()
    connection.close()
    before = _snapshot(path)

    with pytest.raises(RuntimeError, match=f"schema {newer}, this code needs {SCHEMA_VERSION}"):
        StudioStore.open(folder)

    assert _meta_version(path) == newer  # never downgraded
    assert _snapshot(path) == before
