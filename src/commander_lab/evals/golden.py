from __future__ import annotations

import json
import random
from pathlib import Path

from commander_lab.agents import build_pilot
from commander_lab.agents.pilots import KorvoldPilot
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
        config = PilotConfig(
            pilot_name="auto",
            strength=case.strength,
            mode=PilotDecisionMode.DETERMINISTIC,
            mistake_rate=0.0,
        )
        # Historical Korvold golden cases remain executable as provenance/eval fixtures,
        # but they must not route through the live own-deck pilot selector.
        pilot = (
            KorvoldPilot(config)
            if case.strategy.casefold() == "korvold"
            else build_pilot(config, strategy=case.strategy)
        )
        state = case.state.model_copy(update={"seat_position": case.seat})
        decision = pilot.choose_action(state, case.actions, random.Random(0))
        selected = next(
            (action for action in case.actions if action.action_id == decision.selected_action_id),
            None,
        )
        selected_class = (
            str(selected.metadata.get("action_class", "")) if selected is not None else ""
        )
        preferred_classes = set(case.preferred_action_classes)
        acceptable_classes = set(case.acceptable_action_classes)
        bad_classes = set(case.bad_action_classes)
        critical_failure = decision.selected_action_id in set(case.critical_failure_actions)
        if critical_failure:
            passed = False
            score = 0.0
            outcome_class = "critical_failure"
        elif selected_class and selected_class in preferred_classes:
            passed = True
            score = 1.0
            outcome_class = "preferred"
        elif selected_class and selected_class in acceptable_classes:
            passed = True
            score = 0.75
            outcome_class = "acceptable"
        elif selected_class and selected_class in bad_classes:
            passed = False
            score = 0.0
            outcome_class = "bad"
        elif case.accepted_actions:
            passed = decision.selected_action_id in case.accepted_actions
            score = 1.0 if passed else 0.0
            outcome_class = "accepted_id" if passed else "rejected_id"
        else:
            passed = False
            score = 0.25
            outcome_class = "unclassified"
        expected = (
            {
                "preferred_action_classes": sorted(preferred_classes),
                "acceptable_action_classes": sorted(acceptable_classes),
                "bad_action_classes": sorted(bad_classes),
                "critical_failure_actions": sorted(case.critical_failure_actions),
            }
            if preferred_classes or acceptable_classes or bad_classes
            else sorted(case.accepted_actions)
        )
        results.append(
            EvalCaseResult(
                case_id=case.case_id,
                tier=EvalTier.GOLDEN,
                status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
                passed=passed,
                critical=case.critical,
                score=score,
                expected=expected,
                observed={
                    "action_id": decision.selected_action_id,
                    "action_class": selected_class or None,
                    "outcome_class": outcome_class,
                },
                details=(
                    case.description,
                    f"group={case.scenario_group}",
                    f"preferred_action_class={case.preferred_action_class or 'unspecified'}",
                    f"outcome_class={outcome_class}",
                ),
                source=source,
            )
        )
    return results
