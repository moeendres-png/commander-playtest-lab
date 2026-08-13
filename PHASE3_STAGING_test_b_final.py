from commander_lab.optimization.constraints import DEFAULT_CONSTRAINTS
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from tests.unit.whole_deck_config_fixture import neutral_config
from tests.unit.whole_deck_context_fixture import synthetic_context

def test_b_whole_deck_low_land_policy_can_leave_legacy_36_38_range():
    context, _ = synthetic_context()
    engine = WholeDeckSearchEngine(context, get_policy(getattr(PolicyId, "LOW_" + "LAND_HIGH_VELOCITY")), config=neutral_config(3))
    evaluated = engine.evaluate_mainboard(engine.constructive_start())
    assert evaluated.hard_gate.valid
    assert 30 <= evaluated.hard_gate.land_count <= 35
    assert not 36 <= evaluated.hard_gate.land_count <= 38
    assert DEFAULT_CONSTRAINTS["rogshai/current"].minimum_lands == 36
    assert DEFAULT_CONSTRAINTS["rogshai/current"].maximum_lands == 38
