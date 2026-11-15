from __future__ import annotations

from commander_lab.models import RuntimeValidationLevel


def test_mutation_guard_validation_levels_remain_distinct() -> None:
    assert RuntimeValidationLevel.STRUCTURAL_ONLY != RuntimeValidationLevel.TACTICAL_ORACLE
    assert RuntimeValidationLevel.TACTICAL_ORACLE != RuntimeValidationLevel.EXTERNAL_RULES_ENGINE
