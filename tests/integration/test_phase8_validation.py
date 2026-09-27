from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.rules import run_phase8_validation


def test_phase8_validation_marks_all_local_cards_and_keeps_external_gate_blocked(
    repo_root: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("COMMANDER_LAB_FORGE_BRIDGE_CMD", raising=False)
    monkeypatch.delenv("COMMANDER_LAB_XMAGE_BRIDGE_CMD", raising=False)
    summary = run_phase8_validation(repo_root, output_directory=tmp_path, seed=17)
    assert summary["local_acceptance_passed"] is True
    assert summary["interaction_cases"] >= 50
    assert summary["tactical_passed"] == summary["interaction_cases"]
    assert summary["rules_engine_release_gate_passed"] is False
    registry = json.loads((tmp_path / "validation_registry.json").read_text())
    oracle_payload = json.loads((repo_root / "data/cards/oracle_subset.json").read_text())
    oracle_names = {card["oracle_name"] for card in oracle_payload["cards"]}
    assert oracle_names.issubset(registry["cards"])
    assert len(registry["cards"]) >= len(oracle_names)
    assert registry["tactical_cases"] >= 50
    assert registry["rules_engine_passed"] == 0
