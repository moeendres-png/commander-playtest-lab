from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import (
    CANDIDATE_VALIDATION_REPORT_SCHEMA_VERSION,
    DECK_CANDIDATE_SET_SCHEMA_VERSION,
    FUTURE_XMAGE_SCENARIO_CONTRACT_VERSION,
    PRE_SIMULATION_INVARIANT_REPORT_SCHEMA_VERSION,
    SIMULATION_CANDIDATE_QUEUE_SCHEMA_VERSION,
)


def _clean_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("card identity cannot be blank")
    return normalized


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceIdentity(StrictModel):
    provider: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    target_deck_id: str | None = None
    builder_identity: str | None = None
    builder_version: str | None = None


class PhysicalPrinting(StrictModel):
    oracle_name: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    set_code: str | None = None
    collector_number: str | None = None
    printing_id: str | None = None

    @field_validator("oracle_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _clean_name(value)


class DeckCandidate(StrictModel):
    candidate_id: str = Field(min_length=1)
    candidate_label: str = Field(min_length=1)
    deck_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    commander_names: tuple[str, ...]
    mainboard: dict[str, int]
    physical_printings: tuple[PhysicalPrinting, ...] = ()
    design_policy: str | None = None
    design_philosophy: str | None = None
    design_hypothesis: str | None = None
    land_count: int | None = Field(default=None, ge=0)
    packages: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    current_control: bool = False
    hard_validity: Literal["UNVERIFIED", "PASS", "FAIL"] = "UNVERIFIED"
    hard_validity_reasons: tuple[str, ...] = ()
    simulation_required: bool = False

    @field_validator("commander_names")
    @classmethod
    def normalize_commanders(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        names = tuple(_clean_name(name) for name in value)
        if not names:
            raise ValueError("at least one commander is required")
        if len(set(names)) != len(names):
            raise ValueError("commander names must be unique")
        return names

    @field_validator("mainboard")
    @classmethod
    def normalize_mainboard(cls, value: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for raw_name, quantity in value.items():
            name = _clean_name(raw_name)
            if quantity < 1:
                raise ValueError(f"mainboard quantity must be positive: {name}")
            if name in normalized:
                raise ValueError(f"duplicate normalized mainboard identity: {name}")
            normalized[name] = int(quantity)
        return normalized


class DeckCandidateSet(StrictModel):
    candidate_set_id: str = Field(min_length=1)
    schema_version: str = DECK_CANDIDATE_SET_SCHEMA_VERSION
    created_at: datetime
    source_identity: SourceIdentity
    commander_identity: tuple[str, ...]
    candidate_count: int = Field(ge=0)
    candidates: tuple[DeckCandidate, ...]

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: str) -> str:
        if value != DECK_CANDIDATE_SET_SCHEMA_VERSION:
            raise ValueError(f"unsupported candidate set schema: {value}")
        return value

    @field_validator("commander_identity")
    @classmethod
    def validate_identity(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({str(symbol).upper() for symbol in value if str(symbol)}))
        if any(symbol not in {"W", "U", "B", "R", "G"} for symbol in normalized):
            raise ValueError(f"invalid commander color identity: {normalized}")
        return normalized

    @model_validator(mode="after")
    def count_matches(self) -> DeckCandidateSet:
        if self.candidate_count != len(self.candidates):
            raise ValueError(
                f"candidate_count={self.candidate_count} does not match candidates={len(self.candidates)}"
            )
        ids = [candidate.candidate_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate_id values must be unique within a candidate set")
        return self


class CandidateValidationResult(StrictModel):
    candidate_id: str
    deck_hash: str
    hard_validity: Literal["PASS", "FAIL"]
    hard_validity_reasons: tuple[str, ...] = ()
    duplicate_identical_deck: bool = False
    duplicate_of_candidate_id: str | None = None
    simulation_required: bool
    source_candidate_ids: tuple[str, ...]
    diagnostic_metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateValidationReport(StrictModel):
    schema_version: str = CANDIDATE_VALIDATION_REPORT_SCHEMA_VERSION
    candidate_set_id: str
    source_identity: SourceIdentity
    input_candidate_count: int
    hard_valid_candidate_count: int
    hard_invalid_candidate_count: int
    duplicate_identical_deck_count: int
    hard_valid_unique_count: int
    results: tuple[CandidateValidationResult, ...]
    hard_fail_codes_observed: tuple[str, ...]
    no_pre_simulation_heuristic_admission: bool = True


class SimulationCandidateQueueEntry(StrictModel):
    candidate_id: str
    candidate_label: str
    deck_hash: str
    commander_names: tuple[str, ...]
    mainboard: dict[str, int]
    physical_printings: tuple[PhysicalPrinting, ...] = ()
    source_candidate_set: str
    source_candidate_ids: tuple[str, ...]
    validation_status: Literal["PASS"] = "PASS"
    simulation_required: Literal[True] = True
    simulation_queue_status: Literal["QUEUED"] = "QUEUED"
    pre_simulation_elimination_reason: None = None
    current_control: bool = False
    design_policy: str | None = None
    design_philosophy: str | None = None
    design_hypothesis: str | None = None
    packages: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    diagnostic_metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationCandidateQueue(StrictModel):
    schema_version: str = SIMULATION_CANDIDATE_QUEUE_SCHEMA_VERSION
    source_candidate_set: str
    input_hard_valid_unique_count: int = Field(ge=0)
    output_simulation_queue_count: int = Field(ge=0)
    candidates: tuple[SimulationCandidateQueueEntry, ...]
    lossless_handoff: bool

    @model_validator(mode="after")
    def enforce_lossless(self) -> SimulationCandidateQueue:
        if self.input_hard_valid_unique_count != self.output_simulation_queue_count:
            raise ValueError("lossless handoff invariant violated: input/output count mismatch")
        if self.output_simulation_queue_count != len(self.candidates):
            raise ValueError("simulation queue count does not match queue entries")
        if not self.lossless_handoff:
            raise ValueError("lossless_handoff must be true for a valid queue artifact")
        if any(entry.pre_simulation_elimination_reason is not None for entry in self.candidates):
            raise ValueError("hard-valid unique queue entries cannot have elimination reasons")
        return self


class PreSimulationInvariantReport(StrictModel):
    schema_version: str = PRE_SIMULATION_INVARIANT_REPORT_SCHEMA_VERSION
    candidate_set_id: str
    input_hard_valid_unique_count: int
    output_simulation_queue_count: int
    lossless_handoff: bool
    every_hard_valid_unique_candidate_queued: bool
    no_pre_simulation_heuristic_can_remove: bool
    objective_prior_admission_authority: bool = False
    meta_distance_admission_authority: bool = False
    structural_score_admission_authority: bool = False
    fidelity_tier_admission_authority: bool = False
    qd_archive_admission_authority: bool = False
    current_nearness_admission_authority: bool = False
    structural_decision_authority: bool = False
    tactical_decision_authority: bool = False
    xmage_target_rules_authority: bool = True
    our_pilot_target_decision_policy: bool = True


class FutureXmageScenario(StrictModel):
    schema_version: str = FUTURE_XMAGE_SCENARIO_CONTRACT_VERSION
    candidate_id: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    opponent_deck_ids: tuple[str, str, str]
    player_count: Literal[4] = 4
    seat: int = Field(ge=0, le=3)
    scenario_id: str = Field(min_length=1)
    seed: int = Field(ge=0)
    xmage_commit: str = Field(min_length=1)
    bridge_version: str = Field(min_length=1)
    pilot_identity: str = Field(min_length=1)
    pilot_version: str = Field(min_length=1)
    decision_policy_version: str = Field(min_length=1)


__all__ = [
    "CandidateValidationReport",
    "CandidateValidationResult",
    "DeckCandidate",
    "DeckCandidateSet",
    "FutureXmageScenario",
    "PhysicalPrinting",
    "PreSimulationInvariantReport",
    "SimulationCandidateQueue",
    "SimulationCandidateQueueEntry",
    "SourceIdentity",
]
