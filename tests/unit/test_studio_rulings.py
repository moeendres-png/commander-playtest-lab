"""Rulings (schema 13): importer, replace semantics, read view, reports. Synthetic files."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, import_all, rulings
from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.data_report import data_report
from commander_lab.studio.store import DataClass
from tests.unit.test_studio_store import _synthetic_cards, _workbook

ORACLE_A = "11111111-1111-4111-8111-111111111111"
ORACLE_B = "22222222-2222-4222-8222-222222222222"
COMMANDER = "Test Commander"


def _line(oracle_id: str, published_at: str, comment: str, source: str = "wotc") -> str:
    return json.dumps(
        {
            "object": "ruling",
            "oracle_id": oracle_id,
            "source": source,
            "published_at": published_at,
            "comment": comment,
        }
    )


def _file(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _dump(store: StudioStore) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in store.connection.execute(
            "SELECT oracle_id, ordinal, published_at, ruling_source, comment, source_id "
            "FROM card_ruling ORDER BY oracle_id, ordinal"
        )
    ]


def _links(store: StudioStore) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in store.connection.execute(
            "SELECT oracle_id, published_at, comment, source_id FROM card_ruling_source "
            "ORDER BY oracle_id, published_at, comment, source_id"
        )
    ]


def test_import_reports_counts_and_stores_rows_in_date_order(tmp_path: Path) -> None:
    path = _file(
        tmp_path / "card_rulings_1655.jsonl",
        [
            _line(ORACLE_A, "2021-06-01", "Later ruling."),
            _line(ORACLE_A, "2019-07-12", "Earlier ruling."),
            _line(ORACLE_A, "2019-07-12", "Same day, other text.", source="scryfall"),
            _line(ORACLE_B, "2020-01-01", "Only ruling of B."),
        ],
    )
    store = StudioStore.in_memory()
    report = rulings.import_rulings(store, [path])
    assert report["rows_before"] == 0
    assert report["rulings"] == 4
    assert report["cards_with_rulings"] == 2
    assert report["rows_skipped"] == 0
    files = report["files"]
    assert isinstance(files, list) and len(files) == 1
    assert files[0]["rows_read"] == 4 and files[0]["rows_written"] == 4
    rows = _dump(store)
    assert [row[2] for row in rows if row[0] == ORACLE_A] == [
        "2019-07-12",
        "2019-07-12",
        "2021-06-01",
    ]
    assert store.count("card_ruling") == 4
    store.close()


def test_reimport_changes_nothing(tmp_path: Path) -> None:
    path = _file(
        tmp_path / "card_rulings_1655.jsonl",
        [_line(ORACLE_A, "2019-07-12", "One."), _line(ORACLE_B, "2020-01-01", "Two.")],
    )
    store = StudioStore.in_memory()
    rulings.import_rulings(store, [path])
    before = _dump(store)
    links_before = _links(store)
    report = rulings.import_rulings(store, [path])
    assert _dump(store) == before
    assert _links(store) == links_before
    assert report["rows_before"] == 2 and report["rulings"] == 2
    assert report["rows_linked"] == 0
    store.close()


def test_a_changed_file_replaces_only_its_own_rows(tmp_path: Path) -> None:
    first = _file(
        tmp_path / "card_rulings_1655.jsonl",
        [_line(ORACLE_A, "2019-07-12", "Old text."), _line(ORACLE_A, "2020-01-01", "Dropped.")],
    )
    other = _file(tmp_path / "extra_rulings.jsonl", [_line(ORACLE_B, "2018-01-01", "Kept.")])
    store = StudioStore.in_memory()
    rulings.import_rulings(store, [first])
    rulings.import_rulings(store, [other])
    assert store.count("card_ruling") == 3
    _file(first, [_line(ORACLE_A, "2019-07-12", "New text.")])
    report = rulings.import_rulings(store, [first])
    assert report["rows_before"] == 3 and report["rulings"] == 2
    comments = sorted(str(row[4]) for row in _dump(store))
    assert comments == ["Kept.", "New text."]
    store.close()


def test_a_shared_ruling_survives_replacing_one_of_its_files(tmp_path: Path) -> None:
    first = _file(
        tmp_path / "first.jsonl",
        [
            _line(ORACLE_A, "2019-07-12", "Shared."),
            _line(ORACLE_A, "2019-07-12", "Only first."),
        ],
    )
    second = _file(
        tmp_path / "second.jsonl",
        [
            _line(ORACLE_A, "2019-07-12", "Shared."),
            _line(ORACLE_B, "2020-01-01", "Only second."),
        ],
    )
    store = StudioStore.in_memory()
    report = rulings.import_rulings(store, [first, second])
    assert report["rulings"] == 3
    files = report["files"]
    assert isinstance(files, list)
    assert files[0]["rows_written"] == 2 and files[1]["rows_written"] == 1
    assert files[1]["rows_linked"] == 1 and report["rows_linked"] == 1
    _file(first, [_line(ORACLE_A, "2021-01-01", "Replacement.")])
    report = rulings.import_rulings(store, [first])
    assert report["rows_before"] == 3 and report["rulings"] == 3
    comments = sorted(str(row[4]) for row in _dump(store))
    assert comments == ["Only second.", "Replacement.", "Shared."]
    _file(second, [_line(ORACLE_B, "2020-01-01", "Only second.")])
    rulings.import_rulings(store, [second])
    comments = sorted(str(row[4]) for row in _dump(store))
    assert comments == ["Only second.", "Replacement."]
    store.close()


def test_bad_lines_are_skipped_with_reasons(tmp_path: Path) -> None:
    path = _file(
        tmp_path / "card_rulings_1655.jsonl",
        [
            _line(ORACLE_A, "2019-07-12", "Good."),
            "this is not json",
            "[1, 2]",
            json.dumps({"oracle_id": ORACLE_A, "published_at": "2019-07-12"}),
            _line(ORACLE_A, "2019-07-12", "Good."),
            "",
        ],
    )
    store = StudioStore.in_memory()
    report = rulings.import_rulings(store, [path])
    files = report["files"]
    assert isinstance(files, list)
    entry = files[0]
    assert entry["rows_read"] == 5
    assert entry["rows_written"] == 1
    assert entry["rows_skipped"] == 4
    assert entry["skipped_reasons"] == {
        "NOT_JSON": 1,
        "NOT_AN_OBJECT": 1,
        "FIELD_MISSING": 1,
        "DUPLICATE": 1,
    }
    assert report["rulings"] == 1
    store.close()


def test_a_file_without_any_ruling_is_refused_and_changes_nothing(tmp_path: Path) -> None:
    good = _file(tmp_path / "good.jsonl", [_line(ORACLE_A, "2019-07-12", "Good.")])
    bad = _file(tmp_path / "bad.jsonl", ["no json at all"])
    store = StudioStore.in_memory()
    rulings.import_rulings(store, [good])
    with pytest.raises(ValueError, match="no ruling in the file"):
        rulings.import_rulings(store, [bad])
    assert store.count("card_ruling") == 1
    with pytest.raises(ValueError, match="no rulings file given"):
        rulings.import_rulings(store, [])
    with pytest.raises(ValueError, match="same name"):
        rulings.import_rulings(store, [good, tmp_path / "sub" / "good.jsonl"])
    store.close()


def _add_card(store: StudioStore, card_id: str, oracle_id: str | None) -> None:
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE, title="test", sha256="0" * 64
    )
    store.connection.execute(
        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, source_id) "
        "VALUES (?, ?, ?, 'G', ?)",
        (card_id, oracle_id, f"Card {card_id}", source_id),
    )
    store.connection.commit()


def test_rulings_for_card_statuses(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    _add_card(store, "card:a", ORACLE_A)
    _add_card(store, "card:blank", None)
    view = rulings.rulings_for_card(store, "card:a")
    assert view["status"] == "NOT_IMPORTED" and view["rulings"] == []
    assert rulings.rulings_for_card(store, "card:blank")["status"] == "UNKNOWN"
    path = _file(tmp_path / "r.jsonl", [_line(ORACLE_B, "2020-01-01", "Other card.")])
    rulings.import_rulings(store, [path])
    assert rulings.rulings_for_card(store, "card:a")["status"] == "NONE_PUBLISHED"
    path2 = _file(tmp_path / "r2.jsonl", [_line(ORACLE_A, "2019-07-12", "For A.")])
    rulings.import_rulings(store, [path2])
    view = rulings.rulings_for_card(store, "card:a")
    assert view["status"] == "AVAILABLE"
    assert view["rulings"] == [
        {"published_at": "2019-07-12", "source": "wotc", "comment": "For A."}
    ]
    with pytest.raises(KeyError):
        rulings.rulings_for_card(store, "card:unknown")
    store.close()


def test_schema_13_migration_opens_a_schema_12_store(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    folder.mkdir()
    raw = sqlite3.connect(folder / "studio.sqlite3")
    raw.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    raw.execute("INSERT INTO meta(key, value) VALUES ('schema_version', '12')")
    raw.execute(
        "CREATE TABLE universe_profile (profile_id TEXT PRIMARY KEY, "
        "name TEXT NOT NULL UNIQUE, spec TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    raw.execute(
        "INSERT INTO universe_profile VALUES ('universe:alt', 'alt', '{}', '2026-01-01T00:00:00Z')"
    )
    raw.commit()
    raw.close()
    store = StudioStore.open(folder)
    version = store.connection.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()[0]
    assert version == "13"
    assert store.count("card_ruling") == 0
    assert store.count("card_ruling_source") == 0
    assert store.connection.execute("SELECT COUNT(*) FROM universe_profile").fetchone()[0] == 1
    store.close()


def test_data_report_counts_the_rulings(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    _add_card(store, "card:a", ORACLE_A)
    _add_card(store, "card:b", ORACLE_B)
    empty = data_report(store)["rulings"]
    assert isinstance(empty, dict)
    assert empty["rows"] == 0 and empty["published_earliest"] is None
    path = _file(
        tmp_path / "r.jsonl",
        [
            _line(ORACLE_A, "2019-07-12", "One."),
            _line(ORACLE_A, "2021-06-01", "Two.", source="scryfall"),
            _line("33333333-3333-4333-8333-333333333333", "2020-01-01", "Not collected."),
        ],
    )
    rulings.import_rulings(store, [path])
    section = data_report(store)["rulings"]
    assert isinstance(section, dict)
    assert section["rows"] == 3
    assert section["cards_with_rulings"] == 2
    assert section["collection_cards_with_rulings"] == {"count": 1, "of": 2}
    assert section["by_source"] == {"scryfall": 1, "wotc": 2}
    assert section["published_earliest"] == "2019-07-12"
    assert section["published_latest"] == "2021-06-01"
    store.close()


def _import_all_args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "commander": COMMANDER,
        "inventory": str(_workbook(tmp_path / "cards.xlsx", _synthetic_cards())),
        "scryfall": None,
        "roles": None,
        "rulings": None,
        "signals": [],
        "decklists": None,
        "decklist_format": "edhrec",
        "marks": None,
        "expect_pool": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_import_all_imports_given_rulings_and_counts_the_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(import_all, "_RESEARCH", tmp_path / "no-research")
    path = _file(tmp_path / "r.jsonl", [_line(ORACLE_A, "2019-07-12", "One.")])
    store = StudioStore.open(tmp_path / "studio")
    result = import_all.run(_import_all_args(tmp_path, rulings=[str(path)]), store)
    status = {step["step"]: step["status"] for step in result["steps"]}
    assert status["Regeltexte"] == "IMPORTED"
    layers = {layer["key"]: layer for layer in result["layers"]}
    assert layers["rulings"]["rows"] == 1
    assert layers["rulings"]["status"] == "PARTIAL"  # no pool card carries the oracle id
    assert store.count("card_ruling") == 1
    store.close()


def test_import_all_uses_the_curated_rulings_file_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    research = tmp_path / "research"
    package = research / "deckbuilder_1655"
    package.mkdir(parents=True)
    _file(package / "card_rulings_1655.jsonl", [_line(ORACLE_A, "2019-07-12", "One.")])
    monkeypatch.setattr(import_all, "_RESEARCH", research)
    assert import_all.default_rulings_files() == [package / "card_rulings_1655.jsonl"]
    store = StudioStore.open(tmp_path / "studio")
    result = import_all.run(_import_all_args(tmp_path), store)
    status = {step["step"]: step["status"] for step in result["steps"]}
    assert status["Regeltexte"] == "IMPORTED"
    assert store.count("card_ruling") == 1
    store.close()


def test_import_rulings_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _file(tmp_path / "r.jsonl", [_line(ORACLE_A, "2019-07-12", "One.")])
    data = tmp_path / "data"
    assert studio_main(["--data", str(data), "import-rulings", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["rulings"] == 1 and report["cards_with_rulings"] == 1
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(SystemExit, match="import-rulings"):
        studio_main(["--data", str(data), "import-rulings", str(missing)])
