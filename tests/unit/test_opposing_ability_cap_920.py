"""Full-game pilot: an ability of an opponent's permanent is put up once a turn (#920).

Plan seed 2, game seed 202, pod 037 of the precon sweep ends in three engine NullPointerExceptions
on Capricopian ("{2}: Put a +1/+1 counter on Capricopian, then you may reselect which player it is
attacking. Only the player it is attacking may activate this ability"). The attacked player is the
only one who can activate it, and the pilot did so with the first activation still on the stack.
The engine's ``getDefenderId`` then returns null (the creature is evidently out of combat after
the first resolution) and reaches a ``PlayerIdPredicate``. The ability serves the attacker as much as the
activator, so the pilot uses an opponent's ability once a turn.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)

CAPRICOPIAN_LABEL = (
    "Capricopian — {2}: Put a +1/+1 counter on {this}, then you may reselect which player "
    "{this} is attacking. Only the player {this} is attacking may activate this ability and "
    "only during the declare attackers step."
)


def _declare_attackers_state(*, mine: bool) -> dict[str, Any]:
    state = _state(step="declare_attackers", pool_white=2)
    capricopian = {"object_id": "capricopian", "name": "Capricopian", "tapped": True}
    owner = state["players"][0] if mine else state["players"][1]
    owner["battlefield"].append(capricopian)
    return state


def _priority(state: dict[str, Any]) -> dict[str, Any]:
    activate = _option(
        "activate",
        "activated_ability",
        CAPRICOPIAN_LABEL,
        ability_type="activated_nonmana",
        source_name="Capricopian",
        source_object_id="capricopian",
        mana_cost_generic=2,
        pool_covers_mana_cost=True,
    )
    pass_option = _option("pass", "pass_priority", "Pass priority")
    return _request("priority", [pass_option, activate], state=state)


def _activations(mine: bool, rounds: int = 3) -> list[str]:
    policy = _policy()
    state = _declare_attackers_state(mine=mine)
    chosen = []
    for offset in range(rounds):
        request = _priority(state)
        request["decision_offset"] = offset + 1
        # An activation put on the stack changes the window the next decision sees.
        request["pilot_state"]["stack"] = [{"name": "Capricopian"}] * offset
        chosen.append(policy.decide(request)["selected_option_ids"][0])
    return chosen


def test_an_opponents_ability_is_activated_once_a_turn() -> None:
    chosen = _activations(mine=False)
    assert chosen.count("activate") <= 1


def test_the_pilot_does_use_the_ability_once() -> None:
    # Control: the cap does not take the ability away altogether.
    assert "activate" in _activations(mine=False)


def test_the_pilots_own_permanent_keeps_the_ordinary_cap() -> None:
    # Control: the same ability on the pilot's own permanent is not limited to one.
    assert _activations(mine=True).count("activate") > 1
