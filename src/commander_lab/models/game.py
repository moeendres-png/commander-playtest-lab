from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .common import Color, FrozenModel


class ZoneName(StrEnum):
    LIBRARY = "library"
    HAND = "hand"
    BATTLEFIELD = "battlefield"
    GRAVEYARD = "graveyard"
    EXILE = "exile"
    COMMAND = "command"
    STACK = "stack"


class GameStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


class TurnPhase(StrEnum):
    BEGINNING = "beginning"
    PRECOMBAT_MAIN = "precombat_main"
    COMBAT = "combat"
    POSTCOMBAT_MAIN = "postcombat_main"
    ENDING = "ending"


class ActionType(StrEnum):
    PASS_PRIORITY = "pass_priority"
    PLAY_LAND = "play_land"
    CAST_SPELL = "cast_spell"
    CAST_COMMANDER = "cast_commander"
    ACTIVATE_ABILITY = "activate_ability"
    DECLARE_ATTACKERS = "declare_attackers"
    DECLARE_BLOCKERS = "declare_blockers"
    CHOOSE_TARGETS = "choose_targets"
    CHOOSE_MODE = "choose_mode"
    PAY_COST = "pay_cost"
    MULLIGAN = "mulligan"
    CONCEDE = "concede"
    STRUCTURAL_DECISION = "structural_decision"


class ZoneState(FrozenModel):
    library: tuple[str, ...] = ()
    hand: tuple[str, ...] = ()
    battlefield: tuple[str, ...] = ()
    graveyard: tuple[str, ...] = ()
    exile: tuple[str, ...] = ()
    command: tuple[str, ...] = ()

    def cards_in(self, zone: ZoneName) -> tuple[str, ...]:
        if zone == ZoneName.STACK:
            raise ValueError("stack is global and stored on GameState")
        return getattr(self, zone.value)


class PlayerState(FrozenModel):
    player_id: str
    seat: int = Field(ge=0)
    life: int = 40
    poison_counters: int = Field(default=0, ge=0)
    commander_damage_received: dict[str, int] = Field(default_factory=dict)
    commander_cast_count: dict[str, int] = Field(default_factory=dict)
    mana_pool: dict[Color | str, int] = Field(default_factory=dict)
    zones: ZoneState = Field(default_factory=ZoneState)
    land_plays_remaining: int = Field(default=1, ge=0)
    has_lost: bool = False
    loss_reason: str | None = None


class LegalAction(FrozenModel):
    action_id: str
    actor_id: str
    action_type: ActionType
    source_object_id: str | None = None
    target_ids: tuple[str, ...] = ()
    allowed_target_ids: tuple[str, ...] = ()
    modes: tuple[str, ...] = ()
    choices_schema: dict[str, Any] = Field(default_factory=dict)
    cost: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionProposal(FrozenModel):
    proposal_id: str
    actor_id: str
    legal_action_id: str | None = None
    action_type: ActionType
    source_object_id: str | None = None
    target_ids: tuple[str, ...] = ()
    selected_modes: tuple[str, ...] = ()
    choices: dict[str, Any] = Field(default_factory=dict)
    decision_tier: int = Field(default=1, ge=1, le=3)
    policy_name: str = "heuristic"
    rationale: str | None = None
    model_name: str | None = None
    model_config_hash: str | None = None


class GameEvent(FrozenModel):
    event_id: str
    game_id: str
    sequence: int = Field(ge=0)
    event_type: str
    actor_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    pre_state_hash: str | None = None
    post_state_hash: str | None = None
    occurred_at: datetime | None = None


class GameState(FrozenModel):
    game_id: str
    seed: int = Field(ge=0)
    rng_counter: int = Field(default=0, ge=0)
    status: GameStatus = GameStatus.NOT_STARTED
    turn_number: int = Field(default=0, ge=0)
    active_player_id: str | None = None
    priority_player_id: str | None = None
    phase: TurnPhase = TurnPhase.BEGINNING
    step: str | None = None
    players: tuple[PlayerState, ...]
    stack: tuple[str, ...] = ()
    legal_actions: tuple[LegalAction, ...] = ()
    winner_ids: tuple[str, ...] = ()
    event_sequence: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_player_references(self) -> GameState:
        ids = [player.player_id for player in self.players]
        if len(ids) != len(set(ids)):
            raise ValueError("player ids must be unique")
        known = set(ids)
        for ref in (self.active_player_id, self.priority_player_id):
            if ref is not None and ref not in known:
                raise ValueError(f"unknown player reference: {ref}")
        if not set(self.winner_ids).issubset(known):
            raise ValueError("winner ids must reference players")
        return self
