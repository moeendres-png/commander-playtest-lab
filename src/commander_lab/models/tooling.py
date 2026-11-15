"""Models still used by the candidate repository and the eval models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import FrozenModel
from .structural import StructuralCardProfile


class CandidateProfile(FrozenModel):
    candidate_id: str
    card: StructuralCardProfile
    allowed_deck_ids: tuple[str, ...] = ()
    physical_status: str = "unverified_phase5"
    notes: str | None = None


class WorkflowReport(FrozenModel):
    workflow_id: str
    goal: str
    conclusion: str
    evidence: tuple[str, ...]
    caveats: tuple[str, ...]
    tool_invocations: tuple[str, ...]
    model_calls: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    estimate_type: Literal[
        "structural_model_estimates",
        "tactical_oracle_results",
        "external_rules_engine_results",
    ] = "structural_model_estimates"
