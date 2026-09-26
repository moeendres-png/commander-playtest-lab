from commander_lab.whole_deck.mana import derive_mana_base_policy
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search_models import WholeDeckNeighborhood


def test_c_search_dimensions_are_independent():
    dimensions = tuple(WholeDeckNeighborhood)
    assert len(dimensions) == 8
    assert dimensions[-1] != dimensions[-2]
    mana = derive_mana_base_policy(get_policy(PolicyId.OWNED_POOL_NEUTRAL))
    assert mana.preferred_basic_maximum < mana.preferred_land_minimum
    assert mana.hard_land_minimum <= mana.preferred_land_minimum
