from __future__ import annotations

import json
from pathlib import Path

from commander_lab.tools.candidates import load_current_optimization_availability
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_active_own_deck_scope_is_rogshai_only() -> None:
    service = CommanderToolService(ROOT)
    assert service.ACTIVE_OWN_DECK_IDS == ("rogshai/current",)
    assert service.FROZEN_OPPONENT_ONLY_DECK_IDS == frozenset({"kaervek/current"})
    assert "korvold/current" in service.decks


def test_inactive_korvold_allocation_is_released_to_current_availability() -> None:
    release = json.loads(
        (ROOT / "data/collections/current/INACTIVE_FORMER_OWN_DECK_RELEASES.json").read_text(
            encoding="utf-8"
        )
    )
    assert release["active_own_decks"] == ["rogshai/current"]
    assert "korvold/current" in release["inactive_former_own_decks"]
    assert release["released_allocations"]["Lightning Greaves"] == 1

    current = load_current_optimization_availability(ROOT)
    assert current.get("Lightning Greaves", 0) >= 1
