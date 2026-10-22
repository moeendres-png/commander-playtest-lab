"""Full-game pilot: a Crew payment is made of the creatures that add power, and ends at the total.

Plan seed 30, game seed 30, pod 045 of the precon sweep aborts on The Prydwen's Crew 2. The
engine asks for one creature at a time ("(selected power S of N)") and ends the payment when none
is chosen. The pilot chose a creature at every ask: Rex, Cyber-Hound (power 0), Brotherhood Scribe
(-1), Sentinel Sarah Lyons (2) and Dr. Madison Li (0) came to a total of 1, the cost failed and the
activation was reversed, which stopped the game. Sarah Lyons alone had paid the Crew.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)

PRYDWEN_ID = "prydwen"


def _creature(object_id: str, name: str, zone_index: int) -> dict[str, Any]:
    return _option(
        object_id,
        "choice",
        name,
        object_id=object_id,
        name=name,
        zone="battlefield",
        zone_index=zone_index,
    )


REX = _creature("rex", "Rex, Cyber-Hound", 3)
SCRIBE = _creature("scribe", "Brotherhood Scribe", 4)
SARAH = _creature("sarah", "Sentinel Sarah Lyons", 5)
MADISON = _creature("madison", "Dr. Madison Li", 6)
POWERS = {"rex": 0, "scribe": -1, "sarah": 2, "madison": 0}


def _crew_request(
    options: list[dict[str, Any]],
    *,
    have: int,
    need: int = 2,
    powers: dict[str, int] | None = None,
    abilities: dict[str, list[str]] | None = None,
    minimum: int = 0,
) -> dict[str, Any]:
    state = _state(step="declare_attackers")
    state["players"][0]["battlefield"].extend(
        {
            "object_id": option["option_id"],
            "name": option["label"],
            "tapped": False,
            "power": (powers or POWERS)[option["option_id"]],
            "toughness": 3,
            "abilities": (abilities or {}).get(option["option_id"], []),
        }
        for option in options
    )
    request = _request(
        "choose_object",
        options,
        context={
            "targeted": False,
            "outcome": "tap",
            "target_description": "any number of other untapped creature you control",
            "target_name": "another untapped creature you control",
            "required": True,
        },
        prompt=(
            "Select another untapped creature you control "
            f"(selected {len(POWERS) - len(options)}) (selected power {have} of {need})"
        ),
        state=state,
    )
    request["minimum_selections"] = minimum
    request["maximum_selections"] = len(options)
    request["source_object"] = {
        "source_object_id": PRYDWEN_ID,
        "source_name": "The Prydwen, Steel Flagship",
        "ability_type": "activated_nonmana",
    }
    return request


def test_only_the_creature_that_adds_power_is_chosen() -> None:
    request = _crew_request([REX, SCRIBE, SARAH, MADISON], have=0)
    assert _policy().decide(request)["selected_option_ids"] == ["sarah"]


def test_no_creature_is_chosen_once_the_power_is_reached() -> None:
    # Sarah is tapped (2 of 2); tapping the Scribe (-1) now would take the total back to 1.
    request = _crew_request([REX, SCRIBE, MADISON], have=2)
    assert _policy().decide(request)["selected_option_ids"] == []


def test_the_total_is_built_from_several_creatures() -> None:
    powers = {"rex": 1, "scribe": 1, "sarah": 0, "madison": 1}
    request = _crew_request([REX, SCRIBE, SARAH, MADISON], have=0, need=3, powers=powers)
    assert _policy().decide(request)["selected_option_ids"][0] in {"rex", "scribe", "madison"}
    request = _crew_request([REX, SCRIBE, SARAH, MADISON], have=1, need=3, powers=powers)
    assert _policy().decide(request)["selected_option_ids"][0] in {"rex", "scribe", "madison"}


def test_a_creature_that_crews_by_toughness_stays_on_offer() -> None:
    powers = {"rex": 0, "scribe": -1, "sarah": 0, "madison": 0}
    abilities = {"sarah": ["Sentinel Sarah Lyons crews Vehicles using its toughness."]}
    request = _crew_request(
        [REX, SCRIBE, SARAH, MADISON], have=0, powers=powers, abilities=abilities
    )
    assert _policy().decide(request)["selected_option_ids"] == ["sarah"]


def test_the_choice_is_not_emptied_when_no_creature_adds_power() -> None:
    powers = {"rex": 0, "scribe": -1, "sarah": 0, "madison": 0}
    request = _crew_request([REX, SCRIBE, MADISON], have=0, powers=powers)
    assert _policy().decide(request)["selected_option_ids"]


def test_other_tap_choices_are_not_filtered_by_power() -> None:
    request = _crew_request([REX, SCRIBE, MADISON], have=0)
    request["prompt"] = "Select another untapped creature you control"
    assert _policy().decide(request)["selected_option_ids"]


def test_a_required_tap_is_not_ended_early() -> None:
    # "Tap an untapped creature you control" with a minimum keeps its choice.
    request = _crew_request([REX, SCRIBE, MADISON], have=2, minimum=1)
    assert len(_policy().decide(request)["selected_option_ids"]) == 1
