from __future__ import annotations

import json
from pathlib import Path

from commander_lab import __version__
from commander_lab.api.tool_server import create_app
from commander_lab.models import MatchupBatchInput, ToolStatus
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_api_version_tracks_package_version() -> None:
    app = create_app(ROOT)
    assert app.version == __version__ == "1.17.1"


def test_consumed_p5_holdout_remains_regression_only() -> None:
    seal = json.loads((ROOT / "docs/J_P5_HOLDOUT_SEAL.json").read_text(encoding="utf-8"))
    assert seal["holdout_id"] == "J_P5_OPTIMIZER_HOLDOUT_v1"
    assert seal["sha256"] == "b75e8622097221b00ad51322e2ad13fe5158cfd8647e92d2cb21a0d65b447203"
    assert seal["evaluation_count"] == 1
    assert seal["outcomes_evaluated"] is True
    assert seal["post_holdout_tuning_performed"] is False


def test_j_p6_baseline_is_bound_to_final_j_p5_main() -> None:
    freeze = json.loads((ROOT / "docs/J_P6_BASELINE_FREEZE.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "config/J_P6_BENCHMARK_POLICY_v1.json").read_text(encoding="utf-8"))
    expected = "0d5dbc633d0776f72e80e271e52234018e80e307"
    assert freeze["software_commit"] == expected
    assert policy["baseline_main_commit"] == expected
    assert freeze["p5_holdout_evaluation_count"] == 1
    assert freeze["p5_post_holdout_tuning"] is False
    assert policy["holdout_policy"].startswith("P4 and P5 consumed holdouts are regression-only")


def test_fixed_seed_structural_result_is_deterministic() -> None:
    service = CommanderToolService(ROOT)
    deck = service.decks["rogshai/current"]
    first = service.run_matchup_batch(
        MatchupBatchInput(
            deck_id="rogshai/current",
            iterations=4,
            seed=2026080901,
            max_turns=20,
            workers=1,
        )
    )
    second = service.run_matchup_batch(
        MatchupBatchInput(
            deck_id="rogshai/current",
            iterations=4,
            seed=2026080901,
            max_turns=20,
            workers=1,
        )
    )
    assert first.status == ToolStatus.COMPLETED
    assert second.status == ToolStatus.COMPLETED
    assert first.result == second.result
    assert first.metadata.run_identity_hash == second.metadata.run_identity_hash
    assert deck.deck_hash == "7b7d03aa16be6586df8f8a4e9f1acd30f85ad2e8e45e7889e700353a6f19c126"
