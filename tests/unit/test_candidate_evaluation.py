from __future__ import annotations

import hashlib
from pathlib import Path

from commander_lab.candidate_evaluation import build_candidate_evaluation_plan
from commander_lab.decision_context import TestCandidateSpec as ExplicitTestCandidateSpec
from commander_lab.models import CandidateProfile
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_candidate_evaluation_plan_builds_bounded_nonfinal_frontier() -> None:
    service = CommanderToolService(ROOT)
    plan = build_candidate_evaluation_plan(
        ROOT,
        service=service,
        deck_id="rogshai/current",
        max_pairs=8,
        max_cut_hypotheses=12,
        max_candidate_queue=32,
    )

    assert plan["deck_id"] == "rogshai/current"
    assert plan["evidence_class"] == "structural_model_estimates"
    assert plan["final_recommendation"] is False
    assert plan["canonical_mutation_performed"] is False
    assert plan["inventory_reservation_performed"] is False
    assert plan["candidate_discovery"]["discoverable_candidate_count"] > 0
    assert plan["validated_structural_variant_pool_count"] > 0
    assert 0 < len(plan["variant_frontier"]) <= 8
    assert all(row["constraint_valid"] is True for row in plan["variant_frontier"])
    assert all(row["requires_paired_validation"] is True for row in plan["variant_frontier"])
    assert all(row["final_recommendation"] is False for row in plan["variant_frontier"])
    assert "not empirical" in plan["truth_boundary"]


def test_unprofiled_explicit_test_candidate_is_preserved_for_profile_next() -> None:
    service = CommanderToolService(ROOT)
    spec = ExplicitTestCandidateSpec(
        oracle_name="Unprofiled Hypothetical Candidate Fixture",
        allowed_deck_ids=("rogshai/current",),
        source_id="user:test-fixture:unprofiled",
        source_hash="1" * 64,
        notes="Synthetic unit-test authorization only.",
    )
    plan = build_candidate_evaluation_plan(
        ROOT,
        service=service,
        deck_id="rogshai/current",
        test_candidates=(spec,),
        max_pairs=6,
        max_cut_hypotheses=8,
        max_candidate_queue=32,
    )

    row = next(
        item
        for item in plan["next_candidate_queue"]
        if item["oracle_name"] == spec.oracle_name
    )
    assert row["availability"] == "hypothetical_test"
    assert row["quantity"] == 0
    assert row["physically_available"] is False
    assert row["simulation_authorized"] is True
    assert row["model_ready"] is False
    assert row["frontier_eligible"] is False
    assert row["lane"] == "profile_required"
    assert "profile" in row["next_action"]
    assert any(item["oracle_name"] == spec.oracle_name for item in plan["profile_queue"])
    assert all(item["add"] != spec.oracle_name for item in plan["variant_frontier"])


def test_profiled_explicit_test_candidate_can_enter_simulation_only_frontier_without_inventory_claim() -> None:
    service = CommanderToolService(ROOT)
    source = service.candidates["inventory/rootborn-defenses-677fdbcf"]
    oracle_name = "Hypothetical Rootborn Test Fixture"
    test_profile = CandidateProfile(
        candidate_id="fixture/hypothetical-rootborn",
        card=source.card.model_copy(update={"oracle_name": oracle_name}),
        allowed_deck_ids=("rogshai/current",),
        physical_status="fixture_only",
        notes="Structural unit-test profile only.",
    )
    spec = ExplicitTestCandidateSpec(
        oracle_name=oracle_name,
        allowed_deck_ids=("rogshai/current",),
        source_id="user:test-fixture:profiled",
        source_hash="2" * 64,
        notes="Synthetic unit-test authorization only.",
    )

    protected_paths = (
        ROOT / "data/decks/rogshai_current.json",
        ROOT / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json",
        ROOT / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json",
        ROOT / "data/collections/current_deck_allocations.json",
    )
    before = {str(path): _sha256(path) for path in protected_paths}
    plan = build_candidate_evaluation_plan(
        ROOT,
        service=service,
        deck_id="rogshai/current",
        test_candidates=(spec,),
        test_candidate_profiles=(test_profile,),
        max_pairs=8,
        max_cut_hypotheses=96,
        max_candidate_queue=32,
    )
    after = {str(path): _sha256(path) for path in protected_paths}

    assert before == after
    queue_row = next(
        item for item in plan["next_candidate_queue"] if item["oracle_name"] == oracle_name
    )
    assert queue_row["availability"] == "hypothetical_test"
    assert queue_row["quantity"] == 0
    assert queue_row["physically_available"] is False
    assert queue_row["model_ready"] is True
    assert queue_row["frontier_eligible"] is True
    assert queue_row["lane"] == "explicit_test_ready"

    frontier_row = next(item for item in plan["variant_frontier"] if item["add"] == oracle_name)
    assert frontier_row["simulation_only_hypothetical"] is True
    assert frontier_row["physical_buildable"] is False
    assert frontier_row["physical_inventory_bypass_applied"] is True
    assert (
        frontier_row["physical_inventory_bypass_reason"]
        == "explicit_hypothetical_test_authorization"
    )
    assert frontier_row["candidate_provenance"]["availability"] == "hypothetical_test"
    assert frontier_row["candidate_provenance"]["physically_available"] is False
    assert frontier_row["constraint_valid"] is True
    assert frontier_row["requires_paired_validation"] is True
    assert plan["canonical_mutation_performed"] is False
