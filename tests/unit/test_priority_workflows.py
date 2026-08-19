from __future__ import annotations

import json
from pathlib import Path

from commander_lab.priority_workflows import PriorityWorkflowFacade

ROOT = Path(__file__).resolve().parents[2]


def test_build_screen_and_mulligan_mana_use_same_canonical_context() -> None:
    facade = PriorityWorkflowFacade(ROOT)
    screen = facade.build_screen("rogshai/current", limit=5)
    mana = facade.mulligan_mana("rogshai/current")
    assert screen["deck_hash"] == mana["deck_hash"]
    assert screen["context"]["snapshot_hash"] == mana["context"]["snapshot_hash"]
    assert screen["eligible_candidate_count"] > 0
    assert screen["candidate_pool_after_default_screen"] <= screen["eligible_candidate_count"]
    assert screen["feature_fusion"]["canonical_overlay_candidates"] > 0
    assert screen["challenge_benchmark"]["known_good_candidate_recall"] == 1.0
    assert screen["challenge_benchmark"]["known_bad_candidate_rejection"] == 1.0
    assert screen["playstyle_policy"] == "post_build_review_only"
    assert screen["playstyle_used_for_screening_or_ranking"] is False
    assert mana["primary_opponents"] == [
        "opponent/morcant-elves",
        "opponent/doom-prevails-precon",
        "opponent/cosmic-spiderman-midbudget",
    ]
    assert "no empirical card-power ranking" in screen["ranking_claim"]


def test_compare_validate_reuses_paired_engine_and_exact_cache() -> None:
    facade = PriorityWorkflowFacade(ROOT)
    request = {
        "deck_id": "rogshai/current",
        "remove": "Flare of Duplication",
        "add_candidate_id": "inventory/rootborn-defenses-677fdbcf",
        "iterations": 1,
        "seed": 20260811,
        "workers": 2,
    }
    first = facade.compare_validate(**request)
    second = facade.compare_validate(**request)
    assert first["status"] == "completed"
    assert first["evidence_class"] == "structural_model_estimates"
    assert first["pair_count"] == 1
    assert first["paired"]["requested_runs"] == 1
    assert first["paired"]["worker_count"] == 1
    assert first["execution_workers"] == {
        "requested": 2,
        "effective": 1,
        "fallback_applied": True,
        "policy": "validated_single_worker_policy_1_18",
        "deck_quality_evidence": False,
    }
    assert len(first["paired_observations"]) == 1
    assert first["context"]["snapshot_hash"] == facade.context.snapshot_hash
    assert len(first["workflow_semantic_identity"]["identity_hash"]) == 64
    assert (
        first["cache_provenance"]["workflow_semantic_identity_hash"]
        == first["workflow_semantic_identity"]["identity_hash"]
    )
    assert first["cache_provenance"]["governance_context_hash"] == facade.context.snapshot_hash
    assert first["static_screen"]["automatic_rejection"] is False
    assert first["playstyle_review_status"] == "deferred_until_decision_bundle"
    assert "playstyle_fit" not in first
    assert "mana_delta" in first
    assert second["cache_provenance"]["cache_hit"] is True
    assert second["cache_provenance"]["cache_key"] == first["cache_provenance"]["cache_key"]
    assert second["paired"] == first["paired"]
    assert first["truth_boundary"].endswith("not empirical gameplay")


def test_priority_facade_can_use_an_isolated_acceptance_cache(tmp_path: Path) -> None:
    facade = PriorityWorkflowFacade(ROOT, result_cache_path=tmp_path / "acceptance.sqlite3")
    request = {
        "deck_id": "rogshai/current",
        "remove": "Flare of Duplication",
        "add_candidate_id": "inventory/rootborn-defenses-677fdbcf",
        "iterations": 1,
        "seed": 2026082103,
    }
    first = facade.compare_validate(**request)
    second = facade.compare_validate(**request)

    assert first["cache_provenance"]["cache_hit"] is False
    assert second["cache_provenance"]["cache_hit"] is True
    assert first["paired"] == second["paired"]


def test_diagnose_and_decision_bundle_are_reproducible(tmp_path: Path) -> None:
    facade = PriorityWorkflowFacade(ROOT)
    comparison = {
        "status": "completed",
        "baseline_identity": {"deck_id": "rogshai/current", "deck_hash": "a" * 64},
        "variant_identity": {
            "deck_id": "rogshai/test",
            "deck_hash": "b" * 64,
            "remove": "Flare of Duplication",
            "add_candidate_id": "inventory/rootborn-defenses-677fdbcf",
        },
        "context": {"snapshot_hash": facade.context.snapshot_hash},
        "constraint_report": {"valid": True},
        "mana_before": {"colored_sources": {"U": 20}},
        "mana_after": {"colored_sources": {"U": 21}},
        "mana_delta": {"colored_source_delta": {"U": 1}},
        "cache_provenance": {
            "cache_key": "a" * 64,
            "cache_hit": False,
            "evidence_class": "structural_model_estimates",
        },
        "paired": {
            "distributionally_robust_lower_bound": 0.05,
            "confidence_interval": [0.01, 0.20],
            "requested_runs": 8,
            "valid_runs": 8,
        },
    }
    diagnosis = facade.diagnose_next_experiment(comparison)
    assert diagnosis["next_experiment"] == "run_next_paired_micro_batch"
    assert diagnosis["decision_information_state"]["status"] == "MORE_SIMULATIONS_USEFUL"
    written = facade.create_decision_bundle(comparison, tmp_path)
    payload = json.loads(Path(written["json_path"]).read_text(encoding="utf-8"))
    assert payload["context_snapshot"]["snapshot_hash"] == facade.context.snapshot_hash
    assert payload["cache_provenance"]["cache_key"] == "a" * 64
    assert payload["cache_provenance"]["cache_hit"] is False
    assert payload["playstyle_fit_summary"]["automatic_rejection"] is False
    assert payload["playstyle_fit_summary"]["preference_type"] == "post_build_review_only"
    assert payload["playstyle_fit_summary"]["status"] == "completed_after_objective_decision"
    assert payload["playstyle_fit_summary"]["separate_from_recommendation_status"] is True
    assert payload["mana_impact"]["delta"]["colored_source_delta"]["U"] == 1
    assert payload["evidence_class"] == "structural_model_estimates"
    assert payload["extra"]["decision_information_state"]["status"] == "MORE_SIMULATIONS_USEFUL"


def test_playstyle_annotations_do_not_change_objective_workflow_results() -> None:
    facade = PriorityWorkflowFacade(ROOT)
    before = facade.build_screen("rogshai/current", limit=20)
    facade.playstyle.inventory.clear()
    after = facade.build_screen("rogshai/current", limit=20)

    for key in ("bucket_counts", "candidate_pool_after_default_screen", "candidates"):
        assert before[key] == after[key]


def test_public_advancement_interface_applies_resolution_and_model_information() -> None:
    comparison = {
        "status": "completed",
        "paired": {
            "confidence_interval": [0.50, 0.60],
            "distributionally_robust_lower_bound": 0.05,
        },
    }
    measured = {"status": "MEASURED", "effective_resolution": 0.392857142857143}

    separated = PriorityWorkflowFacade.advancement_decision(
        comparison,
        model_resolution=measured,
    )
    assert separated["status"] == "advance"

    unresolved = PriorityWorkflowFacade.advancement_decision(
        comparison,
        model_resolution={"status": "MEASURED", "effective_resolution": 0.70},
    )
    assert unresolved["status"] == "diagnose"
    assert unresolved["reason_code"] == "unresolved_or_lower_tail_unfavorable"

    governed = PriorityWorkflowFacade.advancement_decision(
        comparison,
        model_informativeness={"status": "MODEL_INFORMATION_LIMIT"},
        model_resolution=measured,
    )
    assert governed["status"] == "diagnose"
    assert governed["reason_code"] == "model_information_limit"
