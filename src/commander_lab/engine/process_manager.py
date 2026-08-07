from __future__ import annotations

import os
import shlex
import shutil
import signal
import socket
import subprocess
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    EngineProcessState,
    EngineProcessStatus,
    EngineRuntimeConfig,
    EngineRuntimeMode,
)
from commander_lab.storage.atomic import atomic_write_text


def _now() -> datetime:
    return datetime.now(UTC)


def _split_command(value: str | None) -> tuple[str, ...]:
    return tuple(shlex.split(value)) if value else ()


def load_engine_runtime_config(env: Mapping[str, str] | None = None) -> EngineRuntimeConfig:
    source = os.environ if env is None else env
    mode = source.get("ENGINE_MODE", "external")
    return EngineRuntimeConfig(
        provider=source.get("ENGINE_PROVIDER", "xmage"),
        mode=EngineRuntimeMode(mode),
        home=source.get("ENGINE_HOME") or None,
        source_path=source.get("ENGINE_SOURCE_PATH") or None,
        binary_path=source.get("ENGINE_BINARY_PATH") or None,
        host=source.get("ENGINE_HOST", "127.0.0.1"),
        port=int(source["ENGINE_PORT"]) if source.get("ENGINE_PORT") else None,
        start_command=_split_command(source.get("ENGINE_START_COMMAND")),
        stop_command=_split_command(source.get("ENGINE_STOP_COMMAND")),
        healthcheck_timeout_seconds=float(source.get("ENGINE_HEALTHCHECK_TIMEOUT", "20")),
        request_timeout_seconds=float(source.get("ENGINE_REQUEST_TIMEOUT", "20")),
        protocol_version=source.get("ENGINE_PROTOCOL_VERSION", ENGINE_PROTOCOL_VERSION),
        java_home=source.get("JAVA_HOME") or None,
        maven_home=source.get("MAVEN_HOME") or None,
        allow_tactical_oracle_fallback=source.get(
            "ALLOW_TACTICAL_ORACLE_FALLBACK", "false"
        ).lower() in {"1", "true", "yes"},
        log_directory=source.get("ENGINE_LOG_DIRECTORY", ".runtime/engine"),
    )


class EngineProcessManager:
    """Lifecycle manager for an external rules-engine bridge.

    `healthy` is returned only after a real versioned handshake identifies the
    configured provider and reports runtime_kind=`external_rules_engine`.
    Tactical-oracle bridges are deliberately reported as degraded.
    """

    def __init__(self, config: EngineRuntimeConfig, *, root: str | Path = ".") -> None:
        self.config = config
        self.root = Path(root).resolve()
        self.log_dir = (self.root / config.log_directory).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._client: object | None = None
        self.state_path = self.log_dir / f"{config.provider}.process-state.json"
        self._state = EngineProcessState(
            provider=config.provider,
            status=EngineProcessStatus.NOT_CONFIGURED,
            details=(),
            stdout_log=str(self.log_dir / f"{config.provider}.bridge.stdout.jsonl"),
            stderr_log=str(self.log_dir / f"{config.provider}.bridge.stderr.log"),
        )
        self._lock = threading.RLock()

    @property
    def state(self) -> EngineProcessState:
        return self._state

    def _replace(self, **updates: object) -> EngineProcessState:
        self._state = self._state.model_copy(update=updates)
        atomic_write_text(self.state_path, self._state.model_dump_json(indent=2) + "\n")
        return self._state

    def diagnose(self) -> EngineProcessState:
        details: list[str] = []
        if self.config.mode != EngineRuntimeMode.EXTERNAL:
            return self._replace(
                status=EngineProcessStatus.EXTERNAL_RUNTIME_REQUIRED,
                details=(f"mode is {self.config.mode.value}, not external",),
            )
        if not self.config.start_command:
            return self._replace(
                status=EngineProcessStatus.NOT_CONFIGURED,
                details=("ENGINE_START_COMMAND is empty",),
            )
        executable = self.config.start_command[0]
        if not (Path(executable).exists() or shutil.which(executable)):
            return self._replace(
                status=EngineProcessStatus.DEPENDENCIES_MISSING,
                details=(f"start executable not found: {executable}",),
            )
        if self.config.source_path and not Path(self.config.source_path).exists():
            details.append(f"source path missing: {self.config.source_path}")
        if self.config.binary_path and not Path(self.config.binary_path).exists():
            details.append(f"binary path missing: {self.config.binary_path}")
        if details:
            return self._replace(status=EngineProcessStatus.SOURCE_MISSING, details=tuple(details))
        return self._replace(
            status=EngineProcessStatus.BUILT_NOT_STARTED,
            details=("external start command is configured",),
        )

    def port_available(self) -> bool | None:
        if self.config.port is None:
            return None
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex((self.config.host, self.config.port)) != 0

    def start(self) -> EngineProcessState:
        with self._lock:
            preflight = self.diagnose()
            if preflight.status not in {
                EngineProcessStatus.BUILT_NOT_STARTED,
                EngineProcessStatus.STOPPED,
                EngineProcessStatus.UNHEALTHY,
                EngineProcessStatus.DEGRADED,
            }:
                return preflight
            self._replace(status=EngineProcessStatus.STARTING, started_at=_now(), details=())
            from commander_lab.engine.rules.bridge import JsonLineBridgeClient

            self._client = JsonLineBridgeClient(
                self.config.start_command,
                cwd=self.config.home or self.root,
                startup_timeout_seconds=self.config.healthcheck_timeout_seconds,
                request_timeout_seconds=self.config.request_timeout_seconds,
                engine=self.config.provider,
                protocol_version=self.config.protocol_version,
                log_directory=self.log_dir,
            )
            try:
                self._client.start()
                return self.healthcheck()
            except Exception as exc:
                return self._replace(
                    status=EngineProcessStatus.UNHEALTHY,
                    pid=self._client.pid if self._client else None,
                    last_healthcheck_at=_now(),
                    details=(f"{type(exc).__name__}: {exc}",),
                )

    def healthcheck(self) -> EngineProcessState:
        with self._lock:
            if self._client is None or not self._client.running:
                return self._replace(
                    status=EngineProcessStatus.STOPPED,
                    last_healthcheck_at=_now(),
                    details=("bridge process is not running",),
                )
            try:
                hello, capabilities = self._client.handshake()
                engine = str(hello.get("engine", ""))
                engine_version = str(hello.get("engine_version", "unknown"))
                if engine != self.config.provider:
                    detail = (
                        f"provider mismatch: configured {self.config.provider}, "
                        f"received {engine}"
                    )
                    return self._replace(
                        status=EngineProcessStatus.UNHEALTHY,
                        pid=self._client.pid,
                        engine_version=engine_version,
                        last_healthcheck_at=_now(),
                        details=(detail,),
                    )
                if capabilities.runtime_kind != "external_rules_engine":
                    return self._replace(
                        status=EngineProcessStatus.DEGRADED,
                        pid=self._client.pid,
                        engine_version=engine_version,
                        capabilities=capabilities,
                        last_healthcheck_at=_now(),
                        details=(
                            f"handshake runtime_kind={capabilities.runtime_kind}; not external",
                        ),
                    )
                required = (
                    "commander_supported",
                    "multiplayer_supported",
                    "deck_import_supported",
                    "legal_actions_supported",
                    "action_submission_supported",
                    "event_log_supported",
                )
                missing = tuple(name for name in required if not capabilities.supports(name))
                if missing:
                    return self._replace(
                        status=EngineProcessStatus.DEGRADED,
                        pid=self._client.pid,
                        engine_version=engine_version,
                        capabilities=capabilities,
                        last_healthcheck_at=_now(),
                        details=("missing required capabilities: " + ", ".join(missing),),
                    )
                return self._replace(
                    status=EngineProcessStatus.HEALTHY,
                    pid=self._client.pid,
                    engine_version=engine_version,
                    capabilities=capabilities,
                    last_healthcheck_at=_now(),
                    details=("real external capability handshake succeeded",),
                )
            except Exception as exc:
                return self._replace(
                    status=EngineProcessStatus.UNHEALTHY,
                    pid=self._client.pid,
                    last_healthcheck_at=_now(),
                    details=(f"{type(exc).__name__}: {exc}",),
                )

    def stop(self) -> EngineProcessState:
        with self._lock:
            details: list[str] = []
            if self._client is not None:
                try:
                    self._client.close()
                except Exception as exc:
                    details.append(f"client close failed: {exc}")
                self._client = None
            if self.config.stop_command:
                try:
                    completed = subprocess.run(
                        self.config.stop_command,
                        cwd=self.config.home or self.root,
                        capture_output=True,
                        text=True,
                        timeout=self.config.healthcheck_timeout_seconds,
                        check=False,
                    )
                    if completed.returncode != 0:
                        detail = (
                            f"stop command exited {completed.returncode}: "
                            f"{completed.stderr.strip()}"
                        )
                        details.append(detail)
                except Exception as exc:
                    details.append(f"stop command failed: {exc}")
            return self._replace(
                status=EngineProcessStatus.STOPPED,
                pid=None,
                stopped_at=_now(),
                details=tuple(details) or ("stopped cleanly",),
            )

    def restart(self) -> EngineProcessState:
        self.stop()
        time.sleep(0.05)
        return self.start()


def stop_process_from_state(
    config: EngineRuntimeConfig, *, root: str | Path = "."
) -> EngineProcessState:
    root_path = Path(root).resolve()
    state_path = root_path / config.log_directory / f"{config.provider}.process-state.json"
    if not state_path.exists():
        return EngineProcessState(
            provider=config.provider,
            status=EngineProcessStatus.STOPPED,
            details=("no persisted process state",),
        )
    state = EngineProcessState.model_validate_json(state_path.read_text(encoding="utf-8"))
    if state.pid is not None:
        with suppress(ProcessLookupError, PermissionError):
            os.kill(state.pid, signal.SIGTERM)
    stopped = state.model_copy(
        update={
            "status": EngineProcessStatus.STOPPED,
            "pid": None,
            "stopped_at": _now(),
            "details": ("stop signal sent from persisted state",),
        }
    )
    atomic_write_text(state_path, stopped.model_dump_json(indent=2) + "\n")
    return stopped


__all__ = [
    "EngineProcessManager",
    "load_engine_runtime_config",
    "stop_process_from_state",
]
