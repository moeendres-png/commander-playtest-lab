from __future__ import annotations

import pytest

from commander_lab.adaptive_budget import (
    build_conservative_adaptive_budget_plan,
    challenge_quality_metrics,
)


def test_conservative_challenge_plan_reproduces_quality_safe_144_to_96_budget() -> None:
    buckets = {
        "good_1": "advance",
        "neutral_1": "explore",
        "bad_1": "deprioritize_static",
        "good_2": "advance",
        "neutral_2": "explore",
        "bad_2": "deprioritize_static",
    }
    labels = {
        "good_1": "good",
        "neutral_1": "neutral",
        "bad_1": "bad",
        "good_2": "good",
        "neutral_2": "neutral",
        "bad_2": "bad",
    }
    plan = build_conservative_adaptive_budget_plan(buckets, full_budget_per_candidate=24)
    quality = challenge_quality_metrics(plan, labels)

    assert plan.full_control_paired_comparisons == 144
    assert plan.planned_paired_comparisons == 96
    assert plan.simulation_reduction == pytest.approx(1 / 3)
    assert plan.noisy_early_elimination_allowed is False
    assert quality["material_finalist_recall"] == 1.0
    assert quality["false_elimination_rate_of_material_finalists"] == 0.0
    assert quality["quality_gate_pass"] is True
