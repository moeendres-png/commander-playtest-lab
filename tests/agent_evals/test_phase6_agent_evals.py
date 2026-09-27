from __future__ import annotations

from commander_lab.evals import (
    AgentTrajectory,
    expected_tools_for_goal,
    load_agent_eval_cases,
    score_agent_trajectory,
)
from commander_lab.models import WorkflowReport


def _trajectory(
    case, calls, *, conclusion="Tool-backed structural analysis complete.", caveats=None
):
    outputs = tuple(
        {
            "status": "completed",
            "metadata": {
                "tool_name": tool,
                "invocation_id": f"inv-{index}",
                "estimate_type": "structural_model_estimates",
            },
            "result": {"evidence": tool},
        }
        for index, tool in enumerate(calls)
    )
    return AgentTrajectory(
        case_id=case.case_id,
        tool_calls=tuple(calls),
        tool_outputs=outputs,
        report=WorkflowReport(
            workflow_id=f"wf-{case.case_id}",
            goal=case.goal,
            conclusion=conclusion,
            evidence=tuple(f"Tool result: {tool}" for tool in calls),
            caveats=tuple(
                caveats
                or (
                    "These are structural_model_estimates, not empirical or real win rates.",
                    "Synthetic opponents and incomplete profiles remain uncertain.",
                )
            ),
            tool_invocations=tuple(calls),
        ),
    )


def test_offline_orchestration_policy_selects_required_tools(repo_root) -> None:
    cases = load_agent_eval_cases(repo_root / "data/evals/agent/agent_cases.json")
    for case in cases:
        calls = expected_tools_for_goal(case.goal)
        conclusion = (
            "The candidate is not recommended until paired and holdout validation passes."
            if case.recommendation_task
            else "Tool-backed structural analysis complete."
        )
        scores = score_agent_trajectory(case, _trajectory(case, calls, conclusion=conclusion))
        assert scores.tool_choice >= 0.95, (case.case_id, scores)
        assert scores.no_fabrication == 1.0
        assert scores.interpretation == 1.0
        assert scores.uncertainty == 1.0
        assert scores.model_real_separation == 1.0
        assert scores.validation_before_recommendation == 1.0


def test_agent_eval_detects_fabricated_tool_citation(repo_root) -> None:
    case = load_agent_eval_cases(repo_root / "data/evals/agent/agent_cases.json")[0]
    trajectory = _trajectory(case, ("validate_deck",)).model_copy(
        update={
            "report": _trajectory(case, ("validate_deck",)).report.model_copy(
                update={"tool_invocations": ("validate_deck", "run_matchup_batch")}
            )
        }
    )
    assert score_agent_trajectory(case, trajectory).no_fabrication == 0.0


def test_agent_eval_detects_real_winrate_claim(repo_root) -> None:
    case = load_agent_eval_cases(repo_root / "data/evals/agent/agent_cases.json")[1]
    trajectory = _trajectory(
        case,
        expected_tools_for_goal(case.goal),
        conclusion="The true empirical win rate is 62 percent.",
        caveats=("The run completed.",),
    )
    scores = score_agent_trajectory(case, trajectory)
    assert scores.model_real_separation == 0.0
    assert scores.uncertainty == 0.0


def test_agent_eval_blocks_recommendation_without_validation(repo_root) -> None:
    case = load_agent_eval_cases(repo_root / "data/evals/agent/agent_cases.json")[2]
    trajectory = _trajectory(
        case,
        ("inspect_deck", "recommend_upgrades"),
        conclusion="The swap is confirmed and recommended.",
    )
    assert score_agent_trajectory(case, trajectory).validation_before_recommendation == 0.0
