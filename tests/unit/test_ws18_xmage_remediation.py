from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import FullGameProtocolError, _RuntimePilot
from commander_lab.engine.rules.full_game_ws18 import (
    DynamicExternalPilotDecisionPolicy,
    FullGamePilotBindingV2,
    SUPPORTED_PLAYER_COUNTS,
)
from commander_lab.models import PilotConfig


XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
DECK_HASH = "0" * 64


def _scenario(player_count: int, *, seat: int = 1) -> FutureXmageScenario:
    opponent_ids = tuple(f"opponent-{index}" for index in range(1, player_count))
    return FutureXmageScenario(
        candidate_id="candidate",
        deck_hash=DECK_HASH,
        opponent_deck_ids=opponent_ids,
        player_count=player_count,
        seat=seat,
        scenario_id=f"ws18-{player_count}p",
        seed=424242,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="ws18",
        pilot_identity="test-pilot",
        pilot_version="1.0.0",
        decision_policy_version="1.0.0",
    )


def _binding(seat: int) -> FullGamePilotBindingV2:
    return FullGamePilotBindingV2(
        seat=seat,
        deck_id=f"deck-{seat}",
        strategy="generic",
        commander_names=(f"Commander {seat}",),
        config=PilotConfig(),
        pilot_identity="test-pilot",
        pilot_version="1.0.0",
        decision_policy_version="1.0.0",
    )


def _runtime(seat: int) -> _RuntimePilot:
    return _RuntimePilot(binding=_binding(seat), pilot=SimpleNamespace())


@pytest.mark.parametrize("player_count", SUPPORTED_PLAYER_COUNTS)
def test_future_xmage_scenario_accepts_technical_2p_through_5p(player_count: int) -> None:
    scenario = _scenario(player_count)
    assert scenario.player_count == player_count
    assert len(scenario.opponent_deck_ids) == player_count - 1


@pytest.mark.parametrize("player_count", (1, 6))
def test_future_xmage_scenario_rejects_out_of_scope_player_count(player_count: int) -> None:
    with pytest.raises(ValidationError):
        _scenario(player_count)


def test_future_xmage_scenario_rejects_wrong_opponent_count() -> None:
    with pytest.raises(ValidationError, match="player_count - 1"):
        FutureXmageScenario(
            candidate_id="candidate",
            deck_hash=DECK_HASH,
            opponent_deck_ids=("only-one",),
            player_count=4,
            seat=1,
            scenario_id="bad-opponents",
            seed=1,
            xmage_commit=XMAGE_COMMIT,
            bridge_version="ws18",
            pilot_identity="test-pilot",
            pilot_version="1.0.0",
            decision_policy_version="1.0.0",
        )


def test_future_xmage_scenario_rejects_seat_outside_dynamic_pod() -> None:
    with pytest.raises(ValidationError, match="seat cannot exceed"):
        _scenario(2, seat=3)


@pytest.mark.parametrize("player_count", SUPPORTED_PLAYER_COUNTS)
def test_dynamic_policy_requires_exact_contiguous_seat_cover(player_count: int) -> None:
    policy = DynamicExternalPilotDecisionPolicy(
        tuple(_runtime(seat) for seat in range(1, player_count + 1)),
        scenario_seed=424242,
    )
    assert set(policy._pilots) == set(range(1, player_count + 1))


def test_dynamic_policy_rejects_missing_seat_instead_of_falling_back() -> None:
    with pytest.raises(ValueError, match="cover seats"):
        DynamicExternalPilotDecisionPolicy((_runtime(1), _runtime(3)), scenario_seed=1)


def test_dynamic_policy_rejects_unsupported_discretionary_class_fail_closed() -> None:
    policy = DynamicExternalPilotDecisionPolicy((_runtime(1), _runtime(2)), scenario_seed=1)
    with pytest.raises(FullGameProtocolError, match="unsupported discretionary decision class"):
        policy.decide(
            {
                "decision_id": "d1",
                "actor_id": "actor",
                "decision_class": "future_unknown_decision",
            }
        )


def test_dynamic_policy_builds_valid_five_player_state_for_seat_five() -> None:
    runtimes = tuple(_runtime(seat) for seat in range(1, 6))
    policy = DynamicExternalPilotDecisionPolicy(runtimes, scenario_seed=424242)
    state = {
        "actor_id": "player-5",
        "player_count": 5,
        "turn_number": 1,
        "players": [
            {
                "player_id": f"player-{seat}",
                "life": 40,
                "hand_count": 7,
                "graveyard_count": 0,
                "battlefield": [],
                "hand": [] if seat == 5 else None,
                "mana_pool": {},
                "command": [],
            }
            for seat in range(1, 6)
        ],
    }

    view = policy._pilot_state(runtimes[4], state)

    assert view.seat_position == 5
    assert view.pod_size == 5
    assert len(view.opponents) == 4
    assert view.opponents_to_act_before_next_turn == 4


def test_four_player_scope_remains_explicitly_supported() -> None:
    assert 4 in SUPPORTED_PLAYER_COUNTS
    scenario = _scenario(4)
    assert scenario.player_count == 4
    assert len(scenario.opponent_deck_ids) == 3
