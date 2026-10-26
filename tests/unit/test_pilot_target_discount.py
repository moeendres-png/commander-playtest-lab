"""A spell that costs less against the right target is cast where it can be paid (#989 phase 5c).

Bitter Downfall ({3}{B}) costs {3} less against a creature dealt damage this turn. The engine offers
the cast whenever the cheaper price is payable; the pilot then chose its target by value, took an
undamaged creature, and the payment asked for the full price: 62 of the 93 cancelled payments in 24
recorded real games. These tests pin the card reading, the board reading, the withheld cast and the
target restriction, and the controls that a payable full price, a board the model cannot read and
a board with a cost reducer are left alone.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from commander_lab.engine.rules.full_game_pilot_target_discount import (
    DamagedTargetDiscount,
    _reduced_cost,
    board_lowers_costs,
    damaged_opposing_creatures,
    damaged_target_discount,
)
from tests.unit.test_full_game_pilot_mana_and_may import _option, _policy, _request, _state

_SWAMP = "{T}: Add {B}."


def _creature(object_id: str, name: str, power: int, toughness: int, damage: int = 0) -> Any:
    return {
        "object_id": object_id,
        "name": name,
        "tapped": False,
        "power": power,
        "toughness": toughness,
        "damage": damage,
        "abilities": [],
    }


def _board(
    swamps: int, *opposing: dict[str, Any], own_extra: list[dict[str, Any]] | None = None
) -> Any:
    """A state: the actor holds ``swamps`` untapped Swamps, the first opponent the creatures."""
    state = copy.deepcopy(_state(step="precombat_main"))
    actor = state["players"][0]
    actor["battlefield"] = [
        {"object_id": f"swamp-{index}", "name": "Swamp", "tapped": False, "abilities": [_SWAMP]}
        for index in range(swamps)
    ] + list(own_extra or [])
    state["players"][1]["battlefield"] = list(opposing)
    return state


_CAST = _option(
    "cast",
    "activated_ability",
    "Bitter Downfall — Cast Bitter Downfall",
    ability_type="spell",
    source_name="Bitter Downfall",
)


def test_the_discount_is_read_from_the_card() -> None:
    assert damaged_target_discount("Bitter Downfall") == DamagedTargetDiscount("{3}{B}", "{B}")
    # Other conditions, other spells and an unknown card are not read.
    assert damaged_target_discount("Ephara's Dispersal") is None
    assert damaged_target_discount("Lightning Bolt") is None
    assert damaged_target_discount("A Card Nobody Printed") is None
    assert damaged_target_discount("") is None


@pytest.mark.parametrize(
    ("cost", "less", "expected"),
    [
        ("{3}{B}", 3, "{B}"),
        ("{3}{B}", 1, "{2}{B}"),
        ("{2}{U}", 2, "{U}"),
        ("{3}", 3, "{0}"),
        ("{1}", 5, "{0}"),
        ("{X}{R}", 1, "{X}{R}"),
        ("", 1, None),
    ],
)
def test_the_reduced_cost_takes_the_discount_off_the_generic_part(
    cost: str, less: int, expected: str | None
) -> None:
    assert _reduced_cost(cost, less) == expected


def test_only_damaged_creatures_of_opponents_count() -> None:
    state = _board(
        2,
        _creature("hurt", "Claim Jumper", 3, 3, damage=1),
        _creature("whole", "Faerie Mastermind", 1, 2),
        {"object_id": "land", "name": "Island", "tapped": False, "damage": 2, "abilities": []},
        own_extra=[_creature("mine", "Esior, Wardwing Familiar", 1, 3, damage=2)],
    )
    assert damaged_opposing_creatures(state, "actor") == {"hurt"}


def test_a_cost_reducer_on_the_actors_board_is_seen() -> None:
    reducer = {
        "object_id": "helm",
        "name": "Helm of Awakening",
        "tapped": False,
        "abilities": ["Spells cost {1} less to cast."],
    }
    assert board_lowers_costs(_board(2, own_extra=[reducer]), "actor")
    assert not board_lowers_costs(_board(2), "actor")


def _withheld(state: Any, option: dict[str, Any] = _CAST) -> bool:
    return bool(_policy()._discount_cast_without_target(option, state))


def test_a_cast_that_only_the_discount_pays_is_withheld_without_a_damaged_creature() -> None:
    assert _withheld(_board(2, _creature("whole", "Claim Jumper", 3, 3)))


def test_the_cast_stays_when_a_damaged_creature_can_give_the_discount() -> None:
    state = _board(2, _creature("hurt", "Claim Jumper", 3, 3, damage=1))
    assert not _withheld(state)


def test_the_cast_is_withheld_when_not_even_the_discounted_price_is_payable() -> None:
    state = _board(0, _creature("hurt", "Claim Jumper", 3, 3, damage=1))
    assert _withheld(state)


def test_a_cast_the_full_price_pays_is_left_alone() -> None:
    assert not _withheld(_board(4, _creature("whole", "Claim Jumper", 3, 3)))


def test_a_board_the_model_cannot_read_is_left_alone() -> None:
    mystery = {"object_id": "odd", "name": "Mystery", "tapped": False}
    state = _board(2, _creature("whole", "Claim Jumper", 3, 3), own_extra=[mystery])
    assert not _withheld(state)


def test_a_cost_reducer_on_the_board_leaves_the_cast_alone() -> None:
    reducer = {
        "object_id": "helm",
        "name": "Helm of Awakening",
        "tapped": False,
        "abilities": ["Spells cost {1} less to cast."],
    }
    state = _board(2, _creature("whole", "Claim Jumper", 3, 3), own_extra=[reducer])
    assert not _withheld(state)


def test_other_options_are_left_alone() -> None:
    state = _board(2, _creature("whole", "Claim Jumper", 3, 3))
    bolt = _option(
        "bolt",
        "activated_ability",
        "Cast Lightning Bolt",
        ability_type="spell",
        source_name="Lightning Bolt",
    )
    ability = _option(
        "ability",
        "activated_ability",
        "Bitter Downfall",
        ability_type="activated_nonmana",
        source_name="Bitter Downfall",
    )
    assert not _withheld(state, bolt)
    assert not _withheld(state, ability)


_SPELL = {
    "ability_type": "spell",
    "source_name": "Bitter Downfall",
    "source_object_id": "spell-on-stack",
    "ability_original_id": "ability",
}


def _pick(state: Any) -> str:
    options = [
        _option(
            f"t-{object_id}",
            "target",
            name,
            name=name,
            object_id=object_id,
            zone="battlefield",
            zone_index=index,
        )
        for index, (object_id, name) in enumerate(
            [("whole", "Faerie Mastermind"), ("hurt", "Claim Jumper"), ("big", "Kaervek")]
        )
    ]
    request = _request(
        "target",
        options,
        context={"outcome": "destroypermanent", "targeted": True},
        state=state,
        prompt="Select a creature",
    )
    request["source_object"] = dict(_SPELL)
    return str(_policy().decide(request)["selected_option_ids"][0])


def _creatures(*, hurt: int) -> list[dict[str, Any]]:
    return [
        _creature("whole", "Faerie Mastermind", 1, 2),
        _creature("hurt", "Claim Jumper", 2, 2, damage=hurt),
        _creature("big", "Kaervek", 7, 7),
    ]


def test_with_the_full_price_out_of_reach_the_target_is_the_damaged_creature() -> None:
    assert _pick(_board(2, *_creatures(hurt=1))) == "t-hurt"


def test_with_the_full_price_payable_the_target_is_chosen_as_before() -> None:
    state = _board(4, *_creatures(hurt=1))
    assert _pick(state) == _pick(_board(4, *_creatures(hurt=0)))


def test_without_a_damaged_creature_the_target_is_chosen_as_before() -> None:
    state = _board(2, *_creatures(hurt=0))
    assert _pick(state) == _pick(_board(4, *_creatures(hurt=0)))


def _priority_answer(state: Any) -> str:
    state["players"][0]["hand"] = [{"object_id": "downfall", "name": "Bitter Downfall"}]
    pass_option = _option("pass", "pass_priority", "Pass priority")
    request = _request("priority", [_CAST, pass_option], state=state, prompt="Priority")
    return str(_policy().decide(request)["selected_option_ids"][0])


def test_the_pilot_passes_instead_of_casting_a_spell_no_target_can_discount() -> None:
    assert _priority_answer(_board(2, _creature("whole", "Claim Jumper", 3, 3))) == "pass"


def test_the_pilot_casts_it_when_a_damaged_creature_gives_the_discount() -> None:
    state = _board(2, _creature("hurt", "Claim Jumper", 3, 3, damage=1))
    assert _priority_answer(state) == "cast"
