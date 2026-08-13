from commander_lab.whole_deck.search import WholeDeckSearchContext
from tests.unit.whole_deck_basic_land_fixtures import basic_land_fixture_cards
from tests.unit.whole_deck_commander_fixtures import commander_fixture_cards
from tests.unit.whole_deck_dual_land_fixtures import dual_land_fixture_cards
from tests.unit.whole_deck_nonland_fixtures import nonland_fixture_cards

def synthetic_context():
    cards = commander_fixture_cards() + basic_land_fixture_cards() + dual_land_fixture_cards() + nonland_fixture_cards()
    context = WholeDeckSearchContext.synthetic(cards)
    baseline = tuple(["Island"] * 34 + [f"Filler {index}" for index in range(1, 65)])
    return context, baseline
