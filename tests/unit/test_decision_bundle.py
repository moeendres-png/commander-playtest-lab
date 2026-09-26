from __future__ import annotations

import json
from pathlib import Path

from commander_lab.decision_bundle import DecisionBundle, write_decision_bundle


def _bundle() -> DecisionBundle:
    return DecisionBundle(
        bundle_version="1.1",
        baseline_identity={"deck_id": "rogshai/current", "deck_hash": "a" * 64},
        variant_identity={"deck_id": "rogshai/test", "deck_hash": "b" * 64},
        context_snapshot={"snapshot_hash": "c" * 64},
        physical_legal_validation={"valid": True},
        feature_confidence_summary={"canonical_overlay_candidates": 100},
        mana_impact={"before": {"U": 20}, "after": {"U": 21}},
        playstyle_fit_summary={
            "preference_type": "post_build_review_only",
            "automatic_rejection": False,
        },
        central_paired_result={"placement_improvement": 0.1},
        worst_case_sensitivity_result={},
        commander_denial_result={},
        ablation_result={},
        cache_provenance={"cache_hit": False},
        simulation_counts={"valid_runs": 8},
        stopping_reason="fixed paired budget complete",
        evidence_class="structural_model_estimates",
        known_limitations=("not empirical",),
        recommendation_status="structural_evidence_only",
    )


def test_bundle_hash_is_deterministic_and_writer_round_trips(tmp_path: Path) -> None:
    first = _bundle()
    second = _bundle()
    assert first.bundle_hash == second.bundle_hash
    written = write_decision_bundle(first, tmp_path)
    payload = json.loads(Path(written["json_path"]).read_text(encoding="utf-8"))
    assert payload["bundle_hash"] == first.bundle_hash
    assert payload["baseline_identity"]["deck_id"] == "rogshai/current"
    assert payload["playstyle_fit_summary"]["automatic_rejection"] is False
    markdown = Path(written["markdown_path"]).read_text(encoding="utf-8")
    assert first.bundle_hash in markdown
    assert "## Playstyle fit" in markdown
    assert "Structural simulation" not in markdown
