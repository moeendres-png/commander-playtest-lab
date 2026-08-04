from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import FrozenModel
from .roles import CardRole


class PilotStrength(StrEnum):
    WEAK = "weak"
    AVERAGE = "average"
    STRONG = "strong"
    NEAR_OPTIMAL_HEURISTIC = "near_optimal_heuristic"


class PilotDecisionMode(StrEnum):
    DETERMINISTIC = "deterministic"
    STOCHASTIC = "stochastic"


class PilotUtilityWeights(FrozenModel):
    survival: float = Field(default=1.0, ge=-5.0, le=5.0)
    mana_efficiency: float = Field(default=1.0, ge=-5.0, le=5.0)
    card_advantage: float = Field(default=1.0, ge=-5.0, le=5.0)
    tempo: float = Field(default=1.0, ge=-5.0, le=5.0)
    engine_development: float = Field(default=1.0, ge=-5.0, le=5.0)
    interaction_reserve: float = Field(default=1.0, ge=-5.0, le=5.0)
    commander_value: float = Field(default=1.0, ge=-5.0, le=5.0)
    threat_reduction: float = Field(default=1.0, ge=-5.0, le=5.0)
    win_progress: float = Field(default=1.0, ge=-5.0, le=5.0)
    political_visibility: float = Field(default=-0.65, ge=-5.0, le=5.0)
    rebuild_capacity: float = Field(default=1.0, ge=-5.0, le=5.0)

    def as_dict(self) -> dict[str, float]:
        return {name: float(value) for name, value in self.model_dump().items()}


class PilotConfig(FrozenModel):
    pilot_name: str = "auto"
    strength: PilotStrength = PilotStrength.AVERAGE
    mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC
    weights: PilotUtilityWeights | None = None
    temperature: float | None = Field(default=None, gt=0.0, le=5.0)
    mistake_rate: float | None = Field(default=None, ge=0.0, le=0.5)
    reserve_mana_target: float | None = Field(default=None, ge=0.0, le=10.0)


class PilotCommanderView(FrozenModel):
    name: str
    base_cost: float = Field(ge=0.0)
    next_cost: float = Field(ge=0.0)
    casts: int = Field(ge=0)
    on_battlefield: bool = False
    power: float = Field(default=0.0, ge=0.0)


class PilotOpponentView(FrozenModel):
    player_id: str
    life: float
    threat: float = Field(ge=0.0)
    board_power: float = Field(ge=0.0)
    engine_value: float = Field(ge=0.0)
    graveyard_size: int = Field(ge=0)
    hand_size: int = Field(ge=0)
    commander_damage_from_actor: dict[str, float] = Field(default_factory=dict)


class PilotStateView(FrozenModel):
    player_id: str
    deck_id: str
    strategy: str
    turn: int = Field(ge=1)
    pod_size: int = Field(ge=1, le=10)
    life: float
    hand_size: int = Field(ge=0)
    mana_available: float = Field(ge=0.0)
    lands: int = Field(ge=0)
    ramp_mana: float = Field(ge=0.0)
    resources: float = Field(ge=0.0)
    tokens: float = Field(ge=0.0)
    board_power: float = Field(ge=0.0)
    engine_value: float = Field(ge=0.0)
    graveyard_size: int = Field(ge=0)
    battlefield_names: tuple[str, ...] = ()
    hand_names: tuple[str, ...] = ()
    role_counts: dict[CardRole, int] = Field(default_factory=dict)
    commanders: tuple[PilotCommanderView, ...] = ()
    opponents: tuple[PilotOpponentView, ...] = ()

    @property
    def commander_online(self) -> bool:
        return any(commander.on_battlefield for commander in self.commanders)

    @property
    def max_opponent_threat(self) -> float:
        return max((opponent.threat for opponent in self.opponents), default=0.0)

    @property
    def enemy_board_total(self) -> float:
        return sum(opponent.board_power + opponent.engine_value for opponent in self.opponents)

    @property
    def lowest_opponent_life(self) -> float:
        return min((opponent.life for opponent in self.opponents), default=40.0)

    @property
    def max_graveyard_pressure(self) -> int:
        return max((opponent.graveyard_size for opponent in self.opponents), default=0)


class PilotActionView(FrozenModel):
    action_id: str
    action_kind: Literal[
        "card",
        "commander",
        "counter",
        "protection",
        "combat_target",
        "removal_target",
        "graveyard_target",
        "pass",
    ]
    card_name: str
    mana_cost: float = Field(default=0.0, ge=0.0)
    roles: frozenset[CardRole] = frozenset()
    role_strengths: dict[CardRole, float] = Field(default_factory=dict)
    floor_value: float = Field(default=0.0, ge=0.0, le=3.0)
    immediate_impact: float = Field(default=0.0, ge=0.0, le=2.0)
    turn_cycle_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    multiplayer_scaling: float = Field(default=0.0, ge=-1.0, le=3.0)
    commander_synergy: float = Field(default=0.0, ge=0.0, le=3.0)
    base_power: float = Field(default=0.0, ge=0.0, le=10000.0)
    target_player_id: str | None = None
    target_threat: float = Field(default=0.0, ge=0.0)
    threat_score: float = Field(default=0.0, ge=0.0)
    remaining_mana: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, float | int | str | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def role_strength_keys_exist(self) -> "PilotActionView":
        missing = set(self.role_strengths) - set(self.roles)
        if missing:
            raise ValueError(f"role strengths reference absent roles: {sorted(missing)}")
        return self

    def strength(self, role: CardRole) -> float:
        if role not in self.roles:
            return 0.0
        return self.role_strengths.get(role, 1.0)


class PilotUtilityBreakdown(FrozenModel):
    survival: float = 0.0
    mana_efficiency: float = 0.0
    card_advantage: float = 0.0
    tempo: float = 0.0
    engine_development: float = 0.0
    interaction_reserve: float = 0.0
    commander_value: float = 0.0
    threat_reduction: float = 0.0
    win_progress: float = 0.0
    political_visibility: float = 0.0
    rebuild_capacity: float = 0.0
    specialist_bonus: float = 0.0
    total_utility: float = 0.0

    def components(self) -> dict[str, float]:
        payload = self.model_dump()
        payload.pop("specialist_bonus")
        payload.pop("total_utility")
        return {name: float(value) for name, value in payload.items()}


class PilotDecision(FrozenModel):
    pilot_name: str
    strength: PilotStrength
    mode: PilotDecisionMode
    selected_action_id: str | None = None
    selected_utility: float | None = None
    candidates: tuple[tuple[str, float], ...] = ()
    selected_breakdown: PilotUtilityBreakdown | None = None
