from __future__ import annotations

from commander_lab.models import CardRole
from tests.unit.whole_deck_profile_fixtures import card, profile


def nonland_fixture_cards():
    cards = []
    for index in range(1, 81):
        cards.append(card(f"Filler {index}", profile=profile(f"Filler {index}", mv=2.0), utility=1.0))
    for index in range(1, 7):
        cards.append(
            card(
                f"Engine Piece {index}",
                profile=profile(
                    f"Engine Piece {index}",
                    mv=2.0,
                    roles=frozenset({CardRole.ENGINE}),
                    package_ids=frozenset({"six-piece-engine"}),
                ),
                utility=0.0,
            )
        )
    return cards
