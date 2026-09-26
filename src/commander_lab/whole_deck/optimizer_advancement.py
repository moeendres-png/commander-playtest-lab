from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from commander_lab.models import FrozenModel
from commander_lab.storage import sha256_value

LEGACY_OPTIMIZER_ADVANCEMENT_REASON = "legacy_effective_resolution_retired_use_optimizer_v2_1E_2F"


class CandidateAdvancementStatus(StrEnum):
    RETIRED_1E_2F_REQUIRED = "RETIRED_1E_2F_REQUIRED"
    ELIGIBLE_CONFIRMATORY = "ELIGIBLE_CONFIRMATORY"
    BLOCKED_MODEL_RESOLUTION = "BLOCKED_MODEL_RESOLUTION"
    BLOCKED_POOLED_EFFECT = "BLOCKED_POOLED_EFFECT"
    BLOCKED_PARTITION_COVERAGE = "BLOCKED_PARTITION_COVERAGE"
    BLOCKED_PAIRING = "BLOCKED_PAIRING"
    BLOCKED_SEAT_ROBUSTNESS = "BLOCKED_SEAT_ROBUSTNESS"
    BLOCKED_SCENARIO_ROBUSTNESS = "BLOCKED_SCENARIO_ROBUSTNESS"


class ModelResolutionDecisionPolicy(FrozenModel):
    """Archival model only; effective_resolution is never operative after 1E/2F."""

    source_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    metric: str
    effective_resolution: float = Field(gt=0.0)
    paired_candidate_comparisons_allowed: bool
    evidence_class: str = "structural_model_estimates"
    truth_boundary: str = (
        "historical measured Structural resolution; prohibited as a promotion, elimination, "
        "or equivalence threshold in the current Optimizer v2 decision path"
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
    evidence_context: str = "legacy_exploratory_advancement_retired"
    evidence_class: str = "structural_model_estimates"
    truth_boundary: str = (
        "legacy compatibility artifact only; never authorizes confirmatory advancement"
    )


class ConfirmatoryFrontier(FrozenModel):
    model_resolution_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_resolution: float = Field(gt=0.0)
    eligible_candidate_ids: tuple[str, ...]
    assessments: tuple[CandidateAdvancementAssessment, ...]
    confirmatory_evidence_consumed: bool = False
    sealed_holdout_evidence_consumed: bool = False
    canonical_deck_mutation: bool = False
    evidence_context: str = "legacy_advancement_gate_retired"

    @property
    def frontier_hash(self) -> str:
        return sha256_value(self.model_dump(mode="json"))


def load_model_resolution_decision_policy(root: str | Path) -> ModelResolutionDecisionPolicy:
    del root
    raise RuntimeError(
        "MODEL_RESOLUTION effective_resolution is retired for operative decisions; "
        "use the manifest-bound Optimizer v2 1E/2F policy"
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


def _opponent_group(value: object) -> str:
    if not isinstance(value, (list, tuple)):
        raise TypeError("opponent_deck_ids must be a sequence")
    return "|".join(sorted(str(item) for item in value))


def _expected_axes(
    full_scenarios: Sequence[Any],
) -> tuple[tuple[str, ...], tuple[int, ...], tuple[str, ...]]:
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


def assess_candidate_advancement(
    evidence: CandidatePairedEvidence,
    *,
    full_scenarios: Sequence[Any],
    model_resolution: ModelResolutionDecisionPolicy,
) -> CandidateAdvancementAssessment:
    """Return a fail-closed archival assessment; never evaluate effective_resolution."""

    expected_ids, required_seats, required_groups = _expected_axes(full_scenarios)
    observed_ids = tuple(
        str(row.get("scenario_id"))
        for row in evidence.observations
        if isinstance(row.get("scenario_id"), str)
    )
    full_partition = (
        evidence.budget == len(expected_ids)
        and len(observed_ids) == len(set(observed_ids))
        and tuple(sorted(observed_ids)) == tuple(sorted(expected_ids))
    )
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
    return CandidateAdvancementAssessment(
        candidate_id=evidence.candidate_id,
        deck_hash=evidence.deck_hash,
        status=CandidateAdvancementStatus.RETIRED_1E_2F_REQUIRED,
        eligible_for_confirmatory=False,
        pooled_direction="not_evaluated_legacy_retired",
        interval_low=evidence.interval_low,
        interval_high=evidence.interval_high,
        effective_resolution=model_resolution.effective_resolution,
        budget=evidence.budget,
        full_partition_games=len(expected_ids),
        full_partition_evaluated=full_partition,
        pairing_conditions_passed=pairing_passed,
        required_seats=required_seats,
        seat_effects={},
        missing_seats=required_seats,
        seat_direction_consistent=False,
        required_scenario_groups=required_groups,
        scenario_group_effects={},
        missing_scenario_groups=required_groups,
        scenario_direction_consistent=False,
        failed_axes=(LEGACY_OPTIMIZER_ADVANCEMENT_REASON,),
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
    return ConfirmatoryFrontier(
        model_resolution_identity=model_resolution.source_identity,
        effective_resolution=model_resolution.effective_resolution,
        eligible_candidate_ids=(),
        assessments=assessments,
    )


def require_confirmatory_candidate(
    frontier: ConfirmatoryFrontier,
    candidate_id: str,
) -> CandidateAdvancementAssessment:
    for assessment in frontier.assessments:
        if assessment.candidate_id == candidate_id:
            raise RuntimeError(
                "legacy candidate advancement is retired; use Optimizer v2 1E/2F confirmatory"
            )
    raise RuntimeError("candidate has no exploratory advancement assessment")
