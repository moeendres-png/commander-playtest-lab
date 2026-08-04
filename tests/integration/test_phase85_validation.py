from __future__ import annotations

from pathlib import Path

from commander_lab.engine.rules import run_phase85_validation


def test_phase85_restricted_acceptance_is_explicit(repo_root: Path, tmp_path: Path, monkeypatch) -> None:
    for name in (
        "ENGINE_START_COMMAND", "ENGINE_SOURCE_PATH", "ENGINE_BINARY_PATH",
        "COMMANDER_LAB_XMAGE_BRIDGE_CMD", "COMMANDER_LAB_FORGE_BRIDGE_CMD"
    ):
        monkeypatch.delenv(name, raising=False)
    result = run_phase85_validation(repo_root, output_directory=tmp_path)
    assert result["local_acceptance_passed"]
    assert not result["full_external_acceptance_passed"]
    assert result["status"] == "external_runtime_prepared_but_not_executed"
    assert result["external_engine_validation_pending"] is True
    assert result["phase9_condition"] == "external_engine_validation_pending=true"
    assert all(item["status"] != "rules_engine_validated" for item in result["project_scenarios"])
