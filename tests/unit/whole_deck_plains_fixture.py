from commander_lab.models import Color
from tests.unit.whole_deck_profile_fixtures import card, profile


def plains_card():
    return card(
        "Plains",
        profile=profile("Plains", mv=0.0, is_land=True, produces=frozenset({Color.WHITE})),
        quantity=50,
        basic=True,
        utility=0.0,
    )
