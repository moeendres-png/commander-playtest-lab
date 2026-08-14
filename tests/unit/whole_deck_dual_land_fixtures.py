from __future__ import annotations

from commander_lab.models import Color
from tests.unit.whole_deck_profile_fixtures import card, profile


def dual_land_fixture_cards():
    cards = []
    for index in range(1, 25):
        cards.append(
            card(
                f"Dual Land {index}",
                profile=profile(
                    f"Dual Land {index}",
                    mv=0.0,
                    is_land=True,
                    produces=frozenset({Color.WHITE, Color.BLUE}),
                ),
                utility=0.0,
            )
        )
    return cards
