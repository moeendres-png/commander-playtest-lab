"""Play several simulated games in one rules-engine process and record each one.

A Studio series hands its games to this module in chunks. One bridge JVM plays the games of a
chunk one after the other (``XmageFullGameRunner.run_batch``: every game is shut down before
the next one starts; after a failed game the JVM is discarded and the rest of the chunk
continues in a fresh one, so a failed game takes no neighbour with it). Each game gets its own
setup from ``play.prepare_game``, the function a game played alone uses, its own log and its own
closing entry, so a game in a batch is the game of its seed, not a variant of it.

Evidence and qualification lanes do not use this module: they keep one game per process.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.failure_privacy import public_exception_type
from commander_lab.engine.rules.full_game import (
    FullGameBridgeClient,
    FullGameConformanceResult,
    FullGameDecisionPolicy,
    FullGamePilotBinding,
)
from commander_lab.engine.rules.full_game_batch import games_per_jvm_permitted
from commander_lab.models import RulesDeckInput

from .games import SERIES_GZIP_COMPRESSLEVEL, GameRecorder, game_cohort
from .launch import bridge_jar_sha256, engine_command
from .pilot_audit import PilotAuditPolicy, PilotAuditRecorder
from .play import (
    _RecordingRunner,
    close_recorded_game,
    covered_by_sealed_epoch,
    load_decks,
    prepare_game,
)


@dataclass(frozen=True)
class SeriesGame:
    """One game of a chunk: its seed and the id of the log it writes."""

    seed: int
    game_id: str


class BatchRecordingRunner(_RecordingRunner):
    """The recording full-game runner for several games: one recorder per game.

    The recorder of a game is made when its play starts (``decision_policy`` runs at the start
    of every play of a game), so a game that is started again after a neighbour's failure or a
    start-up collision begins a fresh log instead of appending to the first attempt.
    """

    def __init__(
        self,
        data_folder: str | Path,
        headers: Mapping[str, tuple[str, dict[str, object]]],
        *,
        command: tuple[str, ...] | None,
        max_decisions: int = 50_000,
        request_timeout_seconds: float = 120.0,
        private_card_repository: bool = False,
        record_pilot_audit: bool = False,
    ) -> None:
        super().__init__(
            command=command,
            max_decisions=max_decisions,
            request_timeout_seconds=request_timeout_seconds,
            private_card_repository=private_card_repository,
        )
        self._data_folder = data_folder
        self._headers = headers
        self._recorders: dict[str, GameRecorder] = {}
        self._record_pilot_audit = bool(record_pilot_audit)
        self._audit_recorders: dict[str, PilotAuditRecorder] = {}
        #: Called with the log id of a game once the engine has played it to its end, while
        #: the chunk's other games are still to come. A progress signal only: the log is closed
        #: and the result built after the engine process ends (see ``play_recorded_games``).
        self.on_played: Callable[[str], None] | None = None
        self._current_game_id: str | None = None
        self._announced: set[str] = set()

    def enable_pilot_audit(self, enabled: bool = True) -> None:
        """Enable or disable opt-in pilot request audit recording for subsequent games (#1524)."""
        self._record_pilot_audit = bool(enabled)

    def _begin_audit_game(self, scenario_id: str) -> PilotAuditRecorder:
        previous = self._audit_recorders.pop(scenario_id, None)
        if previous is not None:
            previous.discard()
        game_id, header = self._headers[scenario_id]
        # Mirror GameRecorder.__init__: prepare_game() omits data_class until recording; derive
        # cohort fail-closed when seats are present without overriding an explicit data_class.
        audit_header: dict[str, object] = dict(header)
        if "data_class" not in audit_header and audit_header.get("seats"):
            audit_header["data_class"] = game_cohort(audit_header)
        recorder = PilotAuditRecorder(
            self._data_folder,
            game_id,
            audit_header,
            gzip_compresslevel=SERIES_GZIP_COMPRESSLEVEL,
        )
        self._audit_recorders[scenario_id] = recorder
        return recorder

    def decision_policy(
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> FullGameDecisionPolicy:
        policy = super().decision_policy(scenario, decks, pilots)
        if not self._record_pilot_audit:
            return policy
        audit = self._begin_audit_game(scenario.scenario_id)
        return PilotAuditPolicy(policy, audit)

    def close_audit_game(
        self,
        scenario_id: str,
        outcome: FullGameConformanceResult | Exception,
    ) -> dict[str, object] | None:
        """Close and compress the opt-in audit log for ``scenario_id`` if one was started."""
        audit = self._audit_recorders.pop(scenario_id, None)
        if audit is None:
            return None
        try:
            if isinstance(outcome, Exception):
                _, summary = audit.close(
                    status="failed",
                    failure_class=public_exception_type(outcome),
                )
                return summary
            _, summary = audit.close(
                status="finished",
                winner_seats=[seat - 1 for seat in outcome.winner_seats],
                decision_count=outcome.decision_count,
                semantic_transcript_sha256=outcome.semantic_transcript_sha256,
            )
            return summary
        except OSError:
            audit.discard()
            return None

    def discard_open_audits(self) -> None:
        """Best-effort cleanup of any remaining open audit recorders."""
        while self._audit_recorders:
            _, audit = self._audit_recorders.popitem()
            audit.discard()

    def begin_game(self, scenario_id: str) -> GameRecorder:
        previous = self._recorders.pop(scenario_id, None)
        if previous is not None:
            previous.discard()
        game_id, header = self._headers[scenario_id]
        recorder = GameRecorder(
            self._data_folder,
            game_id,
            header,
            flush_each_frame=False,
            gzip_compresslevel=SERIES_GZIP_COMPRESSLEVEL,
        )
        self._recorders[scenario_id] = recorder
        self.recorder = recorder
        self._current_game_id = game_id
        return recorder

    def after_drive(self, client: FullGameBridgeClient, *, terminal: bool) -> None:
        """Export the event log and tell ``on_played`` once the engine has played it to its end.

        A progress callback that raises changes nothing about the game. A game played again (after
        an unclean engine end, or a start-up collision) is announced once.
        """
        super().after_drive(client, terminal=terminal)
        game_id = self._current_game_id
        if (
            terminal is True
            and game_id is not None
            and self.on_played is not None
            and game_id not in self._announced
        ):
            self._announced.add(game_id)
            with contextlib.suppress(Exception):
                self.on_played(game_id)

    def recorder_of(self, scenario_id: str) -> GameRecorder:
        """The log of a game; a game that failed before its play began still gets one."""
        return self._recorders.get(scenario_id) or self.begin_game(scenario_id)

    def _recorder_for(self, scenario: FutureXmageScenario) -> GameRecorder:
        return self.begin_game(scenario.scenario_id)


RunnerFactory = Callable[
    [Path | str, Mapping[str, tuple[str, dict[str, object]]], int, float, bool],
    BatchRecordingRunner,
]


def _real_runner(
    data_folder: Path | str,
    headers: Mapping[str, tuple[str, dict[str, object]]],
    max_decisions: int,
    request_timeout_seconds: float,
    private_card_repository: bool,
) -> BatchRecordingRunner:
    return BatchRecordingRunner(
        data_folder,
        headers,
        command=engine_command(data_folder),
        max_decisions=max_decisions,
        request_timeout_seconds=request_timeout_seconds,
        private_card_repository=private_card_repository,
    )


def play_recorded_games(
    data_folder: str | Path,
    deck_paths: list[Path],
    games: Sequence[SeriesGame],
    *,
    strategy: str = "generic",
    style: float | None = None,
    seat_styles: Mapping[int, float] | None = None,
    max_decisions: int = 50_000,
    request_timeout_seconds: float = 120.0,
    private_card_repository: bool = False,
    command: tuple[str, ...] | None = None,
    on_game: Callable[[dict[str, object]], None] | None = None,
    on_played: Callable[[str], None] | None = None,
    runner_factory: RunnerFactory = _real_runner,
    record_pilot_audit: bool = False,
) -> list[dict[str, object]]:
    """Play ``games`` (seed and log id each) on the configured engine, several per JVM.

    The bridge command decides how many games one JVM plays
    (``-Dcommanderlab.fullGame.gamesPerJvm``); a longer list is played in pieces of that size.
    Returns one short summary per game, in order, as ``play_recorded_game`` does, and calls
    ``on_game`` with each once its log is closed. A game that fails keeps its log up to the
    failure with the public failure class; the other games of the chunk are unaffected.

    ``on_played`` is the progress signal of a chunk: it gets the log id of each game as soon as
    the engine has played it to its end, before the chunk returns. It is not a result: the log is
    closed and the result built only once the engine process has ended (``on_game``), and a game
    that fails is never announced. Neither the order of the games nor their outcomes depend on it.
    """
    decks = load_decks(deck_paths)
    cmd = command if command is not None else engine_command(data_folder)
    prepared = [
        prepare_game(
            decks,
            seed=game.seed,
            game_id=game.game_id,
            strategy=strategy,
            style=style,
            seat_styles=seat_styles,
            data_folder=data_folder,
            command=cmd,
        )
        for game in games
    ]
    headers = {item.scenario.scenario_id: (item.game_id, item.header) for item in prepared}
    if runner_factory is _real_runner:
        runner = BatchRecordingRunner(
            data_folder,
            headers,
            command=cmd,
            max_decisions=max_decisions,
            request_timeout_seconds=request_timeout_seconds,
            private_card_repository=private_card_repository,
            record_pilot_audit=record_pilot_audit,
        )
    else:
        runner = runner_factory(
            data_folder, headers, max_decisions, request_timeout_seconds, private_card_repository
        )
        if record_pilot_audit and hasattr(runner, "enable_pilot_audit"):
            runner.enable_pilot_audit(True)
    if runner.command != cmd:
        sha = bridge_jar_sha256(data_folder, runner.command)
        for item in prepared:
            item.header["bridge_jar_sha256"] = sha
            item.header["covered_by_sealed_epoch"] = covered_by_sealed_epoch(
                item.header.get("bridge_qualification_state"),
                sha,
                item.header.get("covered_by_sealed_epoch", False),
            )
    runner.on_played = on_played
    permitted = games_per_jvm_permitted(runner.command) if runner.command else 1
    summaries: list[dict[str, object]] = []
    try:
        for start in range(0, len(prepared), permitted):
            piece = prepared[start : start + permitted]
            outcomes: list[FullGameConformanceResult | Exception]
            try:
                outcomes = runner.run_batch(
                    [(item.scenario, item.decks, item.pilots) for item in piece]
                )
            except Exception as error:  # no engine command: every game of the piece failed to start
                outcomes = [error] * len(piece)
            for item, outcome in zip(piece, outcomes, strict=True):
                summary = close_recorded_game(
                    runner.recorder_of(item.scenario.scenario_id), outcome
                )
                if record_pilot_audit and hasattr(runner, "close_audit_game"):
                    runner.close_audit_game(item.scenario.scenario_id, outcome)
                summaries.append(summary)
                if on_game is not None:
                    on_game(summary)
    finally:
        if record_pilot_audit and hasattr(runner, "discard_open_audits"):
            runner.discard_open_audits()
    return summaries
