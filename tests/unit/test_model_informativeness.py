from __future__ import annotations

from commander_lab.advancement import decide_advancement
from commander_lab.model_informativeness import assess_model_informativeness


def _preliminary_variants() -> tuple[dict[str, object], ...]:
    return (
        {"confidence_interval": [-0.0703125, 0.0390625], "lower_tail": {"q10": 0.0}},
        {"confidence_interval": [-0.0234375, 0.0546875], "lower_tail": {"q10": 0.0}},
        {"confidence_interval": [-0.0703125, 0.0234375], "lower_tail": {"q10": 0.0}},
    )


def test_preliminary_saturated_artifact_triggers_diagnostic_gate() -> None:
    report = assess_model_informativeness(
        baseline_place_1_share=0.9296875,
        seat_results={
            "0": {"place_1_share": 0.96875},
            "1": {"place_1_share": 0.9375},
            "2": {"place_1_share": 0.921875},
            "3": {"place_1_share": 0.890625},
        },
        variant_comparisons=_preliminary_variants(),
        failure_mode_metrics=("average_placement", "average_commander_damage"),
    )

    assert report.status == "MODEL_INFORMATION_LIMIT"
    assert report.recommended_action == "DIAGNOSE_BEFORE_MORE_SEED_WORK"
    assert report.separable_variant_count == 0
    assert report.as_dict() == report.as_dict()


def test_more_seeds_without_more_information_cannot_promote_quality() -> None:
    first = assess_model_informativeness(
        baseline_place_1_share=0.93,
        seat_results={str(index): {"place_1_share": 0.91} for index in range(4)},
        variant_comparisons=_preliminary_variants(),
    )
    repeated = assess_model_informativeness(
        baseline_place_1_share=0.93,
        seat_results={str(index): {"place_1_share": 0.91} for index in range(4)},
        variant_comparisons=_preliminary_variants(),
    )

    assert repeated.status == "MODEL_INFORMATION_LIMIT"
    assert repeated.report_hash == first.report_hash
    assert repeated.evidence_class == "structural_model_diagnostic"


def test_discriminative_golden_artifact_permits_comparison() -> None:
    report = assess_model_informativeness(
        baseline_place_1_share=0.55,
        seat_results={
            "0": {"place_1_share": 0.62},
            "1": {"place_1_share": 0.47},
            "2": {"place_1_share": 0.56},
            "3": {"place_1_share": 0.51},
        },
        variant_comparisons=({"confidence_interval": [0.03, 0.19], "lower_tail": {"q10": -0.1}},),
        opponent_evidence_quality={"verified_full_deck": 3},
        failure_mode_metrics=("removal_pressure", "rebuild_delay"),
    )
    decision = decide_advancement(
        {
            "status": "completed",
            "paired": {
                "confidence_interval": [0.03, 0.19],
                "distributionally_robust_lower_bound": 0.01,
            },
        },
        model_informativeness=report.as_dict(),
    )

    assert report.status == "INFORMATIVE"
    assert decision.status == "advance"
    assert decision.sensitivity_allowed is True


def test_information_limit_blocks_finalist_advancement() -> None:
    decision = decide_advancement(
        {
            "status": "completed",
            "paired": {
                "confidence_interval": [-0.01, 0.04],
                "distributionally_robust_lower_bound": -0.08,
            },
        },
        model_informativeness={"status": "MODEL_INFORMATION_LIMIT"},
    )

    assert decision.status == "diagnose"
    assert decision.sensitivity_allowed is False
    assert decision.expensive_ablation_allowed is False
