"""Candidate-neutral external bridge process launcher (current boundary).

Launches the exact pinned candidate builds as **separate external processes**
over the Protocol 2.0.0 JSONL transport. The launcher never inspects engine
internals, never computes legality, and never fabricates a response.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .source_lock import (
    CURRENT_TRANSPORT_PROTOCOL,
    FORGE_CANDIDATE_COMMIT,
    XMAGE_CANDIDATE_COMMIT,
    repo_root,
)

CandidateId = Literal["xmage", "forge"]

DEFAULT_TIMEOUT_S = 180.0


class BridgeLaunchError(RuntimeError):
    """Raised when an exact candidate build cannot be launched."""


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
        raw = self.popen.stdout.readline()
        if not raw:
            stderr = ""
            if self.popen.stderr is not None:
                stderr = self.popen.stderr.read()[-2000:]
            raise BridgeLaunchError(f"bridge closed stdout (stderr tail: {stderr})")
        try:
            response = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BridgeLaunchError(f"non-JSON provider response: {raw[:200]!r}") from exc
        self.transcript.append({"direction": "response", "received": response, "request": envelope})
        payload: dict[str, Any] = response
        return payload

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
        # "full-game" is the dedicated full-game JSONL lane; "compat"/"" select
        # the generic Protocol-2 compatibility lane that both candidates
        # implement, which is the candidate-neutral comparison surface.
        resolved_lane = "full-game" if lane in (None, "full-game") else "compatibility"
        lane_args = ("full-game",) if resolved_lane == "full-game" else ()
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
            cwd=workspace,
            env_overrides={},
            expected_engine_commit=XMAGE_CANDIDATE_COMMIT,
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
            cwd=forge_workspace,
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
