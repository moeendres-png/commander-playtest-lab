from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import Color, DataQuality, FrozenModel, MutableModel, SourceRef
from .pilots import PilotConfig
from .roles import CardRole, StructuralMechanic

STRUCTURAL_ESTIMATE_TYPE = "structural_model_estimates"


class ConditionalStrength(FrozenModel):
    condition: str
    multiplier: float = Field(default=1.0, ge=0.0, le=4.0)
    notes: str | None = None


class StructuralCardProfile(FrozenModel):
    oracle_name: str = Field(min_length=1)
    mana_value: float = Field(default=3.0, ge=0.0, le=20.0)
    roles: frozenset[CardRole]
    role_strengths: dict[CardRole, float] = Field(default_factory=dict)
    mechanic_tags: frozenset[StructuralMechanic] = frozenset()
    color_requirements: dict[Color, int] = Field(default_factory=dict)
    color_identity: frozenset[Color] = frozenset()
    produces_colors: frozenset[Color] = frozenset()
    is_land: bool = False
    is_permanent: bool = True
    is_creature: bool = False
    base_power: float = Field(default=0.0, ge=0.0, le=30.0)
    commander_synergy: float = Field(default=0.0, ge=0.0, le=2.0)
    floor_value: float = Field(default=0.5, ge=0.0, le=2.0)
    immediate_impact: float = Field(default=0.5, ge=0.0, le=1.5)
    turn_cycle_risk: float = Field(default=0.5, ge=0.0, le=1.0)
    multiplayer_scaling: float = Field(default=0.0, ge=-1.0, le=2.0)
    conditional_strength: tuple[ConditionalStrength, ...] = ()
    package_ids: frozenset[str] = frozenset()
    source_quality: DataQuality = DataQuality.PROJECT_INFERRED
    sources: tuple[SourceRef, ...] = ()
    notes: str | None = None

    @model_validator(mode="after")
    def validate_role_strengths(self) -> StructuralCardProfile:
        missing = set(self.role_strengths) - set(self.roles)
        if missing:
            raise ValueError(f"role strengths reference absent roles: {sorted(missing)}")
        if self.is_land and CardRole.MANA_SOURCE not in self.roles:
            raise ValueError("land profiles must include mana_source")
        return self

    def strength(self, role: CardRole) -> float:
        if role not in self.roles:
            return 0.0
        return self.role_strengths.get(role, 1.0)


class StructuralDeckProfile(FrozenModel):
    deck_id: str
    deck_hash: str
    commander_names: tuple[str, ...]
    cards: tuple[StructuralCardProfile, ...]
    commander_base_costs: dict[str, float]
    commander_base_power: dict[str, float] = Field(default_factory=dict)
    commander_strategy: str = "generic"
    data_snapshot_hash: str

    @model_validator(mode="after")
    def commanders_have_costs(self) -> StructuralDeckProfile:
        missing = set(self.commander_names) - set(self.commander_base_costs)
        if missing:
            raise ValueError(f"missing commander base costs: {sorted(missing)}")
        return self


class StructuralAbortLimits(FrozenModel):
    max_turns: int = Field(default=30, ge=1, le=500)
    max_events: int = Field(default=20_000, ge=10)
    max_no_progress_turns: int = Field(default=12, ge=1, le=100)
    max_spells_per_turn: int = Field(default=8, ge=1, le=100)


class StructuralMatchConfig(FrozenModel):
    match_id: str
    seed: int = Field(ge=0)
    deck_ids: tuple[str, ...]
    starting_player_seat: int | None = Field(default=None, ge=0)
    free_multiplayer_mulligan: bool = True
    pilot_configs: tuple[PilotConfig, ...] = ()
    opening_hand_overrides: tuple[tuple[str, ...] | None, ...] = ()
    limits: StructuralAbortLimits = Field(default_factory=StructuralAbortLimits)
    estimate_type: Literal["structural_model_estimates"] = STRUCTURAL_ESTIMATE_TYPE

    @model_validator(mode="after")
    def validate_starting_seat(self) -> StructuralMatchConfig:
        if not self.deck_ids:
            raise ValueError("at least one deck is required")
        if len(self.deck_ids) > 10:
            raise ValueError("at most ten players are supported")
        if self.starting_player_seat is not None and self.starting_player_seat >= len(
            self.deck_ids
        ):
            raise ValueError("starting_player_seat is outside the pod")
        if self.pilot_configs and len(self.pilot_configs) != len(self.deck_ids):
            raise ValueError("pilot_configs must be empty or contain one config per seat")
        if self.opening_hand_overrides and len(self.opening_hand_overrides) != len(self.deck_ids):
            raise ValueError("opening_hand_overrides must be empty or contain one hand per seat")
        if any(hand is not None and len(hand) > 7 for hand in self.opening_hand_overrides):
            raise ValueError("opening-hand overrides may contain at most seven cards")
        return self


class StructuralBatchConfig(FrozenModel):
    run_id: str
    seed: int = Field(ge=0)
    iterations: int = Field(default=1, ge=1, le=10_000_000)
    deck_ids: tuple[str, ...]
    workers: int = Field(default=1, ge=1, le=64)
    starting_player_rotation: bool = True
    pilot_configs: tuple[PilotConfig, ...] = ()
    limits: StructuralAbortLimits = Field(default_factory=StructuralAbortLimits)
    output_directory: str | None = None
    estimate_type: Literal["structural_model_estimates"] = STRUCTURAL_ESTIMATE_TYPE

    @model_validator(mode="after")
    def validate_decks(self) -> StructuralBatchConfig:
        if not self.deck_ids:
            raise ValueError("at least one deck is required")
        if len(self.deck_ids) > 10:
            raise ValueError("at most ten players are supported")
        if self.pilot_configs and len(self.pilot_configs) != len(self.deck_ids):
            raise ValueError("pilot_configs must be empty or contain one config per seat")
        return self


class StructuralPlayerMetrics(FrozenModel):
    player_id: str
    deck_id: str
    pilot_name: str = "GenericCommanderPilot"
    pilot_strength: str = "average"
    pilot_mode: str = "deterministic"
    placement: int
    life: float
    mulligans: int
    lands_played: int
    ramp_resolved: int
    first_ramp_turn: int | None = None
    first_independent_draw_engine_turn: int | None = None
    cards_drawn: int
    commander_casts: int
    commander_tax_paid: int
    first_commander_cast_turn: int | None = None
    commander_peak_power: dict[str, float] = Field(default_factory=dict)
    ishai_peak_power: float = 0.0
    korvold_cards_drawn: int = 0
    hostile_target_events: int = 0
    archenemy_turns: int = 0
    was_archenemy: bool = False
    removals_resolved: int
    counters_resolved: int
    protections_resolved: int
    wipes_resolved: int
    graveyard_hate_resolved: int
    recursions_resolved: int
    engine_value: float
    resources_generated: float
    normal_damage_dealt: float
    commander_damage_dealt: float
    eliminated_turn: int | None = None
    elimination_reason: str | None = None


class StructuralMatchResult(FrozenModel):
    run_id: str
    match_id: str
    seed: int
    estimate_type: Literal["structural_model_estimates"] = STRUCTURAL_ESTIMATE_TYPE
    completed: bool
    aborted: bool = False
    abort_reason: str | None = None
    turns: int
    winner_ids: tuple[str, ...]
    placements: dict[str, int]
    end_reason: str
    player_metrics: dict[str, StructuralPlayerMetrics]
    event_count: int
    event_log_path: str | None = None
    log_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class StructuralBatchResult(MutableModel):
    run_id: str
    estimate_type: Literal["structural_model_estimates"] = STRUCTURAL_ESTIMATE_TYPE
    master_seed: int
    iterations: int
    workers: int
    pod_size: int
    completed_games: int
    aborted_games: int
    match_results: list[StructuralMatchResult]
    aggregate: dict[str, object] = Field(default_factory=dict)
    result_path: str | None = None
