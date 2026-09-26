from __future__ import annotations

from commander_lab.advancement import LEGACY_ADVANCEMENT_REASON, decide_advancement


def _comparison() -> dict[str, object]:
    return {
        "status": "completed",
        "paired": {
            "confidence_interval": [0.10, 0.20],
            "distributionally_robust_lower_bound": 0.05,
        },
    }


def test_domain_input_limit_precedes_legacy_retirement() -> None:
    comparison = _comparison()
    comparison["domain_validity"] = {
        "status": "LIMITED",
        "strong_decision_allowed": False,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"
    assert decision.reason_code == "domain_input_validity_limit"


def test_fidelity_limit_precedes_legacy_retirement() -> None:
    comparison = _comparison()
    comparison["structural_fidelity"] = {
        "status": "UNSUPPORTED_FOR_QUESTION",
        "strong_decision_allowed": False,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"
    assert decision.reason_code == "structural_fidelity_limit"


def test_unmeasured_resolution_remains_diagnostic_only() -> None:
    comparison = _comparison()
    comparison["model_resolution"] = {
        "status": "NEEDS_MEASUREMENT",
        "effective_resolution": None,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"
    assert decision.reason_code == "model_resolution_unmeasured"


def test_measured_legacy_resolution_cannot_control_advancement_boundary() -> None:
    comparison = _comparison()
    comparison["model_resolution"] = {
        "status": "MEASURED",
        "effective_resolution": 0.12,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"
    assert decision.reason_code == LEGACY_ADVANCEMENT_REASON
    assert not decision.sensitivity_allowed
    assert not decision.expensive_ablation_allowed

    comparison["paired"] = {
        "confidence_interval": [0.13, 0.20],
        "distributionally_robust_lower_bound": 0.05,
    }
    decision = decide_advancement(comparison)
    assert decision.status == "diagnose"
    assert decision.reason_code == LEGACY_ADVANCEMENT_REASON
    assert not decision.sensitivity_allowed
