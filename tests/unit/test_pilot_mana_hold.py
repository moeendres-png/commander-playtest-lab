"""A seat that holds a counterspell or removal in hand keeps the mana for it (#989 phase 4a-2).

The pilot spent everything it could in its own main phase: in 24 recorded real games it held such
an instant at 660 passes of its own main phase and had too little mana left for it at 468, and no
instant was cast in an opponent's end step. These tests pin the card reading (which instants hold
mana), the board reading (what counts as a plan of the turn), the withheld cast and the run
limit, and the controls: a thin board, the commander, mana, wipes, a cost reducer, a board the
model cannot read, an instant that has no use, and an instant that is not payable anyway are all
left alone.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from commander_lab.engine.rules.full_game_pilot_mana_hold import (
    HeldInstant,
    held_instants,
    holds_in_a_row,
    is_plan_of_the_turn,
    own_main_phase,
    thin_board,
)
from tests.unit.test_full_game_pilot_mana_and_may import _option, _policy, _request, _state

_PLAINS = "{T}: Add {W}."


def _entry(object_id: str, name: str, *, creature: bool = True, power: int = 2) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "object_id": object_id,
        "name": name,
        "tapped": False,
        "damage": 0,
        "abilities": [],
    }
    if creature:
        entry.update(power=power, toughness=power)
    return entry


def _board(
    plains: int,
    hand: list[str],
    *,
    own: int = 2,
    opposing: int = 1,
    opponent_cards: int = 7,
    extra: list[dict[str, Any]] | None = None,
    turn: int = 5,
) -> Any:
    """The actor holds ``hand``, ``plains`` untapped Plains and ``own`` creatures on its main."""
    state = copy.deepcopy(_state(step="precombat_main"))
    state["turn_number"] = turn
    actor = state["players"][0]
    actor["battlefield"] = (
        [
            {
                "object_id": f"plains-{index}",
                "name": "Plains",
                "tapped": False,
                "abilities": [_PLAINS],
            }
            for index in range(plains)
        ]
        + [_entry(f"mine-{index}", "Grizzly Bears") for index in range(own)]
        + list(extra or [])
    )
    actor["hand"] = [
        {"object_id": f"hand-{index}", "name": name} for index, name in enumerate(hand)
    ]
    actor["hand_count"] = len(hand)
    for opponent in state["players"][1:]:
        opponent["hand_count"] = opponent_cards
        opponent["battlefield"] = []
    state["players"][1]["battlefield"] = [
        _entry(f"theirs-{index}", "Hill Giant", power=3) for index in range(opposing)
    ]
    return state


def _cast(name: str, object_id: str = "spell-1") -> dict[str, Any]:
    return _option(
        f"cast-{name}",
        "activated_ability",
        f"{name} — Cast {name}",
        ability_type="spell",
        source_name=name,
        source_object_id=object_id,
    )


_SERRA = _cast("Serra Angel")
_SWORDS = ["Swords to Plowshares"]


def _breaking(state: Any, option: dict[str, Any] = _SERRA, policy: Any = None) -> bool:
    found = (policy or _policy())._casts_that_break_the_mana_hold([option], state, 1)
    return bool(found)


def test_only_counterspells_and_removal_that_have_a_use_hold_mana() -> None:
    hand = [
        "Swords to Plowshares",
        "Counterspell",
        "Brainstorm",
        "Fact or Fiction",
        "Wrath of God",
        "Heroic Intervention",
        "Brineborn Cutthroat",
    ]
    held = held_instants(_board(6, hand), "actor")
    assert held == (
        HeldInstant("Swords to Plowshares", "removal"),
        HeldInstant("Counterspell", "counter"),
    )


def test_removal_holds_mana_only_while_an_opposing_permanent_can_be_hit() -> None:
    state = _board(6, ["Swords to Plowshares", "Counterspell"], opposing=0)
    assert held_instants(state, "actor") == (HeldInstant("Counterspell", "counter"),)


def test_a_counterspell_holds_mana_only_while_an_opponent_has_cards() -> None:
    state = _board(6, ["Swords to Plowshares", "Counterspell"], opponent_cards=0)
    assert held_instants(state, "actor") == (HeldInstant("Swords to Plowshares", "removal"),)


@pytest.mark.parametrize(
    ("record", "turn", "expected"),
    [
        (None, 9, 0),
        ((1, 5), 9, 1),  # held on the previous own turn of a four-seat table
        ((2, 5), 9, 2),
        ((2, 5), 5, 1),  # the same turn: the run before it
        ((2, 5), 13, 0),  # a turn in between without a hold ended the run
        ((3, 9), 9, 2),
    ],
)
def test_holds_in_a_row_counts_own_turns_one_after_the_other(
    record: tuple[int, int] | None, turn: int, expected: int
) -> None:
    assert holds_in_a_row(record, turn, 4) == expected


def test_the_board_readings() -> None:
    state = _board(5, _SWORDS, own=1)
    assert thin_board(state, "actor")
    assert not thin_board(_board(5, _SWORDS, own=2), "actor")
    assert own_main_phase(state)
    state["stack"] = [{"name": "Counterspell", "object_id": "x"}]
    assert not own_main_phase(state)


def test_the_plan_of_the_turn_is_never_held_back() -> None:
    state = _board(5, _SWORDS)
    state["players"][0]["command"] = [{"object_id": "cmdr-1", "name": "Isamaru, Hound of Konda"}]
    assert is_plan_of_the_turn(state, "actor", "Isamaru, Hound of Konda", "cmdr-1")
    assert is_plan_of_the_turn(state, "actor", "Sol Ring", "x")
    assert is_plan_of_the_turn(state, "actor", "Wrath of God", "x")
    assert is_plan_of_the_turn(state, "actor", "Swords to Plowshares", "x")
    assert is_plan_of_the_turn(state, "actor", "A Card Nobody Printed", "x")
    assert not is_plan_of_the_turn(state, "actor", "Serra Angel", "x")


def test_a_cast_that_would_spend_the_mana_held_for_removal_is_withheld() -> None:
    assert _breaking(_board(5, _SWORDS))


def test_the_cast_stays_when_the_mana_for_the_instant_is_left() -> None:
    assert not _breaking(_board(6, _SWORDS))


def test_a_held_instant_that_is_not_payable_holds_nothing() -> None:
    # Counterspell needs {U}{U}: no blue source, nothing to keep.
    assert not _breaking(_board(5, ["Counterspell"]))


def test_a_thin_board_develops_first() -> None:
    assert not _breaking(_board(5, _SWORDS, own=1))


def test_the_commander_is_not_held_back() -> None:
    state = _board(5, _SWORDS)
    state["players"][0]["command"] = [{"object_id": "serra-cmdr", "name": "Serra Angel"}]
    assert not _breaking(state, _cast("Serra Angel", "serra-cmdr"))


@pytest.mark.parametrize("name", ["Sol Ring", "Wrath of God"])
def test_mana_and_wipes_are_not_held_back(name: str) -> None:
    assert not _breaking(_board(1, _SWORDS), _cast(name))


def test_an_instant_is_left_to_the_timing_rules() -> None:
    assert not _breaking(_board(1, _SWORDS), _cast("Heroic Intervention"))


def test_an_x_spell_is_not_judged() -> None:
    assert not _breaking(_board(1, _SWORDS), _cast("Hydroid Krasis"))


def test_a_board_with_a_cost_reducer_is_not_judged() -> None:
    reducer = {
        "object_id": "helm",
        "name": "Helm of Awakening",
        "tapped": False,
        "abilities": ["Spells cost {1} less to cast."],
    }
    assert not _breaking(_board(5, _SWORDS, extra=[reducer]))


def test_a_board_the_model_cannot_read_is_not_judged() -> None:
    mystery = {"object_id": "odd", "name": "Mystery", "tapped": False}
    assert not _breaking(_board(5, _SWORDS, extra=[mystery]))


def test_no_instant_in_hand_changes_nothing() -> None:
    assert not _breaking(_board(5, ["Brainstorm"]))


def test_other_options_are_left_alone() -> None:
    ability = _option(
        "ability",
        "activated_ability",
        "Serra Angel",
        ability_type="activated_nonmana",
        source_name="Serra Angel",
    )
    assert not _breaking(_board(5, _SWORDS), ability)


def test_the_seat_develops_after_two_turns_of_holding_mana_back() -> None:
    policy = _policy()
    for turn in (5, 9):
        state = _board(5, _SWORDS, turn=turn)
        assert _breaking(state, policy=policy)
        policy._note_mana_hold(1, state)
    # Two own turns in a row held: the third develops.
    assert not _breaking(_board(5, _SWORDS, turn=13), policy=policy)
    # The turn after that starts a new run.
    assert _breaking(_board(5, _SWORDS, turn=17), policy=policy)


def test_the_same_turn_counts_once() -> None:
    policy = _policy()
    state = _board(5, _SWORDS, turn=5)
    for _ in range(4):
        assert _breaking(state, policy=policy)
        policy._note_mana_hold(1, state)
    assert policy._mana_hold[1] == (1, 5)


def _priority_answer(state: Any) -> str:
    pass_option = _option("pass", "pass_priority", "Pass priority")
    request = _request("priority", [_SERRA, pass_option], state=state, prompt="Priority")
    return str(_policy().decide(request)["selected_option_ids"][0])


def test_the_pilot_passes_instead_of_spending_the_mana_held_for_its_removal() -> None:
    assert _priority_answer(_board(5, _SWORDS)) == "pass"


def test_the_pilot_casts_it_when_the_mana_for_the_instant_is_left() -> None:
    assert _priority_answer(_board(6, _SWORDS)) == _SERRA["option_id"]
