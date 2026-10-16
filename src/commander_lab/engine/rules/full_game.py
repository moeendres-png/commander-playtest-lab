from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
import weakref
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, TextIO, cast

from pydantic import Field, model_validator

from commander_lab.agents import build_pilot
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.base import resolve_engine_working_directory
from commander_lab.engine.rules.failure_privacy import (
    redacted_summary,
)
from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    EngineProtocolResponse,
    RulesDeckInput,
)
from commander_lab.semantic_replay.canonicalization import canonical_hash
from commander_lab.semantic_replay.tape_helpers import selected_fingerprints_for_response

from .full_game_pilot import ExternalPilotDecisionPolicy
from .full_game_pilot.common import (
    _XMAGE_SHORT_ID_AFTER_CLOSE_RE,
    _XMAGE_SHORT_ID_APPENDED_RE,
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    FULL_GAME_SHUTDOWN_ALREADY_EXITED,
    FULL_GAME_SHUTDOWN_FORCED_KILL,
    FULL_GAME_SHUTDOWN_GRACEFUL,
    FULL_GAME_SHUTDOWN_UNACKED_EXIT,
    XMAGE_FULL_GAME_COMMAND_ENV,
    FullGameConformanceError,
    FullGamePilotBinding,
    FullGameProtocolError,
    _RuntimePilot,
    _StrictModel,
    mana_payment_fit,
    public_full_game_errors,
)
from .wire_types import (
    BridgeRequestEnvelope,
    CapabilitiesWire,
    FullGameDeckPayload,
    FullGameLaneWire,
    FullGameResultWire,
    ProviderIdentityWire,
    SemanticEventWire,
    SemanticOutcomeWire,
    SemanticTranscript,
    StartEngineWire,
)

ClaimEvidenceStatus = Literal[
    "OBSERVED",
    "CODE_DERIVED",
    "DECLARED_NOT_OBSERVED",
    "NOT_CLAIMED",
]


class FullGameClaimBasis(_StrictModel):
    """What each boolean claim of a full-game result actually rests on (C3).

    The boolean fields of :class:`FullGameConformanceResult` are fixed by the
    lane's design, not measured per game. This record keeps the declaration
    and the observation apart so no consumer reads a design constant as
    runtime evidence:

    * ``OBSERVED``: measured in this run (decision count, terminal state,
      graceful shutdown);
    * ``CODE_DERIVED``: enforced by fail-closed code on every path of this
      run (rules/decision authority, no discretionary fallback), not
      separately measured;
    * ``DECLARED_NOT_OBSERVED``: the lane's contract, with no runtime probe in
      this run (per-actor hidden-information channels);
    * ``NOT_CLAIMED``: explicitly not claimed (bit-exact replay).
    """

    decision_count: Literal["OBSERVED"] = "OBSERVED"
    terminal: Literal["OBSERVED"] = "OBSERVED"
    shutdown_disposition: Literal["OBSERVED"] = "OBSERVED"
    xmage_rules_authority: Literal["CODE_DERIVED"] = "CODE_DERIVED"
    commander_lab_pilot_decision_authority: Literal["CODE_DERIVED"] = "CODE_DERIVED"
    fallback_used: Literal["CODE_DERIVED"] = "CODE_DERIVED"
    # OBSERVED only when the run audited at least one decision frame (C2).
    hidden_information_actor_scoped: Literal["OBSERVED", "DECLARED_NOT_OBSERVED"] = (
        "DECLARED_NOT_OBSERVED"
    )
    bit_exact_replay_validated: Literal["NOT_CLAIMED"] = "NOT_CLAIMED"


class FullGameHiddenInformationAudit(_StrictModel):
    """Per-frame runtime audit of the actor-scoped observation (C2).

    Every decision frame the engine publishes carries the actor's principal-
    scoped state. The audit checks that exactly one row is the actor's, that
    it is the frame's actor, and that no other player's private rows (hand,
    mana pool) appear unless the engine itself marked that row visible to this
    principal (control, CR 723.4). A frame that breaks this ends the run fail
    closed; the counts below describe a run that passed every frame.
    """

    frames_audited: int = Field(default=0, ge=0)
    non_actor_rows_audited: int = Field(default=0, ge=0)
    non_actor_rows_engine_visible: int = Field(default=0, ge=0)


_PRIVATE_ROW_KEYS = ("hand", "mana_pool")


def audit_actor_scoped_frame(decision: dict[str, Any]) -> tuple[int, int, list[str]]:
    """Audit one decision frame; returns (non_actor_rows, engine_visible_rows, violations).

    Violations name seats and keys only, never card identities.
    """
    state = decision.get("pilot_state")
    if not isinstance(state, dict) or not isinstance(state.get("players"), list):
        return 0, 0, ["frame carries no principal-scoped player state"]
    players = [p for p in state["players"] if isinstance(p, dict)]
    actor_rows = [p for p in players if p.get("is_actor") is True]
    violations: list[str] = []
    if len(actor_rows) != 1:
        violations.append(f"frame marks {len(actor_rows)} actor rows, expected 1")
    elif actor_rows[0].get("player_id") != decision.get("actor_id"):
        violations.append("the actor row is not the frame's actor")
    rows = 0
    visible = 0
    for player in players:
        if player.get("is_actor") is True:
            continue
        rows += 1
        if player.get("private_state_visible") is True:
            visible += 1
            continue
        for key in _PRIVATE_ROW_KEYS:
            if key in player:
                seat = player.get("seat")
                public_seat = seat if type(seat) is int and 0 <= seat <= 5 else "invalid"
                violations.append(f"seat {public_seat} exposes {key} to another principal")
    return rows, visible, violations


class FullGameConformanceResult(_StrictModel):
    schema_version: Literal["xmage-full-game-conformance-result-1.2.0"] = (
        "xmage-full-game-conformance-result-1.2.0"
    )
    scenario: FutureXmageScenario
    engine_version: str
    xmage_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    decision_protocol_version: str
    decision_count: int = Field(ge=0)
    terminal: bool
    winner_seats: tuple[int, ...]
    result_payload: dict[str, Any]
    semantic_transcript_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Observed, never defaulted: a game-over result exists only when the bridge
    # process was shut down gracefully (acked request, exit without kill).
    shutdown_disposition: Literal["graceful_shutdown"]
    evidence_class: Literal["technical_conformance_only"] = FULL_GAME_EVIDENCE_CLASS
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False
    official_campaign_eligible: Literal[False] = False
    structural_decision_authority: Literal[False] = False
    tactical_decision_authority: Literal[False] = False
    xmage_rules_authority: Literal[True] = True
    commander_lab_pilot_decision_authority: Literal[True] = True
    hidden_information_actor_scoped: Literal[True] = True
    fallback_used: Literal[False] = False
    bit_exact_replay_validated: Literal[False] = False
    claim_basis: FullGameClaimBasis = Field(default_factory=FullGameClaimBasis)
    hidden_information_audit: FullGameHiddenInformationAudit = Field(
        default_factory=FullGameHiddenInformationAudit
    )


# B8 (#489): (decision_class, seat, turn_number, phase, response_digest,
# active_seat). active_seat is the turn's active player, resolved inside the
# decider's own view (active_player_id -> players[].seat).
ProgressEntry = tuple[str, int | None, int | None, str | None, str, int | None]


def _active_seat(pilot_state: Any) -> int | None:
    """The active player's seat in one actor-scoped view, or None if unresolvable."""
    if not isinstance(pilot_state, dict):
        return None
    active = pilot_state.get("active_player_id")
    seats = [
        player.get("seat")
        for player in pilot_state.get("players") or ()
        if isinstance(player, dict) and active is not None and player.get("player_id") == active
    ]
    return seats[0] if len(seats) == 1 and type(seats[0]) is int else None


class FullGameSmokeResult(_StrictModel):
    """Bounded cardinality smoke outcome (WS223).

    Proves live production startup and authoritative decision progression up
    to a calibrated decision target (or earlier terminal) with clean bounded
    shutdown. This is a lifecycle smoke, not a game-over conformance claim:
    terminal/outcome-shape evidence stays with :class:`FullGameConformanceResult`
    (live 4P gate) and the per-count unit outcome guards.
    """

    schema_version: Literal["xmage-full-game-smoke-result-1.1.0"] = (
        "xmage-full-game-smoke-result-1.1.0"
    )
    scenario_id: str
    player_count: int = Field(ge=2, le=6)
    seed: int = Field(ge=0)
    engine_version: str
    xmage_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    decision_protocol_version: str
    decision_count: int = Field(ge=1)
    smoke_decision_target: int = Field(ge=1)
    bounded_criterion_met: Literal[True]
    terminal_reached: bool
    seed_preserved: Literal[True]
    player_count_preserved: Literal[True]
    observed_decision_classes: tuple[str, ...]
    # B8 (#489): the public progress trace of the answered decisions, one
    # (decision_class, seat, turn_number, phase, response_digest) entry each.
    # Version 1.1 binds semantic selections using the existing replay fingerprints.
    # Recorded on every smoke; only --progress-turns evaluates it.
    progress_trace: tuple[ProgressEntry, ...] = ()
    stop_reason: Literal["turn_boundary", "decision_limit", "terminal"] = "decision_limit"
    stop_turn_number: int | None = None
    progress_digest: str | None = None
    unsupported_callback_seen: Literal[False] = False
    clean_shutdown: Literal[True] = True
    evidence_class: Literal["technical_conformance_only"] = FULL_GAME_EVIDENCE_CLASS
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False
    official_campaign_eligible: Literal[False] = False
    fallback_used: Literal[False] = False


def smoke_progress_contract(
    trace: tuple[ProgressEntry, ...],
    *,
    player_count: int,
    through_turn: int,
) -> dict[str, Any]:
    """Technical progress through a full seat cycle, with attributable responses.

    The caller separately requires the observed next-turn boundary. This trace
    requires priority in every completed turn and from every seated player; it
    never claims card behaviour or terminal full-game qualification.
    """
    turns = sorted({row[2] for row in trace if type(row[2]) is int})
    priority = [(row[1], row[2]) for row in trace if row[0] == "priority"]
    priority_turns = sorted({turn for _seat, turn in priority if type(turn) is int})
    priority_seats = sorted({seat for seat, _turn in priority if type(seat) is int})
    violations = []
    if type(player_count) is not int or not 2 <= player_count <= 6:
        violations.append("invalid player count")
    if type(through_turn) is not int or through_turn < player_count:
        violations.append("progress target must cover a full seat cycle")
    if not turns or turns[-1] < through_turn:
        violations.append(f"game did not reach turn {through_turn} (turns {turns})")
    if any(turn not in priority_turns for turn in range(1, through_turn + 1)):
        violations.append(f"priority missing from a required turn ({priority_turns})")
    if priority_seats != list(range(player_count)):
        violations.append(f"not every seat answered priority (seats {priority_seats})")
    if any(row[1] is None for row in trace):
        violations.append("a decision carried no seat")
    if any(type(row[1]) is not int or not 0 <= row[1] < player_count for row in trace):
        violations.append("a decision carried an invalid seat")
    if any(row[0] == "priority" and (type(row[2]) is not int or row[2] < 1) for row in trace):
        violations.append("a priority decision carried an invalid turn")
    if any(
        not isinstance(row[4], str) or re.fullmatch(r"[0-9a-f]{64}", row[4]) is None
        for row in trace
    ):
        violations.append("a decision carried no valid response digest")
    # Each completed turn has exactly one active player, and the completed turns
    # of a full cycle are taken by every seat: priority in every turn and from
    # every seat alone would accept one player taking turns 2..N. Priority only
    # exists inside a turn, so every priority decision must resolve the active
    # seat; pre-game choices (mulligans, commander placement) have no active
    # player yet, but any active seat they do carry must agree.
    active_by_turn: dict[int, list[int]] = {}
    unresolved_turns: set[int] = set()
    for row in trace:
        if type(row[2]) is int and 1 <= row[2] <= through_turn:
            active = row[5] if len(row) > 5 else None
            if active is None and row[0] != "priority":
                continue
            if type(active) is not int or not 0 <= active < player_count:
                unresolved_turns.add(row[2])
            elif active not in active_by_turn.setdefault(row[2], []):
                active_by_turn[row[2]].append(active)
    if unresolved_turns:
        violations.append(
            f"decisions with no valid active seat in turns {sorted(unresolved_turns)}"
        )
    active_seats_by_turn = {str(turn): seats for turn, seats in sorted(active_by_turn.items())}
    if any(len(seats) != 1 for seats in active_by_turn.values()):
        violations.append(f"a turn had more than one active seat ({active_seats_by_turn})")
    completed = {seats[0] for seats in active_by_turn.values() if len(seats) == 1}
    if type(player_count) is int and completed != set(range(player_count)):
        violations.append(
            f"the completed turns were not taken by every seat ({active_seats_by_turn})"
        )
    return {
        "schema_version": "xmage-smoke-progress-contract-1.2.0",
        "active_seats_by_turn": active_seats_by_turn,
        "through_turn": through_turn,
        "turns_observed": turns,
        "priority_turns": priority_turns,
        "priority_seats": priority_seats,
        "decisions": len(trace),
        "violations": violations,
        "met": not violations,
    }


class FullGameSemanticTapeEvidence(_StrictModel):
    """C1: replay evidence from the semantic replay tape system (WS218).

    Two tapes are recorded in fresh processes and compared step by step
    (`compare_tapes`), and the first tape is consumed by a third fresh process
    (`replay_tape`), which re-derives every legal set, selection, event digest and
    the terminal outcome from the live engine.
    """

    basis: Literal["semantic_replay_tape"] = "semantic_replay_tape"
    tape_schema_version: str
    first_tape_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    second_tape_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    recorded_steps: int = Field(ge=1)
    tape_comparison_match: bool
    compared_steps: int = Field(ge=0)
    first_divergence_kind: str | None = None
    fresh_process_replay_pass: bool
    replay_steps_verified: int = Field(ge=0)
    replay_divergence_class: str | None = None
    # The consumer's own message for the divergence. One class can come from
    # several emit sites (EARLY_TERMINATION has five), so the class alone cannot
    # say which check failed.
    replay_divergence_detail: str | None = None

    @property
    def passed(self) -> bool:
        return self.tape_comparison_match and self.fresh_process_replay_pass

    @model_validator(mode="after")
    def _divergence_consistent(self) -> FullGameSemanticTapeEvidence:
        if self.tape_comparison_match != (self.first_divergence_kind is None):
            raise ValueError("tape comparison match and first divergence disagree")
        if self.fresh_process_replay_pass != (self.replay_divergence_class is None):
            raise ValueError("fresh-process replay verdict and divergence class disagree")
        if self.replay_divergence_detail is not None and self.replay_divergence_class is None:
            raise ValueError("a replay divergence detail needs a divergence class")
        if self.fresh_process_replay_pass and self.replay_steps_verified != self.recorded_steps:
            raise ValueError("a passing replay must verify every recorded step")
        return self


class FullGameReplayGate(_StrictModel):
    schema_version: Literal["xmage-full-game-replay-gate-1.1.0"] = (
        "xmage-full-game-replay-gate-1.1.0"
    )
    scenario_id: str
    seed: int = Field(ge=0)
    # C1: decided by the semantic replay tape, never by the twin transcript hash.
    semantic_replay_match: bool
    semantic_tape: FullGameSemanticTapeEvidence
    # Diagnostic only: two same-seed runs of the conformance runner hash their
    # reduced semantic transcripts; a mismatch is reported, not the verdict.
    twin_transcript_hash_match: bool
    raw_result_match: bool
    first_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    second_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    second_raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bit_exact_replay_validated: Literal[False] = False
    evidence_class: Literal["technical_conformance_only"] = FULL_GAME_EVIDENCE_CLASS
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False

    @model_validator(mode="after")
    def _verdict_is_the_tape(self) -> FullGameReplayGate:
        if self.semantic_replay_match != self.semantic_tape.passed:
            raise ValueError("semantic_replay_match must be the semantic tape verdict")
        return self


# #739: parallel bridge JVMs run in private directories below the engine
# working directory, each with a copy of XMage's card repository.
PRIVATE_ENGINE_DIRECTORY = "private"
XMAGE_CARD_REPOSITORY_FILE = "cards.h2.mv.db"
# Old layout: one ``private/<uuid32>`` directory per game. Orphans of it
# (a crashed Lab never removed them) are swept once they are this old.
_ORPHAN_PRIVATE_DIRECTORY = re.compile(r"[0-9a-f]{32}")
_ORPHAN_PRIVATE_DIRECTORY_AGE_SECONDS = 24 * 3600
# In a slot: the size and mtime of the shared repository the slot copied.
_SLOT_SOURCE_MARKER = "db.source"

# Bridge stderr kept in memory for diagnostics. Only the last 80 lines are
# ever reported (``stderr_tail``); the pump trims to this bound so a chatty
# JVM cannot grow the Lab process over a long game.
_STDERR_BUFFER_LINES = 1_000
_STDERR_TAIL_LINES = 80

# Bridge clients whose JVM is running, so an interrupted batch can stop them at
# once instead of waiting for every game in flight to finish.
_LIVE_CLIENTS: weakref.WeakSet[_RawFullGameClient] = weakref.WeakSet()
_LIVE_CLIENTS_LOCK = threading.Lock()


def kill_live_bridge_processes() -> int:
    """Kill every running full-game bridge JVM of this process; returns how many.

    Each killed client's channel is marked unusable, so its game thread fails
    fast (``BRIDGE_CLOSED``) and its ``close()`` skips the shutdown handshake.
    Used when a batch is interrupted; a killed game never becomes a record.
    """
    with _LIVE_CLIENTS_LOCK:
        clients = list(_LIVE_CLIENTS)
    killed = 0
    for client in clients:
        process = client._process
        if process is None or process.poll() is not None:
            continue
        client._transport_failure = client._transport_failure or "BRIDGE_ABORTED"
        with contextlib.suppress(OSError):
            process.kill()
            killed += 1
    return killed


# A worker slot is held with an exclusive, non-blocking lock on its lock file,
# so other threads, batches and processes skip it. Both raise OSError when the
# slot is taken.
if sys.platform == "win32":
    import msvcrt

    def _lock_slot(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)

    def _unlock_slot(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_slot(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_slot(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _copy_card_repository(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination)


def _remove_orphan_private_directories(root: Path) -> None:
    """Remove old-style ``private/<uuid32>`` directories older than 24 hours."""
    cutoff = time.time() - _ORPHAN_PRIVATE_DIRECTORY_AGE_SECONDS
    with contextlib.suppress(OSError):
        for entry in root.iterdir():
            if not _ORPHAN_PRIVATE_DIRECTORY.fullmatch(entry.name):
                continue
            with contextlib.suppress(OSError):
                if entry.is_dir() and not entry.is_symlink() and entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)


class _RawFullGameClient:
    """One-process client for the dedicated XMage full-game lane."""

    def __init__(
        self,
        command: tuple[str, ...],
        *,
        cwd: str | Path | None = None,
        request_timeout_seconds: float = 120.0,
        private_card_repository: bool = False,
        shutdown_grace_seconds: float = 5.0,
    ) -> None:
        if not command:
            raise ValueError("full-game bridge command must not be empty")
        if not math.isfinite(shutdown_grace_seconds) or shutdown_grace_seconds <= 0:
            raise ValueError("shutdown_grace_seconds must be positive and finite")
        if "full-game" not in command:
            raise ValueError(
                "full-game bridge command must explicitly include the full-game subcommand"
            )
        self.command = command
        self.cwd = resolve_engine_working_directory(cwd)
        self.request_timeout_seconds = request_timeout_seconds
        # How long an acked shutdown may take before the process is killed.
        # Only the CDS archive training run needs more (the JVM writes the
        # archive while it exits).
        self.shutdown_grace_seconds = shutdown_grace_seconds
        self._process: subprocess.Popen[str] | None = None
        self._stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        # Set once the request/reply pairing is lost (timeout, closed or broken
        # pipe, unparsable or unpaired reply). A late reply could still arrive
        # and be read as the answer to the next request, so the channel takes
        # no further requests, and close() skips the shutdown handshake that
        # would only wait out another full request timeout.
        self._transport_failure: str | None = None
        self.shutdown_disposition: str | None = None
        self.private_card_repository = private_card_repository
        self._private_directory: Path | None = None
        self._slot_lock: int | None = None

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr_lines[-_STDERR_TAIL_LINES:])

    @property
    def transport_failure(self) -> str | None:
        """The code that made this channel unusable, or None while it is usable."""
        return self._transport_failure

    def _transport_error(self, code: str, message: str) -> FullGameProtocolError:
        """A transport failure whose stderr stays in memory only (C4)."""
        self._transport_failure = self._transport_failure or code
        tail = self.stderr_tail
        return FullGameProtocolError(
            f"{message}: " + redacted_summary(code, tail),
            code=code,
            diagnostics=tail,
        )

    def start(self) -> None:
        if self._process is not None:
            if self._process.poll() is None:
                return
            raise FullGameProtocolError(
                f"full-game bridge already exited with code {self._process.returncode}",
                code="BRIDGE_EXITED",
            )
        try:
            process_cwd = self._prepare_private_directory() or self.cwd
            self._process = subprocess.Popen(
                self.command,
                cwd=process_cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise FullGameProtocolError(
                redacted_summary("BRIDGE_START_FAILED", (str(exc),)),
                code="BRIDGE_START_FAILED",
                diagnostics=(str(exc),),
            ) from None
        if self._process.stdout is None or self._process.stderr is None:
            raise FullGameProtocolError(
                "full-game bridge pipes unavailable", code="BRIDGE_START_FAILED"
            )
        self._stdout_thread = threading.Thread(
            target=self._pump_stdout,
            args=(self._process.stdout,),
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._pump_stderr,
            args=(self._process.stderr,),
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        with _LIVE_CLIENTS_LOCK:
            _LIVE_CLIENTS.add(self)

    @public_full_game_errors
    def request(self, message_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.start()
        process = self._process
        if process is None:
            raise FullGameProtocolError(
                "full-game bridge did not start", code="BRIDGE_START_FAILED"
            )
        if self._transport_failure is not None:
            raise FullGameProtocolError(
                f"full-game bridge channel is unusable after {self._transport_failure}",
                code="BRIDGE_UNUSABLE",
            )
        if process.poll() is not None or process.stdin is None:
            raise self._transport_error("BRIDGE_NOT_WRITABLE", "full-game bridge is not writable")
        request_id = str(uuid.uuid4())
        body = payload or {}
        request: BridgeRequestEnvelope = {
            "protocol_version": ENGINE_PROTOCOL_VERSION,
            "request_id": request_id,
            "engine": "xmage",
            "message_type": message_type,
            "method": message_type,
            "payload": body,
            "params": body,
        }
        try:
            process.stdin.write(json.dumps(request, sort_keys=True) + "\n")
            process.stdin.flush()
        except OSError:
            # The JVM exited between poll() and write (BrokenPipeError).
            raise self._transport_error(
                "BRIDGE_NOT_WRITABLE", "full-game bridge is not writable"
            ) from None
        try:
            line = self._stdout_queue.get(timeout=self.request_timeout_seconds)
        except queue.Empty:
            raise self._transport_error(
                "BRIDGE_TIMEOUT", f"full-game bridge timeout for {message_type!r}"
            ) from None
        if line is None:
            raise self._transport_error(
                "BRIDGE_CLOSED", f"full-game bridge closed before replying to {message_type!r}"
            )
        try:
            response = EngineProtocolResponse.from_wire(json.loads(line))
        except Exception:
            self._transport_failure = "INVALID_RESPONSE"
            raise FullGameProtocolError(
                f"invalid full-game bridge response for {message_type!r}: "
                + redacted_summary("INVALID_RESPONSE", (line,)),
                code="INVALID_RESPONSE",
                diagnostics=(line,),
            ) from None
        if response.protocol_version != ENGINE_PROTOCOL_VERSION:
            raise FullGameProtocolError(
                f"protocol mismatch: expected {ENGINE_PROTOCOL_VERSION}, "
                f"received {response.protocol_version}",
                code="PROTOCOL_MISMATCH",
            )
        if response.request_id != request_id:
            self._transport_failure = "REQUEST_ID_MISMATCH"
            raise FullGameProtocolError(
                "full-game bridge response request_id mismatch", code="REQUEST_ID_MISMATCH"
            )
        if not response.success:
            error = response.errors[0] if response.errors else None
            raw = () if error is None else (error.code, error.message)
            raise FullGameProtocolError(
                f"{message_type} failed: " + redacted_summary("BRIDGE_ERROR", raw),
                code="BRIDGE_ERROR",
                diagnostics=raw,
            )
        return response.payload

    def _prepare_private_directory(self) -> str | None:
        """#739: a working directory of its own for this bridge JVM.

        XMage keeps its card repository at ``./db/cards.h2`` relative to the
        process working directory and opens it with ``AUTO_SERVER``. JVMs that
        start at the same moment in one directory collide while scanning it
        (``XMAGE_CARD_REPOSITORY_INIT_FAILED``, a null ``expansionDao``), so a
        parallel game runs in its own directory with a copy of the shared,
        already-built repository. With no shared repository yet the JVM builds
        a private one, which :meth:`_release_private_directory` may promote.

        The directory is a worker slot, ``private/slot-<n>``: the first slot
        whose ``slot-<n>.lock`` this client can lock exclusively (``flock``,
        so other threads, batches and processes skip it). The repository is
        copied into a slot once and reused by the games that follow, and
        copied again when the slot's file is missing or the shared one changed.
        """
        if not self.private_card_repository:
            return None
        shared = Path(self.cwd or ".")
        root = shared / PRIVATE_ENGINE_DIRECTORY
        root.mkdir(parents=True, exist_ok=True)
        _remove_orphan_private_directories(root)
        slot = 0
        while True:
            descriptor = os.open(root / f"slot-{slot}.lock", os.O_RDWR | os.O_CREAT, 0o600)
            try:
                _lock_slot(descriptor)
            except OSError:
                os.close(descriptor)
                slot += 1
                continue
            break
        self._slot_lock = descriptor
        try:
            private = root / f"slot-{slot}"
            private.mkdir(exist_ok=True)
            self._private_directory = private
            source_file = shared / "db" / XMAGE_CARD_REPOSITORY_FILE
            slot_file = private / "db" / XMAGE_CARD_REPOSITORY_FILE
            if source_file.is_file():
                # H2 rewrites its file when a game closes it, so the slot's
                # own size says nothing; a marker records which source
                # version the slot copied.
                source_stat = source_file.stat()
                version = f"{source_stat.st_size}:{source_stat.st_mtime_ns}"
                marker = private / _SLOT_SOURCE_MARKER
                current = (
                    slot_file.is_file()
                    and marker.is_file()
                    and marker.read_text(encoding="utf-8") == version
                )
                if not current:
                    marker.unlink(missing_ok=True)
                    shutil.rmtree(private / "db", ignore_errors=True)
                    _copy_card_repository(shared / "db", private / "db")
                    marker.write_text(version, encoding="utf-8")
        except BaseException:
            self._release_slot_lock()
            self._private_directory = None
            raise
        return str(private)

    def _release_slot_lock(self) -> None:
        descriptor = self._slot_lock
        self._slot_lock = None
        if descriptor is not None:
            with contextlib.suppress(OSError):
                _unlock_slot(descriptor)
            with contextlib.suppress(OSError):
                os.close(descriptor)

    def _release_private_directory(self, disposition: str) -> None:
        """Free the worker slot; promote a freshly built repository.

        The slot directory stays for the next game. Only a gracefully shut
        down JVM has closed its H2 files, so only then does a repository it
        built become the shared one, and only when no shared repository
        appeared meanwhile (``os.rename`` refuses a non-empty target, so
        concurrent promotions cannot mix files). A promoted or killed JVM's
        repository leaves the slot empty or is dropped, so the next game
        starts from a clean copy.
        """
        private = self._private_directory
        if private is None:
            return
        self._private_directory = None
        shared = private.parent.parent / "db"
        built = private / "db"
        try:
            if (
                disposition == FULL_GAME_SHUTDOWN_GRACEFUL
                and (built / XMAGE_CARD_REPOSITORY_FILE).is_file()
                and not (shared / XMAGE_CARD_REPOSITORY_FILE).is_file()
            ):
                with contextlib.suppress(OSError):
                    os.rename(built, shared)
            if disposition != FULL_GAME_SHUTDOWN_GRACEFUL:
                # A killed JVM may have left half-written H2 files.
                shutil.rmtree(built, ignore_errors=True)
        finally:
            self._release_slot_lock()

    def close(self) -> str:
        """Shut the bridge process down and release a private directory."""
        disposition = self._close_process()
        self._release_private_directory(disposition)
        return disposition

    def _close_process(self) -> str:
        """Shut the bridge process down, returning the observed disposition.

        Same request/wait/kill sequence as always (no parallel lifecycle);
        the outcome is now returned instead of swallowed so evidence can
        distinguish graceful shutdown from kill/timeout/failed-shutdown:

        - ``graceful_shutdown``: shutdown request acked, process exited
          without kill;
        - ``unacked_exit``: shutdown request failed but the process exited
          on its own without kill;
        - ``forced_kill``: the process had to be killed;
        - ``already_exited``: no live process at entry (or none started).

        Never raises for teardown itself: failures are encoded in the
        returned disposition and callers fail closed where a shutdown
        claim matters.
        """
        process = self._process
        if process is None:
            return FULL_GAME_SHUTDOWN_ALREADY_EXITED
        try:
            if process.poll() is not None:
                return FULL_GAME_SHUTDOWN_ALREADY_EXITED
            shutdown_acked = self._transport_failure is None
            if shutdown_acked:
                try:
                    self.request("shutdown_engine")
                except Exception:
                    shutdown_acked = False
            if process.poll() is None:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=self.shutdown_grace_seconds)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
                return FULL_GAME_SHUTDOWN_FORCED_KILL
            if shutdown_acked:
                return FULL_GAME_SHUTDOWN_GRACEFUL
            return FULL_GAME_SHUTDOWN_UNACKED_EXIT
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    with contextlib.suppress(OSError):
                        stream.close()
            for thread in (self._stdout_thread, self._stderr_thread):
                if thread is not None:
                    thread.join(timeout=2)
            self._process = None
            with _LIVE_CLIENTS_LOCK:
                _LIVE_CLIENTS.discard(self)

    def _pump_stdout(self, stream: TextIO) -> None:
        try:
            for line in iter(stream.readline, ""):
                self._stdout_queue.put(line)
        finally:
            self._stdout_queue.put(None)

    def _pump_stderr(self, stream: TextIO) -> None:
        lines = self._stderr_lines
        for line in iter(stream.readline, ""):
            lines.append(line.rstrip("\n"))
            if len(lines) > _STDERR_BUFFER_LINES:
                # The pump is the only writer; readers only slice the tail.
                del lines[:-_STDERR_TAIL_LINES]

    def __enter__(self) -> _RawFullGameClient:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.shutdown_disposition = self.close()


def _public_error(exc: Exception) -> Exception:
    """The exception a public :class:`XmageFullGameRunner` method would raise for ``exc``."""

    @public_full_game_errors
    def reraise() -> None:
        raise exc

    try:
        reraise()
    except Exception as public:
        return public
    raise AssertionError("unreachable")


class XmageFullGameRunner:
    """Run one isolated 2..6-player XMage Commander game with Commander Lab pilot policy."""

    MIN_PLAYERS = 2
    MAX_PLAYERS = 6

    def __init__(
        self,
        command: tuple[str, ...] | None = None,
        *,
        cwd: str | Path | None = None,
        request_timeout_seconds: float = 120.0,
        max_decisions: int = 50_000,
        private_card_repository: bool = False,
        shutdown_grace_seconds: float = 5.0,
    ) -> None:
        self.command = command or self.command_from_environment()
        self.cwd = cwd
        # #739: run each bridge JVM with its own copy of the card repository
        # (set by the batch runner for parallel games).
        self.private_card_repository = private_card_repository
        self.request_timeout_seconds = request_timeout_seconds
        self.shutdown_grace_seconds = shutdown_grace_seconds
        self.max_decisions = max_decisions
        if self.max_decisions < 1:
            raise ValueError("max_decisions must be positive")
        # Armed by run() for the duration of one game (C2 per-frame audit).
        self._hidden_audit: FullGameHiddenInformationAudit | None = None

    @staticmethod
    def command_from_environment() -> tuple[str, ...] | None:
        raw = os.getenv(XMAGE_FULL_GAME_COMMAND_ENV)
        return tuple(shlex.split(raw)) if raw else None

    @public_full_game_errors
    def run(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> FullGameConformanceResult:
        command = self.command
        if command is None:
            raise FullGameConformanceError(
                f"full-game bridge is not configured; set {XMAGE_FULL_GAME_COMMAND_ENV}"
            )
        policy = self._validated_policy(scenario, decks, pilots)
        audit = FullGameHiddenInformationAudit()
        self._hidden_audit = audit

        with _RawFullGameClient(
            command,
            cwd=self.cwd,
            request_timeout_seconds=self.request_timeout_seconds,
            private_card_repository=self.private_card_repository,
            shutdown_grace_seconds=self.shutdown_grace_seconds,
        ) as client:
            provider = self._open_game(client, scenario, decks)
            try:
                _decision_count, _, terminal = self._drive(client, policy, stop_after=None)
            finally:
                self._hidden_audit = None
            if terminal is not True:
                raise FullGameConformanceError("full game ended without a terminal state")
            result = cast(FullGameResultWire, client.request("get_full_game_result"))
        # The same lifecycle gate as the bounded smoke: a game-over result rests
        # on an observed graceful shutdown, never on a suppressed kill/timeout.
        disposition = getattr(client, "shutdown_disposition", None)
        if disposition != FULL_GAME_SHUTDOWN_GRACEFUL:
            raise FullGameConformanceError(f"full game shutdown not graceful: {disposition}")
        return self._build_result(
            scenario, provider, result, shutdown_disposition=disposition, hidden_audit=audit
        )

    def run_batch(
        self,
        games: Sequence[
            tuple[
                FutureXmageScenario,
                tuple[RulesDeckInput, ...],
                tuple[FullGamePilotBinding, ...],
            ]
        ],
    ) -> list[FullGameConformanceResult | Exception]:
        """Play several games in one bridge process (Owner decision 2026-10-15).

        Opt-in for batch measurement runs only; evidence lanes keep :meth:`run`, one
        game per process. The bridge must be started with
        ``-Dcommanderlab.fullGame.gamesPerJvm=N`` for at least ``len(games)``. Each game
        is shut down before the next one starts. After a failed game the process is
        discarded and the remaining games start in a fresh one. Every result rests on
        the graceful shutdown of the process that played it.
        """
        command = self.command
        if command is None:
            raise FullGameConformanceError(
                f"full-game bridge is not configured; set {XMAGE_FULL_GAME_COMMAND_ENV}"
            )
        outcomes: list[FullGameConformanceResult | Exception] = []
        pending = list(games)
        while pending:
            played: list[tuple[int, Any, ProviderIdentityWire, FullGameResultWire, Any]] = []
            client = _RawFullGameClient(
                command,
                cwd=self.cwd,
                request_timeout_seconds=self.request_timeout_seconds,
                private_card_repository=self.private_card_repository,
                shutdown_grace_seconds=self.shutdown_grace_seconds,
            )
            with client:
                while pending:
                    scenario, decks, pilots = pending.pop(0)
                    index = len(outcomes)
                    outcomes.append(FullGameConformanceError("game not finished"))
                    try:
                        policy = self._validated_policy(scenario, decks, pilots)
                        audit = FullGameHiddenInformationAudit()
                        self._hidden_audit = audit
                        try:
                            provider = self._open_game(client, scenario, decks)
                            _count, _, terminal = self._drive(client, policy, stop_after=None)
                        finally:
                            self._hidden_audit = None
                        if terminal is not True:
                            raise FullGameConformanceError("full game ended without game over")
                        result = cast(FullGameResultWire, client.request("get_full_game_result"))
                        client.request("shutdown_game")
                    except Exception as exc:  # the process is suspect; start a fresh one
                        outcomes[index] = _public_error(exc)
                        break
                    played.append((index, scenario, provider, result, audit))
            disposition = getattr(client, "shutdown_disposition", None)
            for index, scenario, provider, result, audit in played:
                try:
                    outcomes[index] = self._build_result(
                        scenario,
                        provider,
                        result,
                        shutdown_disposition=disposition,
                        hidden_audit=audit,
                    )
                except Exception as exc:
                    outcomes[index] = _public_error(exc)
        return outcomes

    @public_full_game_errors
    def run_smoke(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
        smoke_decision_target: int = 25,
        stop_at_turn: int | None = None,
    ) -> FullGameSmokeResult:
        """Drive a bounded live lifecycle smoke for one supported cardinality.

        Reuses the exact fail-closed validation, handshake, seed/count binding,
        and authoritative pilot policy of :meth:`run`, but stops after
        ``smoke_decision_target`` answered decisions (or earlier terminal) and
        shuts the engine down cleanly instead of requiring game over. Any
        unsupported engine callback surfaces as ``FullGameProtocolError`` /
        ``FullGameConformanceError`` from the shared drive loop, failing the
        smoke closed.
        """
        if smoke_decision_target < 1:
            raise ValueError("smoke_decision_target must be positive")
        command = self.command
        if command is None:
            raise FullGameConformanceError(
                f"full-game bridge is not configured; set {XMAGE_FULL_GAME_COMMAND_ENV}"
            )
        policy = self._validated_policy(scenario, decks, pilots)

        client = _RawFullGameClient(
            command,
            cwd=self.cwd,
            request_timeout_seconds=self.request_timeout_seconds,
            private_card_repository=self.private_card_repository,
            shutdown_grace_seconds=self.shutdown_grace_seconds,
        )
        with client:
            provider = self._open_game(client, scenario, decks)
            progress: list[ProgressEntry] = []
            stop: dict[str, Any] = {}
            decision_count, observed, terminal = self._drive(
                client,
                policy,
                stop_after=smoke_decision_target,
                stop_at_turn=stop_at_turn,
                progress=progress,
                stop=stop,
            )
        # P1 shutdown evidence: a bounded smoke PASS must rest on observed
        # graceful shutdown, never on a suppressed kill/timeout. Anything
        # else fails the smoke closed (message carries the disposition).
        disposition = getattr(client, "shutdown_disposition", None)
        if disposition != FULL_GAME_SHUTDOWN_GRACEFUL:
            raise FullGameConformanceError(
                "bounded smoke shutdown not graceful: "
                f"{disposition} (decisions={decision_count} terminal={terminal})"
            )
        if decision_count == 0:
            raise FullGameConformanceError(
                "bounded smoke observed no authoritative decisions before terminal"
            )

        if stop_at_turn is not None and stop.get("reason") != "turn_boundary":
            raise FullGameConformanceError(
                f"bounded smoke stopped before required turn boundary: {stop.get('reason')}"
            )

        return FullGameSmokeResult(
            scenario_id=scenario.scenario_id,
            player_count=scenario.player_count,
            seed=scenario.seed,
            engine_version=str(provider.get("engine_version", "unknown")),
            xmage_commit=scenario.xmage_commit,
            decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
            decision_count=decision_count,
            smoke_decision_target=smoke_decision_target,
            bounded_criterion_met=True,
            terminal_reached=terminal,
            seed_preserved=True,
            player_count_preserved=True,
            observed_decision_classes=tuple(observed),
            stop_reason=stop.get("reason", "terminal" if terminal else "decision_limit"),
            stop_turn_number=stop.get("turn"),
            progress_trace=tuple(progress),
            progress_digest=hashlib.sha256(
                json.dumps(progress, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        )

    def _validated_policy(
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> ExternalPilotDecisionPolicy:
        self._validate_inputs(scenario, decks, pilots)
        runtime_pilots = tuple(
            _RuntimePilot(
                binding=binding,
                pilot=build_pilot(binding.config, strategy=binding.strategy),
            )
            for binding in sorted(pilots, key=lambda item: item.seat)
        )
        return ExternalPilotDecisionPolicy(runtime_pilots, scenario.seed)

    def _open_game(
        self,
        client: _RawFullGameClient,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
    ) -> ProviderIdentityWire:
        started = cast(StartEngineWire, client.request("start_engine"))
        if started.get("lane") != FULL_GAME_LANE:
            raise FullGameConformanceError("bridge did not enter explicit full-game lane")
        provider = cast(ProviderIdentityWire, client.request("get_provider_version"))
        capabilities = cast(CapabilitiesWire, client.request("get_capabilities"))
        self._validate_handshake(scenario, provider, capabilities)

        handles: list[str] = []
        for deck in decks:
            imported = client.request("import_deck", {"deck": self._deck_payload(deck)})
            handle = imported.get("deck_handle")
            if not isinstance(handle, dict):
                raise FullGameConformanceError("IMPORT_DECK returned no deck_handle")
            handle_id = str(handle.get("handle_id", "")).strip()
            if not handle_id:
                raise FullGameConformanceError("IMPORT_DECK returned blank handle_id")
            handles.append(handle_id)

        game_id = f"{scenario.scenario_id}:{scenario.candidate_id}:{scenario.seed}"
        player_count = scenario.player_count
        created = client.request(
            "create_full_game",
            {
                "game_id": game_id,
                "deck_handles": handles,
                "seed": scenario.seed,
                "starting_player_seat": scenario.seed % player_count,
                "starting_life": 40,
            },
        )
        if created.get("player_count") != player_count or created.get("seed") != scenario.seed:
            raise FullGameConformanceError(
                "full-game creation did not preserve player-count/seed contract"
            )
        if created.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
            raise FullGameConformanceError("full-game creation returned unsafe evidence class")
        if created.get("holdout_consumed") is not False:
            raise FullGameConformanceError("technical conformance must not consume holdout")
        return provider

    def _drive(
        self,
        client: _RawFullGameClient,
        policy: ExternalPilotDecisionPolicy,
        *,
        stop_after: int | None,
        stop_at_turn: int | None = None,
        progress: list[ProgressEntry] | None = None,
        stop: dict[str, Any] | None = None,
    ) -> tuple[int, list[str], bool]:
        """Drive authoritative decisions until terminal (or ``stop_after`` answers).

        With ``stop_at_turn`` the drive also stops before answering the first
        decision of that turn. ``progress`` collects each answered decision's
        public metadata plus the semantic response digest after acknowledged submission.

        Returns ``(decision_count, observed_decision_classes, terminal)``.
        Shared verbatim by :meth:`run` (``stop_after=None``) and
        :meth:`run_smoke` so smoke progression and full-game progression
        cannot diverge.
        """
        status = client.request("start_full_game")
        decision_count = 0
        observed: list[str] = []
        while True:
            failure = status.get("failure")
            if isinstance(failure, dict):
                raw_failure = json.dumps(failure, sort_keys=True)
                raise FullGameConformanceError(
                    "XMage full-game engine failed: "
                    + redacted_summary("ENGINE_FAILURE", (raw_failure,))
                )
            decision = status.get("decision")
            if isinstance(decision, dict):
                decision_class = decision.get("decision_class")
                pilot_state = decision.get("pilot_state")
                turn = pilot_state.get("turn_number") if isinstance(pilot_state, dict) else None
                if stop_at_turn is not None and type(turn) is int and turn >= stop_at_turn:
                    if stop is not None:
                        stop.update(reason="turn_boundary", turn=turn)
                    return decision_count, observed, False
                # Inspect the frame returned by the final permitted submission
                # before applying the cap; it may already be the turn boundary.
                if stop_after is not None and decision_count >= stop_after:
                    if stop is not None:
                        stop.update(reason="decision_limit")
                    return decision_count, observed, False
                decision_count += 1
                if decision_count > self.max_decisions:
                    raise FullGameConformanceError(
                        f"full-game exceeded max_decisions={self.max_decisions}"
                    )
                if isinstance(decision_class, str) and decision_class not in observed:
                    observed.append(decision_class)
                audit = self._hidden_audit
                if audit is not None:
                    rows, visible, violations = audit_actor_scoped_frame(decision)
                    if violations:
                        raise FullGameConformanceError(
                            "hidden information not actor-scoped at decision "
                            f"{decision_count}: " + "; ".join(violations)
                        )
                    audit.frames_audited += 1
                    audit.non_actor_rows_audited += rows
                    audit.non_actor_rows_engine_visible += visible
                response = policy.decide(decision)
                status = client.request(
                    "submit_full_game_decision",
                    {"response": response},
                )
                if progress is not None and not isinstance(status.get("failure"), dict):
                    selected, _labels = selected_fingerprints_for_response(
                        decision, list(response.get("selected_option_ids", []))
                    )
                    ordered, _ordered_labels = selected_fingerprints_for_response(
                        decision, list(response.get("ordering", []))
                    )
                    response_digest = canonical_hash(
                        {
                            "selected": selected,
                            "ordering": ordered,
                            "numeric_choice": response.get("numeric_choice"),
                            "numeric_choices": response.get("numeric_choices"),
                        }
                    )
                    seat = decision.get("seat")
                    phase = pilot_state.get("phase") if isinstance(pilot_state, dict) else None
                    progress.append(
                        (
                            str(decision_class),
                            seat if type(seat) is int else None,
                            turn if type(turn) is int else None,
                            phase if isinstance(phase, str) else None,
                            response_digest,
                            _active_seat(pilot_state),
                        )
                    )
                continue
            if bool(status.get("terminal")):
                if stop is not None:
                    stop.update(reason="terminal")
                return decision_count, observed, True
            if stop_after is not None and decision_count >= stop_after:
                if stop is not None:
                    stop.update(reason="decision_limit")
                return decision_count, observed, False
            status = client.request("get_full_game_decision")

    @staticmethod
    def replay_gate(
        *,
        scenario: FutureXmageScenario,
        first: FullGameConformanceResult,
        second: FullGameConformanceResult,
        tape: FullGameSemanticTapeEvidence,
    ) -> FullGameReplayGate:
        return FullGameReplayGate(
            scenario_id=scenario.scenario_id,
            seed=scenario.seed,
            semantic_replay_match=tape.passed,
            semantic_tape=tape,
            twin_transcript_hash_match=(
                first.semantic_transcript_sha256 == second.semantic_transcript_sha256
            ),
            raw_result_match=first.raw_result_sha256 == second.raw_result_sha256,
            first_semantic_sha256=first.semantic_transcript_sha256,
            second_semantic_sha256=second.semantic_transcript_sha256,
            first_raw_sha256=first.raw_result_sha256,
            second_raw_sha256=second.raw_result_sha256,
            bit_exact_replay_validated=False,
        )

    @staticmethod
    def _validate_inputs(
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> None:
        player_count = scenario.player_count
        if (
            player_count < XmageFullGameRunner.MIN_PLAYERS
            or player_count > XmageFullGameRunner.MAX_PLAYERS
        ):
            raise FullGameConformanceError("operational full-game scope is two to six players")
        if len(decks) != player_count or len(pilots) != player_count:
            raise FullGameConformanceError(
                "deck/pilot cardinality must equal the scenario player count"
            )
        if len({deck.deck_id for deck in decks}) != player_count:
            raise FullGameConformanceError("full-game requires distinct deck identities per seat")
        if {pilot.seat for pilot in pilots} != set(range(1, player_count + 1)):
            raise FullGameConformanceError("pilot bindings must cover seats 1..N exactly")
        for index, (deck, pilot) in enumerate(
            zip(decks, sorted(pilots, key=lambda item: item.seat), strict=True),
            start=1,
        ):
            if deck.deck_id != pilot.deck_id:
                raise FullGameConformanceError(
                    f"seat {index} deck/pilot mismatch: {deck.deck_id} != {pilot.deck_id}"
                )
            if tuple(deck.commander_names) != tuple(pilot.commander_names):
                raise FullGameConformanceError(f"seat {index} commander/pilot mismatch")
            if deck.deck_hash is None:
                raise FullGameConformanceError(f"seat {index} deck_hash is required")
        own = decks[scenario.seat - 1]
        if own.deck_id != scenario.candidate_id:
            raise FullGameConformanceError(
                "FutureXmageScenario candidate_id must occupy the declared scenario seat"
            )
        if own.deck_hash != scenario.deck_hash:
            raise FullGameConformanceError("FutureXmageScenario deck_hash does not match own deck")
        opponent_ids = tuple(
            deck.deck_id for index, deck in enumerate(decks, start=1) if index != scenario.seat
        )
        if opponent_ids != scenario.opponent_deck_ids:
            raise FullGameConformanceError(
                "FutureXmageScenario opponent_deck_ids do not match seat-ordered opponents"
            )
        own_pilot = sorted(pilots, key=lambda item: item.seat)[scenario.seat - 1]
        if own_pilot.pilot_identity != scenario.pilot_identity:
            raise FullGameConformanceError("scenario pilot_identity mismatch")
        if own_pilot.pilot_version != scenario.pilot_version:
            raise FullGameConformanceError("scenario pilot_version mismatch")
        if own_pilot.decision_policy_version != scenario.decision_policy_version:
            raise FullGameConformanceError("scenario decision_policy_version mismatch")

    @staticmethod
    def _validate_handshake(
        scenario: FutureXmageScenario,
        provider: ProviderIdentityWire,
        capabilities_payload: CapabilitiesWire,
    ) -> None:
        if provider.get("engine") != "xmage":
            raise FullGameConformanceError("full-game provider is not XMage")
        if provider.get("engine_commit") != scenario.xmage_commit:
            raise FullGameConformanceError(
                f"XMage commit mismatch: scenario={scenario.xmage_commit} "
                f"provider={provider.get('engine_commit')}"
            )
        raw_lane = capabilities_payload.get("full_game_lane")
        caps = capabilities_payload.get("capabilities")
        if not isinstance(raw_lane, dict) or not isinstance(caps, dict):
            raise FullGameConformanceError("full-game capability handshake is incomplete")
        lane = cast(FullGameLaneWire, raw_lane)
        if lane.get("lane") != FULL_GAME_LANE:
            raise FullGameConformanceError("full-game lane identity mismatch")
        if lane.get("decision_protocol_version") != FULL_GAME_DECISION_PROTOCOL_VERSION:
            raise FullGameConformanceError("full-game decision protocol mismatch")
        lane_min = lane.get("min_players")
        lane_max = lane.get("max_players")
        if (
            not isinstance(lane_min, int)
            or not isinstance(lane_max, int)
            or lane_min != XmageFullGameRunner.MIN_PLAYERS
            or lane_max != XmageFullGameRunner.MAX_PLAYERS
            or not lane_min <= scenario.player_count <= lane_max
        ):
            raise FullGameConformanceError(
                "full-game capability player-count range does not cover the scenario"
            )
        if lane.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
            raise FullGameConformanceError("full-game capability evidence class is unsafe")
        if lane.get("generic_capability_promotion") is not False:
            raise FullGameConformanceError("full-game lane must not promote generic capabilities")
        if lane.get("one_game_per_process") is not True:
            raise FullGameConformanceError("full-game lane must isolate one game per JVM")
        if lane.get("bit_exact_replay_validated") is not False:
            raise FullGameConformanceError("bit-exact replay may not be preclaimed")
        required_true = {
            "commander_supported",
            "partner_supported",
            "multiplayer_supported",
            "headless_supported",
            "seed_supported",
            "deck_import_supported",
            "target_selection_supported",
            "mode_selection_supported",
            "trigger_order_supported",
            "mulligan_supported",
        }
        missing = sorted(name for name in required_true if caps.get(name) is not True)
        if missing:
            raise FullGameConformanceError(
                "full-game lane missing required capabilities: " + ", ".join(missing)
            )

    @staticmethod
    def _deck_payload(deck: RulesDeckInput) -> FullGameDeckPayload:
        if deck.deck_hash is None:
            raise FullGameConformanceError(f"deck_hash required for {deck.deck_id}")
        return {
            "deck_id": deck.deck_id,
            "deck_hash": deck.deck_hash,
            "mainboard": list(deck.mainboard),
            "commander_names": list(deck.commander_names),
            "sideboard": list(deck.sideboard),
        }

    @classmethod
    def _build_result(
        cls,
        scenario: FutureXmageScenario,
        provider: ProviderIdentityWire,
        result: FullGameResultWire,
        *,
        shutdown_disposition: str | None = None,
        hidden_audit: FullGameHiddenInformationAudit | None = None,
    ) -> FullGameConformanceResult:
        if shutdown_disposition != FULL_GAME_SHUTDOWN_GRACEFUL:
            raise FullGameConformanceError(
                f"full game shutdown not graceful: {shutdown_disposition}"
            )
        if result.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
            raise FullGameConformanceError("result evidence class is not technical conformance")
        for field in (
            "consumed_gameplay_evidence",
            "holdout_consumed",
            "official_campaign_eligible",
        ):
            if result.get(field) is not False:
                raise FullGameConformanceError(f"unsafe full-game result flag: {field}")
        if result.get("rules_authority") != "xmage":
            raise FullGameConformanceError("result rules authority is not XMage")
        if result.get("decision_policy_authority") != "commander_lab_external_pilot":
            raise FullGameConformanceError("result decision authority is not Commander Lab pilot")
        if result.get("bit_exact_replay_validated") is not False:
            raise FullGameConformanceError("bit-exact replay was promoted without gate")
        if result.get("seed") != scenario.seed:
            raise FullGameConformanceError("result seed mismatch")
        if result.get("terminal") is not True:
            raise FullGameConformanceError("XMage full-game did not terminate")

        outcomes = result.get("outcomes")
        if not isinstance(outcomes, list) or len(outcomes) != scenario.player_count:
            raise FullGameConformanceError(
                "full-game result must contain one seat outcome per player"
            )
        winner_seats = tuple(
            int(item.get("seat", -1)) + 1
            for item in outcomes
            if isinstance(item, dict) and item.get("won") is True
        )
        semantic = cls.semantic_transcript(result)
        audit = hidden_audit or FullGameHiddenInformationAudit()
        return FullGameConformanceResult(
            scenario=scenario,
            engine_version=str(provider.get("engine_version", "unknown")),
            xmage_commit=str(provider.get("engine_commit", "")),
            decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
            decision_count=int(cast(int, result.get("decision_count", 0))),
            terminal=True,
            winner_seats=winner_seats,
            result_payload=cast(dict[str, Any], result),
            semantic_transcript_sha256=cls._sha256(semantic),
            raw_result_sha256=cls._sha256(result),
            shutdown_disposition=FULL_GAME_SHUTDOWN_GRACEFUL,
            hidden_information_audit=audit,
            claim_basis=FullGameClaimBasis(
                hidden_information_actor_scoped=(
                    "OBSERVED" if audit.frames_audited > 0 else "DECLARED_NOT_OBSERVED"
                )
            ),
        )

    @staticmethod
    def semantic_transcript(result: FullGameResultWire) -> SemanticTranscript:
        transcript = result.get("transcript")
        semantic_events: list[SemanticEventWire] = []
        if isinstance(transcript, list):
            for raw in transcript:
                if not isinstance(raw, dict):
                    continue
                semantic_events.append(
                    {
                        "sequence": raw.get("sequence"),
                        "kind": raw.get("kind"),
                        "decision_class": raw.get("decision_class"),
                        "actor_seat": raw.get("actor_seat"),
                        "prompt": XmageFullGameRunner._semantic_text(raw.get("prompt")),
                        "selected_option_types": raw.get("selected_option_types"),
                        "selected_option_labels": XmageFullGameRunner._semantic_text_list(
                            raw.get("selected_option_labels")
                        ),
                        "numeric_choice": raw.get("numeric_choice"),
                    }
                )
        outcomes = result.get("outcomes")
        semantic_outcomes: list[SemanticOutcomeWire] = []
        if isinstance(outcomes, list):
            semantic_outcomes = [
                {
                    "seat": item.get("seat"),
                    "life": item.get("life"),
                    "won": item.get("won"),
                    "lost": item.get("lost"),
                    "left": item.get("left"),
                }
                for item in outcomes
                if isinstance(item, dict)
            ]
        return {
            "seed": result.get("seed"),
            "turn_number": result.get("turn_number"),
            "decision_count": result.get("decision_count"),
            "events": semantic_events,
            "outcomes": semantic_outcomes,
        }

    @staticmethod
    def _semantic_text(value: object) -> object:
        if not isinstance(value, str):
            return value
        text = re.sub(
            r"\s+object_id=(['\"])[^'\"]+\1",
            "",
            value,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            "<engine-object>",
            text,
        )
        text = re.sub(r"(</font>)\s*\[[0-9a-fA-F]{3,8}\]", r"\1", text)
        # #710: the engine appends the short id after the object NAME, so it
        # survives whenever the message continues past it (punctuation, further
        # words, another closing tag) instead of ending the text. Strip it
        # wherever it is appended, not only before </div>/end-of-text.
        text = _XMAGE_SHORT_ID_AFTER_CLOSE_RE.sub(r"\1", text)
        text = _XMAGE_SHORT_ID_APPENDED_RE.sub("", text)
        return text

    @staticmethod
    def _semantic_text_list(value: object) -> object:
        if not isinstance(value, list):
            return value
        return [XmageFullGameRunner._semantic_text(item) for item in value]

    @staticmethod
    def _sha256(value: SemanticTranscript | FullGameResultWire) -> str:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode()).hexdigest()


__all__ = [
    "FULL_GAME_DECISION_PROTOCOL_VERSION",
    "FULL_GAME_EVIDENCE_CLASS",
    "FULL_GAME_LANE",
    "FULL_GAME_SHUTDOWN_ALREADY_EXITED",
    "FULL_GAME_SHUTDOWN_FORCED_KILL",
    "FULL_GAME_SHUTDOWN_GRACEFUL",
    "FULL_GAME_SHUTDOWN_UNACKED_EXIT",
    "XMAGE_FULL_GAME_COMMAND_ENV",
    "ExternalPilotDecisionPolicy",
    "FullGameConformanceError",
    "FullGameConformanceResult",
    "FullGamePilotBinding",
    "FullGameProtocolError",
    "FullGameReplayGate",
    "FullGameSemanticTapeEvidence",
    "XmageFullGameRunner",
    "_RuntimePilot",
    "mana_payment_fit",
    "public_full_game_errors",
]
