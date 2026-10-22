"""Full-game pilot: counters a cast announced to remove are not spent as mana first.

Plan seed 29, game seed 29, pod 000 of the precon sweep aborts on Hierophant Bio-Titan
(``{10}{G}{G}``, "you may remove any number of +1/+1 counters ... this spell costs {2} less for
each"). The seat announced X = 3 counters to remove, paid the reduced ``{4}{G}{G}`` partly with
Haruspex's ``{T}, Remove X +1/+1 counters from {this}: Add X mana`` and was left with the two
counters of The Swarmlord for the cost. The cast was reversed, which stopped the game.

The announced counters are the cast's own cost: no mana ability removes them, and the seat takes
them from the biggest piles until the number is covered.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)

SEAT = 1
TITAN_ID = "bio-titan"
TITAN_LABEL = "Hierophant Bio-Titan — Cast Hierophant Bio-Titan"
ANNOUNCE_PROMPT = "Announce the value for {X} (+1/+1 counters to remove)"
HARUSPEX_LABEL = (
    "Haruspex — <i>Devouring Monster</i> &mdash; {T}, Remove X +1/+1 counters from {this}: "
    "Add X mana of any one color."
)


def _board(**piles: int) -> dict[str, Any]:
    state = _state(step="precombat_main")
    state["players"][0]["battlefield"].extend(
        {
            "object_id": name,
            "name": name.title(),
            "counters": [{"type": "+1/+1", "count": count}],
            "tapped": False,
        }
        for name, count in piles.items()
    )
    return state


def _casting() -> Any:
    """A policy whose seat chose the Titan's cast and announced X = 3 for it."""
    policy = _policy()
    policy._last_priority_label[SEAT] = TITAN_LABEL
    policy._last_priority_source[SEAT] = TITAN_ID
    policy._reserve_counters(SEAT, {"source_object_id": TITAN_ID}, ANNOUNCE_PROMPT, 3)
    return policy


def test_the_announced_counters_are_the_cost_the_seat_pays() -> None:
    assert _casting()._paying_counters(SEAT) == 3


def test_an_announce_for_another_source_does_not_reserve_the_casts_counters() -> None:
    # Haruspex's own "Remove X counters" announce comes in the middle of the Titan's payment.
    policy = _casting()
    policy._reserve_counters(SEAT, {"source_object_id": "haruspex"}, ANNOUNCE_PROMPT, 1)
    assert policy._paying_counters(SEAT) == 3


def test_x_announced_for_something_else_is_not_a_counter_cost() -> None:
    policy = _policy()
    policy._last_priority_label[SEAT] = "Walking Ballista — {4}: Put a +1/+1 counter"
    policy._last_priority_source[SEAT] = "ballista"
    policy._reserve_counters(
        SEAT, {"source_object_id": "ballista"}, "Announce the value for {X}", 3
    )
    assert policy._paying_counters(SEAT) is None


def test_a_mana_ability_that_removes_the_reserved_counters_is_not_used() -> None:
    forest = _option("forest", "mana_ability", "Forest — {T}: Add {G}.", source_name="Forest")
    haruspex = _option(
        "haruspex", "mana_ability", HARUSPEX_LABEL, source_name="Haruspex", source_object_id="h"
    )
    options = [haruspex, forest]
    policy = _casting()
    assert policy._spends_counters_the_cast_reserves(SEAT, haruspex)
    assert not policy._spends_counters_the_cast_reserves(SEAT, forest)
    response = policy.decide(
        _request("mana_payment", options, context={"unpaid_mana": "{4}"}, state=_board())
    )
    assert response["selected_option_ids"] == ["forest"]


def test_another_counter_kind_is_not_the_reserved_one() -> None:
    charge = _option(
        "charge",
        "mana_ability",
        "Gemstone Array — Remove a charge counter: Add one mana of any color.",
        source_name="Gemstone Array",
    )
    assert not _casting()._spends_counters_the_cast_reserves(SEAT, charge)


def test_without_a_reservation_the_mana_ability_stays_on_offer() -> None:
    haruspex = _option("haruspex", "mana_ability", HARUSPEX_LABEL, source_name="Haruspex")
    assert not _policy()._spends_counters_the_cast_reserves(SEAT, haruspex)


def test_the_reservation_ends_with_the_next_priority_window() -> None:
    policy = _casting()
    pass_priority = _option("pass", "pass_priority", "Pass priority")
    policy.decide(_request("priority", [pass_priority], state=_board(), offset=5))
    assert policy._paying_counters(SEAT) is None
    assert not policy._reserved_counters


def test_the_cost_takes_the_biggest_piles_until_the_number_is_covered() -> None:
    # The Swarmlord holds two, Haruspex one: both are needed for three.
    policy = _casting()
    state = _board(haruspex=1, swarmlord=2)
    options = [
        _option(name, "choice", name.title(), object_id=name, name=name.title())
        for name in ("haruspex", "swarmlord")
    ]

    def ask(remaining: list[dict[str, Any]], offset: int) -> list[str]:
        request = _request("choose_object", remaining, state=state, offset=offset)
        request["minimum_selections"] = 0
        request["maximum_selections"] = len(remaining)
        return list(policy.decide(request)["selected_option_ids"])

    assert ask(options, 2) == ["swarmlord"]
    assert ask([options[0]], 3) == ["haruspex"]
    assert ask([], 4) == []
