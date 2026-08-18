from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from commander_lab.candidate_provenance import (
    OperationalBaselineStatus,
    build_candidate_pool_identity,
    build_candidate_provenance,
    build_variant_provenance,
)
from commander_lab.repositories.candidates import load_candidate_profiles

ROOT = Path(__file__).resolve().parents[2]


def test_rogshai_candidate_pool_binds_inventory_allocation_and_baseline() -> None:
    first = build_candidate_pool_identity(ROOT, "rogshai/current")
    second = build_candidate_pool_identity(ROOT, "rogshai/current")
    assert first == second
    assert first.operational_baseline_status is OperationalBaselineStatus.RESOLVED
    assert first.baseline_deck_hash == (
        "1704b6f1574e4d3152f08cf9936c389683f0ae6efa98a8a277a64daa37f583e3"
    )
    assert len(first.candidate_pool_hash) == 64
    assert len(first.inventory_snapshot_hash) == 64
    assert len(first.allocation_snapshot_hash) == 64
    assert len(first.eligibility_snapshot_hash) == 64


def test_active_korvold_pool_is_explicitly_unresolved_without_fabricated_hash() -> None:
    pool = build_candidate_pool_identity(ROOT, "korvold/current")
    assert pool.operational_baseline_status is OperationalBaselineStatus.UNRESOLVED
    assert pool.baseline_deck_hash is None
    assert len(pool.candidate_pool_hash) == 64


def test_candidate_provenance_explains_current_physical_eligibility() -> None:
    candidates = load_candidate_profiles(ROOT)
    candidate = next(
        value
        for value in candidates.values()
        if "rogshai/current" in value.allowed_deck_ids
        and value.card.oracle_name not in {"Plains", "Island", "Mountain"}
    )
    provenance = build_candidate_provenance(
        ROOT,
        deck_id="rogshai/current",
        candidate_id=candidate.candidate_id,
        oracle_name=candidate.card.oracle_name,
    )
    assert provenance.candidate_pool_hash
    assert provenance.physical_available_quantity > 0
    assert provenance.eligibility_reason == (
        "current_deck_scoped_physical_commander_legal_projection"
    )
    assert provenance.aggregation_mode == "oracle_name_quantity_projection"


def test_variant_provenance_is_deterministic_and_links_candidate_pool() -> None:
    pool = build_candidate_pool_identity(ROOT, "rogshai/current")
    kwargs = {
        "variant_id": "fixture-variant",
        "deck_id": "rogshai/current",
        "baseline_deck_hash": pool.baseline_deck_hash or "",
        "candidate_deck_hash": "1" * 64,
        "candidate_pool_hash": pool.candidate_pool_hash,
        "candidate_ids": ("fixture-candidate",),
        "swaps": (("Old Card", "fixture-candidate"),),
    }
    first = build_variant_provenance(**kwargs)
    second = build_variant_provenance(**kwargs)
    assert first == second
    assert len(first.variant_provenance_hash) == 64


def _copy_candidate_identity_inputs(destination: Path) -> None:
    for relative in (
        "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json",
        "data/decks/manifest.json",
        "data/sync/current_sources.json",
        "data/canonical_import/2026-08-07/inventory_snapshot.json",
        "data/collections/current_deck_allocations.json",
        "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json",
    ):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_candidate_pool_hash_changes_when_allocation_snapshot_changes(tmp_path: Path) -> None:
    _copy_candidate_identity_inputs(tmp_path)
    before = build_candidate_pool_identity(tmp_path, "rogshai/current").candidate_pool_hash
    path = tmp_path / "data/collections/current_deck_allocations.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["candidate_provenance_test_marker"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    after = build_candidate_pool_identity(tmp_path, "rogshai/current").candidate_pool_hash
    assert before != after


def test_non_active_deck_candidate_pool_fails_closed() -> None:
    with pytest.raises(ValueError, match="not a globally active own deck"):
        build_candidate_pool_identity(ROOT, "kaervek/current")
