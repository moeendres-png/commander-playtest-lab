"""Full-game pilot: mana for a {T} ability is not made by tapping that ability's source (#920).

Plan seed 15, game seed 115, pod 026 of the precon sweep aborts on Alchemist's Refuge:
``{G}{U}, {T}: You may cast spells this turn as though they had flash``. The pilot paid part of
the {G}{U} by tapping the Refuge for {C}. The mana cost is paid first, so the ability's own
``{T}`` found its source tapped, the activation was reversed and the game stopped.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)

REFUGE_FLASH_LABEL = (
    "Alchemist's Refuge — {G}{U}, {T}: You may cast spells this turn as though they had flash."
)
REFUGE_MANA_LABEL = "Alchemist's Refuge — {T}: Add {C}."


def _chose_at_priority(
    policy: Any, label: str, source_id: str, *, ability_type: str = "activated_nonmana"
) -> None:
    chosen = _option(
        "chosen",
        "activated_ability",
        label,
        source_name=label.split(" — ", 1)[0],
        source_object_id=source_id,
        ability_type=ability_type,
    )
    policy._remember_own_cast(1, [chosen], ["chosen"], turn=3)


def _refuge_payment(payer_id: str = "refuge") -> dict[str, Any]:
    state = _state(step="precombat_main")
    state["players"][0]["battlefield"].append(
        {"object_id": "refuge", "name": "Alchemist's Refuge", "tapped": False}
    )
    refuge = _option(
        "refuge-mana",
        "mana_ability",
        REFUGE_MANA_LABEL,
        source_name="Alchemist's Refuge",
        source_object_id="refuge",
        ability_type="activated_mana",
        mana_ability=True,
        pool_covers_mana_cost=True,
        requires_tap_source=True,
        requires_untap_source=False,
        requires_sacrifice_source=False,
        source_tapped=False,
    )
    cancel = _option("cancel", "cancel_mana_payment", "Cancel mana payment")
    request = _request(
        "mana_payment",
        [cancel, refuge],
        context={"unpaid_mana": "{1}"},
        prompt="{1}",
        state=state,
    )
    request["source_object"] = {"source_object_id": payer_id, "ability_type": "activated_nonmana"}
    return request


def test_a_tap_ability_is_not_paid_with_its_own_source() -> None:
    policy = _policy()
    _chose_at_priority(policy, REFUGE_FLASH_LABEL, "refuge")
    response = policy.decide(_refuge_payment())
    assert response["selected_option_ids"] == ["cancel"]


def test_another_permanents_ability_may_tap_the_refuge_for_mana() -> None:
    # Control: the payer is a different source, so the Refuge's mana is fair game.
    policy = _policy()
    _chose_at_priority(policy, "Mystic Forge — {T}: Look at the top card.", "forge")
    response = policy.decide(_refuge_payment(payer_id="forge"))
    assert response["selected_option_ids"] == ["refuge-mana"]


def test_an_ability_that_does_not_tap_its_source_may_use_the_source_for_mana() -> None:
    # Control: no {T} in the cost, so tapping the source for mana first costs nothing.
    policy = _policy()
    _chose_at_priority(policy, "Alchemist's Refuge — {2}: Scry 1.", "refuge")
    response = policy.decide(_refuge_payment())
    assert response["selected_option_ids"] == ["refuge-mana"]


def test_the_next_priority_decision_forgets_the_activation() -> None:
    policy = _policy()
    _chose_at_priority(policy, REFUGE_FLASH_LABEL, "refuge")
    assert policy._last_priority_source[1] == "refuge"
    pass_option = _option("pass", "pass_priority", "Pass priority")
    state = _state(step="precombat_main")
    policy.decide(_request("priority", [pass_option], state=state))
    assert 1 not in policy._last_priority_source
