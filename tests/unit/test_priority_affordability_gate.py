"""Affordability gate for priority activated abilities.

Covers the real-deck gate failure where the pilot selected a fetch
activation (``{1}, {T}, Sacrifice``) with an empty pool, spent its only
untapped land on the generic mana, and then failed activation on the
remaining tap cost. The pilot must withhold provably unaffordable
activations from its own selection while leaving engine-offered options
and unknown-cost options untouched.
"""

from __future__ import annotations

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


def _state(pool: dict) -> dict:
    return {
        "actor_id": "actor-1",
        "players": [{"player_id": "actor-1", "mana_pool": pool}],
    }


def _option(metadata: dict) -> dict:
    return {
        "option_id": "opt-fetch",
        "option_type": "activated_ability",
        "label": "Grixis Panorama fetch",
        "metadata": metadata,
    }


FETCH_METADATA = {
    "ability_type": "activated",
    "source_name": "Grixis Panorama",
    "mana_cost_generic": 1,
    "mana_cost_white": 0,
    "mana_cost_blue": 0,
    "mana_cost_black": 0,
    "mana_cost_red": 0,
    "mana_cost_green": 0,
    "mana_cost_colorless": 0,
    # Engine-native verdict (Mana.enough over the deciding player's pool).
    "pool_covers_mana_cost": False,
    "requires_tap_source": True,
    "requires_untap_source": False,
    "requires_sacrifice_source": True,
    "source_tapped": False,
}


def test_withholds_fetch_with_empty_pool() -> None:
    policy = _policy()
    state = _state({"white": 0, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 0})
    assert policy._priority_action_affordable(_option(dict(FETCH_METADATA)), state) is False


def test_allows_fetch_when_pool_covers_generic() -> None:
    policy = _policy()
    metadata = dict(FETCH_METADATA, pool_covers_mana_cost=True)
    state = _state({"white": 0, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 1})
    assert policy._priority_action_affordable(_option(metadata), state) is True


def test_withholds_tap_cost_on_tapped_source() -> None:
    policy = _policy()
    metadata = dict(
        FETCH_METADATA,
        mana_cost_generic=0,
        pool_covers_mana_cost=True,
        source_tapped=True,
    )
    state = _state({"white": 0, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 5})
    assert policy._priority_action_affordable(_option(metadata), state) is False


def test_unknown_cost_facts_mean_affordable() -> None:
    policy = _policy()
    state = _state({"white": 0, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 0})
    assert policy._priority_action_affordable(_option({}), state) is True
    assert (
        policy._priority_action_affordable(
            {"option_id": "x", "option_type": "activated_ability"}, state
        )
        is True
    )


def test_colored_shortfall_withheld() -> None:
    policy = _policy()
    metadata = dict(
        FETCH_METADATA,
        mana_cost_generic=0,
        mana_cost_blue=1,
        pool_covers_mana_cost=False,
    )
    state = _state({"white": 0, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 3})
    assert policy._priority_action_affordable(_option(metadata), state) is False


def test_costed_mana_ability_withheld_when_pool_empty() -> None:
    """Rakdos Signet ({1},{T}) with an empty pool must not be selected."""
    policy = _policy()
    metadata = dict(FETCH_METADATA, source_name="Rakdos Signet")
    state = _state({"white": 0, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 0})
    assert policy._priority_action_affordable(_option(metadata), state) is False


def test_pure_mana_ability_always_affordable() -> None:
    """Sol Ring ({T}: add mana) carries no mana cost: never gated."""
    policy = _policy()
    metadata = {
        "ability_type": "mana",
        "source_name": "Sol Ring",
        "mana_cost_generic": 0,
        "mana_cost_white": 0,
        "mana_cost_blue": 0,
        "mana_cost_black": 0,
        "mana_cost_red": 0,
        "mana_cost_green": 0,
        "mana_cost_colorless": 0,
        "pool_covers_mana_cost": True,
        "requires_tap_source": True,
        "requires_untap_source": False,
        "requires_sacrifice_source": False,
        "source_tapped": False,
    }
    state = _state({"white": 0, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 0})
    assert policy._priority_action_affordable(_option(metadata), state) is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
