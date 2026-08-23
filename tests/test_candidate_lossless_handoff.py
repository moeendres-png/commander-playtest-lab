from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from commander_lab.candidates.contracts import (
    STRUCTURAL_SIMULATION_DECISION_AUTHORITY,
    TACTICAL_DECISION_AUTHORITY,
    XMAGE_TARGET_RULES_AUTHORITY,
)
from commander_lab.candidates.models import (
    DeckCandidate,
    DeckCandidateSet,
    FutureXmageScenario,
    SourceIdentity,
)
from commander_lab.candidates.pipeline import build_simulation_queue
from commander_lab.candidates.validation import (
    CardHardValidityRecord,
    HardValidationContext,
    validate_candidate_set,
)

COMMANDERS = ("Commander Alpha", "Commander Beta")
IDENTITY = ("R", "U", "W")


def _card(name: str, *, quantity: int = 1, identity: str = "") -> CardHardValidityRecord:
    return CardHardValidityRecord(
        oracle_name=name,
        owned_quantity=quantity,
        target_available_quantity=quantity,
        color_identity=frozenset(identity),
        commander_legality="legal",
    )


def _context(extra: dict[str, CardHardValidityRecord] | None = None) -> HardValidationContext:
    cards = {name: _card(name) for name in COMMANDERS}
    cards.update({f"Card {index:03d}": _card(f"Card {index:03d}") for index in range(180)})
    cards["Plains"] = _card("Plains", quantity=100, identity="W")
    if extra:
        cards.update(extra)
    return HardValidationContext(
        target_deck_id="fixture/current",
        expected_commanders=COMMANDERS,
        commander_identity=frozenset(IDENTITY),
        cards=cards,
    )


def _base_mainboard() -> dict[str, int]:
    return {f"Card {index:03d}": 1 for index in range(98)}


def _candidate(
    candidate_id: str,
    *,
    mainboard: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DeckCandidate:
    return DeckCandidate(
        candidate_id=candidate_id,
        candidate_label=candidate_id,
        commander_names=COMMANDERS,
        mainboard=mainboard or _base_mainboard(),
        metadata=metadata or {},
    )


def _candidate_set(*candidates: DeckCandidate) -> DeckCandidateSet:
    return DeckCandidateSet(
        candidate_set_id="test-set",
        created_at=datetime(2026, 8, 24, tzinfo=UTC),
        source_identity=SourceIdentity(
            provider="test",
            source_ref="unit-fixture",
            target_deck_id="fixture/current",
        ),
        commander_identity=IDENTITY,
        candidate_count=len(candidates),
        candidates=candidates,
    )


def _prepare(*candidates: DeckCandidate):
    normalized, report = validate_candidate_set(_candidate_set(*candidates), _context())
    return normalized, report, build_simulation_queue(normalized, report)


@pytest.mark.parametrize(
    ("metadata_key", "metadata_value"),
    [
        ("objective_prior", -1_000_000.0),
        ("meta_distance", 1_000_000.0),
        ("structural_score", -9999.0),
        ("fidelity_tier", "UNSUPPORTED"),
        ("external_routing", "EXTERNAL_RULES_REQUIRED"),
        ("tactical_routing", "TACTICAL_REQUIRED"),
        ("screening_only", True),
        ("qd_archive_membership", False),
        ("finalist_membership", False),
        ("current_distance", 1.0),
    ],
)
def test_heuristic_and_fidelity_metadata_never_blocks_queue(
    metadata_key: str,
    metadata_value: object,
) -> None:
    normalized, report, (queue, invariant) = _prepare(
        _candidate("candidate-a", metadata={metadata_key: metadata_value})
    )
    assert normalized.candidates[0].hard_validity == "PASS"
    assert report.hard_valid_unique_count == 1
    assert queue.output_simulation_queue_count == 1
    assert queue.candidates[0].candidate_id == "candidate-a"
    assert invariant.no_pre_simulation_heuristic_can_remove is True


def test_unusual_land_count_remains_if_hard_valid() -> None:
    board = {"Plains": 40}
    board.update({f"Card {index:03d}": 1 for index in range(58)})
    candidate = _candidate("low-convention-land-shape", mainboard=board)
    candidate = candidate.model_copy(update={"land_count": 40})
    normalized, report = validate_candidate_set(_candidate_set(candidate), _context())
    queue, _invariant = build_simulation_queue(normalized, report)
    assert report.hard_valid_unique_count == 1
    assert queue.output_simulation_queue_count == 1


def test_hard_invalid_deck_is_blocked() -> None:
    board = _base_mainboard()
    board.pop("Card 097")
    normalized, report = validate_candidate_set(
        _candidate_set(_candidate("invalid-size", mainboard=board)),
        _context(),
    )
    queue, invariant = build_simulation_queue(normalized, report)
    result = report.results[0]
    assert result.hard_validity == "FAIL"
    assert "DECK_SIZE_INVALID" in result.hard_validity_reasons
    assert queue.output_simulation_queue_count == 0
    assert invariant.lossless_handoff is True


def test_identical_duplicate_is_deduplicated_with_provenance() -> None:
    normalized, report = validate_candidate_set(
        _candidate_set(_candidate("source-a"), _candidate("source-b")),
        _context(),
    )
    queue, invariant = build_simulation_queue(normalized, report)
    assert report.hard_valid_candidate_count == 2
    assert report.duplicate_identical_deck_count == 1
    assert report.hard_valid_unique_count == 1
    assert queue.output_simulation_queue_count == 1
    assert queue.candidates[0].source_candidate_ids == ("source-a", "source-b")
    duplicate = next(row for row in report.results if row.duplicate_identical_deck)
    assert duplicate.hard_validity == "PASS"
    assert duplicate.hard_validity_reasons == ("DUPLICATE_IDENTICAL_DECK",)
    assert duplicate.duplicate_of_candidate_id == "source-a"
    assert invariant.every_hard_valid_unique_candidate_queued is True


def test_structural_and_tactical_have_no_decision_authority() -> None:
    assert STRUCTURAL_SIMULATION_DECISION_AUTHORITY is False
    assert TACTICAL_DECISION_AUTHORITY is False
    assert XMAGE_TARGET_RULES_AUTHORITY is True


def test_future_xmage_contract_is_strictly_four_player() -> None:
    FutureXmageScenario(
        candidate_id="candidate-a",
        deck_hash="a" * 64,
        opponent_deck_ids=("opp-1", "opp-2", "opp-3"),
        seat=0,
        scenario_id="scenario-a",
        seed=1,
        xmage_commit="future-commit",
        bridge_version="bridge-v1",
        pilot_identity="our-pilot",
        pilot_version="pilot-v1",
        decision_policy_version="policy-v1",
    )
    with pytest.raises(ValidationError):
        FutureXmageScenario.model_validate(
            {
                "candidate_id": "candidate-a",
                "deck_hash": "a" * 64,
                "opponent_deck_ids": ["opp-1", "opp-2", "opp-3"],
                "player_count": 3,
                "seat": 0,
                "scenario_id": "scenario-a",
                "seed": 1,
                "xmage_commit": "future-commit",
                "bridge_version": "bridge-v1",
                "pilot_identity": "our-pilot",
                "pilot_version": "pilot-v1",
                "decision_policy_version": "policy-v1",
            }
        )


@settings(max_examples=60, deadline=None)
@given(
    variant_indexes=st.lists(
        st.integers(min_value=98, max_value=179), min_size=1, max_size=40, unique=True
    ),
    duplicate_sources=st.integers(min_value=0, max_value=8),
)
def test_property_simulation_queue_equals_unique_hard_valid_candidates(
    variant_indexes: list[int],
    duplicate_sources: int,
) -> None:
    candidates: list[DeckCandidate] = []
    for ordinal, variant_index in enumerate(variant_indexes):
        board = _base_mainboard()
        board.pop("Card 097")
        board[f"Card {variant_index:03d}"] = 1
        candidates.append(
            _candidate(
                f"variant-{ordinal}",
                mainboard=board,
                metadata={
                    "objective_prior": -float(ordinal),
                    "meta_distance": float(ordinal) * 1000,
                    "fidelity_tier": "UNSUPPORTED" if ordinal % 2 else "STRUCTURAL",
                    "qd_archive_membership": False,
                },
            )
        )
    for ordinal in range(duplicate_sources):
        candidates.append(_candidate(f"duplicate-{ordinal}", mainboard=_base_mainboard()))

    normalized, report = validate_candidate_set(_candidate_set(*candidates), _context())
    queue, invariant = build_simulation_queue(normalized, report)
    expected_ids = {
        row.candidate_id
        for row in report.results
        if row.hard_validity == "PASS" and not row.duplicate_identical_deck
    }
    queued_ids = {row.candidate_id for row in queue.candidates}
    assert queued_ids == expected_ids
    assert queue.output_simulation_queue_count == report.hard_valid_unique_count
    assert invariant.lossless_handoff is True


def test_sixty_hard_valid_unique_candidates_losslessly_queue() -> None:
    candidates: list[DeckCandidate] = []
    for ordinal, variant_index in enumerate(range(98, 158)):
        board = _base_mainboard()
        board.pop("Card 097")
        board[f"Card {variant_index:03d}"] = 1
        candidates.append(
            _candidate(
                f"bulk-{ordinal:02d}",
                mainboard=board,
                metadata={
                    "objective_prior": -1_000_000.0 - ordinal,
                    "meta_distance": 1_000_000.0 + ordinal,
                    "structural_score": -9999.0,
                    "fidelity_tier": "UNSUPPORTED",
                    "qd_archive_membership": False,
                    "finalist_membership": False,
                    "current_distance": 1.0,
                },
            )
        )
    normalized, report = validate_candidate_set(_candidate_set(*candidates), _context())
    queue, invariant = build_simulation_queue(normalized, report)
    assert report.hard_valid_unique_count == 60
    assert queue.input_hard_valid_unique_count == 60
    assert queue.output_simulation_queue_count == 60
    assert len({row.candidate_id for row in queue.candidates}) == 60
    assert invariant.every_hard_valid_unique_candidate_queued is True
    assert invariant.no_pre_simulation_heuristic_can_remove is True
