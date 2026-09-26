from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .optimizer_v2 import (
    CalibrationSummary,
    DecisionCalibrationPolicy,
    SyntheticCalibrationFixture,
    evaluate_calibration,
)

CALIBRATION_SUITE_VERSION = "optimizer-v2-calibration-0.1.0"


@dataclass(frozen=True, slots=True)
class CalibrationCandidate:
    policy: DecisionCalibrationPolicy
    summary: CalibrationSummary


def synthetic_causal_fixtures() -> tuple[SyntheticCalibrationFixture, ...]:
    """Construct deterministic model fixtures; none are real-game ground truth."""

    rows = (
        ("identical_control_null", 0, 0.000, -0.008, 0.008, 512),
        ("no_op_equivalent", 0, 0.004, -0.010, 0.016, 512),
        ("small_controlled_degradation", -1, -0.080, -0.105, -0.055, 512),
        ("large_controlled_degradation", -1, -0.220, -0.255, -0.185, 256),
        ("small_controlled_improvement", 1, 0.080, 0.055, 0.105, 512),
        ("large_controlled_improvement", 1, 0.220, 0.185, 0.255, 256),
        ("mana_color_failure", -1, -0.300, -0.340, -0.260, 256),
        ("commander_denial_fragility", -1, -0.160, -0.195, -0.125, 384),
        ("interaction_protection_deficiency", -1, -0.120, -0.150, -0.090, 384),
    )
    return tuple(
        SyntheticCalibrationFixture(
            fixture_id=fixture_id,
            truth_direction=direction,
            observed_delta=delta,
            interval_low=low,
            interval_high=high,
            sample_size=sample_size,
        )
        for fixture_id, direction, delta, low, high, sample_size in rows
    )


def calibrate_decision_policy(
    *,
    sesoi_candidates: Sequence[float] = (0.025, 0.05, 0.075, 0.10),
    max_false_promotion: float = 0.05,
    max_false_elimination: float = 0.05,
) -> CalibrationCandidate:
    """Choose the smallest synthetic-fixture SESOI meeting preregistered error goals."""

    if not sesoi_candidates:
        raise ValueError("calibration requires at least one SESOI candidate")
    fixtures = synthetic_causal_fixtures()
    candidates: list[CalibrationCandidate] = []
    for raw in sorted(set(float(value) for value in sesoi_candidates)):
        if raw <= 0.0:
            raise ValueError("SESOI candidates must be positive")
        policy = DecisionCalibrationPolicy(
            sesoi=raw,
            equivalence_margin=raw / 2.0,
            max_false_promotion=max_false_promotion,
            max_false_elimination=max_false_elimination,
        )
        candidates.append(
            CalibrationCandidate(
                policy=policy,
                summary=evaluate_calibration(fixtures, policy=policy),
            )
        )
    passing = [
        row
        for row in candidates
        if row.summary.targets_met
        and row.summary.direction_recovery_rate == 1.0
        and row.summary.equivalence_accuracy == 1.0
    ]
    if not passing:
        raise RuntimeError("no candidate decision policy passed the synthetic calibration suite")
    return min(passing, key=lambda row: row.policy.sesoi)


def calibration_report() -> dict[str, object]:
    selected = calibrate_decision_policy()
    return {
        "schema_version": "1.0.0",
        "suite_version": CALIBRATION_SUITE_VERSION,
        "evidence_context": "calibration",
        "evidence_type": "synthetic_fixture",
        "ground_truth_scope": "synthetic_model_fixture_only",
        "real_commander_winrate_claim": False,
        "selection_rule": "smallest_SESOI_meeting_preregistered_synthetic_error_targets",
        "selected_policy": selected.policy.model_dump(mode="json"),
        "summary": selected.summary.model_dump(mode="json"),
        "fixtures": [row.model_dump(mode="json") for row in synthetic_causal_fixtures()],
        "limitations": [
            "Synthetic causal fixtures test decision logic, not real-table effect sizes.",
            "Real legal deck perturbations are face-validity stress tests, not empirical ground truth.",
            "Confirmatory data must remain fresh and independent of adaptive search evaluations.",
        ],
    }
