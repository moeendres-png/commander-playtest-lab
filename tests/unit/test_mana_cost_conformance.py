"""K4 conformance test: structured mana data from engine (no regex).

Verifies that _engine_cost() correctly sums the structured mana_cost_*
fields provided by the Java bridge (via ability.getManaCostsToPay().getMana()).

The bridge extracts structured data (not regex-parsed):
- Java: XmageFullGamePlayer.enrichAbilityCostFacts() reads Mana object
- Python: _engine_cost() sums mana_cost_white/blue/black/red/green/generic/colorless
"""

from __future__ import annotations

from commander_lab.engine.rules.full_game_pilot_views import _engine_cost


def test_engine_cost_sums_structured_fields():
    """_engine_cost sums the structured mana_cost_* fields."""
    meta = {
        "mana_cost_white": 1,
        "mana_cost_blue": 0,
        "mana_cost_black": 2,
        "mana_cost_red": 0,
        "mana_cost_green": 0,
        "mana_cost_generic": 3,
        "mana_cost_colorless": 0,
    }
    # 1W + 2B + 3 generic = 6 total
    assert _engine_cost(meta) == 6.0


def test_engine_cost_returns_none_without_fields():
    """_engine_cost returns None if no structured fields present."""
    meta = {"some_other_field": "value"}
    assert _engine_cost(meta) is None


def test_engine_cost_ignores_non_int():
    """_engine_cost ignores non-integer values (defensive)."""
    meta = {
        "mana_cost_white": 1,
        "mana_cost_blue": "not-an-int",  # should be ignored
        "mana_cost_generic": 2,
    }
    assert _engine_cost(meta) == 3.0


def test_engine_cost_ignores_bool():
    """_engine_cost ignores booleans (bool is subclass of int in Python)."""
    meta = {
        "mana_cost_white": True,  # True == 1, but should be ignored
        "mana_cost_generic": 2,
    }
    assert _engine_cost(meta) == 2.0
