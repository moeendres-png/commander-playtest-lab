from __future__ import annotations

import json
from pathlib import Path

from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.project_context import _load_scope, load_project_context
from commander_lab.second_deck_readiness import SecondDeckReadinessWorkflow

ROOT = Path(__file__).resolve().parents[2]


def test_project_scope_parser_is_not_rogshai_literal_locked(tmp_path: Path) -> None:
    path = tmp_path / "scope.json"
    path.write_text(
        json.dumps(
            {
                "active_own_decks": ["future/a", "future/b"],
                "historical_own_decks": ["former/c"],
                "primary_deckbuilding_focus": "future/a",
                "historical_allocation_blocks_active_deck": False,
                "sources": {},
            }
        ),
        encoding="utf-8",
    )
    active, historical, focus, _scope = _load_scope(path)
    assert active == ("future/a", "future/b")
    assert historical == ("former/c",)
    assert focus == "future/a"


def test_current_configuration_remains_rogshai_and_korvold_historical() -> None:
    context = load_project_context(ROOT)
    assert context.active_own_deck_ids == ("rogshai/current",)
    assert context.primary_deckbuilding_focus == "rogshai/current"
    assert "korvold/current" in context.historical_own_deck_ids


def test_second_deck_readiness_is_read_only_truth_bounded_and_deterministic() -> None:
    workflow = SecondDeckReadinessWorkflow(ROOT)
    first = workflow.run()
    second = workflow.run()
    assert first == second
    assert first["active_own_decks_subtracted"] == ["rogshai/current"]
    assert first["historical_decks_do_not_block_availability"] is True
    assert int(first["remaining_physical_unique_names"]) > 0
    assert int(first["single_commander_candidate_count"]) > 0
    assert first["creates_second_deck"] is False
    assert first["creates_reservation"] is False
    assert first["universal_commander_power_score"] is None
    assert first["four_player_performance_claim"] is None
    for row in first["single_commander_candidates"]:
        assert row["four_player_model_claim_allowed"] is False
        assert "Physical/legal support-depth evidence only" in row["evidence_boundary"]


def test_priority_facade_uses_adapter_boundary_and_preserves_candidate_recall() -> None:
    facade = PriorityWorkflowFacade(ROOT)
    screen = facade.build_screen("rogshai/current", limit=1)
    coverage = screen["model_coverage"]
    total = int(screen["eligible_candidate_count"])
    accounted = (
        int(coverage["fully_high_confidence_modeled"])
        + int(coverage["partially_modeled"])
        + int(coverage["structurally_unmodeled"])
    )
    assert total == accounted
    assert screen["unmodeled_candidates_discoverable"] is True
    assert screen["playstyle_is_hard_filter"] is False
    readiness = facade.second_deck_readiness()
    assert readiness["partner_configurations_are_separate_bonus_path"] is True
