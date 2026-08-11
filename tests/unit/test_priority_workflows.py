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
    assert screen["feature_fusion"]["canonical_overlay_candidates"] > 0
    assert mana["primary_opponents"] == [
        "opponent/morcant-elves",
        "opponent/doom-prevails-precon",
        "opponent/cosmic-spiderman-midbudget",
    ]
    assert screen["ranking_claim"].startswith("none")


def test_compare_validate_reuses_jp5_paired_engine() -> None:
    facade = PriorityWorkflowFacade(ROOT)
    result = facade.compare_validate(
        deck_id="rogshai/current",
        remove="Flare of Duplication",
        add_candidate_id="inventory/rootborn-defenses-677fdbcf",
        iterations=1,
        seed=20260811,
    )
    assert result["status"] == "completed"
    assert result["evidence_class"] == "structural_model_estimates"
    assert result["pair_count"] == 1
    assert result["paired"]["requested_runs"] == 1
    assert result["context"]["snapshot_hash"] == facade.context.snapshot_hash
    assert result["truth_boundary"].endswith("not empirical gameplay")


def test_diagnose_and_decision_bundle_are_reproducible(tmp_path: Path) -> None:
    facade = PriorityWorkflowFacade(ROOT)
    comparison = {
        "status": "completed",
        "baseline_identity": {"deck_id": "rogshai/current", "deck_hash": "a" * 64},
        "variant_identity": {"deck_id": "rogshai/test", "deck_hash": "b" * 64},
        "context": {"snapshot_hash": facade.context.snapshot_hash},
        "constraint_report": {"valid": True},
        "mana_before": {"colored_sources": {"U": 20}},
        "mana_after": {"colored_sources": {"U": 21}},
        "paired": {
            "distributionally_robust_lower_bound": 0.05,
            "confidence_interval": [0.01, 0.20],
            "requested_runs": 8,
            "valid_runs": 8,
        },
    }
    diagnosis = facade.diagnose_next_experiment(comparison)
    assert diagnosis["next_experiment"] == "run_sensitivity_then_commander_denial"
    written = facade.create_decision_bundle(comparison, tmp_path)
    payload = json.loads(Path(written["json_path"]).read_text(encoding="utf-8"))
    assert payload["context_snapshot"]["snapshot_hash"] == facade.context.snapshot_hash
    assert payload["cache_provenance"]["status"].endswith("J_P6_concurrency_guard")
    assert payload["evidence_class"] == "structural_model_estimates"
