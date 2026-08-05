from __future__ import annotations

from pathlib import Path

from commander_lab.engine.rules import run_phase85_validation
from commander_lab.models import EngineMessageType


def test_phase85_contract_claims_only_messages_actually_exercised(repo_root: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ENGINE_START_COMMAND", raising=False)
    result = run_phase85_validation(repo_root, output_directory=tmp_path)
    contract = result["contract_tests"]
    assert contract["passed"]
    assert contract["exercised"] == [item.value for item in EngineMessageType]
    assert contract["all_message_envelopes_covered_by_contract_tests"]
    assert result["status"] == "external_runtime_prepared_but_not_executed"
    assert not result["full_external_acceptance_passed"]
