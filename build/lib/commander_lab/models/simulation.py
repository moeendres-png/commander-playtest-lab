from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .common import FrozenModel, MutableModel


class SimulationMode(StrEnum):
    STRUCTURAL = "structural"
    TACTICAL = "tactical"
    RULES_VALIDATED = "rules_validated"


class RunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class SimulationConfig(FrozenModel):
    seed: int = Field(ge=0)
    mode: SimulationMode = SimulationMode.STRUCTURAL
    iterations: int = Field(default=1, ge=1)
    pod_size: int = Field(default=4, ge=2, le=10)
    deck_ids: tuple[str, ...]
    opponent_profile_ids: tuple[str, ...] = ()
    pilot_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    max_turns: int = Field(default=30, ge=1)
    paired_seed_group: str | None = None
    engine_version: str = "unimplemented"
    card_data_hash: str
    scenario_hash: str | None = None
    model_configuration: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_pod(self) -> SimulationConfig:
        if len(self.deck_ids) != self.pod_size:
            raise ValueError("deck_ids count must equal pod_size")
        return self


class SimulationRun(MutableModel):
    run_id: str
    config: SimulationConfig
    status: RunStatus = RunStatus.PLANNED
    git_commit: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    deck_hashes: dict[str, str] = Field(default_factory=dict)
    data_snapshot_hash: str
    result_files: list[str] = Field(default_factory=list)
    aborted_games: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)


class MatchResult(FrozenModel):
    run_id: str
    match_id: str
    seed: int = Field(ge=0)
    placements: dict[str, int]
    winner_ids: tuple[str, ...]
    turns: int = Field(ge=0)
    end_reason: str
    player_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    event_log_path: str | None = None
    completed: bool = True


class CardContribution(FrozenModel):
    card_name: str
    deck_hash: str
    method: str
    sample_size: int = Field(ge=1)
    metric_deltas: dict[str, float]
    confidence_intervals: dict[str, tuple[float, float]] = Field(default_factory=dict)
    matchup_scope: tuple[str, ...] = ()
    notes: str | None = None


class UpgradeStatus(StrEnum):
    PROPOSED = "proposed"
    TESTING = "testing"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class CardSwap(FrozenModel):
    remove: str
    add: str
    quantity: int = Field(default=1, ge=1)


class UpgradeProposal(MutableModel):
    proposal_id: str
    deck_id: str
    baseline_deck_hash: str
    swaps: list[CardSwap]
    rationale: str
    objectives: dict[str, float] = Field(default_factory=dict)
    physical_buildable: bool | None = None
    conflicts: list[str] = Field(default_factory=list)
    status: UpgradeStatus = UpgradeStatus.PROPOSED
    validation_run_ids: list[str] = Field(default_factory=list)
    holdout_run_ids: list[str] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
