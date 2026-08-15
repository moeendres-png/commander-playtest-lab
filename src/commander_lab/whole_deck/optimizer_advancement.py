from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from statistics import fmean
from typing import Any

from pydantic import Field, model_validator

from commander_lab.models import FrozenModel
from commander_lab.storage import sha256_value


class CandidateAdvancementStatus(StrEnum):
    ELIGIBLE_CONFIRMATORY = "ELIGIBLE_CONFIRMATORY"
    BLOCKED_MODEL_RESOLUTION = "BLOCKED_MODEL_RESOLUTION"
    BLOCKED_POOLED_EFFECT = "BLOCKED_POOLED_EFFECT"
    BLOCKED_PARTITION_COVERAGE = "BLOCKED_PARTITION_COVERAGE"
    BLOCKED_PAIRING = "BLOCKED_PAIRING"
    BLOCKED_SEAT_ROBUSTNESS = "BLOCKED_SEAT_ROBUSTNESS"
    BLOCKED_SCENARIO_ROBUSTNESS = "BLOCKED_SCENARIO_ROBUSTNESS"


class ModelResolutionDecisionPolicy(FrozenModel):
    source_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    metric: str
    effective_resolution: float = Field(gt=0.0)
    paired_candidate_comparisons_allowed: bool
    evidence_class: str = "structural_model_estimates"
    truth_boundary: str = (
        "measured Structural decision resolution only; not empirical Commander performance"
    )


class CandidatePairedEvidence(FrozenModel):
    candidate_id: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget: int = Field(ge=1)
    interval_low: float
    interval_high: float
    observations: tuple[dict[str, Any], ...]
    pairing_conditions: dict[str, bool]

    @model_validator(mode="after")
    def valid_evidence(self) -> CandidatePairedEvidence:
        if self.interval_low > self.interval_high:
            raise ValueError("paired interval low must not exceed interval high")
        if self.budget != len(self.observations):
            raise ValueError("paired evidence budget must equal observation count")
        return self


class CandidateAdvancementAssessment(FrozenModel):
    candidate_id: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: CandidateAdvancementStatus
    eligible_for_confirmatory: bool
    pooled_direction: str
    interval_low: float
    interval_high: float
    effective_resolution: float
    budget: int
    full_partition_games: int
    full_partition_evaluated: bool
    pairing_conditions_passed: bool
    required_seats: tuple[int, ...]
    seat_effects: dict[str, float]
    missing_seats: tuple[int, ...]
    seat_direction_consistent: bool
    required_scenario_groups: tuple[str, ...]
    scenario_group_effects: dict[str, float]
    missing_scenario_groups: tuple[str, ...]
    scenario_direction_consistent: bool
    failed_axes: tuple[str, ...]
    evidence_context: str = "exploratory"
    evidence_class: str = "structural_model_estimates"
    truth_boundary: str = (
        "eligibility for fresh confirmatory evidence only; not a promotion or canonical deck change"
    )


class ConfirmatoryFrontier(FrozenModel):
    model_resolution_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_resolution: float = Field(gt=0.0)
    eligible_candidate_ids: tuple[str, ...]
    assessments: tuple[CandidateAdvancementAssessment, ...]
    confirmatory_evidence_consumed: bool = False
    sealed_holdout_evidence_consumed: bool = False
    canonical_deck_mutation: bool = False
    evidence_context: str = "exploratory_advancement_gate"

    @property
    def frontier_hash(self) -> str:
        return sha256_value(self.model_dump(mode="json"))


def load_model_resolution_decision_policy(root: str | Path) -> ModelResolutionDecisionPolicy:
    path = Path(root).resolve() / "data" / "diagnostics" / "MODEL_RESOLUTION_CURRENT.json"
    if not path.is_file():
        raise RuntimeError("current model-resolution state is missing")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("status") != "MEASURED":
        raise RuntimeError("candidate advancement requires measured current model resolution")
    metric = payload.get("metric")
    resolution = payload.get("effective_resolution")
    decision_use = payload.get("decision_use")
    if metric != "placement_improvement":
        raise RuntimeError("candidate advancement requires placement_improvement resolution")
    if isinstance(resolution, bool) or not isinstance(resolution, int | float) or resolution <= 0:
        raise RuntimeError("current model-resolution value is invalid")
    if not isinstance(decision_use, dict):
        raise RuntimeError("current model-resolution decision-use policy is missing")
    paired_allowed = decision_use.get("paired_candidate_comparisons_allowed") is True
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return ModelResolutionDecisionPolicy(
        source_identity=sha256_value(canonical),
        metric=str(metric),
        effective_resolution=float(resolution),
        paired_candidate_comparisons_allowed=paired_allowed,
    )


def merge_pairing_conditions(rows: Sequence[Mapping[str, object]]) -> dict[str, bool]:
    if not rows:
        return {}
    keys = sorted({str(key) for row in rows for key in row})
    merged: dict[str, bool] = {}
    for key in keys:
        values = [row.get(key) for row in rows]
        if key == "candidates_share_match":
            merged[key] = all(value is False for value in values)
        else:
            merged[key] = all(value is True for value in values)
    return merged


def _paired_delta(row: Mapping[str, object]) -> float:
    baseline = row.get("baseline_placement")
    variant = row.get("variant_placement")
    if isinstance(baseline, bool) or not isinstance(baseline, int | float):
        raise TypeError("baseline_placement must be numeric")
    if isinstance(variant, bool) or not isinstance(variant, int | float):
        raise TypeError("variant_placement must be numeric")
    return float(baseline) - float(variant)


def _opponent_group(value: object) -> str:
    if not isinstance(value, (list, tuple)):
        raise TypeError("opponent_deck_ids must be a sequence")
    return "|".join(sorted(str(item) for item in value))


def _expected_axes(full_scenarios: Sequence[Any]) -> tuple[tuple[str, ...], tuple[int, ...], tuple[str, ...]]:
    if not full_scenarios:
        raise ValueError("candidate advancement requires a frozen exploratory scenario partition")
    scenario_ids: list[str] = []
    seats: set[int] = set()
    groups: set[str] = set()
    for scenario in full_scenarios:
        scenario_ids.append(str(scenario.scenario_id))
        seats.add(int(scenario.own_seat))
        groups.add(_opponent_group(scenario.opponent_deck_ids))
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("frozen exploratory scenario ids must be unique")
    return tuple(scenario_ids), tuple(sorted(seats)), tuple(sorted(groups))


def _direction(interval_low: float, interval_high: float, resolution: float) -> str:
    if interval_low > resolution:
        return "positive"
    if interval_high < -resolution:
        return "negative"
    if interval_low >= -resolution and interval_high <= resolution:
        return "equivalent"
    return "unresolved"


def _direction_consistent(values: Sequence[float], direction: str) -> bool:
    if not values:
        return False
    if direction == "positive":
        return all(value >= 0.0 for value in values)
    if direction == "negative":
        return all(value <= 0.0 for value in values)
    return False


def assess_candidate_advancement(
    evidence: CandidatePairedEvidence,
    *,
    full_scenarios: Sequence[Any],
    model_resolution: ModelResolutionDecisionPolicy,
) -> CandidateAdvancementAssessment:
    expected_ids, required_seats, required_groups = _expected_axes(full_scenarios)
    observed_ids: list[str] = []
    seat_rows: dict[int, list[float]] = defaultdict(list)
    scenario_rows: dict[str, list[float]] = defaultdict(list)
    for row in evidence.observations:
        scenario_id = row.get("scenario_id")
        own_seat = row.get("own_seat")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise TypeError("scenario_id must be non-empty text")
        if isinstance(own_seat, bool) or not isinstance(own_seat, int):
            raise TypeError("own_seat must be an integer")
        delta = _paired_delta(row)
        observed_ids.append(scenario_id)
        seat_rows[own_seat].append(delta)
        scenario_rows[_opponent_group(row.get("opponent_deck_ids"))].append(delta)

    full_partition = (
        evidence.budget == len(expected_ids)
        and len(observed_ids) == len(set(observed_ids))
        and tuple(sorted(observed_ids)) == tuple(sorted(expected_ids))
    )
    seat_effects = {str(seat): fmean(values) for seat, values in sorted(seat_rows.items())}
    scenario_effects = {group: fmean(values) for group, values in sorted(scenario_rows.items())}
    missing_seats = tuple(seat for seat in required_seats if str(seat) not in seat_effects)
    missing_groups = tuple(group for group in required_groups if group not in scenario_effects)

    required_pairing = (
        "candidates_share_match",
        "same_scenarios",
        "same_match_seeds",
        "same_own_seats",
        "same_opponent_seat_assignments",
        "same_pilot_configuration",
        "same_turn_cap",
        "common_random_numbers",
    )
    pairing_passed = all(evidence.pairing_conditions.get(key) is True for key in required_pairing)
    direction = _direction(
        evidence.interval_low,
        evidence.interval_high,
        model_resolution.effective_resolution,
    )
    seat_consistent = not missing_seats and _direction_consistent(
        tuple(seat_effects[str(seat)] for seat in required_seats),
        direction,
    )
    scenario_consistent = not missing_groups and _direction_consistent(
        tuple(scenario_effects[group] for group in required_groups),
        direction,
    )

    failed: list[str] = []
    if not model_resolution.paired_candidate_comparisons_allowed:
        failed.append("model_resolution_decision_use")
    if direction != "positive":
        failed.append("pooled_effect_above_resolution")
    if not full_partition:
        failed.append("full_exploratory_partition")
    if not pairing_passed:
        failed.append("paired_execution_contract")
    if not seat_consistent:
        failed.append("seat_stratified_direction_consistency")
    if not scenario_consistent:
        failed.append("admissible_scenario_direction_consistency")

    if not model_resolution.paired_candidate_comparisons_allowed:
        status = CandidateAdvancementStatus.BLOCKED_MODEL_RESOLUTION
    elif direction != "positive":
        status = CandidateAdvancementStatus.BLOCKED_POOLED_EFFECT
    elif not full_partition:
        status = CandidateAdvancementStatus.BLOCKED_PARTITION_COVERAGE
    elif not pairing_passed:
        status = CandidateAdvancementStatus.BLOCKED_PAIRING
    elif not seat_consistent:
        status = CandidateAdvancementStatus.BLOCKED_SEAT_ROBUSTNESS
    elif not scenario_consistent:
        status = CandidateAdvancementStatus.BLOCKED_SCENARIO_ROBUSTNESS
    else:
        status = CandidateAdvancementStatus.ELIGIBLE_CONFIRMATORY

    return CandidateAdvancementAssessment(
        candidate_id=evidence.candidate_id,
        deck_hash=evidence.deck_hash,
        status=status,
        eligible_for_confirmatory=status == CandidateAdvancementStatus.ELIGIBLE_CONFIRMATORY,
        pooled_direction=direction,
        interval_low=evidence.interval_low,
        interval_high=evidence.interval_high,
        effective_resolution=model_resolution.effective_resolution,
        budget=evidence.budget,
        full_partition_games=len(expected_ids),
        full_partition_evaluated=full_partition,
        pairing_conditions_passed=pairing_passed,
        required_seats=required_seats,
        seat_effects=seat_effects,
        missing_seats=missing_seats,
        seat_direction_consistent=seat_consistent,
        required_scenario_groups=required_groups,
        scenario_group_effects=scenario_effects,
        missing_scenario_groups=missing_groups,
        scenario_direction_consistent=scenario_consistent,
        failed_axes=tuple(failed),
    )


def build_confirmatory_frontier(
    evidence_by_candidate: Mapping[str, CandidatePairedEvidence],
    *,
    full_scenarios: Sequence[Any],
    model_resolution: ModelResolutionDecisionPolicy,
) -> ConfirmatoryFrontier:
    assessments = tuple(
        assess_candidate_advancement(
            evidence_by_candidate[candidate_id],
            full_scenarios=full_scenarios,
            model_resolution=model_resolution,
        )
        for candidate_id in sorted(evidence_by_candidate)
    )
    eligible = tuple(
        row.candidate_id for row in assessments if row.eligible_for_confirmatory
    )
    return ConfirmatoryFrontier(
        model_resolution_identity=model_resolution.source_identity,
        effective_resolution=model_resolution.effective_resolution,
        eligible_candidate_ids=eligible,
        assessments=assessments,
    )


def require_confirmatory_candidate(
    frontier: ConfirmatoryFrontier,
    candidate_id: str,
) -> CandidateAdvancementAssessment:
    for assessment in frontier.assessments:
        if assessment.candidate_id != candidate_id:
            continue
        if not assessment.eligible_for_confirmatory:
            raise RuntimeError(
                "candidate is blocked from confirmatory advancement: "
                + ", ".join(assessment.failed_axes)
            )
        return assessment
    raise RuntimeError("candidate has no exploratory advancement assessment")


__all__ = [
    "CandidateAdvancementAssessment",
    "CandidateAdvancementStatus",
    "CandidatePairedEvidence",
    "ConfirmatoryFrontier",
    "ModelResolutionDecisionPolicy",
    "assess_candidate_advancement",
    "build_confirmatory_frontier",
    "load_model_resolution_decision_policy",
    "merge_pairing_conditions",
    "require_confirmatory_candidate",
]
