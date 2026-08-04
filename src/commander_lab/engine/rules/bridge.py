from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from commander_lab.models import (
    ActionProposal,
    BridgeRequest,
    BridgeResponse,
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

from .base import (
    RulesEngineAdapter,
    RulesEngineProtocolError,
    RulesEngineUnavailable,
)


_BACKEND_ENV = {
    RulesBackend.FORGE: "COMMANDER_LAB_FORGE_BRIDGE_CMD",
    RulesBackend.XMAGE: "COMMANDER_LAB_XMAGE_BRIDGE_CMD",
}


class JsonLineBridgeClient:
    """Persistent JSON-lines RPC client used by Forge/XMage bridge processes."""

    def __init__(
        self,
        command: tuple[str, ...],
        *,
        cwd: str | Path | None = None,
        startup_timeout_seconds: float = 20.0,
    ) -> None:
        if not command:
            raise ValueError("bridge command must not be empty")
        self.command = command
        self.cwd = None if cwd is None else str(cwd)
        self.startup_timeout_seconds = startup_timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

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

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self.start()
            assert self._process is not None
            if self._process.stdin is None or self._process.stdout is None:
                raise RulesEngineProtocolError("bridge process pipes are unavailable")
            request = BridgeRequest(
                request_id=str(uuid.uuid4()), method=method, params=params or {}
            )
            self._process.stdin.write(request.model_dump_json() + "\n")
            self._process.stdin.flush()
            line = self._process.stdout.readline()
            if not line:
                stderr = ""
                if self._process.stderr is not None:
                    stderr = self._process.stderr.read()
                raise RulesEngineProtocolError(
                    f"bridge closed before replying to {method!r}: {stderr.strip()}"
                )
            try:
                response = BridgeResponse.model_validate_json(line)
            except Exception as exc:
                raise RulesEngineProtocolError(
                    f"invalid JSONL bridge response for {method!r}: {line!r}"
                ) from exc
            if response.request_id != request.request_id:
                raise RulesEngineProtocolError(
                    "bridge response request_id does not match the request"
                )
            if not response.ok:
                error = response.error or {}
                raise RulesEngineProtocolError(
                    f"bridge method {method!r} failed: {error.get('code', 'unknown')}: "
                    f"{error.get('message', error)}"
                )
            assert response.result is not None
            return response.result

    def close(self) -> None:
        with self._lock:
            if self._process is None:
                return
            if self.running:
                try:
                    self.request("shutdown")
                except Exception:
                    self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            self._process = None


class ExternalRulesAdapter(RulesEngineAdapter):
    """Base adapter for an installed Forge or XMage JSONL bridge."""

    def __init__(
        self,
        backend: RulesBackend,
        command: tuple[str, ...] | None = None,
        *,
        cwd: str | Path | None = None,
    ) -> None:
        if backend not in {RulesBackend.FORGE, RulesBackend.XMAGE}:
            raise ValueError("ExternalRulesAdapter supports Forge or XMage only")
        self.backend = backend
        self.command = command or self.command_from_environment(backend)
        self.cwd = cwd
        self._client: JsonLineBridgeClient | None = None

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
            self._client = JsonLineBridgeClient(self.command, cwd=self.cwd)
        return self._client

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
            result = self._require_client().request("probe")
            probe = RulesEngineProbe.model_validate(result)
            if probe.backend != self.backend:
                raise RulesEngineProtocolError(
                    f"configured {self.backend.value} bridge identified itself as {probe.backend.value}"
                )
            return probe
        except Exception as exc:
            return RulesEngineProbe(
                backend=self.backend,
                availability=RulesEngineAvailability.MISCONFIGURED,
                command=self.command,
                capabilities=RulesEngineCapabilities(),
                details=(f"{type(exc).__name__}: {exc}",),
            )

    def load_deck(self, deck: RulesDeckInput) -> RulesDeckHandle:
        result = self._require_client().request(
            "load_deck", {"deck": deck.model_dump(mode="json")}
        )
        handle = RulesDeckHandle.model_validate(result)
        if handle.backend != self.backend:
            raise RulesEngineProtocolError(
                f"{self.backend.value} bridge returned a {handle.backend.value} deck handle"
            )
        return handle

    def start_commander_game(self, request: RulesGameRequest) -> RulesSession:
        result = self._require_client().request(
            "start_commander_game", {"request": request.model_dump(mode="json")}
        )
        session = RulesSession.model_validate(result)
        if session.backend != self.backend:
            raise RulesEngineProtocolError(
                f"{self.backend.value} bridge returned a {session.backend.value} session"
            )
        return session

    def create_scenario(self, scenario: TacticalScenario) -> RulesSession:
        result = self._require_client().request(
            "create_scenario", {"scenario": scenario.model_dump(mode="json")}
        )
        session = RulesSession.model_validate(result)
        if session.backend != self.backend:
            raise RulesEngineProtocolError(
                f"{self.backend.value} bridge returned a {session.backend.value} session"
            )
        return session

    def get_state(self, session_id: str) -> GameState:
        result = self._require_client().request("get_state", {"session_id": session_id})
        return GameState.model_validate(result["state"])

    def get_legal_actions(self, session_id: str) -> tuple[LegalAction, ...]:
        result = self._require_client().request(
            "get_legal_actions", {"session_id": session_id}
        )
        return tuple(LegalAction.model_validate(item) for item in result["actions"])

    def submit_action(self, session_id: str, proposal: ActionProposal) -> GameState:
        result = self._require_client().request(
            "submit_action",
            {"session_id": session_id, "proposal": proposal.model_dump(mode="json")},
        )
        return GameState.model_validate(result["state"])

    def get_logs(self, session_id: str) -> RulesEngineLog:
        result = self._require_client().request("get_logs", {"session_id": session_id})
        return RulesEngineLog.model_validate(result)

    def get_result(self, session_id: str) -> RulesEngineResult:
        result = self._require_client().request("get_result", {"session_id": session_id})
        engine_result = RulesEngineResult.model_validate(result)
        if engine_result.backend != self.backend:
            raise RulesEngineProtocolError(
                f"{self.backend.value} bridge returned a {engine_result.backend.value} result"
            )
        return engine_result

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
