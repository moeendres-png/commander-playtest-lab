"""A cast that costs as much life as the pilot has left is not made (#989 phase 1).

Real pod, game seed 9: Deep Analysis ("Flashback—{1}{U}, Pay 3 life") was flashed back at 3 life,
the payment took the pilot to zero, and the engine failed the action instead of ending the game
for the pilot. The pilot passes instead; with one life more the cast is as before.
"""

from __future__ import annotations

from typing import Any

from commander_lab.engine.rules.full_game_pilot_views import priority_view_fields
from tests.unit.test_full_game_pilot_mana_and_may import _PASS, _option, _policy, _request, _state


def _state_with(life: int) -> dict[str, Any]:
    state = _state(step="precombat_main")
    actor = state["players"][0]
    actor["life"] = life
    actor["battlefield"] = [
        {
            "object_id": f"island-{index}",
            "name": "Island",
            "tapped": False,
            "abilities": ["{T}: Add {U}."],
        }
        for index in range(3)
    ]
    return state


def _cast(name: str, label: str) -> dict[str, Any]:
    return _option(
        "cast",
        "activated_ability",
        label,
        ability_type="spell",
        source_name=name,
        source_object_id=f"id-{name}",
        mana_cost_blue=1,
        mana_cost_generic=1,
        mana_cost_white=0,
        mana_cost_black=0,
        mana_cost_red=0,
        mana_cost_green=0,
        mana_cost_colorless=0,
    )


_FLASHBACK = "Deep Analysis — Flashback {1}{U}"


def _withheld(label: str, name: str, life: int) -> str | None:
    _fields, withhold = priority_view_fields(_cast(name, label), _state_with(life))
    return withhold


def test_a_flashback_that_costs_all_the_life_is_withheld() -> None:
    assert _withheld(_FLASHBACK, "Deep Analysis", 3) == "life_cost_would_kill_the_actor"
    assert _withheld(_FLASHBACK, "Deep Analysis", 2) == "life_cost_would_kill_the_actor"


def test_the_same_flashback_with_one_life_more_is_not_withheld() -> None:
    assert _withheld(_FLASHBACK, "Deep Analysis", 4) is None


def test_the_hard_cast_has_no_life_cost() -> None:
    # Control: the card's printed cast pays mana only; the flashback is the costly one.
    assert _withheld("Deep Analysis — Cast Deep Analysis", "Deep Analysis", 3) is None


def test_a_spell_without_a_life_cost_is_left_alone() -> None:
    assert _withheld("Divination — Cast Divination", "Divination", 1) is None


def test_the_priority_window_passes_instead_of_a_lethal_flashback() -> None:
    policy = _policy()
    request = _request(
        "priority", [_PASS, _cast("Deep Analysis", _FLASHBACK)], state=_state_with(3)
    )
    assert policy.decide(request)["selected_option_ids"] == ["pass"]
