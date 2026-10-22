"""Full-game pilot: mana for a "tap untapped artifacts" ability keeps those artifacts (#920).

Plan seed 3, game seed 203, pod 026 of the precon sweep aborts on Trazyn the Infinite's
``{X}, {T}, Tap X untapped artifacts you control: Target opponent loses X life``. X was announced
as 1 for the one untapped artifact besides Trazyn, and the pilot then paid the {X} by tapping that
artifact (Sol Ring) for mana. The mana cost is paid first, so the tap cost found nothing to tap,
the activation was reversed and the game stopped.
"""

from __future__ import annotations

from typing import Any

from commander_lab.engine.rules.full_game_pilot.common import tap_cost_needs_permanent
from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)

TRAZYN_LABEL = (
    "Trazyn the Infinite — <i>Relentless March</i> &mdash; {X}, {T}, Tap X untapped artifacts you "
    "control: Target opponent loses X life."
)
ATLAS_LABEL = "Endless Atlas — {2}, {T}: Draw a card."
TAP_AN_ARTIFACT_LABEL = "Necron Overlord — {X}, {T}, Tap an artifact you control: Draw X cards."


def _item(name: str, object_id: str, *, tapped: bool = False) -> dict[str, Any]:
    return {"object_id": object_id, "name": name, "tapped": tapped}


TRAZYN = _item("Trazyn the Infinite", "trazyn")
SOL_RING = _item("Sol Ring", "sol-ring")
SPARE_ARTIFACT = _item("Mind Stone", "mind-stone")
TAPPED_ARTIFACT = _item("Arcane Signet", "signet", tapped=True)
SWAMP = _item("Swamp", "swamp")


# --- the pure reading ---------------------------------------------------------


def _needs(label: str, battlefield: list[dict[str, Any]], *, x: int | None = 1) -> bool:
    return tap_cost_needs_permanent(label, x, "trazyn", "sol-ring", battlefield)


def test_the_only_untapped_artifact_is_needed_for_x_of_one() -> None:
    assert _needs(TRAZYN_LABEL, [TRAZYN, SOL_RING, TAPPED_ARTIFACT, SWAMP])


def test_a_second_untapped_artifact_leaves_the_first_free() -> None:
    assert not _needs(TRAZYN_LABEL, [TRAZYN, SOL_RING, SPARE_ARTIFACT, SWAMP])


def test_x_of_two_needs_both_artifacts() -> None:
    battlefield = [TRAZYN, SOL_RING, SPARE_ARTIFACT]
    assert _needs(TRAZYN_LABEL, battlefield, x=2)
    assert not _needs(TRAZYN_LABEL, battlefield, x=1)


def test_a_source_that_is_not_an_artifact_is_never_needed() -> None:
    assert not tap_cost_needs_permanent(
        TRAZYN_LABEL, 1, "trazyn", "swamp", [TRAZYN, SOL_RING, SWAMP]
    )


def test_a_cost_the_board_cannot_cover_anyway_is_not_this_rules() -> None:
    assert not _needs(TRAZYN_LABEL, [TRAZYN, SOL_RING, TAPPED_ARTIFACT], x=2)


def test_tap_an_artifact_reads_as_one() -> None:
    assert _needs(TAP_AN_ARTIFACT_LABEL, [TRAZYN, SOL_RING])
    assert not _needs(TAP_AN_ARTIFACT_LABEL, [TRAZYN, SOL_RING, SPARE_ARTIFACT])


def test_an_ability_without_a_tap_cost_has_nothing_to_keep() -> None:
    assert not _needs(ATLAS_LABEL, [TRAZYN, SOL_RING])
    assert not _needs("", [TRAZYN, SOL_RING])


# --- the payment --------------------------------------------------------------


def _payment(battlefield: list[dict[str, Any]]) -> tuple[Any, dict[str, Any]]:
    policy = _policy()
    chosen = _option(
        "chosen",
        "activated_ability",
        TRAZYN_LABEL,
        source_name="Trazyn the Infinite",
        source_object_id="trazyn",
        ability_type="activated_nonmana",
    )
    policy._remember_own_cast(1, [chosen], ["chosen"], turn=3)
    policy._failed_x_announcements[1] = {"trazyn": 1}
    state = _state(step="precombat_main")
    state["players"][0]["battlefield"].extend(battlefield)
    sol_ring = _option(
        "sol-ring-mana",
        "mana_ability",
        "Sol Ring — {T}: Add {C}{C}.",
        source_name="Sol Ring",
        source_object_id="sol-ring",
        ability_type="activated_mana",
        mana_ability=True,
        pool_covers_mana_cost=True,
        requires_tap_source=True,
        requires_untap_source=False,
        requires_sacrifice_source=False,
        source_tapped=False,
    )
    swamp = _option(
        "swamp-mana",
        "mana_ability",
        "Swamp — {T}: Add {B}.",
        source_name="Swamp",
        source_object_id="swamp",
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
        [cancel, sol_ring, swamp],
        context={"unpaid_mana": "{1}"},
        prompt="{1}",
        state=state,
    )
    request["source_object"] = {"source_object_id": "trazyn", "ability_type": "activated_nonmana"}
    return policy, request


def test_the_artifact_the_tap_cost_needs_is_not_tapped_for_mana() -> None:
    policy, request = _payment([TRAZYN, SOL_RING, TAPPED_ARTIFACT, SWAMP])
    assert policy.decide(request)["selected_option_ids"] == ["swamp-mana"]


def test_a_spare_artifact_leaves_the_sol_ring_on_offer() -> None:
    # Control: with another untapped artifact the Sol Ring may pay (the choice between it and
    # the Swamp is the pilot's own).
    policy, request = _payment([TRAZYN, SOL_RING, SPARE_ARTIFACT, SWAMP])
    assert policy.decide(request)["selected_option_ids"] in (["sol-ring-mana"], ["swamp-mana"])
