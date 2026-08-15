from __future__ import annotations

import pytest

from commander_lab.decision_information import (
    DecisionInformationStatus,
    build_decision_information_state,
)
from commander_lab.decision_quality import (
    ClosureSignal,
    DecisionStage,
    DomainInputValidityStatus,
    DomainQuestionScope,
    ExperimentEvidenceTarget,
    ModelResolutionStatus,
    OpponentAmbiguitySet,
    OpponentAmbiguityVariant,
    RobustDecisionStatus,
    SeedBlockEvidenceClass,
    StructuralFidelityClass,
    assess_domain_input_validity,
    assess_structural_fidelity,
    build_model_resolution_profile,
    classify_experiment_semantics,
    classify_seed_block_evidence,
    diagnose_closure,
    integrate_robust_decision,
)
from commander_lab.models.opponents import OpponentEvidenceKind


def _completed_comparison(interval: tuple[float, float] = (0.08, 0.12)) -> dict[str, object]:
    return {
        "status": "completed",
        "paired": {
            "placement_improvement": 0.10,
            "confidence_interval": list(interval),
            "monte_carlo_standard_error": 0.01,
        },
    }


def test_local_partial_synthetic_opponent_blocks_strong_decision() -> None:
    report = assess_domain_input_validity(
        scope=DomainQuestionScope.LOCAL_CURRENT_MATCHUP,
        evidence_kinds=(
            OpponentEvidenceKind.PARTIALLY_OBSERVED,
            OpponentEvidenceKind.SYNTHETIC_COMPLETION,
        ),
        known_real_slots=54,
        synthetic_slots=46,
        unknown_slots=0,
    )
    assert report.status == DomainInputValidityStatus.LIMITED
    assert report.strong_decision_allowed is False
    assert any("synthetic" in item for item in report.limitations)


def test_verified_full_local_opponent_allows_next_validity_gate() -> None:
    report = assess_domain_input_validity(
        scope=DomainQuestionScope.LOCAL_CURRENT_MATCHUP,
        evidence_kinds=(OpponentEvidenceKind.VERIFIED_FULL_DECK,),
        known_real_slots=100,
        synthetic_slots=0,
        unknown_slots=0,
    )
    assert report.status == DomainInputValidityStatus.ADEQUATE
    assert report.strong_decision_allowed is True


def test_official_precon_is_adequate_only_for_declared_baseline_scope() -> None:
    baseline = assess_domain_input_validity(
        scope=DomainQuestionScope.OFFICIAL_BASELINE,
        evidence_kinds=(OpponentEvidenceKind.OFFICIAL_PRECON,),
    )
    local = assess_domain_input_validity(
        scope=DomainQuestionScope.LOCAL_CURRENT_MATCHUP,
        evidence_kinds=(OpponentEvidenceKind.OFFICIAL_PRECON,),
    )
    assert baseline.status == DomainInputValidityStatus.ADEQUATE
    assert baseline.strong_decision_allowed is True
    assert local.status == DomainInputValidityStatus.LIMITED
    assert local.strong_decision_allowed is False


def test_ambiguity_set_has_no_probability_weights() -> None:
    ambiguity = OpponentAmbiguitySet(
        opponent_id="cosmic",
        variants=(
            OpponentAmbiguityVariant(
                variant_id="public_archetype_a",
                evidence_kinds=("synthetic_completion",),
                external_archetype_prior=True,
            ),
            OpponentAmbiguityVariant(
                variant_id="public_archetype_b",
                evidence_kinds=("synthetic_completion",),
                external_archetype_prior=True,
            ),
        ),
    )
    assert ambiguity.probability_weights is None


def test_question_specific_fidelity_distinguishes_approximation_and_unsupported() -> None:
    medium = assess_structural_fidelity(
        question_id="combat-finisher",
        required_functions=("draw", "combat_modifier"),
        represented_functions=("draw",),
        approximated_functions=("combat_modifier",),
    )
    unsupported = assess_structural_fidelity(
        question_id="copy-stack",
        required_functions=("copy_spell",),
    )
    assert medium.status == StructuralFidelityClass.MEDIUM_FIDELITY_FOR_QUESTION
    assert medium.strong_decision_allowed is True
    assert unsupported.status == StructuralFidelityClass.UNSUPPORTED_FOR_QUESTION
    assert unsupported.strong_decision_allowed is False


def test_model_resolution_requires_real_structural_axis_measurement() -> None:
    synthetic_only = build_model_resolution_profile(
        metric="placement_improvement",
        calibrated_sesoi=0.05,
    )
    measured = build_model_resolution_profile(
        metric="placement_improvement",
        calibrated_sesoi=0.05,
        measured_axis_spreads={"seed_block": 0.03, "seat": 0.07, "pilot": 0.04},
    )
    assert synthetic_only.status == ModelResolutionStatus.NEEDS_MEASUREMENT
    assert synthetic_only.effective_resolution is None
    assert measured.status == ModelResolutionStatus.MEASURED
    assert measured.effective_resolution == pytest.approx(0.07)


def test_same_model_seed_blocks_are_precision_not_independent_replication() -> None:
    assert (
        classify_seed_block_evidence(
            same_model=True,
            same_input_model=True,
            same_metric=True,
        )
        == SeedBlockEvidenceClass.PRECISION_ONLY_SAME_MODEL
    )
    assert (
        classify_seed_block_evidence(
            same_model=True,
            same_input_model=False,
            same_metric=True,
        )
        == SeedBlockEvidenceClass.DISTINCT_STRUCTURAL_EVIDENCE_AXIS
    )


def test_closure_diagnostic_separates_value_from_closing() -> None:
    baseline = {
        "resources_generated": 10.0,
        "engine_value": 8.0,
        "normal_damage_dealt": 20.0,
        "commander_damage_dealt": 10.0,
        "lands_played": 7.0,
        "ramp_resolved": 2.0,
        "removals_resolved": 2.0,
        "counters_resolved": 2.0,
        "protections_resolved": 2.0,
        "wipes_resolved": 1.0,
    }
    candidate = {
        **baseline,
        "resources_generated": 14.0,
        "engine_value": 12.0,
        "normal_damage_dealt": 18.0,
        "commander_damage_dealt": 8.0,
        "removals_resolved": 4.0,
    }
    diagnostic = diagnose_closure(candidate=candidate, baseline=baseline)
    assert ClosureSignal.RESOURCE_GAIN_WITHOUT_CLOSURE in diagnostic.signals
    assert ClosureSignal.VALUE_ENGINE_STALL in diagnostic.signals
    assert ClosureSignal.COMMANDER_DAMAGE_STALL in diagnostic.signals
    assert ClosureSignal.INTERACTION_OVERLOAD in diagnostic.signals
    assert ClosureSignal.UNSUPPORTED_BY_STRUCTURAL_MODEL in diagnostic.signals
    assert "recast_affordability" in diagnostic.unsupported_metrics


def test_single_swap_is_replacement_not_independent_cut_and_add() -> None:
    semantics = classify_experiment_semantics(removed_cards=1, added_cards=1)
    assert semantics.target == ExperimentEvidenceTarget.REPLACEMENT
    assert semantics.supports_independent_cut_claim is False
    assert semantics.supports_independent_add_claim is False


def test_cut_requires_explicit_neutral_replacement_control() -> None:
    semantics = classify_experiment_semantics(
        removed_cards=1,
        added_cards=1,
        neutral_control_added=True,
    )
    assert semantics.target == ExperimentEvidenceTarget.CUT
    assert semantics.supports_independent_cut_claim is True


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


def test_robust_integrator_requires_domain_fidelity_information_and_resolution() -> None:
    domain = assess_domain_input_validity(
        scope=DomainQuestionScope.LOCAL_CURRENT_MATCHUP,
        evidence_kinds=(OpponentEvidenceKind.VERIFIED_FULL_DECK,),
        known_real_slots=100,
        synthetic_slots=0,
        unknown_slots=0,
    )
    fidelity = assess_structural_fidelity(
        question_id="placement",
        required_functions=("placement",),
        represented_functions=("placement",),
    )
    synthetic_only = build_model_resolution_profile(
        metric="placement_improvement",
        calibrated_sesoi=0.05,
    )
    result = integrate_robust_decision(
        comparison_valid=True,
        interval=(0.10, 0.14),
        domain_validity=domain,
        structural_fidelity=fidelity,
        model_information_limit=False,
        model_resolution=synthetic_only,
    )
    assert result.status == RobustDecisionStatus.MODEL_RESOLUTION_LIMIT


def test_robust_integrator_requires_confirmatory_then_final_holdout() -> None:
    domain = assess_domain_input_validity(
        scope=DomainQuestionScope.LOCAL_CURRENT_MATCHUP,
        evidence_kinds=(OpponentEvidenceKind.VERIFIED_FULL_DECK,),
        known_real_slots=100,
        synthetic_slots=0,
        unknown_slots=0,
    )
    fidelity = assess_structural_fidelity(
        question_id="placement",
        required_functions=("placement",),
        represented_functions=("placement",),
    )
    resolution = build_model_resolution_profile(
        metric="placement_improvement",
        calibrated_sesoi=0.05,
        measured_axis_spreads={"null_seed_block": 0.04, "seat": 0.05},
    )
    exploratory = integrate_robust_decision(
        comparison_valid=True,
        interval=(0.09, 0.12),
        domain_validity=domain,
        structural_fidelity=fidelity,
        model_information_limit=False,
        model_resolution=resolution,
        robustness_axes={"pilot": True, "opponent": True, "commander_denial": True},
        stage=DecisionStage.EXPLORATORY,
    )
    final_without_holdout = integrate_robust_decision(
        comparison_valid=True,
        interval=(0.09, 0.12),
        domain_validity=domain,
        structural_fidelity=fidelity,
        model_information_limit=False,
        model_resolution=resolution,
        robustness_axes={"pilot": True, "opponent": True, "commander_denial": True},
        stage=DecisionStage.FINAL,
        confirmatory_passed=True,
        holdout_passed=False,
    )
    final = integrate_robust_decision(
        comparison_valid=True,
        interval=(0.09, 0.12),
        domain_validity=domain,
        structural_fidelity=fidelity,
        model_information_limit=False,
        model_resolution=resolution,
        robustness_axes={"pilot": True, "opponent": True, "commander_denial": True},
        stage=DecisionStage.FINAL,
        confirmatory_passed=True,
        holdout_passed=True,
    )
    assert exploratory.status == RobustDecisionStatus.CONFIRMATORY_REQUIRED
    assert final_without_holdout.status == RobustDecisionStatus.HOLDOUT_REQUIRED
    assert final.status == RobustDecisionStatus.PROMOTE
