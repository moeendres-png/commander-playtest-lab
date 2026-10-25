"""Guides as pilot weights: found by deck or commander, added to the generic weights, bounded."""

from __future__ import annotations

import pytest

from commander_lab.agents.deck_guides import DeckGuide, find_guide, guided_weights
from commander_lab.agents.pilots import generic_weights
from commander_lab.models.pilots import PilotStrength


def test_a_guide_is_found_by_its_deck_id() -> None:
    guide = find_guide("precon/2026/lorehold_spirit", ["something else"])
    assert guide is not None
    assert guide.commanders == {"Quintorius, History Chaser"}


def test_a_deck_with_its_own_id_is_found_by_its_commanders() -> None:
    guide = find_guide(
        "rogshai/current", ["Rograkh, Son of Rohgahh", "Ishai, Ojutai Dragonspeaker"]
    )
    assert guide is not None
    assert guide.deck_id == "custom/rogshai"


def test_a_deck_without_a_guide_has_none() -> None:
    assert find_guide("kaervek/current", ["Kaervek the Merciless"]) is None
    assert find_guide("nothing", []) is None


def test_the_deltas_are_added_to_the_generic_weights_of_the_strength() -> None:
    guide = DeckGuide("x", frozenset(), {"engine_development": 0.3, "tempo": -0.15})
    strengths = list(PilotStrength)
    assert strengths
    for strength in strengths:
        base = generic_weights(strength)
        guided = guided_weights(guide, strength)
        assert guided.engine_development == pytest.approx(base.engine_development + 0.3)
        assert guided.tempo == pytest.approx(base.tempo - 0.15)
        assert guided.survival == base.survival


def test_the_weights_stay_inside_their_bounds() -> None:
    guide = DeckGuide("x", frozenset(), {"survival": 9.0, "tempo": -9.0})
    guided = guided_weights(guide, PilotStrength.NEAR_OPTIMAL_HEURISTIC)
    assert guided.survival == 5.0
    assert guided.tempo == -5.0
