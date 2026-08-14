from __future__ import annotations

from commander_lab.whole_deck.knowledge_quality import build_knowledge_quality_report


def test_knowledge_quality_reconciles_current_candidate_universe(repo_root) -> None:
    report = build_knowledge_quality_report(repo_root)

    assert report["candidate_universe_count"] == 795
    assert report["structurally_usable_count"] + report["semantic_unknown_count"] == 795
    assert report["structurally_usable_fraction"] >= 0.65
    assert report["unknown_high_risk_annotation_count"] == 0
    assert report["orphan_feature_annotations"] == []
    assert report["candidate_without_facts"] == []
    assert report["facts_without_candidate"] == []
    assert report["duplicate_inventory_identities"] == []
    assert report["knowledge_pipeline_ready"] is True


def test_unknowns_remain_visible_and_runtime_vetoes_are_quarantined(repo_root) -> None:
    report = build_knowledge_quality_report(repo_root)

    assert report["semantic_unknown_count"] > 0
    assert len(report["semantic_unknown_cards"]) == report["semantic_unknown_count"]
    assert all(
        row["status"] == "QUARANTINED_BY_RUNTIME_SEMANTIC_GATE"
        for row in report["canonical_feature_runtime_vetoes"]
    )
