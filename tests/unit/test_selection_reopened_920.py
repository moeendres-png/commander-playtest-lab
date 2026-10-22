"""Full-game pilot: "Continue the selection" twice in a row ends the selection (#920).

Plan seed 6, game seed 206, pod 039 of the precon sweep ran into the 50000-decision limit on
Slaughter the Strong: after the pilot's picks no creature fit the remaining total power, so the
engine skipped the pick and asked "End the selection" or "Continue the selection" again, and the
pilot answered "Continue" every time. A Continue that is followed by the same ask, with no pick in
between, has nothing left to continue.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)


def _selection_ask(offset: int) -> dict[str, Any]:
    request = _request(
        "choose_use",
        [
            _option("end", "boolean", "End the selection", value=True),
            _option("continue", "boolean", "Continue the selection", value=False),
        ],
        context={"outcome": "detriment", "secondary_prompt": "Selected: "},
        prompt="Creature selection",
        offset=offset,
        state=_state(step="precombat_main"),
    )
    request["source_object"] = {
        "source_object_id": "spell",
        "ability_original_id": "slaughter-the-strong",
        "ability_type": "spell",
        "source_name": "Slaughter the Strong",
    }
    return request


def _answers(count: int) -> list[str]:
    policy = _policy()
    return [
        policy.decide(_selection_ask(offset))["selected_option_ids"][0]
        for offset in range(1, count + 1)
    ]


def test_continue_is_never_answered_forever() -> None:
    answers = _answers(6)
    assert "end" in answers


def test_a_continue_is_followed_by_the_end() -> None:
    answers = _answers(6)
    assert all(
        not (first == "continue" and second == "continue") for first, second in pairwise(answers)
    )


def test_the_first_ask_keeps_the_pilots_own_answer() -> None:
    # Control: with no Continue just answered, the ask is an ordinary may-prompt.
    assert _answers(1) == ["continue"]


def test_a_pick_between_two_asks_clears_the_reopening() -> None:
    policy = _policy()
    assert policy.decide(_selection_ask(1))["selected_option_ids"] == ["continue"]
    pick = _request(
        "target",
        [
            _option(
                "creature-0", "target", "Grizzly Bears", object_id="creature-0", zone="battlefield"
            )
        ],
        context={"targeted": True, "outcome": "boostcreature"},
        prompt="Select a creature you control (selected 0) (selected power 0 of 4)",
        state=_state(step="precombat_main"),
        offset=2,
    )
    pick["minimum_selections"] = 0
    policy.decide(pick)
    assert policy.decide(_selection_ask(3))["selected_option_ids"] == ["continue"]
