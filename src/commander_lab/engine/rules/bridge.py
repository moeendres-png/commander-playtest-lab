from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    ActionProposal,
    EngineCapabilityHandshake,
    EngineMessageType,
    EngineProtocolRequest,
    EngineProtocolResponse,
    GameState,
    LegalAction,
    RulesBackend,
    RulesDeckHandle,
    RulesDeckInput,
    RulesEngineAvailability,
    RulesEngineCapabilities,
    RulesEngineLog,
    RulesEngineProbe,
    RulesEngineResult,
    RulesGameRequest,
    RulesSession,
    TacticalScenario,
)

from .base import RulesEngineAdapter, RulesEngineProtocolError, RulesEngineUnavailable

_BACKEND_ENV = {
    RulesBackend.FORGE: "COMMANDER_LAB_FORGE_BRIDGE_CMD",
    RulesBackend.XMAGE: "COMMANDER_LAB_XMAGE_BRIDGE_CMD",
}


class JsonLineBridgeClient:
    """Persistent, timeout-aware, versioned JSONL client.

    Requests contain both the Phase-8.5 envelope and Phase-8 `method`/`params`
    aliases. This permits deterministic migration of old test fixtures while the
    strict contract is used by current bridges.
    """

    def __init__(
        self,
        command: tuple[str, ...],
        *,
        cwd: str | Path | None = None,
        startup_timeout_seconds: float = 20.0,
        request_timeout_seconds: float = 20.0,
        engine: str = "unknown",
        engine_version: str | None = None,
        protocol_version: str = ENGINE_PROTOCOL_VERSION,
        log_directory: str | Path | None = None,
    ) -> None:
        if not command:
            raise ValueError("bridge command must not be empty")
        self.command = command
        self.cwd = None if cwd is None else str(cwd)
        self.startup_timeout_seconds = startup_timeout_seconds
        self.request_timeout_seconds = request_timeout_seconds
        self.engine = engine
        self.engine_version = engine_version
        self.protocol_version = protocol_version
        self.log_directory = None if log_directory is None else Path(log_directory)
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()
        self._stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr_lines[-50:])

    @staticmethod
    def _pump(
        stream: Any,
        target: queue.Queue[str | None] | list[str],
        log_path: Path | None = None,
    ) -> None:
        log_handle = None
        try:
            if log_path is not None:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_handle = log_path.open("a", encoding="utf-8")
            for line in iter(stream.readline, ""):
                if log_handle is not None:
                    log_handle.write(line)
                    log_handle.flush()
                if isinstance(target, queue.Queue):
                    target.put(line)
                else:
                    target.append(line.rstrip("\n"))
        finally:
            if log_handle is not None:
                log_handle.close()
            if isinstance(target, queue.Queue):
                target.put(None)

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            try:
                self._process = subprocess.Popen(
                    self.command,
                    cwd=self.cwd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                raise RulesEngineUnavailable(
                    f"unable to start bridge command {self.command!r}: {exc}"
                ) from exc
            assert self._process.stdout is not None
            assert self._process.stderr is not None
            self._stdout_queue = queue.Queue()
            self._stderr_lines = []
            stdout_log = self.log_directory / f"{self.engine}.bridge.stdout.jsonl" if self.log_directory else None
            stderr_log = self.log_directory / f"{self.engine}.bridge.stderr.log" if self.log_directory else None
            self._stdout_thread = threading.Thread(
                target=self._pump, args=(self._process.stdout, self._stdout_queue, stdout_log), daemon=True
            )
            self._stderr_thread = threading.Thread(
                target=self._pump, args=(self._process.stderr, self._stderr_lines, stderr_log), daemon=True
            )
            self._stdout_thread.start()
            self._stderr_thread.start()
            # Detect immediate startup failures without claiming a handshake.
            deadline = time.monotonic() + min(self.startup_timeout_seconds, 0.25)
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    raise RulesEngineUnavailable(
                        f"bridge exited during startup with code {self._process.returncode}: "
                        + " | ".join(self.stderr_tail)
                    )
                time.sleep(0.01)

    def request(
        self,
        method: str | EngineMessageType,
        params: dict[str, Any] | None = None,
        *,
        game_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self.start()
            assert self._process is not None
            if self._process.stdin is None:
                raise RulesEngineProtocolError("bridge process stdin is unavailable")
            legacy_aliases = {
                "probe": EngineMessageType.ENGINE_HELLO,
                "start_commander_game": EngineMessageType.CREATE_GAME,
                "create_scenario": EngineMessageType.CREATE_GAME,
                "get_state": EngineMessageType.GET_GAME_STATE,
                "get_logs": EngineMessageType.GET_EVENT_LOG,
                "get_result": EngineMessageType.GET_GAME_STATE,
                "shutdown": EngineMessageType.SHUTDOWN_GAME,
            }
            try:
                if isinstance(method, EngineMessageType):
                    message_type = method
                else:
                    message_type = legacy_aliases[method] if method in legacy_aliases else EngineMessageType(method)
            except ValueError as exc:
                raise RulesEngineProtocolError(f"unknown bridge message type: {method}") from exc
            request = EngineProtocolRequest(
                protocol_version=self.protocol_version,
                request_id=str(uuid.uuid4()),
                engine=self.engine if self.engine in {"xmage", "forge", "tactical"} else "unknown",
                engine_version=self.engine_version,
                game_id=game_id,
                message_type=message_type,
                payload=params or {},
                method=message_type.value,
                params=params or {},
            )
            self._process.stdin.write(json.dumps(request.wire_dict(), sort_keys=True) + "\n")
            self._process.stdin.flush()
            wait = self.request_timeout_seconds if timeout_seconds is None else timeout_seconds
            try:
                line = self._stdout_queue.get(timeout=wait)
            except queue.Empty as exc:
                raise RulesEngineProtocolError(
                    f"bridge timeout after {wait:.3f}s for {message_type.value!r}"
                ) from exc
            if line is None:
                raise RulesEngineProtocolError(
                    f"bridge closed before replying to {message_type.value!r}: "
                    + " | ".join(self.stderr_tail)
                )
            try:
                response = EngineProtocolResponse.from_wire(json.loads(line))
            except Exception as exc:
                raise RulesEngineProtocolError(
                    f"invalid JSONL bridge response for {message_type.value!r}: {line!r}"
                ) from exc
            if response.protocol_version != self.protocol_version:
                raise RulesEngineProtocolError(
                    f"protocol version mismatch: expected {self.protocol_version}, "
                    f"received {response.protocol_version}"
                )
            if response.request_id != request.request_id:
                raise RulesEngineProtocolError("bridge response request_id does not match request")
            if not response.success:
                error = response.errors[0] if response.errors else None
                raise RulesEngineProtocolError(
                    f"bridge message {message_type.value!r} failed: "
                    f"{error.code if error else 'unknown'}: {error.message if error else 'unknown error'}"
                )
            return response.payload

    def legacy_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self.start()
            assert self._process is not None and self._process.stdin is not None
            request_id = str(uuid.uuid4())
            self._process.stdin.write(
                json.dumps({"request_id": request_id, "method": method, "params": params or {}}) + "\n"
            )
            self._process.stdin.flush()
            try:
                line = self._stdout_queue.get(timeout=self.request_timeout_seconds)
            except queue.Empty as exc:
                raise RulesEngineProtocolError(f"legacy bridge timeout for {method!r}") from exc
            if line is None:
                raise RulesEngineProtocolError("legacy bridge returned no response")
            obj = json.loads(line)
            if obj.get("request_id") != request_id:
                raise RulesEngineProtocolError("legacy response request_id mismatch")
            if not obj.get("ok"):
                raise RulesEngineProtocolError(str(obj.get("error")))
            return dict(obj.get("result") or {})

    def handshake(self) -> tuple[dict[str, Any], EngineCapabilityHandshake]:
        hello = self.request(EngineMessageType.ENGINE_HELLO)
        caps_raw = self.request(EngineMessageType.ENGINE_CAPABILITIES)
        caps = EngineCapabilityHandshake.model_validate(
            caps_raw.get("capabilities", caps_raw)
        )
        return hello, caps

    def close(self) -> None:
        with self._lock:
            process = self._process
            if process is None:
                return
            stdout_thread = self._stdout_thread
            stderr_thread = self._stderr_thread
            try:
                if process.poll() is None:
                    try:
                        self.request(EngineMessageType.SHUTDOWN_GAME, timeout_seconds=2.0)
                    except Exception:
                        process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            finally:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None and not stream.closed:
                        stream.close()
                current = threading.current_thread()
                for thread in (stdout_thread, stderr_thread):
                    if thread is not None and thread is not current:
                        thread.join(timeout=2)
                self._process = None
                self._stdout_thread = None
                self._stderr_thread = None


class ExternalRulesAdapter(RulesEngineAdapter):
    """Adapter for an actually installed Forge or XMage JSONL bridge."""

    def __init__(
        self,
        backend: RulesBackend,
        command: tuple[str, ...] | None = None,
        *,
        cwd: str | Path | None = None,
        request_timeout_seconds: float = 20.0,
    ) -> None:
        if backend not in {RulesBackend.FORGE, RulesBackend.XMAGE}:
            raise ValueError("ExternalRulesAdapter supports Forge or XMage only")
        self.backend = backend
        self.command = command or self.command_from_environment(backend)
        self.cwd = cwd
        self.request_timeout_seconds = request_timeout_seconds
        self._client: JsonLineBridgeClient | None = None
        self._capabilities: EngineCapabilityHandshake | None = None
        self._legacy_mode = False

    @staticmethod
    def command_from_environment(backend: RulesBackend) -> tuple[str, ...] | None:
        raw = os.getenv(_BACKEND_ENV[backend])
        return tuple(shlex.split(raw)) if raw else None

    def _require_client(self) -> JsonLineBridgeClient:
        if self.command is None:
            raise RulesEngineUnavailable(
                f"{self.backend.value} bridge is not configured; set {_BACKEND_ENV[self.backend]}"
            )
        if self._client is None:
            self._client = JsonLineBridgeClient(
                self.command,
                cwd=self.cwd,
                engine=self.backend.value,
                request_timeout_seconds=self.request_timeout_seconds,
            )
        return self._client

    def _require_capability(self, name: str) -> None:
        if self._capabilities is None:
            self.probe()
        if self._capabilities is None or not self._capabilities.supports(name):
            raise RulesEngineProtocolError(
                f"{self.backend.value} bridge did not advertise required capability {name}"
            )

    def probe(self) -> RulesEngineProbe:
        if self.command is None:
            return RulesEngineProbe(
                backend=self.backend,
                availability=RulesEngineAvailability.UNAVAILABLE,
                command=(),
                capabilities=RulesEngineCapabilities(),
                details=(f"set {_BACKEND_ENV[self.backend]} to a JSONL bridge command",),
            )
        try:
            client = self._require_client()
            try:
                hello, caps = client.handshake()
                if hello.get("engine") != self.backend.value:
                    raise RulesEngineProtocolError(
                        f"configured {self.backend.value} bridge identified itself as {hello.get('engine')}"
                    )
                self._capabilities = caps
                compatibility = RulesEngineCapabilities(
                    deck_loading=caps.deck_import_supported,
                    commander_games=caps.commander_supported,
                    deterministic_seed=caps.seed_supported,
                    reproducible_starting_state=caps.starting_state_injection_supported,
                    scenario_injection=caps.scenario_injection_supported,
                    legal_action_query=caps.legal_actions_supported,
                    action_submission=caps.action_submission_supported,
                    event_logs=caps.event_log_supported,
                    game_logs=caps.event_log_supported,
                    multiplayer=caps.multiplayer_supported,
                    maximum_players=caps.max_players,
                    **caps.model_dump(),
                )
                return RulesEngineProbe(
                    backend=self.backend,
                    availability=RulesEngineAvailability.AVAILABLE,
                    backend_version=str(hello.get("engine_version") or "unknown"),
                    command=self.command,
                    capabilities=compatibility,
                    details=("versioned capability handshake succeeded",),
                )
            except RulesEngineProtocolError:
                # Phase-8 legacy bridge compatibility. A legacy probe is never
                # sufficient for the process manager's `healthy` status.
                result = client.request("engine_hello") if False else None
                raise
        except Exception as exc:
            # Old fixtures can still expose a `probe` only. This is deliberately
            # reported as a degraded compatibility probe.
            try:
                if self._client is None:
                    raise exc
                raw = self._legacy_request("probe")
                probe = RulesEngineProbe.model_validate(raw)
                if probe.backend != self.backend:
                    raise RulesEngineProtocolError(
                        f"configured {self.backend.value} bridge identified itself as {probe.backend.value}"
                    )
                self._legacy_mode = True
                self._capabilities = EngineCapabilityHandshake(
                    commander_supported=probe.capabilities.commander_games,
                    partner_supported=False,
                    multiplayer_supported=probe.capabilities.multiplayer,
                    max_players=probe.capabilities.maximum_players,
                    headless_supported=True,
                    seed_supported=probe.capabilities.deterministic_seed,
                    deck_import_supported=probe.capabilities.deck_loading,
                    legal_actions_supported=probe.capabilities.legal_action_query,
                    action_submission_supported=probe.capabilities.action_submission,
                    event_log_supported=probe.capabilities.event_logs,
                    replay_supported=False,
                    starting_state_injection_supported=probe.capabilities.reproducible_starting_state,
                    scenario_injection_supported=probe.capabilities.scenario_injection,
                    runtime_kind="unknown",
                    notes=("legacy Phase-8 probe; not sufficient for external health",),
                )
                return probe.model_copy(
                    update={"details": tuple(probe.details) + ("legacy protocol compatibility",)}
                )
            except Exception:
                return RulesEngineProbe(
                    backend=self.backend,
                    availability=RulesEngineAvailability.MISCONFIGURED,
                    command=self.command,
                    capabilities=RulesEngineCapabilities(),
                    details=(f"{type(exc).__name__}: {exc}",),
                )

    def _legacy_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send an old Phase-8 request on the persistent compatibility process."""
        return self._require_client().legacy_request(method, params)

    def load_deck(self, deck: RulesDeckInput) -> RulesDeckHandle:
        self._require_capability("deck_import_supported")
        if self._legacy_mode:
            result = self._legacy_request("load_deck", {"deck": deck.model_dump(mode="json")})
            return RulesDeckHandle.model_validate(result)
        result = self._require_client().request(
            EngineMessageType.LOAD_DECK, {"deck": deck.model_dump(mode="json")}
        )
        handle = RulesDeckHandle.model_validate(result.get("deck_handle", result))
        if handle.backend != self.backend:
            raise RulesEngineProtocolError(
                f"{self.backend.value} bridge returned a {handle.backend.value} deck handle"
            )
        return handle

    def start_commander_game(self, request: RulesGameRequest) -> RulesSession:
        self._require_capability("commander_supported")
        self._require_capability("multiplayer_supported")
        if self._legacy_mode:
            return RulesSession.model_validate(
                self._legacy_request("start_commander_game", {"request": request.model_dump(mode="json")})
            )
        result = self._require_client().request(
            EngineMessageType.CREATE_GAME, {"request": request.model_dump(mode="json")}, game_id=request.game_id
        )
        game_id = str(result.get("game_id", request.game_id))
        self._require_client().request(EngineMessageType.START_GAME, {}, game_id=game_id)
        state_payload = self._require_client().request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
        state = GameState.model_validate(state_payload.get("state", state_payload))
        return RulesSession(
            backend=self.backend, session_id=game_id, game_id=game_id, state=state,
            seed=request.seed, deck_handles=request.deck_handles, created_from="game"
        )

    def create_scenario(self, scenario: TacticalScenario) -> RulesSession:
        self._require_capability("scenario_injection_supported")
        if self._legacy_mode:
            return RulesSession.model_validate(
                self._legacy_request("create_scenario", {"scenario": scenario.model_dump(mode="json")})
            )
        result = self._require_client().request(
            EngineMessageType.CREATE_GAME,
            {"scenario": scenario.model_dump(mode="json")},
            game_id=scenario.state.game_id,
        )
        state = GameState.model_validate(result.get("state", scenario.state.model_dump(mode="json")))
        return RulesSession(
            backend=self.backend,
            session_id=str(result.get("game_id", scenario.state.game_id)),
            game_id=scenario.state.game_id,
            state=state,
            seed=scenario.state.seed,
            scenario_id=scenario.scenario_id,
            created_from="scenario",
        )

    def get_state(self, session_id: str) -> GameState:
        if self._legacy_mode:
            result = self._legacy_request("get_state", {"session_id": session_id})
            return GameState.model_validate(result["state"])
        result = self._require_client().request(
            EngineMessageType.GET_GAME_STATE, {}, game_id=session_id
        )
        return GameState.model_validate(result.get("state", result))

    def get_legal_actions(self, session_id: str) -> tuple[LegalAction, ...]:
        self._require_capability("legal_actions_supported")
        if self._legacy_mode:
            result = self._legacy_request("get_legal_actions", {"session_id": session_id})
            return tuple(LegalAction.model_validate(item) for item in result["actions"])
        result = self._require_client().request(
            EngineMessageType.GET_LEGAL_ACTIONS, {}, game_id=session_id
        )
        return tuple(LegalAction.model_validate(item) for item in result.get("actions", ()))

    def submit_action(self, session_id: str, proposal: ActionProposal) -> GameState:
        self._require_capability("action_submission_supported")
        if self._legacy_mode:
            result = self._legacy_request(
                "submit_action",
                {"session_id": session_id, "proposal": proposal.model_dump(mode="json")},
            )
            return GameState.model_validate(result["state"])
        result = self._require_client().request(
            EngineMessageType.SUBMIT_ACTION,
            {"proposal": proposal.model_dump(mode="json")},
            game_id=session_id,
        )
        return GameState.model_validate(result.get("state", result))

    def get_logs(self, session_id: str) -> RulesEngineLog:
        self._require_capability("event_log_supported")
        if self._legacy_mode:
            return RulesEngineLog.model_validate(
                self._legacy_request("get_logs", {"session_id": session_id})
            )
        result = self._require_client().request(
            EngineMessageType.GET_EVENT_LOG, {}, game_id=session_id
        )
        return RulesEngineLog.model_validate(result.get("log", result))

    def get_result(self, session_id: str) -> RulesEngineResult:
        if self._legacy_mode:
            raise RulesEngineProtocolError(
                "legacy bridge results are unverified and cannot be promoted to rules_engine_validated"
            )
        if self._capabilities is None:
            self.probe()
        if self._capabilities is None or self._capabilities.runtime_kind != "external_rules_engine":
            raise RulesEngineProtocolError(
                "bridge did not provide an external_rules_engine capability attestation"
            )
        state = self.get_state(session_id)
        return RulesEngineResult(
            backend=self.backend,
            session_id=session_id,
            completed=state.status.value == "completed",
            final_state=state,
            normalized_result={},
            validation_level="rules_engine_validated",
            backend_version=None,
            warnings=("result derived from versioned state endpoint",),
        )

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


class ForgeRulesAdapter(ExternalRulesAdapter):
    def __init__(self, command: tuple[str, ...] | None = None, *, cwd: str | Path | None = None):
        super().__init__(RulesBackend.FORGE, command, cwd=cwd)


class XMageRulesAdapter(ExternalRulesAdapter):
    def __init__(self, command: tuple[str, ...] | None = None, *, cwd: str | Path | None = None):
        super().__init__(RulesBackend.XMAGE, command, cwd=cwd)


__all__ = [
    "ExternalRulesAdapter",
    "ForgeRulesAdapter",
    "JsonLineBridgeClient",
    "XMageRulesAdapter",
]
