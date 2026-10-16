from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from commander_lab.storage import sha256_value

AdvancementStatus = Literal["advance", "diagnose", "reject", "profile_required"]
LEGACY_ADVANCEMENT_REASON = "legacy_advancement_retired_use_optimizer_v2_1E_2F"


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
    """Compatibility shim for the retired pre-1E/2F advancement API.

    Historical callers may still use this function to diagnose hard-constraint, domain,
    fidelity, model-information, and stale-resolution problems. It must never use the retired
    ``effective_resolution`` value to authorize sensitivity, ablation, promotion, rejection, or
    canonical deck changes. Once the diagnostic prerequisites are satisfied, current decisions
    are routed to the manifest-bound Optimizer-v2 1E/2F path.
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
            reason="legacy resolution metadata is stale or unmeasured; it cannot authorize advancement",
            sensitivity_allowed=False,
            expensive_ablation_allowed=False,
        )

    return AdvancementDecision(
        status="diagnose",
        reason_code=LEGACY_ADVANCEMENT_REASON,
        reason=(
            "legacy effective-resolution advancement is retired; use the manifest-bound "
            "Optimizer v2 1E/2F confirmatory decision path"
        ),
        sensitivity_allowed=False,
        expensive_ablation_allowed=False,
    )
