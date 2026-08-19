from __future__ import annotations

import json
from pathlib import Path

XMAGE_REPOSITORY = "https://github.com/moeendres-png/mage.git"
XMAGE_ACTIONS_REPOSITORY = "moeendres-png/mage"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"


def test_current_xmage_b3_runtime_truth_is_pinned_and_fail_closed(repo_root: Path) -> None:
    config = json.loads((repo_root / "config/rules_engines.json").read_text(encoding="utf-8"))
    primary = config["primary_engine"]
    runtime = config["current_runtime"]

    assert primary["repository"] == XMAGE_REPOSITORY
    assert primary["commit"] == XMAGE_COMMIT
    assert primary["production_ready"] is False
    assert primary["real_execution"] is True
    assert primary["status"] == "B3_GAME_START_VALIDATED_DEGRADED"

    assert config["provider_decision"] == "NO_PROVIDER_READY"
    assert config["production_bridge"] == "b3_partial_game_start_bridge"
    assert runtime["provider_selected"] is False
    assert runtime["production_provider"] is None
    assert runtime["required_missing_capabilities"] == [
        "legal_actions_supported",
        "action_submission_supported",
        "event_log_supported",
    ]
    assert primary["missing_required_capabilities"] == runtime["required_missing_capabilities"]


def test_current_bootstraps_use_compatibility_candidate(repo_root: Path) -> None:
    windows = (repo_root / "scripts/bootstrap_engine_windows.ps1").read_text(encoding="utf-8")
    linux = (repo_root / "scripts/bootstrap_engine_linux.sh").read_text(encoding="utf-8")

    for text in (windows, linux):
        assert XMAGE_REPOSITORY in text
        assert XMAGE_COMMIT in text


def test_current_external_workflow_uses_compatibility_candidate(repo_root: Path) -> None:
    workflow = (repo_root / ".github/workflows/external-engine-integration.yml").read_text(
        encoding="utf-8"
    )

    assert f"repository: {XMAGE_ACTIONS_REPOSITORY}" in workflow
    assert f"default: {XMAGE_COMMIT}" in workflow
    assert "git describe --tags --always" in workflow
    assert "engine-bridge/pom.xml" in workflow


def test_b3_bridge_is_present_but_provider_remains_fail_closed(repo_root: Path) -> None:
    bridge_root = repo_root / "engine-bridge"

    assert (bridge_root / "pom.xml").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/Main.java").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/JsonlBridge.java").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/XmageProvider.java").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/XmageGameManager.java").is_file()
    assert (bridge_root / "src/main/java/org/commanderlab/xmage/XmageBridgePlayer.java").is_file()

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
    assert config["production_bridge"] == "b3_partial_game_start_bridge"
    assert config["primary_engine"]["production_ready"] is False
    assert config["primary_engine"]["real_execution"] is True
    assert config["current_runtime"]["provider_selected"] is False
