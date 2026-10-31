"""A discard from the pilot's own hand gives up the card the hand values least.

Real games on the pinned engine: in 24 recorded games Quintorius, History Chaser's "Discard a card"
chose the alphabetically last card of the hand 146 times of 146, Faithless Looting and the
discard of Syphon Mind the same. All cards of a hand scored alike as targets, and the tie went to
the last label: Inferno Titan went when the hand also held Field of Ruin and Fact or Fiction.
These tests pin the ranking by the hand valuation (surplus lands first, then the cards the
hand needs least) and the controls that other outcomes and other zones keep the old ranking.
"""

from __future__ import annotations

from typing import Any

from commander_lab.agents.pilots import GenericCommanderPilot
from commander_lab.models import PilotActionView, PilotConfig, PilotStrength
from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)


def _discard_state(hand: list[str], lands_on_board: int) -> dict[str, Any]:
    state = _state(step="precombat_main")
    actor = state["players"][0]
    actor["battlefield"] = [
        {"object_id": f"land-{index}", "name": "Plains", "tapped": False}
        for index in range(lands_on_board)
    ]
    actor["hand"] = [
        {"object_id": f"hand-{index}", "name": name} for index, name in enumerate(hand)
    ]
    actor["hand_count"] = len(hand)
    return state


def _discard(
    hand: list[str],
    lands_on_board: int,
    *,
    count: int = 1,
    outcome: str = "discard",
    zone: str = "hand",
    offset: int = 1,
) -> list[str]:
    """Names the pilot discards, from a frame shaped like the engine's discard choice."""
    options = [
        _option(
            f"hand-{index}",
            "choice",
            name,
            name=name,
            object_id=f"hand-{index}",
            zone=zone,
            zone_index=index,
        )
        for index, name in enumerate(hand)
    ]
    request = _request(
        "choose_object",
        options,
        context={"outcome": outcome},
        state=_discard_state(hand, lands_on_board),
        prompt="Select a card to discard",
        offset=offset,
    )
    request["minimum_selections"] = count
    request["maximum_selections"] = count
    response = _policy().decide(request)
    by_id = {option["option_id"]: option["label"] for option in options}
    return sorted(by_id[option_id] for option_id in response["selected_option_ids"])


def test_the_surplus_land_goes_before_a_spell_that_sorts_last() -> None:
    # Five lands on the table and a sixth in hand: the land is the surplus. By name the
    # last of the two is Savannah Lions, which the old ranking discarded.
    assert _discard(["Plains", "Savannah Lions"], lands_on_board=5) == ["Plains"]


def test_a_land_is_kept_while_the_board_is_short_of_lands() -> None:
    # Control for the land rule: with one land on the table the Plains is worth more than
    # a spell, so the spell goes.
    assert _discard(["Plains", "Savannah Lions"], lands_on_board=1) == ["Savannah Lions"]


def test_the_cheap_ramp_stays_over_a_vanilla_creature_that_sorts_earlier() -> None:
    # Sol Ring sorts after Savannah Lions, and the old ranking discarded it.
    assert _discard(["Savannah Lions", "Sol Ring"], lands_on_board=3) == ["Savannah Lions"]


def test_a_discard_of_two_takes_both_surplus_lands() -> None:
    # Faithless Looting: two cards. The land total shrinks as the hand does, but five lands on
    # the table keep both extra Plains surplus.
    hand = ["Plains", "Plains", "Sol Ring", "Savannah Lions"]
    assert _discard(hand, lands_on_board=5, count=2) == ["Plains", "Plains"]


def test_other_outcomes_keep_the_generic_ranking() -> None:
    # Control: the same hand under a neutral outcome is not a discard, so the hand valuation is
    # not used. The generic ranking scores both cards alike and the seeded rng of the decision
    # breaks the tie (it was the last label before the tie-break): both cards turn up, where the
    # hand valuation would give Plains every time.
    picks = {
        tuple(_discard(["Plains", "Savannah Lions"], lands_on_board=5, outcome="neutral", offset=n))
        for n in range(1, 41)
    }
    assert picks == {("Plains",), ("Savannah Lions",)}


def test_cards_outside_the_hand_keep_the_generic_ranking() -> None:
    # Control: a "discard" outcome over cards that are not in the actor's hand is not ranked
    # by the hand valuation either.
    picks = {
        tuple(_discard(["Plains", "Savannah Lions"], lands_on_board=5, zone="graveyard", offset=n))
        for n in range(1, 41)
    }
    assert picks == {("Plains",), ("Savannah Lions",)}


def test_the_hand_valuation_does_not_depend_on_the_rng() -> None:
    picks = {
        tuple(_discard(["Plains", "Savannah Lions"], lands_on_board=5, offset=n))
        for n in range(1, 41)
    }
    assert picks == {("Plains",)}


def _view(name: str, mana_cost: float, *, land: bool) -> PilotActionView:
    return PilotActionView(
        action_id=name,
        action_kind="card",
        card_name=name,
        mana_cost=mana_cost,
        floor_value=0.5,
        immediate_impact=0.3,
        metadata={"is_land": land},
    )


def test_extra_lands_outside_the_offered_cards_count_into_the_land_total() -> None:
    pilot = GenericCommanderPilot(
        PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC)
    )
    views = [_view("Plains", 0.0, land=True), _view("Grizzly Bears", 2.0, land=False)]
    # Offered alone, the single land is the first land of the hand: it is kept.
    assert pilot.choose_bottom_cards(views, 1, commander_names=()) == ("Grizzly Bears",)
    # With five more lands elsewhere it is surplus.
    assert pilot.choose_bottom_cards(views, 1, commander_names=(), extra_lands=5) == ("Plains",)
