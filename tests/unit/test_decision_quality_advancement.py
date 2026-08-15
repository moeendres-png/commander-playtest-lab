from __future__ import annotations

from commander_lab.advancement import decide_advancement


def _comparison() -> dict[str, object]:
    return {
        "status": "completed",
        "paired": {
            "confidence_interval": [0.10, 0.20],
            "distributionally_robust_lower_bound": 0.05,
        },
    }


def test_domain_input_limit_precedes_positive_structural_effect() -> None:
    comparison = _comparison()
    comparison["domain_validity"] = {
        "status": "LIMITED",
        "strong_decision_allowed": False,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"
    assert decision.reason_code == "domain_input_validity_limit"


def test_fidelity_limit_precedes_positive_structural_effect() -> None:
    comparison = _comparison()
    comparison["structural_fidelity"] = {
        "status": "UNSUPPORTED_FOR_QUESTION",
        "strong_decision_allowed": False,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"
    assert decision.reason_code == "structural_fidelity_limit"


def test_unmeasured_resolution_precedes_positive_structural_effect() -> None:
    comparison = _comparison()
    comparison["model_resolution"] = {
        "status": "NEEDS_MEASUREMENT",
        "effective_resolution": None,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"
    assert decision.reason_code == "model_resolution_unmeasured"


def test_measured_resolution_controls_advancement_boundary() -> None:
    comparison = _comparison()
    comparison["model_resolution"] = {
        "status": "MEASURED",
        "effective_resolution": 0.12,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"

    comparison["paired"] = {
        "confidence_interval": [0.13, 0.20],
        "distributionally_robust_lower_bound": 0.05,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "advance"
