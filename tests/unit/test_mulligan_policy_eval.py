"""The mulligan ruler (scripts/mulligan_policy_eval.py) and the colours a card makes (#989)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from commander_lab.agents.card_knowledge import card_facts
from commander_lab.models import PilotStrength

ROOT = Path(__file__).resolve().parents[2]
PRECONS = sorted((ROOT / "data/decks/precons").glob("*.json"))[::20]


@pytest.fixture(scope="module")
def ruler():
    spec = importlib.util.spec_from_file_location(
        "mulligan_policy_eval", ROOT / "scripts/mulligan_policy_eval.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_colours_made_by_lands() -> None:
    assert card_facts("Forest").colours_made == frozenset("G")  # type: ignore[union-attr]
    assert card_facts("Command Tower").colours_made == frozenset("WUBRG")  # type: ignore[union-attr]
    # A fetch land fixes any colour even though it makes no mana itself.
    assert card_facts("Evolving Wilds").colours_made == frozenset("WUBRG")  # type: ignore[union-attr]
    # A spell makes no colour by being a spell.
    assert card_facts("Counterspell").colours_made == frozenset()  # type: ignore[union-attr]


def test_ruler_ranks_the_policies_in_the_expected_order(ruler) -> None:
    """Wrong-reason control: a ruler that cannot tell keeping everything from judging is no ruler."""
    reports = {
        policy: ruler.evaluate(PRECONS, 60, 5, policy, PilotStrength.AVERAGE)
        for policy in ("always_keep", "pilot")
    }
    keep_all, pilot = reports["always_keep"], reports["pilot"]
    assert pilot["mana_spent"] > keep_all["mana_spent"]
    assert pilot["missed_land_drops"] < keep_all["missed_land_drops"]
    assert pilot["colour_blocked_turns"] < keep_all["colour_blocked_turns"]
    assert pilot["share_no_spell"] < keep_all["share_no_spell"]
    assert keep_all["mulligans_per_hand"] == 0.0
    assert pilot["mulligans_per_hand"] > 0.0


def test_ruler_is_deterministic(ruler) -> None:
    first = ruler.evaluate(PRECONS[:3], 20, 9, "pilot", PilotStrength.AVERAGE)
    second = ruler.evaluate(PRECONS[:3], 20, 9, "pilot", PilotStrength.AVERAGE)
    assert first == second
