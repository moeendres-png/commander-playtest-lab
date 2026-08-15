from __future__ import annotations

from commander_lab.whole_deck.optimizer_calibration import (
    calibrate_decision_policy,
    calibration_report,
    synthetic_causal_fixtures,
)


def test_calibration_suite_covers_required_synthetic_directions() -> None:
    fixtures = synthetic_causal_fixtures()
    fixture_ids = {row.fixture_id for row in fixtures}
    assert fixture_ids == {
        "identical_control_null",
        "no_op_equivalent",
        "small_controlled_degradation",
        "large_controlled_degradation",
        "small_controlled_improvement",
        "large_controlled_improvement",
        "mana_color_failure",
        "commander_denial_fragility",
        "interaction_protection_deficiency",
    }
    assert {row.truth_direction for row in fixtures} == {-1, 0, 1}


def test_calibration_selects_smallest_policy_meeting_preregistered_targets() -> None:
    selected = calibrate_decision_policy()
    assert selected.policy.sesoi == 0.05
    assert selected.policy.equivalence_margin == 0.025
    assert selected.summary.targets_met
    assert selected.summary.false_promotions == 0
    assert selected.summary.false_eliminations == 0
    assert selected.summary.direction_recovery_rate == 1.0
    assert selected.summary.equivalence_accuracy == 1.0


def test_calibration_report_preserves_truth_boundary() -> None:
    report = calibration_report()
    assert report["evidence_context"] == "calibration"
    assert report["evidence_type"] == "synthetic_fixture"
    assert report["ground_truth_scope"] == "synthetic_model_fixture_only"
    assert report["real_commander_winrate_claim"] is False
