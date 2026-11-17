"""Play one simulated game with the rules engine and record it for the Studio viewer.

The existing full-game runner does all the work: XMage decides every rule, the Lab's pilots
decide every choice. This module only chooses decks and a seed, lets the runner play, and has
the recorder of ``games.py`` write down what happened. Every seat is a pilot here; a human
seat is a later step.
"""

from __future__ import annotations

import contextlib
import copy
import queue
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from commander_lab.agents import (
    derive_deck_plan,
    style_label,
    style_reserve_mana,
    style_weights,
)
from commander_lab.bridge_qualification import BRIDGE_ALIGNED, bridge_qualification
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.failure_privacy import (
    public_exception_type,
    public_full_game_exception_message,
)
from commander_lab.engine.rules.full_game import (
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGamePilotBinding,
    FullGameProtocolError,
    XmageFullGameRunner,
    _RawFullGameClient,
)
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin
from commander_lab.storage import sha256_value

from .games import (
    DecisionPolicy,
    GameRecorder,
    RecordingPolicy,
    frame_of,
    free_game_id,
    redact_frame_for_human_seats,
    redact_pilot_state_for_human_seats,
)
from .launch import bridge_jar_sha256, engine_command

PILOT_IDENTITY = "GenericCommanderPilot"
PILOT_VERSION = "1.0.0"
POLICY_VERSION = "xmage-full-game-policy-1.0.0"
BRIDGE_VERSION = "xmage-engine-bridge-0.1.0-SNAPSHOT"


def _with_hash(deck: RulesDeckInput) -> RulesDeckInput:
    if deck.deck_hash is not None:
        return deck
    derived = sha256_value(
        {
            "deck_id": deck.deck_id,
            "commander_names": list(deck.commander_names),
            "mainboard": list(deck.mainboard),
            "sideboard": list(deck.sideboard),
        }
    )
    return deck.model_copy(update={"deck_hash": derived})


def load_decks(paths: list[Path]) -> tuple[RulesDeckInput, ...]:
    """Deck snapshots in seat order. Two to six decks, each with its own id."""
    if not 2 <= len(paths) <= 6:
        raise ValueError("a game has two to six seats")
    decks = tuple(_with_hash(load_rules_deck_snapshot(path)) for path in paths)
    if len({deck.deck_id for deck in decks}) != len(decks):
        raise ValueError("every seat needs its own deck (distinct deck ids)")
    return decks


class _RecordingRunner(XmageFullGameRunner):
    """The full-game runner with a recorder between the engine's questions and the pilots."""

    recorder: GameRecorder | None = None

    def _validated_policy(  # type: ignore[override]
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> DecisionPolicy:
        policy = super()._validated_policy(scenario, decks, pilots)
        return RecordingPolicy(policy, self._recorder_for(scenario))

    def _recorder_for(self, scenario: FutureXmageScenario) -> GameRecorder:
        """The log the game of ``scenario`` is written to; one bound recorder for one game."""
        if self.recorder is None:
            raise RuntimeError("no recorder bound")
        return self.recorder

    def _drive(  # type: ignore[override]
        self, client: object, policy: object, *, stop_after: int | None = None, **kwargs: object
    ) -> tuple[int, object, bool]:
        res = super()._drive(client, policy, stop_after=stop_after, **kwargs)  # type: ignore[arg-type]
        if self.recorder is not None and hasattr(client, "request"):
            try:
                raw_log = client.request("export_event_log")
                if isinstance(raw_log, dict):
                    events = raw_log.get("events")
                    if isinstance(events, list):
                        self.recorder.save_event_log(events)
            except Exception:
                pass
        return res


@dataclass(frozen=True)
class PreparedGame:
    """Everything one recorded game needs before the engine is asked anything."""

    game_id: str
    scenario: FutureXmageScenario
    decks: tuple[RulesDeckInput, ...]
    pilots: tuple[FullGamePilotBinding, ...]
    header: dict[str, object]


def prepare_game(
    decks: tuple[RulesDeckInput, ...],
    *,
    seed: int,
    game_id: str,
    strategy: str = "generic",
    style: float | None = None,
    seat_styles: Mapping[int, float] | None = None,
    human_seats: Sequence[int] = (),
    decision_timeout_seconds: int = 120,
    data_folder: str | Path | None = None,
    command: Sequence[str] | None = None,
    jar_sha256: str | None = None,
    qualification: Mapping[str, object] | None = None,
) -> PreparedGame:
    """Scenario, pilots and log header of one game. A game played alone and a game played in a
    batch (``play_batch``) are built by this one function, so they cannot differ in setup."""
    own = decks[0]
    if own.deck_hash is None:
        raise ValueError("the own deck has no deck hash")
    human_set: list[int] = []
    for raw_seat in human_seats:
        seat_idx = int(raw_seat)
        if seat_idx < 0 or seat_idx >= len(decks):
            raise ValueError(f"human seat {seat_idx} out of range 0..{len(decks) - 1}")
        if seat_idx not in human_set:
            human_set.append(seat_idx)
    if decision_timeout_seconds < 0 or decision_timeout_seconds > 86_400:
        raise ValueError("decision_timeout_seconds must be between 0 and 86400")
    pin = canonical_xmage_engine_pin()
    resolved_sha = (
        jar_sha256
        if jar_sha256 is not None
        else (
            bridge_jar_sha256(data_folder, command)
            if data_folder is not None or command is not None
            else None
        )
    )
    qual = dict(qualification) if qualification is not None else bridge_qualification()
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=len(decks),
        seat=1,
        scenario_id=f"studio-game-{game_id}",
        seed=seed,
        xmage_commit=pin,
        bridge_version=BRIDGE_VERSION,
        pilot_identity=PILOT_IDENTITY,
        pilot_version=PILOT_VERSION,
        decision_policy_version=POLICY_VERSION,
    )
    seat_details = []
    pilots_list = []
    for seat, deck in enumerate(decks, start=1):
        seat_style = (seat_styles or {}).get(seat, style if style is not None else 0.5)
        plan = derive_deck_plan(deck)
        seat_details.append((deck, seat_style, plan))
        pilots_list.append(
            FullGamePilotBinding(
                seat=seat,
                deck_id=deck.deck_id,
                strategy=strategy,
                commander_names=deck.commander_names,
                config=PilotConfig(
                    pilot_name="auto",
                    strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                    mode=PilotDecisionMode.DETERMINISTIC,
                    style=seat_style,
                    weights=style_weights(seat_style),
                    reserve_mana_target=style_reserve_mana(seat_style),
                    deck_plan=plan.as_dict(),
                ),
                pilot_identity=PILOT_IDENTITY,
                pilot_version=PILOT_VERSION,
                decision_policy_version=POLICY_VERSION,
            )
        )
    qual_state = qual.get("status")
    header: dict[str, object] = {
        "seed": seed,
        "engine_commit": pin,
        "bridge_jar_sha256": resolved_sha,
        "bridge_qualification_state": qual_state,
        "covered_by_sealed_epoch": covered_by_sealed_epoch(
            qual_state, resolved_sha, qual.get("covered_by_sealed_epoch", False)
        ),
        "bridge_sealed_epoch": qual.get("sealed_epoch"),
        "pilot": f"{PILOT_IDENTITY} {PILOT_VERSION}",
        "decision_policy": POLICY_VERSION,
        "strategy": strategy,
        "seats": [
            {
                "seat": index,
                "deck_id": deck.deck_id,
                "commanders": list(deck.commander_names),
                "pilot": "Mensch" if index in human_set else "KI",
                "style": s_style,
                "style_name": style_label(s_style),
                "deck_plan": s_plan.as_dict(),
            }
            for index, (deck, s_style, s_plan) in enumerate(seat_details)
        ],
    }
    if human_set or decision_timeout_seconds != 120:
        header["human_seats"] = human_set
        header["decision_timeout_seconds"] = int(decision_timeout_seconds)
    return PreparedGame(game_id, scenario, decks, tuple(pilots_list), header)


def covered_by_sealed_epoch(qual_state: object, bridge_sha: object, covered_flag: object) -> bool:
    """True only when qualification aligns with the sealed epoch and a jar SHA-256 is recorded."""
    return (
        bool(covered_flag)
        and qual_state == BRIDGE_ALIGNED
        and isinstance(bridge_sha, str)
        and bool(bridge_sha.strip())
    )


def close_recorded_game(
    recorder: GameRecorder, outcome: FullGameConformanceResult | Exception
) -> dict[str, object]:
    """Write the closing entry of a game log from its outcome and return the short summary."""
    header = getattr(recorder, "header", {})
    bridge_sha = header.get("bridge_jar_sha256")
    qual_state = header.get("bridge_qualification_state")
    covered = covered_by_sealed_epoch(
        qual_state, bridge_sha, header.get("covered_by_sealed_epoch", False)
    )
    if isinstance(outcome, Exception):
        # run() is behind the public error boundary, so its message carries only a fixed
        # site and audited codes (failure_privacy); it says why the game did not start.
        failure = {
            "status": "failed",
            "failure_class": public_exception_type(outcome),
            "failure_message": public_full_game_exception_message(outcome),
            "bridge_jar_sha256": bridge_sha,
            "bridge_qualification_state": qual_state,
            "covered_by_sealed_epoch": covered,
        }
        path = recorder.close(failure)
        return {
            "game_id": recorder.game_id,
            **failure,
            "frames": recorder.frames,
            "log": str(path),
        }
    # the engine counts seats from 1 in its outcome, the board frames count from 0
    winners = [seat - 1 for seat in outcome.winner_seats]
    payload = getattr(outcome, "result_payload", None)
    raw_skipped = (
        payload.get("forced_decisions_skipped", 0)
        if isinstance(payload, Mapping)
        else getattr(outcome, "forced_decisions_skipped", 0)
    )
    forced_skipped = int(raw_skipped) if isinstance(raw_skipped, (int, float)) else 0
    closing: dict[str, object] = {
        "status": "finished",
        "winner_seats": winners,
        "decision_count": outcome.decision_count,
        "forced_decisions_skipped": forced_skipped,
        "engine_version": outcome.engine_version,
        "semantic_transcript_sha256": outcome.semantic_transcript_sha256,
        "bridge_jar_sha256": bridge_sha,
        "bridge_qualification_state": qual_state,
        "covered_by_sealed_epoch": covered,
    }
    path = recorder.close(closing)
    return {
        "game_id": recorder.game_id,
        "status": "finished",
        "winner_seats": winners,
        "decision_count": outcome.decision_count,
        "forced_decisions_skipped": forced_skipped,
        "frames": recorder.frames,
        "log": str(path),
        "bridge_jar_sha256": bridge_sha,
        "bridge_qualification_state": qual_state,
        "covered_by_sealed_epoch": covered,
    }


def play_recorded_game(
    data_folder: str | Path,
    deck_paths: list[Path],
    *,
    seed: int,
    game_id: str | None = None,
    strategy: str = "generic",
    style: float | None = None,
    seat_styles: Mapping[int, float] | None = None,
    max_decisions: int = 50_000,
    request_timeout_seconds: float = 120.0,
) -> dict[str, object]:
    """Play one game on the configured engine and write its log. Returns a short summary.

    The engine start command comes from the environment as for every full game of the Lab,
    or from the engine file in the Studio data folder.
    A game that fails keeps its log up to the failure, with the public failure class.
    """
    decks = load_decks(deck_paths)
    game = game_id or free_game_id(data_folder, f"{decks[0].deck_id}-{len(decks)}p-seed{seed}")
    cmd = engine_command(data_folder)
    sha = bridge_jar_sha256(data_folder, cmd)
    prepared = prepare_game(
        decks,
        seed=seed,
        game_id=game,
        strategy=strategy,
        style=style,
        seat_styles=seat_styles,
        data_folder=data_folder,
        command=cmd,
        jar_sha256=sha,
    )
    recorder = GameRecorder(data_folder, game, prepared.header)
    runner = _RecordingRunner(
        command=cmd,
        max_decisions=max_decisions,
        request_timeout_seconds=request_timeout_seconds,
    )
    runner.recorder = recorder
    try:
        result = runner.run(scenario=prepared.scenario, decks=decks, pilots=prepared.pilots)
    except Exception as error:
        return close_recorded_game(recorder, error)
    return close_recorded_game(recorder, result)


class _InteractiveCommand:
    """Single command passed from FastAPI request threads to the engine loop thread."""

    def __init__(self, kind: str, payload: object = None) -> None:
        self.kind = kind
        self.payload = payload
        self.done = threading.Event()
        self.result: dict[str, object] | None = None
        self.error: Exception | None = None

    def resolve(self, value: dict[str, object]) -> None:
        self.result = value
        self.done.set()

    def reject(self, error: Exception) -> None:
        self.error = error
        self.done.set()


class InteractiveGameSession:
    """Manages one live XMage full-game session with one or more human seats.

    Only the session's background thread speaks to ``_RawFullGameClient`` so pipe
    request/response ordering cannot race; HTTP endpoints enqueue decision or
    concede commands and read strictly principal-scoped snapshots.
    """

    def __init__(
        self,
        data_folder: str | Path,
        prepared: PreparedGame,
        *,
        human_seats: Sequence[int],
        decision_timeout_seconds: int = 0,
        ai_delay_ms: int = 250,
        max_decisions: int = 50_000,
        command: Sequence[str] | None = None,
        client_factory: Callable[..., object] | None = None,
    ) -> None:
        self.data_folder = Path(data_folder)
        self.prepared = prepared
        self.game_id = prepared.game_id
        self.human_seats: frozenset[int] = frozenset(int(s) for s in human_seats)
        if not self.human_seats:
            raise ValueError("interactive session requires at least one human seat")
        self.decision_timeout_seconds = int(decision_timeout_seconds)
        self.ai_delay_ms = max(0, min(5_000, int(ai_delay_ms)))
        self.max_decisions = max_decisions
        self._command = tuple(command) if command is not None else None
        self._client_factory = client_factory
        self._recorder = GameRecorder(data_folder, self.game_id, prepared.header)
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._commands: queue.Queue[_InteractiveCommand] = queue.Queue()
        self._frames: list[dict[str, object]] = []
        self._pending_decision: dict[str, object] | None = None
        self._pending_raw_decision: dict[str, object] | None = None
        self._player_ids_by_seat: dict[int, str] = {}
        self._can_concede_by_seat: dict[int, bool] = {}
        self._running = True
        self._result: dict[str, object] | None = None
        self._thread = threading.Thread(
            target=self._run,
            name=f"interactive-play-{self.game_id}",
            daemon=True,
        )

    def start(self, *, wait_seconds: float = 15.0) -> None:
        self._thread.start()
        self._ready.wait(timeout=wait_seconds)

    def _build_client(self, runner: XmageFullGameRunner) -> object:
        ipc_timeout = (
            max(120.0, float(self.decision_timeout_seconds) + 60.0)
            if self.decision_timeout_seconds > 0
            else 3_600.0
        )
        if self._client_factory is not None:
            return self._client_factory(
                runner.command,
                cwd=runner.cwd,
                request_timeout_seconds=ipc_timeout,
            )
        if runner.command is None:
            raise RuntimeError("no bridge command configured for interactive play")
        return _RawFullGameClient(
            runner.command,
            cwd=runner.cwd,
            request_timeout_seconds=ipc_timeout,
        )

    def _update_outcomes_locked(self, status: Mapping[str, object]) -> None:
        outcomes = status.get("outcomes")
        if isinstance(outcomes, list):
            for entry in outcomes:
                if not isinstance(entry, Mapping):
                    continue
                seat = entry.get("seat")
                pid = entry.get("player_id")
                if type(seat) is int and isinstance(pid, str) and pid:
                    self._player_ids_by_seat[seat] = pid
                    self._can_concede_by_seat[seat] = bool(entry.get("can_concede"))

    def _sanitize_decision(self, decision: Mapping[str, object]) -> dict[str, object]:
        sanitized: dict[str, object] = {
            "decision_id": decision.get("decision_id"),
            "actor_id": decision.get("actor_id"),
            "seat": decision.get("seat"),
            "acting_for_seat": decision.get("acting_for_seat"),
            "decision_class": decision.get("decision_class"),
            "prompt": decision.get("prompt"),
            "minimum_selections": decision.get("minimum_selections"),
            "maximum_selections": decision.get("maximum_selections"),
            "legal_options": copy.deepcopy(decision.get("legal_options") or []),
            "context": copy.deepcopy(decision.get("context") or {}),
            "source_object": copy.deepcopy(decision.get("source_object")),
        }
        raw_state = decision.get("pilot_state")
        if isinstance(raw_state, Mapping):
            sanitized["pilot_state"] = redact_pilot_state_for_human_seats(
                raw_state, self.human_seats
            )
        seat = decision.get("seat")
        actor_id = decision.get("actor_id")
        if type(seat) is int and isinstance(actor_id, str) and actor_id:
            self._player_ids_by_seat[seat] = actor_id
        return sanitized

    def _publish_status(self, status: Mapping[str, object], client: object) -> None:
        decision = status.get("decision")
        with self._lock:
            self._update_outcomes_locked(status)
            if isinstance(decision, Mapping):
                seat = decision.get("seat")
                if type(seat) is int and seat in self.human_seats:
                    sanitized = self._sanitize_decision(decision)
                    actor_id = decision.get("actor_id")
                    if (
                        isinstance(actor_id, str)
                        and actor_id
                        and seat not in self._can_concede_by_seat
                        and hasattr(client, "request")
                    ):
                        with contextlib.suppress(Exception):
                            offer = client.request("get_concede_offer", {"player_id": actor_id})
                            if isinstance(offer, Mapping):
                                self._can_concede_by_seat[seat] = bool(offer.get("can_concede"))
                    sanitized["can_concede"] = any(
                        self._can_concede_by_seat.get(s, False) for s in self.human_seats
                    )
                    self._pending_decision = sanitized
                    self._pending_raw_decision = copy.deepcopy(dict(decision))
                else:
                    self._pending_decision = None
                    self._pending_raw_decision = None
            else:
                self._pending_decision = None
                self._pending_raw_decision = None
        self._ready.set()

    def _record_decision(
        self, decision: Mapping[str, object], response: Mapping[str, object]
    ) -> None:
        self._recorder.record(decision, response)
        redacted = redact_frame_for_human_seats(
            frame_of(self._recorder.frames, decision, response),
            self.human_seats,
        )
        with self._lock:
            self._frames.append(redacted)
            self._pending_decision = None
            self._pending_raw_decision = None

    def _run_concede_command(
        self, client: object, cmd: _InteractiveCommand, current_status: dict[str, object]
    ) -> dict[str, object]:
        seat_arg = cmd.payload
        seat = int(seat_arg) if type(seat_arg) is int else min(self.human_seats)
        if seat not in self.human_seats:
            cmd.reject(ValueError(f"seat {seat} is not a human seat"))
            return current_status
        with self._lock:
            actor_id = self._player_ids_by_seat.get(seat)
        if not actor_id:
            cmd.reject(RuntimeError("concede unavailable before player identity is known"))
            return current_status
        try:
            offer = client.request("get_concede_offer", {"player_id": actor_id})  # type: ignore[attr-defined]
            if not isinstance(offer, Mapping) or not offer.get("can_concede"):
                raise ValueError("Aufgeben ist für diesen Platz derzeit nicht möglich")
            next_status = client.request(  # type: ignore[attr-defined]
                "submit_concede",
                {"proposal": {"actor_id": actor_id, "player_id": actor_id}},
            )
            if not isinstance(next_status, dict):
                raise RuntimeError("invalid submit_concede response")
            self._publish_status(next_status, client)
            cmd.resolve({"conceded": True, "seat": seat})
            return next_status
        except Exception as exc:
            cmd.reject(exc)
            return current_status

    def _run(self) -> None:
        outcome: FullGameConformanceResult | Exception | None = None
        try:
            runner = XmageFullGameRunner(
                command=self._command,
                max_decisions=self.max_decisions,
            )
            policy = runner._validated_policy(
                self.prepared.scenario,
                self.prepared.decks,
                self.prepared.pilots,
            )
            client = self._build_client(runner)
            with client:  # type: ignore[attr-defined]
                started = client.request("start_engine")  # type: ignore[attr-defined]
                if started.get("lane") != FULL_GAME_LANE:
                    raise FullGameConformanceError("bridge did not enter explicit full-game lane")
                provider = client.request("get_provider_version")  # type: ignore[attr-defined]
                capabilities = client.request("get_capabilities")  # type: ignore[attr-defined]
                runner._validate_handshake(self.prepared.scenario, provider, capabilities)

                handles: list[str] = []
                for deck in self.prepared.decks:
                    imported = client.request(  # type: ignore[attr-defined]
                        "import_deck", {"deck": runner._deck_payload(deck)}
                    )
                    handle = imported.get("deck_handle")
                    if not isinstance(handle, dict):
                        raise FullGameConformanceError("IMPORT_DECK returned no deck_handle")
                    handle_id = str(handle.get("handle_id", "")).strip()
                    if not handle_id:
                        raise FullGameConformanceError("IMPORT_DECK returned blank handle_id")
                    handles.append(handle_id)

                game_wire_id = (
                    f"{self.prepared.scenario.scenario_id}:"
                    f"{self.prepared.scenario.candidate_id}:"
                    f"{self.prepared.scenario.seed}"
                )
                player_count = self.prepared.scenario.player_count
                created = client.request(  # type: ignore[attr-defined]
                    "create_full_game",
                    {
                        "game_id": game_wire_id,
                        "deck_handles": handles,
                        "seed": self.prepared.scenario.seed,
                        "starting_player_seat": self.prepared.scenario.seed % player_count,
                        "starting_life": 40,
                        "human_seats": sorted(self.human_seats),
                        "decision_timeout_seconds": self.decision_timeout_seconds,
                    },
                )
                if created.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
                    raise FullGameConformanceError(
                        "full-game creation returned unsafe evidence class"
                    )
                if created.get("holdout_consumed") is not False:
                    raise FullGameConformanceError("technical conformance must not consume holdout")

                status = client.request("start_full_game")  # type: ignore[attr-defined]
                self._publish_status(status, client)
                decision_count = 0
                shutdown_requested = False

                while not shutdown_requested:
                    failure = status.get("failure")
                    if isinstance(failure, dict):
                        raise FullGameConformanceError("XMage full-game engine failed")
                    decision = status.get("decision")
                    if isinstance(decision, dict):
                        decision_count += 1
                        if decision_count > self.max_decisions:
                            raise FullGameProtocolError(
                                f"full-game exceeded max_decisions={self.max_decisions}",
                                code="ENGINE_FAILURE",
                            )
                        seat = decision.get("seat")
                        if type(seat) is int and seat in self.human_seats:
                            # Park on command queue until human answers, concedes, or shuts down.
                            while True:
                                cmd = self._commands.get()
                                if cmd.kind == "shutdown":
                                    shutdown_requested = True
                                    cmd.resolve({"shut_down": True})
                                    break
                                if cmd.kind == "concede":
                                    status = self._run_concede_command(client, cmd, status)
                                    break
                                if cmd.kind == "decision":
                                    response_payload = cmd.payload
                                    if not isinstance(response_payload, Mapping):
                                        cmd.reject(ValueError("response payload must be a dict"))
                                        continue
                                    try:
                                        next_status = client.request(  # type: ignore[attr-defined]
                                            "submit_full_game_decision",
                                            {"response": dict(response_payload)},
                                        )
                                    except FullGameProtocolError as exc:
                                        if (
                                            exc.code == "BRIDGE_ERROR"
                                            and getattr(client, "_transport_failure", None) is None
                                        ):
                                            cmd.reject(ValueError(str(exc)))
                                            continue
                                        cmd.reject(exc)
                                        raise
                                    self._record_decision(decision, response_payload)
                                    status = next_status
                                    self._publish_status(status, client)
                                    cmd.resolve({"accepted": True})
                                    break
                            continue

                        # AI seat: allow responsive concede/shutdown during delay.
                        delay = max(0.0, float(self.ai_delay_ms) / 1000.0)
                        ai_cmd: _InteractiveCommand | None
                        try:
                            ai_cmd = self._commands.get(timeout=delay)
                        except queue.Empty:
                            ai_cmd = None
                        if ai_cmd is not None:
                            if ai_cmd.kind == "shutdown":
                                shutdown_requested = True
                                ai_cmd.resolve({"shut_down": True})
                                break
                            if ai_cmd.kind == "concede":
                                status = self._run_concede_command(client, ai_cmd, status)
                                continue
                            ai_cmd.reject(ValueError("no human decision currently pending"))
                        response = policy.decide(decision)
                        next_status = client.request(  # type: ignore[attr-defined]
                            "submit_full_game_decision",
                            {"response": response},
                        )
                        self._record_decision(decision, response)
                        status = next_status
                        self._publish_status(status, client)
                        continue

                    if bool(status.get("terminal")):
                        break
                    status = client.request("get_full_game_decision")  # type: ignore[attr-defined]
                    self._publish_status(status, client)

                if shutdown_requested:
                    outcome = FullGameConformanceError("Spiel durch Benutzer beendet")
                else:
                    raw_result = client.request("get_full_game_result")  # type: ignore[attr-defined]
                    with contextlib.suppress(Exception):
                        raw_log = client.request("export_event_log")  # type: ignore[attr-defined]
                        if isinstance(raw_log, dict):
                            self._recorder.save_event_log(raw_log.get("events"))
                    outcome = XmageFullGameRunner._build_result(
                        self.prepared.scenario,
                        provider,
                        raw_result,
                        shutdown_disposition="graceful_shutdown",
                    )
        except Exception as exc:
            outcome = exc
        finally:
            if outcome is None:
                outcome = FullGameConformanceError("full game ended without outcome")
            closed = close_recorded_game(self._recorder, outcome)
            with self._lock:
                self._pending_decision = None
                self._pending_raw_decision = None
                self._running = False
                self._result = closed
            self._ready.set()

    def snapshot(self, *, start: int = 0, count: int = 200) -> dict[str, object]:
        with self._lock:
            sliced = [copy.deepcopy(frame) for frame in self._frames[start : start + count]]
            pending = copy.deepcopy(self._pending_decision)
            if isinstance(pending, dict):
                raw_state = pending.get("pilot_state")
                if isinstance(raw_state, Mapping):
                    pending["pilot_state"] = redact_pilot_state_for_human_seats(
                        raw_state, self.human_seats
                    )
            return {
                "game_id": self.game_id,
                "interactive": True,
                "running": self._running,
                "header": copy.deepcopy(self.prepared.header),
                "human_seats": sorted(self.human_seats),
                "decision_timeout_seconds": self.decision_timeout_seconds,
                "ai_delay_ms": self.ai_delay_ms,
                "can_concede": any(
                    self._can_concede_by_seat.get(s, False) for s in self.human_seats
                )
                and self._running,
                "pending_decision": pending,
                "frames": sliced,
                "start": start,
                "total": len(self._frames),
                "result": copy.deepcopy(self._result),
            }

    def submit_decision(self, payload: Mapping[str, object]) -> dict[str, object]:
        with self._lock:
            if not self._running:
                raise RuntimeError("die Partie ist bereits beendet")
            pending = self._pending_raw_decision
            if pending is None:
                raise RuntimeError("derzeit liegt keine offene Entscheidung für dich vor")
            expected_decision_id = str(pending.get("decision_id") or "")
            expected_actor_id = str(pending.get("actor_id") or "")
            raw_legal = pending.get("legal_options")
            legal_items = raw_legal if isinstance(raw_legal, list) else []
            legal_ids = {
                str(opt.get("option_id"))
                for opt in legal_items
                if isinstance(opt, Mapping) and opt.get("option_id") is not None
            }
        decision_id = str(payload.get("decision_id") or "").strip()
        if not decision_id or decision_id != expected_decision_id:
            raise ValueError("Entscheidung ist veraltet (decision_id stimmt nicht)")
        raw_selected = payload.get("selected_option_ids") or []
        raw_ordering = payload.get("ordering") or []
        if not isinstance(raw_selected, list) or not isinstance(raw_ordering, list):
            raise ValueError("selected_option_ids und ordering müssen Listen sein")
        selected = [str(item) for item in raw_selected]
        ordering = [str(item) for item in raw_ordering]
        for opt_id in [*selected, *ordering]:
            if opt_id not in legal_ids:
                raise ValueError(f"illegale Option (nicht von XMage angeboten): {opt_id}")
        response: dict[str, object] = {
            "decision_id": expected_decision_id,
            "actor_id": expected_actor_id,
            "selected_option_ids": selected,
            "ordering": ordering,
        }
        if payload.get("numeric_choice") is not None:
            response["numeric_choice"] = payload.get("numeric_choice")
        if payload.get("numeric_choices") is not None:
            response["numeric_choices"] = payload.get("numeric_choices")

        cmd = _InteractiveCommand("decision", response)
        self._commands.put(cmd)
        if not cmd.done.wait(timeout=35.0):
            raise TimeoutError("Engine-Antwort hat zu lange gedauert")
        if cmd.error is not None:
            raise cmd.error
        return cmd.result or {"accepted": True}

    def concede(self, seat: int | None = None) -> dict[str, object]:
        with self._lock:
            if not self._running:
                raise RuntimeError("die Partie ist bereits beendet")
        cmd = _InteractiveCommand("concede", seat)
        self._commands.put(cmd)
        if not cmd.done.wait(timeout=15.0):
            raise TimeoutError("Aufgeben hat zu lange gedauert")
        if cmd.error is not None:
            raise cmd.error
        return cmd.result or {"conceded": True}

    def set_speed(self, ai_delay_ms: int) -> int:
        clamped = max(0, min(5_000, int(ai_delay_ms)))
        self.ai_delay_ms = clamped
        return clamped

    def shutdown(self) -> None:
        if not self._running:
            return
        cmd = _InteractiveCommand("shutdown")
        self._commands.put(cmd)
        cmd.done.wait(timeout=10.0)
        self._thread.join(timeout=5.0)


class InteractivePlayManager:
    """Registry of active/recent interactive human-seat games hosted by the Studio."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, InteractiveGameSession] = {}

    def start_game(
        self,
        data_folder: str | Path,
        deck_paths: list[Path],
        *,
        seed: int,
        human_seats: Sequence[int],
        decision_timeout_seconds: int = 0,
        ai_delay_ms: int = 250,
        game_id: str | None = None,
        strategy: str = "generic",
        style: float | None = None,
        seat_styles: Mapping[int, float] | None = None,
        max_decisions: int = 50_000,
        client_factory: Callable[..., object] | None = None,
    ) -> dict[str, object]:
        decks = load_decks(deck_paths)
        resolved_id = game_id or free_game_id(
            data_folder, f"{decks[0].deck_id}-{len(decks)}p-seed{seed}"
        )
        cmd = engine_command(data_folder)
        sha = bridge_jar_sha256(data_folder, cmd)
        prepared = prepare_game(
            decks,
            seed=seed,
            game_id=resolved_id,
            strategy=strategy,
            style=style,
            seat_styles=seat_styles,
            human_seats=human_seats,
            decision_timeout_seconds=decision_timeout_seconds,
            data_folder=data_folder,
            command=cmd,
            jar_sha256=sha,
        )
        session = InteractiveGameSession(
            data_folder,
            prepared,
            human_seats=human_seats,
            decision_timeout_seconds=decision_timeout_seconds,
            ai_delay_ms=ai_delay_ms,
            max_decisions=max_decisions,
            command=cmd,
            client_factory=client_factory,
        )
        with self._lock:
            self._sessions[resolved_id] = session
        session.start()
        return {
            "game_id": resolved_id,
            "interactive": True,
            "human_seats": sorted(session.human_seats),
            "decision_timeout_seconds": session.decision_timeout_seconds,
        }

    def get(self, game_id: str) -> InteractiveGameSession | None:
        with self._lock:
            return self._sessions.get(game_id)

    def snapshot(
        self,
        data_folder: str | Path,
        game_id: str,
        *,
        start: int = 0,
        count: int = 200,
    ) -> dict[str, object]:
        session = self.get(game_id)
        if session is not None:
            return session.snapshot(start=start, count=count)
        from .games import read_game

        recorded = read_game(data_folder, game_id, start=start, count=count)
        header = recorded.get("header")
        human_list = (
            [int(s) for s in header.get("human_seats", []) if type(s) is int]
            if isinstance(header, Mapping) and isinstance(header.get("human_seats"), list)
            else []
        )
        human_set = frozenset(human_list)
        raw_frames = recorded.get("frames")
        frame_items = raw_frames if isinstance(raw_frames, list) else []
        if human_set:
            frames: list[dict[str, object]] = [
                redact_frame_for_human_seats(f, human_set)
                for f in frame_items
                if isinstance(f, Mapping)
            ]
        else:
            frames = [dict(f) for f in frame_items if isinstance(f, Mapping)]
        return {
            "game_id": game_id,
            "interactive": bool(human_set),
            "running": recorded.get("running", False),
            "header": header,
            "human_seats": human_list,
            "decision_timeout_seconds": (
                header.get("decision_timeout_seconds", 120) if isinstance(header, Mapping) else 120
            ),
            "ai_delay_ms": 0,
            "can_concede": False,
            "pending_decision": None,
            "frames": frames,
            "start": recorded.get("start", start),
            "total": recorded.get("total", 0),
            "result": recorded.get("result"),
        }

    def shutdown_game(self, game_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(game_id, None)
        if session is not None:
            session.shutdown()

    def shutdown_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.shutdown()
