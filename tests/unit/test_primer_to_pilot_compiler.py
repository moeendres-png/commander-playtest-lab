from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from commander_lab.engine.rules.tactical import TacticalRuleOracle
from commander_lab.models import (
    PilotRule,
    PrimerEvidenceType,
    PrimerRuleStatus,
)

ROOT = Path(__file__).resolve().parents[2]


def _rules(path: str) -> tuple[PilotRule, ...]:
    payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return tuple(PilotRule.model_validate(row) for row in payload["rules"])


def test_inferred_rule_cannot_be_activated_without_manual_approval() -> None:
    row = _rules("data/primer_rules/rules/automatic_candidates.json")[0].model_dump(mode="json")
    row["status"] = "active"
    with pytest.raises(ValidationError, match="manual approval"):
        PilotRule.model_validate(row)


def test_automatic_extraction_remains_disabled() -> None:
    rules = _rules("data/primer_rules/rules/automatic_candidates.json")
    assert len(rules) == 8
    assert all(rule.status == PrimerRuleStatus.NEEDS_REVIEW for rule in rules)
    assert all(rule.evidence_type == PrimerEvidenceType.PRIMER_INFERRED for rule in rules)


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
