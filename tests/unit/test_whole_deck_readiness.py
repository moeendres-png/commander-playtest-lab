from __future__ import annotations

from commander_lab.whole_deck.readiness import build_campaign_readiness


def test_readiness_fails_closed_without_external_gates(repo_root) -> None:
    report = build_campaign_readiness(repo_root, smoke_status="PASS")
    assert report["primary_pod_scheduler_status"] == "PASS"
    assert report["opponent_count"] == 8
    assert report["opponent_full_cycle_combinations"] == 56
    assert report["knowledge_quality"]["knowledge_pipeline_ready"] is True
    assert report["external_engine_status"] == "NO_PROVIDER_READY"
    assert report["ready_for_official_campaign"] is False
    assert report["readiness_label"] == "NOT_READY_FOR_OFFICIAL_WHOLE_DECK_CAMPAIGN"


def test_readiness_can_pass_after_all_mandatory_external_gates(repo_root) -> None:
    gates = {
        "ci_status": "PASS",
        "security_status": "PASS",
        "windows_status": "PASS",
        "j_p6_status": "PASS",
        "j_final_status": "PASS",
        "release_status": "PASS",
    }
    report = build_campaign_readiness(
        repo_root, external_gates=gates, smoke_status="PASS"
    )
    assert report["remaining_blockers"] == []
    assert report["ready_for_official_campaign"] is True
    assert report["readiness_label"] == "READY_FOR_OFFICIAL_WHOLE_DECK_CAMPAIGN"
