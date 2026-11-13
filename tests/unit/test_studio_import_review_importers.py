"""Review findings on the tagger role import and the rulings import."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, research_import, rulings
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_research_importers import _ruling, _ruling_file, _tagger


def _claims(store: StudioStore) -> int:
    return store.count("card_role_claim")


def test_tagger_file_without_role_rows_does_not_replace_the_scope(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    research_import.import_tagger_roles(
        store, _tagger(tmp_path / "bulk.csv", [("o1", "ramp", "a"), ("o2", "ramp", "a")])
    )
    report = research_import.import_tagger_roles(
        store, _tagger(tmp_path / "bulk.csv", [("o3", "anthem", "x")])
    )
    assert report["status"] == "NO_ROWS" and "unchanged" in str(report["message"])
    assert _claims(store) == 2


def test_tagger_file_removing_most_claims_needs_force(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    rows = [(f"o{i}", "ramp", "a") for i in range(10)]
    research_import.import_tagger_roles(store, _tagger(tmp_path / "bulk.csv", rows))
    small = _tagger(tmp_path / "bulk.csv", rows[:2])
    blocked = research_import.import_tagger_roles(store, small)
    assert blocked["status"] == "WARNUNG" and _claims(store) == 10
    forced = research_import.import_tagger_roles(store, small, force=True)
    assert forced["status"] == "IMPORTED" and _claims(store) == 2


def test_tagger_small_change_replaces_without_force(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    rows = [(f"o{i}", "ramp", "a") for i in range(10)]
    research_import.import_tagger_roles(store, _tagger(tmp_path / "bulk.csv", rows))
    done = research_import.import_tagger_roles(store, _tagger(tmp_path / "bulk.csv", rows[:8]))
    assert done["status"] == "IMPORTED" and _claims(store) == 8


def test_rulings_are_replaced_per_source_file(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    a = _ruling_file(
        tmp_path / "a.jsonl", [_ruling("o1", "2020-01-01", "A1"), _ruling("o1", "2020-02-01", "A2")]
    )
    b = _ruling_file(tmp_path / "b.jsonl", [_ruling("o2", "2021-01-01", "B1")])
    rulings.import_rulings(store, [a])
    rulings.import_rulings(store, [b])
    assert store.count("card_ruling") == 3  # importing B did not delete A's rows
    _ruling_file(a, [_ruling("o1", "2020-01-01", "A1 changed")])
    rulings.import_rulings(store, [a])
    comments = sorted(r[0] for r in store.connection.execute("SELECT comment FROM card_ruling"))
    assert comments == ["A1 changed", "B1"]
    rulings.import_rulings(store, [a])
    assert store.count("card_ruling") == 2


def test_rulings_file_without_rows_is_refused_and_changes_nothing(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    good = _ruling_file(tmp_path / "a.jsonl", [_ruling("o1", "2020-01-01", "A1")])
    rulings.import_rulings(store, [good])
    empty = _ruling_file(tmp_path / "a.jsonl", ["not json"])
    with pytest.raises(ValueError, match="no ruling"):
        rulings.import_rulings(store, [empty])
    assert store.count("card_ruling") == 1


def test_same_ruling_in_two_files_is_shown_once(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    row = store.connection.execute(
        "SELECT card_id, oracle_id FROM card_fact WHERE oracle_id IS NOT NULL LIMIT 1"
    ).fetchone()
    same = [_ruling(str(row["oracle_id"]), "2020-01-01", "Text")]
    rulings.import_rulings(
        store, [_ruling_file(tmp_path / "a.jsonl", same), _ruling_file(tmp_path / "b.jsonl", same)]
    )
    shown = rulings.rulings_for_card(store, str(row["card_id"]))["rulings"]
    assert isinstance(shown, list) and len(shown) == 1


def test_card_without_oracle_id_has_unknown_rulings(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.connection.execute("UPDATE card SET oracle_id = NULL")
    store.connection.execute("DELETE FROM scryfall_card")
    card = store.connection.execute("SELECT card_id FROM card LIMIT 1").fetchone()[0]
    rulings.import_rulings(
        store, [_ruling_file(tmp_path / "r.jsonl", [_ruling("o1", "2020-01-01", "x")])]
    )
    assert rulings.rulings_for_card(store, str(card))["status"] == "UNKNOWN"
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"host": "127.0.0.1"})
    assert json.loads(client.get(f"/api/cards/{card}/rulings").text)["status"] == "UNKNOWN"


def test_same_content_under_two_names_does_not_inflate(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    lines = [_ruling("o1", "2020-01-01", "A1"), _ruling("o2", "2020-01-02", "B1")]
    rulings.import_rulings(store, [_ruling_file(tmp_path / "a.jsonl", lines)])
    rulings.import_rulings(store, [_ruling_file(tmp_path / "b.jsonl", lines)])
    assert store.count("card_ruling") == 2
    rulings.import_rulings(store, [tmp_path / "a.jsonl"])  # re-import: unchanged
    assert store.count("card_ruling") == 2


def test_renamed_and_changed_file_gives_the_union_of_distinct_rulings(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    old = [_ruling("o1", "2020-01-01", "A1"), _ruling("o2", "2020-01-02", "B1")]
    rulings.import_rulings(store, [_ruling_file(tmp_path / "a.jsonl", old)])
    new = [_ruling("o1", "2020-01-01", "A1"), _ruling("o3", "2021-01-01", "C1")]
    rulings.import_rulings(store, [_ruling_file(tmp_path / "renamed.jsonl", new)])
    assert store.count("card_ruling") == 3


def test_changed_content_under_the_same_name_replaces_the_older_version(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    path = tmp_path / "a.jsonl"
    rulings.import_rulings(store, [_ruling_file(path, [_ruling("o1", "2020-01-01", "A1")])])
    rulings.import_rulings(store, [_ruling_file(path, [_ruling("o2", "2020-01-02", "B1")])])
    assert [r[0] for r in store.connection.execute("SELECT oracle_id FROM card_ruling")] == ["o2"]


def test_a_ruling_is_unique_in_the_table_and_old_duplicates_are_removed(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    store.connection.execute(
        "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('src:x', 'NORMALIZED_SOURCE', 'x', 'x', 'now')"
    )
    store.connection.execute(
        "INSERT INTO card_ruling VALUES ('o1', 1, '2020-01-01', 'wotc', 'T', 'src:x')"
    )
    store.connection.commit()
    with pytest.raises(sqlite3.IntegrityError):
        store.connection.execute(
            "INSERT INTO card_ruling VALUES ('o1', 2, '2020-01-01', 'wotc', 'T', 'src:x')"
        )
    store.connection.rollback()
    store.connection.execute("DROP INDEX card_ruling_unique")
    store.connection.execute(
        "INSERT INTO card_ruling VALUES ('o1', 2, '2020-01-01', 'wotc', 'T', 'src:x')"
    )
    store.connection.commit()
    store.close()
    again = StudioStore.open(tmp_path / "studio")  # dedupes, then creates the index
    assert again.count("card_ruling") == 1
    again.close()
