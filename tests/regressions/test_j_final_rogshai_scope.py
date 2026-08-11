from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from commander_lab.engine.structural.project import _merge_unique_structural_profiles
from commander_lab.fresh_rebuild import load_fresh_rebuild_runtime, load_fresh_rogshai_universe
from commander_lab.models import StructuralDeckProfile
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.project_context import load_project_context
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_productive_active_deck_scope_is_rogshai_only() -> None:
    context = load_project_context(ROOT)
    assert CommanderToolService.ACTIVE_OWN_DECK_IDS == ("rogshai/current",)
    assert CommanderToolService.HISTORICAL_OWN_DECK_IDS == ("korvold/current",)
    assert CommanderToolService.FROZEN_OPPONENT_ONLY_DECK_IDS == frozenset({"kaervek/current"})
    assert context.active_own_deck_ids == ("rogshai/current",)
    assert "korvold/current" in context.historical_own_deck_ids


def test_historical_korvold_allocation_does_not_block_rogshai() -> None:
    universe = load_fresh_rogshai_universe(ROOT)
    assert "Lightning Greaves" in universe.candidate_names
    assert universe.available_quantities["Lightning Greaves"] == 1
    service = CommanderToolService(ROOT)
    assert service.candidate_inventory.get("Lightning Greaves", 0) >= 1


def test_complete_fresh_rebuild_candidate_recall_and_coverage() -> None:
    universe = load_fresh_rogshai_universe(ROOT)
    runtime = load_fresh_rebuild_runtime(ROOT)
    coverage = runtime["candidate_universe"]["coverage_counts"]
    assert universe.candidate_count == 795
    assert len(universe.verified_physical_names) == 795
    assert universe.structurally_scorable_count == 123
    assert universe.review_required_count == 672
    assert coverage == {
        "STRUCTURALLY_MODELED": 123,
        "PARTIALLY_MODELED": 588,
        "STRUCTURALLY_UNMODELED": 84,
    }
    assert 123 + 588 + 84 == universe.candidate_count


def test_current_rogshai_membership_is_neutral_for_fresh_discovery() -> None:
    service = CommanderToolService(ROOT)
    universe = load_fresh_rogshai_universe(ROOT)
    current_names = {card.oracle_name for card in service.decks["rogshai/current"].cards}
    assert current_names <= universe.candidate_names
    assert "Ishai, Ojutai Dragonspeaker" in universe.candidate_names
    assert "Rograkh, Son of Rohgahh" in universe.candidate_names


def test_high_level_build_screen_sees_all_795_without_silent_exclusion() -> None:
    facade = PriorityWorkflowFacade(ROOT)
    result = facade.build_screen("rogshai/current", limit=795)
    rows = result["candidates"]
    assert result["legal_physical_candidate_count"] == 795
    assert result["discoverable_candidate_count"] == 795
    assert result["eligible_candidate_count"] == 795
    assert result["candidate_recall"] == 1.0
    assert result["excluded_candidate_count_by_reason"] == {}
    assert result["fully_high_confidence_modeled"] == 123
    assert result["partially_modeled"] == 588
    assert result["structurally_unmodeled"] == 84
    assert result["unmodeled_candidate_discoverability"] is True
    assert result["fresh_rebuild_neutrality"] == {
        "current_deck_membership_quality_prior": False,
        "historical_deck_membership_quality_prior": False,
        "historical_allocation_blocks_active_deck": False,
    }
    assert isinstance(rows, list)
    assert len(rows) == 795
    assert all(row["explorable"] is True for row in rows)
    assert any(row["requires_profile_before_model_dependent_recommendation"] for row in rows)
    assert {row["oracle_name"] for row in rows} == load_fresh_rogshai_universe(ROOT).candidate_names


def test_structural_profile_collision_fails_closed() -> None:
    profile = cast(StructuralDeckProfile, object())
    target = {"opponent/duplicate": profile}
    incoming = {"opponent/duplicate": profile}
    with pytest.raises(ValueError, match="structural deck_id collision"):
        _merge_unique_structural_profiles(target, incoming, source="j-final-regression")
