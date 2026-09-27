from __future__ import annotations

from types import SimpleNamespace

import pytest

from commander_lab.whole_deck.optimizer_advancement import (
    CandidateAdvancementStatus,
    CandidatePairedEvidence,
    ModelResolutionDecisionPolicy,
    assess_candidate_advancement,
    build_confirmatory_frontier,
    load_model_resolution_decision_policy,
    merge_pairing_conditions,
    require_confirmatory_candidate,
)


def _scenarios() -> tuple[SimpleNamespace, ...]:
    return tuple(
        SimpleNamespace(
            scenario_id=f"scenario-{index}",
            own_seat=index % 4 + 1,
            opponent_deck_ids=("opponent/a", "opponent/b", "opponent/c"),
        )
        for index in range(8)
    )


def _policy() -> ModelResolutionDecisionPolicy:
    return ModelResolutionDecisionPolicy(
        source_identity="a" * 64,
        metric="placement_improvement",
        effective_resolution=0.375,
        paired_candidate_comparisons_allowed=True,
    )


def _evidence() -> CandidatePairedEvidence:
    rows = tuple(
        {
            "scenario_id": scenario.scenario_id,
            "own_seat": scenario.own_seat,
            "opponent_deck_ids": list(scenario.opponent_deck_ids),
            "baseline_placement": 3.0,
            "variant_placement": 2.0,
        }
        for scenario in _scenarios()
    )
    return CandidatePairedEvidence(
        candidate_id="candidate/one",
        deck_hash="b" * 64,
        budget=len(rows),
        interval_low=0.9,
        interval_high=1.1,
        observations=rows,
        pairing_conditions={
            "candidates_share_match": True,
            "same_scenarios": True,
            "same_match_seeds": True,
            "same_own_seats": True,
            "same_opponent_seat_assignments": True,
            "same_pilot_configuration": True,
            "same_turn_cap": True,
            "common_random_numbers": True,
        },
    )


def test_merge_pairing_conditions_remains_available_for_archival_readers() -> None:
    merged = merge_pairing_conditions(
        (
            {"candidates_share_match": False, "same_scenarios": True},
            {"candidates_share_match": False, "same_scenarios": True},
        )
    )
    assert merged == {"candidates_share_match": True, "same_scenarios": True}


def test_legacy_effective_resolution_can_never_authorize_confirmatory() -> None:
    assessment = assess_candidate_advancement(
        _evidence(),
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert assessment.status == CandidateAdvancementStatus.RETIRED_1E_2F_REQUIRED
    assert not assessment.eligible_for_confirmatory
    assert assessment.pooled_direction == "not_evaluated_legacy_retired"
    assert "legacy_effective_resolution_retired_use_optimizer_v2_1E_2F" in assessment.failed_axes


def test_legacy_frontier_is_never_a_machine_whitelist() -> None:
    evidence = _evidence()
    frontier = build_confirmatory_frontier(
        {evidence.candidate_id: evidence},
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert frontier.eligible_candidate_ids == ()
    with pytest.raises(RuntimeError, match="legacy candidate advancement is retired"):
        require_confirmatory_candidate(frontier, evidence.candidate_id)


def test_model_resolution_loader_is_hard_retired(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="effective_resolution is retired"):
        load_model_resolution_decision_policy(tmp_path)
