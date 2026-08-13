from commander_lab.whole_deck.models import DeckDesignPolicy, PolicyId, TargetCorridor
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from commander_lab.whole_deck.search_models import WholeDeckSearchConfig
from tests.unit.whole_deck_context_fixture import synthetic_context

def test_f_policies_are_allowed_to_converge_on_identical_list():
    context, _ = synthetic_context()
    common = {"target_corridors": {"land_count": TargetCorridor(preferred_minimum=34, preferred_maximum=34, hard_minimum=34, hard_maximum=34)}, "contextual_weights": {}, "functional_meta_weight": 0.0}
    left = DeckDesignPolicy(policy_id=PolicyId.OWNED_POOL_NEUTRAL, **common); right = DeckDesignPolicy(policy_id=PolicyId.RESILIENT_COMMANDER_INDEPENDENT, **common)
    config = WholeDeckSearchConfig(seed=44, diversified_starts=0, max_steps_per_start=1, finalist_limit=1)
    a = WholeDeckSearchEngine(context, left, config=config).run(); b = WholeDeckSearchEngine(context, right, config=config).run()
    ah = next(v.deck_hash for v in a.variants if v.variant_id == a.finalist_variant_ids[0]); bh = next(v.deck_hash for v in b.variants if v.variant_id == b.finalist_variant_ids[0])
    assert ah == bh
