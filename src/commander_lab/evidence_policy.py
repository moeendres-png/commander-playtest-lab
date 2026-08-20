from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from commander_lab.storage.run_identity import sha256_run_value

DECISION_POLICY_VERSION = "evidence-safe-decision-1.0.0"


class DirectionState(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    UNRESOLVED = "UNRESOLVED"


class SamplingState(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    MORE_SAMPLES = "MORE_SAMPLES"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class ModelState(StrEnum):
    RESOLVABLE = "RESOLVABLE"
    MODEL_LIMITED = "MODEL_LIMITED"
    NEEDS_DIFFERENT_EVIDENCE = "NEEDS_DIFFERENT_EVIDENCE"


class MagnitudeClass(StrEnum):
    BELOW_SESOI = "BELOW_SESOI"
    AT_OR_ABOVE_SESOI = "AT_OR_ABOVE_SESOI"


class RobustnessState(StrEnum):
    ROBUST = "ROBUST"
    TRADEOFF = "TRADEOFF"
    NOT_TESTED = "NOT_TESTED"


class EvidenceAction(StrEnum):
    ADVANCE = "ADVANCE"
    SAFE_ELIMINATE = "SAFE_ELIMINATE"
    CONTINUE_SAMPLING = "CONTINUE_SAMPLING"
    ESCALATE_EVIDENCE = "ESCALATE_EVIDENCE"
    TRADEOFF_REVIEW = "TRADEOFF_REVIEW"
    INCONCLUSIVE = "INCONCLUSIVE"


class RacingDisposition(StrEnum):
    ACTIVE = "ACTIVE"
    SAFE_ELIMINATED = "SAFE_ELIMINATED"
    UNCERTAIN_FRONTIER = "UNCERTAIN_FRONTIER"
    DEFERRED_INCONCLUSIVE = "DEFERRED_INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    candidate_id: str | None
    control_id: str | None
    paired_delta_estimate: float
    descriptive_interval: tuple[float, float]
    sampling_state: SamplingState
    direction_state: DirectionState
    model_state: ModelState
    technical_resolution: float | None
    sesoi: float | None
    magnitude_class: MagnitudeClass
    robustness_state: RobustnessState
    tradeoff_flags: tuple[str, ...]
    sequential_stage: int | None
    sequential_evidence_state: str
    remaining_budget: int | None
    action: EvidenceAction
    action_reason: str
    evidence_type: str = "structural_model_estimates"
    sequential_interval: tuple[float, float] | None = None
    policy_version: str = DECISION_POLICY_VERSION

    @property
    def decision_hash(self) -> str:
        return sha256_run_value(asdict(self))

    def as_dict(self) -> dict[str, Any]:
        return {"decision_hash": self.decision_hash, **asdict(self)}


def _validate_interval(interval: tuple[float, float], *, name: str) -> tuple[float, float]:
    low, high = float(interval[0]), float(interval[1])
    if low > high:
        raise ValueError(f"{name} low must not exceed high")
    return low, high


def classify_direction(interval: tuple[float, float]) -> DirectionState:
    low, high = _validate_interval(interval, name="decision interval")
    if low > 0.0:
        return DirectionState.POSITIVE
    if high < 0.0:
        return DirectionState.NEGATIVE
    return DirectionState.UNRESOLVED


def magnitude_class_for(delta: float, sesoi: float | None) -> MagnitudeClass:
    if sesoi is None or sesoi <= 0.0:
        return MagnitudeClass.AT_OR_ABOVE_SESOI
    return (
        MagnitudeClass.AT_OR_ABOVE_SESOI
        if abs(float(delta)) >= float(sesoi)
        else MagnitudeClass.BELOW_SESOI
    )


def classify_evidence(
    *,
    paired_delta_estimate: float,
    descriptive_interval: tuple[float, float],
    sequential_interval: tuple[float, float] | None = None,
    candidate_id: str | None = None,
    control_id: str | None = None,
    model_state: ModelState = ModelState.RESOLVABLE,
    robustness_state: RobustnessState = RobustnessState.NOT_TESTED,
    tradeoff_flags: tuple[str, ...] = (),
    remaining_budget: int | None = None,
    technical_resolution: float | None = None,
    sesoi: float | None = None,
    sequential_stage: int | None = None,
    evidence_type: str = "structural_model_estimates",
) -> EvidenceDecision:
    """Classify evidence without effect-size or technical-resolution eligibility cutoffs.

    The sequential interval, when supplied, controls directional decisions. The ordinary
    descriptive interval remains reportable but never substitutes for the sequential interval
    during repeated looks. ``technical_resolution`` and ``sesoi`` are diagnostics only: neither
    can make a candidate advance or be eliminated.
    """

    descriptive = _validate_interval(descriptive_interval, name="descriptive interval")
    sequential = (
        _validate_interval(sequential_interval, name="sequential interval")
        if sequential_interval is not None
        else None
    )
    decision_interval = sequential or descriptive
    direction = classify_direction(decision_interval)
    magnitude = magnitude_class_for(paired_delta_estimate, sesoi)
    flags = tuple(sorted(set(str(flag) for flag in tradeoff_flags if str(flag))))
    robustness = RobustnessState.TRADEOFF if flags else robustness_state

    if direction == DirectionState.UNRESOLVED:
        sampling = (
            SamplingState.MORE_SAMPLES
            if remaining_budget is None or remaining_budget > 0
            else SamplingState.BUDGET_EXHAUSTED
        )
    else:
        sampling = SamplingState.SUFFICIENT

    if flags or robustness == RobustnessState.TRADEOFF:
        action = EvidenceAction.TRADEOFF_REVIEW
        reason = "directional evidence has a decision-material robustness or whole-deck tradeoff"
    elif model_state in {ModelState.MODEL_LIMITED, ModelState.NEEDS_DIFFERENT_EVIDENCE}:
        action = EvidenceAction.ESCALATE_EVIDENCE
        reason = "same-model sampling cannot resolve the declared model or fidelity limitation"
    elif direction == DirectionState.POSITIVE and sampling == SamplingState.SUFFICIENT:
        action = EvidenceAction.ADVANCE
        reason = "controlled paired evidence supports a positive within-model direction"
    elif direction == DirectionState.NEGATIVE and sampling == SamplingState.SUFFICIENT:
        action = EvidenceAction.SAFE_ELIMINATE
        reason = "controlled paired evidence supports a negative within-model direction"
    elif sampling == SamplingState.MORE_SAMPLES:
        action = EvidenceAction.CONTINUE_SAMPLING
        reason = "direction remains unresolved and preregistered same-model budget remains"
    else:
        action = EvidenceAction.INCONCLUSIVE
        reason = "direction remains unresolved at the preregistered same-model budget limit"

    sequential_state = (
        "CONTROLLED_DIRECTIONAL_LOOK" if sequential is not None else "FIXED_SAMPLE_DIRECTIONAL_LOOK"
    )
    return EvidenceDecision(
        candidate_id=candidate_id,
        control_id=control_id,
        paired_delta_estimate=float(paired_delta_estimate),
        descriptive_interval=descriptive,
        sequential_interval=sequential,
        sampling_state=sampling,
        direction_state=direction,
        model_state=model_state,
        technical_resolution=(
            None if technical_resolution is None else float(technical_resolution)
        ),
        sesoi=None if sesoi is None else float(sesoi),
        magnitude_class=magnitude,
        robustness_state=robustness,
        tradeoff_flags=flags,
        sequential_stage=sequential_stage,
        sequential_evidence_state=sequential_state,
        remaining_budget=remaining_budget,
        action=action,
        action_reason=reason,
        evidence_type=evidence_type,
    )


__all__ = [
    "DECISION_POLICY_VERSION",
    "DirectionState",
    "EvidenceAction",
    "EvidenceDecision",
    "MagnitudeClass",
    "ModelState",
    "RacingDisposition",
    "RobustnessState",
    "SamplingState",
    "classify_direction",
    "classify_evidence",
    "magnitude_class_for",
]
