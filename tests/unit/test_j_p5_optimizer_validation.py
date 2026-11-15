from __future__ import annotations

import json
from pathlib import Path

from commander_lab.decision_statistics import holm_adjust, paired_randomization_p_value
from commander_lab.models import ObjectiveVector

ROOT = Path(__file__).resolve().parents[2]


def test_p5_holdout_is_sealed_and_untouched() -> None:
    data = (ROOT / "data/evals/holdout/J_P5_OPTIMIZER_HOLDOUT_v1.json").read_bytes()
    import hashlib

    assert (
        hashlib.sha256(data).hexdigest()
        == "b75e8622097221b00ad51322e2ad13fe5158cfd8647e92d2cb21a0d65b447203"
    )
    payload = json.loads(data)
    assert payload["status"] == "sealed_untouched"
    assert payload["outcomes_evaluated_at_seal"] is False
    assert payload["scenario_count"] == 24


def test_robust_objective_has_exact_required_axes() -> None:
    fields = set(ObjectiveVector.model_fields)
    assert fields == {
        "central_performance",
        "worst_quartile",
        "commander_independence",
        "rebuild",
        "finish_reliability",
        "matchup_robustness",
        "pod_size_robustness",
        "seat_robustness",
        "opponent_uncertainty",
        "physical_allocation",
    }


def test_paired_randomization_and_holm_are_deterministic() -> None:
    diffs = (1, 1, 0, 1, -1, 1, 0, 1)
    p1 = paired_randomization_p_value(diffs, seed=11)
    p2 = paired_randomization_p_value(diffs, seed=11)
    assert p1 == p2
    adjusted = holm_adjust((p1, 0.04, 0.20))
    assert len(adjusted) == 3
    assert all(0 <= x <= 1 for x in adjusted)


def test_current_challenge_set_preserves_classes_and_truth_boundary() -> None:
    payload = json.loads(
        (ROOT / "data/evals/golden/J_P5_OPTIMIZER_CHALLENGE_SET_v1.json").read_text()
    )
    assert {row["class"] for row in payload["variants"]} == {"good", "neutral", "bad"}
    assert payload["evidence_boundary"] == "structural_model_estimates"
    assert payload["canonical_mutation_allowed"] is False
    assert {row["deck_id"] for row in payload["variants"]} == {"rogshai/current"}
