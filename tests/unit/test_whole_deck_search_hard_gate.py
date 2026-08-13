from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from tests.unit.whole_deck_config_fixture import neutral_config
from tests.unit.whole_deck_context_fixture import synthetic_context

def test_hard_gate_checks_nonbasic_singleton_and_physical_quantity():
    context, baseline = synthetic_context()
    engine = WholeDeckSearchEngine(context, get_policy(PolicyId.OWNED_POOL_NEUTRAL), config=neutral_config(1))
    illegal = list(baseline); illegal[-1] = "Filler 1"
    evaluated = engine.evaluate_mainboard(tuple(illegal))
    assert not evaluated.hard_gate.valid
    assert any(issue.startswith("singleton:Filler 1") for issue in evaluated.hard_gate.issues)
