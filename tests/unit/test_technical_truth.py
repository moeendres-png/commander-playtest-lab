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
    assert truth["active_deck_hashes"] == {
        "rogshai/current": "7b7d03aa16be6586df8f8a4e9f1acd30f85ad2e8e45e7889e700353a6f19c126"
    }
    assert truth["playstyle_policy"]["stage"] == "post_build_review_only"
    assert truth["playstyle_policy"]["objective_decision_signal"] is False
    assert len(truth["canonical_context_snapshot"]) == 64
    assert truth["roadmap_mvp_state"]["j_p6_merged_baseline_is_ancestor"] is True
    assert truth["roadmap_mvp_state"]["priority_context_surface_present"] is True
    assert truth["roadmap_mvp_state"]["priority_workflow_surface_present"] is True
    assert truth["roadmap_mvp_state"]["exact_result_cache_surface_present"] is True
    assert truth["roadmap_mvp_state"]["production_adaptive_scheduler_present"] is False
    assert truth["roadmap_mvp_state"]["model_informativeness_gate_present"] is True
    assert truth["roadmap_mvp_state"]["workflow_session_present"] is True
    assert truth["roadmap_mvp_state"]["public_high_level_workflow_surface_present"] is True
    assert truth["external_engine_status"]["provider_decision"] == "NO_PROVIDER_READY"
    assert truth["external_engine_status"]["production_provider_ready"] is False
    assert truth["current_blockers"] == []
    assert "external_rules_engine_validation_pending" in truth["documented_limitations"]
    readiness = truth["first_run_readiness"]
    assert readiness["preparation_surface_present"] is True
    assert readiness["authorized_runner_surface_present"] is True
    assert readiness["preliminary_run"]["official_first_run"] is False
    assert readiness["official_run"] == {
        "default_status": "not_started",
        "authorization_required": True,
    }
    assert truth["git"]["commit"]
    assert truth["git"]["tree"]
