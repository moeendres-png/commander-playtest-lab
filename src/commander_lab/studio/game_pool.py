"""Worker processes with long-lived bridge JVMs for the games of a Studio series (#1585).

A series used to start its bridge JVMs per look window: a window of ten pairs and four workers
became chunks of five games, every window started new JVMs, and a fresh JVM costs about 64 CPU
seconds of class loading and JIT warm-up that its first games pay for. Here each worker is a
process of its own (``python -m commander_lab.studio pool-worker``) that keeps one bridge JVM
open and plays the games it is handed one after the other, across every window, until the JVM
has played its budget of games (``-Dcommanderlab.fullGame.gamesPerJvm``, at most 56) or a game
fails. The supervisor, :class:`GamePool`, keeps a queue of games; a worker that has finished a
game takes the next one, whatever table it is for. Nothing about a game depends on which worker
plays it or at which position of its JVM: seed, decks in seat order and game id are fixed when
the games are planned, and the worker builds each game with ``play.prepare_game``, the one
function a game played alone uses.

Protocol, JSON lines. Supervisor to worker: ``{"op": "play", ...task}`` (one game in flight per
worker) and ``{"op": "retire"}``; closing the pipe also retires the worker. Worker to
supervisor: ``ready``, ``played`` (the engine has played the game to its end; a progress signal),
``done`` (the log is closed and the summary of the game is final) and ``jvm_exit`` (one JVM life
ended, with its observed way of ending), then ``bye``.

A game's result rests on the acknowledged ``shutdown_game`` of that game in its own result type
(``full_game_series.FullGameSeriesResult``, Owner decision E9); evidence and qualification lanes
do not use this module. Cancelling a series stops handing out games and lets the games already
in flight end; the logs of finished games stay.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Protocol

from .games import games_folder
from .series_record import DeterminismViolation, SeriesRecord, file_sha256
from .store import now_utc
from .table_spec import game_wall_limit_seconds

#: ``1`` (or ``true``) lets a paired series play on long-lived worker JVMs. Unset: the chunked
#: path of ``play_batch`` stays in use until the pool is measured against the real engine.
SERIES_POOL_ENV = "COMMANDER_LAB_STUDIO_SERIES_POOL"

#: A game that has been in flight this long with no answer is given up: the worker process is
#: killed and the game fails as ``TimeLimit``. Far beyond any real game (the engine's own
#: request timeouts end a hung game after two minutes); this only guards the series against a
#: worker that never answers. The limit is set per seat count in ``table_spec`` (S1, #1660);
#: this default is the four-seat value, unchanged at 1,800 s.
GAME_WALL_LIMIT_SECONDS = game_wall_limit_seconds(4)
#: How long a retiring worker may take to end its JVM cleanly before it is killed.
RETIRE_WAIT_SECONDS = 30.0
#: How long an idle worker that has ended (its tree killed, reaped) may keep its place while the
#: end of its stdout is awaited. Once the worker and its group are gone, the kernel closes their
#: ends of the pipe at once and the reader sees the end within milliseconds; the end stays away
#: only while a process outside the group (one that started a session of its own) still holds
#: the pipe. Without a limit such a worker would hold its place for good, and with one worker
#: and games waiting ``run`` would never end (#1652). A few seconds are far beyond the normal
#: delay and short against a game; the worker is then given up like one whose stdout ended.
ENDED_EOF_GRACE_SECONDS = 5.0
_POLL_SECONDS = 0.5
_STDERR_TAIL_LINES = 40
#: Windows has no process groups to signal; a worker's process tree is ended with ``taskkill``.
_WINDOWS = os.name == "nt"
_TASKKILL_WAIT_SECONDS = 30.0
_EXIT_POLL_SECONDS = 0.05


def series_pool_enabled() -> bool:
    return os.environ.get(SERIES_POOL_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


class GamePoolError(RuntimeError):
    """The pool itself cannot work (a worker does not start); not a failed game."""


@dataclass(frozen=True)
class GameTask:
    """One game, fully determined when it is planned (S1, #1660).

    Every per-seat tuple is in seat order with one entry per seat: the deck file and its
    SHA-256, the style and the pilot fingerprint of that seat. The worker checks each deck file
    and each fingerprint before the game and plays nothing on a mismatch (an infrastructure
    failure). ``game_key`` names the game for the determinism guard (``series_record``); a
    task without it or without ``jar_sha256``, or whose key its fields do not give, is refused
    by the worker (``plan_task`` never builds one). ``table`` is the canonical ``TableSpec`` and ``table_hash`` its hash, ``None``
    for a caller that has no table spec yet.
    """

    task_id: str
    seed: int
    game_id: str
    deck_paths: tuple[str, ...]
    deck_sha256: tuple[str, ...] = ()
    seat_styles: tuple[float, ...] = ()
    pilot_fingerprints: tuple[str, ...] = ()
    strategy: str = "generic"
    jar_sha256: str | None = None
    game_key: str | None = None
    table_hash: str | None = None
    table: Mapping[str, object] | None = None
    engine_pin: str | None = None
    skip_forced_decisions: bool | None = None
    round_limit: int | None = None
    #: what ``jvm_options_of`` read from the command and the environment when it was planned
    jvm_options: Mapping[str, object] | None = None

    def to_wire(self) -> dict[str, object]:
        return {
            "op": "play",
            "task_id": self.task_id,
            "seed": self.seed,
            "game_id": self.game_id,
            "deck_paths": list(self.deck_paths),
            "deck_sha256": list(self.deck_sha256),
            "seat_styles": list(self.seat_styles),
            "pilot_fingerprints": list(self.pilot_fingerprints),
            "strategy": self.strategy,
            "jar_sha256": self.jar_sha256,
            "game_key": self.game_key,
            "table_hash": self.table_hash,
            "table": dict(self.table) if self.table is not None else None,
            "engine_pin": self.engine_pin,
            "skip_forced_decisions": self.skip_forced_decisions,
            "round_limit": self.round_limit,
            "jvm_options": dict(self.jvm_options) if self.jvm_options is not None else None,
        }


GameSummary = dict[str, object]


#: The engine's mana-copy switch (``XmageFullGamePlayer``: on unless it is ``false``). It is a
#: performance change that mirrors the engine's own computation, checked by a differential test
#: of the bridge, not proven; a series that mixes both values could combine incomparable games,
#: so it is part of the game key (#1660, S1 Rest).
NESTED_COPY_SKIP_PROPERTY = "commanderlab.nestedCopySkip"
#: Environment variables the JVM reads as options before the command line (``JAVA_TOOL_OPTIONS``,
#: ``_JAVA_OPTIONS``) or the ``java`` launcher reads (``JDK_JAVA_OPTIONS``). Their text can set
#: any ``-D`` property, a Java agent or a collector, so it is not parsed: a variable that is set
#: enters the game key as the SHA-256 of its whitespace-normalised text. The text itself can name
#: machine paths and agent flags and is never written anywhere (AGENTS.md section 12): not into
#: the task on the wire, the key, the manifest or the journal. A worker inherits the environment
#: of the supervisor, which is the JVM's environment.
JVM_ENV_OPTION_NAMES = ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS")


def _jvm_property_of(command: Sequence[str] | None, name: str) -> str | None:
    """The value of ``-D<name>=`` among the JVM options of ``command``; the last one wins.

    Only the options before ``-jar`` are JVM options (what follows is an argument of the
    program), and the JVM takes the last of two equal ``-D`` options. ``None``: not set.
    """
    parts = list(command or ())
    if "-jar" in parts:
        parts = parts[: parts.index("-jar")]
    prefix = f"-D{name}="
    found: str | None = None
    for part in parts:
        if part.startswith(prefix):
            found = part[len(prefix) :]
    return found


def skip_forced_decisions_of(command: Sequence[str] | None) -> bool | None:
    """The forced-pass switch a bridge command sets; ``None`` when it does not set it."""
    from .launch import SKIP_FORCED_DECISIONS_PROPERTY

    value = _jvm_property_of(command, SKIP_FORCED_DECISIONS_PROPERTY)
    # the bridge reads it with ``Boolean.getBoolean``: "true" in any case, nothing trimmed
    return None if value is None else value.lower() == "true"


def jvm_env_digest(text: str) -> str:
    """SHA-256 of a JVM option variable's text with its white space normalised."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def jvm_options_of(
    command: Sequence[str] | None, env: Mapping[str, str] | None = None
) -> dict[str, object]:
    """What besides the forced-pass switch can change a game on this JVM (``game_key``).

    ``nested_copy_skip``: the mana-copy switch of the command, ``None`` when it does not set it
    (exactly ``false`` is the only value that turns it off, as in the bridge). ``env_options``: each JVM
    option variable of ``env`` (default: the process environment) that is set and not blank,
    name -> ``jvm_env_digest`` of its text (the text itself is never kept). Not read, on purpose (see ``series_record``): ``gamesPerJvm``, heap size,
    collector and AppCDS archive.
    """
    environment = os.environ if env is None else env
    raw = _jvm_property_of(command, NESTED_COPY_SKIP_PROPERTY)
    # the bridge: on unless the text is exactly "false" (no trimming, case matters)
    nested = None if raw is None else raw != "false"
    options = {
        name: jvm_env_digest(environment[name])
        for name in JVM_ENV_OPTION_NAMES
        if environment.get(name, "").strip()
    }
    return {"nested_copy_skip": nested, "env_options": options}


def plan_task(
    *,
    task_id: str,
    seed: int,
    game_id: str,
    deck_paths: Sequence[str],
    seat_styles: Sequence[float],
    jar_sha256: str | None,
    engine_pin: str | None,
    skip_forced_decisions: bool | None,
    jvm_options: Mapping[str, object],
    strategy: str = "generic",
    round_limit: int | None = None,
    table: Mapping[str, object] | None = None,
    table_hash: str | None = None,
    deck_hashes: dict[str, str] | None = None,
) -> GameTask:
    """A complete task: deck hashes, seat pilots and ``game_key`` from its inputs (S1, #1660).

    ``deck_hashes`` caches file hashes by path across the tasks of a series. Without a bridge
    JAR or engine pin there is no task (``ValueError``): a pool game is never planned without
    the key its worker and the determinism guard check.
    """
    from .series_record import game_key

    if len(seat_styles) != len(deck_paths):
        raise ValueError("ein Stil je Sitz")
    cache = deck_hashes if deck_hashes is not None else {}
    for path in deck_paths:
        if path not in cache:
            cache[path] = file_sha256(path)
    hashes = tuple(cache[path] for path in deck_paths)
    fingerprints = tuple(seat_pilot_fingerprint(style) for style in seat_styles)
    if not jar_sha256 or not engine_pin:
        raise ValueError(
            "kein Bridge-JAR-SHA oder Engine-Pin bekannt: eine Pool-Partie wird nicht ohne "
            "Spielschlüssel geplant"
        )
    key = game_key(
        jar_sha256=jar_sha256,
        engine_pin=engine_pin,
        pilot_fingerprints=fingerprints,
        seat_styles=seat_styles,
        deck_sha256=hashes,
        seed=seed,
        strategy=strategy,
        table_options=table,
        skip_forced_decisions=skip_forced_decisions,
        round_limit=round_limit,
        jvm_options=jvm_options,
    )
    return GameTask(
        task_id=task_id,
        seed=seed,
        game_id=game_id,
        deck_paths=tuple(deck_paths),
        deck_sha256=hashes,
        seat_styles=tuple(float(style) for style in seat_styles),
        pilot_fingerprints=fingerprints,
        strategy=strategy,
        jar_sha256=jar_sha256,
        game_key=key,
        table_hash=table_hash,
        table=table,
        engine_pin=engine_pin,
        skip_forced_decisions=skip_forced_decisions,
        round_limit=round_limit,
        jvm_options=dict(jvm_options),
    )


# --------------------------------------------------------------------------------- worker side


def _emit(out: IO[str], message: Mapping[str, object]) -> None:
    out.write(json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n")
    out.flush()


class WorkerEngine(Protocol):
    """What a worker plays games with: one long-lived JVM session and the recording of games."""

    def play(self, message: Mapping[str, object], on_played: Callable[[], None]) -> GameSummary: ...

    def ended_lives(self) -> list[dict[str, object]]:
        """Every JVM life that has ended so far, in order."""
        ...

    def close(self) -> None: ...


class SessionWorkerEngine:
    """The real engine of a worker: a series session over the recording batch runner."""

    def __init__(
        self,
        data_folder: str | Path,
        *,
        label: str,
        private_card_repository: bool,
        command: tuple[str, ...] | None,
    ) -> None:
        from commander_lab.engine.rules.full_game_series import XmageFullGameSeriesSession

        from .launch import bridge_jar_sha256, engine_command
        from .play_batch import BatchRecordingRunner

        self._data_folder = data_folder
        self._command = command if command is not None else engine_command(data_folder)
        self._jar_sha = bridge_jar_sha256(data_folder, self._command)
        # the configuration this worker plays with, read once: its pin, command and environment
        self._engine_pin = own_engine_pin()
        self._environment = dict(os.environ)
        self._headers: dict[str, tuple[str, dict[str, object]]] = {}
        self._runner = BatchRecordingRunner(
            data_folder,
            self._headers,
            command=self._command,
            private_card_repository=private_card_repository,
        )
        self._session = XmageFullGameSeriesSession(self._runner, id_prefix=label)

    def play(self, message: Mapping[str, object], on_played: Callable[[], None]) -> GameSummary:
        from .play import close_recorded_game, load_decks, prepare_game

        game_id = str(message["game_id"])
        expected_jar = message.get("jar_sha256")
        if expected_jar is not None and expected_jar != self._jar_sha:
            # the supervisor planned the game (and its key) for another bridge JAR
            return refused_game_summary(
                game_id,
                "BridgeJarMismatch",
                "der Auftrag nennt einen anderen Bridge-JAR als den, den dieser Worker startet",
            )
        refused = config_refusal(
            message, engine_pin=self._engine_pin, command=self._command, env=self._environment
        )
        if refused is not None:
            return refused
        decks = load_decks([Path(str(path)) for path in _as_list(message.get("deck_paths"))])
        styles = [float(str(style)) for style in _as_list(message.get("seat_styles"))]
        prepared = prepare_game(
            decks,
            seed=int(str(message["seed"])),
            game_id=game_id,
            strategy=str(message.get("strategy") or "generic"),
            seat_styles={seat: style for seat, style in enumerate(styles, start=1)},
            data_folder=self._data_folder,
            command=self._command,
            jar_sha256=self._jar_sha,
        )
        scenario_id = prepared.scenario.scenario_id
        self._headers[scenario_id] = (prepared.game_id, prepared.header)
        self._runner.on_played = lambda _game_id: on_played()
        try:
            outcome = self._session.play(prepared.scenario, prepared.decks, prepared.pilots)
            return close_recorded_game(self._runner.recorder_of(scenario_id), outcome)
        finally:
            self._headers.pop(scenario_id, None)

    def ended_lives(self) -> list[dict[str, object]]:
        return [life.as_dict() for life in self._session.lives if life.end != "open"]

    def close(self) -> None:
        self._session.close()


EngineFactory = Callable[[], WorkerEngine]


def worker_main(
    *,
    stdin: IO[str],
    stdout: IO[str],
    label: str,
    engine_factory: EngineFactory,
) -> int:
    """Run the worker loop until ``retire`` or the end of ``stdin``; returns the exit code."""
    reported = 0
    engine: WorkerEngine | None = None

    def _report_lives() -> None:
        nonlocal reported
        if engine is None:
            return
        lives = engine.ended_lives()
        for life in lives[reported:]:
            _emit(stdout, {"ev": "jvm_exit", **life})
        reported = len(lives)

    try:
        # ``ready`` only once the engine exists: a worker whose engine cannot be built ends
        # before it is ready, and the supervisor raises ``GamePoolError`` instead of handing
        # out (and losing) one game per freshly started worker
        engine = engine_factory()
        _emit(stdout, {"ev": "ready", "pid": os.getpid(), "label": label})
        for raw in stdin:
            line = raw.strip()
            if not line:
                continue
            message = json.loads(line)
            op = message.get("op")
            if op == "retire":
                break
            if op != "play":
                continue
            task_id = str(message["task_id"])
            refused = task_refusal(message)
            summary = (
                refused
                if refused is not None
                else engine.play(message, _played_emitter(stdout, task_id))
            )
            if message.get("game_key") is not None:
                summary = {**summary, "game_key": message.get("game_key")}
            _report_lives()
            _emit(stdout, {"ev": "done", "task_id": task_id, "summary": summary})
    finally:
        if engine is not None:
            engine.close()
            _report_lives()
        _emit(stdout, {"ev": "bye"})
    return 0


def seat_pilot_fingerprint(style: float) -> str:
    """The pilot fingerprint of one seat: pilot code and data, policy, strength and style."""
    from commander_lab.models import PilotStrength

    from .pilot_fingerprint import pilot_fingerprint
    from .play import POLICY_VERSION

    return pilot_fingerprint(
        policy_version=POLICY_VERSION,
        strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC.value,
        style=style,
    )


def refused_game_summary(game_id: str, failure_class: str, message: str) -> GameSummary:
    """A game the worker did not start because its setup is wrong: infrastructure, no result."""
    return {
        "game_id": game_id,
        "status": "failed",
        "failure_class": failure_class,
        "failure_kind": "infrastructure",
        "failure_message": message,
        "log": None,
    }


def task_refusal(message: Mapping[str, object]) -> GameSummary | None:
    """Check a task before its game: every deck file against its hash, every seat's pilot.

    ``None``: the game may be played. Otherwise the summary of a game that never started
    (``failure_kind`` infrastructure): a task without one hash, style and fingerprint per seat,
    a deck file that is missing or differs from its hash, or a seat whose pilot fingerprint is
    not the one this worker's pilot code gives for that style (the supervisor planned the game
    with other pilot code).
    """
    game_id = str(message.get("game_id"))
    paths = [str(path) for path in _as_list(message.get("deck_paths"))]
    hashes = [str(value) for value in _as_list(message.get("deck_sha256"))]
    styles = _as_list(message.get("seat_styles"))
    fingerprints = [str(value) for value in _as_list(message.get("pilot_fingerprints"))]
    seats = len(paths)
    if not seats or not (len(hashes) == len(styles) == len(fingerprints) == seats):
        return refused_game_summary(
            game_id,
            "TaskIncomplete",
            "der Auftrag braucht je Sitz Deck-Hash, Stil und Pilot-Fingerabdruck",
        )
    if not message.get("jar_sha256") or not message.get("game_key"):
        # without them the worker cannot check its JAR and the guard has nothing to compare
        return refused_game_summary(
            game_id, "TaskIncomplete", "der Auftrag braucht Bridge-JAR-SHA und Spielschlüssel"
        )
    for seat, (path, expected) in enumerate(zip(paths, hashes, strict=True)):
        try:
            actual = file_sha256(path)
        except OSError:
            actual = None
        if actual != expected:
            return refused_game_summary(
                game_id,
                "DeckHashMismatch",
                f"Deck-Datei von Sitz {seat} fehlt oder weicht von ihrem Hash ab",
            )
    for seat, (style, expected) in enumerate(zip(styles, fingerprints, strict=True)):
        try:
            actual_fp: str | None = seat_pilot_fingerprint(float(str(style)))
        except ValueError:
            actual_fp = None
        if actual_fp != expected:
            return refused_game_summary(
                game_id,
                "PilotFingerprintMismatch",
                f"Pilot-Fingerabdruck von Sitz {seat} passt nicht zum Pilot-Code dieses Workers",
            )
    if task_key_of(message) != message.get("game_key"):  # recomputed, never echoed
        return refused_game_summary(
            game_id, "GameKeyMismatch", "der Spielschlüssel passt nicht zu den Angaben des Auftrags"
        )
    return None


def own_engine_pin() -> str:
    """The engine pin this worker's code runs under (``config/rules_engines.json``)."""
    from commander_lab.qualification.current_boundary.bridge_launcher import (
        canonical_xmage_engine_pin,
    )

    return canonical_xmage_engine_pin()


def config_refusal(
    message: Mapping[str, object],
    *,
    engine_pin: str,
    command: Sequence[str] | None,
    env: Mapping[str, str] | None = None,
) -> GameSummary | None:
    """Refuse a task whose pin or switches are not those this worker plays with (S1 Rest).

    ``task_refusal`` checks the task against itself (its key from its own fields). This checks the
    fields the worker cannot verify from the files alone against the worker's own configuration:
    the engine pin of its code, and from its own bridge command and environment the forced-pass
    switch, the mana-copy switch and the JVM option variables. The JAR is checked by the engine
    (``BridgeJarMismatch``). A game the supervisor planned for another configuration would carry
    a key that names a game this JVM does not play; it is never started (``GameKeyMismatch``, an
    infrastructure failure, not a result).
    """
    game_id = str(message.get("game_id"))
    own_jvm = jvm_options_of(command, env)
    mismatches = [
        text
        for text, differs in (
            ("Engine-Pin", message.get("engine_pin") != engine_pin),
            (
                "Schalter für erzwungene Pässe",
                message.get("skip_forced_decisions") != skip_forced_decisions_of(command),
            ),
            ("JVM-Optionen (Mana-Kopie, Umgebung)", message.get("jvm_options") != own_jvm),
        )
        if differs
    ]
    if not mismatches:
        return None
    return refused_game_summary(
        game_id,
        "GameKeyMismatch",
        "der Auftrag weicht von der Konfiguration dieses Workers ab: " + ", ".join(mismatches),
    )


def task_key_of(message: Mapping[str, object]) -> str | None:
    """The game key the fields of a task give; ``None`` when they give none (incomplete)."""
    from .series_record import game_key

    strategy, table = message.get("strategy"), message.get("table")
    skip, rounds = message.get("skip_forced_decisions"), message.get("round_limit")
    jvm = message.get("jvm_options")
    if not isinstance(strategy, str) or not (table is None or isinstance(table, dict)):
        return None
    if not isinstance(jvm, dict):
        return None  # a task without them is not a task this worker's key can name
    if not (skip is None or isinstance(skip, bool)) or not (rounds is None or type(rounds) is int):
        return None
    try:
        return game_key(
            jar_sha256=str(message.get("jar_sha256") or ""),
            engine_pin=str(message.get("engine_pin") or ""),
            pilot_fingerprints=[str(v) for v in _as_list(message.get("pilot_fingerprints"))],
            seat_styles=[float(str(v)) for v in _as_list(message.get("seat_styles"))],
            deck_sha256=[str(v) for v in _as_list(message.get("deck_sha256"))],
            seed=int(str(message.get("seed"))),
            strategy=strategy,
            table_options=table,
            skip_forced_decisions=skip,
            round_limit=rounds,
            jvm_options=jvm,
        )
    except ValueError:
        return None


def run_worker_process(
    data_folder: str | Path,
    *,
    label: str,
    private_card_repository: bool,
    command: tuple[str, ...] | None = None,
) -> int:
    """Entry point of ``python -m commander_lab.studio pool-worker``.

    The protocol runs over the original stdout; anything else the process prints goes to stderr.
    """
    protocol_out = sys.stdout
    sys.stdout = sys.stderr
    return worker_main(
        stdin=sys.stdin,
        stdout=protocol_out,
        label=label,
        engine_factory=lambda: SessionWorkerEngine(
            data_folder,
            label=label,
            private_card_repository=private_card_repository,
            command=command,
        ),
    )


def _played_emitter(out: IO[str], task_id: str) -> Callable[[], None]:
    def announce() -> None:
        _emit(out, {"ev": "played", "task_id": task_id})

    return announce


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


# ------------------------------------------------------------------------------ supervisor side


class _ProcessWorker:
    """One worker process and the threads that read its pipes."""

    def __init__(
        self,
        label: str,
        argv: Sequence[str],
        env: Mapping[str, str],
        events: queue.Queue[tuple[_ProcessWorker, dict[str, object] | None]],
    ) -> None:
        self.label = label
        self.ready = False
        self.task: GameTask | None = None
        self.task_started = 0.0
        self.stderr_tail: deque[str] = deque(maxlen=_STDERR_TAIL_LINES)
        self.killed = False
        self.said_bye = False
        #: found ended while idle and already killed with its tree and reaped; its queued events
        #: (``jvm_exit``, ``bye``, the end of its stdout) are still read before it is given up
        self.ended = False
        #: when it was first found ended (``time.monotonic``); the grace for its end of stdout
        #: counts from here (``ENDED_EOF_GRACE_SECONDS``)
        self.ended_at = 0.0
        # POSIX: the worker leads a process group of its own, which its bridge JVM joins (the
        # JVM is started without a session of its own), so killing the group ends both (#1584).
        # A worker started this way no longer gets the terminal's Ctrl+C; the supervisor ends it.
        self.proc = subprocess.Popen(
            list(argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(env),
            start_new_session=not _WINDOWS,
        )
        self._events = events
        self._out = threading.Thread(target=self._read_stdout, daemon=True)
        self._err = threading.Thread(target=self._read_stderr, daemon=True)
        self._out.start()
        self._err.start()

    def _read_stdout(self) -> None:
        stream = self.proc.stdout
        try:
            if stream is not None:
                for line in stream:
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(message, dict):
                        self._events.put((self, message))
        finally:
            self._events.put((self, None))

    def _read_stderr(self) -> None:
        stream = self.proc.stderr
        if stream is not None:
            for line in stream:
                self.stderr_tail.append(line.rstrip("\n"))

    def end_if_exited(self) -> bool:
        """Whether the worker process has ended; an ended worker is killed with its tree first.

        Never ``poll()`` here: reaping a worker that died on its own would leave its JVM out of
        reach of the group kill (#1652).
        """
        if self.ended:
            return True
        self.ended = reap_ended_process(self.proc, windows=_WINDOWS)
        if self.ended:
            self.ended_at = time.monotonic()
        return self.ended

    def send(self, message: Mapping[str, object]) -> bool:
        stdin = self.proc.stdin
        if stdin is None:
            return False
        try:
            stdin.write(json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n")
            stdin.flush()
        except (OSError, ValueError):
            return False
        return True

    def retire(self, wait_seconds: float) -> None:
        """Ask the worker to end its JVM and exit; kill it when it does not in time."""
        self.send({"op": "retire"})
        stdin = self.proc.stdin
        if stdin is not None:
            with contextlib.suppress(OSError, ValueError):
                stdin.close()
        if _wait_for_exit(self.proc, wait_seconds, windows=_WINDOWS):
            # ended: what it left in its group (the JVM of a worker that had died) goes before
            # the reap; after a clean retire the group is empty and the signal reaches nobody
            reap_ended_process(self.proc, windows=_WINDOWS)
        else:
            self.kill()
        self._out.join(timeout=2)
        self._err.join(timeout=2)

    def kill(self) -> None:
        """End the worker and every process it started (its bridge JVM), then reap it."""
        self.killed = True
        kill_process_tree(self.proc, windows=_WINDOWS)


def _exited(proc: subprocess.Popen[str], *, windows: bool) -> bool:
    """Whether ``proc`` has ended, without reaping it on POSIX.

    POSIX: ``waitid`` with ``WNOWAIT`` leaves an ended worker a zombie, so its id still names
    its process group and ``killpg`` still reaches what it started. Windows: ``poll()``; the
    ``Popen`` handle keeps the id from being reused. POSIX without ``os.waitid`` (older Pythons
    on macOS; UNKNOWN, not run there): ``poll()`` reaps, so the group is signalled right here,
    where the end is first seen, because ``kill_process_tree`` sends no group signal after the
    reap. POSIX does not reuse a process group id while the group still has members, so the
    signal reaches the JVM the worker left behind; only an empty group's id may meanwhile name
    a new group (a narrow window, on this fallback only).
    """
    if proc.returncode is not None:
        return True
    if windows or sys.platform == "win32":
        return proc.poll() is not None
    if not hasattr(os, "waitid"):
        if proc.poll() is None:
            return False
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        return True
    try:
        state = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        # reaped elsewhere: ``poll()`` sets ``returncode``, so no group signal can follow
        proc.poll()
        return True
    return state is not None


def _wait_for_exit(proc: subprocess.Popen[str], timeout: float, *, windows: bool) -> bool:
    """Wait up to ``timeout`` seconds for ``proc`` to end, without reaping it on POSIX."""
    deadline = time.monotonic() + timeout
    while not _exited(proc, windows=windows):
        if time.monotonic() >= deadline:
            return False
        time.sleep(_EXIT_POLL_SECONDS)
    return True


def reap_ended_process(proc: subprocess.Popen[str], *, windows: bool) -> bool:
    """If ``proc`` has ended: kill its tree, then reap it; returns whether it had ended.

    A worker that died on its own leaves its JVM in its process group. The group is reachable
    only while the worker is not reaped, so the order is: see the end (``WNOWAIT``), kill the
    group, reap (#1652). Windows: ``taskkill /T /F`` (UNKNOWN, not run on Windows).
    """
    if not _exited(proc, windows=windows):
        return False
    kill_process_tree(proc, windows=windows)
    return True


def kill_process_tree(proc: subprocess.Popen[str], *, windows: bool) -> None:
    """End ``proc`` and its descendants: the whole tree, not only the Python worker.

    POSIX: ``SIGKILL`` to the process group the worker leads (``start_new_session``), sent only
    while the worker is not yet reaped, so its id still names that group and no other. Windows:
    ``taskkill /T /F`` on the worker's tree, which finds the JVM only while the worker still
    lives (a JVM whose worker already died is not reached; UNKNOWN, not run on Windows).
    """
    if windows:
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=_TASKKILL_WAIT_SECONDS,
                check=False,
            )
    elif proc.returncode is None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        proc.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=10)


@dataclass
class GamePool:
    """Worker processes with long-lived bridge JVMs; plays lists of games in order of the queue.

    ``run`` can be called once per look window: the workers and their JVMs stay open between the
    calls and are ended by ``close``. All callbacks run in the thread that called ``run``.
    """

    data_folder: Path
    workers: int
    command: tuple[str, ...] | None = None
    private_card_repository: bool = False
    #: How a worker process is started: its label to the argument vector. ``None``: the
    #: ``pool-worker`` command of this package. A seam for tests of the process handling.
    worker_argv: Callable[[str], list[str]] | None = None
    game_wall_limit_seconds: float = GAME_WALL_LIMIT_SECONDS
    ended_eof_grace_seconds: float = ENDED_EOF_GRACE_SECONDS
    _events: queue.Queue[tuple[_ProcessWorker, dict[str, object] | None]] = field(
        default_factory=queue.Queue, init=False
    )
    _workers: list[_ProcessWorker] = field(default_factory=list, init=False)
    _spawned: int = field(default=0, init=False)
    _jvm_lives: list[dict[str, object]] = field(default_factory=list, init=False)
    _games_finished: int = field(default=0, init=False)
    _games_failed: int = field(default=0, init=False)
    _closed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.data_folder = Path(self.data_folder)
        self.workers = max(1, int(self.workers))

    # -- worker management

    def _spawn(self) -> _ProcessWorker:
        self._spawned += 1
        label = f"w{self._spawned}"
        worker = self._spawn_process(label)
        self._workers.append(worker)
        return worker

    def _spawn_process(self, label: str) -> _ProcessWorker:
        from .launch import ENGINE_COMMAND_ENV, command_text

        if self.worker_argv is not None:
            argv = self.worker_argv(label)
        else:
            argv = [
                sys.executable,
                "-m",
                "commander_lab.studio",
                "--data",
                str(self.data_folder),
                "pool-worker",
                "--label",
                label,
            ]
            if self.private_card_repository:
                # parallel bridge JVMs would collide on the shared card database (#739)
                argv.append("--private-card-repository")
        env = dict(os.environ)
        if self.command is not None:
            env[ENGINE_COMMAND_ENV] = command_text(self.command)
        return _ProcessWorker(label, argv, env, self._events)

    def _drop(self, worker: _ProcessWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    def _idle_worker(self, limit: int) -> _ProcessWorker | None:
        for worker in list(self._workers):
            if worker.task is not None:
                continue
            if not worker.end_if_exited():
                return worker
            # it ended while idle (between two windows, or just after its last game): its tree
            # is killed and it is reaped; the end of its stdout gives it up (``_lose``), and a
            # fresh worker takes its place. When that end stays away (a process outside its
            # group holds the pipe), the grace gives it up instead, so it never holds its place
            # for good. Its reader thread and pipe stay open until that holder ends; the pipe is
            # not closed from here, under a thread that reads it.
            if time.monotonic() - worker.ended_at >= self.ended_eof_grace_seconds:
                self._lose(worker, finish=None)
        if len(self._workers) < limit:
            return self._spawn()
        return None

    # -- running games

    def _consume_event(
        self,
        worker: _ProcessWorker,
        message: dict[str, object] | None,
        *,
        on_played: Callable[[GameTask], None] | None,
        finish: Callable[[_ProcessWorker, GameSummary], None],
    ) -> None:
        if worker not in self._workers:
            return  # an event of a worker that was already given up
        if message is None:
            self._lose(worker, finish=finish)
            return
        kind = message.get("ev")
        if kind == "ready":
            worker.ready = True
        elif kind == "bye":
            worker.said_bye = True
        elif kind == "played":
            if worker.task is not None and on_played is not None:
                on_played(worker.task)
        elif kind == "jvm_exit":
            self._jvm_lives.append({k: v for k, v in message.items() if k != "ev"})
        elif kind == "done":
            summary = message.get("summary")
            if isinstance(summary, dict) and worker.task is not None:
                finish(worker, summary)

    def _drain_events(
        self,
        *,
        on_played: Callable[[GameTask], None] | None,
        finish: Callable[[_ProcessWorker, GameSummary], None],
    ) -> None:
        """Process already-queued worker events before ``_idle_worker`` checks the EOF grace
        (#1652 P3-A), so a queued ``jvm_exit`` / ``bye`` emitted between windows is never lost."""
        while True:
            try:
                worker, message = self._events.get_nowait()
            except queue.Empty:
                return
            self._consume_event(worker, message, on_played=on_played, finish=finish)

    def run(
        self,
        tasks: Sequence[GameTask],
        *,
        on_played: Callable[[GameTask], None] | None = None,
        on_done: Callable[[GameTask, GameSummary], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        record: SeriesRecord | None = None,
    ) -> dict[str, GameSummary]:
        """Play ``tasks`` and return the summary of every game that ended, by task id.

        Games are handed out in list order to whichever worker is free. A cancelled run stops
        handing out games, waits for the games in flight and returns what ended.

        With a ``record`` (S1, #1660) every final result goes to the series journal before
        ``on_done`` sees it, and a task whose game already has a result in the journal (a
        resumed series) is not played again: its journaled summary is returned and handed to
        ``on_done``. A game key with a second transcript hash raises
        :class:`~commander_lab.studio.series_record.DeterminismViolation` at once; nothing more
        is handed out, and the caller ends the pool (``close``).
        """
        if self._closed:
            raise GamePoolError("the pool is closed")
        results: dict[str, GameSummary] = {}
        journaled = record.results() if record is not None else {}
        if record is not None:
            members = record.members()
            strangers = [task.game_id for task in tasks if task.game_id not in members]
            if strangers:
                raise GamePoolError(
                    f"{len(strangers)} games are not in the manifest of the series: "
                    + ", ".join(strangers[:3])
                )
        to_play: list[GameTask] = []
        for task in tasks:
            stored = journaled.get(task.game_id)
            if stored is None:
                to_play.append(task)
                continue
            results[task.task_id] = stored
            if on_done is not None:
                on_done(task, stored)
        pending = deque(to_play)
        limit = min(self.workers, max(1, len(pending)))
        cancelled = False

        def _finish(worker: _ProcessWorker, summary: GameSummary) -> None:
            task = worker.task
            worker.task = None
            if task is None:
                return
            if record is not None:
                # the guard runs here; a violation ends the run before ``on_done``
                record.record(task.game_id, summary)
            results[task.task_id] = summary
            if summary.get("status") == "finished":
                self._games_finished += 1
            else:
                self._games_failed += 1
            if on_done is not None:
                on_done(task, summary)

        while True:
            self._drain_events(on_played=on_played, finish=_finish)
            if not cancelled and should_cancel is not None and should_cancel():
                cancelled = True
                pending.clear()
            while pending and not cancelled:
                worker = self._idle_worker(limit)
                if worker is None:
                    break
                task = pending.popleft()
                worker.task = task
                worker.task_started = time.monotonic()
                if not worker.send(task.to_wire()):
                    worker.task = None
                    pending.appendleft(task)
                    self._lose(worker, finish=None)
            busy = [worker for worker in self._workers if worker.task is not None]
            if not busy and not pending:
                return results
            try:
                worker, message = self._events.get(timeout=_POLL_SECONDS)
            except queue.Empty:
                self._check_wall_limit(_finish)
                continue
            self._consume_event(worker, message, on_played=on_played, finish=_finish)
            self._check_wall_limit(_finish)

    def _check_wall_limit(self, finish: Callable[[_ProcessWorker, GameSummary], None]) -> None:
        now = time.monotonic()
        for worker in list(self._workers):
            if worker.task is not None and now - worker.task_started > self.game_wall_limit_seconds:
                worker.kill()  # the worker and its JVM (process group / tree), not the worker only
                self._lose(worker, finish=finish, failure_class="TimeLimit")

    def _not_started(self, worker: _ProcessWorker) -> str:
        tail = " | ".join(list(worker.stderr_tail)[-5:])
        return f"worker {worker.label} ended before it was ready" + (f": {tail}" if tail else "")

    def _lose(
        self,
        worker: _ProcessWorker,
        *,
        finish: Callable[[_ProcessWorker, GameSummary], None] | None,
        failure_class: str = "WorkerExited",
    ) -> None:
        """A worker process ended (or was given up). Its game in flight failed as infrastructure.

        Whatever the worker started (its JVM) is ended with it: a worker that died on its own
        would otherwise leave its JVM running. The JVM life open in it never reported its end;
        it is recorded here with what is unknown left unknown.
        """
        self._drop(worker)
        with contextlib.suppress(Exception):
            worker.kill()
        if not worker.ready:
            raise GamePoolError(self._not_started(worker))
        if worker.task is not None:
            self._record_lost_life(worker, failure_class)
            if finish is not None:
                finish(worker, self._lost_game_summary(worker.task, failure_class))
        elif not worker.said_bye:
            # died while idle: its open JVM life never reported its end (#1652)
            self._record_lost_life(worker, failure_class)

    def _record_lost_life(self, worker: _ProcessWorker, reason: str) -> None:
        """A JVM life that ended without its ``jvm_exit``: id and games played are unknown."""
        self._jvm_lives.append(
            {
                "life_id": None,
                "games": None,
                "end": "worker_lost",
                "disposition": "process_tree_killed",
                "worker": worker.label,
                "reason": reason,
            }
        )

    def _lost_game_summary(self, task: GameTask, failure_class: str) -> GameSummary:
        message = {
            "WorkerExited": "the worker process ended while it played this game",
            "TimeLimit": "the game did not end within the limit; its worker was ended",
        }.get(failure_class, "the game was lost")
        failure: GameSummary = {
            "status": "failed",
            "failure_class": failure_class,
            "failure_message": message,
        }
        path = _close_orphaned_log(self.data_folder, task.game_id, failure)
        return {"game_id": task.game_id, **failure, "log": str(path) if path else None}

    # -- end of the series

    def summary(self) -> dict[str, object]:
        """What the workers did: n of N games, and each JVM life with its way of ending."""
        lives = list(self._jvm_lives)
        lost = sum(1 for life in lives if life.get("end") == "worker_lost")
        return {
            "executor": "studio-game-pool-1",
            "workers": self.workers,
            "worker_processes_started": self._spawned,
            "games_finished": self._games_finished,
            "games_failed": self._games_failed,
            "jvm_lives": lives,
            "jvm_lives_ended": len(lives),
            # of those, lives whose worker was lost or killed: id and games played unknown
            "jvm_lives_lost": lost,
        }

    def close(self) -> None:
        """End every worker: each ends its JVM cleanly, one that does not answer is killed."""
        self._closed = True
        workers, self._workers = list(self._workers), []
        for worker in workers:
            worker.retire(RETIRE_WAIT_SECONDS)
        while True:
            try:
                sender, message = self._events.get_nowait()
            except queue.Empty:
                break
            if message is not None and message.get("ev") == "jvm_exit":
                self._jvm_lives.append({k: v for k, v in message.items() if k != "ev"})
            elif message is not None and message.get("ev") == "bye":
                sender.said_bye = True
        for worker in workers:
            # ended before it reported every life: killed while ending its JVM, or died while
            # idle before ``close``; one life is unknown
            if worker.ready and not worker.said_bye:
                self._record_lost_life(worker, "RetireTimeout" if worker.killed else "WorkerExited")

    def __enter__(self) -> GamePool:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _close_orphaned_log(
    data_folder: Path, game_id: str, failure: Mapping[str, object]
) -> Path | None:
    """Write the closing entry of a log whose worker died mid-game, and pack it.

    A log without a closing entry reads as a game that is still running; the game has failed.
    A game that never wrote a log has nothing to close.
    """
    import gzip

    log = games_folder(data_folder) / f"{game_id}.jsonl"
    if not log.is_file():
        return None
    closing = {"kind": "result", "ended_at": now_utc(), **failure}
    with log.open("a", encoding="utf-8") as handle:
        handle.write("\n" if log.stat().st_size and not _ends_with_newline(log) else "")
        handle.write(json.dumps(closing, separators=(",", ":"), ensure_ascii=False) + "\n")
    packed = log.with_suffix(".jsonl.gz")
    with log.open("rb") as source, gzip.open(packed, "wb", compresslevel=1) as target:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            target.write(chunk)
    log.unlink()
    return packed


def _ends_with_newline(path: Path) -> bool:
    with path.open("rb") as handle:
        handle.seek(-1, os.SEEK_END)
        return handle.read(1) == b"\n"


__all__ = [
    "ENDED_EOF_GRACE_SECONDS",
    "GAME_WALL_LIMIT_SECONDS",
    "SERIES_POOL_ENV",
    "DeterminismViolation",
    "GamePool",
    "GamePoolError",
    "GameSummary",
    "GameTask",
    "SessionWorkerEngine",
    "WorkerEngine",
    "config_refusal",
    "jvm_env_digest",
    "jvm_options_of",
    "own_engine_pin",
    "plan_task",
    "refused_game_summary",
    "run_worker_process",
    "seat_pilot_fingerprint",
    "series_pool_enabled",
    "skip_forced_decisions_of",
    "task_key_of",
    "task_refusal",
    "worker_main",
]
