from __future__ import annotations

from pathlib import Path

from commander_lab.engine.rules import run_phase85_validation


def test_phase85_restricted_acceptance_is_explicit(repo_root: Path, tmp_path: Path, monkeypatch) -> None:
    for name in (
        "ENGINE_START_COMMAND", "ENGINE_SOURCE_PATH", "ENGINE_BINARY_PATH",
        "COMMANDER_LAB_XMAGE_BRIDGE_CMD", "COMMANDER_LAB_FORGE_BRIDGE_CMD"
    ):
        monkeypatch.delenv(name, raising=False)
    canonical_state = repo_root / "artifacts/engine_setup/logs/xmage.process-state.json"
    state_before = canonical_state.read_bytes()
    monkeypatch.setenv("ENGINE_LOG_DIRECTORY", str(tmp_path / "engine-logs"))
    result = run_phase85_validation(repo_root, output_directory=tmp_path)
    assert result["local_acceptance_passed"]
    assert not result["full_external_acceptance_passed"]
    assert result["status"] == "external_runtime_prepared_but_not_executed"
    assert result["external_engine_validation_pending"] is True
    assert result["phase9_condition"] == "external_engine_validation_pending=true"
    assert canonical_state.read_bytes() == state_before
    assert all(item["status"] != "external_rules_engine" for item in result["project_scenarios"])
