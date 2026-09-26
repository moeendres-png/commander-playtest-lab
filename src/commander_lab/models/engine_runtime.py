from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import FrozenModel, utc_now

ENGINE_PROTOCOL_VERSION = "2.0.0"


class EngineProcessStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    DEPENDENCIES_MISSING = "dependencies_missing"
    SOURCE_MISSING = "source_missing"
    BUILD_FAILED = "build_failed"
    BUILT_NOT_STARTED = "built_not_started"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"
    EXTERNAL_RUNTIME_REQUIRED = "external_runtime_required"


class RuntimeValidationLevel(StrEnum):
    STRUCTURAL_ONLY = "structural_only"
    TACTICAL_ORACLE = "tactical_oracle"
    EXTERNAL_RULES_ENGINE = "external_rules_engine"


class EngineRuntimeMode(StrEnum):
    EXTERNAL = "external"
    TACTICAL_ORACLE = "tactical_oracle"
    REPLAY = "replay"


class EngineMessageType(StrEnum):
    # Protocol 2 surface.  The Phase-8.5 names remain supported below as
    # compatibility messages during provider-bridge migration.
    START_ENGINE = "start_engine"
    GET_CAPABILITIES = "get_capabilities"
    GET_PROVIDER_VERSION = "get_provider_version"
    IMPORT_DECK = "import_deck"
    CREATE_COMMANDER_GAME = "create_commander_game"
    ADD_PLAYER = "add_player"
    START_GAME = "start_game"
    GET_GAME_STATE = "get_game_state"
    GET_LEGAL_ACTIONS = "get_legal_actions"
    SUBMIT_ACTION = "submit_action"
    PASS_PRIORITY = "pass_priority"
    SELECT_TARGETS = "select_targets"
    CHOOSE_MODES = "choose_modes"
    ORDER_TRIGGERS = "order_triggers"
    RESOLVE_MULLIGAN = "resolve_mulligan"
    CONCEDE = "concede"
    EXPORT_EVENT_LOG = "export_event_log"
    EXPORT_REPLAY = "export_replay"
    SHUTDOWN_GAME = "shutdown_game"
    SHUTDOWN_ENGINE = "shutdown_engine"

    # Compatibility contract retained for existing Tactical-Oracle and archived
    # provider fixtures.  These values are not promoted to external validation.
    ENGINE_HELLO = "engine_hello"
    ENGINE_CAPABILITIES = "engine_capabilities"
    LOAD_DECK = "load_deck"
    CREATE_GAME = "create_game"
    SET_SEED = "set_seed"
    ADVANCE_PRIORITY = "advance_priority"
    ADVANCE_PHASE = "advance_phase"
    GET_EVENT_LOG = "get_event_log"


class EngineResponseStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    UNSUPPORTED = "unsupported"


class EngineCapabilityHandshake(FrozenModel):
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
    target_selection_supported: bool = False
    mode_selection_supported: bool = False
    trigger_order_supported: bool = False
    mulligan_supported: bool = False
    concede_supported: bool = False
    game_shutdown_supported: bool = False
    engine_shutdown_supported: bool = False
    runtime_kind: Literal["external_rules_engine", "tactical_oracle", "unknown"] = "unknown"
    notes: tuple[str, ...] = ()

    def supports(self, capability: str) -> bool:
        if not hasattr(self, capability):
            raise KeyError(f"unknown engine capability: {capability}")
        value = getattr(self, capability)
        return bool(value)


class EngineProtocolRequest(FrozenModel):
    protocol_version: str = ENGINE_PROTOCOL_VERSION
    request_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    engine: Literal["xmage", "forge", "tactical", "unknown"] = "unknown"
    engine_version: str | None = None
    game_id: str | None = None
    message_type: EngineMessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    # Compatibility aliases retained for Phase-8 bridge fixtures.
    method: str | None = None
    params: dict[str, Any] | None = None

    @model_validator(mode="after")
    def normalize_compatibility_aliases(self) -> EngineProtocolRequest:
        expected = self.message_type.value
        if self.method is not None and self.method != expected:
            raise ValueError("method must match message_type")
        if self.params is not None and self.params != self.payload:
            raise ValueError("params must match payload")
        return self

    def wire_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude_none=True)
        payload["method"] = self.message_type.value
        payload["params"] = self.payload
        return payload


class EngineProtocolErrorDetail(FrozenModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class EngineProtocolResponse(FrozenModel):
    protocol_version: str = ENGINE_PROTOCOL_VERSION
    request_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    success: bool
    status: EngineResponseStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[EngineProtocolErrorDetail, ...] = ()
    engine_event_offset: int = Field(default=0, ge=0)
    # Compatibility aliases retained for old bridge fixtures.
    ok: bool | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_result(self) -> EngineProtocolResponse:
        if self.ok is not None and self.ok != self.success:
            raise ValueError("ok must match success")
        if self.result is not None and self.result != self.payload:
            raise ValueError("result must match payload")
        if self.success and self.errors:
            raise ValueError("successful response cannot contain errors")
        if not self.success and not self.errors and self.error is None:
            raise ValueError("failed response requires at least one error")
        return self

    @classmethod
    def from_wire(cls, value: dict[str, Any]) -> EngineProtocolResponse:
        if "success" in value:
            return cls.model_validate(value)
        ok = bool(value.get("ok"))
        raw_error = value.get("error")
        errors: tuple[EngineProtocolErrorDetail, ...] = ()
        if raw_error:
            errors = (
                EngineProtocolErrorDetail(
                    code=str(raw_error.get("code", "bridge_error")),
                    message=str(raw_error.get("message", raw_error)),
                    details={k: v for k, v in raw_error.items() if k not in {"code", "message"}},
                ),
            )
        return cls(
            request_id=str(value.get("request_id", "")),
            success=ok,
            status=EngineResponseStatus.OK if ok else EngineResponseStatus.ERROR,
            payload=dict(value.get("result") or {}),
            errors=errors,
            ok=ok,
            result=dict(value.get("result") or {}) if ok else None,
            error=raw_error,
            engine_event_offset=int(value.get("engine_event_offset", 0)),
        )

    def wire_dict(self) -> dict[str, Any]:
        value = self.model_dump(mode="json", exclude_none=True)
        value["ok"] = self.success
        value["result"] = self.payload if self.success else None
        if not self.success and self.errors:
            value["error"] = self.errors[0].model_dump(mode="json")
        return value


class EngineRuntimeConfig(FrozenModel):
    provider: Literal["xmage", "forge"] = "xmage"
    mode: EngineRuntimeMode = EngineRuntimeMode.EXTERNAL
    home: str | None = None
    source_path: str | None = None
    binary_path: str | None = None
    host: str = "127.0.0.1"
    port: int | None = Field(default=None, ge=1, le=65535)
    start_command: tuple[str, ...] = ()
    stop_command: tuple[str, ...] = ()
    healthcheck_timeout_seconds: float = Field(default=20.0, gt=0)
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    protocol_version: str = ENGINE_PROTOCOL_VERSION
    java_home: str | None = None
    maven_home: str | None = None
    allow_tactical_oracle_fallback: bool = False
    log_directory: str = ".runtime/engine"


class EngineProcessState(FrozenModel):
    provider: Literal["xmage", "forge"]
    status: EngineProcessStatus
    pid: int | None = Field(default=None, ge=1)
    engine_version: str | None = None
    adapter_version: str = "commander-lab-protocol-2.0.0"
    protocol_version: str = ENGINE_PROTOCOL_VERSION
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_healthcheck_at: datetime | None = None
    capabilities: EngineCapabilityHandshake | None = None
    details: tuple[str, ...] = ()
    stdout_log: str | None = None
    stderr_log: str | None = None


class EngineInstallationIdentity(FrozenModel):
    provider: Literal["xmage", "forge"]
    release: str
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_path: str | None = None
    binary_path: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    binary_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    verified: bool = False
    verification_notes: tuple[str, ...] = ()


class EngineReplay(FrozenModel):
    schema_version: int = 1
    protocol_version: str = ENGINE_PROTOCOL_VERSION
    engine: Literal["xmage", "forge", "tactical"]
    engine_version: str
    validation_level: RuntimeValidationLevel
    game_id: str
    initial_state: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    final_state: dict[str, Any]
    event_log_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=utc_now)


__all__ = [
    "ENGINE_PROTOCOL_VERSION",
    "EngineCapabilityHandshake",
    "EngineInstallationIdentity",
    "EngineMessageType",
    "EngineProcessState",
    "EngineProcessStatus",
    "EngineProtocolErrorDetail",
    "EngineProtocolRequest",
    "EngineProtocolResponse",
    "EngineReplay",
    "EngineResponseStatus",
    "EngineRuntimeConfig",
    "EngineRuntimeMode",
    "RuntimeValidationLevel",
]
