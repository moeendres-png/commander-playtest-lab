from __future__ import annotations

from pathlib import Path

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.storage.database import SCHEMA_VERSION
from commander_lab.technical_truth import build_technical_truth

ROOT = Path(__file__).resolve().parents[2]


def test_technical_truth_derives_current_versions_scope_and_engine_boundary() -> None:
    truth = build_technical_truth(ROOT)
    assert truth["package_version"] == __version__
    assert truth["engine_version"] == ENGINE_VERSION
    assert truth["schema_versions"]["database"] == SCHEMA_VERSION
    assert truth["active_deck_set"] == ["rogshai/current"]
    assert truth["historical_own_deck_set"] == ["korvold/current"]
    assert truth["primary_deckbuilding_focus"] == "rogshai/current"
    assert len(truth["canonical_context_snapshot"]) == 64
    assert truth["roadmap_mvp_state"]["j_p6_merged_baseline_is_ancestor"] is True
    assert truth["roadmap_mvp_state"]["priority_context_surface_present"] is True
    assert truth["roadmap_mvp_state"]["priority_workflow_surface_present"] is True
    assert truth["roadmap_mvp_state"]["exact_result_cache_surface_present"] is True
    assert truth["roadmap_mvp_state"]["production_adaptive_scheduler_present"] is False
    assert truth["external_engine_status"]["provider_decision"] == "NO_PROVIDER_READY"
    assert truth["external_engine_status"]["production_provider_ready"] is False
    assert "external_rules_engine_validation_pending" in truth["current_blockers"]
    assert truth["git"]["commit"]
    assert truth["git"]["tree"]
