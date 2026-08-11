from __future__ import annotations

import inspect
import json
from pathlib import Path

from commander_lab.tools.candidates import load_current_optimization_availability
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> dict[str, object]:
    return json.loads((ROOT / "data/collections/current" / name).read_text(encoding="utf-8"))


def test_project_scope_is_rogshai_only_and_preserves_historical_korvold() -> None:
    scope = _load("J_FINAL_ACTIVE_SCOPE.json")
    active = _load("ACTIVE_OWN_DECKS_CURRENT.json")
    release = _load("INACTIVE_FORMER_OWN_DECK_RELEASES.json")

    assert CommanderToolService.ACTIVE_OWN_DECK_IDS == ("rogshai/current",)
    assert active["active_own_deck_ids"] == ["rogshai/current"]
    assert active["inactive_former_own_deck_ids"] == ["korvold/current"]
    assert active["korvold_historical_list_preserved"] is True
    assert active["korvold_optimization_target"] is False
    assert active["korvold_simultaneous_build_requirement"] is False
    assert scope["active_own_decks"] == ["rogshai/current"]
    assert scope["historical_own_decks"] == ["korvold/current"]
    assert scope["historical_allocation_blocks_active_deck"] is False
    assert release["active_own_decks"] == ["rogshai/current"]
    assert "korvold/current" in release["inactive_former_own_decks"]


def test_released_korvold_allocations_are_available_to_current_own_pool() -> None:
    baseline = _load("J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json")
    release = _load("INACTIVE_FORMER_OWN_DECK_RELEASES.json")
    current = load_current_optimization_availability(ROOT)

    released = release["released_allocations"]
    assert isinstance(released, dict) and released
    name = sorted(released)[0]
    expected = int(baseline.get("cards", {}).get(name, 0)) + int(released[name])
    assert current[name] == expected


def test_inventory_fallback_only_reserves_currently_active_own_decks() -> None:
    source = inspect.getsource(CommanderToolService.__init__)
    assert "for deck_id in self.ACTIVE_OWN_DECK_IDS:" in source
    assert 'for deck_id in ("korvold/current", "rogshai/current"):' not in source


def test_playstyle_preference_is_soft_practicality_not_archetype_ban() -> None:
    preference = _load("PLAYSTYLE_PREFERENCE_CURRENT.json")
    assert preference["preference_type"] == "soft_practicality_and_fun_preference"
    assert "archetype_ban" in preference["explicitly_not"]
    assert "ban_on_complexity" in preference["explicitly_not"]
    assert "ban_on_long_decisive_turns" in preference["explicitly_not"]
    assert "repetitive_action_burden" in preference["evaluation_dimensions"]
    assert "trigger_bookkeeping_load" in preference["evaluation_dimensions"]
    assert "loop_dependence" in preference["evaluation_dimensions"]
