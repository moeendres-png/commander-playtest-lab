"""Which defender an attacker goes for when the pilot scores them alike (#989 phase 6).

In 24 recorded real games 435 attack decisions were tied on the pilot's score and were broken by
the action id, which is built from the label: the highest "Full Game Seat N" won in 328 of 328
player-against-player ties, and a planeswalker whose name sorts after "Full Game Seat" won the
other 107. The attack score (lethal, the weakest defender, crack-back) was computed for every
option and never reached that ranking. These tests pin the tie-break: the tied defender the
attack score prefers, and among defenders it cannot tell apart the seeded rng, never a name.
"""

from __future__ import annotations

import random
from types import SimpleNamespace
from typing import Any

from commander_lab.agents import GenericCommanderPilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.engine.rules.full_game_pilot.combat import _CombatDecisions
from commander_lab.models import PilotConfig, PilotStrength


def _runtime(utilities: dict[str, float]) -> Any:
    """A pilot whose utility for each action id is given; precision as the near-optimal one."""
    pilot = SimpleNamespace(
        policy=SimpleNamespace(precision=6),
        evaluate_action=lambda _state, action: SimpleNamespace(
            total_utility=utilities[action.action_id]
        ),
    )
    return SimpleNamespace(pilot=pilot)


def _action(action_id: str) -> Any:
    return SimpleNamespace(action_id=action_id)


def _break(
    utilities: dict[str, float], scores: dict[str, float], chosen: str, seed: int = 1
) -> str:
    actions = [_action(action_id) for action_id in utilities]
    return _CombatDecisions._break_attack_tie(
        _runtime(utilities),
        object(),
        actions,
        scores,
        chosen,
        random.Random(seed),  # type: ignore[arg-type]
    )


def test_the_attack_score_breaks_a_tie_between_defenders() -> None:
    utilities = {"attack:seat 4": 2.0, "attack:seat 3": 2.0, "attack:seat 2": 2.0}
    scores = {"attack:seat 4": 0.7, "attack:seat 3": 1.3, "attack:seat 2": 0.7}
    picks = {_break(utilities, scores, "attack:seat 4", seed) for seed in range(12)}
    assert picks == {"attack:seat 3"}


def test_defenders_the_score_cannot_tell_apart_are_chosen_by_the_rng() -> None:
    utilities = {"attack:seat 4": 2.0, "attack:seat 3": 2.0, "attack:seat 2": 2.0}
    scores = {"attack:seat 4": 0.7, "attack:seat 3": 0.7, "attack:seat 2": 0.7}
    picks = {_break(utilities, scores, "attack:seat 4", seed) for seed in range(60)}
    assert picks == {"attack:seat 4", "attack:seat 3", "attack:seat 2"}


def test_a_defender_the_pilot_scored_higher_is_kept() -> None:
    utilities = {"attack:seat 4": 2.5, "attack:seat 3": 2.0}
    scores = {"attack:seat 4": 0.7, "attack:seat 3": 1.3}
    assert _break(utilities, scores, "attack:seat 4") == "attack:seat 4"


def test_the_hold_choice_is_left_alone() -> None:
    utilities = {"attack:seat 4": 0.2, "attack:seat 3": 0.2, "attack:hold": 0.2}
    scores = {"attack:seat 4": 0.7, "attack:seat 3": 1.3}
    assert _break(utilities, scores, "attack:hold") == "attack:hold"


def test_utilities_that_differ_below_the_pilots_precision_still_tie() -> None:
    utilities = {"attack:seat 4": 2.0000001, "attack:seat 3": 2.0}
    scores = {"attack:seat 4": 0.7, "attack:seat 3": 1.3}
    assert _break(utilities, scores, "attack:seat 4") == "attack:seat 3"


def _policy(seed: int) -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC)
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Esior, Wardwing Familiar",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), seed)  # type: ignore[arg-type]


def _state() -> dict[str, Any]:
    def player(player_id: str, seat: int, board: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "player_id": player_id,
            "seat": seat,
            "is_actor": seat == 0,
            "life": 40,
            "hand_count": 7,
            "library_count": 90,
            "graveyard_count": 0,
            "battlefield": board,
            "graveyard": [],
            "command": [],
            "hand": [],
            "mana_pool": {},
        }

    claim = {
        "object_id": "claim",
        "name": "Claim Jumper",
        "tapped": False,
        "power": 3,
        "toughness": 3,
        "damage": 0,
    }
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 6,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "declare_attackers",
        "step": "declare_attackers",
        "players": [
            player("actor", 0, [claim]),
            player("opponent-1", 1, []),
            player("opponent-2", 2, []),
            player("opponent-3", 3, []),
        ],
        "stack": [],
        "commander_status": [],
    }


def _attack_request() -> dict[str, Any]:
    options = [
        {
            "option_id": "hold",
            "label": "Do not attack with Claim Jumper",
            "option_type": "hold_attacker",
            "metadata": {"object_id": "claim", "name": "Claim Jumper"},
        },
        *[
            {
                "option_id": f"attack-{seat}",
                "label": f"Claim Jumper attacks Full Game Seat {seat + 1}",
                "option_type": "declare_attacker",
                "metadata": {
                    "object_id": "claim",
                    "name": "Claim Jumper",
                    "defender_id": f"opponent-{seat}",
                },
            }
            for seat in (1, 2, 3)
        ],
    ]
    return {
        "decision_id": "opaque-declare_attacker",
        "decision_offset": 1,
        "actor_id": "actor",
        "decision_class": "declare_attacker",
        "pilot_state": _state(),
        "context": {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": options,
        "prompt": "Choose attack for Claim Jumper",
    }


def test_the_weaker_defender_is_attacked_not_the_highest_seat() -> None:
    request = _attack_request()
    # Seat 3 is the one down to 25 life: the attack score finishes it, and the pilot's own
    # score does not tell the three defenders apart (before, the highest seat label won).
    for player in request["pilot_state"]["players"]:
        if player["player_id"] == "opponent-2":
            player["life"] = 25
    picks = {_policy(seed).decide(request)["selected_option_ids"][0] for seed in range(8)}
    assert picks == {"attack-2"}
