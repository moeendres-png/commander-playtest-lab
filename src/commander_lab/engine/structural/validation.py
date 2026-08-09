from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import StructuralAbortLimits, StructuralBatchConfig

from .batch import run_structural_batch
from .project import load_project_structural_decks

VALIDATION_SCENARIOS: dict[str, tuple[str, ...]] = {
    "goldfish_korvold": ("korvold/current",),
    "goldfish_rogshai": ("rogshai/current",),
    "three_player": ("korvold/current", "rogshai/current", "synthetic/aggro"),
    "four_player": (
        "korvold/current",
        "rogshai/current",
        "synthetic/aggro",
        "synthetic/control",
    ),
    "five_player": (
        "korvold/current",
        "rogshai/current",
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    ),
}


def run_phase3_validation(
    root: str | Path,
    *,
    iterations: int = 24,
    workers: int = 1,
    seed: int = 20260804,
) -> dict[str, object]:
    root_path = Path(root)
    output_root = root_path / "data/runs/phase3_validation"
    output_root.mkdir(parents=True, exist_ok=True)
    decks = load_project_structural_decks(root_path, include_synthetic_fixtures=True)
    scenario_results: dict[str, object] = {}
    for index, (scenario_name, deck_ids) in enumerate(VALIDATION_SCENARIOS.items()):
        config = StructuralBatchConfig(
            run_id=f"phase3-{scenario_name}",
            seed=seed + index,
            iterations=iterations,
            deck_ids=deck_ids,
            workers=workers,
            output_directory=str(output_root / scenario_name),
            limits=StructuralAbortLimits(
                max_turns=35,
                max_events=30_000,
                max_no_progress_turns=20,
                max_spells_per_turn=8,
            ),
        )
        batch = run_structural_batch(config, decks)
        scenario_results[scenario_name] = {
            "estimate_type": batch.estimate_type,
            "iterations": batch.iterations,
            "completed_games": batch.completed_games,
            "aborted_games": batch.aborted_games,
            "aggregate": batch.aggregate,
            "result_path": batch.result_path,
            "first_log_sha256": batch.match_results[0].log_sha256,
        }
    summary = {
        "schema_version": "0.3.0",
        "estimate_type": "structural_model_estimates",
        "engine_validation_only": True,
        "synthetic_profiles_are_not_opponent_claims": True,
        "seed": seed,
        "iterations_per_scenario": iterations,
        "workers": workers,
        "scenarios": scenario_results,
    }
    (output_root / "validation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    return summary
