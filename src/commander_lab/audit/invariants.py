from __future__ import annotations

from collections import Counter
from typing import Iterable

from commander_lab.models import GameState, GameStatus


class StateInvariantError(ValueError):
    pass


def validate_game_state(state: GameState, *, expected_card_multisets: dict[str, Counter[str]] | None = None) -> None:
    players = {player.player_id: player for player in state.players}
    if state.priority_player_id is not None and players[state.priority_player_id].has_lost:
        raise StateInvariantError("an eliminated player cannot hold priority")
    if state.active_player_id is not None and players[state.active_player_id].has_lost:
        raise StateInvariantError("an eliminated player cannot be active")
    if state.status == GameStatus.COMPLETED and not state.winner_ids:
        raise StateInvariantError("completed game requires at least one winner")
    action_ids = [action.action_id for action in state.legal_actions]
    if len(action_ids) != len(set(action_ids)):
        raise StateInvariantError("legal action ids must be unique")
    for action in state.legal_actions:
        if action.actor_id not in players:
            raise StateInvariantError(f"legal action references unknown actor {action.actor_id}")
        if players[action.actor_id].has_lost:
            raise StateInvariantError("an eliminated player cannot receive legal actions")
        if action.allowed_target_ids and not set(action.target_ids).issubset(action.allowed_target_ids):
            raise StateInvariantError("legal action contains target outside allowed target set")
    for player in state.players:
        if any(value < 0 for value in player.commander_damage_received.values()):
            raise StateInvariantError("commander damage cannot be negative")
        if any(value < 0 for value in player.commander_cast_count.values()):
            raise StateInvariantError("commander cast count cannot be negative")
        if any(value < 0 for value in player.mana_pool.values()):
            raise StateInvariantError("mana pool cannot be negative")
        if player.has_lost and not player.loss_reason:
            raise StateInvariantError("eliminated player requires a loss reason")
        if expected_card_multisets is not None and player.player_id in expected_card_multisets:
            observed = Counter(
                (*player.zones.library, *player.zones.hand, *player.zones.battlefield,
                 *player.zones.graveyard, *player.zones.exile, *player.zones.command)
            )
            if observed != expected_card_multisets[player.player_id]:
                raise StateInvariantError(f"card multiset changed for {player.player_id}")
