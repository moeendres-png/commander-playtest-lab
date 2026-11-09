"""The pilot's ramp terms decay with the game round, not with the engine's turn counter.

The engine counts every player's turn, so in a four-player pod the raw counter is about four times
the number of turns the actor has taken. The ramp terms were spent by the actor's third turn
(Chulane baseline 2026-11-09: 21 % of ramp castable in the first five own turns never cast).
"""

from __future__ import annotations

import random

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.agents.pilots import _game_round
from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
)
from tests.unit.test_pilots import _action, _state

_CONFIG = PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)


def _components(turn: int, pod: int, roles: set[CardRole]) -> dict[str, float]:
    state = _state(turn=turn).model_copy(update={"pod_size": pod})
    action = _action("a", "Some Spell", cost=2, roles=roles)
    return GenericCommanderPilot(_CONFIG)._base_components(state, action)


@pytest.mark.parametrize(
    ("turn", "pod", "expected"),
    [(1, 4, 1), (4, 4, 1), (5, 4, 2), (14, 4, 4), (16, 4, 4), (17, 4, 5), (7, 2, 4), (9, 1, 9)],
)
def test_game_round_counts_rounds_of_the_pod(turn: int, pod: int, expected: int) -> None:
    state = _state(turn=turn).model_copy(update={"pod_size": pod})
    assert _game_round(state) == expected


def test_ramp_bonus_depends_on_the_round_not_on_the_seat_count() -> None:
    # Same round (4) in a one-seat and a four-seat pod: the same ramp terms.
    solo = _components(4, 1, {CardRole.RAMP})
    pod = _components(14, 4, {CardRole.RAMP})
    assert solo["mana_efficiency"] == pod["mana_efficiency"]
    assert solo["tempo"] == pod["tempo"]


def test_ramp_is_still_favoured_on_the_actors_fourth_turn_of_a_four_player_pod() -> None:
    # Own turn 4 is turn 14 of the engine counter. The raw counter had already spent the bonus.
    early = _components(14, 4, {CardRole.RAMP})
    plain = _components(14, 4, set())
    assert early["mana_efficiency"] > plain["mana_efficiency"] + 0.5
    assert early["tempo"] > plain["tempo"] + 0.5


def test_ramp_bonus_still_runs_out_in_the_late_game() -> None:
    # A card role with no turn-dependent term is the control: only the ramp terms differ.
    late = _components(80, 4, {CardRole.RAMP})
    control = _components(80, 4, {CardRole.DRAW})
    assert late["tempo"] == control["tempo"]
    assert 0.0 < late["mana_efficiency"] - control["mana_efficiency"] <= 0.2 + 1e-9


def test_a_spell_without_a_ramp_role_does_not_depend_on_the_turn() -> None:
    # Wrong-reason control: the change must not touch any other card.
    first = _components(2, 4, {CardRole.ENGINE})
    later = _components(60, 4, {CardRole.ENGINE})
    assert first["mana_efficiency"] == later["mana_efficiency"]
    assert first["tempo"] == later["tempo"]


def test_pilot_casts_the_ramp_spell_on_its_fourth_turn() -> None:
    pilot = GenericCommanderPilot(_CONFIG)
    ramp = _action("ramp", "Wood Elves", cost=3, roles={CardRole.RAMP}, immediate=0.7, floor=0.7)
    plain = _action("plain", "Plain Spell", cost=3, roles=set(), immediate=0.8, floor=0.8)
    early = _state(turn=14, mana=4.0).model_copy(update={"pod_size": 4})
    decision = pilot.choose_action(early, (ramp, plain), random.Random(7))
    assert decision.selected_action_id == "ramp"


def test_the_utility_of_a_ramp_spell_falls_with_the_rounds_and_a_plain_spells_does_not() -> None:
    pilot = GenericCommanderPilot(_CONFIG)
    ramp = _action("ramp", "Wood Elves", cost=3, roles={CardRole.RAMP}, immediate=0.7, floor=0.7)
    plain = _action("plain", "Plain Spell", cost=3, roles=set(), immediate=0.8, floor=0.8)

    def utility(action: PilotActionView, turn: int) -> float:
        state = _state(turn=turn, mana=4.0).model_copy(update={"pod_size": 4})
        return pilot.evaluate_action(state, action).total_utility

    assert utility(ramp, 2) > utility(ramp, 14) > utility(ramp, 40) > utility(ramp, 120)
    assert utility(plain, 2) == utility(plain, 120)
