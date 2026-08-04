from __future__ import annotations

from commander_lab.models import ActionProposal, GameState, LegalAction


class IllegalActionProposal(ValueError):
    """Raised when a proposed action does not match an engine-offered legal action."""


def validate_action_proposal(state: GameState, proposal: ActionProposal) -> LegalAction:
    """Resolve and strictly validate an agent proposal against ``state.legal_actions``.

    Agents may describe only one of the exact legal actions supplied by the engine.  The
    returned ``LegalAction`` remains the authority; the proposal cannot add targets,
    modes, sources, or choices that were not exposed by that action.
    """

    player = next((item for item in state.players if item.player_id == proposal.actor_id), None)
    if player is None:
        raise IllegalActionProposal(f"unknown actor: {proposal.actor_id}")
    if player.has_lost:
        raise IllegalActionProposal(f"eliminated player cannot act: {proposal.actor_id}")
    if state.priority_player_id is not None and proposal.actor_id != state.priority_player_id:
        raise IllegalActionProposal(
            f"actor {proposal.actor_id} does not have priority; priority belongs to "
            f"{state.priority_player_id}"
        )

    candidates = tuple(
        action
        for action in state.legal_actions
        if action.actor_id == proposal.actor_id
        and action.action_type == proposal.action_type
        and (proposal.legal_action_id is None or action.action_id == proposal.legal_action_id)
    )
    if proposal.source_object_id is not None:
        candidates = tuple(
            action for action in candidates if action.source_object_id == proposal.source_object_id
        )
    if len(candidates) != 1:
        raise IllegalActionProposal(
            "proposal must identify exactly one engine-offered legal action"
        )
    legal = candidates[0]

    if proposal.source_object_id not in {None, legal.source_object_id}:
        raise IllegalActionProposal("proposal source differs from legal action source")
    if proposal.target_ids and not set(proposal.target_ids).issubset(set(legal.allowed_target_ids)):
        raise IllegalActionProposal("proposal contains a target not allowed by the legal action")
    if proposal.selected_modes and not set(proposal.selected_modes).issubset(set(legal.modes)):
        raise IllegalActionProposal("proposal contains a mode not allowed by the legal action")

    required = set(legal.choices_schema.get("required", ()))
    missing = required - set(proposal.choices)
    if missing:
        raise IllegalActionProposal(f"proposal is missing required choices: {sorted(missing)}")
    allowed_choice_keys = set(legal.choices_schema.get("properties", {}))
    if allowed_choice_keys and not set(proposal.choices).issubset(allowed_choice_keys):
        raise IllegalActionProposal("proposal contains choices outside the legal schema")
    return legal
