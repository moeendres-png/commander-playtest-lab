from __future__ import annotations

from pathlib import Path

from commander_lab.canonical_features import load_canonical_feature_annotations
from commander_lab.models import CardRole
from commander_lab.tools.current_candidates import (
    _legacy_load_candidate_profiles,
    canonical_feature_fusion_summary,
    load_candidate_profiles,
)

ROOT = Path(__file__).resolve().parents[2]


def _by_name(candidates):
    return {candidate.card.oracle_name: candidate for candidate in candidates.values()}


def test_projection_is_complete_for_materialized_current_rows() -> None:
    annotations = load_canonical_feature_annotations(ROOT)
    assert len(annotations) == 443
    counterspell = annotations["Counterspell"]
    assert CardRole.COUNTER in counterspell.mapped_roles
    assert "package:rogshai:stack_interaction" in counterspell.package_ids
    kediss = annotations["Kediss, Emberclaw Familiar"]
    assert CardRole.COMBAT_PAYOFF in kediss.mapped_roles
    assert "package:rogshai:kediss_multi_opponent_damage" in kediss.package_ids


def test_fusion_preserves_existing_numeric_profile_values() -> None:
    legacy = _by_name(_legacy_load_candidate_profiles(ROOT))
    current = _by_name(load_candidate_profiles(ROOT))
    before = legacy["Boros Charm"].card
    after = current["Boros Charm"].card

    assert after.floor_value == before.floor_value
    assert after.immediate_impact == before.immediate_impact
    assert after.turn_cycle_risk == before.turn_cycle_risk
    assert after.multiplayer_scaling == before.multiplayer_scaling
    assert after.commander_synergy == before.commander_synergy
    assert before.roles <= after.roles
    assert before.package_ids <= after.package_ids
    assert "package:rogshai:commander_protection" in after.package_ids
    assert any(
        source.source_type == "canonical_drive_derived_projection" for source in after.sources
    )


def test_fusion_does_not_drop_candidates_and_reports_overlay_coverage() -> None:
    legacy = _legacy_load_candidate_profiles(ROOT)
    current = load_candidate_profiles(ROOT)
    assert set(current) == set(legacy)
    summary = canonical_feature_fusion_summary(ROOT)
    assert summary["rogshai_candidates_loaded"] > 0
    assert summary["canonical_overlay_candidates"] > 0
    assert summary["heuristic_or_curated_without_overlay"] >= 0
