from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from commander_lab.storage import sha256_value

AdvancementStatus = Literal["advance", "diagnose", "reject", "profile_required"]


@dataclass(frozen=True)
class AdvancementDecision:
    status: AdvancementStatus
    reason_code: str
    reason: str
    sensitivity_allowed: bool
    expensive_ablation_allowed: bool
    evidence_class: str = "structural_advancement_decision"

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


def decide_advancement(
    comparison: dict[str, Any],
    *,
    model_informativeness: dict[str, Any] | None = None,
    domain_validity: dict[str, Any] | None = None,
    structural_fidelity: dict[str, Any] | None = None,
    model_resolution: dict[str, Any] | None = None,
    profile_required: bool = False,
) -> AdvancementDecision:
    """Apply fail-closed preregistered gates before finalist-only work.

    Decision-quality metadata may be supplied explicitly or embedded in the comparison. Legacy
    comparisons without the new metadata remain readable, but any supplied decision-quality limit
    is upstream of effect-based advancement.
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
        )
    if fidelity and fidelity.get("strong_decision_allowed") is not True:
        return AdvancementDecision(
            status="diagnose",
            reason_code="structural_fidelity_limit",
            reason="question-specific structural fidelity is insufficient for finalist advancement",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
        )
    if informativeness.get("status") == "MODEL_INFORMATION_LIMIT":
        return AdvancementDecision(
            status="diagnose",
            reason_code="model_information_limit",
            reason="more seeds alone cannot repair the detected model-information limit",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
        )
    if resolution and resolution.get("status") != "MEASURED":
        return AdvancementDecision(
            status="diagnose",
            reason_code="model_resolution_unmeasured",
            reason="synthetic calibration alone does not establish Structural Model resolution",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
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
    robust = float(paired.get("distributionally_robust_lower_bound", 0.0))
    effective_resolution = 0.0
    if resolution:
        raw_resolution = resolution.get("effective_resolution")
        if isinstance(raw_resolution, (int, float)) and not isinstance(raw_resolution, bool):
            effective_resolution = max(0.0, float(raw_resolution))
    if low > effective_resolution and robust >= 0.0:
        return AdvancementDecision(
            status="advance",
            reason_code="separated_positive_beyond_resolution_and_lower_tail_nonnegative",
            reason=(
                "central interval is positive beyond the available Structural decision resolution "
                "and the robust lower-tail bound is nonnegative"
            ),
            sensitivity_allowed=True,
            expensive_ablation_allowed=True,
        )
    if high < -effective_resolution:
        return AdvancementDecision(
            status="reject",
            reason_code="separated_negative_beyond_resolution",
            reason="paired structural interval is materially separated in the unfavorable direction",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
        )
    return AdvancementDecision(
        status="diagnose",
        reason_code="unresolved_or_lower_tail_unfavorable",
        reason="the variant is not qualified for finalist-only sensitivity",
        sensitivity_allowed=False,
        expensive_ablation_allowed=False,
    )


__all__ = ["AdvancementDecision", "decide_advancement"]
