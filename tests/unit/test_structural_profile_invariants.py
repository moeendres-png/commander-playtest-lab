from __future__ import annotations

import pytest
from pydantic import ValidationError

from commander_lab.models import CardRole, StructuralCardProfile, StructuralDeckProfile
from commander_lab.models.structural import validate_commander_deck_profile


def _card(name: str) -> StructuralCardProfile:
    return StructuralCardProfile(
        oracle_name=name,
        mana_value=1.0,
        roles=frozenset({CardRole.ENABLER}),
    )


def _partner_profile(card_count: int) -> StructuralDeckProfile:
    if card_count < 2:
        raise ValueError("partner fixture needs at least two cards")
    cards = [_card("Ishai, Ojutai Dragonspeaker"), _card("Rograkh, Son of Rohgahh")]
    cards.extend(_card(f"Library Card {index:03d}") for index in range(card_count - 2))
    return StructuralDeckProfile(
        deck_id="fixture/partners",
        deck_hash="deck-hash",
        commander_names=("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"),
        cards=tuple(cards),
        commander_base_costs={
            "Ishai, Ojutai Dragonspeaker": 4.0,
            "Rograkh, Son of Rohgahh": 0.0,
        },
        data_snapshot_hash="snapshot-hash",
    )


def test_partner_profile_rejects_missing_commander_card_profile() -> None:
    with pytest.raises(ValidationError, match="each commander must have exactly one"):
        StructuralDeckProfile(
            deck_id="fixture/malformed",
            deck_hash="deck-hash",
            commander_names=("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"),
            cards=(
                _card("Ishai, Ojutai Dragonspeaker"),
                *tuple(_card(f"Library Card {index:03d}") for index in range(97)),
            ),
            commander_base_costs={
                "Ishai, Ojutai Dragonspeaker": 4.0,
                "Rograkh, Son of Rohgahh": 0.0,
            },
            data_snapshot_hash="snapshot-hash",
        )


def test_partner_profile_rejects_duplicate_commander_profile() -> None:
    with pytest.raises(ValidationError, match="each commander must have exactly one"):
        StructuralDeckProfile(
            deck_id="fixture/duplicate",
            deck_hash="deck-hash",
            commander_names=("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"),
            cards=(
                _card("Ishai, Ojutai Dragonspeaker"),
                _card("Ishai, Ojutai Dragonspeaker"),
                _card("Rograkh, Son of Rohgahh"),
            ),
            commander_base_costs={
                "Ishai, Ojutai Dragonspeaker": 4.0,
                "Rograkh, Son of Rohgahh": 0.0,
            },
            data_snapshot_hash="snapshot-hash",
        )


def test_production_commander_validator_rejects_98_profile_partner_deck() -> None:
    malformed = _partner_profile(98)
    with pytest.raises(ValueError, match="contains 98 cards"):
        validate_commander_deck_profile(malformed)


def test_production_commander_validator_accepts_100_profile_partner_deck() -> None:
    valid = _partner_profile(100)
    assert validate_commander_deck_profile(valid) is valid
