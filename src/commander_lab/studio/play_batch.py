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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import FullGameConformanceResult
from commander_lab.engine.rules.full_game_batch import _games_per_jvm_permitted

from .games import GameRecorder
from .launch import engine_command
from .play import (
    _RecordingRunner,
    close_recorded_game,
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

    The recorder of a game is made when its play starts (``_validated_policy`` runs at the start
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

    def begin_game(self, scenario_id: str) -> GameRecorder:
        previous = self._recorders.pop(scenario_id, None)
        if previous is not None:
            previous.discard()
        game_id, header = self._headers[scenario_id]
        recorder = GameRecorder(self._data_folder, game_id, header)
        self._recorders[scenario_id] = recorder
        self.recorder = recorder
        return recorder

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
    on_game: Callable[[dict[str, object]], None] | None = None,
    runner_factory: RunnerFactory = _real_runner,
) -> list[dict[str, object]]:
    """Play ``games`` (seed and log id each) on the configured engine, several per JVM.

    The bridge command decides how many games one JVM plays
    (``-Dcommanderlab.fullGame.gamesPerJvm``); a longer list is played in pieces of that size.
    Returns one short summary per game, in order, as ``play_recorded_game`` does, and calls
    ``on_game`` with each once its log is closed. A game that fails keeps its log up to the
    failure with the public failure class; the other games of the chunk are unaffected.
    """
    decks = load_decks(deck_paths)
    prepared = [
        prepare_game(
            decks,
            seed=game.seed,
            game_id=game.game_id,
            strategy=strategy,
            style=style,
            seat_styles=seat_styles,
        )
        for game in games
    ]
    headers = {item.scenario.scenario_id: (item.game_id, item.header) for item in prepared}
    runner = runner_factory(
        data_folder, headers, max_decisions, request_timeout_seconds, private_card_repository
    )
    permitted = _games_per_jvm_permitted(runner.command) if runner.command else 1
    summaries: list[dict[str, object]] = []
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
            summary = close_recorded_game(runner.recorder_of(item.scenario.scenario_id), outcome)
            summaries.append(summary)
            if on_game is not None:
                on_game(summary)
    return summaries
