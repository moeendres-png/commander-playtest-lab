"""Studio series: several games per bridge JVM on several workers, one game each.

A fake chunk runner and a fake engine stand in for the real one; the real-engine identity
check is ``scripts/check_studio_series_identity.py``.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import games, launch
from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.play_batch import (
    BatchRecordingRunner,
    SeriesGame,
    play_recorded_games,
)
from commander_lab.studio.simulations import (
    BatchSimulation,
    GameSummary,
    SimulationBatchManager,
    plan_chunks,
    simulation_manager,
)
from commander_lab.studio.store import StudioStore
from commander_lab.studio.web import create_app

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "data/decks/deckbau/chulane_current.json"
PRECONS = [
    ROOT / "data/decks/precons/2026_lorehold_spirit.json",
    ROOT / "data/decks/precons/2024_animated_army.json",
    ROOT / "data/decks/precons/2022_token_triumph.json",
]


def _batch(tmp_path: Path, seeds: list[int], runner: object, **kwargs: object) -> BatchSimulation:
    return BatchSimulation(
        "t1",
        tmp_path,
        "chulane",
        "rev",
        "precon",
        [],
        seeds,
        chunk_runner=runner,
        **kwargs,  # type: ignore[arg-type]
    )


def _finished(batch: BatchSimulation, seed: int, winners: list[int]) -> GameSummary:
    return GameSummary(
        game_id=batch.game_id_of(seed), seed=seed, status="finished", winner_seats=winners
    )


def test_chunks_respect_games_per_jvm_and_use_every_worker() -> None:
    assert plan_chunks([], 4, 6) == []
    assert plan_chunks(list(range(10)), 1, 6) == [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]]
    chunks = plan_chunks(list(range(10)), 4, 6)
    assert len(chunks) == 4 and max(map(len, chunks)) <= 6
    assert [seed for chunk in chunks for seed in chunk] == list(range(10))
    assert plan_chunks([1, 2], 8, 6) == [[1], [2]]
    assert all(len(c) <= 1 for c in plan_chunks(list(range(5)), 2, 1))


def test_settings_defaults_and_ranges() -> None:
    workers, per_jvm = launch.checked_series_settings(None, None)
    assert 1 <= workers <= 4 and per_jvm == 16 == launch.DEFAULT_GAMES_PER_JVM  # #1587
    assert launch.checked_series_settings(16, 24) == (16, 24)
    # the edges of the range stay selectable: 1 (isolated), 6 (the old default), 24 (the maximum)
    for edge in (1, 6, 24):
        assert launch.checked_series_settings(2, edge) == (2, edge)
    for bad in ((0, 6), (17, 6), (2, 0), (2, 25)):
        with pytest.raises(ValueError):
            launch.checked_series_settings(*bad)


def test_default_games_per_jvm_is_within_range_and_the_studio_budget() -> None:
    from commander_lab.engine.rules.full_game_series import SERIES_JVM_GAME_CAP

    assert launch.MIN_GAMES_PER_JVM <= launch.DEFAULT_GAMES_PER_JVM <= launch.MAX_GAMES_PER_JVM
    assert launch.MAX_GAMES_PER_JVM == 24  # 24 stays an option, never the default
    # Owner decision E9: the Studio budget is at most 56 games per JVM, above the whole range
    assert launch.MAX_GAMES_PER_JVM <= SERIES_JVM_GAME_CAP == 56


def test_series_engine_with_the_default_asks_the_bridge_for_16_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"x")
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, f"java -Xmx3g -jar {jar} full-game")
    _, per_jvm = launch.checked_series_settings(None, None)
    engine = launch.series_engine(tmp_path, per_jvm)
    assert engine is not None and engine.games_per_jvm == 16
    assert "-Dcommanderlab.fullGame.gamesPerJvm=16" in engine.jvm_flags


def test_default_games_per_jvm_only_regroups_chunks_never_the_seeds() -> None:
    """#1587: 16 instead of 6 changes how many games one JVM plays, not which seeds are played."""
    seeds = list(range(1000, 1048))
    for workers in (1, 2, 4, 7):
        old = plan_chunks(seeds, workers, 6)
        new = plan_chunks(seeds, workers, launch.DEFAULT_GAMES_PER_JVM)
        assert [s for chunk in old for s in chunk] == seeds
        assert [s for chunk in new for s in chunk] == seeds
        assert max(map(len, new)) <= launch.DEFAULT_GAMES_PER_JVM
        assert len(new) >= min(workers, len(seeds))
    # the plan itself does change for a long series, which is the point of the new default
    assert plan_chunks(seeds, 4, 6) != plan_chunks(seeds, 4, 16)
    assert [len(c) for c in plan_chunks(seeds, 4, 16)] == [12, 12, 12, 12]


def test_series_engine_adds_fast_flags_and_archive_only_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"x")
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, f"java -Xmx3g -jar {jar} full-game")
    plain = launch.series_engine(tmp_path, 3)
    assert plain is not None
    assert plain.serial_gc and not plain.appcds and plain.games_per_jvm == 3
    assert "-Dcommanderlab.fullGame.gamesPerJvm=3" in plain.jvm_flags
    assert plain.command[-3:] == ("-jar", str(jar.resolve()), "full-game")
    jar.with_suffix(".jsa").write_bytes(b"x")
    with_archive = launch.series_engine(tmp_path, 1)
    assert with_archive is not None and with_archive.appcds
    assert not any("gamesPerJvm" in flag for flag in with_archive.jvm_flags)
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, "/opt/wrapper full-game")
    wrapper = launch.series_engine(tmp_path, 6)
    assert wrapper is not None and wrapper.games_per_jvm == 1 and not wrapper.jvm_flags


def test_every_game_keeps_its_seed_row_and_status_with_a_failed_neighbour(tmp_path: Path) -> None:
    seen: list[list[int]] = []

    def runner(seeds: Sequence[int]) -> Iterator[GameSummary]:
        seen.append(list(seeds))
        for seed in seeds:
            if seed == 3:
                yield GameSummary(
                    game_id=batch.game_id_of(seed), seed=seed, status="failed", failure_class="X"
                )
            else:
                yield _finished(batch, seed, [0] if seed % 2 else [1])

    batch = _batch(tmp_path, [1, 2, 3, 4, 5, 6], runner, workers=2, games_per_jvm=3)
    batch.run_worker()
    data = batch.to_dict()
    rows = data["games"]
    assert [row["seed"] for row in rows] == [1, 2, 3, 4, 5, 6]  # type: ignore[index]
    assert [row["status"] for row in rows] == ["finished"] * 2 + ["failed"] + ["finished"] * 3  # type: ignore[index]
    assert [row["game_id"] for row in rows] == [f"batch-t1-s{s}" for s in range(1, 7)]  # type: ignore[index]
    assert data["games_failed"] == 1 and data["games_completed"] == 5
    assert sorted(map(tuple, seen)) == [(1, 2, 3), (4, 5, 6)]
    execution = data["execution"]
    assert execution["workers"] == 2 and execution["games_per_jvm"] == 3  # type: ignore[index]
    assert (tmp_path / "games" / "t1.series.json").is_file()


def test_a_chunk_that_dies_fails_only_its_unreported_games(tmp_path: Path) -> None:
    def runner(seeds: Sequence[int]) -> Iterator[GameSummary]:
        yield _finished(batch, seeds[0], [0])
        if seeds[0] == 1:
            raise RuntimeError("engine process vanished")

    batch = _batch(tmp_path, [1, 2, 3, 4], runner, workers=2, games_per_jvm=2)
    batch.run_worker()
    status = {g.seed: g.status for g in batch._games}
    assert status == {1: "finished", 2: "failed", 3: "finished", 4: "failed"}
    assert batch.status == "completed"


def test_chunks_run_in_parallel_and_cancellation_stops_new_chunks(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    count = 0
    lock = threading.Lock()

    def runner(seeds: Sequence[int]) -> Iterator[GameSummary]:
        nonlocal count
        with lock:
            count += 1
        started.set()
        release.wait(5)
        for seed in seeds:
            yield _finished(batch, seed, [0])

    batch = _batch(tmp_path, list(range(1, 9)), runner, workers=2, games_per_jvm=2)
    thread = threading.Thread(target=batch.run_worker)
    thread.start()
    assert started.wait(5)
    time.sleep(0.2)
    batch.cancel()
    release.set()
    thread.join(10)
    assert batch.status == "cancelled"
    assert count == 2  # two workers took one chunk each; the other chunks never started
    assert len(batch._games) == 4


def test_invalid_settings_are_refused(tmp_path: Path) -> None:
    for kwargs in ({"workers": 0}, {"workers": 17}, {"games_per_jvm": 0}, {"games_per_jvm": 25}):
        with pytest.raises(ValueError):
            _batch(tmp_path, [1], lambda seeds: iter(()), **kwargs)


def test_api_and_cli_validate_the_settings(tmp_path: Path) -> None:
    StudioStore.open(tmp_path).close()
    client = TestClient(create_app(tmp_path))
    for body in ({"workers": 17}, {"games_per_jvm": 25}, {"workers": 0}):
        res = client.post(
            "/api/simulations/batch",
            headers={"X-Studio": "1"},
            json={"revision_id": "rev@x/main/current", **body},
        )
        assert res.status_code == 422
    assert (
        studio_main(["--data", str(tmp_path), "simulate", "--revision", "r", "--workers", "99"])
        == 2
    )


class _FakeEngineRunner(BatchRecordingRunner):
    """Plays no engine: records one frame per game and fails the games in ``fail``."""

    fail: frozenset[int] = frozenset()

    def run_batch(self, games):  # type: ignore[no-untyped-def]
        outcomes: list[object] = []
        for scenario, _decks, _pilots in games:
            recorder = self._recorder_for(scenario)
            recorder.record(
                {"decision_class": "priority", "seat": 0, "legal_options": [], "pilot_state": {}},
                {},
            )
            if scenario.seed in self.fail:
                outcomes.append(RuntimeError("boom"))
            else:
                outcomes.append(
                    SimpleNamespace(
                        winner_seats=(scenario.seed % 4 + 1,),
                        decision_count=scenario.seed,
                        engine_version="fake",
                        semantic_transcript_sha256=f"hash-{scenario.seed}",
                    )
                )
        return outcomes


def test_a_batch_writes_one_log_per_game_with_its_own_seed_and_status(tmp_path: Path) -> None:
    def factory(data, headers, max_decisions, timeout, private):  # type: ignore[no-untyped-def]
        runner = _FakeEngineRunner(
            data,
            headers,
            command=("java", "-Dcommanderlab.fullGame.gamesPerJvm=2", "-jar", "x"),
            max_decisions=max_decisions,
            request_timeout_seconds=timeout,
            private_card_repository=private,
        )
        runner.fail = frozenset({2})
        return runner

    reported: list[str] = []
    summaries = play_recorded_games(
        tmp_path,
        [DECK, *PRECONS],
        [SeriesGame(seed, f"g-s{seed}") for seed in (1, 2, 3)],
        on_game=lambda summary: reported.append(str(summary["game_id"])),
        runner_factory=factory,
    )
    assert [s["status"] for s in summaries] == ["finished", "failed", "finished"]
    assert reported == ["g-s1", "g-s2", "g-s3"]
    for seed, status in ((1, "finished"), (2, "failed"), (3, "finished")):
        log = games.read_game(tmp_path, f"g-s{seed}", start=0, count=5)
        assert log["header"]["seed"] == seed  # type: ignore[index]
        result = log["result"]
        assert result["status"] == status  # type: ignore[index]
        assert log["total"] == 1
        if status == "finished":
            assert result["semantic_transcript_sha256"] == f"hash-{seed}"  # type: ignore[index]
            assert result["decision_count"] == seed  # type: ignore[index]


def test_every_batch_log_names_the_deck_state_of_each_seat(tmp_path: Path) -> None:
    """#1657: a batch game's header names a 64-hex ``deck_hash`` per seat, as a game alone."""

    def factory(data, headers, max_decisions, timeout, private):  # type: ignore[no-untyped-def]
        return _FakeEngineRunner(
            data,
            headers,
            command=("java", "-jar", "x"),
            max_decisions=max_decisions,
            request_timeout_seconds=timeout,
            private_card_repository=private,
        )

    play_recorded_games(tmp_path, [DECK, *PRECONS], [SeriesGame(1, "g-h1")], runner_factory=factory)
    header = games.read_game(tmp_path, "g-h1", start=0, count=1)["header"]
    seats = header["seats"]  # type: ignore[index]
    assert len(seats) == 1 + len(PRECONS)
    assert all(re.fullmatch(r"[0-9a-f]{64}", str(row["deck_hash"])) for row in seats)
    assert len({row["deck_hash"] for row in seats}) == len(seats)


class _Client:
    """The engine side of one game as the shared drive loop sees it: no decisions, a scripted end."""

    def __init__(self, *, fails: bool = False, terminal: bool = True) -> None:
        self.fails = fails
        self.terminal = terminal

    def request(self, op: str, payload: object = None) -> dict[str, object]:
        if op == "start_full_game":
            if self.fails:
                raise RuntimeError("engine failed")
            return {"terminal": self.terminal}
        return {}


class _DrivingRunner(BatchRecordingRunner):
    """Like ``_FakeEngineRunner``, but each game goes through the real ``_drive`` loop and
    ``after_drive`` hook, one after the other, and the result of every game exists only when
    ``run_batch`` returns."""

    fail: frozenset[int] = frozenset()
    not_terminal: frozenset[int] = frozenset()
    twice: frozenset[int] = frozenset()
    events: list[str]

    def run_batch(self, games):  # type: ignore[no-untyped-def]
        outcomes: list[object] = []
        for scenario, _decks, _pilots in games:
            seed = scenario.seed
            self.events.append(f"start-{seed}")
            recorder = self._recorder_for(scenario)
            recorder.record(
                {"decision_class": "priority", "seat": 0, "legal_options": [], "pilot_state": {}},
                {},
            )
            try:
                for _ in range(2 if seed in self.twice else 1):
                    client = _Client(
                        fails=seed in self.fail, terminal=seed not in self.not_terminal
                    )
                    _count, _classes, terminal = self._drive(client, None, stop_after=0)
                if terminal is not True:
                    raise RuntimeError("full game ended without game over")
            except RuntimeError as error:
                outcomes.append(error)
                continue
            outcomes.append(
                SimpleNamespace(
                    winner_seats=(seed % 4 + 1,),
                    decision_count=seed,
                    engine_version="fake",
                    semantic_transcript_sha256=f"hash-{seed}",
                )
            )
        return outcomes


def _play_driving(
    tmp_path: Path,
    seeds: Sequence[int],
    *,
    on_played: object = None,
    on_game: object = None,
    fail: frozenset[int] = frozenset(),
    not_terminal: frozenset[int] = frozenset(),
    twice: frozenset[int] = frozenset(),
) -> tuple[list[dict[str, object]], list[str]]:
    events: list[str] = []

    def factory(data, headers, max_decisions, timeout, private):  # type: ignore[no-untyped-def]
        runner = _DrivingRunner(
            data,
            headers,
            command=("java", "-Dcommanderlab.fullGame.gamesPerJvm=8", "-jar", "x"),
            max_decisions=max_decisions,
            request_timeout_seconds=timeout,
            private_card_repository=private,
        )
        runner.fail, runner.not_terminal, runner.twice = fail, not_terminal, twice
        runner.events = events
        return runner

    def played(game_id: str) -> None:
        events.append(f"played-{game_id}")
        if callable(on_played):
            on_played(game_id)

    def closed(summary: dict[str, object]) -> None:
        events.append(f"closed-{summary['game_id']}")
        if callable(on_game):
            on_game(summary)

    summaries = play_recorded_games(
        tmp_path,
        [DECK, *PRECONS],
        [SeriesGame(seed, f"g-s{seed}") for seed in seeds],
        on_played=played,
        on_game=closed,
        runner_factory=factory,
    )
    return summaries, events


def test_progress_is_announced_per_game_before_the_chunk_returns(tmp_path: Path) -> None:
    summaries, events = _play_driving(tmp_path, (1, 2, 3), fail=frozenset({2}))
    # each finished game is announced as soon as it is played, not when the chunk is over; the
    # failed game is never announced; logs close and results appear only after the chunk
    assert events == [
        "start-1",
        "played-g-s1",
        "start-2",
        "start-3",
        "played-g-s3",
        "closed-g-s1",
        "closed-g-s2",
        "closed-g-s3",
    ]
    assert [s["status"] for s in summaries] == ["finished", "failed", "finished"]


def test_a_game_that_does_not_reach_its_end_is_not_announced(tmp_path: Path) -> None:
    _summaries, events = _play_driving(tmp_path, (1, 2), not_terminal=frozenset({1}))
    assert [e for e in events if e.startswith("played")] == ["played-g-s2"]


def test_a_game_played_again_is_announced_once(tmp_path: Path) -> None:
    _summaries, events = _play_driving(tmp_path, (1, 2), twice=frozenset({1}))
    assert events.count("played-g-s1") == 1 and events.count("played-g-s2") == 1


def test_progress_changes_no_result(tmp_path: Path) -> None:
    """Same seeds: same transcript hash, winner and decision count with or without the signal, and
    with a signal that raises."""

    def raises(_game_id: str) -> None:
        raise BrokenPipeError("the reader is gone")

    def keyed(folder: Path, summaries: list[dict[str, object]]) -> list[tuple[object, ...]]:
        rows: list[tuple[object, ...]] = []
        for s in summaries:
            result = games.read_game(folder, str(s["game_id"]), start=0, count=1)["result"]
            rows.append(
                (
                    s["game_id"],
                    s["status"],
                    s.get("winner_seats"),
                    s.get("decision_count"),
                    result.get("semantic_transcript_sha256"),  # type: ignore[union-attr]
                )
            )
        return rows

    plain, _ = _play_driving(tmp_path / "a", (1, 2, 3, 4), fail=frozenset({3}))
    marked, _ = _play_driving(
        tmp_path / "b", (1, 2, 3, 4), on_played=lambda _g: None, fail=frozenset({3})
    )
    broken, _ = _play_driving(tmp_path / "c", (1, 2, 3, 4), on_played=raises, fail=frozenset({3}))
    rows = keyed(tmp_path / "a", plain)
    assert rows == keyed(tmp_path / "b", marked) == keyed(tmp_path / "c", broken)
    assert [row[4] for row in rows] == ["hash-1", "hash-2", None, "hash-4"]
    assert [row[3] for row in rows] == [1, 2, None, 4]


def test_the_batch_cli_prints_a_progress_line_that_is_not_a_result_line() -> None:
    from commander_lab.studio.simulations import _played_game, _reported_game

    progress = json.dumps({"event": "played", "played_game_id": "batch-t1-s1"})
    result = json.dumps({"game_id": "batch-t1-s1", "status": "finished"})
    assert _played_game(progress) == "batch-t1-s1"
    assert _reported_game(progress) is None  # a played game is not a closed game
    assert _reported_game(result) == "batch-t1-s1"
    assert _played_game(result) is None
    assert _played_game("not json") is None and _played_game('{"event": "played"}') is None


def test_the_batch_cli_prints_progress_before_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio import play_batch

    def fake(_folder, _decks, series_games, *, on_game, on_played, **_kwargs):  # type: ignore[no-untyped-def]
        for game in series_games:
            on_played(game.game_id)
        summaries = [{"game_id": g.game_id, "status": "finished"} for g in series_games]
        for summary in summaries:
            on_game(summary)
        return summaries

    monkeypatch.setattr(play_batch, "play_recorded_games", fake)
    code = studio_main(
        [
            "--data",
            str(tmp_path),
            "play-batch",
            "--deck",
            "a.json",
            "--game",
            "1:g1",
            "--game",
            "2:g2",
        ]
    )
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert code == 0
    assert lines == [
        {"event": "played", "played_game_id": "g1"},
        {"event": "played", "played_game_id": "g2"},
        {"game_id": "g1", "status": "finished"},
        {"game_id": "g2", "status": "finished"},
    ]


class _FakeProcess:
    """A ``play-batch`` child: the lines it printed, in order."""

    def __init__(self, lines: list[str]) -> None:
        self.stdout = iter(lines)

    def wait(self) -> int:
        return 0

    def poll(self) -> int:
        return 0

    def terminate(self) -> None:  # pragma: no cover - not reached
        pass

    def kill(self) -> None:  # pragma: no cover - not reached
        pass


def test_a_series_counts_played_games_before_their_results_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import simulations

    batch = _batch(tmp_path, [1, 2, 3, 4], lambda seeds: iter(()), workers=1, games_per_jvm=4)
    lines = [
        json.dumps({"event": "played", "played_game_id": "batch-t1-s1"}),
        json.dumps({"event": "played", "played_game_id": "batch-t1-s2"}),
        json.dumps({"event": "played", "played_game_id": "batch-other-s9"}),  # not this series
        json.dumps({"game_id": "batch-t1-s1", "status": "finished"}),
        json.dumps({"game_id": "batch-t1-s2", "status": "finished"}),
    ]
    monkeypatch.setattr(simulations.subprocess, "Popen", lambda *_a, **_k: _FakeProcess(lines))
    monkeypatch.setattr(
        simulations,
        "extract_game_log_telemetry",
        lambda _folder, game_id, candidate_seat=0: GameSummary(
            game_id=game_id, seed=int(game_id.rsplit("-s", 1)[1]), status="finished"
        ),
    )
    stream = batch._process_chunk([1, 2, 3, 4], tmp_path / "deck.json")
    first = next(stream)  # the first result line comes after both progress lines
    data = batch.to_dict()
    assert first.game_id == "batch-t1-s1"
    assert data["games_played"] == 2 and data["games_completed"] == 0
    assert data["games_planned"] == 4
    list(stream)  # the rest of the chunk: seeds 3 and 4 never reported, so they fail
    assert batch.to_dict()["games_played"] == 2


def test_a_played_game_that_ends_as_a_failed_row_is_not_counted_twice(tmp_path: Path) -> None:
    """A cancelled series leaves the logs of announced games open: they end as ``Cancelled`` rows."""
    batch = _batch(
        tmp_path, list(range(1, 11)), lambda seeds: iter(()), workers=1, games_per_jvm=10
    )
    for seed in range(1, 6):
        batch.mark_played(batch.game_id_of(seed))
    for seed in range(1, 7):  # the five announced games and the one in progress
        batch._add_game(batch._failed(seed, "Cancelled", "The series was cancelled"))
    data = batch.to_dict()
    assert data["games_played"] == 0 and data["games_failed"] == 6
    assert data["games_played"] + data["games_failed"] <= data["games_planned"]  # type: ignore[operator]
    # a game that has a finished row stays played even if an id also has a failed row
    batch.mark_played(batch.game_id_of(7))
    batch._add_game(_finished(batch, 7, [0]))
    assert batch.to_dict()["games_played"] == 1


def test_games_played_covers_resumed_games_and_never_counts_failures(tmp_path: Path) -> None:
    done = GameSummary(game_id="batch-t1-s1", seed=1, status="finished", winner_seats=[0])
    broken = GameSummary(game_id="batch-t1-s2", seed=2, status="failed", failure_class="X")
    batch = _batch(
        tmp_path,
        [1, 2, 3],
        lambda seeds: iter(()),
        workers=1,
        games_per_jvm=3,
        initial_games=[done, broken],
    )
    assert (
        batch.to_dict()["games_played"] == 1
    )  # resumed finished game; the failed one was not played
    batch.mark_played("batch-t1-s3")
    batch.mark_played("batch-t1-s3")  # announced twice: counted once
    batch.mark_played("batch-t1-s99")  # not a game of this series
    data = batch.to_dict()
    assert data["games_played"] == 2 and data["games_failed"] == 1
    assert data["games_played"] <= data["games_planned"]


def test_stored_seed_list_in_series_record(tmp_path: Path) -> None:
    """The saved series record stores the explicit seed list in top-level seeds field."""
    batch = _batch(tmp_path, [10, 20, 30], lambda seeds: iter(()), workers=1, games_per_jvm=3)
    batch.run_worker()
    data = batch.to_dict()
    assert data["seeds"] == [10, 20, 30]
    series_json = tmp_path / "games" / "t1.series.json"
    assert series_json.is_file()
    saved = json.loads(series_json.read_text(encoding="utf-8"))
    assert saved["seeds"] == [10, 20, 30]


def test_resuming_an_interrupted_series_runs_only_remaining_seeds(tmp_path: Path) -> None:
    """An interrupted series is resumed: already finished games are not re-executed."""
    seen_seeds: list[list[int]] = []

    def first_run(seeds: Sequence[int]) -> Iterator[GameSummary]:
        seen_seeds.append(list(seeds))
        for seed in seeds:
            if seed == 2:
                # Interrupted / killed at seed 2
                raise RuntimeError("simulated crash")
            yield _finished(batch1, seed, [0])

    batch1 = _batch(tmp_path, [1, 2, 3, 4], first_run, workers=1, games_per_jvm=4)
    batch1.run_worker()
    assert any(g.seed == 1 and g.status == "finished" for g in batch1._games)
    assert any(g.seed == 2 and g.status == "failed" for g in batch1._games)

    # Resume the batch: only remaining seeds (2, 3, 4) should be planned
    resumed_seen: list[list[int]] = []

    def second_run(seeds: Sequence[int]) -> Iterator[GameSummary]:
        resumed_seen.append(list(seeds))
        for seed in seeds:
            yield _finished(batch2, seed, [0])

    batch2 = BatchSimulation(
        "t1",
        tmp_path,
        "chulane",
        "rev",
        "precon",
        [],
        [1, 2, 3, 4],
        chunk_runner=second_run,
        initial_games=[g for g in batch1._games if g.status == "finished"],
        workers=1,
        games_per_jvm=4,
    )
    assert batch2.chunks == [[2, 3, 4]]  # seed 1 was not re-planned!
    batch2.run_worker()

    assert batch2.status == "completed"
    assert resumed_seen == [[2, 3, 4]]
    # All 4 games are in the final batch in seed order
    assert [g.seed for g in batch2._games] == [1, 2, 3, 4]
    assert all(g.status == "finished" for g in batch2._games)
    assert batch2.to_dict()["games_completed"] == 4


def test_resuming_a_completed_series_does_no_work(tmp_path: Path) -> None:
    """Resuming a fully completed batch plans no chunks and finishes immediately."""
    runs = 0

    def runner(seeds: Sequence[int]) -> Iterator[GameSummary]:
        nonlocal runs
        runs += 1
        for seed in seeds:
            yield _finished(batch, seed, [0])

    finished_games = [
        GameSummary(game_id=f"batch-c1-s{s}", seed=s, status="finished", winner_seats=[0])
        for s in (1, 2)
    ]
    batch = BatchSimulation(
        "c1",
        tmp_path,
        "chulane",
        "rev",
        "precon",
        [],
        [1, 2],
        chunk_runner=runner,
        initial_games=finished_games,
        workers=1,
        games_per_jvm=2,
    )
    assert batch.chunks == []
    assert batch.status == "completed"
    batch.run_worker()
    assert runs == 0
    assert batch.to_dict()["games_completed"] == 2


def test_web_api_resume_endpoint(tmp_path: Path) -> None:
    """Web API POST /api/simulations/batch/{batch_id}/resume triggers resumption."""
    StudioStore.open(tmp_path).close()
    client = TestClient(create_app(tmp_path))

    # Try resuming unknown batch -> 404
    res = client.post("/api/simulations/batch/unknown-batch-123/resume", headers={"X-Studio": "1"})
    assert res.status_code == 404


def _write_game_log(data: Path, batch_id: str, seed: int, status: str) -> None:
    folder = data / "games"
    folder.mkdir(parents=True, exist_ok=True)
    game_id = f"batch-{batch_id}-s{seed}"
    entries = [
        {"kind": "header", "schema": "studio-game-log-1", "game_id": game_id, "seed": seed},
        {"kind": "frame", "turn": 3, "seat": 0, "players": [{"hand": []}]},
        {
            "kind": "result",
            "status": status,
            "winner_seats": [0] if status == "finished" else [],
            "decision_count": 42,
        },
    ]
    (folder / f"{game_id}.jsonl").write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8"
    )


def _write_series_record(
    data: Path, batch_id: str, *, with_seeds: bool, with_opponents: bool = True
) -> None:
    folder = data / "games"
    folder.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {
        "batch_id": batch_id,
        "deck_id": "chulane",
        "revision_id": "current",
        "pod": "precon",
        "status": "failed",
        "execution": {"workers": 1, "games_per_jvm": 1, "chunks": [[1, 2, 3]]},
        "games": [
            {"game_id": f"batch-{batch_id}-s{s}", "seed": s, "status": "finished"}
            for s in (1, 2, 3)
        ],
    }
    if with_seeds:
        record["seeds"] = [1, 2, 3]
    if with_opponents:  # since #1658 a record names its opponents
        record["opponent_ids"] = list(launch.POD_PRESETS["precon"])
    (folder / f"{batch_id}.series.json").write_text(json.dumps(record), encoding="utf-8")


def test_from_saved_series_takes_over_finished_games_from_disk(tmp_path: Path) -> None:
    """Disk resume: a game whose log says finished is taken over, not re-planned."""
    _write_series_record(tmp_path, "d1", with_seeds=True)
    _write_game_log(tmp_path, "d1", 1, "finished")
    _write_game_log(tmp_path, "d1", 2, "failed")

    batch = BatchSimulation.from_saved_series(tmp_path, "d1", chunk_runner=lambda seeds: iter(()))
    assert [game.seed for game in batch._games] == [1]
    assert batch._games[0].winner_seats == [0]
    assert batch._games[0].decision_count == 42
    assert sorted(seed for chunk in batch.chunks for seed in chunk) == [2, 3]


def test_from_saved_series_reads_legacy_record_without_seeds_field(tmp_path: Path) -> None:
    """Records written before the seeds field fall back to the execution chunks."""
    _write_series_record(tmp_path, "d2", with_seeds=False)
    _write_game_log(tmp_path, "d2", 1, "finished")
    _write_game_log(tmp_path, "d2", 2, "failed")

    batch = BatchSimulation.from_saved_series(tmp_path, "d2", chunk_runner=lambda seeds: iter(()))
    assert batch.seeds == [1, 2, 3]
    assert [game.seed for game in batch._games] == [1]
    assert sorted(seed for chunk in batch.chunks for seed in chunk) == [2, 3]


def test_from_saved_series_unknown_batch_raises_key_error(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        BatchSimulation.from_saved_series(tmp_path, "nope", chunk_runner=lambda seeds: iter(()))


def test_from_saved_series_refuses_a_record_without_its_opponents(tmp_path: Path) -> None:
    """#1658: a record of before the opponent fix (its games ran against a stand-in table)
    is not resumed against another table; one series never mixes two tables."""
    _write_series_record(tmp_path, "d0", with_seeds=True, with_opponents=False)
    with pytest.raises(ValueError, match="nicht fortsetzbar"):
        BatchSimulation.from_saved_series(tmp_path, "d0", chunk_runner=lambda seeds: iter(()))


def test_from_saved_series_rejects_a_corrupt_record(tmp_path: Path) -> None:
    """A corrupt record raises a clear ValueError, not a raw JSONDecodeError."""
    folder = tmp_path / "games"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "d3.series.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt series record"):
        BatchSimulation.from_saved_series(tmp_path, "d3", chunk_runner=lambda seeds: iter(()))


def test_resume_batch_rebuilds_from_disk_and_finishes_the_rest(tmp_path: Path) -> None:
    """Manager resume: the finished game is kept, the rest is played, record rewritten."""
    _write_series_record(tmp_path, "d4", with_seeds=True)
    _write_game_log(tmp_path, "d4", 1, "finished")
    _write_game_log(tmp_path, "d4", 2, "failed")
    decks = tmp_path / "games" / "decks"
    decks.mkdir(parents=True, exist_ok=True)
    (decks / "current.json").write_text("{}", encoding="utf-8")

    def runner(seeds: Sequence[int]) -> Iterator[GameSummary]:
        for seed in seeds:
            yield GameSummary(
                game_id=f"batch-d4-s{seed}", seed=seed, status="finished", winner_seats=[0]
            )

    store = StudioStore.open(tmp_path)
    try:
        manager = SimulationBatchManager()
        batch = manager.resume_batch(store, tmp_path, "d4", chunk_runner=runner)
        for _ in range(50):
            if batch.status not in ("pending", "running"):
                break
            time.sleep(0.1)
    finally:
        store.close()
    assert batch.status == "completed"
    assert sorted(game.seed for game in batch._games) == [1, 2, 3]
    saved = json.loads((tmp_path / "games" / "d4.series.json").read_text(encoding="utf-8"))
    assert saved["seeds"] == [1, 2, 3]
    assert saved["games_completed"] == 3


def test_resume_batch_refuses_an_active_batch(tmp_path: Path) -> None:
    """Resuming a batch that is still active raises instead of starting twice."""
    store = StudioStore.open(tmp_path)
    try:
        manager = SimulationBatchManager()
        running = BatchSimulation(
            "d5",
            tmp_path,
            "chulane",
            "current",
            "precon",
            [],
            [1],
            chunk_runner=lambda seeds: iter(()),
        )
        running.status = "running"
        manager._batches["d5"] = running
        with pytest.raises(RuntimeError, match="already active"):
            manager.resume_batch(store, tmp_path, "d5", chunk_runner=lambda seeds: iter(()))
    finally:
        store.close()


def test_web_api_get_batch_falls_back_to_the_saved_record(tmp_path: Path) -> None:
    """A batch that is not in memory is served from its saved series record."""
    StudioStore.open(tmp_path).close()
    _write_series_record(tmp_path, "d6", with_seeds=True)
    client = TestClient(create_app(tmp_path))
    res = client.get("/api/simulations/batch/d6", headers={"X-Studio": "1"})
    assert res.status_code == 200
    assert res.json()["batch_id"] == "d6"


def test_web_api_resume_of_a_running_batch_conflicts(tmp_path: Path) -> None:
    """Resuming a batch that is still active answers 409, not a second run."""
    StudioStore.open(tmp_path).close()
    client = TestClient(create_app(tmp_path))
    running = BatchSimulation(
        "d7",
        tmp_path,
        "chulane",
        "current",
        "precon",
        [],
        [1],
        chunk_runner=lambda seeds: iter(()),
    )
    running.status = "running"
    simulation_manager._batches["d7"] = running
    try:
        res = client.post("/api/simulations/batch/d7/resume", headers={"X-Studio": "1"})
        assert res.status_code == 409
    finally:
        simulation_manager._batches.pop("d7", None)


def test_web_api_corrupt_series_record_is_a_clean_client_error(tmp_path: Path) -> None:
    """A corrupt saved record answers 422 on both paths, not an unhandled 500."""
    StudioStore.open(tmp_path).close()
    folder = tmp_path / "games"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "d8.series.json").write_text("{not json", encoding="utf-8")
    client = TestClient(create_app(tmp_path))
    res = client.get("/api/simulations/batch/d8", headers={"X-Studio": "1"})
    assert res.status_code == 422
    res = client.post("/api/simulations/batch/d8/resume", headers={"X-Studio": "1"})
    assert res.status_code == 422


def test_recording_runner_uses_public_hooks_with_identical_transcript_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1731: ``_RecordingRunner`` records frames via ``decision_policy`` and exports the event
    log via ``after_drive`` while preserving identical transcript hashes vs the bare runner."""
    from commander_lab.candidates.models import FutureXmageScenario
    from commander_lab.engine.rules import full_game
    from commander_lab.studio.play import _RecordingRunner

    commit = "b" * 40
    decision: dict[str, object] = {
        "decision_id": "rec-d1",
        "actor_id": "p0",
        "decision_class": "priority",
        "seat": 0,
        "legal_options": [{"option_id": "pass", "label": "Pass", "option_type": "pass"}],
        "pilot_state": {
            "seat": 0,
            "turn_number": 1,
            "phase": "main1",
            "step": "precombat_main",
            "players": [
                {
                    "player_id": "p0",
                    "seat": 0,
                    "is_actor": True,
                    "life": 40,
                    "hand": [],
                    "battlefield": [],
                    "graveyard": [],
                },
                {
                    "player_id": "p1",
                    "seat": 1,
                    "is_actor": False,
                    "life": 40,
                    "hand_count": 7,
                    "battlefield": [],
                    "graveyard": [],
                },
            ],
        },
    }
    raw_result: dict[str, object] = {
        "evidence_class": full_game.FULL_GAME_EVIDENCE_CLASS,
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
        "official_campaign_eligible": False,
        "rules_authority": "xmage",
        "decision_policy_authority": "commander_lab_external_pilot",
        "bit_exact_replay_validated": False,
        "seed": 42,
        "turn_number": 1,
        "decision_count": 1,
        "terminal": True,
        "transcript": [
            {
                "sequence": 1,
                "kind": "decision",
                "decision_class": "priority",
                "actor_seat": 0,
                "prompt": "Pass",
                "selected_option_types": ["pass"],
                "selected_option_labels": ["Pass"],
                "numeric_choice": None,
            }
        ],
        "outcomes": [
            {"seat": 0, "life": 40, "won": True, "lost": False, "left": False},
            {"seat": 1, "life": 0, "won": False, "lost": True, "left": False},
        ],
    }

    class _FakeClient:
        requests: list[str]

        def __init__(self, *_a: object, **_k: object) -> None:
            self.requests = []
            self.shutdown_disposition: str | None = None

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *_a: object) -> None:
            self.shutdown_disposition = full_game.FULL_GAME_SHUTDOWN_GRACEFUL

        def request(self, op: str, _payload: object = None) -> dict[str, object]:
            self.requests.append(op)
            if op == "start_full_game":
                return {"decision": decision}
            if op == "submit_full_game_decision":
                return {"terminal": True}
            if op == "export_event_log":
                return {"events": [{"sequence": 1, "turn": 1, "step": "MAIN1", "kind": "pass"}]}
            if op == "get_full_game_result":
                return raw_result
            return {}

    class _PassPolicy:
        def decide(self, req: dict[str, object]) -> dict[str, object]:
            return {"decision_id": req["decision_id"], "selected_option_ids": ["pass"]}

    scenario = FutureXmageScenario(
        candidate_id="deck-a",
        deck_hash="d" * 64,
        opponent_deck_ids=("deck-b",),
        player_count=2,
        seat=1,
        scenario_id="rec-sc",
        seed=42,
        xmage_commit=commit,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    provider = {"engine_version": "1.4.61", "engine_commit": commit}
    monkeypatch.setattr(full_game, "_RawFullGameClient", _FakeClient)

    bare = full_game.XmageFullGameRunner(("java", "-jar", "x.jar", "full-game"))
    monkeypatch.setattr(bare, "_validated_policy", lambda *_a: _PassPolicy())
    monkeypatch.setattr(bare, "_open_game", lambda *_a, **_k: provider)
    bare_res = bare.run(scenario=scenario, decks=(), pilots=())

    rec_runner = _RecordingRunner(("java", "-jar", "x.jar", "full-game"))
    monkeypatch.setattr(rec_runner, "_validated_policy", lambda *_a: _PassPolicy())
    monkeypatch.setattr(rec_runner, "_open_game", lambda *_a, **_k: provider)
    recorder = games.GameRecorder(
        tmp_path,
        "rec-eq-1",
        {"seed": 42, "seats": [{"seat": 1, "pilot": "AI"}, {"seat": 2, "pilot": "AI"}]},
    )
    rec_runner.recorder = recorder
    rec_res = rec_runner.run(scenario=scenario, decks=(), pilots=())
    recorder.close({"status": "finished", "winner_seats": list(rec_res.winner_seats)})

    assert rec_res.semantic_transcript_sha256 == bare_res.semantic_transcript_sha256
    assert rec_res.raw_result_sha256 == bare_res.raw_result_sha256
    stored = games.read_game(tmp_path, "rec-eq-1", start=0, count=5)
    assert stored["total"] == 1
    result_entry = stored["result"]
    assert isinstance(result_entry, dict)
    assert result_entry["event_log"] == [
        {"sequence": 1, "turn": 1, "step": "MAIN1", "kind": "pass"}
    ]


def test_batch_recording_runner_opt_in_pilot_audit_invariance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1524: BatchRecordingRunner leaves games/ untouched and creates no pilot_audit/ when OFF;
    when record_pilot_audit=True, wraps policy transparently without altering transcript/raw hash
    or game log content and writes audit separately under pilot_audit/."""
    from commander_lab.candidates.models import FutureXmageScenario
    from commander_lab.engine.rules import full_game
    from commander_lab.qualification.current_boundary.bridge_launcher import (
        canonical_xmage_engine_pin,
    )
    from commander_lab.studio import pilot_audit
    from commander_lab.studio.play_batch import BatchRecordingRunner

    commit = canonical_xmage_engine_pin()
    decision = {
        "decision_id": "d-audit-1",
        "decision_class": "priority",
        "seat": 0,
        "actor_id": "p0",
        "prompt": "Main 1",
        "legal_options": [
            {"option_id": "land-1", "option_type": "play_land", "label": "Play Forest"},
            {"option_id": "pass", "option_type": "pass", "label": "Pass"},
        ],
        "pilot_state": {
            "seat": 0,
            "actor_id": "p0",
            "active_player_id": "p0",
            "turn_number": 1,
            "phase": "precombat_main",
            "step": "precombat_main",
            "players": [{"player_id": "p0", "is_actor": True, "command": []}],
        },
    }
    raw_result: dict[str, object] = {
        "evidence_class": full_game.FULL_GAME_EVIDENCE_CLASS,
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
        "official_campaign_eligible": False,
        "rules_authority": "xmage",
        "decision_policy_authority": "commander_lab_external_pilot",
        "bit_exact_replay_validated": False,
        "seed": 77,
        "turn_number": 1,
        "decision_count": 1,
        "terminal": True,
        "transcript": [
            {
                "sequence": 1,
                "kind": "decision",
                "decision_class": "priority",
                "actor_seat": 0,
                "prompt": "Pass",
                "selected_option_types": ["pass"],
                "selected_option_labels": ["Pass"],
                "numeric_choice": None,
            }
        ],
        "outcomes": [
            {"seat": 0, "life": 40, "won": True, "lost": False, "left": False},
            {"seat": 1, "life": 0, "won": False, "lost": True, "left": False},
        ],
    }

    class _FakeClient:
        def __init__(self, *_a: object, **_k: object) -> None:
            self.shutdown_disposition: str | None = None

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *_a: object) -> None:
            self.shutdown_disposition = full_game.FULL_GAME_SHUTDOWN_GRACEFUL

        def request(self, op: str, _payload: object = None) -> dict[str, object]:
            if op == "start_full_game":
                return {"decision": decision}
            if op == "submit_full_game_decision":
                return {"terminal": True}
            if op == "export_event_log":
                return {"events": [{"sequence": 1, "turn": 1, "step": "MAIN1", "kind": "pass"}]}
            if op == "get_full_game_result":
                return raw_result
            return {}

    class _PassPolicy:
        def decide(self, req: dict[str, object]) -> dict[str, object]:
            return {"decision_id": req["decision_id"], "selected_option_ids": ["pass"]}

    scenario = FutureXmageScenario(
        candidate_id="deck-a",
        deck_hash="d" * 64,
        opponent_deck_ids=("deck-b",),
        player_count=2,
        seat=1,
        scenario_id="batch-audit-sc",
        seed=77,
        xmage_commit=commit,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    provider = {"engine_version": "1.4.61", "engine_commit": commit}
    monkeypatch.setattr(full_game, "_RawFullGameClient", _FakeClient)

    # Mirror real play.prepare_game() headers, which omit data_class until recording.
    header: dict[str, object] = {
        "seed": 77,
        "seats": [{"seat": 0, "pilot": "KI"}, {"seat": 1, "pilot": "KI"}],
    }

    # Audit OFF (default)
    dir_off = tmp_path / "off"
    runner_off = BatchRecordingRunner(
        dir_off,
        {"batch-audit-sc": ("g-audit-1", dict(header))},
        command=("java", "-jar", "x.jar", "full-game"),
    )
    monkeypatch.setattr(runner_off, "_validated_policy", lambda *_a: _PassPolicy())
    monkeypatch.setattr(runner_off, "_open_game", lambda *_a, **_k: provider)
    res_off = runner_off.run(scenario=scenario, decks=(), pilots=())
    runner_off.recorder_of("batch-audit-sc").close(
        {"status": "finished", "winner_seats": list(res_off.winner_seats)}
    )
    assert not pilot_audit.pilot_audit_folder(dir_off, create=False).exists()

    # Audit ON
    dir_on = tmp_path / "on"
    runner_on = BatchRecordingRunner(
        dir_on,
        {"batch-audit-sc": ("g-audit-1", dict(header))},
        command=("java", "-jar", "x.jar", "full-game"),
        record_pilot_audit=True,
    )
    monkeypatch.setattr(runner_on, "_validated_policy", lambda *_a: _PassPolicy())
    monkeypatch.setattr(runner_on, "_open_game", lambda *_a, **_k: provider)
    res_on = runner_on.run(scenario=scenario, decks=(), pilots=())
    runner_on.recorder_of("batch-audit-sc").close(
        {"status": "finished", "winner_seats": list(res_on.winner_seats)}
    )
    om_summary = runner_on.close_audit_game("batch-audit-sc", res_on)

    # Identical game result hashes & counts
    assert res_on.semantic_transcript_sha256 == res_off.semantic_transcript_sha256
    assert res_on.raw_result_sha256 == res_off.raw_result_sha256
    assert res_on.winner_seats == res_off.winner_seats
    assert res_on.decision_count == res_off.decision_count

    # Separate audit file written with 1/1 land omission
    assert om_summary is not None
    assert om_summary["series"]["display"] == "1/1"
    audit_path = pilot_audit.audit_log_path(dir_on, "g-audit-1")
    assert audit_path is not None
    assert audit_path.parent == dir_on / "pilot_audit"
    assert games.list_games(dir_on)[0]["game_id"] == "g-audit-1"
