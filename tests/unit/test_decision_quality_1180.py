from __future__ import annotations

from commander_lab.decision_information import (
    DecisionInformationStatus,
    build_decision_information_state,
)
from commander_lab.model_informativeness import assess_model_informativeness
from commander_lab.semantic_evidence import (
    DecisionMateriality,
    SemanticConfidence,
    SemanticEvidenceRecord,
    SemanticEvidenceType,
    semantic_evidence_summary,
)


def _comparison(low: float, high: float, effect: float = 0.0, *, iterations: int = 64):
    return {
        "status": "completed",
        "paired": {
            "placement_improvement": effect,
            "confidence_interval": [low, high],
            "monte_carlo_standard_error": abs(high - low) / 4,
        },
        "precision_context": {
            "current_iterations": iterations,
            "preregistered_precision_ceiling": 1024,
            "additional_precision_authorized": False,
        },
    }


def test_decision_information_routes_material_states_and_ceiling():
    assert (
        build_decision_information_state(_comparison(0.03, 0.08, 0.05)).status
        == DecisionInformationStatus.STOP_WITH_PREFERENCE
    )
    assert (
        build_decision_information_state(_comparison(-0.08, -0.03, -0.05)).status
        == DecisionInformationStatus.STOP
    )
    assert (
        build_decision_information_state(_comparison(-0.01, 0.01)).status
        == DecisionInformationStatus.NO_MATERIAL_DECISION_DIFFERENCE
    )
    assert (
        build_decision_information_state(_comparison(-0.04, 0.05, iterations=512)).status
        == DecisionInformationStatus.MORE_SIMULATIONS_USEFUL
    )
    assert (
        build_decision_information_state(_comparison(-0.04, 0.05, iterations=1024)).status
        == DecisionInformationStatus.PRECISION_CEILING_REACHED
    )


def test_model_information_limit_preempts_more_seed_work_when_cohort_is_broadly_nonseparable():
    rows = tuple({"confidence_interval": [-0.05, 0.05]} for _ in range(10))
    info = assess_model_informativeness(
        baseline_place_1_share=0.4,
        seat_results=None,
        variant_comparisons=rows,
        failure_mode_metrics=(),
    ).as_dict()
    assert info["status"] == "MODEL_INFORMATION_LIMIT"
    state = build_decision_information_state(
        _comparison(-0.05, 0.05, iterations=512), model_informativeness=info
    )
    assert state.status == DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC


def test_opponent_and_tactical_routes_remain_distinct():
    comparison = _comparison(-0.04, 0.05, iterations=256)
    opponent = build_decision_information_state(comparison, scenario_spread=0.2)
    assert opponent.status == DecisionInformationStatus.OPPONENT_UNCERTAINTY_DOMINATES
    tactical = build_decision_information_state(comparison, tactical_evidence_required=True)
    assert tactical.status == DecisionInformationStatus.TACTICAL_EVIDENCE_NEEDED


def test_material_semantic_conflict_preserves_both_claims_and_defers():
    common = dict(
        card_id="card-x",
        oracle_name="Conflict Card",
        feature="decision_feature_x",
        confidence=SemanticConfidence.HIGH,
        source_version="1",
        extraction_method="fixture",
        review_status="unreviewed",
        decision_materiality=DecisionMateriality.HIGH,
    )
    left = SemanticEvidenceRecord(
        **common,
        value=True,
        evidence_type=SemanticEvidenceType.CANONICAL_PROJECT,
        source_id="source-a",
    )
    right = SemanticEvidenceRecord(
        **common,
        value=False,
        evidence_type=SemanticEvidenceType.PROJECT_DERIVED,
        source_id="source-b",
    )
    summary = semantic_evidence_summary(
        oracle_name="Conflict Card", profile=None, additional_records=(left, right)
    )
    conflict = summary["semantic_conflict"]
    assert conflict["material_conflict"] is True
    assert conflict["requires_semantic_adjudication"] is True
    assert conflict["automatic_promotion"] is False
    assert conflict["automatic_rejection"] is False
    assert len(conflict["records"]) == 2
    assert summary["needs_targeted_adjudication"] is True
    assert len(summary["semantic_evidence_hash"]) == 64
