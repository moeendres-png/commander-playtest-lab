from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.decision_context import (
    CandidateAvailability,
    DecisionContextError,
    TestCandidateSpec,
    load_decision_context_registry,
)

ROOT = Path(__file__).resolve().parents[2]


def _write_json(root: Path, relative: str, payload: object) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _write_multi_deck_fixture(root: Path) -> tuple[Path, Path]:
    _write_json(
        root,
        "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json",
        {
            "active_own_decks": ["fixture/alpha", "fixture/beta"],
            "primary_deckbuilding_focus": "fixture/alpha",
        },
    )
    _write_json(
        root,
        "data/decks/manifest.json",
        {
            "decks": {
                "fixture/alpha": {
                    "deck_hash": "1" * 64,
                    "commanders": ["Alpha Commander"],
                },
                "fixture/beta": {
                    "deck_hash": "2" * 64,
                    "commanders": ["Beta Commander"],
                },
            }
        },
    )
    inventory = _write_json(
        root,
        "data/canonical_import/2026-08-07/inventory_snapshot.json",
        {"cards": [{"oracle_name": "Shared Free Card", "quantity": 1}]},
    )
    allocation = _write_json(
        root,
        "data/collections/current_deck_allocations.json",
        {"allocations": {"fixture/alpha": {}, "fixture/beta": {}}},
    )
    _write_json(
        root,
        "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json",
        {
            "eligible_by_deck": {
                "fixture/alpha": {
                    "Alpha Free Card": {
                        "commander_legal": True,
                        "physical_available_quantity": 1,
                    },
                    "Shared Free Card": {
                        "commander_legal": True,
                        "physical_available_quantity": 1,
                    },
                    "Reserved Alpha Card": {
                        "commander_legal": True,
                        "physical_available_quantity": 0,
                    },
                },
                "fixture/beta": {
                    "Beta Free Card": {
                        "commander_legal": True,
                        "physical_available_quantity": 2,
                    },
                    "Shared Free Card": {
                        "commander_legal": True,
                        "physical_available_quantity": 1,
                    },
                },
            }
        },
    )
    _write_json(
        root,
        "data/collections/current/POD_SCENARIOS_CURRENT.json",
        {"scenarios": [], "frequency_policy": "No fixed opponent frequency weights."},
    )
    return inventory, allocation


def test_current_decision_context_is_read_only_and_deck_scoped() -> None:
    inventory = ROOT / "data/canonical_import/2026-08-07/inventory_snapshot.json"
    allocation = ROOT / "data/collections/current_deck_allocations.json"
    before_inventory = inventory.read_bytes()
    before_allocation = allocation.read_bytes()

    registry = load_decision_context_registry(ROOT)

    assert registry.deck_ids == ("rogshai/current",)
    assert registry.candidates_for_deck("rogshai/current")
    assert all(
        row.availability is CandidateAvailability.PHYSICAL_FREE
        for row in registry.candidates_for_deck("rogshai/current")
    )
    assert inventory.read_bytes() == before_inventory
    assert allocation.read_bytes() == before_allocation


def test_multi_deck_fixture_keeps_candidate_and_run_contexts_separate(tmp_path: Path) -> None:
    inventory, allocation = _write_multi_deck_fixture(tmp_path)
    before_inventory = inventory.read_bytes()
    before_allocation = allocation.read_bytes()
    registry = load_decision_context_registry(
        tmp_path,
        test_candidates=(
            TestCandidateSpec(
                oracle_name="Beta Theory Card",
                allowed_deck_ids=("fixture/beta",),
                source_id="user:test-candidates:fixture",
                source_hash="a" * 64,
                notes="Explicit isolated test candidate; not physical inventory.",
            ),
        ),
    )

    assert registry.deck_ids == ("fixture/alpha", "fixture/beta")
    alpha = registry.candidates_for_deck("fixture/alpha")
    beta = registry.candidates_for_deck("fixture/beta")
    alpha_names = {row.oracle_name for row in alpha}
    beta_names = {row.oracle_name for row in beta}

    assert "Alpha Free Card" in alpha_names
    assert "Beta Free Card" not in alpha_names
    assert "Beta Theory Card" not in alpha_names
    assert "Beta Free Card" in beta_names
    assert "Alpha Free Card" not in beta_names
    assert "Beta Theory Card" in beta_names
    assert "Reserved Alpha Card" not in alpha_names

    theory = next(row for row in beta if row.oracle_name == "Beta Theory Card")
    assert theory.availability is CandidateAvailability.HYPOTHETICAL_TEST
    assert theory.physically_available is False
    assert theory.quantity == 0

    alpha_candidate = next(row for row in alpha if row.oracle_name == "Alpha Free Card")
    beta_candidate = next(row for row in beta if row.oracle_name == "Beta Theory Card")
    alpha_run = registry.build_run_context(
        deck_id="fixture/alpha",
        variant_id="alpha/test-variant",
        candidate_ids=(alpha_candidate.candidate_id,),
        opponent_ids=("opponent/a", "opponent/b", "opponent/c"),
        pilot_ids=("pilot/strong",),
        pod_size=4,
        seed=11,
        evidence_class="structural_model_estimates",
    )
    beta_run = registry.build_run_context(
        deck_id="fixture/beta",
        variant_id="beta/test-variant",
        candidate_ids=(beta_candidate.candidate_id,),
        opponent_ids=("opponent/x", "opponent/y", "opponent/z"),
        pilot_ids=("pilot/strong",),
        pod_size=4,
        seed=11,
        evidence_class="structural_model_estimates",
    )

    assert alpha_run.deck_id == "fixture/alpha"
    assert beta_run.deck_id == "fixture/beta"
    assert alpha_run.run_identity_hash != beta_run.run_identity_hash
    assert alpha_run.context_snapshot_hash == registry.snapshot_hash
    assert beta_run.context_snapshot_hash == registry.snapshot_hash
    alpha_availability = alpha_run.candidate_provenance[0].availability
    beta_availability = beta_run.candidate_provenance[0].availability
    assert alpha_availability is CandidateAvailability.PHYSICAL_FREE
    assert beta_availability is CandidateAvailability.HYPOTHETICAL_TEST

    with pytest.raises(DecisionContextError, match="not scoped"):
        registry.build_run_context(
            deck_id="fixture/alpha",
            variant_id="illegal/cross-deck",
            candidate_ids=(beta_candidate.candidate_id,),
            opponent_ids=("opponent/a", "opponent/b", "opponent/c"),
            pilot_ids=("pilot/strong",),
            pod_size=4,
            seed=11,
            evidence_class="structural_model_estimates",
        )

    assert inventory.read_bytes() == before_inventory
    assert allocation.read_bytes() == before_allocation


def test_purchase_candidate_is_not_implicitly_test_approved(tmp_path: Path) -> None:
    _write_multi_deck_fixture(tmp_path)
    registry = load_decision_context_registry(tmp_path)
    assert all(
        row.availability is not CandidateAvailability.PURCHASE_CANDIDATE
        for own_deck_id in registry.deck_ids
        for row in registry.candidates_for_deck(own_deck_id)
    )
