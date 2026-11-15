from __future__ import annotations

from commander_lab.engine.structural import commander_cast_cost


def test_commander_tax_cost() -> None:
    assert commander_cast_cost(5, 0) == 5
    assert commander_cast_cost(5, 1) == 7
    assert commander_cast_cost(4, 3) == 10
