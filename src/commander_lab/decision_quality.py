from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum

from commander_lab.models.opponents import OpponentEvidenceKind
from commander_lab.storage.run_identity import sha256_run_value


class DomainQuestionScope(StrEnum):
    OFFICIAL_BASELINE = "OFFICIAL_BASELINE"
    LOCAL_CURRENT_MATCHUP = "LOCAL_CURRENT_MATCHUP"
    STRUCTURAL_STRESS_TEST = "STRUCTURAL_STRESS_TEST"


class DomainInputValidityStatus(StrEnum):
    ADEQUATE = "ADEQUATE"
    LIMITED = "LIMITED"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class DomainInputValidityReport:
    scope: DomainQuestionScope
    status: DomainInputValidityStatus
    evidence_kinds: tuple[str, ...]
    known_real_slots: int | None
    synthetic_slots: int | None
    unknown_slots: int | None
    strong_decision_allowed: bool
    limitations: tuple[str, ...]
    recommended_action: str
    evidence_class: str = "domain_input_validity"
    truth_boundary: str = "input/domain-validity assessment; not empirical gameplay performance"

    @property
    def report_hash(self) -> str:
        return sha256_run_value(asdict(self))


def assess_domain_input_validity(
    *,
    scope: DomainQuestionScope,
    evidence_kinds: Sequence[OpponentEvidenceKind | str],
    known_real_slots: int | None = None,
    synthetic_slots: int | None = None,
    unknown_slots: int | None = None,
) -> DomainInputValidityReport:
    """Assess whether opponent/domain inputs can support the requested inference.

    Counts are descriptive only. No frequency, probability, or arbitrary percentage threshold is
    inferred from incomplete local opponent evidence.
    """
    if any(
        value is not None and value < 0
        for value in (known_real_slots, synthetic_slots, unknown_slots)
    ):
        raise ValueError("slot counts must be non-negative when supplied")
    kinds = tuple(
        dict.fromkeys(
            value.value if isinstance(value, OpponentEvidenceKind) else str(value)
            for value in evidence_kinds
        )
    )
    kind_set = set(kinds)
    limitations: list[str] = []

    verified_full = OpponentEvidenceKind.VERIFIED_FULL_DECK.value in kind_set
    official_precon = OpponentEvidenceKind.OFFICIAL_PRECON.value in kind_set
    synthetic = OpponentEvidenceKind.SYNTHETIC_COMPLETION.value in kind_set
    unknown = OpponentEvidenceKind.UNKNOWN.value in kind_set
    partial = bool(
        kind_set
        & {
            OpponentEvidenceKind.PARTIALLY_OBSERVED.value,
            OpponentEvidenceKind.REPORTED.value,
            OpponentEvidenceKind.INFERRED.value,
        }
    )
    has_unresolved_slots = (synthetic_slots or 0) > 0 or (unknown_slots or 0) > 0

    if scope == DomainQuestionScope.OFFICIAL_BASELINE:
        if verified_full or official_precon:
            status = DomainInputValidityStatus.ADEQUATE
            action = "use_only_for_the_declared_official_or_verified_baseline_question"
        else:
            status = DomainInputValidityStatus.INSUFFICIENT
            limitations.append("no verified full-deck or official-precon baseline is present")
            action = "obtain_a_verified_or_official_baseline"
    elif scope == DomainQuestionScope.LOCAL_CURRENT_MATCHUP:
        if verified_full and not has_unresolved_slots and not synthetic and not unknown:
            status = DomainInputValidityStatus.ADEQUATE
            action = "proceed_with_question_specific_model_fidelity_checks"
        elif not kinds or kind_set <= {OpponentEvidenceKind.UNKNOWN.value}:
            status = DomainInputValidityStatus.INSUFFICIENT
            limitations.append("local current deck identity is unsupported")
            action = "collect_direct_local_deck_evidence_before_strong_matchup_inference"
        else:
            status = DomainInputValidityStatus.LIMITED
            if official_precon and not verified_full:
                limitations.append(
                    "official precon is a strong baseline but current local deviations are unverified"
                )
            if partial:
                limitations.append("local opponent evidence is partial or inferred")
            if synthetic or (synthetic_slots or 0) > 0:
                limitations.append("synthetic completion is not local observation")
            if unknown or (unknown_slots or 0) > 0:
                limitations.append("real local slots remain unknown")
            action = "use_an_evidence_bounded_ambiguity_ensemble_or_collect_more_local_evidence"
    else:
        if kinds:
            status = DomainInputValidityStatus.ADEQUATE
            action = "use_as_structural_stress_evidence_only"
            if synthetic or partial or unknown or has_unresolved_slots:
                limitations.append(
                    "stress-test plausibility does not establish current local matchup truth"
                )
        else:
            status = DomainInputValidityStatus.INSUFFICIENT
            limitations.append("stress scenario lacks declared provenance")
            action = "declare_scenario_provenance_before_use"

    strong_allowed = status == DomainInputValidityStatus.ADEQUATE and scope != (
        DomainQuestionScope.STRUCTURAL_STRESS_TEST
    )
    return DomainInputValidityReport(
        scope=scope,
        status=status,
        evidence_kinds=kinds,
        known_real_slots=known_real_slots,
        synthetic_slots=synthetic_slots,
        unknown_slots=unknown_slots,
        strong_decision_allowed=strong_allowed,
        limitations=tuple(limitations),
        recommended_action=action,
    )


@dataclass(frozen=True)
class OpponentAmbiguityVariant:
    variant_id: str
    evidence_kinds: tuple[str, ...]
    source_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    external_archetype_prior: bool = False


@dataclass(frozen=True)
class OpponentAmbiguitySet:
    opponent_id: str
    variants: tuple[OpponentAmbiguityVariant, ...]
    probability_weights: None = None
    evidence_class: str = "synthetic_assumption"
    truth_boundary: str = (
        "plausible scenario family; variants are not probabilities and are not local observations"
    )

    def __post_init__(self) -> None:
        if not self.variants:
            raise ValueError("ambiguity set requires at least one plausible variant")
        ids = [row.variant_id for row in self.variants]
        if len(ids) != len(set(ids)):
            raise ValueError("ambiguity-set variant ids must be unique")


class StructuralFidelityClass(StrEnum):
    HIGH_FIDELITY_FOR_QUESTION = "HIGH_FIDELITY_FOR_QUESTION"
    MEDIUM_FIDELITY_FOR_QUESTION = "MEDIUM_FIDELITY_FOR_QUESTION"
    LOW_FIDELITY_FOR_QUESTION = "LOW_FIDELITY_FOR_QUESTION"
    UNSUPPORTED_FOR_QUESTION = "UNSUPPORTED_FOR_QUESTION"


@dataclass(frozen=True)
class StructuralFidelityReport:
    question_id: str
    status: StructuralFidelityClass
    required_functions: tuple[str, ...]
    represented_functions: tuple[str, ...]
    approximated_functions: tuple[str, ...]
    unsupported_functions: tuple[str, ...]
    strong_decision_allowed: bool
    recommended_action: str
    evidence_class: str = "structural_model_fidelity"
    truth_boundary: str = "question-specific model coverage; not rules-engine validation"

    @property
    def report_hash(self) -> str:
        return sha256_run_value(asdict(self))


def assess_structural_fidelity(
    *,
    question_id: str,
    required_functions: Sequence[str],
    represented_functions: Sequence[str] = (),
    approximated_functions: Sequence[str] = (),
    unsupported_functions: Sequence[str] = (),
) -> StructuralFidelityReport:
    required = tuple(dict.fromkeys(required_functions))
    represented = tuple(dict.fromkeys(represented_functions))
    approximated = tuple(dict.fromkeys(approximated_functions))
    explicit_unsupported = tuple(dict.fromkeys(unsupported_functions))
    required_set = set(required)
    represented_set = set(represented) & required_set
    approximated_set = set(approximated) & required_set
    overlap = represented_set & approximated_set
    if overlap:
        raise ValueError(
            f"functions cannot be both represented and approximated: {sorted(overlap)}"
        )
    unresolved = required_set - represented_set - approximated_set
    unsupported_set = (set(explicit_unsupported) & required_set) | unresolved
    if unsupported_set:
        status = StructuralFidelityClass.UNSUPPORTED_FOR_QUESTION
        action = "use_tactical_or_external_rules_evidence_or_extend_the_structural_model"
    elif not required:
        status = StructuralFidelityClass.HIGH_FIDELITY_FOR_QUESTION
        action = "proceed"
    elif represented_set == required_set:
        status = StructuralFidelityClass.HIGH_FIDELITY_FOR_QUESTION
        action = "proceed_with_structural_evidence_boundary"
    elif represented_set and approximated_set:
        status = StructuralFidelityClass.MEDIUM_FIDELITY_FOR_QUESTION
        action = "proceed_cautiously_and_require_robustness_confirmation"
    else:
        status = StructuralFidelityClass.LOW_FIDELITY_FOR_QUESTION
        action = "do_not_make_a_strong_decision_without_a_higher_fidelity_axis"
    return StructuralFidelityReport(
        question_id=question_id,
        status=status,
        required_functions=required,
        represented_functions=tuple(sorted(represented_set)),
        approximated_functions=tuple(sorted(approximated_set)),
        unsupported_functions=tuple(sorted(unsupported_set)),
        strong_decision_allowed=status
        in {
            StructuralFidelityClass.HIGH_FIDELITY_FOR_QUESTION,
            StructuralFidelityClass.MEDIUM_FIDELITY_FOR_QUESTION,
        },
        recommended_action=action,
    )


class ModelResolutionStatus(StrEnum):
    MEASURED = "MEASURED"
    NEEDS_MEASUREMENT = "NEEDS_MEASUREMENT"


@dataclass(frozen=True)
class ModelResolutionProfile:
    metric: str
    calibrated_sesoi: float
    measured_axis_spreads: Mapping[str, float]
    status: ModelResolutionStatus
    effective_resolution: float | None
    evidence_class: str = "structural_model_estimates"
    truth_boundary: str = (
        "structural-model resolution only; synthetic calibration is not empirical gameplay truth"
    )

    @property
    def profile_hash(self) -> str:
        payload = {
            **asdict(self),
            "measured_axis_spreads": dict(sorted(self.measured_axis_spreads.items())),
        }
        return sha256_run_value(payload)


def build_model_resolution_profile(
    *,
    metric: str,
    calibrated_sesoi: float,
    measured_axis_spreads: Mapping[str, float] | None = None,
) -> ModelResolutionProfile:
    if calibrated_sesoi < 0.0:
        raise ValueError("calibrated_sesoi must be non-negative")
    spreads = dict(measured_axis_spreads or {})
    if any(value < 0.0 for value in spreads.values()):
        raise ValueError("model-resolution spreads must be non-negative")
    if not spreads:
        return ModelResolutionProfile(
            metric=metric,
            calibrated_sesoi=calibrated_sesoi,
            measured_axis_spreads={},
            status=ModelResolutionStatus.NEEDS_MEASUREMENT,
            effective_resolution=None,
        )
    return ModelResolutionProfile(
        metric=metric,
        calibrated_sesoi=calibrated_sesoi,
        measured_axis_spreads=dict(sorted(spreads.items())),
        status=ModelResolutionStatus.MEASURED,
        effective_resolution=max(calibrated_sesoi, *spreads.values()),
    )


class SeedBlockEvidenceClass(StrEnum):
    PRECISION_ONLY_SAME_MODEL = "PRECISION_ONLY_SAME_MODEL"
    DISTINCT_STRUCTURAL_EVIDENCE_AXIS = "DISTINCT_STRUCTURAL_EVIDENCE_AXIS"


def classify_seed_block_evidence(
    *, same_model: bool, same_input_model: bool, same_metric: bool
) -> SeedBlockEvidenceClass:
    if same_model and same_input_model and same_metric:
        return SeedBlockEvidenceClass.PRECISION_ONLY_SAME_MODEL
    return SeedBlockEvidenceClass.DISTINCT_STRUCTURAL_EVIDENCE_AXIS


class ClosureSignal(StrEnum):
    RESOURCE_GAIN_WITH_CLOSURE = "RESOURCE_GAIN_WITH_CLOSURE"
    RESOURCE_GAIN_WITHOUT_CLOSURE = "RESOURCE_GAIN_WITHOUT_CLOSURE"
    COMMANDER_DAMAGE_STALL = "COMMANDER_DAMAGE_STALL"
    VALUE_ENGINE_STALL = "VALUE_ENGINE_STALL"
    MANA_STALL = "MANA_STALL"
    RECAST_STALL = "RECAST_STALL"
    INTERACTION_OVERLOAD = "INTERACTION_OVERLOAD"
    UNSUPPORTED_BY_STRUCTURAL_MODEL = "UNSUPPORTED_BY_STRUCTURAL_MODEL"


@dataclass(frozen=True)
class ClosureDiagnostic:
    signals: tuple[ClosureSignal, ...]
    supported_metrics: tuple[str, ...]
    unsupported_metrics: tuple[str, ...]
    evidence_class: str = "structural_model_estimates"
    truth_boundary: str = "closure diagnostic is descriptive structural evidence, not causal proof"


def _delta(candidate: Mapping[str, float], baseline: Mapping[str, float], key: str) -> float | None:
    if key not in candidate or key not in baseline:
        return None
    return float(candidate[key]) - float(baseline[key])


def diagnose_closure(
    *, candidate: Mapping[str, float], baseline: Mapping[str, float]
) -> ClosureDiagnostic:
    keys = (
        "resources_generated",
        "engine_value",
        "normal_damage_dealt",
        "commander_damage_dealt",
        "lands_played",
        "ramp_resolved",
        "removals_resolved",
        "counters_resolved",
        "protections_resolved",
        "wipes_resolved",
    )
    deltas = {key: _delta(candidate, baseline, key) for key in keys}
    supported = tuple(sorted(key for key, value in deltas.items() if value is not None))
    unsupported = [
        key
        for key in (
            "unused_mana",
            "stranded_spells",
            "recast_affordability",
            "restore_pressure_turns",
        )
        if key not in candidate or key not in baseline
    ]
    signals: list[ClosureSignal] = []
    resource_delta = deltas["resources_generated"]
    normal_damage = deltas["normal_damage_dealt"]
    commander_damage = deltas["commander_damage_dealt"]
    closure_damage = sum(value or 0.0 for value in (normal_damage, commander_damage))

    if resource_delta is not None and resource_delta > 0.0:
        signals.append(
            ClosureSignal.RESOURCE_GAIN_WITH_CLOSURE
            if closure_damage > 0.0
            else ClosureSignal.RESOURCE_GAIN_WITHOUT_CLOSURE
        )
    if commander_damage is not None and commander_damage < 0.0:
        signals.append(ClosureSignal.COMMANDER_DAMAGE_STALL)
    if (
        deltas["engine_value"] is not None
        and deltas["engine_value"] > 0.0
        and closure_damage <= 0.0
    ):
        signals.append(ClosureSignal.VALUE_ENGINE_STALL)
    if (
        deltas["lands_played"] is not None
        and deltas["ramp_resolved"] is not None
        and deltas["lands_played"] < 0.0
        and deltas["ramp_resolved"] <= 0.0
    ):
        signals.append(ClosureSignal.MANA_STALL)
    interaction_keys = (
        "removals_resolved",
        "counters_resolved",
        "protections_resolved",
        "wipes_resolved",
    )
    interaction_deltas = [deltas[key] for key in interaction_keys]
    if all(value is not None for value in interaction_deltas):
        interaction_gain = sum(float(value) for value in interaction_deltas if value is not None)
        if interaction_gain > 0.0 and closure_damage <= 0.0:
            signals.append(ClosureSignal.INTERACTION_OVERLOAD)
    if "recast_affordability" in unsupported or "restore_pressure_turns" in unsupported:
        signals.append(ClosureSignal.UNSUPPORTED_BY_STRUCTURAL_MODEL)
    return ClosureDiagnostic(
        signals=tuple(dict.fromkeys(signals)),
        supported_metrics=supported,
        unsupported_metrics=tuple(unsupported),
    )


class ExperimentEvidenceTarget(StrEnum):
    CUT = "CUT"
    ADD = "ADD"
    REPLACEMENT = "REPLACEMENT"
    PACKAGE = "PACKAGE"
    CONDITIONAL_EFFECT = "CONDITIONAL_EFFECT"
    INTERACTION = "INTERACTION"


@dataclass(frozen=True)
class ExperimentSemantics:
    target: ExperimentEvidenceTarget
    supports_independent_cut_claim: bool
    supports_independent_add_claim: bool
    interpretation: str


def classify_experiment_semantics(
    *,
    removed_cards: int,
    added_cards: int,
    neutral_control_removed: bool = False,
    neutral_control_added: bool = False,
    package_intervention: bool = False,
    conditional_intervention: bool = False,
    interaction_intervention: bool = False,
) -> ExperimentSemantics:
    if removed_cards < 0 or added_cards < 0:
        raise ValueError("experiment card counts must be non-negative")
    special_count = sum((package_intervention, conditional_intervention, interaction_intervention))
    if special_count > 1:
        raise ValueError("only one special experiment target may be declared")
    if package_intervention:
        return ExperimentSemantics(
            ExperimentEvidenceTarget.PACKAGE,
            False,
            False,
            "package intervention supports package-level evidence only",
        )
    if conditional_intervention:
        return ExperimentSemantics(
            ExperimentEvidenceTarget.CONDITIONAL_EFFECT,
            False,
            False,
            "controlled condition change supports conditional structural evidence",
        )
    if interaction_intervention:
        return ExperimentSemantics(
            ExperimentEvidenceTarget.INTERACTION,
            False,
            False,
            "controlled interaction change supports interaction-level structural evidence",
        )
    if removed_cards and added_cards and not (neutral_control_removed or neutral_control_added):
        return ExperimentSemantics(
            ExperimentEvidenceTarget.REPLACEMENT,
            False,
            False,
            "swap evidence identifies the replacement, not independent cut and add effects",
        )
    if removed_cards and neutral_control_added:
        return ExperimentSemantics(
            ExperimentEvidenceTarget.CUT,
            True,
            False,
            "cut effect is isolated against an explicitly neutral replacement control",
        )
    if added_cards and neutral_control_removed:
        return ExperimentSemantics(
            ExperimentEvidenceTarget.ADD,
            False,
            True,
            "add effect is isolated against an explicitly neutral removal control",
        )
    raise ValueError("experiment design does not identify one supported evidence target")


class DecisionStage(StrEnum):
    EXPLORATORY = "EXPLORATORY"
    CONFIRMATORY = "CONFIRMATORY"
    FINAL = "FINAL"


class RobustDecisionStatus(StrEnum):
    PROMOTE = "PROMOTE"
    ELIMINATE = "ELIMINATE"
    EQUIVALENT = "EQUIVALENT"
    INVALID_COMPARISON = "INVALID_COMPARISON"
    DOMAIN_INPUT_LIMIT = "DOMAIN_INPUT_LIMIT"
    STRUCTURAL_FIDELITY_LIMIT = "STRUCTURAL_FIDELITY_LIMIT"
    TACTICAL_EVIDENCE_NEEDED = "TACTICAL_EVIDENCE_NEEDED"
    MODEL_INFORMATION_LIMIT = "MODEL_INFORMATION_LIMIT"
    MODEL_RESOLUTION_LIMIT = "MODEL_RESOLUTION_LIMIT"
    MORE_PRECISION_USEFUL = "MORE_PRECISION_USEFUL"
    PRECISION_CEILING_REACHED = "PRECISION_CEILING_REACHED"
    ROBUSTNESS_LIMIT = "ROBUSTNESS_LIMIT"
    CONFIRMATORY_REQUIRED = "CONFIRMATORY_REQUIRED"
    HOLDOUT_REQUIRED = "HOLDOUT_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class RobustDecision:
    status: RobustDecisionStatus
    reason: str
    next_action: str
    interval: tuple[float, float] | None
    effective_resolution: float | None
    failed_robustness_axes: tuple[str, ...] = ()
    evidence_class: str = "structural_model_estimates"
    truth_boundary: str = "decision integration is not an empirical Commander winrate claim"


def integrate_robust_decision(
    *,
    comparison_valid: bool,
    interval: tuple[float, float] | None,
    domain_validity: DomainInputValidityReport,
    structural_fidelity: StructuralFidelityReport,
    model_information_limit: bool,
    model_resolution: ModelResolutionProfile,
    tactical_evidence_required: bool = False,
    robustness_axes: Mapping[str, bool] | None = None,
    precision_ceiling_reached: bool = False,
    additional_precision_authorized: bool = False,
    stage: DecisionStage = DecisionStage.EXPLORATORY,
    confirmatory_passed: bool = False,
    holdout_passed: bool = False,
) -> RobustDecision:
    """Integrate final decision gates without collapsing evidence axes into one score."""
    if not comparison_valid:
        return RobustDecision(
            RobustDecisionStatus.INVALID_COMPARISON,
            "comparison failed a hard constraint or execution gate",
            "repair_comparison_before_inference",
            interval,
            model_resolution.effective_resolution,
        )
    if not domain_validity.strong_decision_allowed:
        return RobustDecision(
            RobustDecisionStatus.DOMAIN_INPUT_LIMIT,
            "domain/input evidence is insufficient for a strong decision in this scope",
            domain_validity.recommended_action,
            interval,
            model_resolution.effective_resolution,
        )
    if not structural_fidelity.strong_decision_allowed:
        return RobustDecision(
            RobustDecisionStatus.STRUCTURAL_FIDELITY_LIMIT,
            "the structural model does not represent the decision question with enough fidelity",
            structural_fidelity.recommended_action,
            interval,
            model_resolution.effective_resolution,
        )
    if tactical_evidence_required:
        return RobustDecision(
            RobustDecisionStatus.TACTICAL_EVIDENCE_NEEDED,
            "the material distinction depends on legal-action, timing, or rules execution",
            "run_bounded_tactical_or_validated_external_rules_evidence",
            interval,
            model_resolution.effective_resolution,
        )
    if model_information_limit:
        return RobustDecision(
            RobustDecisionStatus.MODEL_INFORMATION_LIMIT,
            "the structural cohort is saturated or non-separable",
            "diagnose_information_limit_before_more_seed_work",
            interval,
            model_resolution.effective_resolution,
        )
    if model_resolution.status != ModelResolutionStatus.MEASURED:
        return RobustDecision(
            RobustDecisionStatus.MODEL_RESOLUTION_LIMIT,
            "synthetic calibration alone does not establish structural model resolution",
            "measure_null_seed_seat_scenario_pilot_or_compression_variability",
            interval,
            None,
        )
    if interval is None or model_resolution.effective_resolution is None:
        return RobustDecision(
            RobustDecisionStatus.UNRESOLVED,
            "comparison interval or measured resolution is unavailable",
            "collect_the_missing_decision_information",
            interval,
            model_resolution.effective_resolution,
        )

    resolution = model_resolution.effective_resolution
    direction: str | None = None
    if interval[0] > resolution:
        direction = "positive"
    elif interval[1] < -resolution:
        direction = "negative"
    elif interval[0] >= -resolution and interval[1] <= resolution:
        direction = "equivalent"

    if direction is None:
        if precision_ceiling_reached and not additional_precision_authorized:
            return RobustDecision(
                RobustDecisionStatus.PRECISION_CEILING_REACHED,
                "the interval crosses the measured decision boundary at the precision ceiling",
                "select_a_non_seed_evidence_axis_or_remain_unresolved",
                interval,
                resolution,
            )
        return RobustDecision(
            RobustDecisionStatus.MORE_PRECISION_USEFUL,
            "additional paired precision can still change the structural decision",
            "run_preregistered_paired_precision_only_batch",
            interval,
            resolution,
        )

    failed_axes = tuple(
        sorted(name for name, passed in (robustness_axes or {}).items() if not passed)
    )
    if failed_axes:
        return RobustDecision(
            RobustDecisionStatus.ROBUSTNESS_LIMIT,
            "the directional result does not survive all declared robustness axes",
            "resolve_or_report_the_failed_robustness_axes",
            interval,
            resolution,
            failed_axes,
        )
    if direction == "equivalent":
        return RobustDecision(
            RobustDecisionStatus.EQUIVALENT,
            "the entire interval lies inside the measured structural resolution region",
            "stop_with_structural_equivalence_for_this_question",
            interval,
            resolution,
        )
    if stage == DecisionStage.EXPLORATORY or not confirmatory_passed:
        return RobustDecision(
            RobustDecisionStatus.CONFIRMATORY_REQUIRED,
            "exploratory directional evidence cannot become a strong deck decision",
            "freeze_frontier_and_run_fresh_confirmatory_evidence",
            interval,
            resolution,
        )
    if stage == DecisionStage.FINAL and not holdout_passed:
        return RobustDecision(
            RobustDecisionStatus.HOLDOUT_REQUIRED,
            "final decision requires authorized sealed holdout confirmation",
            "run_authorized_sealed_holdout_without_search_learning",
            interval,
            resolution,
        )
    if direction == "positive":
        return RobustDecision(
            RobustDecisionStatus.PROMOTE,
            "directional effect exceeds measured resolution and passed declared gates",
            "retain_as_model_supported_preference_with_evidence_boundary",
            interval,
            resolution,
        )
    return RobustDecision(
        RobustDecisionStatus.ELIMINATE,
        "directional degradation exceeds measured resolution and passed declared gates",
        "retain_as_model_supported_elimination_with_evidence_boundary",
        interval,
        resolution,
    )


__all__ = [
    "ClosureDiagnostic",
    "ClosureSignal",
    "DecisionStage",
    "DomainInputValidityReport",
    "DomainInputValidityStatus",
    "DomainQuestionScope",
    "ExperimentEvidenceTarget",
    "ExperimentSemantics",
    "ModelResolutionProfile",
    "ModelResolutionStatus",
    "OpponentAmbiguitySet",
    "OpponentAmbiguityVariant",
    "RobustDecision",
    "RobustDecisionStatus",
    "SeedBlockEvidenceClass",
    "StructuralFidelityClass",
    "StructuralFidelityReport",
    "assess_domain_input_validity",
    "assess_structural_fidelity",
    "build_model_resolution_profile",
    "classify_experiment_semantics",
    "classify_seed_block_evidence",
    "diagnose_closure",
    "integrate_robust_decision",
]
