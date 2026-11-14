"""Pilot validation checks that used to live in the Phase-4 validation harness.

The harness module is gone; these tests keep every assertion it made about the live
pilots and the structural simulator: stochastic replay identical across worker counts,
a decision-log audit with all utility dimensions, and the strength calibration benchmark.
"""

from __future__ import annotations

import itertools
import json
import random
from pathlib import Path
from typing import Any

from commander_lab.agents.pilots import GenericCommanderPilot
from commander_lab.engine.structural.batch import run_structural_batch
from commander_lab.engine.structural.project import load_project_structural_decks
from commander_lab.engine.structural.simulator import StructuralSimulator
from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotOpponentView,
    PilotStateView,
    PilotStrength,
    StructuralAbortLimits,
    StructuralBatchConfig,
    StructuralMatchConfig,
)


def _result_signature(result: Any) -> list[tuple[object, ...]]:
    return [
        (
            match.seed,
            tuple(sorted(match.placements.items())),
            match.winner_ids,
            match.turns,
            match.log_sha256,
            match.end_reason,
        )
        for match in result.match_results
    ]


def _config(
    name: str,
    *,
    seed: int,
    iterations: int,
    workers: int,
    output_directory: Path,
    mode: PilotDecisionMode,
) -> StructuralBatchConfig:
    deck_ids = (
        "rogshai/current",
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )
    strengths = (
        PilotStrength.STRONG,
        PilotStrength.STRONG,
        PilotStrength.AVERAGE,
        PilotStrength.STRONG,
    )
    return StructuralBatchConfig(
        run_id=name,
        seed=seed,
        iterations=iterations,
        deck_ids=deck_ids,
        workers=workers,
        pilot_configs=tuple(
            PilotConfig(
                pilot_name="auto",
                strength=strength,
                mode=mode,
                mistake_rate=0.0 if mode == PilotDecisionMode.STOCHASTIC else None,
            )
            for strength in strengths
        ),
        output_directory=str(output_directory),
        limits=StructuralAbortLimits(
            max_turns=35,
            max_events=40_000,
            max_no_progress_turns=20,
            max_spells_per_turn=8,
        ),
    )


def _benchmark_state(**updates: object) -> PilotStateView:
    opponents = (
        PilotOpponentView(
            player_id="p2",
            life=30,
            threat=8,
            board_power=8,
            engine_value=3,
            graveyard_size=6,
            hand_size=5,
        ),
        PilotOpponentView(
            player_id="p3",
            life=28,
            threat=5,
            board_power=4,
            engine_value=1,
            graveyard_size=3,
            hand_size=4,
        ),
        PilotOpponentView(
            player_id="p4",
            life=25,
            threat=4,
            board_power=3,
            engine_value=1,
            graveyard_size=2,
            hand_size=4,
        ),
    )
    payload: dict[str, object] = {
        "player_id": "p1",
        "deck_id": "synthetic/pilot-benchmark",
        "strategy": "generic",
        "turn": 5,
        "pod_size": 4,
        "life": 34,
        "hand_size": 5,
        "mana_available": 4,
        "lands": 4,
        "ramp_mana": 0,
        "resources": 0,
        "tokens": 0,
        "board_power": 3,
        "engine_value": 1,
        "graveyard_size": 5,
        "opponents": opponents,
    }
    payload.update(updates)
    return PilotStateView.model_validate(payload)


def _benchmark_action(
    action_id: str,
    card_name: str,
    *,
    cost: float,
    roles: tuple[CardRole, ...] = (),
    remaining_mana: float = 0.0,
    immediate_impact: float = 0.7,
    floor_value: float = 0.7,
    base_power: float = 0.0,
    target_threat: float = 0.0,
    multiplayer_scaling: float = 0.0,
) -> PilotActionView:
    role_set = frozenset(roles)
    return PilotActionView(
        action_id=action_id,
        action_kind="card",
        card_name=card_name,
        mana_cost=cost,
        roles=role_set,
        role_strengths={role: 1.0 for role in role_set},
        remaining_mana=remaining_mana,
        immediate_impact=immediate_impact,
        floor_value=floor_value,
        base_power=base_power,
        target_threat=target_threat,
        multiplayer_scaling=multiplayer_scaling,
    )


def _decision_quality_benchmark(seed: int, trials: int) -> dict[str, object]:
    low_life_state = _benchmark_state(life=15)
    low_hand_state = _benchmark_state(hand_size=2, graveyard_size=14)
    finish_opponents = (
        PilotOpponentView(
            player_id=f"p{index}",
            life=life,
            threat=4,
            board_power=3,
            engine_value=1,
            graveyard_size=2,
            hand_size=3,
        )
        for index, life in enumerate((7, 8, 9), start=2)
    )
    scenarios = (
        (
            "early_ramp",
            _benchmark_state(turn=2, mana_available=2),
            (
                _benchmark_action(
                    "ramp",
                    "Efficient Ramp",
                    cost=2,
                    roles=(CardRole.RAMP,),
                    immediate_impact=0.8,
                    floor_value=0.8,
                ),
                _benchmark_action(
                    "slow_engine",
                    "Slow Engine",
                    cost=2,
                    roles=(CardRole.ENGINE,),
                    immediate_impact=0.25,
                    floor_value=0.55,
                ),
            ),
            "ramp",
        ),
        (
            "urgent_removal",
            low_life_state,
            (
                _benchmark_action(
                    "removal",
                    "Efficient Removal",
                    cost=2,
                    roles=(CardRole.REMOVAL,),
                    remaining_mana=2,
                    immediate_impact=1.0,
                    floor_value=0.8,
                    target_threat=11,
                ),
                _benchmark_action(
                    "draw",
                    "Draw Spell",
                    cost=2,
                    roles=(CardRole.DRAW,),
                    remaining_mana=2,
                    immediate_impact=0.5,
                    floor_value=0.8,
                ),
            ),
            "removal",
        ),
        (
            "post_wipe_rebuild",
            low_hand_state,
            (
                _benchmark_action(
                    "recursion",
                    "Recursion",
                    cost=3,
                    roles=(CardRole.RECURSION,),
                    remaining_mana=1,
                    immediate_impact=0.8,
                    floor_value=0.9,
                ),
                _benchmark_action(
                    "vanilla_body",
                    "Vanilla Body",
                    cost=3,
                    remaining_mana=1,
                    base_power=4,
                ),
            ),
            "recursion",
        ),
        (
            "table_finisher",
            _benchmark_state(opponents=tuple(finish_opponents)),
            (
                _benchmark_action(
                    "finisher",
                    "Table Finisher",
                    cost=5,
                    roles=(CardRole.FINISHER,),
                    immediate_impact=1.5,
                    floor_value=0.8,
                    multiplayer_scaling=1.5,
                ),
                _benchmark_action(
                    "draw",
                    "Draw Spell",
                    cost=2,
                    roles=(CardRole.DRAW,),
                    remaining_mana=3,
                    immediate_impact=0.5,
                    floor_value=0.8,
                ),
            ),
            "finisher",
        ),
    )
    result: dict[str, object] = {}
    rates: list[float] = []
    for strength_index, strength in enumerate(PilotStrength):
        pilot = GenericCommanderPilot(
            PilotConfig(
                pilot_name="GenericCommanderPilot",
                strength=strength,
                mode=PilotDecisionMode.STOCHASTIC,
            )
        )
        scenario_rates: dict[str, float] = {}
        correct = 0
        total = 0
        for scenario_index, (name, state, actions, expected) in enumerate(scenarios):
            hits = 0
            for trial in range(trials):
                scenario_seed = seed + strength_index * 1_000_003 + scenario_index * 10_007 + trial
                decision = pilot.choose_action(state, actions, random.Random(scenario_seed))
                hits += decision.selected_action_id == expected
            scenario_rates[name] = hits / trials
            correct += hits
            total += trials
        rate = correct / total
        rates.append(rate)
        result[strength.value] = {
            "correct_choices": correct,
            "total_choices": total,
            "expected_choice_rate": rate,
            "scenario_rates": scenario_rates,
        }
    return {
        "trials_per_scenario": trials,
        "scenarios": [scenario[0] for scenario in scenarios],
        "by_strength": result,
        "monotonic_non_decreasing": all(
            later + 1e-12 >= earlier for earlier, later in itertools.pairwise(rates)
        ),
        "purpose": "controlled action-choice calibration, not match win-rate validation",
    }


def _audit_decision_log(root: Path, output_directory: Path, seed: int) -> dict[str, object]:
    decks = load_project_structural_decks(root, include_synthetic_fixtures=True)
    event_path = output_directory / "pilot_decision_audit.jsonl"
    config = StructuralMatchConfig(
        match_id="phase4-decision-audit",
        seed=seed,
        deck_ids=("rogshai/current", "synthetic/aggro", "synthetic/control"),
        pilot_configs=(
            PilotConfig(
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            PilotConfig(
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            PilotConfig(
                strength=PilotStrength.STRONG,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
        ),
        limits=StructuralAbortLimits(
            max_turns=35,
            max_events=40_000,
            max_no_progress_turns=20,
        ),
    )
    result = StructuralSimulator(decks).simulate(config, event_log_path=event_path)
    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    decisions = [event for event in events if event["event_type"] == "pilot_decision"]
    phases: dict[str, int] = {}
    dimensions: set[str] = set()
    for event in decisions:
        phase = str(event["payload"]["phase"])
        phases[phase] = phases.get(phase, 0) + 1
        breakdown = event["payload"].get("breakdown") or {}
        dimensions.update(breakdown)
    required = {
        "survival",
        "mana_efficiency",
        "card_advantage",
        "tempo",
        "engine_development",
        "interaction_reserve",
        "commander_value",
        "threat_reduction",
        "win_progress",
        "political_visibility",
        "rebuild_capacity",
    }
    return {
        "match_completed": result.completed,
        "event_log": str(event_path),
        "event_log_sha256": result.log_sha256,
        "decision_events": len(decisions),
        "decision_phases": dict(sorted(phases.items())),
        "required_utility_dimensions_present": required.issubset(dimensions),
        "observed_breakdown_fields": sorted(dimensions),
    }


def test_phase4_validation_is_reproducible_and_audited(tmp_path: Path, repo_root: Path) -> None:
    iterations = 2
    seed = 707
    decks = load_project_structural_decks(repo_root, include_synthetic_fixtures=True)
    stochastic_config = _config(
        "phase4-specialists-stochastic",
        seed=seed + 1,
        iterations=iterations,
        workers=1,
        output_directory=tmp_path / "phase4" / "stochastic",
        mode=PilotDecisionMode.STOCHASTIC,
    )
    stochastic = run_structural_batch(stochastic_config, decks)
    replay_config = stochastic_config.model_copy(
        update={
            "workers": 1,
            "output_directory": str(tmp_path / "phase4" / "stochastic_replay"),
        }
    )
    stochastic_replay = run_structural_batch(replay_config, decks)
    assert _result_signature(stochastic) == _result_signature(stochastic_replay)

    audit = _audit_decision_log(repo_root, tmp_path / "phase4", seed + 3)
    assert audit["match_completed"]
    assert audit["decision_events"] > 0  # type: ignore[operator]
    assert audit["required_utility_dimensions_present"]

    benchmark = _decision_quality_benchmark(seed + 2, trials=max(64, iterations * 8))
    assert benchmark["monotonic_non_decreasing"]
    rates: Any = benchmark["by_strength"]
    assert rates["weak"]["expected_choice_rate"] < rates["average"]["expected_choice_rate"]
    assert rates["average"]["expected_choice_rate"] <= rates["strong"]["expected_choice_rate"]
    assert (
        rates["strong"]["expected_choice_rate"]
        <= rates["near_optimal_heuristic"]["expected_choice_rate"]
    )
