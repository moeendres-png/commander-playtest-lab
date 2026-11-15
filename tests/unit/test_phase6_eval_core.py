from __future__ import annotations

import pytest

from commander_lab.engine import IllegalActionProposal, validate_action_proposal
from commander_lab.engine.structural import commander_cast_cost, commander_damage_is_lethal
from commander_lab.models import (
    ActionProposal,
    ActionType,
    GameState,
    GameStatus,
    LegalAction,
    PlayerState,
)


def test_commander_tax_progression() -> None:
    assert [commander_cast_cost(5, casts) for casts in range(4)] == [5, 7, 9, 11]
    with pytest.raises(ValueError):
        commander_cast_cost(5, -1)


def test_commander_damage_is_separate_by_commander() -> None:
    assert not commander_damage_is_lethal({"Ishai": 12, "Rograkh": 10})
    assert commander_damage_is_lethal({"Ishai": 21, "Rograkh": 0})
    assert commander_damage_is_lethal([0, 24])


def test_action_proposal_must_match_one_legal_action() -> None:
    legal = LegalAction(
        action_id="cast-1",
        actor_id="p1",
        action_type=ActionType.CAST_SPELL,
        source_object_id="card-1",
        allowed_target_ids=("p2",),
        modes=("destroy",),
        choices_schema={"required": ["x"], "properties": {"x": {"type": "integer"}}},
    )
    state = GameState(
        game_id="g",
        seed=1,
        status=GameStatus.IN_PROGRESS,
        priority_player_id="p1",
        players=(PlayerState(player_id="p1", seat=0), PlayerState(player_id="p2", seat=1)),
        legal_actions=(legal,),
    )
    proposal = ActionProposal(
        proposal_id="p",
        actor_id="p1",
        legal_action_id="cast-1",
        action_type=ActionType.CAST_SPELL,
        source_object_id="card-1",
        target_ids=("p2",),
        selected_modes=("destroy",),
        choices={"x": 2},
    )
    assert validate_action_proposal(state, proposal) == legal

    with pytest.raises(IllegalActionProposal):
        validate_action_proposal(
            state,
            proposal.model_copy(update={"target_ids": ("p1",)}),
        )
    with pytest.raises(IllegalActionProposal):
        validate_action_proposal(
            state,
            proposal.model_copy(update={"actor_id": "p2"}),
        )
