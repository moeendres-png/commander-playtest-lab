from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from commander_lab.models import Deck
from commander_lab.project_context import ProjectContextError, load_project_context
from commander_lab.storage import compute_deck_hash

ROOT = Path(__file__).resolve().parents[2]
SECOND_DECK_ID = "synthetic-second/current"


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
        "data/decks/rogshai_current.json",
        "data/canonical_import/2026-08-07/inventory_snapshot.json",
        "data/collections/current_deck_allocations.json",
    ):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copytree(
        ROOT / "data/collections/current/rogshai_feature_projection",
        destination / "data/collections/current/rogshai_feature_projection",
    )
    shutil.copytree(ROOT / "config", destination / "config")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _extend_scope_registry_and_pods(root: Path) -> None:
    scope_path = root / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    scope["active_own_decks"].append(SECOND_DECK_ID)
    scope["active_own_deck_ids"].append(SECOND_DECK_ID)
    _write_json(scope_path, scope)

    registry_path = root / "config/deck_decision_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["deck_policies"][SECOND_DECK_ID] = copy.deepcopy(
        registry["deck_policies"]["rogshai/current"]
    )
    _write_json(registry_path, registry)

    pods_path = root / "data/collections/current/POD_SCENARIOS_CURRENT.json"
    pods = json.loads(pods_path.read_text(encoding="utf-8"))
    primary = next(
        row for row in pods["scenarios"] if row["scenario_type"] == "primary_four_player_context"
    )
    second_primary = copy.deepcopy(primary)
    second_primary["scenario_id"] = "primary_4p_synthetic_second"
    second_primary["own_deck"] = SECOND_DECK_ID
    second_primary["own_deck_id"] = "deck:synthetic-second"
    second_primary["purpose"] = "synthetic test-only second active deck context"
    pods["scenarios"].append(second_primary)
    _write_json(pods_path, pods)


def _add_valid_second_deck(root: Path) -> str:
    source_path = root / "data/decks/rogshai_current.json"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["deck_id"] = SECOND_DECK_ID
    payload["deck_hash"] = "0" * 64
    deck = Deck.model_validate(payload)
    digest = compute_deck_hash(deck)
    payload["deck_hash"] = digest
    target_path = root / "data/decks/synthetic_second_current.json"
    _write_json(target_path, payload)

    manifest_path = root / "data/decks/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["active_own_decks"].append(SECOND_DECK_ID)
    manifest["global_active_own_decks"].append(SECOND_DECK_ID)
    spec = copy.deepcopy(manifest["decks"]["rogshai/current"])
    spec["deck_hash"] = digest
    spec["normalized_file"] = "synthetic_second_current.json"
    spec["source_file"] = "synthetic_second_current.txt"
    spec["physical_printings_file"] = "synthetic_second_current_physical_printings.json"
    manifest["decks"][SECOND_DECK_ID] = spec
    _write_json(manifest_path, manifest)
    return digest


def test_current_project_context_still_has_exactly_one_active_rogshai() -> None:
    context = load_project_context(ROOT)
    assert context.active_own_deck_ids == ("rogshai/current",)


def test_project_context_accepts_consistent_synthetic_two_deck_scope(tmp_path: Path) -> None:
    _copy_context_inputs(tmp_path)
    _extend_scope_registry_and_pods(tmp_path)
    digest = _add_valid_second_deck(tmp_path)

    context = load_project_context(tmp_path)
    assert context.active_own_deck_ids == ("rogshai/current", SECOND_DECK_ID)
    assert dict(context.active_deck_hashes)[SECOND_DECK_ID] == digest
    assert context.primary_opponent_deck_ids(SECOND_DECK_ID) == context.primary_opponent_deck_ids(
        "rogshai/current"
    )


def test_project_context_fails_closed_when_active_deck_is_missing_from_manifest(
    tmp_path: Path,
) -> None:
    _copy_context_inputs(tmp_path)
    _extend_scope_registry_and_pods(tmp_path)
    manifest_path = tmp_path / "data/decks/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["active_own_decks"].append(SECOND_DECK_ID)
    manifest["global_active_own_decks"].append(SECOND_DECK_ID)
    _write_json(manifest_path, manifest)

    with pytest.raises(ProjectContextError, match="missing from deck manifest"):
        load_project_context(tmp_path)


def test_project_context_fails_closed_when_active_manifest_entry_is_invalid(
    tmp_path: Path,
) -> None:
    _copy_context_inputs(tmp_path)
    manifest_path = tmp_path / "data/decks/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["decks"]["rogshai/current"]["validation"]["valid"] = False
    _write_json(manifest_path, manifest)

    with pytest.raises(ProjectContextError, match="not marked valid"):
        load_project_context(tmp_path)
