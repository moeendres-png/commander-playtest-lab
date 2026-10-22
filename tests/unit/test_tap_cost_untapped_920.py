"""Full-game pilot: "Tap an artifact you control" is not answered with a tapped permanent (#920).

Plan seed 19, game seed 119, pod 013 of the precon sweep aborts on Necron Overlord's
``{X}, {T}, Tap an artifact you control``. The mana was paid with the Sceptre of Eternal Glory
first, and the engine still listed the Sceptre (and the Overlord, tapped by its own {T}) among
the artifacts to tap. The pilot picked the Sceptre, the tap cost failed and the activation was
reversed, which stopped the game.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)

OVERLORD_ID = "overlord"


def _artifact(object_id: str, name: str, zone_index: int) -> dict[str, Any]:
    return _option(
        object_id,
        "choice",
        name,
        object_id=object_id,
        name=name,
        zone="battlefield",
        zone_index=zone_index,
    )


def _tap_request(
    options: list[dict[str, Any]],
    *,
    tapped: tuple[str, ...],
    outcome: str = "tap",
    minimum: int = 1,
) -> dict[str, Any]:
    state = _state(step="precombat_main")
    state["players"][0]["battlefield"].extend(
        {
            "object_id": option["option_id"],
            "name": option["label"],
            "tapped": option["option_id"] in tapped,
        }
        for option in options
    )
    request = _request(
        "choose_object",
        options,
        context={
            "targeted": False,
            "outcome": outcome,
            "target_description": "an artifact you control",
            "required": False,
        },
        prompt="Select an artifact you control",
        state=state,
    )
    request["minimum_selections"] = minimum
    request["source_object"] = {
        "source_object_id": OVERLORD_ID,
        "source_name": "Necron Overlord",
        "ability_type": "activated_nonmana",
    }
    return request


SCEPTRE = _artifact("sceptre", "Sceptre of Eternal Glory", 8)
OVERLORD = _artifact(OVERLORD_ID, "Necron Overlord", 37)
ATLAS = _artifact("atlas", "Endless Atlas", 13)
ARCHIVE = _artifact("archive", "Hedron Archive", 36)


def test_a_tapped_artifact_is_not_tapped_again() -> None:
    # The Sceptre paid the mana and the Overlord paid its {T}: both are tapped.
    request = _tap_request([SCEPTRE, OVERLORD, ATLAS, ARCHIVE], tapped=("sceptre", OVERLORD_ID))
    response = _policy().decide(request)
    assert response["selected_option_ids"][0] in {"atlas", "archive"}


def test_untapped_artifacts_are_all_still_on_offer() -> None:
    # Control: with nothing tapped the filter changes nothing.
    request = _tap_request([SCEPTRE, ATLAS, ARCHIVE], tapped=())
    response = _policy().decide(request)
    assert response["selected_option_ids"][0] in {"sceptre", "atlas", "archive"}


def test_the_choice_is_not_emptied_when_every_option_is_tapped() -> None:
    request = _tap_request([SCEPTRE, OVERLORD], tapped=("sceptre", OVERLORD_ID))
    response = _policy().decide(request)
    assert response["selected_option_ids"]


def test_the_minimum_is_kept_when_too_few_untapped_are_left() -> None:
    request = _tap_request([SCEPTRE, OVERLORD, ATLAS], tapped=("sceptre", OVERLORD_ID), minimum=2)
    request["maximum_selections"] = 2
    response = _policy().decide(request)
    assert len(response["selected_option_ids"]) == 2


def test_other_outcomes_do_not_filter_tapped_permanents() -> None:
    # A sacrifice is as legal for a tapped permanent as for an untapped one.
    request = _tap_request([SCEPTRE, ATLAS], tapped=("sceptre",), outcome="sacrifice")
    response = _policy().decide(request)
    assert response["selected_option_ids"]
