from commander_lab.models import Color
from tests.unit.whole_deck_profile_fixtures import card, profile

def mountain_card():
    return card("Mountain", profile=profile("Mountain", mv=0.0, is_land=True, produces=frozenset({Color.RED})), quantity=50, basic=True, utility=0.0)
