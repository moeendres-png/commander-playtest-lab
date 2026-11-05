"""A standalone card keeps its identity when a prepare spell reuses its name."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.agents.card_knowledge import canonical_card_name


@pytest.mark.parametrize("standalone_first", [True, False])
def test_exact_card_name_wins_over_a_prepare_spell_alias(
    tmp_path: Path, standalone_first: bool
) -> None:
    entries = [
        ("Rampant Growth", {"name": "Rampant Growth"}),
        ("Studious First-Year", {"name": "Studious First-Year // Rampant Growth"}),
    ]
    if not standalone_first:
        entries.reverse()
    path = tmp_path / "cards.json"
    path.write_text(json.dumps({"cards": dict(entries)}), encoding="utf-8")
    assert canonical_card_name("Rampant Growth", path) == "Rampant Growth"
    assert canonical_card_name("rampant growth", path) == "rampant growth"
    assert (
        canonical_card_name("Studious First-Year", path) == "Studious First-Year // Rampant Growth"
    )
    assert canonical_card_name("Wear", path) == "Wear"


@pytest.mark.parametrize("name", ["Rampant Growth", "Exsanguinate", "Seething Song", "Raise Dead"])
def test_known_standalone_names_remain_separate_in_the_live_catalog(name: str) -> None:
    assert canonical_card_name(name) == name
