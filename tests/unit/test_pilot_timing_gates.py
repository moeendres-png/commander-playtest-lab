"""Phase 4a: instants and mana-costing abilities wait for their window.

Real games showed the pilot spending its mana as soon as it had priority: 59 % of its instants
were cast in its own upkeep or draw step (removal, charms, a Seething Song whose mana was lost),
and on opponents' turns removal went out in the upkeep. A window later in the same turn cycle is
always coming, so these options are withheld (the engine still offers them, passing is legal).
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.agents.card_knowledge import CardFacts, card_facts
from commander_lab.engine.rules.full_game_pilot_views import (
    _timing_withhold_reason,
    priority_view_fields,
)
from tests.unit.test_full_game_pilot_judgment import (
    _PASS,
    _card,
    _cast,
    _opponent_state,
    _policy,
    _request,
)

_TITAN = _card("titan", "Grave Titan", 6, 6)


def _at(state: dict[str, Any], *, own: bool, phase: str, step: str) -> dict[str, Any]:
    state.update(
        active_player_id="actor" if own else "opponent-1",
        phase=phase,
        step=step,
    )
    return state


def _swords() -> dict[str, Any]:
    return _cast("swords", "Swords to Plowshares", white=1)


def _reason(option: dict[str, Any], state: dict[str, Any]) -> str | None:
    return priority_view_fields(option, state)[1]


@pytest.mark.parametrize(
    ("phase", "step"),
    [("beginning", "upkeep"), ("beginning", "draw")],
)
def test_an_instant_is_not_cast_before_the_own_main_phase(phase: str, step: str) -> None:
    state = _at(_opponent_state({1: [_TITAN]}), own=True, phase=phase, step=step)
    assert _reason(_swords(), state) == "instant_before_own_main"
    response = _policy().decide(_request("priority", [_PASS, _swords()], state))
    assert response["selected_option_ids"] == ["pass"]


def test_the_same_instant_is_still_offered_in_the_own_main_phase() -> None:
    state = _opponent_state({1: [_TITAN]})
    assert _reason(_swords(), state) is None
    response = _policy().decide(_request("priority", [_PASS, _swords()], state))
    assert response["selected_option_ids"] == ["swords"]


@pytest.mark.parametrize(
    ("phase", "step"),
    [
        ("beginning", "upkeep"),
        ("beginning", "draw"),
        ("precombat_main", "precombat_main"),
        ("combat", "begin_combat"),
    ],
)
def test_removal_waits_on_an_opponents_turn_until_combat_or_the_end_step(
    phase: str, step: str
) -> None:
    state = _at(_opponent_state({1: [_TITAN]}), own=False, phase=phase, step=step)
    assert _reason(_swords(), state) == "instant_waits_for_combat_or_end_step"
    response = _policy().decide(_request("priority", [_PASS, _swords()], state))
    assert response["selected_option_ids"] == ["pass"]


@pytest.mark.parametrize(
    ("phase", "step"),
    [
        ("combat", "declare_attackers"),
        ("combat", "declare_blockers"),
        ("postcombat_main", "postcombat_main"),
        ("end", "end_turn"),
    ],
)
def test_removal_is_offered_once_attackers_are_declared_and_at_the_end(
    phase: str, step: str
) -> None:
    state = _at(_opponent_state({1: [_TITAN]}), own=False, phase=phase, step=step)
    assert _reason(_swords(), state) is None


def test_the_end_step_cast_still_goes_out() -> None:
    state = _at(_opponent_state({1: [_TITAN]}), own=False, phase="end", step="end_turn")
    response = _policy().decide(_request("priority", [_PASS, _swords()], state))
    assert response["selected_option_ids"] == ["swords"]


@pytest.mark.parametrize(
    ("own", "phase", "step"),
    [
        (True, "beginning", "upkeep"),
        (False, "beginning", "upkeep"),
        (False, "precombat_main", "precombat_main"),
    ],
)
def test_an_answer_to_something_on_the_stack_is_never_held(
    own: bool, phase: str, step: str
) -> None:
    state = _opponent_state({1: [_TITAN]}, stack=[{"object_id": "spell-1", "name": "Claim Jumper"}])
    _at(state, own=own, phase=phase, step=step)
    assert _reason(_swords(), state) is None


def test_a_flash_creature_waits_like_other_instants() -> None:
    viper = _cast("viper", "Ambush Viper", green=1, generic=1)
    state = _at(
        _opponent_state({1: [_TITAN]}), own=False, phase="precombat_main", step="precombat_main"
    )
    assert _reason(viper, state) == "instant_waits_for_combat_or_end_step"
    state = _at(_opponent_state({1: [_TITAN]}), own=False, phase="end", step="end_turn")
    assert _reason(viper, state) is None


def test_a_card_that_is_not_instant_speed_is_not_a_timing_matter() -> None:
    jumper = _cast("claim", "Claim Jumper", white=1, generic=2)
    state = _at(_opponent_state({}), own=True, phase="beginning", step="upkeep")
    assert _reason(jumper, state) is None


def _tutor() -> CardFacts:
    return CardFacts(
        name="Vampiric Tutor",
        mana_value=1.0,
        mana_cost="{B}",
        type_line="Instant",
        oracle_text=(
            "Search your library for a card, then shuffle and put that card on top. "
            "You lose 2 life."
        ),
        power=None,
        toughness=None,
        keywords=frozenset(),
        colors=frozenset({"B"}),
        color_identity=frozenset({"B"}),
        produced_mana=frozenset(),
    )


def test_a_tutor_to_the_top_is_cast_before_the_draw_step() -> None:
    state = _at(_opponent_state({}), own=True, phase="beginning", step="upkeep")
    assert _timing_withhold_reason(_tutor(), state) is None
    state = _at(_opponent_state({}), own=False, phase="beginning", step="upkeep")
    assert _timing_withhold_reason(_tutor(), state) == "instant_waits_for_combat_or_end_step"


def test_a_cantrip_that_only_looks_at_the_top_card_is_not_a_tutor() -> None:
    consider = card_facts("Consider")
    assert consider is not None
    state = _at(_opponent_state({}), own=True, phase="beginning", step="draw")
    assert _timing_withhold_reason(consider, state) == "instant_before_own_main"


def _ability(cost: dict[str, int]) -> dict[str, Any]:
    return {
        "option_id": "pump",
        "label": "Inferno Titan — {R}: {this} gets +1/+0 until end of turn.",
        "option_type": "activated_ability",
        "metadata": {
            "source_name": "Inferno Titan",
            "source_object_id": "titan-1",
            "ability_type": "activated_nonmana",
            **{f"mana_cost_{color}": value for color, value in cost.items()},
        },
    }


def test_an_ability_that_costs_mana_waits_for_the_own_main_phase() -> None:
    upkeep = _at(_opponent_state({}), own=True, phase="beginning", step="upkeep")
    assert _reason(_ability({"red": 1}), upkeep) == "ability_mana_cost_before_own_main"
    main = _opponent_state({})
    assert _reason(_ability({"red": 1}), main) is None


def test_an_ability_that_costs_no_mana_is_not_held() -> None:
    upkeep = _at(_opponent_state({}), own=True, phase="beginning", step="upkeep")
    assert _reason(_ability({"red": 0, "generic": 0}), upkeep) is None


def test_an_ability_on_an_opponents_turn_is_not_held() -> None:
    upkeep = _at(_opponent_state({}), own=False, phase="beginning", step="upkeep")
    assert _reason(_ability({"red": 1}), upkeep) is None


def test_an_ability_answering_the_stack_is_not_held() -> None:
    state = _opponent_state({}, stack=[{"object_id": "trigger-1", "name": "Upkeep trigger"}])
    _at(state, own=True, phase="beginning", step="upkeep")
    assert _reason(_ability({"red": 1}), state) is None
