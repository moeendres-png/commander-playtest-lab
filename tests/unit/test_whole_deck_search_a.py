from __future__ import annotations
import random
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from commander_lab.whole_deck.search_models import WholeDeckNeighborhood
from tests.unit.whole_deck_config_fixture import neutral_config
from tests.unit.whole_deck_context_fixture import synthetic_context

def test_a_six_plus_coordinated_changes_escape_single_swap_valley():
    context, baseline = synthetic_context()
    engine = WholeDeckSearchEngine(context, get_policy(PolicyId.OWNED_POOL_NEUTRAL), config=neutral_config(7))
    before = engine.evaluate_mainboard(baseline)
    proposal, removed, added = engine.propose(baseline, WholeDeckNeighborhood.ENGINE_PACKAGE, random.Random(11))
    after = engine.evaluate_mainboard(proposal)
    assert len(removed) >= 6 and len(added) >= 6
    assert set(added) == {f"Engine Piece {index}" for index in range(1, 7)}
    assert after.objective_prior > before.objective_prior
    one = list(baseline); one.remove("Filler 1"); one.append("Engine Piece 1")
    assert engine.evaluate_mainboard(tuple(one)).objective_prior < before.objective_prior
