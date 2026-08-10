from __future__ import annotations

from commander_lab.engine.structural.simulator import (
    commander_cast_cost,
    commander_damage_is_lethal,
)
from commander_lab.models import RuntimeValidationLevel


def test_mutation_guard_commander_damage_threshold_is_inclusive_at_21() -> None:
    assert commander_damage_is_lethal({"ishai": 21})
    assert not commander_damage_is_lethal({"ishai": 20.999})
    assert not commander_damage_is_lethal({"ishai": 12, "rograkh": 12})


def test_mutation_guard_commander_tax_is_two_per_prior_cast() -> None:
    assert commander_cast_cost(5, 0) == 5
    assert commander_cast_cost(5, 1) == 7
    assert commander_cast_cost(5, 2) == 9


def test_mutation_guard_validation_levels_remain_distinct() -> None:
    assert RuntimeValidationLevel.STRUCTURAL_ONLY != RuntimeValidationLevel.TACTICAL_ORACLE
    assert RuntimeValidationLevel.TACTICAL_ORACLE != RuntimeValidationLevel.EXTERNAL_RULES_ENGINE
