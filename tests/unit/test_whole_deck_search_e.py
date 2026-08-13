from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from tests.unit.whole_deck_config_fixture import neutral_config
from tests.unit.whole_deck_context_fixture import synthetic_context

def test_e_different_seed_can_change_exploration_without_breaking_reproducibility():
    context, _ = synthetic_context(); policy = get_policy(PolicyId.OWNED_POOL_NEUTRAL)
    first = WholeDeckSearchEngine(context, policy, config=neutral_config(111)).run()
    second = WholeDeckSearchEngine(context, policy, config=neutral_config(222)).run()
    repeated = WholeDeckSearchEngine(context, policy, config=neutral_config(111)).run()
    assert first.explored_variant_ids != second.explored_variant_ids
    assert first.explored_variant_ids == repeated.explored_variant_ids
