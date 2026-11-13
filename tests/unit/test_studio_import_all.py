"""``import-all``: one checked import with a completeness table. All files are synthetic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, import_all
from commander_lab.studio.__main__ import main
from tests.unit.test_studio_builder import _public_file
from tests.unit.test_studio_store import _synthetic_cards, _workbook

COMMANDER = "Test Commander"


def _signals(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "commander_card_signals.csv").write_text(
        "commander_name,card_name,num_decks,potential_decks,synergy\n"
        f"{COMMANDER},Filler 03,40,100,0.12\n",
        encoding="utf-8",
    )
    return folder


def _decklists(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        payload = {
            "urlhash": f"h{index}",
            "variante": "upgraded",
            "bracket": 3,
            "savedate": "2026-10-01",
            "source_url": f"https://example.invalid/{index}",
            "commanders": [COMMANDER],
            "cards": [{"name": "Filler 03", "quantity": 1}, {"name": "Forest", "quantity": 5}],
            "karten_summe": 6,
            "parse_status": "ok",
        }
        (folder / f"h{index}.json").write_text(json.dumps(payload), encoding="utf-8")
    return folder


def _files(tmp_path: Path) -> dict[str, Path]:
    marks = tmp_path / "marks.json"
    marks.write_text(
        json.dumps(
            {
                "format": "studio-marks-1",
                "marks": [{"card_name": "Filler 03", "favorite": True}],
            }
        ),
        encoding="utf-8",
    )
    return {
        "inventory": _workbook(tmp_path / "cards.xlsx", _synthetic_cards()),
        "scryfall": _public_file(tmp_path / "oracle.jsonl.gz"),
        "signals": _signals(tmp_path / "sig"),
        "decklists": _decklists(tmp_path / "decks"),
        "marks": marks,
    }


@pytest.fixture(autouse=True)
def _no_repo_research(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(import_all, "_RESEARCH", tmp_path / "no-research")


def _layers(out: str) -> dict[str, str]:
    marker = "Vollständigkeit je Schicht"
    rows = out[out.index(marker) :].splitlines()[3:]
    found = {}
    for row in rows:
        if not row.strip():
            break
        found[row.split("  ")[0].strip()] = row.split()[-1]
    return found


def test_everything_given_is_imported_and_counted_per_layer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    code = main(
        [
            "--data", str(tmp_path / "studio"),
            "import-all", "--commander", COMMANDER,
            "--inventory", str(files["inventory"]),
            "--scryfall", str(files["scryfall"]),
            "--signals", str(files["signals"]),
            "--decklists", str(files["decklists"]),
            "--marks", str(files["marks"]),
        ]
    )  # fmt: skip
    out = capsys.readouterr().out
    assert code == 0, out
    assert "Datenbericht" in out
    layers = _layers(out)
    assert layers["Sammlung (Bestand)"] == "COMPLETE"
    assert layers["Kartenfakten (Scryfall)"] == "COMPLETE"
    assert layers["Rollen"] == "MISSING"  # no role file given
    assert layers["Quelldecks (Decklisten)"] == "PARTIAL"
    assert layers["Signal edhrec_commander_inclusion"] == "PARTIAL"
    assert layers["Markierungen"] == "PARTIAL"
    assert "NOT_PROVIDED" in out  # roles


def test_a_step_that_is_not_given_is_not_provided(tmp_path: Path) -> None:
    files = _files(tmp_path)
    store = StudioStore.open(tmp_path / "studio")
    args = argparse.Namespace(
        commander=COMMANDER,
        inventory=str(files["inventory"]),
        scryfall=None,
        roles=None,
        signals=None,
        decklists=None,
        decklist_format="edhrec",
        marks=None,
        expect_pool=None,
    )
    result = import_all.run(args, store)
    status = {step["step"]: step["status"] for step in result["steps"]}
    assert status["Sammlung"] == "IMPORTED"
    assert status["Scryfall-Kartenfakten"] == "NOT_PROVIDED"
    assert status["Rollen"] == "NOT_PROVIDED"
    assert status["Decklisten"] == "NOT_PROVIDED"
    assert status["Signale"] == "NOT_PROVIDED"
    assert status["Markierungen"] == "NOT_PROVIDED"
    layers = {layer["layer"]: layer for layer in result["layers"]}
    assert layers["Quelldecks (Decklisten)"]["status"] == "MISSING"
    assert layers["Kartenfakten (Scryfall)"]["covered"] == 0
    store.close()


def test_expect_pool_fails_when_the_size_differs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    base = [
        "--data", str(tmp_path / "studio"),
        "import-all", "--commander", COMMANDER,
        "--inventory", str(files["inventory"]),
        "--scryfall", str(files["scryfall"]),
    ]  # fmt: skip
    assert main([*base]) == 0
    out = capsys.readouterr().out
    size = int(out.split("Poolgröße: ")[1].split()[0])
    assert size > 0
    assert main([*base, "--expect-pool", str(size)]) == 0
    capsys.readouterr()
    assert main([*base, "--expect-pool", str(size + 1)]) == import_all.EXIT_POOL_MISMATCH
    captured = capsys.readouterr()
    assert "STIMMT NICHT" in captured.out
    assert f"erwartet {size + 1}" in captured.err


def test_a_failing_step_stops_the_rest_and_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _files(tmp_path)
    code = main(
        [
            "--data", str(tmp_path / "studio"),
            "import-all", "--commander", COMMANDER,
            "--inventory", str(files["inventory"]),
            "--scryfall", str(tmp_path / "missing.jsonl.gz"),
            "--marks", str(files["marks"]),
        ]
    )  # fmt: skip
    out = capsys.readouterr().out
    assert code == import_all.EXIT_STEP_FAILED
    assert "FAILED" in out
    assert "SKIPPED_AFTER_ERROR" in out


def test_default_signal_folders_are_those_with_signal_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    research = tmp_path / "research"
    _signals(research / "with_signals")
    (research / "other").mkdir(parents=True)
    (research / "other" / "notes.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(import_all, "_RESEARCH", research)
    assert [path.name for path in import_all.default_signal_folders()] == ["with_signals"]
    monkeypatch.setattr(import_all, "_RESEARCH", tmp_path / "absent")
    assert import_all.default_signal_folders() == []


def test_layer_overview_names_the_import_call_of_each_missing_layer(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio.web import create_app

    files = _files(tmp_path)
    store = StudioStore.open(tmp_path / "studio")
    from commander_lab.studio import importers

    importers.import_inventory_workbook(store, files["inventory"])
    store.close()
    with TestClient(create_app(tmp_path / "studio")) as client:
        body = client.get("/api/layers", params={"commander": COMMANDER}).json()
    layers = {item["key"]: item for item in body["layers"]}
    assert layers["inventory"]["status"] == "COMPLETE"
    assert layers["decklists"]["status"] == "MISSING"
    assert '--decklists "<Ordner>"' in layers["decklists"]["command"]
    assert f'--commander "{COMMANDER}"' in layers["roles"]["command"]
    assert "--signals" in body["signals_command"]


_SIGNAL_LAYERS = {
    "signal:edhrec_commander_inclusion",
    "signal:edhrec_bracket_inclusion:core",
    "signal:edhrec_bracket_inclusion:upgraded",
    "signal:edhrec_bracket_inclusion:optimized",
    "signal:edhrec_bracket_inclusion:cedh",
    "signal:edhrec_commander_synergy",
    "signal:edhrec_global_inclusion",
    "signal:spellbook_variants",
    "signal:tournament_lists",
    "signal:edhtop16_commander_play_rate",
}


def test_every_signal_layer_is_listed_as_missing_in_a_store_without_signals(
    tmp_path: Path,
) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio import importers
    from commander_lab.studio.web import create_app

    files = _files(tmp_path)
    store = StudioStore.open(tmp_path / "studio")
    importers.import_inventory_workbook(store, files["inventory"])
    _size, table = import_all.completeness(store, COMMANDER)
    store.close()
    signal_rows = {item["key"]: item for item in table if item["key"].startswith("signal:")}
    assert set(signal_rows) == _SIGNAL_LAYERS
    assert {item["status"] for item in signal_rows.values()} == {"MISSING"}
    with TestClient(create_app(tmp_path / "studio")) as client:
        body = client.get("/api/layers", params={"commander": COMMANDER}).json()
    api_rows = {item["key"]: item for item in body["layers"] if item["key"].startswith("signal:")}
    assert set(api_rows) == _SIGNAL_LAYERS
    assert all("--signals" in item["command"] for item in api_rows.values())
    assert "--signals" in body["signals_command"]
    script = (Path(import_all.__file__).parent / "static" / "ui.js").read_text(encoding="utf-8")
    assert "overview.signals_command" in script
