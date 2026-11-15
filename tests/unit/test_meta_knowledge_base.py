"""Validation rules of the meta snapshot models (`commander_lab.models.meta`)."""

from __future__ import annotations

from commander_lab.storage import sha256_value


def _stable_deck_hash(cards: tuple[str, ...]) -> str:
    return sha256_value(sorted(card.strip().casefold() for card in cards))
