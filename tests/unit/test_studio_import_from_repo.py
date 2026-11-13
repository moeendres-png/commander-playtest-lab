"""``import-all --from-repo`` over a small repository-shaped folder. All data is synthetic."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from commander_lab.studio import StudioStore, import_all, importers, repo_import
from commander_lab.studio.__main__ import main
from tests.unit.test_studio_builder import _fill, _public_file
from tests.unit.test_studio_counted_universe import FIELDS, _both
from tests.unit.test_studio_import_all import _decklists
from tests.unit.test_studio_roles_import import FILLER, FOREST, _file
from tests.unit.test_studio_store import _synthetic_cards, _workbook
from tests.unit.test_studio_universe_web import _deck

COMMANDER = "Test Commander"


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _research(tmp_path: Path, *, only: tuple[str, ...] | None = None) -> Path:
    """A repository-shaped ``data/research`` folder with one small file per kind."""
    research = tmp_path / "research"

    def wanted(name: str) -> bool:
        return only is None or name in only

    if wanted("collection"):
        sheets = load_workbook(_workbook(tmp_path / "cards.xlsx", _synthetic_cards()))
        for sheet in sheets.worksheets:
            target = research / repo_import.COLLECTION_FOLDER / f"{sheet.title}.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                for row in sheet.iter_rows(values_only=True):
                    writer.writerow(["" if cell is None else cell for cell in row])
    if wanted("corpus"):
        _decklists(research / repo_import.CORPUS_FOLDER / "edhrec" / "upgraded")
    if wanted("roles"):
        folder = research / repo_import.ROLES_FOLDER
        folder.mkdir(parents=True)
        _file(folder, "roles_s1_synthetic.json", {"ramp": [FOREST], "card_draw": [FILLER]})
    if wanted("edhrec"):
        row = {
            "card_id": "card:project:0007",
            "card_name": "Swarm Rat",
            "theme": "general",
            "url": "https://example.invalid/general",
            "snapshot_utc": "2026-11-09T00:00:00Z",
            "num_decks": 50,
            "potential_decks": 1000,
            "inclusion_pct": 5.0,
            "lift": "1.5",
        }
        _write_csv(
            research / repo_import.EDHREC_FOLDER / "edhrec_table_synthetic_1.csv",
            [row],
            list(row),
        )
    if wanted("playgroup"):
        folder = research / repo_import.PLAYGROUP_FOLDER
        folder.mkdir(parents=True)
        record = {
            "card_name": "Swarm Rat",
            "slug": "swarm-rat",
            "card_id": "card:project:0007",
            "oracle_id": "oracle-swarm-rat",
            "format_mode": "multiplayer",
            "live_inclusion_pct": 4.0,
            "times_brought": 100,
            "fetch_status": "OK",
            "top_commanders": [],
            "final_zones": [],
        }
        (folder / "playgroup_card_atlas_1.jsonl").write_text(
            json.dumps(record) + "\n", encoding="utf-8"
        )
    if wanted("counted"):
        research.mkdir(parents=True, exist_ok=True)
        _write_csv(research / "synthetic_decklist_inclusion_20261112.csv", _both(), FIELDS)
    return research


def _args(**given: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "commander": COMMANDER,
        "inventory": None,
        "scryfall": None,
        "roles": None,
        "rulings": None,
        "from_repo": True,
        "signals": None,
        "decklists": None,
        "decklist_format": "edhrec",
        "marks": None,
        "expect_pool": None,
    }
    values.update(given)
    return argparse.Namespace(**values)


@pytest.fixture
def scryfall(tmp_path: Path) -> str:
    return str(_public_file(tmp_path / "oracle.jsonl.gz"))


def _steps(result: import_all.ImportAllResult) -> dict[str, import_all.StepResult]:
    return {step["step"]: step for step in result["steps"]}


def test_from_repo_runs_every_repository_step_and_extends_the_layer_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scryfall: str
) -> None:
    monkeypatch.setattr(import_all, "_RESEARCH", _research(tmp_path))
    store = StudioStore.open(tmp_path / "studio")
    result = import_all.run(_args(scryfall=scryfall), store)
    steps = _steps(result)
    assert not result["failed"], steps
    for name in (
        "Sammlung",
        "Scryfall-Kartenfakten",
        "Rollen",
        "Decklisten-Korpus (Repo)",
        "Oracle-Zuordnung des Korpus",
        "EDHREC-Beobachtungen (Repo)",
        "Playgroup-Atlas (Repo)",
        "Signale research",
    ):
        assert steps[name]["status"] == "IMPORTED", (name, steps[name])
    assert steps["Regeltexte"]["status"] == "NOT_PROVIDED"  # no rulings file in this folder
    assert store.count("corpus_deck") == 3 and store.count("inventory") == 77
    layers = {layer["key"]: layer for layer in result["layers"]}
    assert layers["corpus"]["rows"] == 3 and layers["corpus"]["covered"] > 0
    assert layers["observations"]["rows"] == 2 and layers["observations"]["covered"] == 1
    assert layers["playgroup"]["rows"] == 1 and layers["playgroup"]["covered"] == 1
    assert layers["signal:decklist_universe:edhrec:3"]["rows"] == 4
    assert result["pool_size"] == 75
    # The corpus feeds the automatic universe only through its local decks: 3 are below the
    # minimum of 30, so the counted file of the repository is the chosen one.
    from commander_lab.studio import strength_view
    from commander_lab.studio.strength import StrengthSettings

    chosen = strength_view.compute(store, COMMANDER, StrengthSettings())["universe_choice"]
    assert chosen["kind"] == "counted" and chosen["automatic"] is True
    store.close()


def test_from_repo_needs_the_scryfall_file_and_says_so_in_german(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(import_all, "_RESEARCH", _research(tmp_path))
    with pytest.raises(SystemExit) as stopped:
        main(
            [
                "--data",
                str(tmp_path / "studio"),
                "import-all",
                "--commander",
                COMMANDER,
                "--from-repo",
            ]
        )
    message = str(stopped.value)
    assert "--from-repo braucht --scryfall" in message and "nicht heruntergeladen" in message
    store = StudioStore.open(tmp_path / "studio")
    assert store.count("inventory") == 0  # nothing ran before the check
    store.close()
    with pytest.raises(SystemExit, match="--inventory"):
        main(["--data", str(tmp_path / "studio"), "import-all", "--commander", COMMANDER])


def test_explicit_arguments_keep_working_and_win_over_the_repo_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scryfall: str
) -> None:
    monkeypatch.setattr(import_all, "_RESEARCH", _research(tmp_path))
    workbook = _workbook(tmp_path / "own.xlsx", _synthetic_cards()[:10])
    store = StudioStore.open(tmp_path / "studio")
    args = _args(
        scryfall=scryfall,
        inventory=str(workbook),
        decklists=str(_decklists(tmp_path / "own-decks")),
    )
    steps = _steps(import_all.run(args, store))
    assert steps["Sammlung"]["status"] == "IMPORTED" and store.count("inventory") == 10
    assert steps["Decklisten"]["status"] == "IMPORTED"
    assert steps["Decklisten-Korpus (Repo)"]["status"] == "NOT_PROVIDED"
    assert store.count("corpus_deck") == 3  # the explicit folder, not the repo corpus
    store.close()
    # Without --from-repo nothing of the repository is read except the signal defaults.
    plain = StudioStore.open(tmp_path / "plain")
    steps = _steps(import_all.run(_args(inventory=str(workbook), from_repo=False), plain))
    assert "Decklisten-Korpus (Repo)" not in steps and plain.count("corpus_deck") == 0
    plain.close()


def test_a_repository_without_a_folder_reports_that_step_as_not_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scryfall: str
) -> None:
    monkeypatch.setattr(import_all, "_RESEARCH", _research(tmp_path, only=("collection",)))
    store = StudioStore.open(tmp_path / "studio")
    steps = _steps(import_all.run(_args(scryfall=scryfall), store))
    assert steps["Sammlung"]["status"] == "IMPORTED"
    for name in (
        "Rollen",
        "Decklisten-Korpus (Repo)",
        "Oracle-Zuordnung des Korpus",
        "EDHREC-Beobachtungen (Repo)",
        "Playgroup-Atlas (Repo)",
    ):
        assert steps[name]["status"] == "NOT_PROVIDED", name
    store.close()
    monkeypatch.setattr(import_all, "_RESEARCH", tmp_path / "empty")
    with pytest.raises(ValueError, match="keine Sammlung im Repo"):
        import_all.run(_args(scryfall=scryfall), StudioStore.open(tmp_path / "other"))


def test_repo_files_are_found_from_a_root_folder(tmp_path: Path) -> None:
    found = repo_import.RepoFiles.discover(_research(tmp_path))
    assert found.collection_dir is not None and found.corpus_dir is not None
    assert [path.name for path in found.roles] == ["roles_s1_synthetic.json"]
    assert len(found.edhrec_parts) == 1 and len(found.playgroup_parts) == 1
    empty = repo_import.RepoFiles.discover(tmp_path / "nothing")
    assert empty.collection_dir is None and empty.corpus_dir is None
    assert not empty.roles and not empty.edhrec_parts and not empty.playgroup_parts
    with pytest.raises(ValueError, match="no sheet CSVs"):
        repo_import.build_inventory_workbook(tmp_path / "nothing", tmp_path / "out.xlsx")


def test_the_workbook_built_from_csvs_is_the_one_the_importer_reads(tmp_path: Path) -> None:
    research = _research(tmp_path, only=("collection",))
    out = tmp_path / "built.xlsx"
    sheets = repo_import.build_inventory_workbook(research / repo_import.COLLECTION_FOLDER, out)
    assert sheets == [importers.IDENTITY_SHEET, importers.INVENTORY_SHEET]
    store = StudioStore.open(tmp_path / "studio")

    importers.import_inventory_workbook(store, out)
    assert store.count("card") == 77 and store.count("inventory") == 77
    store.close()


def test_the_oracle_mapping_uses_the_front_face_and_never_the_back_half(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    _deck(store, "m1", "edhrec", 3, ["Filler 00 // Hidden Back", "Hidden Back", "Unknown Thing"])
    store.connection.commit()
    result = repo_import.map_corpus_oracle_ids(store.connection)
    rows = {
        str(row["card_name"]): row["oracle_id"]
        for row in store.connection.execute(
            "SELECT card_name, oracle_id FROM corpus_deck_card WHERE deck_id = 'm1'"
        )
    }
    assert rows["Filler 00 // Hidden Back"] is not None and rows["Filler 00 // Hidden Back"] != ""
    assert rows["Hidden Back"] is None  # the back half of a two-part name is another card
    assert rows["Unknown Thing"] is None
    assert result["mapped_exact"] >= 1 and result["unresolved_names"] >= 2
    again = repo_import.map_corpus_oracle_ids(store.connection)
    assert again["names_to_map"] == result["unresolved_names"]  # idempotent: only the rest
    store.close()
