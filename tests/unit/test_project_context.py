from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from commander_lab.project_context import ProjectContextError, load_project_context

ROOT = Path(__file__).resolve().parents[2]


def test_current_context_resolves_rogshai_primary_and_korvold_historical() -> None:
    first = load_project_context(ROOT)
    second = load_project_context(ROOT)

    expected = (
        "opponent/morcant-elves",
        "opponent/doom-prevails-precon",
        "opponent/cosmic-spiderman-midbudget",
    )
    assert first.active_own_deck_ids == ("rogshai/current",)
    assert first.historical_own_deck_ids == ("korvold/current",)
    assert first.primary_opponent_deck_ids("rogshai/current") == expected
    with pytest.raises(ProjectContextError, match="no canonical primary scenario"):
        first.primary_opponent_deck_ids("korvold/current")
    assert first.historical_reference_opponent_deck_ids("korvold/current") == expected
    assert first.snapshot_hash == second.snapshot_hash
    assert len(first.snapshot_hash) == 64
    assert "opponent/blight-curse-precon" in first.holdout_deck_ids
    assert set(expected).isdisjoint(first.holdout_deck_ids)
    assert first.playstyle_preference_type == "post_build_review_only"
    assert dict(first.active_deck_hashes) == {
        "rogshai/current": "7b7d03aa16be6586df8f8a4e9f1acd30f85ad2e8e45e7889e700353a6f19c126"
    }
    assert "config/J_P5_SEARCH_POLICY_v1.json" in dict(first.policy_config_hashes)
    assert len(first.playstyle_preference_hash) == 64
    hashes = dict(first.source_hashes)
    assert "inventory_snapshot" in hashes
    assert "allocation_snapshot" in hashes
    assert "playstyle_preference" in hashes
    assert "inactive_deck_releases" in hashes
    assert any(key.startswith("drive_feature:INVENTORY_CARD_FEATURES_CURRENT") for key in hashes)
    assert any(key.startswith("drive_feature:MULTIPLAYER_CARD_FEATURES_CURRENT") for key in hashes)
    assert any(key.startswith("drive_feature:CARD_SYNERGY_GRAPH_CURRENT") for key in hashes)
    assert any(key.startswith("drive_feature:DECK_PACKAGE_TAXONOMY_CURRENT") for key in hashes)


def _copy_context_inputs(destination: Path) -> None:
    for relative in (
        "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json",
        "data/collections/current/PLAYSTYLE_PREFERENCE_CURRENT.json",
        "data/collections/current/INACTIVE_FORMER_OWN_DECK_RELEASES.json",
        "data/collections/current/POD_SCENARIOS_CURRENT.json",
        "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json",
        "data/opponents/opponent_registry.json",
        "data/pilots/pilot_registry.json",
        "data/decks/manifest.json",
        "data/canonical_import/2026-08-07/inventory_snapshot.json",
        "data/collections/current_deck_allocations.json",
    ):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    source_projection = ROOT / "data/collections/current/rogshai_feature_projection"
    target_projection = destination / "data/collections/current/rogshai_feature_projection"
    shutil.copytree(source_projection, target_projection)
    shutil.copytree(ROOT / "config", destination / "config")


def test_context_fails_closed_when_required_source_is_missing(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    (tmp_path / "data/opponents/opponent_registry.json").unlink()
    with pytest.raises(ProjectContextError, match="required project-context input is missing"):
        load_project_context(tmp_path)


def test_context_fails_closed_when_holdout_is_promoted_to_primary(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    path = tmp_path / "data/collections/current/POD_SCENARIOS_CURRENT.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    primary = next(
        row for row in payload["scenarios"] if row["scenario_id"] == "primary_4p_rogshai"
    )
    primary["opponent_entity_ids"][0] = "opponent:blight_curse"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectContextError, match="holdout opponent was silently promoted"):
        load_project_context(tmp_path)


def test_context_fails_closed_on_unknown_opponent_entity(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    path = tmp_path / "data/collections/current/POD_SCENARIOS_CURRENT.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    primary = next(
        row for row in payload["scenarios"] if row["scenario_id"] == "primary_4p_rogshai"
    )
    primary["opponent_entity_ids"][0] = "opponent:unknown_fixture"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectContextError, match="unknown canonical opponent entity id"):
        load_project_context(tmp_path)


def test_context_fails_closed_when_playstyle_boundary_is_weakened(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    path = tmp_path / "data/collections/current/PLAYSTYLE_PREFERENCE_CURRENT.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["explicitly_not"].remove("archetype_ban")
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectContextError, match="playstyle preference lost"):
        load_project_context(tmp_path)


def test_context_fails_closed_when_live_scope_is_stale(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    path = tmp_path / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["current_valid"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectContextError, match="stale"):
        load_project_context(tmp_path)


def test_context_hash_changes_if_policy_config_changes(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    before = load_project_context(tmp_path).snapshot_hash
    path = tmp_path / "config/protected_cards.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["fixture_context_hash_change"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    after = load_project_context(tmp_path).snapshot_hash
    assert before != after


def test_context_hash_changes_if_feature_projection_changes(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    before = load_project_context(tmp_path).snapshot_hash
    part = tmp_path / "data/collections/current/rogshai_feature_projection/part_04.json"
    rows = json.loads(part.read_text(encoding="utf-8"))
    rows[0][1].append("card_selection")
    part.write_text(json.dumps(rows), encoding="utf-8")
    after = load_project_context(tmp_path).snapshot_hash
    assert before != after


def test_context_hash_changes_if_playstyle_preference_changes(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    before = load_project_context(tmp_path).snapshot_hash
    path = tmp_path / "data/collections/current/PLAYSTYLE_PREFERENCE_CURRENT.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["avoid_normalized_pattern"] += " with avoidable administrative overhead"
    path.write_text(json.dumps(payload), encoding="utf-8")
    after = load_project_context(tmp_path).snapshot_hash
    assert before != after
