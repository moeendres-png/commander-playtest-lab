from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from commander_lab.models import CardRole, StructuralCardProfile


def test_profile_snapshot_is_valid_and_complete(repo_root, structural_profiles) -> None:
    raw = json.loads(
        (repo_root / "data/cards/structural_role_profiles.json").read_text(encoding="utf-8")
    )
    assert raw["estimate_type"] == "structural_model_estimates"
    assert raw["profile_count"] == 195
    assert len(structural_profiles.profiles) == 195
    assert all(profile.roles for profile in structural_profiles.profiles)


def test_current_decks_have_complete_role_coverage(structural_decks) -> None:
    deck = structural_decks["rogshai/current"]
    assert len(deck.cards) == 100
    assert all(card.roles for card in deck.cards)
    assert sum(card.is_land for card in deck.cards) == 36


def test_multiple_roles_and_structural_dimensions_are_present(structural_profiles) -> None:
    korvold = structural_profiles.resolve("Korvold, Fae-Cursed King")
    assert {CardRole.DRAW, CardRole.ENGINE, CardRole.PAYOFF}.issubset(korvold.roles)
    assert korvold.commander_synergy > 0
    assert 0 <= korvold.turn_cycle_risk <= 1
    assert korvold.multiplayer_scaling >= 0


def test_strength_for_absent_role_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StructuralCardProfile(
            oracle_name="Invalid",
            roles=frozenset({CardRole.DRAW}),
            role_strengths={CardRole.RAMP: 1.0},
        )
