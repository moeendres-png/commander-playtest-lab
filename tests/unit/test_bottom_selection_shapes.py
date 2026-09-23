"""Bottom-of-library selection shapes.

The bridge flags every native putCardsOnBottomOfLibrary path with
``bottom_of_library_selection``. Two shapes share it: London mulligan
(options are hand cards) and library bottom-ordering (e.g. Dig Through
Time: options are looked-at library cards, disjoint from hand). Only the
London shape may use opening-hand bottom valuation; library ordering
must rank the offered options.
"""

from __future__ import annotations

import random

import pytest

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in (1, 2):
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"test/seat-{seat}",
            strategy="generic",
            commander_names=("Test Commander",),
            config=PilotConfig(
                pilot_name="auto",
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(
            _RuntimePilot(binding=binding, pilot=build_pilot(binding.config, strategy="generic"))
        )
    return ExternalPilotDecisionPolicy(tuple(runtimes), scenario_seed=1)


def _request() -> dict:
    return {"context": {"bottom_of_library_selection": True, "outcome": "neutral"}}


def _state(hand_ids: list[str]) -> dict:
    return {
        "actor_id": "actor-1",
        "players": [
            {
                "player_id": "actor-1",
                "mana_pool": {},
                "hand": [
                    {"object_id": card_id, "name": f"Hand Card {index}"}
                    for index, card_id in enumerate(hand_ids)
                ],
            }
        ],
    }


def _option(card_id: str, name: str) -> dict:
    return {
        "option_id": card_id,
        "option_type": "choice",
        "label": name,
        "metadata": {"object_id": card_id, "name": name},
    }


def test_london_shape_uses_hand_bottom_valuation() -> None:
    policy = _policy()
    hand = ["hand-1", "hand-2", "hand-3"]
    options = [_option(card_id, f"Hand Card {index}") for index, card_id in enumerate(hand)]
    selected = policy._decide_targets(
        policy._pilots[1], _state(hand), _request(), options, 1, 1, random.Random(0)
    )
    assert len(selected) == 1
    assert selected[0] in hand


def test_library_shape_ranks_offered_options() -> None:
    """Dig Through Time shape: options are library cards, not hand cards."""
    policy = _policy()
    hand = ["hand-1", "hand-2"]
    options = [
        _option("lib-1", "Farewell"),
        _option("lib-2", "Port Town"),
        _option("lib-3", "Exotic Orchard"),
        _option("lib-4", "Island"),
        _option("lib-5", "Reliquary Tower"),
    ]
    selected = policy._decide_targets(
        policy._pilots[1], _state(hand), _request(), options, 1, 1, random.Random(0)
    )
    assert len(selected) == 1
    assert selected[0] in {option["option_id"] for option in options}
    assert selected[0] not in hand


def _mode_option(mode_id: str, label: str, targets_available: bool | None) -> dict:
    metadata: dict = {"mode_id": mode_id}
    if targets_available is not None:
        metadata["mode_targets_available"] = targets_available
    return {
        "option_id": mode_id,
        "option_type": "mode",
        "label": label,
        "metadata": metadata,
    }


def test_mode_prefers_targets_available() -> None:
    """Abrade shape: the targetless mode must not be selected when a
    viable mode is offered."""
    policy = _policy()
    options = [
        _mode_option("mode-damage", "deal 3 damage to target creature", False),
        _mode_option("mode-artifact", "destroy target artifact", True),
    ]
    selected = policy._decide_mode(
        policy._pilots[1], _state(["hand-1"]), options, random.Random(0)
    )
    assert selected == "mode-artifact"


def test_mode_unknown_flag_means_no_filtering() -> None:
    policy = _policy()
    options = [
        _mode_option("mode-a", "draw a card", None),
        _mode_option("mode-b", "create a token", None),
    ]
    selected = policy._decide_mode(
        policy._pilots[1], _state(["hand-1"]), options, random.Random(0)
    )
    assert selected in {"mode-a", "mode-b"}


def test_mode_all_targetless_still_chooses_offered() -> None:
    """No viable mode: pilot still chooses (bridge maps doom to pass)."""
    policy = _policy()
    options = [
        _mode_option("mode-a", "deal 3 damage to target creature", False),
        _mode_option("mode-b", "destroy target artifact", False),
    ]
    selected = policy._decide_mode(
        policy._pilots[1], _state(["hand-1"]), options, random.Random(0)
    )
    assert selected in {"mode-a", "mode-b"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
