import pytest

from commander_lab.agents.guardrails import GuardrailViolation, WorkflowBudgetTracker, validate_user_goal
from commander_lab.models import CostLimits


def test_direct_game_state_mutation_is_rejected() -> None:
    with pytest.raises(GuardrailViolation):
        validate_user_goal("Please overwrite_game_state and force_winner")


def test_model_budget_is_enforced() -> None:
    tracker = WorkflowBudgetTracker(CostLimits(max_model_calls=2, max_total_tokens=1000))
    tracker.register_model_usage(calls=1, tokens=200)
    with pytest.raises(GuardrailViolation):
        tracker.register_model_usage(calls=2, tokens=100)
