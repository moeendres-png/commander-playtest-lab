from __future__ import annotations

from commander_lab.decision_information import (
    DecisionInformationStatus,
    build_decision_information_state,
)


def _comparison(low: float, high: float, effect: float = 0.0) -> dict[str, object]:
    return {
        "status": "completed",
        "paired": {
            "placement_improvement": effect,
            "confidence_interval": [low, high],
            "monte_carlo_standard_error": 0.02,
        },
    }


def test_decision_information_stops_on_material_preference() -> None:
    state = build_decision_information_state(_comparison(0.04, 0.10, 0.07))
    assert state.status == DecisionInformationStatus.STOP_WITH_PREFERENCE


def test_decision_information_stops_inside_indifference_region() -> None:
    state = build_decision_information_state(_comparison(-0.01, 0.02, 0.005))
    assert state.status == DecisionInformationStatus.NO_MATERIAL_DECISION_DIFFERENCE


def test_decision_information_distinguishes_model_tactical_and_opponent_uncertainty() -> None:
    comparison = _comparison(-0.10, 0.10)
    model = build_decision_information_state(
        comparison,
        model_informativeness={"status": "MODEL_INFORMATION_LIMIT"},
    )
    tactical = build_decision_information_state(comparison, tactical_evidence_required=True)
    opponent = build_decision_information_state(comparison, scenario_spread=0.5)

    assert model.status == DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC
    assert tactical.status == DecisionInformationStatus.TACTICAL_EVIDENCE_NEEDED
    assert opponent.status == DecisionInformationStatus.OPPONENT_UNCERTAINTY_DOMINATES


def test_more_simulations_only_when_seed_uncertainty_can_still_change_decision() -> None:
    state = build_decision_information_state(_comparison(-0.10, 0.08))
    assert state.status == DecisionInformationStatus.MORE_SIMULATIONS_USEFUL
