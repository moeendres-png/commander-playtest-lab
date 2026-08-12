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


def build_decision_information_state(
    comparison: dict[str, Any],
    *,
    model_informativeness: dict[str, Any] | None = None,
    scenario_spread: float | None = None,
    failure_mode_differences: tuple[str, ...] = (),
    missing_semantic_axes: tuple[str, ...] = (),
    tactical_evidence_required: bool = False,
    precision_context: dict[str, Any] | None = None,
    indifference_threshold: float = 0.025,
) -> DecisionInformationState:
    """Diagnose which uncertainty source should control the next experiment."""
    if indifference_threshold < 0.0:
        raise ValueError("indifference_threshold must be non-negative")
    context = precision_context or comparison.get("precision_context") or {}
    if not isinstance(context, dict):
        context = {}
    current_iterations = _integer(context.get("current_iterations"))
    precision_ceiling = _integer(context.get("preregistered_precision_ceiling"))
    additional_precision_authorized = context.get("additional_precision_authorized") is True

    if comparison.get("status") != "completed":
        return DecisionInformationState(
            schema_version="1.1.0",
            status=DecisionInformationStatus.STOP,
            pairwise_effect=None,
            confidence_interval=None,
            decision_uncertainty=None,
            indifference_threshold=indifference_threshold,
            seed_spread=None,
            scenario_spread=scenario_spread,
            failure_mode_differences=failure_mode_differences,
            missing_semantic_axes=missing_semantic_axes,
            current_iterations=current_iterations,
            precision_ceiling=precision_ceiling,
            additional_precision_authorized=additional_precision_authorized,
            next_recommended_experiment="repair_constraints_or_choose_another_candidate",
            stop_reason="comparison did not pass the hard-constraint gate",
        )

    paired = comparison.get("paired", {})
    if not isinstance(paired, dict):
        paired = {}
    effect = _number(paired.get("placement_improvement"))
    interval = _interval(paired.get("confidence_interval"))
    mcse = _number(paired.get("monte_carlo_standard_error"))
    seed_spread = (interval[1] - interval[0]) / 2.0 if interval is not None else mcse
    uncertainty = seed_spread

    if tactical_evidence_required:
        status = DecisionInformationStatus.TACTICAL_EVIDENCE_NEEDED
        next_experiment = "run_bounded_tactical_evidence_fixture"
        reason = "the unresolved decision depends on legal-action/timing/rules execution"
    elif scenario_spread is not None and seed_spread is not None and scenario_spread > seed_spread:
        status = DecisionInformationStatus.OPPONENT_UNCERTAINTY_DOMINATES
        next_experiment = "test_finalists_across_declared_opponent_envelopes"
        reason = "between-scenario uncertainty exceeds within-scenario seed uncertainty"
    elif missing_semantic_axes:
        status = DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC
        next_experiment = "resolve_decision_material_semantic_axes"
        reason = "a decision-material semantic axis is missing from the current comparison"
    elif interval is not None and interval[0] > indifference_threshold:
        status = DecisionInformationStatus.STOP_WITH_PREFERENCE
        next_experiment = "stop_with_structural_preference"
        reason = "the paired interval is separated beyond the decision-indifference threshold"
    elif interval is not None and interval[1] < -indifference_threshold:
        status = DecisionInformationStatus.STOP
        next_experiment = "stop_or_return_to_candidate_screening"
        reason = "the paired interval is materially negative"
    elif (
        interval is not None
        and interval[0] >= -indifference_threshold
        and interval[1] <= indifference_threshold
    ):
        status = DecisionInformationStatus.NO_MATERIAL_DECISION_DIFFERENCE
        next_experiment = "stop_no_material_difference"
        reason = "the entire interval lies inside the decision-indifference region"
    elif (model_informativeness or {}).get("status") == "MODEL_INFORMATION_LIMIT":
        status = DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC
        next_experiment = "diagnose_model_information_before_more_seed_work"
        reason = "the structural cohort is saturated or non-separable; seeds alone are insufficient"
    elif (
        current_iterations is not None
        and precision_ceiling is not None
        and current_iterations >= precision_ceiling
        and not additional_precision_authorized
    ):
        status = DecisionInformationStatus.PRECISION_CEILING_REACHED
        next_experiment = "select_next_non_seed_evidence_or_remain_unresolved"
        reason = (
            "the preregistered precision ceiling is reached and more seed work is not authorized"
        )
    else:
        status = DecisionInformationStatus.MORE_SIMULATIONS_USEFUL
        next_experiment = "run_next_paired_micro_batch"
        reason = "current seed uncertainty can still plausibly change the material decision within budget"

    return DecisionInformationState(
        schema_version="1.1.0",
        status=status,
        pairwise_effect=effect,
        confidence_interval=interval,
        decision_uncertainty=uncertainty,
        indifference_threshold=indifference_threshold,
        seed_spread=seed_spread,
        scenario_spread=scenario_spread,
        failure_mode_differences=failure_mode_differences,
        missing_semantic_axes=missing_semantic_axes,
        current_iterations=current_iterations,
        precision_ceiling=precision_ceiling,
        additional_precision_authorized=additional_precision_authorized,
        next_recommended_experiment=next_experiment,
        stop_reason=reason,
    )


__all__ = [
    "DecisionInformationState",
    "DecisionInformationStatus",
    "build_decision_information_state",
]
