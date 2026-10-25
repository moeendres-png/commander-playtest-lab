"""Which loyalty ability of a planeswalker the full-game pilot uses (#989 phase 6).

Every loyalty ability scored alike, so the one that sorted last by name was used, and '-' sorts
after '+': in 24 recorded real games a planeswalker that offered a plus and a minus ability took
the minus one 83 times of 83, Quintorius for -4 ("Spirits you control gain double strike") with no
Spirit on the table 43 times in 63 uses. These tests pin the valuation of the abilities of one
offer and that a minus ability that buys nothing is not put up.
"""

from __future__ import annotations

import random
from typing import Any

from commander_lab.agents import GenericCommanderPilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.engine.rules.full_game_pilot_walkers import (
    LOYALTY_FLOOR,
    choose_loyalty_ability,
    loyalty_option_value,
    parse_loyalty_label,
)
from commander_lab.models import PilotConfig, PilotStrength

_PASS = {"option_id": "pass", "label": "Pass priority", "option_type": "pass_priority"}
_EM_DASH = chr(0x2014)
_MINUS_SIGN = chr(0x2212)

_QUINTORIUS = "Quintorius, History Chaser"
_QUINTORIUS_PLUS = "You may discard a card. If you do, draw two cards, then mill a card."
_QUINTORIUS_MINUS = "Spirits you control gain double strike and vigilance until end of turn."
_CHANDRA = "Chandra, Torch of Defiance"
_CHANDRA_PLUS = "Exile the top card of your library. You may cast that card. If you don't, {this} deals 2 damage to each opponent."
_CHANDRA_MINUS = "{this} deals 4 damage to target creature."


def _permanent(
    object_id: str, name: str, power: int = 0, toughness: int = 0, **extra: Any
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "name": name,
        "tapped": False,
        "power": power,
        "toughness": toughness,
        "damage": 0,
        **extra,
    }


def _walker(object_id: str, name: str, loyalty: int) -> dict[str, Any]:
    return _permanent(object_id, name, counters=[{"type": "loyalty", "count": loyalty}])


def _state(
    *,
    board: list[dict[str, Any]],
    opposing: list[dict[str, Any]] | None = None,
    phase: str = "precombat_main",
) -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "is_actor": True,
        "seat": 0,
        "life": 40,
        "hand_count": 2,
        "library_count": 80,
        "graveyard_count": 0,
        "battlefield": board,
        "graveyard": [],
        "command": [],
        "hand": [],
        "mana_pool": {},
    }
    opponent = {
        "player_id": "opponent-1",
        "seat": 1,
        "life": 40,
        "hand_count": 7,
        "library_count": 90,
        "graveyard_count": 0,
        "battlefield": list(opposing or []),
        "graveyard": [],
        "command": [],
    }
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 6,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": phase,
        "step": phase,
        "players": [actor, opponent],
        "stack": [],
        "commander_status": [],
    }


def _ability(option_id: str, source: dict[str, Any], cost: str, text: str) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "label": f"{source['name']} {_EM_DASH} {cost}: {text}",
        "option_type": "activated_ability",
        "metadata": {
            "source_name": source["name"],
            "source_object_id": source["object_id"],
            "ability_type": "activated_nonmana",
        },
    }


def test_the_label_of_a_loyalty_ability_is_read() -> None:
    plus = parse_loyalty_label(f"{_QUINTORIUS} {_EM_DASH} +1: {_QUINTORIUS_PLUS}")
    assert plus is not None
    assert (plus.cost, plus.is_x) == (1, False)
    minus = parse_loyalty_label(f"{_QUINTORIUS} {_EM_DASH} -4: {_QUINTORIUS_MINUS}")
    assert minus is not None
    assert (minus.cost, minus.is_x, minus.text) == (-4, False, _QUINTORIUS_MINUS)
    printed_minus = parse_loyalty_label(f"{_CHANDRA} {_EM_DASH} {_MINUS_SIGN}3: {_CHANDRA_MINUS}")
    assert printed_minus is not None and printed_minus.cost == -3
    zero = parse_loyalty_label(f"{_CHANDRA} {_EM_DASH} 0: Draw a card.")
    assert zero is not None and zero.cost == 0
    variable = parse_loyalty_label(f"Ugin {_EM_DASH} {_MINUS_SIGN}X: Destroy each permanent.")
    assert variable is not None and (variable.cost, variable.is_x) == (0, True)


def test_a_mana_ability_and_a_land_play_are_no_loyalty_abilities() -> None:
    assert parse_loyalty_label(f"Sol Ring {_EM_DASH} {{T}}: Add {{C}}{{C}}.") is None
    assert parse_loyalty_label(f"Mountain {_EM_DASH} Play Mountain") is None


def test_the_plus_ability_is_used_when_the_minus_one_has_nothing_to_act_on() -> None:
    walker = _walker("pw", _QUINTORIUS, 5)
    state = _state(board=[walker])
    options = [
        _ability("minus", walker, "-4", _QUINTORIUS_MINUS),
        _ability("plus", walker, "+1", _QUINTORIUS_PLUS),
    ]
    picks = {
        str(choose_loyalty_ability(options, state, random.Random(seed))["option_id"])  # type: ignore[index]
        for seed in range(12)
    }
    assert picks == {"plus"}
    minus_value = loyalty_option_value(options[0], state)
    assert minus_value is not None and minus_value < LOYALTY_FLOOR


def test_the_minus_ability_is_used_when_it_has_something_to_act_on() -> None:
    walker = _walker("pw", _CHANDRA, 4)
    state = _state(
        board=[walker],
        opposing=[_permanent("angel", "Serra Angel", 4, 4)],
    )
    options = [
        _ability("minus", walker, "-3", _CHANDRA_MINUS),
        _ability("plus", walker, "+1", _CHANDRA_PLUS),
    ]
    best = choose_loyalty_ability(options, state, random.Random(1))
    assert best is not None and best["option_id"] == "minus"


def test_the_plus_ability_is_used_when_the_minus_has_no_target() -> None:
    walker = _walker("pw", _CHANDRA, 4)
    state = _state(board=[walker])
    options = [
        _ability("minus", walker, "-3", _CHANDRA_MINUS),
        _ability("plus", walker, "+1", _CHANDRA_PLUS),
    ]
    best = choose_loyalty_ability(options, state, random.Random(1))
    assert best is not None and best["option_id"] == "plus"


def test_a_minus_ability_that_would_end_the_planeswalker_needs_more_than_a_small_effect() -> None:
    walker = _walker("pw", _CHANDRA, 3)
    state = _state(board=[walker], opposing=[_permanent("elf", "Llanowar Elves", 1, 1)])
    options = [
        _ability("minus", walker, "-3", _CHANDRA_MINUS),
        _ability("plus", walker, "+1", _CHANDRA_PLUS),
    ]
    best = choose_loyalty_ability(options, state, random.Random(1))
    assert best is not None and best["option_id"] == "plus"


def test_an_offer_without_a_loyalty_ability_is_left_alone() -> None:
    state = _state(board=[_permanent("sol", "Sol Ring")])
    options = [_PASS]
    assert choose_loyalty_ability(options, state, random.Random(1)) is None


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC)
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Quintorius, Loremaster",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20261025)  # type: ignore[arg-type]


def _request(options: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": "opaque-priority",
        "decision_offset": 1,
        "actor_id": "actor",
        "decision_class": "priority",
        "pilot_state": state,
        "context": {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": options,
        "prompt": "priority",
    }


def test_the_pilot_uses_the_plus_ability_of_a_planeswalker_with_nothing_to_support() -> None:
    walker = _walker("pw", _QUINTORIUS, 5)
    state = _state(board=[walker])
    options = [
        _PASS,
        _ability("minus", walker, "-4", _QUINTORIUS_MINUS),
        _ability("plus", walker, "+1", _QUINTORIUS_PLUS),
    ]
    response = _policy().decide(_request(options, state))
    assert response["selected_option_ids"] == ["plus"]


def test_the_pilot_does_not_put_up_a_minus_ability_that_buys_nothing() -> None:
    walker = _walker("pw", _QUINTORIUS, 5)
    state = _state(board=[walker])
    options = [_PASS, _ability("minus", walker, "-4", _QUINTORIUS_MINUS)]
    response = _policy().decide(_request(options, state))
    assert response["selected_option_ids"] == ["pass"]


def test_the_pilot_uses_the_removal_ability_when_a_creature_is_worth_it() -> None:
    walker = _walker("pw", _CHANDRA, 4)
    state = _state(board=[walker], opposing=[_permanent("angel", "Serra Angel", 4, 4)])
    options = [
        _PASS,
        _ability("minus", walker, "-3", _CHANDRA_MINUS),
        _ability("plus", walker, "+1", _CHANDRA_PLUS),
    ]
    response = _policy().decide(_request(options, state))
    assert response["selected_option_ids"] == ["minus"]


def test_a_damage_ability_is_not_counted_for_a_creature_it_cannot_kill() -> None:
    walker = _walker("pw", _CHANDRA, 4)
    state = _state(board=[walker], opposing=[_permanent("avatar", "Avatar of Woe", 6, 5)])
    options = [
        _ability("minus", walker, "-3", _CHANDRA_MINUS),
        _ability("plus", walker, "+1", _CHANDRA_PLUS),
    ]
    best = choose_loyalty_ability(options, state, random.Random(1))
    assert best is not None and best["option_id"] == "plus"
