from __future__ import annotations

import json
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
    rows = []
    groups = (
        ("opponent/a", "opponent/b", "opponent/c"),
        ("opponent/a", "opponent/b", "opponent/d"),
    )
    for index in range(8):
        rows.append(
            SimpleNamespace(
                scenario_id=f"scenario-{index}",
                own_seat=index % 4 + 1,
                opponent_deck_ids=groups[index % 2],
            )
        )
    return tuple(rows)


def _pairing() -> dict[str, bool]:
    return {
        "candidates_share_match": True,
        "same_scenarios": True,
        "same_match_seeds": True,
        "same_own_seats": True,
        "same_opponent_seat_assignments": True,
        "same_pilot_configuration": True,
        "same_turn_cap": True,
        "common_random_numbers": True,
    }


def _policy(*, paired_allowed: bool = True) -> ModelResolutionDecisionPolicy:
    return ModelResolutionDecisionPolicy(
        source_identity="a" * 64,
        metric="placement_improvement",
        effective_resolution=0.14285714285714324,
        paired_candidate_comparisons_allowed=paired_allowed,
    )


def _evidence(
    deltas: tuple[float, ...],
    *,
    low: float = 0.30,
    high: float = 0.70,
    budget: int | None = None,
    pairing: dict[str, bool] | None = None,
) -> CandidatePairedEvidence:
    scenarios = _scenarios()
    chosen = scenarios[: budget if budget is not None else len(scenarios)]
    rows = []
    for index, scenario in enumerate(chosen):
        delta = deltas[index]
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "own_seat": scenario.own_seat,
                "opponent_deck_ids": list(scenario.opponent_deck_ids),
                "baseline_placement": 3.0,
                "variant_placement": 3.0 - delta,
            }
        )
    return CandidatePairedEvidence(
        candidate_id="candidate/one",
        deck_hash="b" * 64,
        budget=len(rows),
        interval_low=low,
        interval_high=high,
        observations=tuple(rows),
        pairing_conditions=pairing or _pairing(),
    )


def test_merge_pairing_conditions_normalizes_candidate_isolation() -> None:
    merged = merge_pairing_conditions(
        (
            {
                "candidates_share_match": False,
                "same_scenarios": True,
                "same_match_seeds": True,
            },
            {
                "candidates_share_match": False,
                "same_scenarios": True,
                "same_match_seeds": True,
            },
        )
    )
    assert merged == {
        "candidates_share_match": True,
        "same_match_seeds": True,
        "same_scenarios": True,
    }


def test_positive_full_partition_candidate_is_confirmatory_eligible() -> None:
    evidence = _evidence((0.5,) * 8)
    assessment = assess_candidate_advancement(
        evidence,
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert assessment.status == CandidateAdvancementStatus.ELIGIBLE_CONFIRMATORY
    assert assessment.eligible_for_confirmatory
    assert assessment.full_partition_evaluated
    assert assessment.seat_direction_consistent
    assert assessment.scenario_direction_consistent
    assert assessment.failed_axes == ()


def test_pooled_effect_must_exceed_measured_resolution() -> None:
    assessment = assess_candidate_advancement(
        _evidence((0.5,) * 8, low=0.10, high=0.50),
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert assessment.status == CandidateAdvancementStatus.BLOCKED_POOLED_EFFECT
    assert "pooled_effect_above_resolution" in assessment.failed_axes


def test_partial_exploratory_partition_fails_closed() -> None:
    assessment = assess_candidate_advancement(
        _evidence((0.5,) * 8, budget=4),
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert assessment.status == CandidateAdvancementStatus.BLOCKED_PARTITION_COVERAGE
    assert not assessment.full_partition_evaluated


def test_pairing_contract_failure_blocks_advancement() -> None:
    pairing = _pairing()
    pairing["same_opponent_seat_assignments"] = False
    assessment = assess_candidate_advancement(
        _evidence((0.5,) * 8, pairing=pairing),
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert assessment.status == CandidateAdvancementStatus.BLOCKED_PAIRING
    assert not assessment.pairing_conditions_passed


def test_seat_direction_reversal_blocks_positive_pooled_candidate() -> None:
    assessment = assess_candidate_advancement(
        _evidence((1.0, 1.0, 1.0, -0.5, 1.0, 1.0, 1.0, -0.5)),
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert assessment.status == CandidateAdvancementStatus.BLOCKED_SEAT_ROBUSTNESS
    assert assessment.seat_effects["4"] < 0.0
    assert not assessment.seat_direction_consistent


def test_scenario_group_reversal_blocks_positive_pooled_candidate() -> None:
    assessment = assess_candidate_advancement(
        _evidence((1.0, -0.25, 1.0, -0.25, 1.0, -0.25, 1.0, -0.25)),
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert assessment.status == CandidateAdvancementStatus.BLOCKED_SCENARIO_ROBUSTNESS
    assert any(value < 0.0 for value in assessment.scenario_group_effects.values())
    assert not assessment.scenario_direction_consistent


def test_current_resolution_policy_can_disable_paired_advancement() -> None:
    assessment = assess_candidate_advancement(
        _evidence((0.5,) * 8),
        full_scenarios=_scenarios(),
        model_resolution=_policy(paired_allowed=False),
    )
    assert assessment.status == CandidateAdvancementStatus.BLOCKED_MODEL_RESOLUTION
    assert not assessment.eligible_for_confirmatory


def test_confirmatory_frontier_is_a_machine_whitelist() -> None:
    eligible = _evidence((0.5,) * 8)
    blocked = _evidence((1.0, 1.0, 1.0, -0.5, 1.0, 1.0, 1.0, -0.5)).model_copy(
        update={"candidate_id": "candidate/two", "deck_hash": "c" * 64}
    )
    frontier = build_confirmatory_frontier(
        {eligible.candidate_id: eligible, blocked.candidate_id: blocked},
        full_scenarios=_scenarios(),
        model_resolution=_policy(),
    )
    assert frontier.eligible_candidate_ids == (eligible.candidate_id,)
    assert require_confirmatory_candidate(frontier, eligible.candidate_id).eligible_for_confirmatory
    with pytest.raises(RuntimeError, match="blocked from confirmatory advancement"):
        require_confirmatory_candidate(frontier, blocked.candidate_id)
    with pytest.raises(RuntimeError, match="no exploratory advancement assessment"):
        require_confirmatory_candidate(frontier, "candidate/missing")


def test_model_resolution_loader_fails_closed_and_reads_current_policy(tmp_path) -> None:
    diagnostics = tmp_path / "data" / "diagnostics"
    diagnostics.mkdir(parents=True)
    path = diagnostics / "MODEL_RESOLUTION_CURRENT.json"
    path.write_text(
        json.dumps(
            {
                "status": "MEASURED",
                "metric": "placement_improvement",
                "effective_resolution": 0.14285714285714324,
                "decision_use": {"paired_candidate_comparisons_allowed": True},
            }
        ),
        encoding="utf-8",
    )
    policy = load_model_resolution_decision_policy(tmp_path)
    assert policy.effective_resolution == pytest.approx(0.14285714285714324)
    assert policy.paired_candidate_comparisons_allowed

    path.write_text(json.dumps({"status": "NEEDS_MEASUREMENT"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="requires measured"):
        load_model_resolution_decision_policy(tmp_path)
