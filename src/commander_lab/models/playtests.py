from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import FrozenModel, MutableModel


PLAYTEST_SCHEMA_VERSION = "1.0.0"
CALIBRATION_SCHEMA_VERSION = "1.0.0"


class EvidenceSplit(StrEnum):
    UNSPLIT = "unsplit"
    TRAIN = "train"
    VALIDATION = "validation"
    EXCLUDED = "excluded"


class SplitStrategy(StrEnum):
    STABLE_HASH = "stable_hash"
    CHRONOLOGICAL = "chronological"


class CalibrationStatus(StrEnum):
    NOT_RUN = "not_run"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PROVISIONAL = "provisional"
    VALIDATED_INTERNAL_HOLDOUT = "validated_internal_holdout"
    REJECTED_ON_VALIDATION = "rejected_on_validation"
    FAILED = "failed"


class ParameterDecision(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_SIGNAL = "no_signal"
    ACCEPTED_INTERNAL_HOLDOUT = "accepted_internal_holdout"
    REJECTED_VALIDATION = "rejected_validation"


class PlaytestParticipant(MutableModel):
    player_id: str = Field(min_length=1)
    player_name: str | None = None
    deck_name: str = Field(min_length=1)
    deck_version: str = Field(default="unversioned", min_length=1)
    deck_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    commander_names: list[str] = Field(default_factory=list)
    seat: int = Field(ge=0)
    placement: int | None = Field(default=None, ge=1)
    final_life: int | None = None
    mulligans: int | None = Field(default=None, ge=0)
    starting_hand_lands: int | None = Field(default=None, ge=0, le=7)
    lands_played: int | None = Field(default=None, ge=0)
    first_ramp_turn: int | None = Field(default=None, ge=1)
    ramp_events: int | None = Field(default=None, ge=0)
    first_commander_cast_turn: int | None = Field(default=None, ge=1)
    commander_casts: int | None = Field(default=None, ge=0)
    commander_removals_received: int | None = Field(default=None, ge=0)
    removal_events: int | None = Field(default=None, ge=0)
    first_independent_draw_engine_turn: int | None = Field(default=None, ge=1)
    independent_draw_engines: int | None = Field(default=None, ge=0)
    boardwipes_cast: int | None = Field(default=None, ge=0)
    boardwipes_seen: int | None = Field(default=None, ge=0)
    successful_rebuilds: int | None = Field(default=None, ge=0)
    rebuilt_after_wipe: bool | None = None
    ishai_peak_power: float | None = Field(default=None, ge=0.0)
    ishai_power_by_turn: dict[int, float] = Field(default_factory=dict)
    korvold_cards_drawn: int | None = Field(default=None, ge=0)
    was_archenemy: bool | None = None
    archenemy_events: int | None = Field(default=None, ge=0)
    win_axis: str | None = None
    loss_causes: list[str] = Field(default_factory=list)
    dead_cards: list[str] = Field(default_factory=list)
    sequencing_errors: list[str] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_observations(self) -> PlaytestParticipant:
        if self.placement == 1 and self.loss_causes:
            raise ValueError("a first-place participant cannot have loss_causes")
        if self.ishai_power_by_turn and any(turn < 1 for turn in self.ishai_power_by_turn):
            raise ValueError("Ishai power observation turns must be positive")
        if self.ishai_power_by_turn and self.ishai_peak_power is not None:
            if max(self.ishai_power_by_turn.values()) > self.ishai_peak_power + 1e-9:
                raise ValueError("ishai_peak_power cannot be below an observed turn value")
        return self


class RealPlaytest(MutableModel):
    schema_version: Literal["1.0.0"] = PLAYTEST_SCHEMA_VERSION
    dataset_version: str = Field(default="unversioned", min_length=1)
    game_id: str = Field(min_length=1)
    played_on: date | None = None
    pod_size: int = Field(ge=2, le=10)
    participants: list[PlaytestParticipant]
    turns: int | None = Field(default=None, ge=0)
    winner_player_ids: list[str] = Field(default_factory=list)
    end_reason: str | None = None
    starting_player_id: str | None = None
    freeform_log: str | None = None
    source_file: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    imported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_split: EvidenceSplit = EvidenceSplit.UNSPLIT
    validated: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    excluded_reason: str | None = None

    @model_validator(mode="after")
    def participants_match_pod(self) -> RealPlaytest:
        if len(self.participants) != self.pod_size:
            raise ValueError("participant count must equal pod_size")
        ids = {participant.player_id for participant in self.participants}
        if len(ids) != len(self.participants):
            raise ValueError("participant ids must be unique")
        seats = {participant.seat for participant in self.participants}
        if len(seats) != len(self.participants):
            raise ValueError("participant seats must be unique")
        if not set(self.winner_player_ids).issubset(ids):
            raise ValueError("winner ids must reference participants")
        if self.starting_player_id is not None and self.starting_player_id not in ids:
            raise ValueError("starting_player_id must reference a participant")
        if self.validated and self.validation_errors:
            raise ValueError("validated games cannot contain validation_errors")
        return self


class PlaytestDatasetManifest(FrozenModel):
    schema_version: Literal["1.0.0"] = PLAYTEST_SCHEMA_VERSION
    dataset_id: str
    dataset_version: str
    created_at: datetime
    updated_at: datetime
    game_ids: tuple[str, ...]
    game_hashes: dict[str, str]
    data_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_files: tuple[str, ...] = ()
    validated_games: int = Field(ge=0)
    excluded_games: int = Field(ge=0)
    split_strategy: SplitStrategy | None = None
    split_seed: int | None = Field(default=None, ge=0)
    train_fraction: float | None = Field(default=None, gt=0.0, lt=1.0)
    split_assignments: dict[str, EvidenceSplit] = Field(default_factory=dict)
    split_sealed_at: datetime | None = None


class DistributionSummary(FrozenModel):
    observations: int = Field(ge=0)
    missing: int = Field(ge=0)
    mean: float | None = None
    median: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    q25: float | None = None
    q75: float | None = None
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    mean_interval: tuple[float, float] | None = None


class CategoryEstimate(FrozenModel):
    count: int = Field(ge=0)
    total: int = Field(ge=0)
    proportion: float = Field(ge=0.0, le=1.0)
    interval: tuple[float, float]


class MetricComparison(FrozenModel):
    deck_key: str
    metric: str
    split: EvidenceSplit
    real: DistributionSummary
    simulated: DistributionSummary
    mean_delta_real_minus_simulated: float | None = None
    comparison_status: Literal["available", "insufficient_real", "insufficient_simulated"]
    notes: tuple[str, ...] = ()


class CalibrationParameterResult(FrozenModel):
    deck_key: str
    metric: str
    parameter_name: str
    decision: ParameterDecision
    train_real_observations: int = Field(ge=0)
    validation_real_observations: int = Field(ge=0)
    train_simulated_observations: int = Field(ge=0)
    validation_simulated_observations: int = Field(ge=0)
    baseline_value: float = 1.0
    proposed_value: float | None = None
    accepted_value: float | None = None
    train_difference_interval: tuple[float, float] | None = None
    validation_error_before: float | None = None
    validation_error_after: float | None = None
    validation_improvement_fraction: float | None = None
    rationale: tuple[str, ...] = ()


class CalibrationReport(FrozenModel):
    schema_version: Literal["1.0.0"] = CALIBRATION_SCHEMA_VERSION
    calibration_id: str
    created_at: datetime
    dataset_id: str
    dataset_version: str
    dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_deck_versions: dict[str, str] = Field(default_factory=dict)
    version_conflicts: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    simulation_source_hashes: dict[str, str]
    simulation_run_ids: tuple[str, ...] = ()
    simulation_master_seeds: tuple[int, ...] = ()
    simulation_estimate_types: tuple[str, ...] = ()
    simulated_matches_total: int = Field(default=0, ge=0)
    simulated_matches_used: int = Field(default=0, ge=0)
    simulated_matches_excluded: int = Field(default=0, ge=0)
    simulated_exclusion_reasons: dict[str, int] = Field(default_factory=dict)
    split_strategy: SplitStrategy
    split_seed: int = Field(ge=0)
    train_game_ids: tuple[str, ...]
    validation_game_ids: tuple[str, ...]
    excluded_game_ids: tuple[str, ...]
    status: CalibrationStatus
    comparisons: tuple[MetricComparison, ...]
    categorical_real: dict[str, dict[str, CategoryEstimate]] = Field(default_factory=dict)
    categorical_simulated: dict[str, dict[str, CategoryEstimate]] = Field(default_factory=dict)
    parameter_results: tuple[CalibrationParameterResult, ...]
    accepted_parameters: dict[str, float]
    confidence_level: float = Field(gt=0.0, lt=1.0)
    bootstrap_samples: int = Field(ge=100)
    internal_validation_only: bool = True
    independent_confirmation: bool = False
    engine_parameters_modified: bool = False
    calibration_profile_applied: bool = False
    external_engine_validation_pending: bool = True
    warnings: tuple[str, ...] = ()
    methodology: tuple[str, ...] = ()
