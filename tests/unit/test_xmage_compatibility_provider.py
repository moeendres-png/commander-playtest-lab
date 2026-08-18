from __future__ import annotations

import json
from pathlib import Path

XMAGE_REPOSITORY = "https://github.com/moeendres-png/mage.git"
XMAGE_ACTIONS_REPOSITORY = "moeendres-png/mage"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"

HISTORICAL_REPOSITORY = "https://github.com/magefree/mage.git"
HISTORICAL_COMMIT = "06d166b098ad36b277edef01116472203d5a047e"


def test_current_xmage_compatibility_candidate_records_b3_partial_execution(
    repo_root: Path,
) -> None:
    config = json.loads((repo_root / "config/rules_engines.json").read_text(encoding="utf-8"))
    primary = config["primary_engine"]

    assert primary["repository"] == XMAGE_REPOSITORY
    assert primary["commit"] == XMAGE_COMMIT
    assert primary["status"] == "B3_PARTIAL"
    assert primary["production_ready"] is False
    assert primary["real_execution"] is True

    assert config["provider_decision"] == "NO_PROVIDER_READY"
    assert config["production_bridge"] == "b3_partial_jsonl_bridge_no_action_loop"
    assert config["current_runtime"]["provider_selected"] is False
    assert config["current_runtime"]["production_provider"] is None
    assert config["current_runtime"]["xmage_status"] == "B3_PARTIAL"

    capabilities = config["production_bridge_capabilities"]
    assert "real_deck_import" in capabilities["external_rules_engine_evidence"]
    assert "real_game_start" in capabilities["external_rules_engine_evidence"]
    assert "legal_action_enumeration" in capabilities["production_blockers"]
    assert "action_submission" in capabilities["production_blockers"]
    assert "event_log" in capabilities["production_blockers"]


def test_current_bootstraps_use_compatibility_candidate(
    repo_root: Path,
) -> None:
    windows = (repo_root / "scripts/bootstrap_engine_windows.ps1").read_text(encoding="utf-8")
    linux = (repo_root / "scripts/bootstrap_engine_linux.sh").read_text(encoding="utf-8")

    for text in (windows, linux):
        assert XMAGE_REPOSITORY in text
        assert XMAGE_COMMIT in text


def test_current_external_workflow_uses_compatibility_candidate(
    repo_root: Path,
) -> None:
    workflow = (repo_root / ".github/workflows/external-engine-integration.yml").read_text(
        encoding="utf-8"
    )

    assert f"repository: {XMAGE_ACTIONS_REPOSITORY}" in workflow
    assert f"default: {XMAGE_COMMIT}" in workflow
    assert "git describe --tags --always" in workflow
    assert "engine-bridge/pom.xml" in workflow


def test_historical_jp3b_provider_evidence_remains_pinned(
    repo_root: Path,
) -> None:
    for relative in (
        ".github/workflows/j-p3b-xmage-fixtures.yml",
        ".github/workflows/j-p3b-xmage-real-spike.yml",
    ):
        text = (repo_root / relative).read_text(encoding="utf-8")

        assert HISTORICAL_REPOSITORY in text
        assert HISTORICAL_COMMIT in text
        assert XMAGE_COMMIT not in text


def test_b3_bridge_is_present_but_remains_fail_closed(
    repo_root: Path,
) -> None:
    bridge_root = repo_root / "engine-bridge"

    assert (bridge_root / "pom.xml").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/Main.java").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/JsonlBridge.java").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/XmageProvider.java").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/XmageDeckImporter.java").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/XmageGameManager.java").is_file()

    workflow = (repo_root / ".github/workflows/external-engine-integration.yml").read_text(
        encoding="utf-8"
    )
    assert "-DskipTests install" in workflow
    assert "working-directory: engine-bridge" in workflow
    assert "mvn -B -ntp verify" in workflow

    windows = (repo_root / "scripts/bootstrap_engine_windows.ps1").read_text(encoding="utf-8")
    linux = (repo_root / "scripts/bootstrap_engine_linux.sh").read_text(encoding="utf-8")
    assert "-DskipTests install" in windows
    assert "-DskipTests install" in linux

    config = json.loads((repo_root / "config/rules_engines.json").read_text(encoding="utf-8"))
    assert config["provider_decision"] == "NO_PROVIDER_READY"
    assert config["production_bridge"] == "b3_partial_jsonl_bridge_no_action_loop"
    assert config["primary_engine"]["production_ready"] is False
    assert config["primary_engine"]["real_execution"] is True
    blockers = set(config["production_bridge_capabilities"]["production_blockers"])
    assert {"legal_action_enumeration", "action_submission", "event_log"} <= blockers
