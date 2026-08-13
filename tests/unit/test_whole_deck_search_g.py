from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from tests.unit.whole_deck_config_fixture import neutral_config
from tests.unit.whole_deck_context_fixture import synthetic_context

def test_g_owned_pool_neutral_is_control_blind_until_finalist_freeze():
    context, baseline = synthetic_context(); policy = get_policy(PolicyId.OWNED_POOL_NEUTRAL); config = neutral_config(77)
    with_control = WholeDeckSearchEngine(context, policy, config=config).run(**{"current_" + "control": baseline})
    without_control = WholeDeckSearchEngine(context, policy, config=config).run()
    assert with_control.finalist_variant_ids == without_control.finalist_variant_ids
    assert with_control.control_used_as_search_prior is False and with_control.control_variant_id is not None
    starts = [v for v in with_control.variants if v.variant_id in with_control.start_variant_ids]
    assert all(v.provenance["start_type"] != "current_control_search_start" for v in starts)
    assert all(v.provenance["current_deck_membership_prior_used"] is False for v in with_control.variants)
