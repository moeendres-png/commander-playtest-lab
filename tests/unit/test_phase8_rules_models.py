from __future__ import annotations

import pytest
from pydantic import ValidationError

from commander_lab.engine.rules import load_project_rules_decks
from commander_lab.models import RulesDeckInput, ValidationLevel


def test_project_rules_decks_are_exact_commander_decks(repo_root) -> None:
    decks = load_project_rules_decks(repo_root)
    assert set(decks) == {"korvold/current", "rogshai/current"}
    assert len(decks["korvold/current"].mainboard) == 99
    assert len(decks["rogshai/current"].mainboard) == 98
    assert len(decks["rogshai/current"].commander_names) == 2


def test_rules_deck_input_rejects_non_100_card_deck() -> None:
    with pytest.raises(ValidationError):
        RulesDeckInput(
            deck_id="bad",
            name="Bad",
            commander_names=("Commander",),
            mainboard=("Card",) * 98,
        )


def test_validation_levels_are_exactly_the_three_required_values() -> None:
    assert {item.value for item in ValidationLevel} == {
        "structural_only",
        "tactical_validated",
        "rules_engine_validated",
    }
