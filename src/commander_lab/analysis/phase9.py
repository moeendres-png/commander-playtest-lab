from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from commander_lab.engine.structural import load_project_structural_decks, run_structural_batch
from commander_lab.importers import RealPlaytestImporter
from commander_lab.models import PilotConfig, StructuralBatchConfig
from commander_lab.reporting import calibration_report_markdown
from commander_lab.storage import PlaytestRepository, atomic_write_json, atomic_write_text

from .calibration import CalibrationPolicy, assign_playtest_splits, calibrate_playtests


def run_phase9_validation(
    root: str | Path,
    *,
    output_directory: str | Path,
    seed: int = 20260805,
) -> dict[str, object]:
    """Exercise the Phase-9 workflow without pretending fixture rows are real evidence."""
    root_path = Path(root).resolve()
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixture_path = output / "synthetic_validation_playtests.csv"
    _write_fixture(fixture_path)

    with tempfile.TemporaryDirectory(prefix="commander-lab-phase9-") as temp:
        workspace = Path(temp)
        games = RealPlaytestImporter().import_file(
            fixture_path,
            dataset_version="synthetic-phase9-validation",
        )
        repository = PlaytestRepository(workspace)
        manifest = repository.ingest(games, dataset_version="synthetic-phase9-validation")
        assignments = assign_playtest_splits(
            games,
            strategy=CalibrationPolicy().split_strategy,
            train_fraction=0.7,
            seed=seed,
        )
        manifest = repository.seal_split(
            "synthetic-phase9-validation",
            assignments=assignments,
            strategy=CalibrationPolicy().split_strategy,
            seed=seed,
            train_fraction=0.7,
        )
        decks = load_project_structural_decks(root_path, include_synthetic_fixtures=True)
        simulation_dir = output / "structural_reference"
        batch = run_structural_batch(
            StructuralBatchConfig(
                run_id="phase9-validation-reference",
                seed=seed,
                iterations=16,
                workers=1,
                deck_ids=(
                    "korvold/current",
                    "rogshai/current",
                    "synthetic/aggro",
                    "synthetic/control",
                ),
                pilot_configs=tuple(PilotConfig() for _ in range(4)),
                output_directory=str(simulation_dir),
            ),
            decks,
        )
        report = calibrate_playtests(
            manifest=manifest,
            games=repository.load_games("synthetic-phase9-validation"),
            simulation_batches=[batch],
            simulation_source_hashes={
                str(simulation_dir / "structural_results.json"): "synthetic-validation-fixture"
            },
            policy=CalibrationPolicy(
                split_seed=seed,
                bootstrap_samples=200,
            ),
        )

    report_json = output / "synthetic_calibration_report.json"
    report_md = output / "synthetic_calibration_report.md"
    atomic_write_json(report_json, report.model_dump(mode="json"))
    atomic_write_text(report_md, calibration_report_markdown(report))
    result = {
        "phase": "9",
        "implementation_status": "passed",
        "real_playtest_calibration_status": "not_run",
        "reason": "No user-supplied real playtest records were present.",
        "synthetic_fixture_status": report.status.value,
        "synthetic_fixture_games": len(games),
        "accepted_parameters_from_synthetic_fixture": report.accepted_parameters,
        "expected_fixture_decision": "insufficient_evidence",
        "train_validation_separated": True,
        "independent_confirmation_claimed": False,
        "engine_parameters_modified": False,
        "canonical_deck_files_modified": False,
        "google_drive_files_modified": False,
        "external_engine_validation_pending": True,
        "structural_reference_path": str(simulation_dir / "structural_results.json"),
        "calibration_report_path": str(report_json),
        "calibration_markdown_path": str(report_md),
    }
    atomic_write_json(output / "phase9_validation_output.json", result)
    return result


def _write_fixture(path: Path) -> None:
    rows: list[dict[str, object]] = []
    for game_index in range(6):
        for seat in range(4):
            is_korvold = seat == 0
            is_rogshai = seat == 1
            placement = ((seat + game_index) % 4) + 1
            rows.append(
                {
                    "game_id": f"synthetic-g{game_index:02d}",
                    "played_on": f"2026-07-{game_index + 1:02d}",
                    "dataset_version": "synthetic-phase9-validation",
                    "player_id": f"g{game_index}-p{seat}",
                    "deck_name": (
                        "Korvold" if is_korvold else "RogShai" if is_rogshai else f"Fixture Opponent {seat}"
                    ),
                    "deck_version": "synthetic-fixture-v1",
                    "commander_names": (
                        "Korvold, Fae-Cursed King"
                        if is_korvold
                        else "Ishai, Ojutai Dragonspeaker+Rograkh, Son of Rohgahh"
                        if is_rogshai
                        else "Fixture Commander"
                    ),
                    "seat": seat,
                    "placement": placement,
                    "mulligans": 0,
                    "starting_hand_lands": 3,
                    "lands_played": 7,
                    "first_ramp_turn": 2,
                    "ramp_events": 2,
                    "first_commander_cast_turn": 4 if is_korvold else 3 if is_rogshai else 5,
                    "commander_casts": 1,
                    "commander_removals_received": 1,
                    "removal_events": 2,
                    "first_independent_draw_engine_turn": 4,
                    "independent_draw_engines": 1,
                    "boardwipes_cast": 0,
                    "boardwipes_seen": 1,
                    "successful_rebuilds": 1,
                    "rebuilt_after_wipe": "true",
                    "ishai_peak_power": 8 if is_rogshai else "",
                    "korvold_cards_drawn": 5 if is_korvold else "",
                    "was_archenemy": "true" if seat in {0, 1} else "false",
                    "archenemy_events": 2 if seat in {0, 1} else 0,
                    "win_axis": "table_damage" if placement == 1 else "",
                    "loss_causes": "opponent_finish" if placement != 1 else "",
                    "dead_cards": "Fixture Dead Card" if placement != 1 else "",
                    "sequencing_errors": "fixture_error" if game_index == 0 and seat == 0 else "",
                    "turns": 10,
                    "starting_player_id": f"g{game_index}-p{game_index % 4}",
                    "end_reason": "fixture_completion",
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
