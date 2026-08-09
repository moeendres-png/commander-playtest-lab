from __future__ import annotations

import json
import random
from pathlib import Path

from commander_lab.agents import build_pilot
from commander_lab.models import PilotConfig, PilotDecisionMode

from .models import EvalCaseResult, EvalStatus, EvalTier, GoldenDecisionCase


def load_golden_cases(path: str | Path) -> tuple[GoldenDecisionCase, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(GoldenDecisionCase.model_validate(item) for item in payload["cases"])


def run_golden_cases(
    cases: tuple[GoldenDecisionCase, ...],
    *,
    source: str = "data/evals/golden/pilot_decisions.json",
) -> list[EvalCaseResult]:
    results: list[EvalCaseResult] = []
    for case in cases:
        pilot = build_pilot(
            PilotConfig(
                pilot_name="auto",
                strength=case.strength,
                mode=PilotDecisionMode.DETERMINISTIC,
                mistake_rate=0.0,
            ),
            strategy=case.strategy,
        )
        decision = pilot.choose_action(case.state, case.actions, random.Random(0))
        passed = decision.selected_action_id in case.accepted_actions
        results.append(
            EvalCaseResult(
                case_id=case.case_id,
                tier=EvalTier.GOLDEN,
                status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
                passed=passed,
                critical=case.critical,
                score=1.0 if passed else 0.0,
                expected=sorted(case.accepted_actions),
                observed=decision.selected_action_id,
                details=(
                    case.description,
                    f"group={case.scenario_group}",
                    f"preferred_action_class={case.preferred_action_class or 'unspecified'}",
                ),
                source=source,
            )
        )
    return results
