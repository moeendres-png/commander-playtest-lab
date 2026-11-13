"""Tagger roles from CSV, rulings, the rulings route, schema 13. Synthetic data, no network."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, research_import, roles, rulings
from commander_lab.studio.store import SCHEMA_VERSION
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _fill

HEADERS = {"host": "127.0.0.1"}


def _tagger(path: Path, rows: list[tuple[str, str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["oracle_id", "card_name", "category", "bulk_label", "weight"])
        for oracle_id, category, label in rows:
            writer.writerow([oracle_id, "x", category, label, "median"])
    return path


def _claims(store: StudioStore) -> set[tuple[str, str]]:
    return {
        (str(r[0]), str(r[1]))
        for r in store.connection.execute("SELECT oracle_id, role FROM card_role")
    }


def test_tagger_csv_becomes_a_full_snapshot_of_studio_roles(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    path = _tagger(
        tmp_path / "card_tagger_bulk_test.csv",
        [
            ("o1", "ramp", "mana dork"),
            ("o1", "ramp", "land ramp"),
            ("o2", "removal", "spot removal"),
            ("o3", "anthem", "anthem"),  # not a Studio role
            ("o3", "mill", "surveil"),
            ("o 4", "ramp", "bad id"),
        ],
    )
    report = research_import.import_tagger_roles(store, path)
    assert _claims(store) == {("o1", "ramp"), ("o2", "removal")}
    assert report["unknown_categories"] == {"anthem": 1, "mill": 1}
    assert report["rows_skipped"] == 1 and report["rows_read"] == 6
    assert report["role_origin"] == roles.ORIGIN_CROSSWALK and report["mode"] == roles.FULL_SNAPSHOT
    source = store.connection.execute("SELECT title, sha256 FROM source").fetchone()
    assert source["title"] == path.name and len(source["sha256"]) == 64
    claim = store.connection.execute(
        "SELECT original_tag, mapping_rule FROM card_role_claim WHERE role = 'ramp'"
    ).fetchone()
    assert claim["original_tag"] == "land ramp|mana dork"
    assert claim["mapping_rule"].startswith("crosswalk:")


def test_tagger_import_is_idempotent_and_replaces_only_its_scope(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    path = _tagger(tmp_path / "bulk.csv", [("o1", "ramp", "a"), ("o2", "ramp", "a")])
    research_import.import_tagger_roles(store, path)
    before = store.connection.execute("SELECT * FROM card_role_claim ORDER BY 1, 2").fetchall()
    research_import.import_tagger_roles(store, path)
    after = store.connection.execute("SELECT * FROM card_role_claim ORDER BY 1, 2").fetchall()
    assert [tuple(r) for r in before] == [tuple(r) for r in after]
    # another scope's claim survives a changed file of this scope
    store.connection.execute(
        "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('src:other', 'ORIGINAL_SOURCE', 'other', 'x', 'now')"
    )
    store.connection.execute(
        "INSERT INTO card_role_claim(oracle_id, role, role_origin, scope_key, source_id) "
        "VALUES ('o9', 'ramp', 'SCRYFALL_TAGGER_ORIGINAL', 'WUG', 'src:other')"
    )
    changed = _tagger(tmp_path / "bulk.csv", [("o1", "ramp", "a")])
    report = research_import.import_tagger_roles(store, changed)
    assert report["claims_removed"] == 1
    assert _claims(store) == {("o1", "ramp"), ("o9", "ramp")}


def test_tagger_csv_without_its_columns_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("oracle_id,card_name\no1,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing column"):
        research_import.import_tagger_roles(StudioStore.in_memory(), bad)


def test_capture_date_reads_the_readme_table(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "| `a.csv` | x | EDHREC, Abruf 2026-11-11/12 |\n| `b.csv` | y | Bulk, 2026-11-12 |\n"
        "| `c.csv` | z | none |\n",
        encoding="utf-8",
    )
    assert research_import.capture_date(readme, "a.csv") == "2026-11-12"
    assert research_import.capture_date(readme, "b.csv") == "2026-11-12"
    assert research_import.capture_date(readme, "c.csv") is None
    assert research_import.capture_date(readme, "missing.csv") is None


def _ruling_file(path: Path, lines: list[object]) -> Path:
    path.write_text(
        "\n".join(x if isinstance(x, str) else json.dumps(x) for x in lines) + "\n",
        encoding="utf-8",
    )
    return path


def _ruling(oracle: str, day: str, text: str) -> dict[str, str]:
    return {
        "object": "ruling",
        "oracle_id": oracle,
        "source": "wotc",
        "published_at": day,
        "comment": text,
    }


def test_rulings_import_replaces_scope_and_reports_skips(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    first = _ruling_file(
        tmp_path / "card_rulings_1.jsonl",
        [
            _ruling("o1", "2020-01-02", "B"),
            _ruling("o1", "2019-01-01", "A"),
            "not json",
            {"oracle_id": "o2"},
            _ruling("o1", "2019-01-01", "A"),
        ],
    )
    report = rulings.import_rulings(store, [first])
    assert report["rulings"] == 2 and report["cards_with_rulings"] == 1
    files = report["files"]
    assert isinstance(files, list)
    assert files[0]["skipped_reasons"] == {"NOT_JSON": 1, "FIELD_MISSING": 1, "DUPLICATE": 1}
    ordered = [
        r[0] for r in store.connection.execute("SELECT comment FROM card_ruling ORDER BY ordinal")
    ]
    assert ordered == ["A", "B"]
    second = _ruling_file(tmp_path / "scryfall_rulings_2.jsonl", [_ruling("o2", "2021-01-01", "C")])
    rulings.import_rulings(store, [first, second])
    rulings.import_rulings(store, [first, second])  # idempotent
    assert store.count("card_ruling") == 3
    rulings.import_rulings(store, [second])  # replaces only its own file's rulings
    assert store.count("card_ruling") == 3


def test_rulings_route_and_read_function(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    card = store.connection.execute(
        "SELECT card_id, oracle_id FROM card_fact WHERE oracle_id IS NOT NULL ORDER BY card_id"
    ).fetchall()
    assert len(card) >= 2
    first, second = card[0], card[1]
    assert rulings.rulings_for_card(store, str(first["card_id"]))["status"] == "NOT_IMPORTED"
    path = _ruling_file(
        tmp_path / "r.jsonl", [_ruling(str(first["oracle_id"]), "2020-01-01", "Text")]
    )
    rulings.import_rulings(store, [path])
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers=HEADERS)
    found = client.get(f"/api/cards/{first['card_id']}/rulings").json()
    assert found["status"] == "AVAILABLE" and found["rulings"][0]["comment"] == "Text"
    none = client.get(f"/api/cards/{second['card_id']}/rulings").json()
    assert none["status"] == "NONE_PUBLISHED" and none["rulings"] == []
    assert client.get("/api/cards/nope/rulings").status_code == 404


def test_schema_12_store_upgrades_to_13_with_the_ruling_table(tmp_path: Path) -> None:
    assert SCHEMA_VERSION == 13
    store = StudioStore.open(tmp_path / "studio")
    store.connection.execute("DROP TABLE card_ruling")
    store.connection.execute("UPDATE meta SET value = '12' WHERE key = 'schema_version'")
    store.connection.commit()
    store.close()
    again = StudioStore.open(tmp_path / "studio")
    row = again.connection.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    assert row["value"] == "13"
    assert again.count("card_ruling") == 0
    again.close()
    # a second open changes nothing
    StudioStore.open(tmp_path / "studio").close()
    db = sqlite3.connect(tmp_path / "studio" / "studio.sqlite3")
    assert db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0] == "13"
