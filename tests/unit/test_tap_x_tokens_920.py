"""Full-game pilot: an X paid by tapping X untapped tokens (#920).

Plan seed 14, game seed 114, pod 004 of the precon sweep aborts on Hazel of the Rootbloom:
``{T}, Pay 2 life, Tap X untapped tokens you control: Add X mana in any combination of colors``.
That Hazel was itself a token (a copy), so the engine counted it among the untapped tokens it
offers as X's ceiling, and the ability's own ``{T}`` tapped it first. The tap cost found nothing
to tap, the mana ability was reversed and the game stopped.

The tokens are board-public and the cost is printed on the option and the prompt, so the pilot
keeps the announced X within the tokens that are there besides the source, and does not start
the ability when none is.
"""

from __future__ import annotations

from typing import Any

from commander_lab.engine.rules.full_game_pilot.common import option_x_tap_cap, x_tap_prompt_cap
from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)

HAZEL_ID = "hazel"
HAZEL_LABEL = (
    "Hazel of the Rootbloom — {T}, Pay 2 life, Tap X untapped tokens you control: "
    "Add X mana in any combination of colors."
)
TAP_X_PROMPT = "Announce the value for {X} (untapped tokens you control to tap)"


def _item(name: str, object_id: str, *, tapped: bool = False) -> dict[str, Any]:
    return {"object_id": object_id, "name": name, "tapped": tapped, "toughness": 2}


def _hazel() -> dict[str, Any]:
    item = _item("Hazel of the Rootbloom", HAZEL_ID)
    item["abilities"] = [
        "At the beginning of your end step, create a token that's a copy of target token you "
        "control.",
        "{T}, Pay 2 life, Tap X untapped tokens you control: Add X mana in any combination of "
        "colors.",
    ]
    return item


def _board(*extra: dict[str, Any]) -> list[dict[str, Any]]:
    return [_hazel(), *extra]


def _hazel_state(*extra: dict[str, Any]) -> dict[str, Any]:
    state = _state(step="precombat_main")
    state["players"][0]["battlefield"].extend(_board(*extra))
    return state


SERVO = _item("Servo Token", "servo")
TAPPED_SERVO = _item("Servo Token", "servo-tapped", tapped=True)
SQUIRREL = _item("Squirrel Token", "squirrel")


# --- the pure reading ---------------------------------------------------------


def test_the_prompt_cap_counts_untapped_tokens_besides_the_source() -> None:
    source = {"source_object_id": HAZEL_ID}
    assert x_tap_prompt_cap(TAP_X_PROMPT, source, _board(SERVO, SQUIRREL, TAPPED_SERVO)) == 2
    assert x_tap_prompt_cap(TAP_X_PROMPT, source, _board(TAPPED_SERVO)) == 0
    assert x_tap_prompt_cap(TAP_X_PROMPT, source, _board()) == 0


def test_a_source_that_is_a_token_is_not_one_of_its_own_tokens() -> None:
    # Hazel as a "Hazel of the Rootbloom Token" taps itself first.
    token_hazel = _hazel()
    token_hazel["name"] = "Hazel of the Rootbloom Token"
    assert x_tap_prompt_cap(TAP_X_PROMPT, {"source_object_id": HAZEL_ID}, [token_hazel]) == 0
    assert x_tap_prompt_cap(TAP_X_PROMPT, {"source_object_id": HAZEL_ID}, [token_hazel, SERVO]) == 1


def test_a_source_without_its_own_tap_counts_itself() -> None:
    battlefield = [_item("Some Token", "src"), SERVO]
    battlefield[0]["abilities"] = ["Tap X untapped tokens you control: Add X mana."]
    assert x_tap_prompt_cap(TAP_X_PROMPT, {"source_object_id": "src"}, battlefield) == 2


def test_other_prompts_read_as_no_cap() -> None:
    source = {"source_object_id": HAZEL_ID}
    battlefield = _board(SERVO)
    assert x_tap_prompt_cap("Announce the value for {X}", source, battlefield) is None
    assert (
        x_tap_prompt_cap(
            "Announce the value for {X} (untapped artifact creatures you control to tap)",
            source,
            battlefield,
        )
        is None
    )
    assert x_tap_prompt_cap(TAP_X_PROMPT, None, battlefield) is None
    assert x_tap_prompt_cap(TAP_X_PROMPT, source, None) is None
    assert x_tap_prompt_cap("", source, battlefield) is None


def test_the_option_cap_reads_tokens_too() -> None:
    metadata = {"source_object_id": HAZEL_ID}
    assert option_x_tap_cap(HAZEL_LABEL, metadata, _board(SERVO, TAPPED_SERVO)) == 1
    assert option_x_tap_cap(HAZEL_LABEL, metadata, _board()) == 0


# --- the announce -------------------------------------------------------------


def _announce(state: dict[str, Any], numeric_max: int) -> int:
    request = _request(
        "announce_x",
        [],
        context={"numeric_min": 0, "numeric_max": numeric_max, "outcome": "benefit"},
        prompt=TAP_X_PROMPT,
        state=state,
    )
    request["minimum_selections"] = 0
    request["maximum_selections"] = 0
    request["source_object"] = {
        "source_object_id": HAZEL_ID,
        "source_name": "Hazel of the Rootbloom",
        "ability_type": "activated_mana",
    }
    response = _policy().decide(request)
    chosen = response["numeric_choice"]
    assert isinstance(chosen, int)
    return chosen


def test_the_engine_counting_the_source_does_not_make_x_one() -> None:
    # The engine's ceiling is 1 because Hazel is a token herself; no other token is there.
    assert _announce(_hazel_state(), numeric_max=1) == 0


def test_x_is_the_tokens_to_tap_when_there_are_some() -> None:
    assert _announce(_hazel_state(SERVO, SQUIRREL), numeric_max=3) == 2


def test_x_stays_within_the_engines_ceiling() -> None:
    assert _announce(_hazel_state(SERVO, SQUIRREL), numeric_max=1) == 1


# --- the payment --------------------------------------------------------------


def _payment(state: dict[str, Any]) -> dict[str, Any]:
    hazel = _option(
        "hazel",
        "mana_ability",
        HAZEL_LABEL,
        source_name="Hazel of the Rootbloom",
        source_object_id=HAZEL_ID,
        ability_type="activated_mana",
        mana_ability=True,
        pool_covers_mana_cost=True,
        requires_tap_source=True,
        requires_untap_source=False,
        requires_sacrifice_source=False,
        source_tapped=False,
    )
    swamp = _option("swamp", "mana_ability", "Swamp — {T}: Add {B}.", source_name="Swamp")
    cancel = _option("cancel", "cancel_mana_payment", "Cancel mana payment")
    request = _request(
        "mana_payment",
        [cancel, hazel, swamp],
        context={"unpaid_mana": "{1}{G}"},
        prompt="{1}{G}",
        state=state,
    )
    request["source_object"] = {"source_name": "Squirrel Sovereign", "ability_type": "spell"}
    return request


def test_hazel_is_not_started_with_no_token_to_tap() -> None:
    # Two life paid for no mana, and the ability reversed when the source is a token itself.
    response = _policy().decide(_payment(_hazel_state()))
    assert response["selected_option_ids"] == ["swamp"]


def test_hazel_is_still_offered_with_a_token_to_tap() -> None:
    # Control: with a token besides Hazel the ability stays selectable (the choice between it
    # and a Swamp is the pilot's own).
    response = _policy().decide(_payment(_hazel_state(SERVO)))
    assert response["selected_option_ids"] in (["hazel"], ["swamp"])
