from __future__ import annotations

import pytest

from commander_lab.engine import IllegalActionProposal, validate_action_proposal
from commander_lab.models import (
    ActionProposal,
    ActionType,
    GameState,
    GameStatus,
    LegalAction,
    PlayerState,
)


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
