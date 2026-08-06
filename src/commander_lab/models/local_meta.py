from __future__ import annotations
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from pydantic import Field, model_validator
from .common import FrozenModel, MutableModel, NumericRange

LOCAL_META_SCHEMA_VERSION="1.0.0"

class ObservationStatus(StrEnum):
    DIRECTLY_OBSERVED="directly_observed"
    REPORTED_BY_PLAYER="reported_by_player"
    INFERRED_ROLE="inferred_role"
    UNKNOWN="unknown"
    SYNTHETIC_ASSUMPTION="synthetic_assumption"

class LocalCardObservation(FrozenModel):
    card_name: str
    status: ObservationStatus
    occurrences: int = Field(default=1,ge=1)
    notes: str|None=None

class LocalRoleObservation(FrozenModel):
    role: str
    status: ObservationStatus
    confidence: float=Field(default=0.5,ge=0,le=1)
    notes: str|None=None

class LocalGameParticipant(MutableModel):
    participant_id: str
    public_label: str
    commander: str
    deck_version: str="unknown"
    deck_hash: str|None=Field(default=None,pattern=r"^[0-9a-f]{64}$")
    seat_position: int=Field(ge=0)
    started_game: bool=False
    mulligans: int|None=Field(default=None,ge=0)
    commander_casts: int|None=Field(default=None,ge=0)
    removal_used: int|None=Field(default=None,ge=0)
    boardwipes_used: int|None=Field(default=None,ge=0)
    engines_seen: tuple[str,...]=()
    visible_cards: tuple[LocalCardObservation,...]=()
    archenemy_observations: tuple[str,...]=()
    win_axis: str|None=None
    placement: int|None=Field(default=None,ge=1)
    best_cards: tuple[str,...]=()
    weakest_cards: tuple[str,...]=()
    dead_cards: tuple[str,...]=()
    sequencing_errors: tuple[str,...]=()

class LocalGameRecord(MutableModel):
    schema_version: str=LOCAL_META_SCHEMA_VERSION
    game_id: str=Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    played_on: date|None=None
    pod_size: int=Field(ge=2,le=10)
    turns: int|None=Field(default=None,ge=1)
    participants: tuple[LocalGameParticipant,...]
    correction_of: str|None=None
    source_status: ObservationStatus=ObservationStatus.DIRECTLY_OBSERVED
    notes: str|None=None
    ingested_at: datetime=Field(default_factory=lambda:datetime.now(UTC))
    raw_hash: str|None=Field(default=None,pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_game(self)->"LocalGameRecord":
        if len(self.participants)!=self.pod_size: raise ValueError("participant count must equal pod_size")
        ids=[p.participant_id for p in self.participants]
        if len(ids)!=len(set(ids)): raise ValueError("participant IDs must be unique")
        return self

class LocalFrequencyEstimate(FrozenModel):
    observations: int=Field(ge=0)
    count: int=Field(ge=0)
    raw_frequency: float=Field(ge=0,le=1)
    shrunk_frequency: float=Field(ge=0,le=1)
    uncertainty_interval: tuple[float,float]
    prior_strength: float=Field(ge=0)

class LocalOpponentProfileVersion(FrozenModel):
    profile_id: str
    opponent_key: str
    version: int=Field(ge=1)
    commander: str
    deck_version_label: str="unknown"
    based_on_game_ids: tuple[str,...]=()
    observed_cards: tuple[LocalCardObservation,...]=()
    observed_roles: tuple[LocalRoleObservation,...]=()
    possible_roles: tuple[LocalRoleObservation,...]=()
    speed_turn_range: NumericRange|None=None
    interaction_density: LocalFrequencyEstimate|None=None
    wipe_density: LocalFrequencyEstimate|None=None
    commander_dependency: LocalFrequencyEstimate|None=None
    win_axes: tuple[str,...]=()
    uncertainty_notes: tuple[str,...]=()
    sample_size: int=Field(default=0,ge=0)
    data_quality: str="insufficient_data"
    last_observed_at: date|None=None
    profile_hash: str=Field(pattern=r"^[0-9a-f]{64}$")
    supersedes_profile_id: str|None=None
    official_precon_superseded: bool=False

class LocalMetaSnapshot(FrozenModel):
    snapshot_id: str
    profile_ids: tuple[str,...]
    real_game_count: int=Field(ge=0)
    observed_matchups: int=Field(ge=0)
    data_quality: str
    uncertainty_band: str
    last_observation: date|None=None
    train_game_ids: tuple[str,...]=()
    validation_game_ids: tuple[str,...]=()
    snapshot_hash: str=Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime=Field(default_factory=lambda:datetime.now(UTC))
