from __future__ import annotations

import json
from pathlib import Path

from commander_lab.canonical_features import load_canonical_feature_annotations
from commander_lab.models import CandidateProfile, CardRole
from commander_lab.repositories.candidates import load_candidate_profiles as repository_candidates
from commander_lab.tools.current_candidates import (
    canonical_feature_fusion_summary,
    load_candidate_profiles,
)

ROOT = Path(__file__).resolve().parents[2]


def _by_name(candidates):
    return {candidate.card.oracle_name: candidate for candidate in candidates.values()}


def _curated_by_name() -> dict[str, CandidateProfile]:
    payload = json.loads(
        (ROOT / "data/cards/phase5_upgrade_candidates.json").read_text(encoding="utf-8")
    )
    rows = [CandidateProfile.model_validate(row) for row in payload["candidates"]]
    return {row.card.oracle_name: row for row in rows}


def test_projection_is_complete_for_materialized_current_rows() -> None:
    annotations = load_canonical_feature_annotations(ROOT)
    assert len(annotations) == 443
    counterspell = annotations["Counterspell"]
    assert CardRole.COUNTER in counterspell.mapped_roles
    assert "package:rogshai:stack_interaction" in counterspell.package_ids
    kediss = annotations["Kediss, Emberclaw Familiar"]
    assert CardRole.COMBAT_PAYOFF in kediss.mapped_roles
    assert "package:rogshai:kediss_multi_opponent_damage" in kediss.package_ids


def test_fusion_preserves_curated_numeric_profile_values() -> None:
    curated = _curated_by_name()
    current = _by_name(load_candidate_profiles(ROOT))
    before = curated["Opt"].card
    after = current["Opt"].card

    assert after.floor_value == before.floor_value
    assert after.immediate_impact == before.immediate_impact
    assert after.turn_cycle_risk == before.turn_cycle_risk
    assert after.multiplayer_scaling == before.multiplayer_scaling
    assert after.commander_synergy == before.commander_synergy
    assert before.package_ids <= after.package_ids
    assert any(
        source.source_type == "canonical_drive_derived_projection" for source in after.sources
    )


def test_tools_adapter_is_explicit_alias_of_repository_loader() -> None:
    current = load_candidate_profiles(ROOT)
    repository = repository_candidates(ROOT)
    assert set(current) == set(repository)
    assert {key: value.card.model_dump(mode="json") for key, value in current.items()} == {
        key: value.card.model_dump(mode="json") for key, value in repository.items()
    }
    summary = canonical_feature_fusion_summary(ROOT)
    assert summary["rogshai_candidates_loaded"] > 0
    assert summary["canonical_overlay_candidates"] > 0
    assert summary["heuristic_or_curated_without_overlay"] >= 0
