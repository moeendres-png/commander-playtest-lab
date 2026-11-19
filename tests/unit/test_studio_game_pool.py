"""The series game pool: worker processes with long-lived JVMs, JSON lines over pipes (#1585).

The worker processes here are real processes (``python worker.py``) that play with a scripted
engine, so the pipe protocol, the reuse of a worker over several runs (look windows), a worker
that dies in a game, cancelling and the wall limit are exercised as they run in a series. The real
engine is not involved: those checks are NOT_RUN in this file (``scripts/check_studio_series_
identity.py`` is the real-engine identity check).
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import textwrap
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest

from commander_lab.engine.rules import full_game_series
from commander_lab.engine.rules.full_game_series import build_series_result, checked_shutdown_ack
from commander_lab.studio import game_pool
from commander_lab.studio.game_pool import GamePool, GamePoolError, GameTask, worker_main

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "data/decks/deckbau/chulane_current.json"
PRECONS = [
    ROOT / "data/decks/precons/2026_lorehold_spirit.json",
    ROOT / "data/decks/precons/2024_animated_army.json",
    ROOT / "data/decks/precons/2022_token_triumph.json",
]

_WORKER = textwrap.dedent(
    '''
    import hashlib, os, sys, time
    from pathlib import Path
    from commander_lab.studio.game_pool import worker_main
    from commander_lab.studio.games import games_folder

    DATA = Path(sys.argv[2])
    BUDGET = int(sys.argv[3])

    class Engine:
        """Plays by script: a game is a function of its seed and decks, never of the worker."""

        def __init__(self):
            self.lives = []
            self.life = None

        def play(self, message, on_played):
            game_id = message["game_id"]
            if self.life is None or self.life["games"] >= BUDGET:
                if self.life is not None:
                    self.life["end"] = "budget"
                self.life = {
                    "life_id": f"{sys.argv[1]}-{len(self.lives) + 1}",
                    "games": 0, "end": "open", "disposition": None,
                }
                self.lives.append(self.life)
            if "crash" in game_id:
                # the worker dies in a game, with a log that has no closing entry
                games_folder(DATA).joinpath(game_id + ".jsonl").write_text(
                    '{"kind":"header"}\\n', encoding="utf-8")
                os._exit(3)
            if "hang" in game_id:
                time.sleep(3600)
            digest = hashlib.sha256(
                (str(message["seed"]) + "|" + "|".join(message["deck_paths"])).encode()
            ).hexdigest()
            self.life["games"] += 1
            on_played()
            return {
                "game_id": game_id, "status": "finished", "winner_seats": [message["seed"] % 4],
                "decision_count": 40 + message["seed"], "semantic_transcript_sha256": digest,
                "jvm_life_id": self.life["life_id"], "position_in_jvm": self.life["games"],
                "pid": os.getpid(),
            }

        def ended_lives(self):
            return [dict(life) for life in self.lives if life["end"] != "open"]

        def close(self):
            if self.life is not None and self.life["end"] == "open":
                self.life["end"] = "series_closed"
                self.life["disposition"] = "graceful_shutdown"

    sys.exit(worker_main(stdin=sys.stdin, stdout=sys.stdout, label=sys.argv[1],
                         engine_factory=Engine))
    '''
)


def _pool(
    tmp_path: Path, *, workers: int, budget: int = 4, wall: float = 60.0
) -> tuple[GamePool, Path]:
    script = tmp_path / "worker.py"
    script.write_text(_WORKER, encoding="utf-8")
    (tmp_path / "games").mkdir(exist_ok=True)

    def argv(label: str) -> list[str]:
        return [sys.executable, str(script), label, str(tmp_path), str(budget)]

    pool = GamePool(tmp_path, workers=workers, worker_argv=argv, game_wall_limit_seconds=wall)
    return pool, script


def _tasks(seeds: range, table: str = "t") -> list[GameTask]:
    return [
        GameTask(
            task_id=f"{table}:{seed}",
            seed=seed,
            game_id=f"g-{table}-s{seed}",
            deck_paths=(f"{table}-a.json", f"{table}-b.json"),
        )
        for seed in seeds
    ]


def _expected_hash(task: GameTask) -> str:
    return hashlib.sha256((str(task.seed) + "|" + "|".join(task.deck_paths)).encode()).hexdigest()


def test_workers_and_their_jvms_live_across_runs_and_a_game_does_not_depend_on_its_worker(
    tmp_path: Path,
) -> None:
    window1 = _tasks(range(1, 9), "base") + _tasks(range(1, 9), "variant")
    window2 = _tasks(range(9, 17), "base") + _tasks(range(9, 17), "variant")
    done_order: list[str] = []
    pool, _ = _pool(tmp_path, workers=3, budget=4)
    with pool:
        first = pool.run(window1, on_done=lambda task, _s: done_order.append(task.task_id))
        started_after_first = pool.summary()["worker_processes_started"]
        second = pool.run(window2)
        started_after_second = pool.summary()["worker_processes_started"]
    summaries = {**first, **second}

    assert len(summaries) == 32 and set(summaries) == {t.task_id for t in window1 + window2}
    # same process pool for both windows: no worker was started for the second one
    assert started_after_first == started_after_second == 3
    for task in window1 + window2:
        got = summaries[task.task_id]
        assert got["status"] == "finished"
        assert got["semantic_transcript_sha256"] == _expected_hash(task)
    # the 3 workers played 32 games in JVM lives of at most 4 games: the lives span the windows
    lives = pool.summary()["jvm_lives"]
    assert isinstance(lives, list)
    assert sum(int(life["games"]) for life in lives) == 32  # type: ignore[call-overload]
    assert max(int(life["games"]) for life in lives) == 4  # type: ignore[call-overload]
    # 32 games at 4 per JVM need 8 lives; dynamic hand-out leaves at most one part-full life each
    assert 8 <= len(lives) <= 8 + 3
    # and a JVM life spans the look-window boundary: it played games of both windows
    assert {s["jvm_life_id"] for s in first.values()} & {s["jvm_life_id"] for s in second.values()}
    assert len(done_order) == 16


def test_the_result_of_a_game_is_the_same_for_one_worker_and_for_several(tmp_path: Path) -> None:
    tasks = _tasks(range(1, 11))
    by_workers: list[dict[str, object]] = []
    for count in (1, 4):
        folder = tmp_path / f"w{count}"
        folder.mkdir()
        pool, _ = _pool(folder, workers=count, budget=3)
        with pool:
            results = pool.run(tasks)
        by_workers.append(
            {
                task_id: (s["semantic_transcript_sha256"], s["winner_seats"], s["decision_count"])
                for task_id, s in results.items()
            }
        )
    assert by_workers[0] == by_workers[1] and len(by_workers[0]) == 10


def test_a_worker_that_dies_in_a_game_fails_that_game_closes_its_log_and_the_rest_goes_on(
    tmp_path: Path,
) -> None:
    pool, _ = _pool(tmp_path, workers=1, budget=8)
    tasks = [*_tasks(range(1, 3)), _tasks(range(3, 4), "crash")[0], *_tasks(range(4, 6))]
    done: list[tuple[str, object]] = []
    with pool:
        results = pool.run(tasks, on_done=lambda t, s: done.append((t.task_id, s["status"])))
        info = pool.summary()

    assert [status for _id, status in done] == [
        "finished",
        "finished",
        "failed",
        "finished",
        "finished",
    ]
    lost = results["crash:3"]
    assert lost["failure_class"] == "WorkerExited"
    # the unclosed log is closed with the failure, so it does not read as a game still running
    games = tmp_path / "games"
    assert not (games / "g-crash-s3.jsonl").exists()
    packed = games / "g-crash-s3.jsonl.gz"
    with gzip.open(packed, "rt", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    assert json.loads(lines[-1])["failure_class"] == "WorkerExited"
    assert (info["games_finished"], info["games_failed"], info["worker_processes_started"]) == (
        4,
        1,
        2,
    )


def test_cancelling_stops_handing_out_games_and_keeps_what_ended(tmp_path: Path) -> None:
    pool, _ = _pool(tmp_path, workers=1, budget=8)
    seen: list[str] = []

    def cancel() -> bool:
        return len(seen) >= 2

    with pool:
        results = pool.run(
            _tasks(range(1, 10)),
            on_done=lambda task, _s: seen.append(task.task_id),
            should_cancel=cancel,
        )
    # one worker, one game in flight: the games that ended are kept, the rest was never handed out
    assert set(results) == set(seen) and 2 <= len(results) < 9


def test_a_worker_that_cannot_start_is_a_pool_error_not_a_failed_game(tmp_path: Path) -> None:
    pool = GamePool(
        tmp_path,
        workers=1,
        worker_argv=lambda _label: [sys.executable, "-c", "import sys; sys.exit(2)"],
    )
    with pytest.raises(GamePoolError, match="ended before it was ready"):
        pool.run(_tasks(range(1, 3)))
    pool.close()


def test_a_game_that_never_ends_is_given_up_at_the_wall_limit(tmp_path: Path) -> None:
    pool, _ = _pool(tmp_path, workers=1, budget=8, wall=1.5)
    tasks = [_tasks(range(1, 2), "hang")[0], *_tasks(range(2, 3))]
    with pool:
        results = pool.run(tasks)
    assert results["hang:1"]["failure_class"] == "TimeLimit"
    assert results["t:2"]["status"] == "finished"  # a fresh worker took the next game


def test_the_worker_loop_speaks_the_protocol_and_reports_each_jvm_life() -> None:
    class Engine:
        def __init__(self) -> None:
            self.lives: list[dict[str, object]] = []

        def play(self, message: Mapping[str, object], on_played: Callable[[], None]):  # type: ignore[no-untyped-def]
            if not self.lives or self.lives[-1]["end"] != "open":
                self.lives.append({"life_id": f"j{len(self.lives) + 1}", "games": 0, "end": "open"})
            self.lives[-1]["games"] = int(self.lives[-1]["games"]) + 1  # type: ignore[call-overload]
            on_played()
            if self.lives[-1]["games"] == 2:
                self.lives[-1]["end"] = "budget"  # the JVM is retired right after its last game
            return {"game_id": message["game_id"], "status": "finished"}

        def ended_lives(self) -> list[dict[str, object]]:
            return [dict(life) for life in self.lives if life["end"] != "open"]

        def close(self) -> None:
            if self.lives and self.lives[-1]["end"] == "open":
                self.lives[-1]["end"] = "series_closed"

    plays = [
        json.dumps({"op": "play", "task_id": f"t{n}", "seed": n, "game_id": f"g{n}"})
        for n in (1, 2, 3)
    ]
    out = io.StringIO()
    code = worker_main(
        stdin=io.StringIO("\n".join([*plays, json.dumps({"op": "retire"}), plays[0]]) + "\n"),
        stdout=out,
        label="w9",
        engine_factory=Engine,
    )
    events = [json.loads(line) for line in out.getvalue().splitlines()]
    assert code == 0
    assert [e["ev"] for e in events] == [
        "ready",
        "played",
        "done",
        "played",
        "jvm_exit",  # the first JVM reached its budget of 2 games with the second game
        "done",
        "played",
        "done",
        "jvm_exit",  # the second one ended with the series (nothing after retire was played)
        "bye",
    ]
    assert [e["end"] for e in events if e["ev"] == "jvm_exit"] == ["budget", "series_closed"]
    assert [e["task_id"] for e in events if e["ev"] == "done"] == ["t1", "t2", "t3"]


# --- the real worker engine, glue to the Studio's game logs; the series session is scripted -----


def _series_result(scenario: object, position: int):  # type: ignore[no-untyped-def]
    from commander_lab.engine.rules.full_game_pilot.common import FULL_GAME_EVIDENCE_CLASS

    seed = scenario.seed  # type: ignore[attr-defined]
    wire = {
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
        "official_campaign_eligible": False,
        "rules_authority": "xmage",
        "decision_policy_authority": "commander_lab_external_pilot",
        "bit_exact_replay_validated": False,
        "seed": seed,
        "terminal": True,
        "turn_number": 7,
        "decision_count": 11,
        "outcomes": [{"seat": i, "life": 5, "won": i == seed % 4} for i in range(4)],
        "transcript": [],
    }
    game_id = f"{scenario.scenario_id}:{scenario.candidate_id}:{seed}"  # type: ignore[attr-defined]
    ack = checked_shutdown_ack(
        {"game_id": game_id, "shut_down": True, "engine_thread_alive": False, "game_over": True},
        game_id=game_id,
    )
    from commander_lab.engine.rules.full_game import FullGameHiddenInformationAudit

    return build_series_result(
        scenario,  # type: ignore[arg-type]
        {"engine_version": "1.4.61", "engine_commit": "b" * 40},  # type: ignore[typeddict-item]
        wire,  # type: ignore[arg-type]
        ack,
        jvm_life_id="s-1",
        position_in_jvm=position,
        hidden_audit=FullGameHiddenInformationAudit(),
    )


def test_the_session_worker_engine_records_a_game_like_a_game_played_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"jar")
    monkeypatch.setenv(
        "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD",
        f"java -Dcommanderlab.fullGame.gamesPerJvm=2 -jar {jar} full-game",
    )

    class FakeSession:
        def __init__(self, runner: object, *, id_prefix: str = "") -> None:
            self.runner = runner
            self.position = 0
            self.lives = (SimpleNamespace(end="open", as_dict=lambda: {"life_id": "s-1"}),)

        def play(self, scenario: object, decks: object, pilots: object):  # type: ignore[no-untyped-def]
            recorder = self.runner._recorder_for(scenario)  # type: ignore[attr-defined]
            recorder.record(
                {"decision_class": "priority", "seat": 0, "legal_options": [], "pilot_state": {}},
                {},
            )
            self.runner.on_played(recorder.game_id)  # type: ignore[attr-defined]
            self.position += 1
            return _series_result(scenario, self.position)

        def close(self) -> tuple[object, ...]:
            return self.lives

    monkeypatch.setattr(full_game_series, "XmageFullGameSeriesSession", FakeSession)
    engine = game_pool.SessionWorkerEngine(
        tmp_path, label="s", private_card_repository=False, command=None
    )
    played: list[str] = []
    summary = engine.play(
        {
            "seed": 6,
            "game_id": "ser-base-s6-t0",
            "deck_paths": [str(DECK), *map(str, PRECONS)],
        },
        lambda: played.append("played"),
    )
    assert played == ["played"]
    assert summary["status"] == "finished" and summary["winner_seats"] == [2]
    assert summary["result_basis"] == "SHUTDOWN_GAME_ACK_NOT_PROCESS_EXIT"
    assert summary["jvm_life_id"] == "s-1" and summary["position_in_jvm"] == 1
    # the bridge jar is named in the game, exactly as for a game played alone
    assert summary["bridge_jar_sha256"] == hashlib.sha256(b"jar").hexdigest()
    from commander_lab.studio import games

    log = games.read_game(tmp_path, "ser-base-s6-t0", start=0, count=5)
    assert log["header"]["seed"] == 6  # type: ignore[index]
    assert log["result"]["result_basis"] == "SHUTDOWN_GAME_ACK_NOT_PROCESS_EXIT"  # type: ignore[index]
    # the setup of the next game does not see this game's header any more
    assert engine._headers == {}
