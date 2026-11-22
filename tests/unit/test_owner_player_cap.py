"""Guard the simulator's seat maximum: six (Owner, 2026-11-08), eight for SIMULATE since #1672.

The Owner instructed on 2026-11-22 "ja kümmer dich drum, dass es halt geht und führe es auch ein
für die Simulationen" (register entry E17): seven and eight seats for simulations only; PLAY stays
at six (``launch.MAX_RELEASED_PLAY_SEATS``). Nine and more stay refused everywhere.

Schema-only tests: admission != successful XMage runtime qualification at any seat count.
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


def test_hard_full_game_maximum_is_eight() -> None:
    assert XmageFullGameRunner.MIN_PLAYERS == 2
    assert XmageFullGameRunner.MAX_PLAYERS == 8
    # This validates schema admission only, not a complete seven- or eight-player game.
    assert _scenario(6).player_count == 6
    assert _scenario(8).player_count == 8


def test_play_stays_at_six_seats() -> None:
    from commander_lab.studio import launch

    assert launch.MAX_RELEASED_PLAY_SEATS == 6
    assert launch.MAX_PARTIE_SEATS == 6


@pytest.mark.parametrize("player_count", [9, 10])
def test_new_operational_scenarios_refuse_nine_or_more(player_count: int) -> None:
    with pytest.raises(ValidationError):
        _scenario(player_count)
