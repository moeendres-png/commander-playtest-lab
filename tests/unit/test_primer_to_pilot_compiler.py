from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.rules.tactical import TacticalRuleOracle

ROOT = Path(__file__).resolve().parents[2]


def test_tactical_oracle_semantics_used_by_curated_rules() -> None:
    oracle = TacticalRuleOracle()
    kediss = oracle.evaluate("kediss_trigger", {"commander_combat_damage": 7, "opponent_count": 3})
    assert kediss["normal_damage_each"] == 7
    assert kediss["additional_commander_damage"] == 0
    jeska = oracle.evaluate("jeska_triple", {"combat_damage": 6, "is_commander": True})
    assert jeska["commander_damage"] == 18
    silence = oracle.evaluate("silence_restriction", {"silence_resolved": True, "same_turn": True})
    assert silence["can_cast_spell"] is False
    assert silence["can_activate_ability"] is True


def test_saved_replay_evidence_is_structural_and_parseable() -> None:
    replay = ROOT / "tests/fixtures/replays/phase12_2_structural_replay.jsonl"
    rows = [
        json.loads(line) for line in replay.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert rows
    assert all(row["estimate_type"] == "structural_model_estimates" for row in rows)
    assert any(row["event_type"] == "london_mulligan" for row in rows)
