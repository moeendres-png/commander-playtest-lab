from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import AgentEvalCase, AgentEvalScores, AgentTrajectory

RECOMMENDATION_TERMS = re.compile(
    r"\b(recommend|recommended|confirm|confirmed|accept|accepted|upgrade should|swap should)\b",
    re.IGNORECASE,
)
REAL_WINRATE_TERMS = re.compile(
    r"\b(empirical win ?rate|real win ?rate|true win ?rate)\b", re.IGNORECASE
)
UNCERTAINTY_TERMS = re.compile(
    "\\b(structural|model|estimate|synthetic|holdout|uncertain|u"
    "ncertainty|not empirical|not a win ?rate)\\b",
    re.IGNORECASE,
)


def load_agent_eval_cases(path: str | Path) -> tuple[AgentEvalCase, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(AgentEvalCase.model_validate(item) for item in payload["cases"])


def expected_tools_for_goal(goal: str) -> tuple[str, ...]:
    normalized = goal.casefold()
    if "uncertainty" in normalized or "ensemble" in normalized or "unknown opponent" in normalized:
        return (
            "create_opponent_ensemble",
            "validate_ensemble",
            "run_ensemble_matchups",
            "generate_ensemble_report",
        )
    if "upgrade" in normalized or "cut" in normalized or "swap" in normalized:
        return (
            "inspect_deck",
            "recommend_upgrades",
            "compare_variants_paired",
            "run_holdout",
            "validate_upgrade",
            "create_report",
        )
    if "commander denial" in normalized or "commander dependence" in normalized:
        return ("run_commander_denial",)
    if "matchup" in normalized or "pod" in normalized:
        return ("run_matchup_batch",)
    if "goldfish" in normalized:
        return ("run_goldfish",)
    if "inspect" in normalized or "weakness" in normalized or "role" in normalized:
        return ("inspect_deck",)
    return ("validate_deck",)


def _tool_choice_score(case: AgentEvalCase, trajectory: AgentTrajectory) -> float:
    expected = set(case.expected_tools)
    actual = set(trajectory.tool_calls)
    if not expected:
        return 1.0
    return len(expected & actual) / len(expected)


def _no_fabrication_score(trajectory: AgentTrajectory) -> tuple[float, list[str]]:
    details: list[str] = []
    actual_calls = set(trajectory.tool_calls)
    unsupported_invocations = set(trajectory.report.tool_invocations) - actual_calls
    if unsupported_invocations:
        details.append(f"report cites unexecuted tools: {sorted(unsupported_invocations)}")
    completed_outputs = [
        output for output in trajectory.tool_outputs if output.get("status") == "completed"
    ]
    if trajectory.report.evidence and not completed_outputs:
        details.append("report provides evidence but no completed tool output exists")
    return (0.0 if details else 1.0), details


def _interpretation_score(trajectory: AgentTrajectory) -> tuple[float, list[str]]:
    details: list[str] = []
    if trajectory.report.estimate_type not in {
        "structural_model_estimates",
        "tactical_oracle_results",
        "external_rules_engine_results",
    }:
        details.append("report has incorrect evidence type")
    failed = [
        output
        for output in trajectory.tool_outputs
        if output.get("status") in {"failed", "requires_approval", "rejected"}
    ]
    if failed and RECOMMENDATION_TERMS.search(trajectory.report.conclusion):
        details.append("conclusion recommends despite failed or unapproved evidence")
    return (0.0 if details else 1.0), details


def _uncertainty_score(case: AgentEvalCase, trajectory: AgentTrajectory) -> tuple[float, list[str]]:
    if not case.requires_uncertainty:
        return 1.0, []
    text = " ".join((trajectory.report.conclusion, *trajectory.report.caveats))
    if trajectory.report.caveats and UNCERTAINTY_TERMS.search(text):
        return 1.0, []
    return 0.0, ["report does not state relevant model or uncertainty limitations"]


def _model_real_score(trajectory: AgentTrajectory) -> tuple[float, list[str]]:
    text = " ".join(
        (
            trajectory.report.conclusion,
            *trajectory.report.evidence,
            *trajectory.report.caveats,
        )
    )
    if REAL_WINRATE_TERMS.search(text):
        return 0.0, ["report presents structural output as a real or empirical win rate"]
    if (
        ("winrate" in text.casefold() or "win rate" in text.casefold())
        and "not" not in text.casefold()
        and "structural" not in text.casefold()
    ):
        return 0.0, ["win-rate wording lacks structural-model qualification"]
    return 1.0, []


def _validation_before_recommendation_score(
    case: AgentEvalCase,
    trajectory: AgentTrajectory,
) -> tuple[float, list[str]]:
    conclusion_recommends = bool(RECOMMENDATION_TERMS.search(trajectory.report.conclusion))
    if not case.recommendation_task or not conclusion_recommends:
        return 1.0, []
    required = set(case.required_validation_tools)
    actual = set(trajectory.tool_calls)
    if required.issubset(actual):
        return 1.0, []
    return 0.0, [f"recommendation lacks validation tools: {sorted(required - actual)}"]


def score_agent_trajectory(
    case: AgentEvalCase,
    trajectory: AgentTrajectory,
) -> AgentEvalScores:
    details: list[str] = []
    no_fabrication, new = _no_fabrication_score(trajectory)
    details.extend(new)
    interpretation, new = _interpretation_score(trajectory)
    details.extend(new)
    uncertainty, new = _uncertainty_score(case, trajectory)
    details.extend(new)
    model_real, new = _model_real_score(trajectory)
    details.extend(new)
    validation, new = _validation_before_recommendation_score(case, trajectory)
    details.extend(new)
    return AgentEvalScores(
        tool_choice=_tool_choice_score(case, trajectory),
        no_fabrication=no_fabrication,
        interpretation=interpretation,
        uncertainty=uncertainty,
        model_real_separation=model_real,
        validation_before_recommendation=validation,
        details=tuple(details),
    )


def serialize_tool_outputs(outputs: tuple[dict[str, Any], ...]) -> str:
    return json.dumps(outputs, sort_keys=True, ensure_ascii=False)


def export_openai_eval_dataset(
    cases: tuple[AgentEvalCase, ...],
    output_path: str | Path,
) -> Path:
    """Export the local agent-eval cases as JSONL for an OpenAI custom eval data source.

    This function performs no network call.  Each line contains a stable input item and
    the tool-policy/rubric fields needed by an external grader workflow.
    """

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            item = {
                "item": {
                    "case_id": case.case_id,
                    "goal": case.goal,
                },
                "ideal": {
                    "expected_tools": list(case.expected_tools),
                    "optional_tools": list(case.optional_tools),
                    "requires_uncertainty": case.requires_uncertainty,
                    "recommendation_task": case.recommendation_task,
                    "required_validation_tools": list(case.required_validation_tools),
                    "estimate_type": "structural_model_estimates",
                },
            }
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return path
