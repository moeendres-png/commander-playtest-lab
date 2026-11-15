from __future__ import annotations

import json
from pathlib import Path

from commander_lab.canonical_features import load_canonical_feature_annotations
from commander_lab.models import CandidateProfile, CardRole

ROOT = Path(__file__).resolve().parents[2]


def _by_name(candidates):
    return {candidate.card.oracle_name: candidate for candidate in candidates.values()}


def _curated_by_name() -> dict[str, CandidateProfile]:
    payload = json.loads(
        (ROOT / "data/cards/phase5_upgrade_candidates.json").read_text(encoding="utf-8")
    )
    rows = [CandidateProfile.model_validate(row) for row in payload["candidates"]]
    return {row.card.oracle_name: row for row in rows}


def test_current_rogshai_projection_is_complete_for_materialized_rows() -> None:
    annotations = load_canonical_feature_annotations(ROOT, deck_id="rogshai/current")
    assert len(annotations) == 443
    counterspell = annotations["Counterspell"]
    assert counterspell.deck_id == "rogshai/current"
    assert CardRole.COUNTER in counterspell.mapped_roles
    assert "package:rogshai:stack_interaction" in counterspell.package_ids
    kediss = annotations["Kediss, Emberclaw Familiar"]
    assert CardRole.COMBAT_PAYOFF in kediss.mapped_roles
    assert "package:rogshai:kediss_multi_opponent_damage" in kediss.package_ids
