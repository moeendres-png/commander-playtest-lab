from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .common import FrozenModel, MutableModel
from .game import GameEvent, GameState

RulesCardZone = Literal["commander", "main", "sideboard"]


class ValidationLevel(StrEnum):
    STRUCTURAL_ONLY = "structural_only"
    TACTICAL_ORACLE = "tactical_oracle"
    EXTERNAL_RULES_ENGINE = "external_rules_engine"


class RulesBackend(StrEnum):
    TACTICAL = "tactical"
    FORGE = "forge"
    XMAGE = "xmage"


class RulesEngineAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    MISCONFIGURED = "misconfigured"


class RulesEngineCapabilities(FrozenModel):
    # Phase-8 compatibility names.
    deck_loading: bool = False
    commander_games: bool = False
    deterministic_seed: bool = False
    reproducible_starting_state: bool = False
    scenario_injection: bool = False
    legal_action_query: bool = False
    action_submission: bool = False
    event_logs: bool = False
    game_logs: bool = False
    multiplayer: bool = False
    maximum_players: int | None = Field(default=None, ge=1)

    # Versioned Phase-8.5 capability-handshake names. These are explicit and
    # must be reported by a bridge; callers must not infer them from provider.
    commander_supported: bool = False
    partner_supported: bool = False
    multiplayer_supported: bool = False
    max_players: int | None = Field(default=None, ge=1)
    headless_supported: bool = False
    seed_supported: bool = False
    deck_import_supported: bool = False
    legal_actions_supported: bool = False
    action_submission_supported: bool = False
    event_log_supported: bool = False
    replay_supported: bool = False
    stack_visible: bool = False
    priority_visible: bool = False
    commander_damage_visible: bool = False
    commander_tax_visible: bool = False
    starting_state_injection_supported: bool = False
    scenario_injection_supported: bool = False
    healthcheck_supported: bool = True
    runtime_kind: Literal["external_rules_engine", "tactical_oracle", "unknown"] = "unknown"
    notes: tuple[str, ...] = ()

    def supports(self, capability: str) -> bool:
        aliases = {
            "commander_supported": self.commander_supported or self.commander_games,
            "multiplayer_supported": self.multiplayer_supported or self.multiplayer,
            "max_players": self.max_players or self.maximum_players,
            "seed_supported": self.seed_supported or self.deterministic_seed,
            "deck_import_supported": self.deck_import_supported or self.deck_loading,
            "legal_actions_supported": self.legal_actions_supported or self.legal_action_query,
            "action_submission_supported": self.action_submission_supported
            or self.action_submission,
            "event_log_supported": self.event_log_supported or self.event_logs,
            "starting_state_injection_supported": (
                self.starting_state_injection_supported or self.reproducible_starting_state
            ),
            "scenario_injection_supported": self.scenario_injection_supported
            or self.scenario_injection,
        }
        if capability in aliases:
            return bool(aliases[capability])
        if not hasattr(self, capability):
            raise KeyError(f"unknown rules-engine capability: {capability}")
        return bool(getattr(self, capability))


class RulesEngineProbe(FrozenModel):
    backend: RulesBackend
    availability: RulesEngineAvailability
    backend_version: str | None = None
    command: tuple[str, ...] = ()
    capabilities: RulesEngineCapabilities
    details: tuple[str, ...] = ()


class RulesCardPrinting(FrozenModel):
    oracle_name: str = Field(min_length=1)
    set_code: str = Field(min_length=1)
    collector_number: str = Field(min_length=1)
    zone: RulesCardZone

    @field_validator("oracle_name", "set_code", "collector_number")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("printing identity fields cannot be blank")
        return normalized


class RulesDeckInput(FrozenModel):
    deck_id: str
    name: str
    commander_names: tuple[str, ...]
    mainboard: tuple[str, ...]
    sideboard: tuple[str, ...] = ()
    card_printings: tuple[RulesCardPrinting, ...] = ()
    deck_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_path: str | None = None

    @model_validator(mode="after")
    def validate_commander_deck_size(self) -> RulesDeckInput:
        total = len(self.mainboard) + len(self.commander_names)
        if total != 100:
            raise ValueError(f"Commander deck must contain exactly 100 cards; observed {total}")
        if len(self.commander_names) not in {1, 2}:
            raise ValueError("Commander configuration must contain one commander or two partners")
        if self.card_printings:
            expected: Counter[tuple[str, RulesCardZone]] = Counter()
            expected.update((name, "commander") for name in self.commander_names)
            expected.update((name, "main") for name in self.mainboard)
            expected.update((name, "sideboard") for name in self.sideboard)
            observed: Counter[tuple[str, RulesCardZone]] = Counter(
                (printing.oracle_name, printing.zone) for printing in self.card_printings
            )
            if observed != expected:
                missing = expected - observed
                unexpected = observed - expected
                raise ValueError(
                    "card printings do not exactly match deck zones; "
                    f"missing={dict(missing)}, unexpected={dict(unexpected)}"
                )
        return self


class RulesDeckHandle(FrozenModel):
    backend: RulesBackend
    handle_id: str
    deck_id: str
    deck_hash: str
    commander_names: tuple[str, ...]
    accepted_cards: int = Field(ge=0)
    rejected_cards: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class RulesGameRequest(FrozenModel):
    game_id: str
    deck_handles: tuple[str, ...]
    format: Literal["commander"] = "commander"
    seed: int | None = Field(default=None, ge=0)
    starting_player_seat: int = Field(default=0, ge=0)
    starting_life: int = Field(default=40, ge=1)
    deterministic_starting_state: dict[str, Any] | None = None
    external_control: bool = False

    @model_validator(mode="after")
    def validate_pod(self) -> RulesGameRequest:
        if not 1 <= len(self.deck_handles) <= 10:
            raise ValueError("rules-engine game requires between one and ten decks")
        if self.starting_player_seat >= len(self.deck_handles):
            raise ValueError("starting_player_seat is outside the pod")
        return self


class TacticalScenario(FrozenModel):
    scenario_id: str
    description: str
    state: GameState
    rule: str | None = None
    input_state: dict[str, Any] = Field(default_factory=dict)
    action_effects: dict[str, dict[str, Any]] = Field(default_factory=dict)
    expected_normalized: dict[str, Any] = Field(default_factory=dict)
    cards: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class RulesSession(FrozenModel):
    backend: RulesBackend
    session_id: str
    game_id: str
    state: GameState
    seed: int | None = None
    deck_handles: tuple[str, ...] = ()
    scenario_id: str | None = None
    created_from: Literal["game", "scenario"] = "game"


class RulesEngineLog(FrozenModel):
    backend: RulesBackend
    session_id: str
    events: tuple[GameEvent, ...] = ()
    raw_lines: tuple[str, ...] = ()
    log_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class RulesEngineResult(FrozenModel):
    backend: RulesBackend
    session_id: str
    completed: bool
    final_state: GameState
    normalized_result: dict[str, Any] = Field(default_factory=dict)
    validation_level: ValidationLevel
    backend_version: str | None = None
    warnings: tuple[str, ...] = ()


class InteractionSpec(FrozenModel):
    interaction_id: str
    description: str
    category: str
    cards: tuple[str, ...]
    rule: str
    input_state: dict[str, Any]
    expected_normalized: dict[str, Any]
    comparison_keys: tuple[str, ...]
    critical: bool = True
    preferred_backend: Literal["xmage", "forge", "either"] = "either"
    source_notes: tuple[str, ...] = ()


class InteractionValidation(FrozenModel):
    interaction_id: str
    level: ValidationLevel
    passed: bool
    backend: RulesBackend
    expected: dict[str, Any]
    observed: dict[str, Any]
    comparison_keys: tuple[str, ...]
    mismatches: tuple[str, ...] = ()
    backend_version: str | None = None
    evidence_path: str | None = None


class CardValidationRecord(FrozenModel):
    oracle_name: str
    level: ValidationLevel
    interaction_ids: tuple[str, ...] = ()
    tactical_passed: int = Field(default=0, ge=0)
    rules_engine_passed: int = Field(default=0, ge=0)
    notes: tuple[str, ...] = ()


class ValidationRegistry(MutableModel):
    schema_version: int = 1
    engine_version: str
    cards: dict[str, CardValidationRecord]
    interactions: dict[str, InteractionValidation]
    tactical_cases: int = Field(default=0, ge=0)
    tactical_passed: int = Field(default=0, ge=0)
    rules_engine_cases: int = Field(default=0, ge=0)
    rules_engine_passed: int = Field(default=0, ge=0)
    notes: list[str] = Field(default_factory=list)


class BridgeRequest(FrozenModel):
    request_id: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class BridgeResponse(FrozenModel):
    request_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    @model_validator(mode="after")
    def result_or_error(self) -> BridgeResponse:
        if self.ok and self.result is None:
            raise ValueError("successful bridge response requires result")
        if not self.ok and self.error is None:
            raise ValueError("failed bridge response requires error")
        return self


__all__ = [
    "BridgeRequest",
    "BridgeResponse",
    "CardValidationRecord",
    "InteractionSpec",
    "InteractionValidation",
    "RulesBackend",
    "RulesCardPrinting",
    "RulesDeckHandle",
    "RulesDeckInput",
    "RulesEngineAvailability",
    "RulesEngineCapabilities",
    "RulesEngineLog",
    "RulesEngineProbe",
    "RulesEngineResult",
    "RulesGameRequest",
    "RulesSession",
    "TacticalScenario",
    "ValidationLevel",
    "ValidationRegistry",
]
