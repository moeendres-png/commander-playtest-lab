from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from commander_lab.evidence_policy import (
    EvidenceAction,
    ModelState,
    RobustnessState,
    classify_evidence,
)
from commander_lab.storage import sha256_value

AdvancementStatus = Literal[
    "advance",
    "diagnose",
    "reject",
    "profile_required",
    "tradeoff_review",
    "inconclusive",
]


@dataclass(frozen=True)
class AdvancementDecision:
    status: AdvancementStatus
    reason_code: str
    reason: str
    sensitivity_allowed: bool
    expensive_ablation_allowed: bool
    evidence_class: str = "structural_advancement_decision"
    evidence_action: str | None = None
    direction_state: str | None = None
    sampling_state: str | None = None
    model_state: str | None = None
    technical_resolution: float | None = None
    sesoi: float | None = None

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def decision_hash(self) -> str:
        return sha256_value(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {"decision_hash": self.decision_hash, **self.payload()}


def _embedded_mapping(
    comparison: dict[str, Any], explicit: dict[str, Any] | None, key: str
) -> dict[str, Any]:
    if explicit is not None:
        return explicit
    raw = comparison.get(key)
    return dict(raw) if isinstance(raw, dict) else {}


def _number(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def decide_advancement(
    comparison: dict[str, Any],
    *,
    model_informativeness: dict[str, Any] | None = None,
    domain_validity: dict[str, Any] | None = None,
    structural_fidelity: dict[str, Any] | None = None,
    model_resolution: dict[str, Any] | None = None,
    profile_required: bool = False,
    sesoi: float | None = None,
) -> AdvancementDecision:
    """Apply hard-integrity gates, then evidence-safe paired advancement.

    Numeric model resolution and SESOI are reporting diagnostics only. They never decide whether a
    candidate advances or is eliminated. Explicit input/fidelity/informativeness limitations remain
    upstream because more same-model seeds cannot repair those limits.
    """

    if comparison.get("status") != "completed":
        return AdvancementDecision(
            status="reject",
            reason_code="hard_constraints_or_execution_failed",
            reason="variant did not complete the hard-constraint comparison",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
        )
    if profile_required:
        return AdvancementDecision(
            status="profile_required",
            reason_code="insufficient_candidate_profile",
            reason="candidate must be profiled before model-based recommendation",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
        )

    domain = _embedded_mapping(comparison, domain_validity, "domain_validity")
    fidelity = _embedded_mapping(comparison, structural_fidelity, "structural_fidelity")
    resolution = _embedded_mapping(comparison, model_resolution, "model_resolution")
    informativeness = _embedded_mapping(comparison, model_informativeness, "model_informativeness")

    if domain and domain.get("strong_decision_allowed") is not True:
        return AdvancementDecision(
            status="diagnose",
            reason_code="domain_input_validity_limit",
            reason="domain/input evidence cannot support finalist advancement for this scope",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
            model_state=ModelState.NEEDS_DIFFERENT_EVIDENCE.value,
            evidence_action=EvidenceAction.ESCALATE_EVIDENCE.value,
        )
    if fidelity and fidelity.get("strong_decision_allowed") is not True:
        return AdvancementDecision(
            status="diagnose",
            reason_code="structural_fidelity_limit",
            reason="question-specific structural fidelity is insufficient for finalist advancement",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
            model_state=ModelState.NEEDS_DIFFERENT_EVIDENCE.value,
            evidence_action=EvidenceAction.ESCALATE_EVIDENCE.value,
        )
    if informativeness.get("status") == "MODEL_INFORMATION_LIMIT":
        return AdvancementDecision(
            status="diagnose",
            reason_code="model_information_limit",
            reason="more seeds alone cannot repair the detected model-information limit",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
            model_state=ModelState.MODEL_LIMITED.value,
            evidence_action=EvidenceAction.ESCALATE_EVIDENCE.value,
        )
    if resolution and resolution.get("status") != "MEASURED":
        return AdvancementDecision(
            status="diagnose",
            reason_code="model_resolution_unmeasured",
            reason="structural model diagnostics are incomplete for this comparison scope",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
            model_state=ModelState.NEEDS_DIFFERENT_EVIDENCE.value,
            evidence_action=EvidenceAction.ESCALATE_EVIDENCE.value,
        )

    paired = comparison.get("paired", {})
    interval = paired.get("confidence_interval", ()) if isinstance(paired, dict) else ()
    if not isinstance(interval, list | tuple) or len(interval) != 2:
        return AdvancementDecision(
            status="diagnose",
            reason_code="missing_uncertainty_interval",
            reason="paired comparison lacks the uncertainty evidence required to advance",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
        )
    low = float(interval[0])
    high = float(interval[1])
    effect = _number(paired, "placement_improvement")
    if effect is None:
        effect = (low + high) / 2.0
    robust = _number(paired, "distributionally_robust_lower_bound")
    technical_resolution = _number(resolution, "effective_resolution") if resolution else None

    precision_context = comparison.get("precision_context")
    remaining_budget: int | None = None
    if isinstance(precision_context, dict):
        current = precision_context.get("current_iterations")
        ceiling = precision_context.get("preregistered_precision_ceiling")
        if isinstance(current, int) and isinstance(ceiling, int):
            remaining_budget = max(0, ceiling - current)

    flags: tuple[str, ...] = ()
    robustness = RobustnessState.NOT_TESTED
    if robust is not None:
        robustness = RobustnessState.ROBUST if robust >= 0.0 else RobustnessState.TRADEOFF
        if robust < 0.0:
            flags = ("distributionally_robust_lower_bound_negative",)

    evidence = classify_evidence(
        paired_delta_estimate=effect,
        descriptive_interval=(low, high),
        remaining_budget=remaining_budget,
        technical_resolution=technical_resolution,
        sesoi=sesoi,
        robustness_state=robustness,
        tradeoff_flags=flags,
    )

    status_by_action: dict[EvidenceAction, AdvancementStatus] = {
        EvidenceAction.ADVANCE: "advance",
        EvidenceAction.SAFE_ELIMINATE: "reject",
        EvidenceAction.CONTINUE_SAMPLING: "diagnose",
        EvidenceAction.ESCALATE_EVIDENCE: "diagnose",
        EvidenceAction.TRADEOFF_REVIEW: "tradeoff_review",
        EvidenceAction.INCONCLUSIVE: "inconclusive",
    }
    status = status_by_action[evidence.action]
    allow_followup = evidence.action in {
        EvidenceAction.ADVANCE,
        EvidenceAction.TRADEOFF_REVIEW,
    }
    return AdvancementDecision(
        status=status,
        reason_code=f"evidence_safe_{evidence.action.value.lower()}",
        reason=evidence.action_reason,
        sensitivity_allowed=allow_followup,
        expensive_ablation_allowed=allow_followup,
        evidence_action=evidence.action.value,
        direction_state=evidence.direction_state.value,
        sampling_state=evidence.sampling_state.value,
        model_state=evidence.model_state.value,
        technical_resolution=technical_resolution,
        sesoi=sesoi,
    )


__all__ = ["AdvancementDecision", "decide_advancement"]
