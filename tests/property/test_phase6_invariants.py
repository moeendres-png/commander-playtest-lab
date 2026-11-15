from __future__ import annotations

from commander_lab.engine import IllegalActionProposal, validate_action_proposal
from commander_lab.models import (
    ActionProposal,
    ActionType,
    GameState,
    GameStatus,
    LegalAction,
    PlayerState,
)


def test_illegal_actions_are_rejected_for_many_invalid_targets() -> None:
    legal = LegalAction(
        action_id="choose",
        actor_id="p1",
        action_type=ActionType.CHOOSE_TARGETS,
        allowed_target_ids=("p2", "p3"),
    )
    state = GameState(
        game_id="property-actions",
        seed=9,
        status=GameStatus.IN_PROGRESS,
        priority_player_id="p1",
        players=(
            PlayerState(player_id="p1", seat=0),
            PlayerState(player_id="p2", seat=1),
            PlayerState(player_id="p3", seat=2),
        ),
        legal_actions=(legal,),
    )
    for invalid_target in ("p1", "p4", "unknown", "card-99"):
        proposal = ActionProposal(
            proposal_id=f"bad-{invalid_target}",
            actor_id="p1",
            legal_action_id="choose",
            action_type=ActionType.CHOOSE_TARGETS,
            target_ids=(invalid_target,),
        )
        try:
            validate_action_proposal(state, proposal)
        except IllegalActionProposal:
            pass
        else:
            raise AssertionError(f"illegal target was accepted: {invalid_target}")
