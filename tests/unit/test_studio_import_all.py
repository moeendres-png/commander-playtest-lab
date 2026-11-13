"""``import-all`` and its completeness report on a synthetic delivery. No network."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, completeness, import_all
from commander_lab.studio.__main__ import main
from commander_lab.studio.queries import legal_pool
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _public_file
from tests.unit.test_studio_store import _synthetic_cards, _workbook

COMMANDER = "Test Commander"
HEADERS = {"host": "127.0.0.1"}


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _delivery(root: Path) -> dict[str, Path]:
    """A complete synthetic delivery: workbook, card data, research folder, deck lists."""
    collection = _workbook(root / "collection.xlsx", _synthetic_cards())
    scryfall = _public_file(root / "oracle.jsonl.gz")
    pack = root / "research" / "pack"
    pack.mkdir(parents=True)
    (root / "research" / "README.md").write_text("", encoding="utf-8")
    (pack / "README.md").write_text(
        "| `commander_card_signals_1.csv` | EDHREC, Abruf 2026-11-11/12 |\n"
        "| `card_tagger_bulk_9.csv` | Tagger, 2026-11-12 |\n",
        encoding="utf-8",
    )
    fields = ["commander_name", "card_name", "num_decks", "potential_decks", "synergy"]
    _write_csv(
        pack / "commander_card_signals_1.csv",
        fields,
        [
            {
                "commander_name": COMMANDER,
                "card_name": f"Filler {i:02d}",
                "num_decks": 5,
                "potential_decks": 10,
                "synergy": 0.1,
            }
            for i in range(1, 11)
        ],
    )
    _write_csv(
        pack / "edhrec_salt.csv", ["card_name", "salt", "rank"],
        [{"card_name": "Filler 01", "salt": 2.5, "rank": 1}],
    )  # fmt: skip
    _write_csv(
        pack / "card_tagger_bulk_9.csv",
        ["oracle_id", "card_name", "category", "bulk_label", "weight"],
        [
            {"oracle_id": f"oracle-filler-{i:02d}", "card_name": "x", "category": "ramp",
             "bulk_label": "mana dork", "weight": "median"}
            for i in range(1, 6)
        ]
        + [{"oracle_id": "oracle-forest", "card_name": "x", "category": "anthem",
            "bulk_label": "anthem", "weight": "median"}],
    )  # fmt: skip
    (pack / "card_rulings_9.jsonl").write_text(
        json.dumps(
            {"oracle_id": "oracle-filler-01", "source": "wotc", "published_at": "2020-01-01",
             "comment": "A ruling."}
        )
        + "\n",
        encoding="utf-8",
    )  # fmt: skip
    (pack / "mtgjson_printings_1.jsonl").write_text("{}\n", encoding="utf-8")
    (pack / "mystery.bin").write_text("?", encoding="utf-8")
    decks = root / "decks"
    decks.mkdir()
    for key in ("aaa", "bbb"):
        payload = {
            "urlhash": key,
            "variante": "upgraded",
            "bracket": 3,
            "savedate": "2026-10-01",
            "commanders": [COMMANDER],
            "cards": [
                {"name": COMMANDER, "quantity": 1},
                {"name": "Forest", "quantity": 20},
                {"name": f"Filler {1 if key == 'aaa' else 2:02d}", "quantity": 1},
                {"name": "Unknown Card", "quantity": 1},
            ],
            "karten_summe": 23,
        }
        (decks / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")
    return {
        "collection": collection,
        "scryfall": scryfall,
        "research": root / "research",
        "decks": decks,
    }


def _run(
    store: StudioStore,
    files: dict[str, Path],
    *,
    commander: str = COMMANDER,
    scryfall: Path | None = None,
    research: Path | None = None,
    decklists: list[Path] | None = None,
) -> dict[str, object]:
    return import_all.import_all(
        store,
        commander=commander,
        collection=files["collection"],
        scryfall=scryfall or files["scryfall"],
        research=research or files["research"],
        decklists=[files["decks"]] if decklists is None else decklists,
    )


def _layers(report: dict[str, object]) -> dict[str, completeness.LayerRow]:
    rows = report["layers"]
    assert isinstance(rows, list)
    return {str(row["layer"]): row for row in rows}


def test_full_delivery_fills_every_layer_and_counts_computed_pool(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    report = _run(store, _delivery(tmp_path))
    pool = len(legal_pool(store, [COMMANDER]))
    assert report["legal_pool_cards"] == pool and pool > 0
    assert report["stopped_at"] is None and report["failed_steps"] == 0
    layers = _layers(report)
    assert set(layers) == {
        "inventory", "public_card_facts", "commander_legality", "roles", "commander_inclusion",
        "bracket_inclusion_core",
        "bracket_inclusion_upgraded",
        "bracket_inclusion_optimized",
        "bracket_inclusion_cedh", "global_inclusion", "synergy", "combos", "salt", "tournament",
        "rulings", "corpus_decks", "universe_profiles", "playgroup",
    }  # fmt: skip
    assert layers["inventory"]["status"] == completeness.COMPLETE
    assert layers["commander_inclusion"]["n"] == 10
    assert layers["commander_inclusion"]["of"] == pool - 1
    assert layers["commander_inclusion"]["status"] == completeness.PARTIAL
    assert layers["commander_inclusion"]["capture_date"] == "2026-11-12"
    assert layers["roles"]["n"] == 5
    assert layers["salt"]["n"] == 1
    assert (
        layers["rulings"]["n"] == 1 and layers["rulings"]["status"] == completeness.RULINGS_STATUS
    )
    assert layers["bracket_inclusion"]["status"] == completeness.NOT_DELIVERED
    assert layers["playgroup"]["status"] == completeness.NOT_DELIVERED
    assert layers["corpus_decks"]["n"] is not None and layers["corpus_decks"]["n"] >= 2
    assert layers["universe_profiles"]["n"] is not None and layers["universe_profiles"]["n"] >= 2
    # the commander's cards without a row stay unknown: a layer is never complete by assumption
    assert layers["global_inclusion"]["n"] == 0


def test_decks_are_linked_and_unused_files_are_listed(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    report = _run(store, _delivery(tmp_path))
    stats = store.connection.execute(
        "SELECT SUM(cards), SUM(resolved) FROM corpus_deck_stat"
    ).fetchone()
    assert stats[0] == 46 and stats[1] == 44  # only "Unknown Card" is unresolved
    unused = report["unused_files"]
    assert isinstance(unused, list)
    reasons = {str(group["reason"]): group["files"] for group in unused}
    assert any("MTGJSON" in reason for reason in reasons)
    assert any(reason.startswith("nicht erkannt") for reason in reasons)
    assert not any("commander_card_signals" in f for files in reasons.values() for f in files)


def test_missing_optional_inputs_are_reported_and_the_run_continues(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    store = StudioStore.in_memory()
    report = _run(store, files, research=tmp_path / "nowhere", decklists=[])
    steps = report["steps"]
    assert isinstance(steps, list)
    by_name = {step["step"]: step["status"] for step in steps}
    for name in ("signals", "tagger_roles", "rulings", "decklists", "playgroup_atlas"):
        assert by_name[name] == import_all.STEP_NOT_DELIVERED
    assert by_name["relink_corpus"] == import_all.STEP_OK
    layers = _layers(report)
    assert layers["roles"]["status"] == completeness.NOT_DELIVERED
    assert layers["inventory"]["status"] == completeness.COMPLETE
    assert report["stopped_at"] is None


def test_a_failing_required_step_stops_the_run_but_reports(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    store = StudioStore.in_memory()
    report = _run(store, files, scryfall=tmp_path / "missing.jsonl.gz")
    assert isinstance(report["stopped_at"], str) and "public_card_facts" in report["stopped_at"]
    steps = report["steps"]
    assert isinstance(steps, list)
    assert [step["step"] for step in steps] == ["inventory", "public_card_facts"]
    assert steps[-1]["status"] == import_all.STEP_FAILED
    assert store.count("card") > 0  # what ran before the failure stays


def test_a_failing_optional_step_does_not_hide_the_rest(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    (files["research"] / "pack" / "card_tagger_bulk_9.csv").write_text("oracle_id\n1\n", "utf-8")
    store = StudioStore.in_memory()
    report = _run(store, files)
    assert report["failed_steps"] == 1 and report["stopped_at"] is None
    assert _layers(report)["rulings"]["n"] == 1


def test_import_all_twice_changes_nothing(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    store = StudioStore.in_memory()
    first = _run(store, files)
    tables = ("card_signal", "card_role", "card_role_claim", "card_ruling", "corpus_deck_card",
              "corpus_deck", "universe_profile", "source")  # fmt: skip
    before = {table: store.count(table) for table in tables}
    second = _run(store, files)
    assert {table: store.count(table) for table in tables} == before
    strip = lambda report: [  # noqa: E731
        (row["layer"], row["n"], row["of"], row["status"]) for row in _layers(report).values()
    ]
    assert strip(first) == strip(second)


def test_cli_writes_report_and_route_serves_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _delivery(tmp_path)
    data = tmp_path / "data"
    code = main(
        [
            "--data", str(data), "import-all",
            "--collection", str(files["collection"]),
            "--scryfall", str(files["scryfall"]),
            "--research", str(files["research"]),
            "--decklists", str(files["decks"]),
            "--commander", COMMANDER,
        ]
    )  # fmt: skip
    assert code == 0
    out = capsys.readouterr().out
    assert "von" in out and "TEILWEISE" in out and "NICHT GELIEFERT" in out
    written = json.loads((data / completeness.REPORT_FILE).read_text(encoding="utf-8"))
    assert written["commander"] == COMMANDER
    client = TestClient(create_app(data), headers=HEADERS)
    served = client.get("/api/import-report").json()
    assert served["legal_pool_cards"] == written["legal_pool_cards"]
    empty = TestClient(create_app(tmp_path / "other"), headers=HEADERS)
    assert empty.get("/api/import-report").status_code == 404


def test_cli_requires_commander_and_exit_code_one_on_required_failure(
    tmp_path: Path,
) -> None:
    files = _delivery(tmp_path)
    base = [
        "--data", str(tmp_path / "d"), "import-all",
        "--collection", str(files["collection"]),
        "--scryfall", str(tmp_path / "missing.jsonl.gz"),
        "--research", str(files["research"]),
    ]  # fmt: skip
    with pytest.raises(SystemExit) as raised:
        main(base)
    assert raised.value.code == 2
    assert main([*base, "--commander", COMMANDER]) == 1


def test_commander_not_in_collection_is_reported_not_assumed(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    report = _run(store, _delivery(tmp_path), commander="Nobody At All")
    assert report["legal_pool_cards"] is None and report["commander_in_collection"] is False
    warnings = report["warnings"]
    assert isinstance(warnings, list)
    assert any("nicht in der Sammlung" in str(w) for w in warnings)
