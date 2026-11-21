"""Play one simulated game with the rules engine and record it for the Studio viewer.

The existing full-game runner does all the work: XMage decides every rule, the Lab's pilots
decide every choice. This module only chooses decks and a seed, lets the runner play, and has
the recorder of ``games.py`` write down what happened. A game with human seats
(``InteractiveGameSession``) plays through the runner's public steps (``FullGameMatch``): the
human seat is a game whose decisions come from outside.
"""

from __future__ import annotations

import contextlib
import copy
import json
import queue
import threading
import time
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
    machine_codes,
    public_exception_type,
    public_full_game_exception_message,
    redacted_summary,
)
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGameBridgeClient,
    FullGameBridgeSession,
    FullGameCancelled,
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGameMatch,
    FullGamePilotBinding,
    FullGameProtocolError,
    ProgressEntry,
    XmageFullGameRunner,
)
from commander_lab.engine.rules.full_game_series import FullGameSeriesResult
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin
from commander_lab.storage import sha256_value

from .games import (
    HUMAN_PILOT_LABEL,
    DecisionPolicy,
    GameRecorder,
    RecordingPolicy,
    free_game_id,
    redact_frame_for_human_seats,
    redact_pilot_state_for_human_seats,
)
from .launch import bridge_jar_sha256, engine_command, interactive_bridge_command
from .pilot_fingerprint import pilot_fingerprint

PILOT_IDENTITY = "GenericCommanderPilot"
PILOT_VERSION = "1.0.0"
POLICY_VERSION = "xmage-full-game-policy-1.0.0"
BRIDGE_VERSION = "xmage-engine-bridge-0.1.0-SNAPSHOT"

# Owner decision 2026-11-17: in PLAY a human waits without limit; no timeout ends the game. Every
# start path with a human seat therefore hands the bridge the explicit value 0 (unlimited); the
# bridge default of 120 s must never apply to a human seat.
HUMAN_SEAT_TIMEOUT_SECONDS = 0
_HUMAN_TIMEOUT_MESSAGE = (
    "Im PLAY gibt es kein Zeitlimit: decision_timeout_seconds muss 0 (unbegrenzt) sein, "
    "ein Mensch wartet unbegrenzt und kein Zeitlimit beendet die Partie"
)
# While the loop waits for the human it looks at the bridge process this often, so a dead
# bridge ends the game as failed instead of leaving the page waiting for ever.
_PARK_POLL_SECONDS = 2.0
# How long one request to the bridge of an interactive game may take; the human's own thinking
# time is not in it (the engine waits for the human without limit, the loop parks instead).
_INTERACTIVE_REQUEST_TIMEOUT_SECONDS = 3_600.0
DEFAULT_AI_DELAY_MS = 250
_AI_DELAY_SLICE_SECONDS = 0.05
# Longest time one state request may be held open waiting for a change (#1593). Short on purpose:
# the page asks again at once, and a server shutdown waits for held requests.
MAX_LONG_POLL_SECONDS = 8.0


def _is_numeric_choice_decision(
    decision: Mapping[str, object], response: Mapping[str, object] | None
) -> bool:
    decision_class = str(decision.get("decision_class") or "")
    if decision_class in {"announce_x", "x_value", "amount", "multi_amount"}:
        return True
    context = decision.get("context")
    if isinstance(context, Mapping) and (
        context.get("numeric_min") is not None
        or context.get("numeric_max") is not None
        or isinstance(context.get("numeric_legs"), list)
    ):
        return True
    return isinstance(response, Mapping) and (
        response.get("numeric_choice") is not None or response.get("numeric_choices") is not None
    )


def _is_forced_numeric_decision(decision: Mapping[str, object]) -> bool:
    context = decision.get("context")
    if not isinstance(context, Mapping):
        return False
    legs = context.get("numeric_legs")
    if isinstance(legs, list) and legs:
        for leg in legs:
            if not isinstance(leg, Mapping):
                return False
            low = leg.get("min")
            high = leg.get("max")
            if type(low) is not int or type(high) is not int or low != high:
                return False
        return True
    low = context.get("numeric_min")
    high = context.get("numeric_max")
    return type(low) is int and type(high) is int and low == high


def _is_priority_pass(
    options: Sequence[Mapping[str, object]],
    response: Mapping[str, object] | None,
) -> bool:
    if not isinstance(response, Mapping):
        return False
    raw_selected = response.get("selected_option_ids")
    if not isinstance(raw_selected, list) or not raw_selected:
        return True
    if len(raw_selected) != 1:
        return False
    chosen_id = str(raw_selected[0])
    for option in options:
        if str(option.get("option_id")) == chosen_id:
            option_type = str(option.get("option_type") or "").strip().lower()
            label = str(option.get("label") or "").strip().lower()
            return option_type == "pass_priority" or label == "pass priority"
    return False


def should_pause_for_ai_step(
    decision: Mapping[str, object],
    response: Mapping[str, object] | None = None,
) -> bool:
    """True only for visible AI steps that should observe ``ai_delay_ms`` (#1592).

    Uses exclusively fields published by the rules engine (``decision_class``, ``legal_options``,
    ``option_type``/``label``, numeric context) and the pilot's chosen response. Forced decisions
    (at most 1 legal option) and priority passes without an action run without delay; visible
    actions (casting spells, playing lands, activating abilities, combat declarations, targets,
    multi-option mana payments, and other choices) pause.
    """
    raw_options = decision.get("legal_options")
    options = (
        [opt for opt in raw_options if isinstance(opt, Mapping)]
        if isinstance(raw_options, list)
        else []
    )
    if not options and _is_numeric_choice_decision(decision, response):
        return not _is_forced_numeric_decision(decision)
    if len(options) <= 1:
        return False
    decision_class = str(decision.get("decision_class") or "")
    return not (decision_class == "priority" and _is_priority_pass(options, response))


# Bridge errors after which the engine cannot continue: waiting for another answer is pointless.
_TERMINAL_BRIDGE_CODES = frozenset(
    {
        "BRIDGE_CLOSED",
        "BRIDGE_EXITED",
        "BRIDGE_TIMEOUT",
        "BRIDGE_UNUSABLE",
        "DECISION_TIMEOUT",
        "PLAYER_LEFT_GAME_UNSUPPORTED_DECISION",
        "XMAGE_FULL_GAME_FAILED",
    }
)


def _is_terminal_bridge_error(error: FullGameProtocolError) -> bool:
    """True when the raw bridge diagnostics already name a code after which the game is over.

    A rejected answer (illegal option, wrong timing, stale id) is not terminal: the human may
    answer again. The bridge words a decision timeout as a later ``STALE_DECISION`` on the next
    answer, so a rejection that names no such code is checked against the bridge status as well
    (``InteractiveGameSession._probe_after_rejection``).
    """
    texts = [str(item) for item in error.diagnostics]
    if "FULL_GAME_ALREADY_TERMINAL" in " ".join(texts):
        return True
    return bool(_TERMINAL_BRIDGE_CODES.intersection(machine_codes(texts)))


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


def header_pilot_fingerprint() -> str:
    """The pilot fingerprint every game log header of this code names (#1658)."""
    return pilot_fingerprint(
        policy_version=POLICY_VERSION, strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC.value
    )


def snapshot_deck_hash(path: Path) -> str | None:
    """The ``deck_hash`` a game log header names for the deck snapshot at ``path`` (#1657).

    The same hash ``load_decks`` gives the deck (its own or the one derived from its content),
    so a simulation series can record the deck state it played. A snapshot that cannot be
    loaded as a Commander deck gives ``None`` (no game can be played with it either).
    """
    try:
        return _with_hash(load_rules_deck_snapshot(path)).deck_hash
    except (OSError, ValueError, KeyError, TypeError):
        return None


def snapshot_revision_id(deck: RulesDeckInput) -> str | None:
    """The Studio revision a deck snapshot was written from (``studio_revision_id``), if any.

    A snapshot written by the deck builder (``decks.lab_snapshot``) or by a paired series names
    its revision; a precon file names none. An unreadable file or a missing or empty field is
    ``None``: the log then names no revision, it never guesses one.
    """
    if not deck.source_path:
        return None
    try:
        payload = json.loads(Path(deck.source_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = payload.get("studio_revision_id") if isinstance(payload, dict) else None
    return value if isinstance(value, str) and value.strip() else None


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

    def _drive(
        self,
        client: FullGameBridgeClient,
        policy: ExternalPilotDecisionPolicy,
        *,
        stop_after: int | None,
        stop_at_turn: int | None = None,
        progress: list[ProgressEntry] | None = None,
        stop: dict[str, object] | None = None,
    ) -> tuple[int, list[str], bool]:
        res = super()._drive(
            client,
            policy,
            stop_after=stop_after,
            stop_at_turn=stop_at_turn,
            progress=progress,
            stop=stop,
        )
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
    if human_set and decision_timeout_seconds != HUMAN_SEAT_TIMEOUT_SECONDS:
        raise ValueError(_HUMAN_TIMEOUT_MESSAGE)
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
        # The identity the mixing checks compare (B2, #1658): code and data of the pilot,
        # policy and strength; the style of each seat is in its seat header.
        "pilot_fingerprint": header_pilot_fingerprint(),
        "decision_policy": POLICY_VERSION,
        "strategy": strategy,
        "seats": [
            _seat_header(index, deck, s_style, s_plan.as_dict(), human_set)
            for index, (deck, s_style, s_plan) in enumerate(seat_details)
        ],
    }
    if human_set or decision_timeout_seconds != 120:
        header["human_seats"] = human_set
        header["decision_timeout_seconds"] = int(decision_timeout_seconds)
    return PreparedGame(game_id, scenario, decks, tuple(pilots_list), header)


def _seat_header(
    index: int,
    deck: RulesDeckInput,
    style: float,
    deck_plan: dict[str, object],
    human_set: Sequence[int],
) -> dict[str, object]:
    """One seat of the log header. ``deck_hash`` names the deck state the seat played (#1657).

    The hash is the deck's own (``load_decks`` gives every snapshot one, and the own deck's is
    the one its scenario uses) or, for a deck handed in without one, the hash ``_with_hash``
    derives from its content. ``studio_revision_id`` is written only when the snapshot names
    the Studio revision it came from. Pilot and scenario are unchanged by both fields.
    """
    row: dict[str, object] = {
        "seat": index,
        "deck_id": deck.deck_id,
        "deck_hash": _with_hash(deck).deck_hash,
    }
    revision_id = snapshot_revision_id(deck)
    if revision_id is not None:
        row["studio_revision_id"] = revision_id
    row.update(
        {
            "commanders": list(deck.commander_names),
            "pilot": HUMAN_PILOT_LABEL if index in human_set else "KI",
            "style": style,
            "style_name": style_label(style),
            "deck_plan": deck_plan,
        }
    )
    return row


def covered_by_sealed_epoch(qual_state: object, bridge_sha: object, covered_flag: object) -> bool:
    """True only when qualification aligns with the sealed epoch and a jar SHA-256 is recorded."""
    return (
        bool(covered_flag)
        and qual_state == BRIDGE_ALIGNED
        and isinstance(bridge_sha, str)
        and bool(bridge_sha.strip())
    )


def close_recorded_game(
    recorder: GameRecorder, outcome: FullGameConformanceResult | FullGameSeriesResult | Exception
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
    series_basis: dict[str, object] = {}
    if isinstance(outcome, FullGameSeriesResult):
        # a Studio series game rests on its own shutdown_game acknowledgement (Owner decision
        # E9); the log says so, with the JVM life that played it and the position in it
        series_basis = {
            "result_basis": outcome.result_basis,
            "jvm_life_id": outcome.jvm_life_id,
            "position_in_jvm": outcome.position_in_jvm,
        }
    closing.update(series_basis)
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
        **series_basis,
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

    The game is a ``FullGameMatch`` of the runner's public steps; its decisions come from outside
    (human seats) or from the pilots (AI seats), and every decision frame passes the match's
    actor-scoped hidden-information audit (fail closed). Only the session's background thread
    speaks to the bridge, so pipe request/response ordering cannot race; HTTP endpoints enqueue
    decision or concede commands and read strictly principal-scoped snapshots.
    """

    def __init__(
        self,
        data_folder: str | Path,
        prepared: PreparedGame,
        *,
        human_seats: Sequence[int],
        decision_timeout_seconds: int = 0,
        ai_delay_ms: int = DEFAULT_AI_DELAY_MS,
        max_decisions: int = 50_000,
        command: Sequence[str] | None = None,
        client_factory: Callable[..., FullGameBridgeClient] | None = None,
    ) -> None:
        self.data_folder = Path(data_folder)
        self.prepared = prepared
        self.game_id = prepared.game_id
        self.human_seats: frozenset[int] = frozenset(int(s) for s in human_seats)
        if not self.human_seats:
            raise ValueError("interactive session requires at least one human seat")
        if int(decision_timeout_seconds) != HUMAN_SEAT_TIMEOUT_SECONDS:
            raise ValueError(_HUMAN_TIMEOUT_MESSAGE)
        self.decision_timeout_seconds = HUMAN_SEAT_TIMEOUT_SECONDS
        self.ai_delay_ms = max(0, min(5_000, int(ai_delay_ms)))
        self.max_decisions = max_decisions
        self._command = tuple(command) if command is not None else None
        self._client_factory = client_factory
        self._recorder = GameRecorder(data_folder, self.game_id, prepared.header)
        self._lock = threading.Lock()
        # Wakes held state requests (#1593); shares the state lock, so a revision is only ever
        # read together with the state it describes.
        self._changed = threading.Condition(self._lock)
        self._revision = 0
        self._ready = threading.Event()
        self._commands: queue.Queue[_InteractiveCommand] = queue.Queue()
        self._frames: list[dict[str, object]] = []
        # Unredacted frames, served only once the game is over (Owner decision 2026-11-17).
        self._raw_frames: list[dict[str, object]] = []
        self._pending_decision: dict[str, object] | None = None
        self._pending_raw_decision: dict[str, object] | None = None
        self._player_ids_by_seat: dict[int, str] = {}
        self._can_concede_by_seat: dict[int, bool] = {}
        self._running = True
        self._discard_on_exit = False
        self._shutdown_event = threading.Event()
        self._active_bridge: FullGameBridgeSession | None = None
        self._result: dict[str, object] | None = None
        # Forced AI priority passes the engine answered itself (#1591), as the engine's status
        # reports them; None until the engine has said so (unknown, not zero).
        self._forced_passes_answered: int | None = None
        self._thread = threading.Thread(
            target=self._run,
            name=f"interactive-play-{self.game_id}",
            daemon=True,
        )

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self, *, wait_seconds: float = 15.0) -> None:
        self._thread.start()
        self._ready.wait(timeout=wait_seconds)

    def _notify_change(self) -> None:
        """Counts one visible state change and wakes every held state request (#1593)."""
        with self._changed:
            self._revision += 1
            self._changed.notify_all()

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

    def _publish_status(self, status: Mapping[str, object], match: object) -> None:
        decision = status.get("decision")
        with self._lock:
            self._update_outcomes_locked(status)
            answered = status.get("forced_decisions_skipped")
            if type(answered) is int and answered >= 0:
                self._forced_passes_answered = answered
            if isinstance(decision, Mapping):
                seat = decision.get("seat")
                if type(seat) is int and seat in self.human_seats:
                    sanitized = self._sanitize_decision(decision)
                    actor_id = decision.get("actor_id")
                    if (
                        isinstance(actor_id, str)
                        and actor_id
                        and seat not in self._can_concede_by_seat
                        and isinstance(match, FullGameMatch)
                    ):
                        with contextlib.suppress(Exception):
                            offer = match.concede_offer(actor_id)
                            if isinstance(offer, Mapping):
                                self._can_concede_by_seat[seat] = bool(
                                    offer.get("concede_available")
                                )
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
        self._notify_change()
        self._ready.set()

    def _record_decision(
        self, decision: Mapping[str, object], response: Mapping[str, object]
    ) -> None:
        frame = self._recorder.record(decision, response)
        redacted = redact_frame_for_human_seats(frame, self.human_seats)
        with self._lock:
            self._frames.append(redacted)
            self._raw_frames.append(frame)
            self._pending_decision = None
            self._pending_raw_decision = None
        self._notify_change()

    def _run_concede_command(
        self, match: FullGameMatch, cmd: _InteractiveCommand, current_status: dict[str, object]
    ) -> dict[str, object]:
        """Concede for a human seat. A refused concede leaves the game as it was; a frame after
        it that fails the hidden-information audit ends the game (it is never published)."""
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
            offer = match.concede_offer(actor_id)
            if not isinstance(offer, Mapping) or not offer.get("concede_available"):
                raise ValueError("Aufgeben ist für diesen Platz derzeit nicht möglich")
            next_status = match.concede(actor_id, raise_on_failure=False)
            if not isinstance(next_status, dict):
                raise RuntimeError("invalid submit_concede response")
            self._publish_status(next_status, match)
            cmd.resolve({"conceded": True, "seat": seat})
            return next_status
        except FullGameConformanceError as exc:
            cmd.reject(exc)
            raise
        except Exception as exc:
            cmd.reject(exc)
            return current_status

    def _probe_after_rejection(
        self, bridge: FullGameBridgeSession, match: FullGameMatch
    ) -> tuple[str, dict[str, object] | FullGameProtocolError | None]:
        """What the bridge says after it rejected a human answer, read from its status.

        ("failed", error): the engine failed or timed out; the game cannot go on.
        ("over", status) / ("moved", status): the game ended, or another decision is open.
        ("same", None): the same decision is still open; the human may answer again.
        Anything unreadable counts as "same" (an error is shown, the answer can be retried). A
        frame that fails the hidden-information audit raises (the game ends, fail closed).
        """
        try:
            status = match.next_decision(raise_on_failure=False)
        except FullGameProtocolError as probe_error:
            if bridge.transport_failure is not None:
                return "failed", probe_error
            return "same", None
        except FullGameConformanceError:
            raise
        except Exception:
            return "same", None
        if not isinstance(status, dict):
            return "same", None
        failure = status.get("failure")
        if isinstance(failure, dict):
            raw = ("BRIDGE_ERROR", str(failure.get("message") or "engine failure"))
            return "failed", FullGameProtocolError(
                "submit_full_game_decision failed: " + redacted_summary("BRIDGE_ERROR", raw),
                code="BRIDGE_ERROR",
                diagnostics=raw,
            )
        if bool(status.get("terminal")):
            return "over", status
        decision = status.get("decision")
        pending = self._pending_raw_decision
        if (
            isinstance(decision, dict)
            and pending is not None
            and decision.get("decision_id") != pending.get("decision_id")
        ):
            return "moved", status
        return "same", None

    def _wait_ai_delay(self, *, pause: bool = True) -> _InteractiveCommand | None:
        """Pause before a visible AI step; a concede or shutdown command ends the pause early.

        When ``pause`` is False (forced decision or priority pass), no delay is taken, but any
        already-queued concede or shutdown command is still returned immediately.
        The delay is read again every slice, so a lowered speed (fast-forward) takes effect at
        once, not only for the next AI decision.
        """
        if not pause:
            try:
                return self._commands.get_nowait()
            except queue.Empty:
                return None
        started = time.monotonic()
        while True:
            remaining = float(self.ai_delay_ms) / 1000.0 - (time.monotonic() - started)
            if remaining <= 0.0:
                try:
                    return self._commands.get_nowait()  # a queued concede or shutdown still counts
                except queue.Empty:
                    return None
            try:
                return self._commands.get(timeout=min(remaining, _AI_DELAY_SLICE_SECONDS))
            except queue.Empty:
                continue

    @staticmethod
    def _raise_if_bridge_gone(bridge: FullGameBridgeSession) -> None:
        """Fail the game when the bridge process has exited while the human is thinking."""
        if bridge.bridge_gone():
            raise FullGameProtocolError(
                "full-game bridge is gone while waiting for the human seat", code="BRIDGE_EXITED"
            )

    def _play(
        self,
        bridge: FullGameBridgeSession,
        match: FullGameMatch,
        policy: ExternalPilotDecisionPolicy,
    ) -> bool:
        """Play ``match`` until the engine reports its end; True when a shutdown stopped it.

        Human seats park on the command queue (answer, concede or shutdown), AI seats ask the
        pilots and pause only before visible steps (#1592). Every status comes from a public
        step of the match, so every decision frame is audited before it is published.
        """
        status: dict[str, object] = {}
        if not self._shutdown_event.is_set():
            status = match.start(raise_on_failure=False)
            self._publish_status(status, match)
        shutdown_requested = self._shutdown_event.is_set()

        decision_count = 0
        while not shutdown_requested and not self._shutdown_event.is_set():
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
                        try:
                            cmd = self._commands.get(timeout=_PARK_POLL_SECONDS)
                        except queue.Empty:
                            self._raise_if_bridge_gone(bridge)
                            continue
                        if cmd.kind == "shutdown":
                            shutdown_requested = True
                            cmd.resolve({"shut_down": True})
                            break
                        if cmd.kind == "concede":
                            status = self._run_concede_command(match, cmd, status)
                            if cmd.error is None:
                                break
                            continue
                        if cmd.kind == "decision":
                            response_payload = cmd.payload
                            if not isinstance(response_payload, Mapping):
                                cmd.reject(ValueError("response payload must be a dict"))
                                continue
                            try:
                                next_status = match.answer(
                                    dict(response_payload), raise_on_failure=False
                                )
                            except FullGameProtocolError as exc:
                                retryable = (
                                    exc.code == "BRIDGE_ERROR"
                                    and bridge.transport_failure is None
                                    and not _is_terminal_bridge_error(exc)
                                )
                                if not retryable:
                                    cmd.reject(exc)
                                    raise
                                try:
                                    kind, found = self._probe_after_rejection(bridge, match)
                                except FullGameConformanceError as leak:
                                    cmd.reject(leak)
                                    raise
                                if kind == "same":
                                    cmd.reject(ValueError(str(exc)))
                                    continue
                                if isinstance(found, FullGameProtocolError):
                                    cmd.reject(found)
                                    raise found from None
                                if isinstance(found, dict):
                                    # the game ended or moved on: carry on from that status
                                    status = found
                                    self._publish_status(status, match)
                                cmd.reject(ValueError("Entscheidung ist veraltet"))
                                break
                            except FullGameConformanceError as leak:
                                # the frame after the answer failed the audit: never published
                                cmd.reject(leak)
                                raise
                            self._record_decision(decision, response_payload)
                            status = next_status
                            self._publish_status(status, match)
                            cmd.resolve({"accepted": True})
                            break
                    continue

                # AI seat: choose first so only visible steps pause (#1592), while still
                # allowing responsive concede/shutdown commands on every step.
                response = policy.decide(decision)
                pause = should_pause_for_ai_step(decision, response)
                ai_cmd = self._wait_ai_delay(pause=pause)
                if ai_cmd is not None:
                    if ai_cmd.kind == "shutdown":
                        shutdown_requested = True
                        ai_cmd.resolve({"shut_down": True})
                        break
                    if ai_cmd.kind == "concede":
                        status = self._run_concede_command(match, ai_cmd, status)
                        continue
                    ai_cmd.reject(ValueError("no human decision currently pending"))
                next_status = match.answer(response, raise_on_failure=False)
                self._record_decision(decision, response)
                status = next_status
                self._publish_status(status, match)
                continue

            if bool(status.get("terminal")):
                break
            status = match.next_decision(raise_on_failure=False)
            self._publish_status(status, match)
        return shutdown_requested or self._shutdown_event.is_set()

    def _run(self) -> None:
        outcome: FullGameConformanceResult | Exception | None = None
        try:
            runner = XmageFullGameRunner(
                command=self._command,
                max_decisions=self.max_decisions,
                request_timeout_seconds=_INTERACTIVE_REQUEST_TIMEOUT_SECONDS,
            )
            policy = runner.decision_policy(
                self.prepared.scenario,
                self.prepared.decks,
                self.prepared.pilots,
            )
            bridge = runner.open_session(client_factory=self._client_factory)
            with self._lock:
                self._active_bridge = bridge
            match: FullGameMatch | None = None
            raw_result = None
            with bridge:
                try:
                    match = bridge.create_game(
                        self.prepared.scenario,
                        self.prepared.decks,
                        policy,
                        human_seats=sorted(self.human_seats),
                        decision_timeout_seconds=self.decision_timeout_seconds,
                        should_stop=self._shutdown_event.is_set,
                    )
                except FullGameCancelled:
                    match = None
                if match is not None and not self._play(bridge, match, policy):
                    raw_result = match.result()
                    with contextlib.suppress(Exception):
                        self._recorder.save_event_log(list(match.events(0).events))
            # the result rests on how the bridge process really ended (the session is closed now)
            if match is None or raw_result is None:
                outcome = FullGameConformanceError("Spiel durch Benutzer beendet")
            else:
                outcome = match.conformance_result(raw_result)
        except Exception as exc:
            outcome = exc
        finally:
            with self._lock:
                self._active_bridge = None
                discard_on_exit = self._discard_on_exit
            if discard_on_exit:
                with contextlib.suppress(Exception):
                    self._recorder.discard()
                with self._lock:
                    self._pending_decision = None
                    self._pending_raw_decision = None
                    self._running = False
            else:
                if outcome is None:
                    outcome = FullGameConformanceError("full game ended without outcome")
                closed = close_recorded_game(self._recorder, outcome)
                with self._lock:
                    self._pending_decision = None
                    self._pending_raw_decision = None
                    self._running = False
                    self._result = closed
            self._notify_change()
            self._ready.set()

    def wait_for_change(self, since: int, wait_seconds: float) -> None:
        """Holds the caller until the state moved past revision ``since`` (#1593).

        Returns at once when ``since`` is already out of date or the game is over, and after
        ``wait_seconds`` (at most ``MAX_LONG_POLL_SECONDS``) when nothing changed. It only waits;
        what the caller then reads is the ordinary, redacted snapshot.
        """
        limit = max(0.0, min(MAX_LONG_POLL_SECONDS, float(wait_seconds)))
        with self._changed:
            self._changed.wait_for(
                lambda: self._revision != since or not self._running,
                timeout=limit,
            )

    def snapshot(
        self,
        *,
        start: int = 0,
        count: int = 200,
        since: int | None = None,
        wait_seconds: float = 0.0,
    ) -> dict[str, object]:
        """The principal-scoped state of the live game, frames from ``start`` on.

        The answer shares its contents with the session (no copies, #1578): do not change it. The
        web routes serialise it outside the state lock.
        """
        if since is not None and wait_seconds > 0.0:
            self.wait_for_change(since, wait_seconds)
        with self._lock:
            # Owner decision 2026-11-17: hands of the AI seats are revealed after the game ends,
            # never while it runs. The unredacted frames are used only from the moment the game
            # has its closing result.
            revealed = not self._running and self._result is not None
            source = self._raw_frames if revealed else self._frames
            # No copies and no second redaction (#1578): everything held here is written once and
            # never changed afterwards. A frame is redacted when it is recorded
            # (``_record_decision``), a pending decision when it is published
            # (``_sanitize_decision``), and the header and the closing result are set once. The
            # only reader is the web route, which serialises the answer and changes nothing.
            sliced = source[start : start + count]
            pending = self._pending_decision
            return {
                "game_id": self.game_id,
                "interactive": True,
                "running": self._running,
                # Counts visible state changes; the page sends it back as ``since`` (#1593).
                "revision": self._revision,
                "header": self.prepared.header,
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
                "hands_revealed": revealed,
                "forced_passes_answered_by_engine": self._forced_passes_answered,
                "result": self._result,
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

    def shutdown(self, *, discard: bool = False) -> None:
        if discard:
            with self._lock:
                self._discard_on_exit = True
        self._shutdown_event.set()
        if self.is_running:
            cmd = _InteractiveCommand("shutdown")
            self._commands.put(cmd)
            if not cmd.done.wait(timeout=3.0 if discard else 10.0):
                with self._lock:
                    active_bridge = self._active_bridge
                if active_bridge is not None:
                    with contextlib.suppress(Exception):
                        active_bridge.kill()
            self._thread.join(timeout=5.0)
        if discard:
            with contextlib.suppress(Exception):
                self._recorder.discard()


class InteractivePlayManager:
    """Registry of active/recent interactive human-seat games hosted by the Studio."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, InteractiveGameSession] = {}

    def live_ids(self) -> frozenset[str]:
        with self._lock:
            return frozenset(gid for gid, session in self._sessions.items() if session.is_running)

    def start_game(
        self,
        data_folder: str | Path,
        deck_paths: list[Path],
        *,
        seed: int,
        human_seats: Sequence[int],
        decision_timeout_seconds: int = HUMAN_SEAT_TIMEOUT_SECONDS,
        ai_delay_ms: int = DEFAULT_AI_DELAY_MS,
        game_id: str | None = None,
        strategy: str = "generic",
        style: float | None = None,
        seat_styles: Mapping[int, float] | None = None,
        max_decisions: int = 50_000,
        client_factory: Callable[..., FullGameBridgeClient] | None = None,
    ) -> dict[str, object]:
        if int(decision_timeout_seconds) != HUMAN_SEAT_TIMEOUT_SECONDS:
            raise ValueError(_HUMAN_TIMEOUT_MESSAGE)
        decks = load_decks(deck_paths)
        resolved_id = game_id or free_game_id(
            data_folder, f"{decks[0].deck_id}-{len(decks)}p-seed{seed}"
        )
        # the fast JVM options of a series, the pass skipping of AI seats included (#1591)
        cmd = interactive_bridge_command(engine_command(data_folder))
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
        since: int | None = None,
        wait_seconds: float = 0.0,
    ) -> dict[str, object]:
        session = self.get(game_id)
        if session is not None:
            return session.snapshot(
                start=start, count=count, since=since, wait_seconds=wait_seconds
            )
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
        # Owner decision 2026-11-17: hands are revealed once the game has a closing result.
        revealed = bool(recorded.get("hands_revealed"))
        if human_set and not revealed:
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
                header.get(
                    "decision_timeout_seconds", HUMAN_SEAT_TIMEOUT_SECONDS if human_set else 120
                )
                if isinstance(header, Mapping)
                else 120
            ),
            "ai_delay_ms": 0,
            "can_concede": False,
            "hands_revealed": revealed,
            "pending_decision": None,
            "frames": frames,
            "start": recorded.get("start", start),
            "total": recorded.get("total", 0),
            "result": recorded.get("result"),
        }

    def shutdown_game(self, game_id: str, *, discard: bool = False) -> None:
        with self._lock:
            session = self._sessions.pop(game_id, None)
        if session is not None:
            session.shutdown(discard=discard)

    def shutdown_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.shutdown()
