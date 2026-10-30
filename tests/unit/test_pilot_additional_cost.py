"""A spell with a mandatory extra mana cost is cast only where both prices can be paid (#1067).

Louisoix's Sacrifice ({U}, "sacrifice a legendary creature or pay {2}") was cast with one untapped
land: the {U} was paid, the {2} was asked, and the payment was cancelled (19 of the 29 cancelled
payments in 24 recorded real games). These tests pin the card reading, the withheld cast, and the
controls: a payable total, a hand that holds a card to reveal, a cost reducer, an optional cost
and a cast for another price are left alone.
"""

from __future__ import annotations

import copy
from typing import Any

from commander_lab.engine.rules.full_game_pilot_additional_cost import (
    AdditionalManaCost,
    additional_mana_cost,
    reveal_alternative_in_hand,
)
from tests.unit.test_full_game_pilot_mana_and_may import _option, _policy, _state

_ISLAND = "{T}: Add {U}."
_FOREST = "{T}: Add {G}."


def _board(
    lands: int,
    hand: list[str] | None = None,
    extra: list[dict[str, Any]] | None = None,
    ability: str = _ISLAND,
) -> Any:
    state = copy.deepcopy(_state(step="precombat_main"))
    actor = state["players"][0]
    actor["battlefield"] = [
        {"object_id": f"island-{i}", "name": "Island", "tapped": False, "abilities": [ability]}
        for i in range(lands)
    ] + list(extra or [])
    if hand is not None:
        actor["hand"] = [{"name": name, "object_id": f"hand-{i}"} for i, name in enumerate(hand)]
    return state


def _cast(name: str, label: str | None = None) -> dict[str, Any]:
    return _option(
        "cast",
        "activated_ability",
        label or f"{name} — Cast {name}",
        ability_type="spell",
        source_name=name,
    )


def _unpayable(state: Any, option: dict[str, Any]) -> bool:
    return bool(_policy()._extra_cost_cast_unpayable(option, state))


def test_the_extra_cost_is_read_from_the_card() -> None:
    assert additional_mana_cost("Louisoix's Sacrifice") == AdditionalManaCost("{2}")
    assert additional_mana_cost("Surtland Elementalist") == AdditionalManaCost("{2}", "giant")
    assert additional_mana_cost("Thunderherd Migration") == AdditionalManaCost("{1}", "dinosaur")
    # Other costs, other cards and an unknown card are not read.
    assert additional_mana_cost("Fling") is None
    assert additional_mana_cost("Lightning Bolt") is None
    assert additional_mana_cost("A Card Nobody Printed") is None
    assert additional_mana_cost("") is None


def test_a_cast_short_of_the_extra_mana_is_withheld() -> None:
    option = _cast("Louisoix's Sacrifice")
    assert _unpayable(_board(1), option)
    assert _unpayable(_board(2), option)


def test_a_cast_both_prices_pay_is_left_alone() -> None:
    assert not _unpayable(_board(3), _cast("Louisoix's Sacrifice"))


def test_a_cast_for_another_price_is_left_alone() -> None:
    option = _cast(
        "Louisoix's Sacrifice", "Louisoix's Sacrifice — Cast Louisoix's Sacrifice with flashback"
    )
    assert not _unpayable(_board(1), option)


def test_a_card_to_reveal_stands_in_for_the_mana() -> None:
    option = _cast("Thunderherd Migration")
    forests = {"ability": _FOREST}
    dinosaur = ["Thunderherd Migration", "Ghalta, Primal Hunger"]
    assert not _unpayable(_board(2, hand=dinosaur, **forests), option)
    assert _unpayable(_board(2, hand=["Thunderherd Migration", "Forest"], **forests), option)
    # Without a reported hand the model does not judge.
    unreported = _board(2, **forests)
    unreported["players"][0].pop("hand", None)
    assert not _unpayable(unreported, option)


def test_the_hand_reading_leaves_the_spell_itself_out() -> None:
    state = _board(1, hand=["Thunderherd Migration"])
    assert reveal_alternative_in_hand(state, "actor", "Thunderherd Migration", "dinosaur") is False


def test_a_cost_reducer_on_the_board_is_left_alone() -> None:
    reducer = {
        "object_id": "helm",
        "name": "Helm of Awakening",
        "tapped": False,
        "abilities": ["Spells cost {1} less to cast."],
    }
    assert not _unpayable(_board(1, extra=[reducer]), _cast("Louisoix's Sacrifice"))


def test_a_card_without_an_extra_cost_is_left_alone() -> None:
    assert not _unpayable(_board(0), _cast("Lightning Bolt"))


def test_a_loyalty_ability_that_adds_mana_is_no_source_of_a_payment() -> None:
    """Chandra's "+1: Add {R}{R}." paid for a Louisoix's Sacrifice that could not be paid (seed 22)."""
    chandra = {
        "object_id": "chandra",
        "name": "Chandra, Torch of Defiance",
        "tapped": False,
        "abilities": ["+1: Add {R}{R}.", "-3: Chandra deals 4 damage to target creature."],
    }
    option = _cast("Louisoix's Sacrifice")
    assert _unpayable(_board(1, extra=[chandra]), option)
    # A mana ability of a permanent still counts: the same board with a Mountain beside it.
    mountain = {
        "object_id": "mountain",
        "name": "Mountain",
        "tapped": False,
        "abilities": ["{T}: Add {R}."],
    }
    assert not _unpayable(_board(2, extra=[mountain]), option)
