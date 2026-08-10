from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from commander_lab.models.common import FrozenModel, MutableModel
from commander_lab.models.pilots import PilotActionView, PilotStateView, PilotStrength
from commander_lab.models.tooling import WorkflowReport


class EvalTier(StrEnum):
    UNIT = "unit"
    PROPERTY = "property"
    GOLDEN = "golden"
    DIFFERENTIAL = "differential"
    AGENT = "agent"


class EvalStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class AcceptanceThresholds(FrozenModel):
    unit_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    property_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    minimum_property_cases: int = Field(default=250, ge=1)
    golden_pass_rate: float = Field(default=0.95, ge=0.0, le=1.0)
    golden_critical_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    differential_match_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    minimum_external_differential_cases: int = Field(default=3, ge=1)
    agent_tool_choice_rate: float = Field(default=0.95, ge=0.0, le=1.0)
    agent_interpretation_rate: float = Field(default=0.95, ge=0.0, le=1.0)
    agent_uncertainty_rate: float = Field(default=0.95, ge=0.0, le=1.0)
    agent_no_fabrication_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    agent_model_real_separation_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    agent_validation_before_recommendation_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    maximum_aborted_property_games_rate: float = Field(default=0.02, ge=0.0, le=1.0)


class EvalCaseResult(FrozenModel):
    case_id: str
    tier: EvalTier
    status: EvalStatus
    passed: bool
    critical: bool = False
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    expected: Any = None
    observed: Any = None
    details: tuple[str, ...] = ()
    source: str | None = None


class EvalTierSummary(FrozenModel):
    tier: EvalTier
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    blocked: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    critical_total: int = Field(ge=0)
    critical_passed: int = Field(ge=0)
    critical_pass_rate: float = Field(ge=0.0, le=1.0)


class AcceptanceGate(FrozenModel):
    gate_name: str
    passed: bool
    measured: float | int | str | bool
    threshold: float | int | str | bool
    details: str
    blocking: bool = True


class EvalSuiteResult(MutableModel):
    suite_id: str
    engine_version: str
    package_version: str
    thresholds: AcceptanceThresholds
    cases: list[EvalCaseResult]
    tier_summaries: dict[EvalTier, EvalTierSummary] = Field(default_factory=dict)
    gates: list[AcceptanceGate] = Field(default_factory=list)
    local_acceptance_passed: bool = False
    full_release_acceptance_passed: bool = False
    estimate_type: Literal["structural_model_estimates"] = "structural_model_estimates"
    notes: list[str] = Field(default_factory=list)


class GoldenDecisionCase(FrozenModel):
    case_id: str
    description: str
    strategy: str
    strength: PilotStrength = PilotStrength.NEAR_OPTIMAL_HEURISTIC
    state: PilotStateView
    actions: tuple[PilotActionView, ...]
    expected_action_id: str | None = None
    acceptable_action_ids: tuple[str, ...] = ()
    bad_action_ids: tuple[str, ...] = ()
    # J-P4 action-class contract.  Existing ID-based corpora remain supported.
    preferred_action_class: str | None = None
    preferred_action_classes: tuple[str, ...] = ()
    acceptable_action_classes: tuple[str, ...] = ()
    bad_action_classes: tuple[str, ...] = ()
    critical_failure_actions: tuple[str, ...] = ()
    scenario_group: Literal["development", "holdout"] = "development"
    seat: int = Field(default=1, ge=1, le=10)
    known_information: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    stack_state_if_relevant: str | None = None
    strategic_reason: str | None = None
    failure_mode: str | None = None
    expected_utility_dimensions: tuple[str, ...] = ()
    critical: bool = True

    @property
    def accepted_actions(self) -> frozenset[str]:
        accepted = set(self.acceptable_action_ids)
        if self.expected_action_id is not None:
            accepted.add(self.expected_action_id)
        return frozenset(accepted)

    @model_validator(mode="after")
    def validate_actions(self) -> GoldenDecisionCase:
        action_ids = {action.action_id for action in self.actions}
        action_classes = {
            str(action.metadata.get("action_class", "")) for action in self.actions
        } - {""}
        has_class_contract = bool(self.preferred_action_classes or self.acceptable_action_classes)
        if not self.accepted_actions and not has_class_contract:
            raise ValueError(
                "golden case requires accepted action IDs or preferred/acceptable action classes"
            )
        if not self.accepted_actions.issubset(action_ids):
            raise ValueError("accepted actions must exist in actions")
        if not set(self.bad_action_ids).issubset(action_ids):
            raise ValueError("bad actions must exist in actions")
        if not set(self.critical_failure_actions).issubset(action_ids):
            raise ValueError("critical failure actions must exist in actions")
        if self.accepted_actions.intersection(self.bad_action_ids):
            raise ValueError("an action cannot be both acceptable and bad")
        preferred_classes = set(self.preferred_action_classes)
        acceptable_classes = set(self.acceptable_action_classes)
        bad_classes = set(self.bad_action_classes)
        if preferred_classes & bad_classes or acceptable_classes & bad_classes:
            raise ValueError("an action class cannot be both accepted and bad")
        referenced_classes = preferred_classes | acceptable_classes | bad_classes
        if not referenced_classes.issubset(action_classes):
            missing = sorted(referenced_classes - action_classes)
            raise ValueError(f"action classes missing from actions: {missing}")
        if self.seat > self.state.pod_size:
            raise ValueError("seat must be within the scenario pod")
        if self.state.turn < 1:
            raise ValueError("scenario turn must be positive")
        return self


class DifferentialCase(FrozenModel):
    case_id: str
    description: str
    backend: Literal["forge", "xmage", "either"] = "either"
    input_state: dict[str, Any]
    expected_normalized: dict[str, Any]
    comparison_keys: tuple[str, ...]
    critical: bool = True


class DifferentialObservation(FrozenModel):
    case_id: str
    backend: str
    normalized_output: dict[str, Any]
    backend_version: str | None = None
    command: tuple[str, ...] = ()
    stdout: str = ""
    stderr: str = ""


class AgentEvalCase(FrozenModel):
    case_id: str
    goal: str
    expected_tools: tuple[str, ...]
    optional_tools: tuple[str, ...] = ()
    requires_uncertainty: bool = True
    recommendation_task: bool = False
    required_validation_tools: tuple[str, ...] = ()
    critical: bool = True


class AgentTrajectory(FrozenModel):
    case_id: str
    tool_calls: tuple[str, ...]
    tool_outputs: tuple[dict[str, Any], ...]
    report: WorkflowReport


class AgentEvalScores(FrozenModel):
    tool_choice: float = Field(ge=0.0, le=1.0)
    no_fabrication: float = Field(ge=0.0, le=1.0)
    interpretation: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    model_real_separation: float = Field(ge=0.0, le=1.0)
    validation_before_recommendation: float = Field(ge=0.0, le=1.0)
    details: tuple[str, ...] = ()

    @property
    def minimum_score(self) -> float:
        return min(
            self.tool_choice,
            self.no_fabrication,
            self.interpretation,
            self.uncertainty,
            self.model_real_separation,
            self.validation_before_recommendation,
        )
