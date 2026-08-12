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


def decide_advancement(
    comparison: dict[str, Any],
    *,
    model_informativeness: dict[str, Any] | None = None,
    profile_required: bool = False,
) -> AdvancementDecision:
    """Apply one preregistered gate before finalist-only sensitivity or ablation."""

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
    if (model_informativeness or {}).get("status") == "MODEL_INFORMATION_LIMIT":
        return AdvancementDecision(
            status="diagnose",
            reason_code="model_information_limit",
            reason="more seeds alone cannot repair the detected model-information limit",
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
    if low > 0.0 and robust >= 0.0:
        return AdvancementDecision(
            status="advance",
            reason_code="separated_positive_and_lower_tail_nonnegative",
            reason="central interval is positive and the robust lower-tail bound is nonnegative",
            sensitivity_allowed=True,
            expensive_ablation_allowed=True,
        )
    if high < 0.0:
        return AdvancementDecision(
            status="reject",
            reason_code="separated_negative",
            reason="paired structural interval is separated in the unfavorable direction",
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
