"""Candidate-neutral external bridge process launcher (current boundary).

Launches the exact pinned candidate builds as **separate external processes**
over the Protocol 2.0.0 JSONL transport. The launcher never inspects engine
internals, never computes legality, and never fabricates a response.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from commander_lab.engine.rules.base import resolve_engine_working_directory

from .source_lock import (
    CURRENT_TRANSPORT_PROTOCOL,
    FORGE_CANDIDATE_COMMIT,
    repo_root,
)

CandidateId = Literal["xmage", "forge"]

DEFAULT_TIMEOUT_S = 180.0

_SHA40 = re.compile(r"[0-9a-f]{40}")


def canonical_xmage_engine_pin() -> str:
    """The canonical live XMage candidate commit.

    ``config/rules_engines.json`` is the sole machine-readable authority for
    current engine pins. The frozen WSR22 ``source_lock`` identity is
    deliberately not repinned and remains the historical WSR22 evidence epoch;
    a live launch must bind the canonical pin so its evidence can never be
    attributed to an engine commit that did not execute.
    """
    manifest_path = repo_root() / "config" / "rules_engines.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    commit = manifest.get("primary_engine", {}).get("commit")
    if not isinstance(commit, str) or _SHA40.fullmatch(commit) is None:
        raise BridgeLaunchError(f"canonical XMage engine pin is missing or malformed: {commit!r}")
    return commit


def _candidate_runtime_cwd(candidate: CandidateId) -> Path:
    """Return a dedicated mutable runtime directory outside candidate worktrees."""
    resolved = resolve_engine_working_directory(None)
    if resolved is None:
        raise BridgeLaunchError("engine runtime directory resolution returned no path")
    target = Path(resolved) / "current-boundary" / candidate
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BridgeLaunchError(
            f"unable to create current-boundary runtime directory {target}: {exc}"
        ) from exc
    return target


class BridgeLaunchError(RuntimeError):
    """Raised when an exact candidate build cannot be launched."""


class BridgeTimeout(BridgeLaunchError):
    """A provider accepted a request and did not answer inside the deadline.

    Distinct from a launch failure and from a protocol failure so a stalled
    candidate is classified TIMEOUT rather than being folded into either. It
    subclasses ``BridgeLaunchError`` so every existing fail-closed handler still
    catches it; nothing converts it into a PASS or a default.
    """


@dataclass(frozen=True)
class LaunchPlan:
    """An exact, reproducible external-process launch recipe."""

    candidate: CandidateId
    lane: str
    argv: tuple[str, ...]
    cwd: Path
    env_overrides: dict[str, str]
    expected_engine_commit: str
    build_identity: dict[str, str]
    workspace: str
    mutates_reference_repository: bool = False


@dataclass
class BridgeProcess:
    """A live external candidate bridge speaking Protocol 2.0.0."""

    plan: LaunchPlan
    popen: subprocess.Popen[str]
    transcript: list[dict[str, Any]] = field(default_factory=list)

    def request(
        self,
        message_type: str,
        params: dict[str, Any] | None = None,
        *,
        game_id: str | None = None,
        protocol_version: str = CURRENT_TRANSPORT_PROTOCOL,
        request_id: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Send one Protocol-2 request and return the parsed response.

        This is a transport call only. It performs no legality reasoning and
        applies no default to a failed or malformed provider response.
        """
        rid = request_id or str(uuid.uuid4())
        envelope: dict[str, Any] = {
            "protocol_version": protocol_version,
            "request_id": rid,
            "message_type": message_type,
        }
        if game_id is not None:
            envelope["game_id"] = game_id
        if params is not None:
            # The canonical Protocol-2 wire form carries the request body under
            # BOTH `payload` and `params` (EngineProtocolRequest.wire_dict). Some
            # providers read `payload`, others read `params`; emitting only one
            # of them would be a harness defect, not an engine difference.
            envelope["payload"] = params
            envelope["params"] = params
        line = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        self.transcript.append({"direction": "request", "sent": envelope})
        try:
            assert self.popen.stdin is not None
            assert self.popen.stdout is not None
            self.popen.stdin.write(line + "\n")
            self.popen.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:  # pragma: no cover - transport failure
            raise BridgeLaunchError(f"bridge stdin unavailable: {exc}") from exc
        raw = self._read_line_with_deadline(timeout_s, message_type, rid)
        if not raw:
            stderr = ""
            if self.popen.stderr is not None:
                stderr = self.popen.stderr.read()[-2000:]
            raise BridgeLaunchError(
                f"bridge closed stdout for {message_type} (stderr tail: {stderr})"
            )
        try:
            response = json.loads(raw)
        except json.JSONDecodeError as exc:
            # A partial or malformed line is a protocol failure, never a PASS and
            # never a silent default.
            raise BridgeLaunchError(
                f"non-JSON provider response for {message_type}: {raw[:200]!r}"
            ) from exc
        self.transcript.append({"direction": "response", "received": response, "request": envelope})
        payload: dict[str, Any] = response
        return payload

    def _read_line_with_deadline(self, timeout_s: float, message_type: str, request_id: str) -> str:
        """Read exactly one response line under a real wall-clock deadline.

        A blocking ``readline()`` with no deadline hangs the whole qualification
        when a provider accepts a request and then stalls, so the run can never
        reach a TIMEOUT classification, can never move to the other candidate, and
        leaves a live child behind.

        The read runs on a daemon thread and is joined against the deadline. On
        expiry the child is terminated and reaped (so no zombie survives and the
        caller can continue), the applied timeout is recorded in the transcript,
        and a ``BridgeTimeout`` is raised. A thread is used rather than ``select``
        because the stream is a buffered ``TextIOWrapper``, whose fd-level
        readiness does not imply a complete line is available.
        """
        assert self.popen.stdout is not None
        self._last_timeout_s = timeout_s
        result: list[str] = []
        finished = threading.Event()

        def _read() -> None:
            try:
                result.append(self.popen.stdout.readline())  # type: ignore[union-attr]
            except (OSError, ValueError):
                result.append("")
            finally:
                finished.set()

        worker = threading.Thread(target=_read, name="bridge-read", daemon=True)
        worker.start()
        if not finished.wait(timeout_s):
            self.transcript.append(
                {
                    "direction": "timeout",
                    "message_type": message_type,
                    "request_id": request_id,
                    "timeout_s": timeout_s,
                    "classification": "TIMEOUT",
                }
            )
            self._terminate_stalled_child()
            raise BridgeTimeout(
                f"BRIDGE_TIMEOUT: no response to {message_type} within {timeout_s}s; "
                "child terminated and reaped, classified TIMEOUT"
            )
        return result[0] if result else ""

    def _terminate_stalled_child(self) -> None:
        """Kill and reap a stalled child so no zombie is left behind."""
        popen = self.popen
        with contextlib.suppress(OSError, ValueError):
            if popen.stdin is not None:
                popen.stdin.close()
        with contextlib.suppress(OSError, ValueError, subprocess.TimeoutExpired):
            popen.kill()
        with contextlib.suppress(OSError, ValueError, subprocess.TimeoutExpired):
            popen.wait(timeout=5)

    def close(self, *, timeout_s: float = 20.0) -> None:
        """Best-effort graceful shutdown; never raises on an already-dead bridge."""
        for message in ("shutdown_game", "shutdown_engine"):
            try:
                self.request(message, {}, timeout_s=timeout_s)
            except (BridgeLaunchError, AssertionError, OSError):
                break
        with contextlib.suppress(OSError):
            if self.popen.stdin is not None:
                self.popen.stdin.close()
        try:
            self.popen.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self.popen.kill()
        finally:
            for stream in (self.popen.stdout, self.popen.stderr):
                if stream is not None:
                    with contextlib.suppress(OSError):
                        stream.close()

    def __enter__(self) -> BridgeProcess:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _read_classpath(workspace: Path, relative: str) -> str:
    path = workspace / relative
    if not path.is_file():
        raise BridgeLaunchError(
            f"missing classpath manifest {path}; build the candidate module first"
        )
    return path.read_text(encoding="utf-8").strip()


def build_launch_plan(
    candidate: CandidateId,
    *,
    lane: str | None = None,
    xmage_workspace: Path | None = None,
    forge_workspace: Path | None = None,
) -> LaunchPlan:
    """Build the exact launch recipe for a candidate.

    ``xmage_workspace`` is the Lab ``engine-bridge`` module (Lab-owned build
    output). ``forge_workspace`` is a read-only reference Forge checkout that
    is *built and executed* but never edited.
    """
    if candidate == "xmage":
        workspace = xmage_workspace or (repo_root() / "engine-bridge")
        # "full-game" is the dedicated full-game JSONL lane; "midgame" is the
        # dedicated starting-state mid-game lane (production-reachable PB-03
        # transport); "compat"/"" select the generic Protocol-2 compatibility
        # lane that both candidates implement, which is the candidate-neutral
        # comparison surface. Every dedicated lane shares this one launch
        # contract: the same classpath manifest, the same isolated runtime cwd
        # outside any candidate worktree, and the same cleared parent env.
        if lane in (None, "full-game"):
            resolved_lane = "full-game"
        elif lane == "midgame":
            resolved_lane = "midgame"
        else:
            resolved_lane = "compatibility"
        lane_args = (resolved_lane,) if resolved_lane in ("full-game", "midgame") else ()
        classpath = _read_classpath(workspace, "target/cp-wsr22.txt")
        argv = (
            "java",
            "-Djava.awt.headless=true",
            f"-Dcommanderlab.repoRoot={workspace.parent}",
            "-cp",
            f"{workspace / 'target' / 'classes'}:{classpath}",
            "org.commanderlab.xmage.Main",
            *lane_args,
        )
        return LaunchPlan(
            candidate=candidate,
            lane=resolved_lane,
            argv=argv,
            cwd=_candidate_runtime_cwd("xmage"),
            env_overrides={},
            expected_engine_commit=canonical_xmage_engine_pin(),
            build_identity={
                "module": "engine-bridge",
                "classes": str(workspace / "target" / "classes"),
                "classpath_manifest": str(workspace / "target" / "cp-wsr22.txt"),
                "maven_coordinates": "org.mage:mage:1.4.61",
            },
            workspace=str(workspace),
        )

    if candidate == "forge":
        if forge_workspace is None:
            raise BridgeLaunchError(
                "a read-only Forge reference workspace is required to launch the Forge candidate"
            )
        module = forge_workspace / "forge-protocol2-bridge"
        classpath = _read_classpath(module, "target/cp-wsr22.txt")
        argv = (
            "java",
            "-Djava.awt.headless=true",
            "-cp",
            f"{module / 'target' / 'classes'}:{classpath}",
            "forge.bridge.BridgeMain",
        )
        return LaunchPlan(
            candidate=candidate,
            lane="protocol2-jsonl",
            argv=argv,
            cwd=_candidate_runtime_cwd("forge"),
            env_overrides={
                "FORGE_ENGINE_SHA": FORGE_CANDIDATE_COMMIT,
                "FORGE_ASSETS_DIR": str(forge_workspace / "forge-gui"),
            },
            expected_engine_commit=FORGE_CANDIDATE_COMMIT,
            build_identity={
                "module": "forge-protocol2-bridge",
                "classes": str(module / "target" / "classes"),
                "classpath_manifest": str(module / "target" / "cp-wsr22.txt"),
                "engine_commit_provenance": "env:FORGE_ENGINE_SHA (provider-reported, not build-derived)",
            },
            workspace=str(forge_workspace),
            mutates_reference_repository=False,
        )

    raise BridgeLaunchError(f"unknown candidate: {candidate!r}")


def launch(plan: LaunchPlan, *, timeout_s: float = 60.0) -> BridgeProcess:
    """Start the external candidate process."""
    env = dict(os.environ)
    env.pop("JAVA_TOOL_OPTIONS", None)
    env.update(plan.env_overrides)
    try:
        popen = subprocess.Popen(
            list(plan.argv),
            cwd=str(plan.cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        raise BridgeLaunchError(f"cannot launch {plan.candidate}: {exc}") from exc
    return BridgeProcess(plan=plan, popen=popen)


def iter_responses(proc: BridgeProcess) -> Iterator[dict[str, Any]]:  # pragma: no cover
    """Yield responses from a live bridge (diagnostic helper)."""
    assert proc.popen.stdout is not None
    for line in proc.popen.stdout:
        if line.strip():
            yield json.loads(line)
