"""Guard the Owner's permanent maximum of six simulator players (2026-11-08).

Schema-only tests: admission != successful XMage six-player runtime qualification.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import XmageFullGameRunner


def _scenario(player_count: int) -> FutureXmageScenario:
    return FutureXmageScenario(
        candidate_id="cap-regression",
        deck_hash="a" * 64,
        opponent_deck_ids=tuple(f"opponent-{index}" for index in range(1, player_count)),
        player_count=player_count,
        seat=1,
        scenario_id=f"cap-regression-{player_count}",
        seed=7,
        xmage_commit="b" * 40,
        bridge_version="test",
        pilot_identity="test",
        pilot_version="test",
        decision_policy_version="test",
    )


def test_hard_full_game_maximum_is_six() -> None:
    assert XmageFullGameRunner.MIN_PLAYERS == 2
    assert XmageFullGameRunner.MAX_PLAYERS == 6
    # This validates schema admission only, not a complete six-player game.
    assert _scenario(6).player_count == 6


@pytest.mark.parametrize("player_count", [7, 8, 10])
def test_new_operational_scenarios_refuse_seven_or_more(player_count: int) -> None:
    with pytest.raises(ValidationError):
        _scenario(player_count)
