from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from commander_lab.project_context import ProjectContextError, load_project_context

ROOT = Path(__file__).resolve().parents[2]


def test_current_context_resolves_primary_pods_and_is_deterministic() -> None:
    first = load_project_context(ROOT)
    second = load_project_context(ROOT)

    expected = (
        "opponent/morcant-elves",
        "opponent/doom-prevails-precon",
        "opponent/cosmic-spiderman-midbudget",
    )
    assert first.primary_opponent_deck_ids("korvold/current") == expected
    assert first.primary_opponent_deck_ids("rogshai/current") == expected
    assert first.snapshot_hash == second.snapshot_hash
    assert len(first.snapshot_hash) == 64
    assert "opponent/blight-curse-precon" in first.holdout_deck_ids
    assert set(expected).isdisjoint(first.holdout_deck_ids)


def _copy_context_inputs(destination: Path) -> None:
    for relative in (
        "data/collections/current/J_P5_POD_SCENARIOS_CURRENT.json",
        "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json",
        "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json",
        "data/opponents/opponent_registry.json",
        "data/pilots/pilot_registry.json",
        "data/decks/manifest.json",
    ):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_context_fails_closed_when_required_source_is_missing(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    (tmp_path / "data/opponents/opponent_registry.json").unlink()
    with pytest.raises(ProjectContextError, match="required project-context input is missing"):
        load_project_context(tmp_path)


def test_context_fails_closed_when_holdout_is_promoted_to_primary(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    path = tmp_path / "data/collections/current/J_P5_POD_SCENARIOS_CURRENT.json"
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
    path = tmp_path / "data/collections/current/J_P5_POD_SCENARIOS_CURRENT.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    primary = next(
        row for row in payload["scenarios"] if row["scenario_id"] == "primary_4p_rogshai"
    )
    primary["opponent_entity_ids"][0] = "opponent:unknown_fixture"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectContextError, match="unknown canonical opponent entity id"):
        load_project_context(tmp_path)
