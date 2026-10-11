from __future__ import annotations

from commander_lab.whole_deck.readiness import build_campaign_readiness


def test_readiness_fails_closed_without_external_gates(repo_root) -> None:
    report = build_campaign_readiness(repo_root, smoke_status="PASS")
    assert report["primary_pod_scheduler_status"] == "PASS"
    assert report["opponent_count"] == 15
    assert report["opponent_full_cycle_combinations"] == 455
    assert report["five_player_full_cycle_combinations"] == 1365
    assert report["knowledge_quality"]["knowledge_pipeline_ready"] is True
    # Current provider truth comes from the manifest (D5), never from the J-P3 history,
    # and it never satisfies a campaign gate on its own.
    assert report["external_engine_status"] == "XMAGE_SELECTED"
    assert report["external_engine_status_source"] == "config/rules_engines.json"
    assert report["historical_p3_provider_decision"] == "NO_PROVIDER_READY"
    assert not any("NO_PROVIDER_READY" in line for line in report["documented_limitations"])
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
    report = build_campaign_readiness(repo_root, external_gates=gates, smoke_status="PASS")
    assert report["remaining_blockers"] == []
    assert report["ready_for_official_campaign"] is True
    assert report["readiness_label"] == "READY_FOR_OFFICIAL_WHOLE_DECK_CAMPAIGN"


def _project_with_provider_decision(repo_root, tmp_path, decision):
    import json
    import shutil

    project = tmp_path / "project"
    shutil.copytree(repo_root, project, ignore=shutil.ignore_patterns(".git", "*.egg-info"))
    path = project / "config/rules_engines.json"
    rules = json.loads(path.read_text(encoding="utf-8"))
    if decision is None:
        rules.pop("provider_decision", None)
    else:
        rules["provider_decision"] = decision
    path.write_text(json.dumps(rules), encoding="utf-8")
    return project


def test_readiness_keeps_the_no_provider_limitation_when_none_is_ready(repo_root, tmp_path):
    project = _project_with_provider_decision(repo_root, tmp_path, "NO_PROVIDER_READY")
    report = build_campaign_readiness(project, smoke_status="PASS")
    assert report["external_engine_status"] == "NO_PROVIDER_READY"
    assert (
        "External rules-engine provider remains NO_PROVIDER_READY and is not promoted to PASS."
        in report["documented_limitations"]
    )


def test_readiness_reports_unknown_when_the_manifest_has_no_decision(repo_root, tmp_path):
    project = _project_with_provider_decision(repo_root, tmp_path, None)
    report = build_campaign_readiness(project, smoke_status="PASS")
    assert report["external_engine_status"] == "UNKNOWN"
    assert report["ready_for_official_campaign"] is False
