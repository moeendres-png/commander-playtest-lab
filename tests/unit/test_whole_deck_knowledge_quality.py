from __future__ import annotations

from commander_lab.fresh_rebuild import load_fresh_rogshai_universe
from commander_lab.whole_deck.knowledge_quality import (
    ORACLE_TEXT_LEGITIMATELY_EMPTY,
    build_knowledge_quality_report,
    classify_semantic_unknown_cause,
)


def test_knowledge_quality_reconciles_current_candidate_universe(repo_root) -> None:
    report = build_knowledge_quality_report(repo_root)

    assert report["candidate_universe_count"] == 795
    assert report["structurally_usable_count"] + report["semantic_unknown_count"] == 795
    assert report["structurally_usable_fraction"] >= 0.65
    assert report["unknown_high_risk_annotation_count"] == 0
    assert report["orphan_feature_annotations"] == []
    assert report["candidate_without_facts"] == []
    assert report["facts_without_candidate"] == []
    assert report["oracle_fact_exception_without_candidate"] == []
    assert report["duplicate_inventory_identities"] == []
    assert report["knowledge_pipeline_ready"] is True


def test_oracle_fact_completeness_is_distinct_from_nonempty_rules_text(repo_root) -> None:
    universe = load_fresh_rogshai_universe(repo_root)
    report = build_knowledge_quality_report(repo_root)

    assert report["candidate_fact_coverage_count"] == universe.candidate_count
    assert report["candidate_fact_coverage_fraction"] == 1.0
    assert report["verified_empty_rules_text_count"] == 17
    assert report["truly_missing_fact_count"] == 0
    assert report["identity_ambiguous_count"] == 0
    assert (
        report["rules_text_nonempty_count"] + report["verified_empty_rules_text_count"]
        == universe.candidate_count
    )
    assert report["oracle_coverage_count"] == report["rules_text_nonempty_count"]
    assert report["oracle_coverage_fraction"] < report["candidate_fact_coverage_fraction"]


def test_oracle_text_status_regression_cases_are_distinct() -> None:
    normal = {
        "oracle_name": "Normal Rules Card",
        "mana_value": 2,
        "color_identity": ["U"],
        "type_line": "Sorcery",
        "oracle_text": "Draw a card.",
    }
    verified_vanilla = {
        "oracle_name": "Verified Vanilla",
        "mana_value": 2,
        "color_identity": ["W"],
        "type_line": "Creature — Human Soldier",
        "oracle_text": "",
        "oracle_text_status": ORACLE_TEXT_LEGITIMATELY_EMPTY,
    }
    incomplete = {
        "oracle_name": "Incomplete Card",
        "mana_value": 2,
        "color_identity": ["W"],
        "type_line": "Creature — Human Soldier",
        "oracle_text": "",
    }

    assert classify_semantic_unknown_cause(normal) != "oracle_facts_missing"
    assert (
        classify_semantic_unknown_cause(verified_vanilla)
        == "known_no_functional_rules_role"
    )
    assert classify_semantic_unknown_cause(incomplete) == "oracle_facts_missing"


def test_unknowns_remain_visible_and_runtime_vetoes_are_quarantined(repo_root) -> None:
    report = build_knowledge_quality_report(repo_root)

    assert report["semantic_unknown_count"] > 0
    assert len(report["semantic_unknown_cards"]) == report["semantic_unknown_count"]
    assert report["known_no_functional_rules_role_count"] == 17
    assert all(
        row["status"] == "QUARANTINED_BY_RUNTIME_SEMANTIC_GATE"
        for row in report["canonical_feature_runtime_vetoes"]
    )
