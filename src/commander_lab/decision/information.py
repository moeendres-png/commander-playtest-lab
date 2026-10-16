from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from commander_lab.storage.run_identity import sha256_run_value


class DecisionInformationStatus(StrEnum):
    STOP_WITH_PREFERENCE = "STOP_WITH_PREFERENCE"
    NO_MATERIAL_DECISION_DIFFERENCE = "NO_MATERIAL_DECISION_DIFFERENCE"
    MORE_SIMULATIONS_USEFUL = "MORE_SIMULATIONS_USEFUL"
    MODEL_NEEDS_DIFFERENT_METRIC = "MODEL_NEEDS_DIFFERENT_METRIC"
    TACTICAL_EVIDENCE_NEEDED = "TACTICAL_EVIDENCE_NEEDED"
    OPPONENT_UNCERTAINTY_DOMINATES = "OPPONENT_UNCERTAINTY_DOMINATES"
    PRECISION_CEILING_REACHED = "PRECISION_CEILING_REACHED"
    STOP = "STOP"


@dataclass(frozen=True)
class DecisionInformationState:
    schema_version: str
    status: DecisionInformationStatus
    pairwise_effect: float | None
    confidence_interval: tuple[float, float] | None
    decision_uncertainty: float | None
    indifference_threshold: float
    seed_spread: float | None
    scenario_spread: float | None
    failure_mode_differences: tuple[str, ...]
    missing_semantic_axes: tuple[str, ...]
    current_iterations: int | None
    precision_ceiling: int | None
    additional_precision_authorized: bool
    next_recommended_experiment: str
    stop_reason: str
    evidence_class: str = "structural_decision_information"
    truth_boundary: str = "decision-information diagnostic, not empirical winrate"
    domain_input_validity: str | None = None
    structural_fidelity: str | None = None
    model_resolution_status: str | None = None
    effective_resolution: float | None = None
    seed_evidence_class: str = "PRECISION_ONLY_SAME_MODEL"

    @property
    def state_hash(self) -> str:
        return sha256_run_value(asdict(self))

    def as_dict(self) -> dict[str, Any]:
        return {"state_hash": self.state_hash, **asdict(self)}


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _interval(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    low = _number(value[0])
    high = _number(value[1])
    if low is None or high is None:
        return None
    return low, high


def _embedded_mapping(
    comparison: dict[str, Any], explicit: dict[str, Any] | None, key: str
) -> dict[str, Any] | None:
    if explicit is not None:
        return explicit
    raw = comparison.get(key)
    return dict(raw) if isinstance(raw, dict) else None


def build_decision_information_state(
    comparison: dict[str, Any],
    *,
    model_informativeness: dict[str, Any] | None = None,
    domain_validity: dict[str, Any] | None = None,
    structural_fidelity: dict[str, Any] | None = None,
    model_resolution: dict[str, Any] | None = None,
    scenario_spread: float | None = None,
    failure_mode_differences: tuple[str, ...] = (),
    missing_semantic_axes: tuple[str, ...] = (),
    tactical_evidence_required: bool = False,
    precision_context: dict[str, Any] | None = None,
    indifference_threshold: float = 0.025,
) -> DecisionInformationState:
    """Diagnose which uncertainty source should control the next experiment.

    Gate order is deliberately epistemic rather than effect-first: input validity, question-specific
    model fidelity, tactical dependency, model informativeness, measured resolution, then effect or
    equivalence. Additional same-model seed blocks are precision evidence only.
    """
    if indifference_threshold < 0.0:
        raise ValueError("indifference_threshold must be non-negative")
    context = precision_context or comparison.get("precision_context") or {}
    if not isinstance(context, dict):
        context = {}
    current_iterations = _integer(context.get("current_iterations"))
    precision_ceiling = _integer(context.get("preregistered_precision_ceiling"))
    additional_precision_authorized = context.get("additional_precision_authorized") is True

    domain_validity = _embedded_mapping(comparison, domain_validity, "domain_validity")
    structural_fidelity = _embedded_mapping(comparison, structural_fidelity, "structural_fidelity")
    model_resolution = _embedded_mapping(comparison, model_resolution, "model_resolution")
    model_informativeness = _embedded_mapping(
        comparison, model_informativeness, "model_informativeness"
    )

    domain_status = str((domain_validity or {}).get("status", "")) or None
    fidelity_status = str((structural_fidelity or {}).get("status", "")) or None
    resolution_status = str((model_resolution or {}).get("status", "")) or None
    measured_resolution = _number((model_resolution or {}).get("effective_resolution"))
    decision_threshold = max(
        indifference_threshold,
        measured_resolution if measured_resolution is not None else indifference_threshold,
    )

    def state(
        *,
        status: DecisionInformationStatus,
        effect: float | None,
        interval: tuple[float, float] | None,
        uncertainty: float | None,
        seed_spread: float | None,
        next_experiment: str,
        reason: str,
    ) -> DecisionInformationState:
        return DecisionInformationState(
            schema_version="1.2.0",
            status=status,
            pairwise_effect=effect,
            confidence_interval=interval,
            decision_uncertainty=uncertainty,
            indifference_threshold=decision_threshold,
            seed_spread=seed_spread,
            scenario_spread=scenario_spread,
            failure_mode_differences=failure_mode_differences,
            missing_semantic_axes=missing_semantic_axes,
            current_iterations=current_iterations,
            precision_ceiling=precision_ceiling,
            additional_precision_authorized=additional_precision_authorized,
            next_recommended_experiment=next_experiment,
            stop_reason=reason,
            domain_input_validity=domain_status,
            structural_fidelity=fidelity_status,
            model_resolution_status=resolution_status,
            effective_resolution=measured_resolution,
        )

    if comparison.get("status") != "completed":
        return state(
            status=DecisionInformationStatus.STOP,
            effect=None,
            interval=None,
            uncertainty=None,
            seed_spread=None,
            next_experiment="repair_constraints_or_choose_another_candidate",
            reason="comparison did not pass the hard-constraint gate",
        )

    paired = comparison.get("paired", {})
    if not isinstance(paired, dict):
        paired = {}
    effect = _number(paired.get("placement_improvement"))
    interval = _interval(paired.get("confidence_interval"))
    mcse = _number(paired.get("monte_carlo_standard_error"))
    seed_spread = (interval[1] - interval[0]) / 2.0 if interval is not None else mcse
    uncertainty = seed_spread

    if domain_validity is not None and domain_validity.get("strong_decision_allowed") is not True:
        return state(
            status=DecisionInformationStatus.OPPONENT_UNCERTAINTY_DOMINATES,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment=str(
                domain_validity.get(
                    "recommended_action",
                    "use_evidence_bounded_opponent_ambiguity_ensemble",
                )
            ),
            reason="domain/input evidence cannot support a strong decision in this scope",
        )
    if (
        structural_fidelity is not None
        and structural_fidelity.get("strong_decision_allowed") is not True
    ):
        return state(
            status=DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment=str(
                structural_fidelity.get(
                    "recommended_action",
                    "resolve_question_specific_structural_fidelity",
                )
            ),
            reason="question-specific structural fidelity is insufficient for a strong decision",
        )
    if missing_semantic_axes:
        return state(
            status=DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="resolve_decision_material_semantic_axes",
            reason="a decision-material semantic axis is missing from the current comparison",
        )
    if tactical_evidence_required:
        return state(
            status=DecisionInformationStatus.TACTICAL_EVIDENCE_NEEDED,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="run_bounded_tactical_evidence_fixture",
            reason="the unresolved decision depends on legal-action/timing/rules execution",
        )
    if (model_informativeness or {}).get("status") == "MODEL_INFORMATION_LIMIT":
        return state(
            status=DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="diagnose_model_information_before_more_seed_work",
            reason="the structural cohort is saturated or non-separable; seeds alone are insufficient",
        )
    if model_resolution is not None and resolution_status != "MEASURED":
        return state(
            status=DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="measure_structural_model_resolution_across_declared_axes",
            reason="synthetic calibration alone does not establish structural model resolution",
        )
    if scenario_spread is not None and seed_spread is not None and scenario_spread > seed_spread:
        return state(
            status=DecisionInformationStatus.OPPONENT_UNCERTAINTY_DOMINATES,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="test_finalists_across_declared_opponent_envelopes",
            reason="between-scenario uncertainty exceeds within-scenario seed uncertainty",
        )
    if interval is not None and interval[0] > decision_threshold:
        return state(
            status=DecisionInformationStatus.STOP_WITH_PREFERENCE,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="stop_with_structural_preference",
            reason="paired interval is separated beyond measured decision resolution",
        )
    if interval is not None and interval[1] < -decision_threshold:
        return state(
            status=DecisionInformationStatus.STOP,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="stop_or_return_to_candidate_screening",
            reason="paired interval is materially negative beyond measured decision resolution",
        )
    if (
        interval is not None
        and interval[0] >= -decision_threshold
        and interval[1] <= decision_threshold
    ):
        return state(
            status=DecisionInformationStatus.NO_MATERIAL_DECISION_DIFFERENCE,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="stop_no_material_difference",
            reason="entire interval lies inside measured decision resolution",
        )
    if (
        current_iterations is not None
        and precision_ceiling is not None
        and current_iterations >= precision_ceiling
        and not additional_precision_authorized
    ):
        return state(
            status=DecisionInformationStatus.PRECISION_CEILING_REACHED,
            effect=effect,
            interval=interval,
            uncertainty=uncertainty,
            seed_spread=seed_spread,
            next_experiment="select_next_non_seed_evidence_or_remain_unresolved",
            reason=(
                "preregistered precision ceiling is reached; same-model seeds add precision only"
            ),
        )
    return state(
        status=DecisionInformationStatus.MORE_SIMULATIONS_USEFUL,
        effect=effect,
        interval=interval,
        uncertainty=uncertainty,
        seed_spread=seed_spread,
        next_experiment="run_next_paired_micro_batch",
        reason=(
            "within the preregistered budget, more paired precision can still change the decision; "
            "same-model seed blocks are precision evidence only"
        ),
    )


__all__ = [
    "DecisionInformationState",
    "DecisionInformationStatus",
    "build_decision_information_state",
]
