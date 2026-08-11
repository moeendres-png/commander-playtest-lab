from __future__ import annotations

import json
from pathlib import Path

from commander_lab import __version__
from commander_lab.api.tool_server import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_api_version_tracks_package_version() -> None:
    app = create_app(ROOT)
    assert app.version == __version__ == "1.15.0"


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


def test_release_truth_includes_real_p3_feasibility_evidence() -> None:
    workflow = (ROOT / ".github/workflows/release-artifacts.yml").read_text(encoding="utf-8")
    assert 'docs/J_P3_PROVIDER_DECISION.json' in workflow
    assert 'external_engine_provider_decision' in workflow
    assert 'xmage_real_execution' in workflow
    assert 'forge_real_execution' in workflow
    assert 'structural_tactical_and_real_external_feasibility_evidence' in workflow
    assert 'external_engine_production_ready": False' in workflow
    assert 'wheel-verify/bin/commander-lab" --help' in workflow
    assert 'XMage/Forge observations = 0' not in workflow
    assert '"validation_level": "structural_and_tactical_only"' not in workflow
