from __future__ import annotations

from pathlib import Path

from commander_lab.engine.rules import run_phase85_validation
from commander_lab.models import EngineMessageType


def test_phase85_contract_claims_only_messages_actually_exercised(
    repo_root: Path, tmp_path: Path, monkeypatch
) -> None:
    canonical_state = repo_root / "artifacts/engine_setup/logs/xmage.process-state.json"
    state_before = canonical_state.read_bytes()
    monkeypatch.delenv("ENGINE_START_COMMAND", raising=False)
    monkeypatch.setenv("ENGINE_LOG_DIRECTORY", str(tmp_path / "engine-logs"))
    result = run_phase85_validation(repo_root, output_directory=tmp_path)
    contract = result["contract_tests"]
    assert contract["passed"], contract
    assert contract["exercised"] == [item.value for item in EngineMessageType]
    assert contract["all_message_envelopes_covered_by_contract_tests"]
    assert result["status"] == "external_runtime_prepared_but_not_executed"
    assert not result["full_external_acceptance_passed"]
    assert canonical_state.read_bytes() == state_before
