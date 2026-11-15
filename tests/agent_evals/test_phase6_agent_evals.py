from __future__ import annotations

from commander_lab.evals import AgentTrajectory
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
