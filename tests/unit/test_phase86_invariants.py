from __future__ import annotations

from collections import Counter

import pytest

from commander_lab.audit.invariants import StateInvariantError, validate_game_state
from commander_lab.models import GameState, GameStatus, PlayerState, ZoneState


def test_invariants_reject_eliminated_priority_player() -> None:
    state = GameState(
        game_id="g",
        seed=1,
        status=GameStatus.IN_PROGRESS,
        priority_player_id="p1",
        players=(PlayerState(player_id="p1", seat=0, has_lost=True, loss_reason="life"),),
    )
    with pytest.raises(StateInvariantError, match="priority"):
        validate_game_state(state)


def test_invariants_detect_card_multiset_change() -> None:
    state = GameState(
        game_id="g",
        seed=1,
        status=GameStatus.IN_PROGRESS,
        players=(
            PlayerState(
                player_id="p1",
                seat=0,
                zones=ZoneState(library=("A",), hand=("B",), command=("C",)),
            ),
        ),
    )
    validate_game_state(state, expected_card_multisets={"p1": Counter(["A", "B", "C"])})
    with pytest.raises(StateInvariantError, match="multiset"):
        validate_game_state(state, expected_card_multisets={"p1": Counter(["A", "B"])})
