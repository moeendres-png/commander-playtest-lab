from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path

from commander_lab.agents import build_pilot
from commander_lab.evals import load_golden_cases
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength

ROOT = Path(__file__).resolve().parents[1]
DEV_PATH = ROOT / "data/evals/golden/pilot_decisions_j_p4_v1.json"
OPPONENT_PATH = ROOT / "data/opponents/current_structural_profiles.json"


def _profile_risk(profile: dict[str, object]) -> dict[str, float]:
    roles = dict(profile.get("roles", {}))
    remove = float(roles.get("removal", 0))
    counter = float(roles.get("counter", 0))
    wipe = float(roles.get("wipe", 0))
    unknown = int(profile.get("unknown_slot_count", 0) or 0)
    provisional = int(profile.get("provisional_completion_count", 0) or 0)
    synthetic_basics = int(profile.get("synthetic_basic_count", 0) or 0)
    evidence_kinds = set(profile.get("evidence_kinds", []))
    data_quality = str(profile.get("data_quality", "project_inferred"))
    synthetic_fraction = min(1.0, (unknown + provisional + synthetic_basics) / 100.0)
    if "synthetic_completion" in evidence_kinds or data_quality == "synthetic_assumption":
        synthetic_fraction = max(synthetic_fraction, 0.35)
    hidden_uncertainty = min(0.95, 0.12 + synthetic_fraction * 0.82)
    intent_uncertainty = min(0.85, 0.25 + synthetic_fraction * 0.45)
    return {
        "hidden_information_uncertainty": hidden_uncertainty,
        "opponent_intent_uncertainty": intent_uncertainty,
        "unknown_opponent_fraction": synthetic_fraction,
        "boardwipe_risk": min(0.9, 0.10 + wipe / 7.0),
        "commander_denial_risk": min(0.9, 0.10 + (remove + counter) / 18.0),
        "stack_pressure": min(0.8, 0.08 + counter / 8.0),
    }


def _opponent_presets() -> dict[str, dict[str, float]]:
    payload = json.loads(OPPONENT_PATH.read_text(encoding="utf-8"))
    return {
        str(profile["deck_id"]): _profile_risk(profile)
        for profile in payload["profiles"]
        if str(profile["deck_id"]) != "opponent/kaervek-reference"
    }


def _normalize_opponents(state: dict[str, object], pod: int) -> None:
    opponents = list(state["opponents"])[: pod - 1]
    while len(opponents) < pod - 1:
        player = len(opponents) + 2
        opponents.append(
            {
                "player_id": f"p{player}",
                "life": 35,
                "threat": 5.5,
                "board_power": 4,
                "engine_value": 2,
                "graveyard_size": 4,
                "hand_size": 5,
                "commander_damage_from_actor": {},
            }
        )
    state["pod_size"] = pod
    state["opponents"] = opponents
    state["seat_position"] = min(int(state["seat_position"]), pod)
    exposure = state.get("opponents_to_act_before_next_turn")
    state["opponents_to_act_before_next_turn"] = min(
        int(exposure if exposure is not None else pod - 1), pod - 1
    )


def _evaluate(case, *, state_update: dict[str, object] | None = None, strength=None):
    state_payload = case.state.model_dump(mode="json")
    if state_update:
        state_payload.update(state_update)
    pod = int(state_payload["pod_size"])
    state_payload["seat_position"] = min(int(state_payload["seat_position"]), pod)
    exposure = state_payload.get("opponents_to_act_before_next_turn")
    state_payload["opponents_to_act_before_next_turn"] = min(
        int(exposure if exposure is not None else pod - 1), pod - 1
    )
    state = type(case.state).model_validate(state_payload)
    pilot = build_pilot(
        PilotConfig(
            pilot_name="auto",
            strength=strength or case.strength,
            mode=PilotDecisionMode.DETERMINISTIC,
            mistake_rate=0.0,
        ),
        strategy=case.strategy,
    )
    decision = pilot.choose_action(state, case.actions, random.Random(0))
    action = next(item for item in case.actions if item.action_id == decision.selected_action_id)
    action_class = str(action.metadata.get("action_class", ""))
    if decision.selected_action_id in case.critical_failure_actions:
        outcome = "critical_failure"
    elif action_class in case.preferred_action_classes:
        outcome = "preferred"
    elif action_class in case.acceptable_action_classes:
        outcome = "acceptable"
    elif action_class in case.bad_action_classes:
        outcome = "bad"
    else:
        outcome = "unclassified"
    return {
        "action_id": decision.selected_action_id,
        "action_class": action_class,
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    cases = load_golden_cases(DEV_PATH)
    rows: list[dict[str, object]] = []

    def add(axis: str, level: object, case, result: dict[str, object]) -> None:
        rows.append(
            {
                "axis": axis,
                "level": str(level),
                "case_id": case.case_id,
                "strategy": case.strategy,
                **result,
            }
        )

    for case in cases:
        base = case.state.model_dump(mode="json")
        for pod in (3, 4, 5):
            state = copy.deepcopy(base)
            _normalize_opponents(state, pod)
            add("pod_size", pod, case, _evaluate(case, state_update=state))
        for seat in sorted({1, max(1, (case.state.pod_size + 1) // 2), case.state.pod_size}):
            add("seat", seat, case, _evaluate(case, state_update={"seat_position": seat}))
        for strength in PilotStrength:
            add("pilot_strength", strength.value, case, _evaluate(case, strength=strength))
        for risk in (0.1, 0.5, 0.9):
            add(
                "commander_denial",
                risk,
                case,
                _evaluate(case, state_update={"commander_denial_risk": risk}),
            )
            add(
                "boardwipe",
                risk,
                case,
                _evaluate(case, state_update={"boardwipe_risk": risk}),
            )

    unknown_assumptions = {
        "low": {
            "hidden_information_uncertainty": 0.1,
            "opponent_intent_uncertainty": 0.15,
            "unknown_opponent_fraction": 0.0,
        },
        "medium": {
            "hidden_information_uncertainty": 0.5,
            "opponent_intent_uncertainty": 0.5,
            "unknown_opponent_fraction": 0.35,
        },
        "high": {
            "hidden_information_uncertainty": 0.9,
            "opponent_intent_uncertainty": 0.8,
            "unknown_opponent_fraction": 0.75,
        },
    }
    for label, update in unknown_assumptions.items():
        for case in cases:
            add("unknown_opponent_assumption", label, case, _evaluate(case, state_update=update))
    for label, update in _opponent_presets().items():
        for case in cases:
            add("opponent_ensemble", label, case, _evaluate(case, state_update=update))

    summary: dict[str, dict[str, dict[str, float | int]]] = {}
    for axis in sorted({str(row["axis"]) for row in rows}):
        summary[axis] = {}
        levels = sorted({str(row["level"]) for row in rows if row["axis"] == axis})
        for level in levels:
            subset = [row for row in rows if row["axis"] == axis and row["level"] == level]
            n = len(subset)
            summary[axis][level] = {
                "n": n,
                "contract_preserving_rate": sum(
                    row["outcome"] in {"preferred", "acceptable"} for row in subset
                )
                / n,
                "preferred_rate": sum(row["outcome"] == "preferred" for row in subset) / n,
                "bad_rate": sum(row["outcome"] == "bad" for row in subset) / n,
                "critical_failure_rate": sum(row["outcome"] == "critical_failure" for row in subset)
                / n,
            }

    per_pilot: dict[str, dict[str, float | int]] = {}
    for strategy in ("korvold", "rogshai"):
        subset = [row for row in rows if row["strategy"] == strategy]
        n = len(subset)
        per_pilot[strategy] = {
            "n": n,
            "contract_preserving_rate": sum(
                row["outcome"] in {"preferred", "acceptable"} for row in subset
            )
            / n,
            "bad_rate": sum(row["outcome"] == "bad" for row in subset) / n,
            "critical_failure_rate": sum(row["outcome"] == "critical_failure" for row in subset)
            / n,
        }

    payload = {
        "schema_version": "1.0.0",
        "phase": "J-P4",
        "estimate_type": "structural_model_estimates",
        "source": "J_P4_DEVELOPMENT_GOLDENS_v1 only; untouched holdout not loaded",
        "holdout_evaluated": False,
        "row_count": len(rows),
        "summary": summary,
        "per_pilot": per_pilot,
        "opponent_profile_source": str(OPPONENT_PATH.relative_to(ROOT)),
        "opponent_ensemble_note": (
            "Each current opponent profile is an unweighted structural sensitivity case. "
            "Risk values are deterministic transforms of current role densities and uncertainty metadata; "
            "they are not observed frequencies or empirical metagame weights."
        ),
        "failures": [row for row in rows if row["outcome"] in {"bad", "critical_failure"}],
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    gate = all(
        metrics["contract_preserving_rate"] >= 0.95 and metrics["critical_failure_rate"] == 0.0
        for levels in summary.values()
        for metrics in levels.values()
    )
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
