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

    The historical function used ``effective_resolution`` as an operative promotion/rejection
    threshold. That decision architecture is retired. Keeping this symbol importable avoids
    breaking archival readers, but it can no longer authorize sensitivity, ablation, promotion,
    rejection, or canonical deck changes. All current decisions must use Optimizer v2 1E/2F.
    """

    del model_informativeness, domain_validity, structural_fidelity, model_resolution
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


__all__ = ["AdvancementDecision", "LEGACY_ADVANCEMENT_REASON", "decide_advancement"]
