from __future__ import annotations

import pytest

from commander_lab.decision.information import (
    DecisionInformationStatus,
    build_decision_information_state,
)


def _completed_comparison(interval: tuple[float, float] = (0.08, 0.12)) -> dict[str, object]:
    return {
        "status": "completed",
        "paired": {
            "placement_improvement": 0.10,
            "confidence_interval": list(interval),
            "monte_carlo_standard_error": 0.01,
        },
    }


def test_decision_information_model_limit_beats_strong_looking_effect() -> None:
    state = build_decision_information_state(
        _completed_comparison(),
        model_informativeness={"status": "MODEL_INFORMATION_LIMIT"},
    )
    assert state.status == DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC
    assert state.next_recommended_experiment == "diagnose_model_information_before_more_seed_work"


def test_decision_information_domain_limit_beats_strong_looking_effect() -> None:
    state = build_decision_information_state(
        _completed_comparison(),
        domain_validity={
            "status": "LIMITED",
            "strong_decision_allowed": False,
            "recommended_action": "use_ambiguity_ensemble",
        },
    )
    assert state.status == DecisionInformationStatus.OPPONENT_UNCERTAINTY_DOMINATES
    assert state.next_recommended_experiment == "use_ambiguity_ensemble"


def test_decision_information_uses_measured_resolution_not_fixed_threshold() -> None:
    state = build_decision_information_state(
        _completed_comparison((0.06, 0.08)),
        model_resolution={"status": "MEASURED", "effective_resolution": 0.07},
    )
    assert state.indifference_threshold == pytest.approx(0.07)
    assert state.status == DecisionInformationStatus.MORE_SIMULATIONS_USEFUL
