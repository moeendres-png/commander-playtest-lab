"""Production-reachable mid-game starting-state capability, consumed from the engine.

The Rules Core is the only authority here. This module is transport plus
classification, never semantics: it launches the pinned candidate's
``midgame`` Protocol-2 lane, submits decisions the engine itself offered, and
records what the engine reported. It computes no legality, no cost, no target,
no mode, no division and no outcome.

Why this module exists
----------------------
The current-boundary qualification lane classified every mid-game obligation
fail-closed against a single coarse capability bit,
``starting_state_injection_supported``. That bit is false on both production
lanes, so a consumer had exactly one statement to read even though the pinned
engine's own restoration seam publishes a per-dimension manifest describing
precisely which starting-state dimensions it can construct. This module is the
consumer that was missing: it reads the engine's own per-dimension statement,
requests an explicit frozen starting state, and reports the engine's own
construction verdict.

It refuses to promote anything. A row is only ever reported as
``ENGINE_NATIVE_REACHABLE`` when the engine accepted the explicit starting state
and the engine's own field-level readback compare produced no mismatch outside
the documented declaration-step priority allowance. Everything else is reported
with the engine's own rejection code and stays fail-closed.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import threading
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .bridge_launcher import STDERR_DRAIN_GRACE_S, StderrCapture, StderrDrain

PROTOCOL_VERSION = "2.0.0"
#: Never inherited by a launch (see bridge_launcher.ORCHESTRATION_KEY_VARIABLE).
ORCHESTRATION_KEY_VARIABLE = "COMMANDER_LAB_ORCHESTRATION_KEY"
MIDGAME_LANE = "xmage_midgame_native_starting_state"
MIDGAME_RECEIPT_SCHEMA = "commander-lab.midgame-capability-probe/1.0.0"

# Every identity field a persisted mid-game receipt must carry before any of its
# rows can be described as fresh on the exact head that is being assembled. A
# receipt that names the engine but not the Lab runner that drove it cannot be
# distinguished from one produced by a different harness, so it is never fresh.
MIDGAME_RECEIPT_IDENTITY_FIELDS = (
    "runner_commit",
    "runner_tree",
    "runner_digest",
    "engine_commit",
)

# The loaded engine artifact identity, provider-reported. The declared engine
# commit is a constant; the artifact digest proves which bytes actually ran. A
# receipt that cannot name a file-backed artifact digest is unbound, never
# fresh.
_ENGINE_ARTIFACT_DIGEST = re.compile(r"[0-9a-f]{64}")

# Freshness classifications for a persisted mid-game receipt. They mirror the
# current-boundary receipt vocabulary so one staleness story holds across the
# whole evidence pipeline: a missing, empty or mismatched required identity is
# zero credit, never grandfathered.
MIDGAME_RECEIPT_FRESH = "FRESH_EXACT"
MIDGAME_RECEIPT_STALE = "STALE"
MIDGAME_RECEIPT_MISSING = "MISSING"
MIDGAME_RECEIPT_INVALID = "INVALID"

# Field prefixes the engine's readback may legitimately report differently at a
# declaration checkpoint. During a declaration step the engine does not hold
# priority the way the readback reports it, so ``priority_player`` may read as
# the next seat. This allowance is the engine seam's own documented arrival
# semantics, not a Lab relaxation: anything outside these prefixes is a real
# construction defect and fails the lane.
DECLARATION_STEP_PRIORITY_ALLOWANCE = ("priority_player:", "priority ")

Outcome = Literal[
    "ENGINE_NATIVE_REACHABLE",
    "ENGINE_STATE_ACCEPTED",
    "CAUSAL_ROUTE_REACHABLE",
    "CAUSAL_ROUTE_MEASURED_BLOCKED",
    "CONSTRUCTION_MISMATCH",
    "UNRECOGNIZED_CONSTRUCTION_VERDICT",
    "ENGINE_REJECTED",
    "TRANSPORT_FAILURE",
]


class MidgameLaneError(RuntimeError):
    """The mid-game lane could not be launched or answered.

    Raised when the engine is engaged and the lane's own scripted obligation
    could not be carried out from the engine's offered options. It never means
    the transport failed; transport and protocol failures are raised as the
    subclasses below so a caller cannot fold them into an engine verdict.
    """


class MidgameLaneTransportError(MidgameLaneError):
    """The transport or the child process failed, so no engine verdict exists.

    Broken pipe, a closed or terminated child, a rejected submission that never
    reached the engine and a failed arrival readback are all transport outcomes.
    None of them is evidence about the engine's starting-state capability, so
    none may be reported as an accepted engine state.
    """


class MidgameLaneTimeout(MidgameLaneTransportError):
    """The child accepted a request and did not answer inside the deadline.

    Distinct from a launch failure and from a protocol failure so a stalled
    candidate is classified as a timeout rather than folded into either,
    mirroring the established ``BridgeLauncher`` classification. It subclasses
    the transport error so every fail-closed handler still catches it; nothing
    converts it into a PASS or a default.
    """


class MidgameLaneArrivalRejected(MidgameLaneError):
    """The engine answered the arrival request with a refusal.

    This is not a transport failure and not an accepted starting state: the lane
    reached the engine and the engine declined to complete the arrival (for
    example restoration, revalidation or the readback failed). It therefore earns
    no acceptance statement and no reachability credit, and it must not be mapped
    to ``ENGINE_STATE_ACCEPTED``.
    """


class MidgameLaneProtocolError(MidgameLaneTransportError):
    """The child answered outside the Protocol-2 envelope.

    A non-JSON line, a non-object line or a line that does not carry the
    expected response shape is a protocol violation, never an engine verdict.
    """


def receipt_freshness(
    receipt: Mapping[str, Any] | None,
    *,
    expected_runner_digest: str,
    expected_engine_commit: str,
    expected_engine_artifact_sha256: str = "",
) -> str:
    """Classify a persisted mid-game receipt against the exact executing head.

    ``FRESH_EXACT`` requires the schema, the canonical content digest, the Lab
    runner digest, the engine commit and the provider-reported loaded engine
    artifact digest to all match the executing head. A receipt that carries no
    identity (or whose expected identity is unavailable) is ``MISSING``; a
    malformed or tampered one is ``INVALID``; a well-formed receipt from another
    runner, engine epoch or engine artifact is ``STALE``. Every
    non-``FRESH_EXACT`` classification is zero credit: the caller may report it
    as an auditable stale fact but must never promote a row from it.
    """
    if not isinstance(receipt, Mapping):
        return MIDGAME_RECEIPT_INVALID
    if receipt.get("schema_version") != MIDGAME_RECEIPT_SCHEMA:
        return MIDGAME_RECEIPT_INVALID
    recorded_digest = receipt.get("receipt_digest")
    if not isinstance(recorded_digest, str) or not recorded_digest:
        # A receipt persisted without its own content digest cannot be bound to
        # the bytes that produced it, so it is unbound rather than fresh.
        return MIDGAME_RECEIPT_MISSING
    from . import receipts as receipt_mod

    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    if receipt_mod.document_digest(body) != recorded_digest:
        return MIDGAME_RECEIPT_INVALID
    identity = {field: receipt.get(field) for field in MIDGAME_RECEIPT_IDENTITY_FIELDS}
    if not all(isinstance(value, str) and value for value in identity.values()):
        return MIDGAME_RECEIPT_MISSING
    artifact_kind = receipt.get("engine_artifact_kind")
    artifact_digest = receipt.get("engine_artifact_sha256")
    if not isinstance(artifact_kind, str) or not artifact_kind:
        return MIDGAME_RECEIPT_MISSING
    if not isinstance(artifact_digest, str) or not artifact_digest:
        return MIDGAME_RECEIPT_MISSING
    if artifact_kind != "file":
        # A reported directory or unavailable artifact is not an identity.
        return MIDGAME_RECEIPT_INVALID
    if _ENGINE_ARTIFACT_DIGEST.fullmatch(artifact_digest) is None:
        # A malformed digest is not an identity this receipt can claim.
        return MIDGAME_RECEIPT_INVALID
    if (
        not expected_runner_digest
        or not expected_engine_commit
        or not expected_engine_artifact_sha256
    ):
        # The executing identity is itself unavailable; nothing can be fresh.
        return MIDGAME_RECEIPT_MISSING
    if (
        identity["runner_digest"] != expected_runner_digest
        or identity["engine_commit"] != expected_engine_commit
        or artifact_digest != expected_engine_artifact_sha256
    ):
        return MIDGAME_RECEIPT_STALE
    return MIDGAME_RECEIPT_FRESH


@dataclass(frozen=True)
class DimensionManifest:
    """The engine's own per-dimension starting-state statement.

    ``global_supported`` stays the coarse bit the engine publishes for a
    globally complete injection of arbitrary states. It is deliberately not
    treated as the capability answer; ``per_dimension_supported`` plus the
    enumerated lists are.
    """

    schema_version: str
    global_supported: bool
    per_dimension_supported: bool
    supported: tuple[str, ...]
    unsupported: tuple[str, ...]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "global_supported": self.global_supported,
            "per_dimension_supported": self.per_dimension_supported,
            "supported_dimensions": list(self.supported),
            "unsupported_dimensions": list(self.unsupported),
        }


@dataclass(frozen=True)
class RowVerdict:
    """One row's engine-reported reachability, with the engine's own evidence.

    ``construction_match`` is the engine's own raw field-level verdict, kept
    verbatim. ``outcome`` applies the one documented allowance — priority is not
    held the way the readback reports it during a declaration step — and is
    derived only from the mismatches outside that allowance. Both are reported
    so a reviewer can see the raw engine bit and the classification side by side;
    neither is hidden inside the other.
    """

    fixture_id: str
    outcome: Outcome
    code: str | None
    detail: str | None
    construction_match: bool | None
    mismatches: tuple[str, ...]
    requested_state_digest: str | None
    constructed_state_digest: str | None
    lane: str
    engine_commit: str | None
    allowance_applied: tuple[str, ...] = ()
    engine_accepted_starting_state: bool = False
    entry_mode: str = "placement"
    causal_verdict: dict[str, Any] | None = None
    # The construction classification, stated explicitly instead of leaving a
    # reader to infer it from outcome + the raw engine bit: EXACT when the
    # engine's own compare matched; ALLOWED_VARIANCE when the only reported
    # mismatches are the documented declaration-step priority allowance (the raw
    # ``engine_construction_match`` stays false and visible); MISMATCH when a
    # real mismatch exists; UNRECOGNIZED when the verdict was uninterpretable.
    # None means the row carries no construction verdict (transport failure).
    construction_verdict: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "outcome": self.outcome,
            "engine_accepted_starting_state": self.engine_accepted_starting_state,
            "code": self.code,
            "detail": self.detail,
            "engine_construction_match": self.construction_match,
            "construction_verdict": self.construction_verdict,
            "mismatches": list(self.mismatches),
            "declaration_step_priority_allowance_applied": list(self.allowance_applied),
            "entry_mode": self.entry_mode,
            "causal_verdict": self.causal_verdict,
            "requested_state_digest": self.requested_state_digest,
            "constructed_state_digest": self.constructed_state_digest,
            "lane": self.lane,
            "engine_commit": self.engine_commit,
        }


class MidgameLaneClient:
    """One isolated mid-game session over the pinned engine's Protocol 2.0.0.

    The launch contract is the canonical current-boundary one: the caller builds
    the exact launch recipe through ``bridge_launcher.build_launch_plan`` (so the
    classpath manifest, the isolated runtime cwd outside every candidate worktree
    and the engine identity are the shared ones), and this client applies the
    same parent-environment clearing on spawn. It never inspects engine
    internals, never computes legality and never fabricates a response.
    """

    def __init__(
        self,
        argv: tuple[str, ...],
        cwd: Path,
        *,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        self._argv = argv
        self._cwd = cwd
        self._env_overrides = dict(env_overrides or {})
        self._process: subprocess.Popen[str] | None = None
        self._engine_commit: str | None = None
        self._engine_artifact: dict[str, Any] | None = None
        self._tape: list[dict[str, Any]] = []
        self.manifest: DimensionManifest | None = None
        self._last_timeout_s: float | None = None
        # The child's stderr, drained continuously by the shared bounded
        # non-blocking drain (#580): an undrained pipe would block a child that
        # writes more than the pipe buffer, and the knowledge boundary scans the
        # process log as a channel of its own.
        self._stderr_drain: StderrDrain | None = None

    # -- transport ---------------------------------------------------

    def __enter__(self) -> MidgameLaneClient:
        # Same spawn contract as bridge_launcher.launch: a parent
        # JAVA_TOOL_OPTIONS must not leak into the child engine JVM, and the
        # plan's own overrides are applied on top of the cleared environment.
        env = dict(os.environ)
        env.pop("JAVA_TOOL_OPTIONS", None)
        # The AF09 orchestration key never reaches a launch by inheritance;
        # only the replay twin's own launch adds it through its overrides.
        env.pop(ORCHESTRATION_KEY_VARIABLE, None)
        env.update(self._env_overrides)
        try:
            self._process = subprocess.Popen(
                list(self._argv),
                cwd=str(self._cwd),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise MidgameLaneError(f"cannot launch the mid-game lane: {exc}") from exc
        if self._process.stderr is not None:
            self._stderr_drain = StderrDrain(
                self._process.stderr,
                retain_limit_chars=self.STDERR_RETENTION_CHARS,
                thread_name="midgame-lane-stderr",
                # The knowledge boundary scans the log at the end of the run, so
                # this caller keeps the newest output rather than the oldest.
                retain_tail=True,
            )
            self._stderr_drain.start()
        return self

    #: Retained bytes of the child's stderr; the oldest text is dropped beyond it.
    STDERR_RETENTION_CHARS = 4_000_000

    def _join_stderr(self, timeout_s: float) -> None:
        drain = self._stderr_drain
        if drain is not None:
            drain.join(timeout_s)

    def stderr_capture(self) -> StderrCapture:
        """The child's stderr capture, with its completeness and truncation flags.

        A hidden-information channel scan may only consume a capture that is
        both complete (the drain saw end of stream) and untruncated (no text was
        dropped); anything else must leave the scan unverified, never PASS.
        """
        drain = self._stderr_drain
        if drain is None:
            return StderrCapture(text="", complete=False, truncated=False)
        return drain.capture()

    @property
    def stderr_log(self) -> str:
        """The child's stderr as drained so far (complete once the child exited)."""
        return self.stderr_capture().text

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._process is None:
            return
        process = self._process
        self._process = None
        with contextlib.suppress(MidgameLaneError):
            self.request("shutdown_engine", {})
        if process.stdin is not None:
            with contextlib.suppress(OSError):
                process.stdin.close()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
        # The direct child is gone (or killed): give the drain a short grace to
        # reach end of stream, then stop it. A descendant that inherited the pipe
        # can hold it open forever, so a drain still alive after the grace is
        # reclaimed instead of pinning its thread for the process life (#580).
        drain = self._stderr_drain
        self._join_stderr(STDERR_DRAIN_GRACE_S)
        if drain is not None and drain.draining:
            drain.stop()
            self._join_stderr(5.0)
        # Release the read ends as well: a retained drain or an unclosed pipe
        # would hold descriptors for the process life. Never close stderr under
        # a drain that could not be stopped — the blocked read would wait on it;
        # that capture stays incomplete and the daemon ends with the process.
        for stream in (process.stdout, process.stderr):
            if stream is None:
                continue
            if stream is process.stderr and drain is not None and drain.draining:
                continue
            with contextlib.suppress(OSError, ValueError):
                stream.close()

    def request(
        self,
        message_type: str,
        payload: dict[str, Any] | None,
        *,
        timeout_s: float = 300.0,
    ) -> dict[str, Any]:
        """Send exactly one Protocol-2 request and return the parsed response.

        The advertised ``timeout_s`` bounds the response wait. A child that
        accepts a request and then stalls or deadlocks is terminated and reaped
        and the call raises a transport timeout, so the qualification run can
        classify the row instead of hanging.

        A failed or malformed provider response is returned verbatim, including
        its error code. It is never converted into a success, a default or a
        pass. Transport and protocol failures raise rather than return.
        """
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise MidgameLaneTransportError("the mid-game lane process is not running")
        envelope: dict[str, Any] = {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": f"{message_type}-{uuid.uuid4()}",
            "message_type": message_type,
        }
        if payload is not None:
            envelope["payload"] = payload
            envelope["params"] = payload
        line = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        try:
            self._process.stdin.write(line + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise MidgameLaneTransportError(f"mid-game lane stdin unavailable: {exc}") from exc
        request_id = envelope["request_id"]
        raw = self._read_line_with_deadline(timeout_s, message_type, request_id)
        if not raw:
            # The drain thread owns the stream; give it a moment to reach EOF.
            self._join_stderr(2)
            stderr = self.stderr_log[-2000:]
            raise MidgameLaneTransportError(
                f"mid-game lane closed stdout for {message_type} (stderr tail: {stderr})"
            )
        parsed: dict[str, Any]
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MidgameLaneProtocolError(f"non-JSON mid-game response: {raw[:200]!r}") from exc
        if not isinstance(decoded, dict):
            raise MidgameLaneProtocolError(f"mid-game response is not a JSON object: {raw[:200]!r}")
        parsed = decoded
        entry = {"message_type": message_type, "request": envelope, "response": parsed}
        self._tape.append(entry)
        if message_type == "get_provider_version" and parsed.get("success"):
            payload_obj = parsed.get("payload") or {}
            if isinstance(payload_obj, dict):
                commit = payload_obj.get("engine_commit")
                self._engine_commit = commit if isinstance(commit, str) else None
                # The provider-reported artifact identity is captured verbatim;
                # it is never derived from the commit constant or a path guess.
                self._engine_artifact = {
                    "kind": payload_obj.get("engine_artifact_kind"),
                    "path": payload_obj.get("engine_artifact_path"),
                    "sha256": payload_obj.get("engine_artifact_sha256"),
                    "size": payload_obj.get("engine_artifact_size"),
                }
        return parsed

    def _read_line_with_deadline(self, timeout_s: float, message_type: str, request_id: str) -> str:
        """Read exactly one response line under a real wall-clock deadline.

        This is the mechanism already established for the current boundary in
        ``bridge_launcher.BridgeProcess._read_line_with_deadline``: the read runs
        on a daemon thread and is joined against the deadline, because the stream
        is a buffered ``TextIOWrapper`` whose fd-level readiness does not imply a
        complete line is available, so ``select`` is not usable here. On expiry
        the child is terminated and reaped so no zombie survives, the applied
        timeout is recorded on the tape, and a timeout error is raised. The
        mechanism is mirrored rather than imported: the established helper is a
        private method on a class in a module four concurrent PRs are editing,
        and no independent transport model is introduced by reusing its exact
        shape and its classification.
        """
        process = self._process
        if process is None or process.stdout is None:
            raise MidgameLaneTransportError("the mid-game lane process is not running")
        self._last_timeout_s = timeout_s
        result: list[str] = []
        finished = threading.Event()

        def _read() -> None:
            try:
                result.append(process.stdout.readline())  # type: ignore[union-attr]
            except (OSError, ValueError):
                result.append("")
            finally:
                finished.set()

        worker = threading.Thread(target=_read, name="midgame-lane-read", daemon=True)
        worker.start()
        if not finished.wait(timeout_s):
            self._tape.append(
                {
                    "message_type": message_type,
                    "direction": "timeout",
                    "request_id": request_id,
                    "timeout_s": timeout_s,
                    "classification": "TIMEOUT",
                }
            )
            self._terminate_stalled_child()
            raise MidgameLaneTimeout(
                f"MIDGAME_LANE_TIMEOUT: no response to {message_type} within {timeout_s}s; "
                "child terminated and reaped, classified TRANSPORT_FAILURE"
            )
        return result[0] if result else ""

    def _terminate_stalled_child(self) -> None:
        """Kill and reap a stalled child so no zombie is left behind."""
        process = self._process
        self._process = None
        if process is None:
            return
        with contextlib.suppress(OSError, ValueError):
            if process.stdin is not None:
                process.stdin.close()
        with contextlib.suppress(OSError, ValueError, subprocess.TimeoutExpired):
            process.kill()
        with contextlib.suppress(OSError, ValueError, subprocess.TimeoutExpired):
            process.wait(timeout=10)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                with contextlib.suppress(OSError):
                    stream.close()

    @property
    def tape(self) -> list[dict[str, Any]]:
        return self._tape

    @property
    def engine_commit(self) -> str | None:
        return self._engine_commit

    @property
    def engine_artifact(self) -> dict[str, Any] | None:
        return self._engine_artifact

    # -- capability --------------------------------------------------

    def read_dimension_manifest(self) -> DimensionManifest:
        """Read the engine's own per-dimension starting-state statement."""
        response = self.request("get_capabilities", None)
        if not response.get("success"):
            code = _error_code(response)
            raise MidgameLaneError(f"get_capabilities failed closed: {code}")
        capabilities = (response.get("payload") or {}).get("capabilities") or {}
        manifest = capabilities.get("starting_state_dimensions")
        if not isinstance(manifest, dict):
            raise MidgameLaneError(
                "the engine published no per-dimension starting-state manifest; this is the "
                "unconsumed-capability condition and it must fail closed rather than fall back "
                "to the coarse global flag"
            )
        self.manifest = DimensionManifest(
            schema_version=str(manifest.get("schema_version", "")),
            global_supported=bool(capabilities.get("starting_state_injection_supported")),
            per_dimension_supported=bool(capabilities.get("starting_state_dimensions_supported")),
            supported=tuple(manifest.get("supported_dimensions") or ()),
            unsupported=tuple(manifest.get("unsupported_dimensions") or ()),
            raw=manifest,
        )
        return self.manifest

    # -- decisions ---------------------------------------------------

    def pending_decision(
        self, *, attempts: int = 60, interval_s: float = 0.5
    ) -> dict[str, Any] | None:
        """Return the exact currently pending engine decision, or None."""
        import time

        for _ in range(attempts):
            response = self.request("get_midgame_decision", None)
            if not response.get("success"):
                code = _error_code(response)
                if (
                    code == "midgame_decision_failed"
                    and "TERMINAL" in str(_error_message(response)).upper()
                ):
                    return None
                raise MidgameLaneError(f"get_midgame_decision failed closed: {code}")
            payload = response.get("payload")
            if isinstance(payload, dict):
                decision = payload.get("decision")
                if isinstance(decision, dict) and decision:
                    return decision
            time.sleep(interval_s)
        return None

    def submit_options(self, decision: dict[str, Any], option_ids: list[str]) -> dict[str, Any]:
        """Submit exact engine-offered option ids for the pending decision.

        The caller selects from the engine's own ``legal_options``. This method
        never substitutes an option, and an empty selection is rejected by the
        engine rather than defaulted here.

        Numeric fields are sent only when the pending frame's own context
        authorizes them. The engine treats a numeric vector on a frame without
        joint numeric legs as schema confusion and fails it closed, so a client
        that always sends them is rejected for a transport reason rather than
        for its answer.
        """
        response: dict[str, Any] = {
            "decision_id": decision["decision_id"],
            "actor_id": decision["actor_id"],
            "selected_option_ids": list(option_ids),
            "ordering": [],
        }
        context = decision.get("context")
        if isinstance(context, dict):
            if context.get("numeric_min") is not None and context.get("numeric_max") is not None:
                response["numeric_choice"] = None
            if isinstance(context.get("numeric_legs"), list):
                response["numeric_choices"] = None
        result = self.request("submit_midgame_decision", {"response": response})
        if not result.get("success"):
            raise MidgameLaneError(
                f"the engine rejected the submitted decision: {_error_code(result)} "
                f"{_error_message(result)}"
            )
        return result.get("payload") or {}

    def complete_arrival(self) -> dict[str, Any]:
        """Ask the engine for its post-arrival completion and construction verdict.

        While the engine is parked on a decision this is a pure query: it runs
        the engine's own commander cast-count restore, revalidation, native
        readback and field-level compare, and answers no decision.
        """
        response = self.request("complete_midgame_arrival", {})
        if not response.get("success"):
            # The engine answered and refused, so this is an engine rejection of
            # the arrival. It must never be reported as an accepted state.
            raise MidgameLaneArrivalRejected(
                f"complete_midgame_arrival failed closed: {_error_code(response)}: "
                f"{_error_message(response)}"
            )
        return response.get("payload") or {}

    def zone_counts(self, actor_id: str) -> dict[str, Any]:
        """Principal-scoped public-zone counts for exactly one principal."""
        response = self.request("get_midgame_state", {"actor_id": actor_id})
        if not response.get("success"):
            raise MidgameLaneError(f"get_midgame_state failed closed: {_error_code(response)}")
        return response.get("payload") or {}

    def events(self, after_offset: int = 0) -> dict[str, Any]:
        """The engine's public semantic event tape after ``after_offset`` events."""
        response = self.request("get_midgame_events", {"after_offset": after_offset})
        if not response.get("success"):
            raise MidgameLaneError(
                f"get_midgame_events failed closed: {_error_code(response)}: {_error_message(response)}"
            )
        return response.get("payload") or {}


def _error_code(response: dict[str, Any]) -> str | None:
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            value = first.get("code")
            return value if isinstance(value, str) else None
    return None


def _error_message(response: dict[str, Any]) -> str:
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            value = first.get("message")
            return value if isinstance(value, str) else ""
    return ""


def _strict_boolean(value: Any) -> bool | None:
    """Return the value only when it is a real JSON boolean.

    ``bool()`` would accept the string ``"false"`` as true, which is exactly how
    a malformed or version-skewed response would otherwise be promoted. Anything
    that is not a JSON boolean is unknown, and unknown fails closed.
    """
    return value if isinstance(value, bool) else None


def _strict_mismatch_list(value: Any) -> tuple[str, ...] | None:
    """Return the mismatch list only when the response carries a real list.

    A missing field, an explicit null, a bare string or a mapping is not a
    mismatch list. Those are unrecognized responses, not empty ones, so they must
    not be read as "no mismatch was reported".
    """
    if value is None or not isinstance(value, (list, tuple)):
        return None
    return tuple(str(item) for item in value)


def classification_from_arrival(
    fixture_id: str,
    lane: str,
    arrival: dict[str, Any],
    *,
    engine_commit: str | None,
) -> RowVerdict:
    """Classify the engine's own construction verdict for one row.

    The decision is entirely the engine's, and a negative verdict is binding.

    ``ENGINE_NATIVE_REACHABLE`` requires all three of:

    * the engine's own ``construction_match`` is the JSON boolean ``true``; or it
      is ``false`` and every reported mismatch is a recognized, explicitly
      modeled disposition (the documented declaration-step priority allowance),
      which is the only case where the contract permits the bounded
      classification to survive a negative raw bit;
    * the mismatch list is present and well formed;
    * nothing outside the documented allowance was reported.

    A ``false`` verdict with a missing, empty, malformed or unrecognized mismatch
    list is an uninterpretable response, not a construction success: it fails
    closed as ``UNRECOGNIZED_CONSTRUCTION_VERDICT`` with no reachability credit.
    A ``true`` verdict that still lists mismatches is self-contradictory and
    fails closed the same way.
    """
    construction_match = _strict_boolean(arrival.get("construction_match"))
    mismatches = _strict_mismatch_list(arrival.get("mismatches"))
    if construction_match is None or mismatches is None:
        return RowVerdict(
            fixture_id=fixture_id,
            outcome="UNRECOGNIZED_CONSTRUCTION_VERDICT",
            code="UNRECOGNIZED_CONSTRUCTION_VERDICT",
            detail=(
                "the engine's construction verdict is not interpretable: "
                f"construction_match={arrival.get('construction_match')!r} "
                f"mismatches={arrival.get('mismatches')!r}"
            ),
            construction_match=construction_match,
            mismatches=mismatches or (),
            requested_state_digest=arrival.get("requested_state_digest"),
            constructed_state_digest=arrival.get("constructed_state_digest"),
            lane=lane,
            engine_commit=engine_commit,
            engine_accepted_starting_state=False,
            construction_verdict="UNRECOGNIZED",
        )
    allowance = tuple(
        mismatch
        for mismatch in mismatches
        if mismatch.startswith(DECLARATION_STEP_PRIORITY_ALLOWANCE)
    )
    unexpected = tuple(mismatch for mismatch in mismatches if mismatch not in allowance)
    outcome: Outcome
    if unexpected:
        outcome = "CONSTRUCTION_MISMATCH"
    elif construction_match and mismatches:
        # The engine said it matched and still listed mismatches: the response is
        # internally contradictory, so it cannot earn reachability.
        return RowVerdict(
            fixture_id=fixture_id,
            outcome="UNRECOGNIZED_CONSTRUCTION_VERDICT",
            code="UNRECOGNIZED_CONSTRUCTION_VERDICT",
            detail=(
                "the engine reported construction_match true together with mismatches: "
                + "; ".join(mismatches)
            ),
            construction_match=construction_match,
            mismatches=mismatches,
            requested_state_digest=arrival.get("requested_state_digest"),
            constructed_state_digest=arrival.get("constructed_state_digest"),
            lane=lane,
            engine_commit=engine_commit,
            engine_accepted_starting_state=False,
            construction_verdict="UNRECOGNIZED",
        )
    elif construction_match:
        outcome = "ENGINE_NATIVE_REACHABLE"
    elif mismatches and allowance:
        # A negative raw bit survives only as the explicitly modeled
        # declaration-step allowance, which the contract permits. The raw bit,
        # the allowance, and the resulting classification are all reported.
        outcome = "ENGINE_NATIVE_REACHABLE"
    else:
        # construction_match is false and the mismatch list is empty: the engine
        # said it does not match and gave no reason this consumer recognizes.
        return RowVerdict(
            fixture_id=fixture_id,
            outcome="UNRECOGNIZED_CONSTRUCTION_VERDICT",
            code="UNRECOGNIZED_CONSTRUCTION_VERDICT",
            detail=(
                "the engine reported construction_match false with no recognized mismatch "
                "disposition, so the row cannot be credited"
            ),
            construction_match=construction_match,
            mismatches=mismatches,
            requested_state_digest=arrival.get("requested_state_digest"),
            constructed_state_digest=arrival.get("constructed_state_digest"),
            lane=lane,
            engine_commit=engine_commit,
            engine_accepted_starting_state=False,
            construction_verdict="UNRECOGNIZED",
        )
    return RowVerdict(
        fixture_id=fixture_id,
        outcome=outcome,
        code=None,
        detail=None if outcome == "ENGINE_NATIVE_REACHABLE" else "; ".join(unexpected),
        construction_match=construction_match,
        mismatches=mismatches,
        requested_state_digest=arrival.get("requested_state_digest"),
        constructed_state_digest=arrival.get("constructed_state_digest"),
        lane=lane,
        engine_commit=engine_commit,
        allowance_applied=allowance,
        # An acceptance statement is made only for a row that actually reached
        # the engine's native reachability. A construction mismatch does not.
        engine_accepted_starting_state=outcome == "ENGINE_NATIVE_REACHABLE",
        construction_verdict=(
            "EXACT"
            if outcome == "ENGINE_NATIVE_REACHABLE" and construction_match
            else "ALLOWED_VARIANCE"
            if outcome == "ENGINE_NATIVE_REACHABLE"
            else "MISMATCH"
        ),
    )


def classification_from_causal_verdict(
    fixture_id: str,
    lane: str,
    entry_mode: str,
    verdict: dict[str, Any],
    terminal_obligation: dict[str, Any] | None,
    *,
    engine_commit: str | None,
) -> RowVerdict:
    """Classify the engine's own causal-route verdict for one row.

    The decision is entirely the engine's, in two separately reported parts.
    ``CAUSAL_ROUTE_REACHABLE`` requires the engine to report ``causal_match``
    with no mismatches **and** the row's terminal obligation to be observed.
    A route the engine executed but whose terminal obligation it did not
    produce — the commander-zone choice that never appears for a setup copy,
    for example — is ``CAUSAL_ROUTE_MEASURED_BLOCKED``: the causal execution
    is proven, the missing terminal is measured, and nothing is promoted. A
    route the engine did not produce is ``CONSTRUCTION_MISMATCH``. The
    engine's own verdict and the terminal record travel verbatim in the row.
    """
    causal_match = _strict_boolean(verdict.get("causal_match"))
    mismatches = _strict_mismatch_list(verdict.get("mismatches"))
    if causal_match is None or mismatches is None:
        return RowVerdict(
            fixture_id=fixture_id,
            outcome="UNRECOGNIZED_CONSTRUCTION_VERDICT",
            code="UNRECOGNIZED_CONSTRUCTION_VERDICT",
            detail=(
                "the engine's causal verdict is not interpretable: "
                f"causal_match={verdict.get('causal_match')!r} "
                f"mismatches={verdict.get('mismatches')!r}"
            ),
            construction_match=None,
            mismatches=mismatches or (),
            requested_state_digest=None,
            constructed_state_digest=None,
            lane=lane,
            engine_commit=engine_commit,
            engine_accepted_starting_state=False,
            entry_mode=entry_mode,
            causal_verdict=dict(verdict),
        )
    outcome: Outcome
    detail: str | None
    if not causal_match or mismatches:
        outcome = "CONSTRUCTION_MISMATCH"
        detail = "; ".join(mismatches) or "the engine did not produce the causal route"
    elif terminal_obligation is None:
        # An unrecorded terminal is not an observed one. The causal route may
        # have executed, but reachability requires the row's terminal
        # obligation to be produced and recorded, so a caller that supplies no
        # terminal gets MEASURED_BLOCKED rather than credit.
        outcome = "CAUSAL_ROUTE_MEASURED_BLOCKED"
        detail = "the engine produced the causal route but no terminal obligation was recorded"
    elif terminal_obligation.get("observed"):
        outcome = "CAUSAL_ROUTE_REACHABLE"
        detail = None
    else:
        outcome = "CAUSAL_ROUTE_MEASURED_BLOCKED"
        detail = str(terminal_obligation.get("detail") or "terminal obligation not observed")
    combined_verdict = dict(verdict)
    if terminal_obligation is not None:
        combined_verdict["terminal_obligation"] = terminal_obligation
    return RowVerdict(
        fixture_id=fixture_id,
        outcome=outcome,
        code=None,
        detail=detail,
        construction_match=None,
        mismatches=mismatches,
        requested_state_digest=None,
        constructed_state_digest=None,
        lane=lane,
        engine_commit=engine_commit,
        # Only a produced causal route proves the engine consumed the starting
        # state through this entry mode. A route the engine did not produce
        # earns no acceptance statement.
        engine_accepted_starting_state=outcome
        in ("CAUSAL_ROUTE_REACHABLE", "CAUSAL_ROUTE_MEASURED_BLOCKED"),
        entry_mode=entry_mode,
        causal_verdict=combined_verdict,
    )


def transport_failure_verdict(
    fixture_id: str,
    lane: str,
    *,
    code: str,
    detail: str | None,
    engine_commit: str | None,
    entry_mode: str = "placement",
) -> RowVerdict:
    """Record a transport or protocol failure that produced no engine verdict.

    This is deliberately separate from :func:`rejected_verdict`. A transport
    failure says nothing about whether the engine can construct the row's
    starting state, so the row carries ``TRANSPORT_FAILURE`` with
    ``engine_accepted_starting_state`` false and zero reachability credit. The
    diagnostic detail is preserved for the operator; it carries only transport
    text, never engine state.
    """
    return RowVerdict(
        fixture_id=fixture_id,
        outcome="TRANSPORT_FAILURE",
        code=code,
        detail=detail,
        construction_match=None,
        mismatches=(),
        requested_state_digest=None,
        constructed_state_digest=None,
        lane=lane,
        engine_commit=engine_commit,
        engine_accepted_starting_state=False,
        entry_mode=entry_mode,
    )


def causal_credit_gate(
    fixture_id: str,
    entry_mode: str,
    arrival_verdict: RowVerdict | None,
    *,
    engine_commit: str | None,
) -> dict[str, Any] | None:
    """Return a row that withholds causal credit, or None when credit may proceed.

    A causal route may only be credited when the engine's own construction verdict
    for the pre-causal arrival established bounded native reachability. Anything
    else — a construction mismatch, an uninterpretable verdict, a rejection, or no
    verdict at all — is returned as the row verdict instead, so a stack or
    elimination outcome the engine produced cannot be reported as a reachable row
    whose requested starting state was never constructed.
    """
    if arrival_verdict is not None and arrival_verdict.outcome == "ENGINE_NATIVE_REACHABLE":
        return None
    if arrival_verdict is None:
        withheld = rejected_verdict(
            fixture_id,
            MIDGAME_LANE,
            code="ARRIVAL_VERDICT_MISSING",
            detail="the engine returned no construction verdict at the requested checkpoint",
            engine_commit=engine_commit,
        )
    else:
        withheld = arrival_verdict
    return withheld.as_dict() | {"entry_mode": entry_mode}


def failure_verdict(
    fixture_id: str,
    lane: str,
    exc: BaseException,
    *,
    engine_commit: str | None,
    entry_mode: str = "placement",
    obligation_code: str = "OBLIGATION_NOT_EXECUTED",
    transport_code: str = "MIDGAME_LANE_TRANSPORT_FAILURE",
    protocol_code: str = "MIDGAME_LANE_PROTOCOL_VIOLATION",
    timeout_code: str = "MIDGAME_LANE_TIMEOUT",
) -> tuple[RowVerdict, Outcome]:
    """Map a lane failure to the row verdict it must produce.

    This is the single place that decides what a failure means, so a transport
    outcome can never be reclassified as an accepted engine state by a caller.
    Only an explicit :class:`MidgameLaneError` obligation case — the engine was
    engaged and the lane could not carry out the row's own scripted obligation
    from engine-offered options — becomes ``ENGINE_STATE_ACCEPTED``, and even
    that carries no reachability credit. Timeout, protocol and transport
    failures become ``TRANSPORT_FAILURE`` with the engine untouched and no
    acceptance statement. Anything that is not a lane error is returned to the
    caller rather than converted.
    """
    if isinstance(exc, MidgameLaneTimeout):
        return (
            transport_failure_verdict(
                fixture_id,
                lane,
                code=timeout_code,
                detail=str(exc),
                engine_commit=engine_commit,
                entry_mode=entry_mode,
            ),
            "TRANSPORT_FAILURE",
        )
    if isinstance(exc, MidgameLaneProtocolError):
        return (
            transport_failure_verdict(
                fixture_id,
                lane,
                code=protocol_code,
                detail=str(exc),
                engine_commit=engine_commit,
                entry_mode=entry_mode,
            ),
            "TRANSPORT_FAILURE",
        )
    if isinstance(exc, MidgameLaneTransportError):
        return (
            transport_failure_verdict(
                fixture_id,
                lane,
                code=transport_code,
                detail=str(exc),
                engine_commit=engine_commit,
                entry_mode=entry_mode,
            ),
            "TRANSPORT_FAILURE",
        )
    if isinstance(exc, MidgameLaneArrivalRejected):
        # The engine refused the arrival: an engine rejection with no acceptance
        # statement, never the bounded accepted-obligation disposition.
        return (
            rejected_verdict(
                fixture_id,
                lane,
                code="ARRIVAL_REJECTED",
                detail=str(exc),
                engine_commit=engine_commit,
                state_accepted=False,
            ),
            "ENGINE_REJECTED",
        )
    if isinstance(exc, MidgameLaneError):
        return (
            rejected_verdict(
                fixture_id,
                lane,
                code=obligation_code,
                detail=str(exc),
                engine_commit=engine_commit,
                state_accepted=True,
            ),
            "ENGINE_STATE_ACCEPTED",
        )
    raise TypeError(
        f"refusing to classify a non-lane failure as an engine verdict: {type(exc).__name__}: {exc}"
    )


def classification_from_placement_obligation(
    fixture_id: str,
    lane: str,
    terminal_obligation: dict[str, Any] | None,
    *,
    engine_commit: str | None,
) -> RowVerdict:
    """Classify a placement row by its measured terminal obligation.

    A placement row's requested starting state is constructed by the placement
    seam and the row's temporal point is reached by the obligation executor, so
    there is no engine ``causal_match`` for this entry: the engine never reports
    one. This classifier therefore claims only what the engine produced — the
    measured terminal obligation — and records that explicitly instead of
    asserting a causal match the engine did not report.

    The outcome label is the one the lane already publishes for a measured
    obligation so the row set and its partition stay stable; the honest evidence
    lives in ``causal_verdict``, which no longer contains a fabricated
    ``causal_match``.
    """
    observed = bool(terminal_obligation is not None and terminal_obligation.get("observed"))
    outcome: Outcome = "CAUSAL_ROUTE_REACHABLE" if observed else "CAUSAL_ROUTE_MEASURED_BLOCKED"
    detail = (
        None
        if observed
        else str((terminal_obligation or {}).get("detail") or "terminal obligation not observed")
    )
    evidence: dict[str, Any] = {
        "entry_mode": "placement",
        "entry_kind": "placement_obligation_no_stack_route",
        "engine_reports_causal_match": False,
        "note": (
            "a placement entry has no stack route to reconstruct; the engine "
            "produced the terminal obligation and reported no causal_match"
        ),
        "terminal_obligation": terminal_obligation,
    }
    return RowVerdict(
        fixture_id=fixture_id,
        outcome=outcome,
        code=None,
        detail=detail,
        construction_match=None,
        mismatches=(),
        requested_state_digest=None,
        constructed_state_digest=None,
        lane=lane,
        engine_commit=engine_commit,
        engine_accepted_starting_state=observed,
        entry_mode="placement",
        causal_verdict=evidence,
    )


def rejected_verdict(
    fixture_id: str,
    lane: str,
    *,
    code: str | None,
    detail: str | None,
    engine_commit: str | None,
    state_accepted: bool = False,
    entry_mode: str = "placement",
) -> RowVerdict:
    """Record a row the lane did not reach a verdict on, with the engine's own code.

    ``state_accepted`` separates the two genuinely different failures. When it
    is false the engine rejected the explicit starting state and the row is not
    materializable. When it is true the engine accepted the state and the lane
    simply did not execute the row's scripted obligation, which is recorded as
    ``ENGINE_STATE_ACCEPTED`` by the caller. Neither is a pass.

    ``entry_mode`` records the route the row actually requested. A causal row
    rejected before arrival must not be labelled as a placement row: the
    persisted evidence would then claim a route the probe never attempted.
    """
    return RowVerdict(
        fixture_id=fixture_id,
        outcome="ENGINE_REJECTED",
        code=code,
        detail=detail,
        construction_match=None,
        mismatches=(),
        requested_state_digest=None,
        constructed_state_digest=None,
        lane=lane,
        engine_commit=engine_commit,
        engine_accepted_starting_state=state_accepted,
        entry_mode=entry_mode,
    )


def iter_frozen_records(materialization_path: Path) -> Iterator[dict[str, Any]]:
    """Yield the frozen materialization records in file order."""
    document = json.loads(materialization_path.read_text(encoding="utf-8"))
    for record in document.get("records") or ():
        if isinstance(record, dict) and record.get("fixture_id"):
            yield record


def frozen_record(materialization_path: Path, fixture_id: str) -> dict[str, Any]:
    """Return one frozen record, or fail closed when it is absent."""
    for record in iter_frozen_records(materialization_path):
        if record["fixture_id"] == fixture_id:
            return record
    raise KeyError(f"frozen materialization record missing: {fixture_id}")
