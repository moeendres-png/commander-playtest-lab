"""Targets, modes, trigger orders and colour picks that score alike are not decided by the alphabet.

In 24 recorded real games the pilot's ranking left the best two options tied, with different
names, in 191 of 772 target rankings, 48 of 207 trigger orders, 17 of 48 modes, 32 of 626 colour
picks and all 3 replacement effects. The target ranking sorts by score, name and id, and the
deterministic pilot picks the largest action id, so the name that sorts last always won (the same
opponent permanent every time). These tests pin that a tie is broken by the decision's seeded rng,
the same way for the same seed and for any offer order, and that a clear winner is left alone.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import (
    PilotActionView,
    PilotConfig,
    PilotDecision,
    PilotDecisionMode,
    PilotStrength,
)

NAMES = ["Alpha option", "Beta option", "Gamma option"]


def _policy(
    mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC,
) -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in (1, 2):
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"test/seat-{seat}",
            strategy="generic",
            commander_names=("Test Commander",),
            config=PilotConfig(
                pilot_name="auto",
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=mode,
            ),
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(
            _RuntimePilot(binding=binding, pilot=build_pilot(binding.config, strategy="generic"))
        )
    return ExternalPilotDecisionPolicy(tuple(runtimes), scenario_seed=1)


def _state() -> dict[str, Any]:
    return {
        "actor_id": "actor-1",
        "players": [
            {
                "player_id": "actor-1",
                "mana_pool": {},
                "hand": [{"object_id": "hand-1", "name": "Hand Card"}],
            }
        ],
    }


def _semantic_options(names: list[str]) -> list[dict[str, Any]]:
    return [
        {"option_id": f"id-{name}", "option_type": "choice", "label": name, "metadata": {}}
        for name in names
    ]


def _target_options(names: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "option_id": f"id-{name}",
            "option_type": "target",
            "label": name,
            "metadata": {
                "object_id": f"id-{name}",
                "name": name,
                "zone": "battlefield",
                "zone_index": index,
            },
        }
        for index, name in enumerate(names)
    ]


def _semantic_pick(names: list[str], seed: int) -> str:
    policy = _policy()
    picked = policy._decide_semantic_option(
        policy._pilots[1], _state(), _semantic_options(names), random.Random(seed)
    )
    return picked.removeprefix("id-")


def _target_pick(names: list[str], seed: int) -> str:
    policy = _policy()
    picked = policy._decide_targets(
        policy._pilots[1],
        _state(),
        {"context": {"outcome": "neutral"}},
        _target_options(names),
        1,
        1,
        random.Random(seed),
    )
    assert len(picked) == 1
    return picked[0].removeprefix("id-")


@pytest.mark.parametrize("pick", [_semantic_pick, _target_pick])
def test_options_that_score_alike_are_not_taken_in_name_order(pick: Any) -> None:
    picks = {pick(NAMES, seed) for seed in range(30)}
    assert picks <= set(NAMES)
    assert len(picks) > 1, "the same option every time is a decision by name"


@pytest.mark.parametrize("pick", [_semantic_pick, _target_pick])
def test_a_tie_is_broken_the_same_way_for_the_same_seed_and_any_offer_order(pick: Any) -> None:
    for seed in range(12):
        forward = pick(NAMES, seed)
        assert pick(NAMES, seed) == forward
        assert pick(list(reversed(NAMES)), seed) == forward


def test_equal_scores_are_shuffled_only_among_different_names() -> None:
    ranked = [
        (3.0, "Zed", "z:0"),
        (2.0, "Same", "s:1"),
        (2.0, "Same", "s:0"),
        (1.0, "Quux", "q:0"),
        (1.0, "Bar", "b:0"),
    ]
    out = ExternalPilotDecisionPolicy._equal_scores_by_rng(ranked, random.Random(0))
    # a clear winner stays first, groups stay in score order, equal names keep their order
    assert out[0] == (3.0, "Zed", "z:0")
    assert out[1:3] == [(2.0, "Same", "s:1"), (2.0, "Same", "s:0")]
    assert {item[1] for item in out[3:]} == {"Quux", "Bar"}
    firsts = {
        ExternalPilotDecisionPolicy._equal_scores_by_rng(ranked, random.Random(seed))[3][1]
        for seed in range(20)
    }
    assert firsts == {"Quux", "Bar"}


def _decision(candidates: tuple[tuple[str, float], ...], selected: str) -> PilotDecision:
    return PilotDecision(
        pilot_name="auto",
        strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
        mode=PilotDecisionMode.DETERMINISTIC,
        selected_action_id=selected,
        selected_utility=dict(candidates)[selected],
        candidates=candidates,
    )


def _actions(costs: dict[str, float]) -> list[PilotActionView]:
    return [
        PilotActionView(
            action_id=action_id, action_kind="card", card_name=action_id, mana_cost=cost
        )
        for action_id, cost in costs.items()
    ]


def test_only_options_tied_with_the_pilots_pick_are_reopened() -> None:
    policy = _policy()
    runtime = policy._pilots[1]
    candidates = (("semantic:c:0", 1.0), ("semantic:b:0", 1.0), ("semantic:a:0", 0.5))
    actions = _actions({"semantic:a:0": 0.0, "semantic:b:0": 0.0, "semantic:c:0": 0.0})
    picks = {
        policy._among_equal_scores(
            runtime, _decision(candidates, "semantic:c:0"), actions, random.Random(seed)
        )
        for seed in range(30)
    }
    assert picks == {"semantic:b:0", "semantic:c:0"}


def test_a_dearer_option_does_not_join_the_tie() -> None:
    policy = _policy()
    candidates = (("semantic:c:0", 1.0), ("semantic:b:0", 1.0))
    actions = _actions({"semantic:b:0": 2.0, "semantic:c:0": 0.0})
    picks = {
        policy._among_equal_scores(
            policy._pilots[1], _decision(candidates, "semantic:c:0"), actions, random.Random(seed)
        )
        for seed in range(20)
    }
    assert picks == {"semantic:c:0"}


def test_two_copies_of_one_label_are_not_a_tie_between_different_options() -> None:
    policy = _policy()
    candidates = (("semantic:token:1", 1.0), ("semantic:token:0", 1.0))
    actions = _actions({"semantic:token:0": 0.0, "semantic:token:1": 0.0})
    for seed in range(10):
        assert (
            policy._among_equal_scores(
                policy._pilots[1],
                _decision(candidates, "semantic:token:1"),
                actions,
                random.Random(seed),
            )
            == "semantic:token:1"
        )


def test_a_stochastic_pilot_keeps_its_own_pick() -> None:
    policy = _policy(PilotDecisionMode.STOCHASTIC)
    candidates = (("semantic:c:0", 1.0), ("semantic:b:0", 1.0))
    actions = _actions({"semantic:b:0": 0.0, "semantic:c:0": 0.0})
    for seed in range(10):
        assert (
            policy._among_equal_scores(
                policy._pilots[1],
                _decision(candidates, "semantic:c:0"),
                actions,
                random.Random(seed),
            )
            == "semantic:c:0"
        )
