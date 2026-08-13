from commander_lab.models import Color
from tests.unit.whole_deck_profile_fixtures import card, profile


def island_card():
    return card(
        "Island",
        profile=profile("Island", mv=0.0, is_land=True, produces=frozenset({Color.BLUE})),
        quantity=50,
        basic=True,
        utility=0.0,
    )
