from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from commander_lab.models import CostLimits, ToolResponse, ToolStatus, WorkflowReport


FORBIDDEN_DIRECT_STATE_TERMS = frozenset(
    {
        "set_life",
        "move_card",
        "overwrite_game_state",
        "force_winner",
        "add_mana_directly",
        "edit_event_log",
    }
)


class GuardrailViolation(RuntimeError):
    pass


@dataclass(slots=True)
class WorkflowBudgetTracker:
    limits: CostLimits
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        return (
            self.input_tokens / 1_000_000 * self.limits.input_cost_per_million_usd
            + self.output_tokens / 1_000_000 * self.limits.output_cost_per_million_usd
        )

    def ensure_next_model_call_allowed(self) -> None:
        if self.model_calls >= self.limits.max_model_calls:
            raise GuardrailViolation("maximum model calls exceeded")
        if self.total_tokens >= self.limits.max_total_tokens:
            raise GuardrailViolation("maximum total token budget exceeded")
        if self.estimated_cost_usd >= self.limits.max_estimated_cost_usd:
            raise GuardrailViolation("maximum estimated API cost exceeded")

    def register_model_usage(
        self,
        *,
        calls: int,
        tokens: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        self.model_calls += calls
        if input_tokens is None and output_tokens is None:
            self.input_tokens += tokens or 0
        else:
            self.input_tokens += input_tokens or 0
            self.output_tokens += output_tokens or 0
        if self.model_calls > self.limits.max_model_calls:
            raise GuardrailViolation("maximum model calls exceeded")
        if self.total_tokens > self.limits.max_total_tokens:
            raise GuardrailViolation("maximum total token budget exceeded")
        if self.estimated_cost_usd > self.limits.max_estimated_cost_usd:
            raise GuardrailViolation("maximum estimated API cost exceeded")


def forbidden_state_terms(value: str) -> tuple[str, ...]:
    normalized = value.casefold()
    return tuple(sorted(term for term in FORBIDDEN_DIRECT_STATE_TERMS if term in normalized))


def validate_user_goal(goal: str) -> None:
    forbidden = forbidden_state_terms(goal)
    if forbidden:
        raise GuardrailViolation(
            "agents may not mutate deterministic game state directly: " + ", ".join(forbidden)
        )


def validate_tool_output(response: ToolResponse) -> None:
    if response.metadata.estimate_type != "structural_model_estimates":
        raise GuardrailViolation("simulation tool output has invalid estimate label")
    if response.status == ToolStatus.FAILED and not response.errors:
        raise GuardrailViolation("failed tools must contain understandable errors")


def validate_workflow_report(report: WorkflowReport) -> None:
    if report.estimate_type != "structural_model_estimates":
        raise GuardrailViolation("workflow output has invalid estimate label")
    if not report.tool_invocations:
        raise GuardrailViolation("agent workflow must cite at least one structured tool invocation")
    forbidden = forbidden_state_terms(report.conclusion)
    if forbidden:
        raise GuardrailViolation(
            "workflow output requests direct state mutation: " + ", ".join(forbidden)
        )


def flatten_agent_input(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return str(value)
