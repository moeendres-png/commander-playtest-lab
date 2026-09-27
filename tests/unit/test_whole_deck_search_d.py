from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from tests.unit.whole_deck_config_fixture import neutral_config
from tests.unit.whole_deck_context_fixture import synthetic_context


def test_d_same_inputs_produce_identical_result():
    context, _ = synthetic_context()
    policy = get_policy(PolicyId.OWNED_POOL_NEUTRAL)
    config = neutral_config(2026)
    first = WholeDeckSearchEngine(context, policy, config=config).run()
    second = WholeDeckSearchEngine(context, policy, config=config).run()
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
