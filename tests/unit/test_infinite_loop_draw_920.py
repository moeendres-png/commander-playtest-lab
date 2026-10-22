"""Full-game pilot: the engine's "Draw game because of infinite looping?" ask is answered Yes (#920).

Plan seed 1, game seed 401, pod 017 of the precon sweep looped to the 50000-decision limit:
Flourishing Defenses ("Whenever a -1/-1 counter is put on a creature, you may create a 1/1 green
Elf Warrior creature token") against Blowfly Infestation, which put the next -1/-1 counter on the
new token. XMage asked the players every fifteen rounds whether the game is a draw because of
infinite looping, and the pilot declined each time while the stack grew to 199 abilities.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)

_LOOP_PROMPT = "Draw game because of infinite looping?"


def _loop_ask(prompt: str = _LOOP_PROMPT, offset: int = 1) -> dict[str, Any]:
    return _request(
        "choose_use",
        [
            _option("yes", "boolean", "Yes", value=True),
            _option("no", "boolean", "No", value=False),
        ],
        context={"outcome": "detriment"},
        prompt=prompt,
        offset=offset,
        state=_state(step="precombat_main"),
    )


def test_the_infinite_loop_draw_is_confirmed() -> None:
    assert _policy().decide(_loop_ask())["selected_option_ids"] == ["yes"]


def test_the_ask_is_confirmed_every_time_it_is_repeated() -> None:
    policy = _policy()
    answers = [
        policy.decide(_loop_ask(offset=offset))["selected_option_ids"][0] for offset in range(1, 4)
    ]
    assert answers == ["yes", "yes", "yes"]


def test_other_detriment_asks_keep_the_pilots_own_answer() -> None:
    # Control: an ordinary detriment may-prompt is not forced to Yes.
    response = _policy().decide(_loop_ask(prompt="Sacrifice a creature?"))
    assert response["selected_option_ids"] == ["no"]
