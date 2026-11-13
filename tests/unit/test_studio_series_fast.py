"""Studio series: several games per bridge JVM on several workers, one game each.

A fake chunk runner and a fake engine stand in for the real one; the real-engine identity
check is ``scripts/check_studio_series_identity.py``.
"""

from __future__ import annotations

import json
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
from commander_lab.studio.simulations import BatchSimulation, GameSummary, plan_chunks
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
    assert 1 <= workers <= 4 and per_jvm == 6
    assert launch.checked_series_settings(16, 24) == (16, 24)
    for bad in ((0, 6), (17, 6), (2, 0), (2, 25)):
        with pytest.raises(ValueError):
            launch.checked_series_settings(*bad)


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
