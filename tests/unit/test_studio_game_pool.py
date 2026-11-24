"""The series game pool: worker processes with long-lived JVMs, JSON lines over pipes (#1585).

The worker processes here are real processes (``python worker.py``) that play with a scripted
engine, so the pipe protocol, the reuse of a worker over several runs (look windows), a worker
that dies in a game, cancelling and the wall limit are exercised as they run in a series. The real
engine is not involved: those checks are NOT_RUN in this file (``scripts/check_studio_series_
identity.py`` is the real-engine identity check).
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import json
import queue
import re
import sys
import textwrap
import threading
from collections.abc import Callable, Mapping, Sequence
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
            if "crash" in game_id and "kid" not in game_id:
                # the worker dies in a game, with a log that has no closing entry
                games_folder(DATA).joinpath(game_id + ".jsonl").write_text(
                    '{"kind":"header"}\\n', encoding="utf-8")
                os._exit(3)
            if "kid" in game_id:
                # the worker starts a process of its own (as it starts its bridge JVM) ...
                import subprocess
                # (pipes of its own, like the JVM: it holds none of the worker's)
                kid = subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(3600)"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                DATA.joinpath("grandchild.pid").write_text(str(kid.pid), encoding="utf-8")
                if "crash" in game_id:
                    os._exit(3)  # ... and dies on its own, leaving it behind
            if "holder" in game_id:
                # a process in a session of its own that inherits the worker's stdout: the group
                # kill does not reach it, so the supervisor never sees the end of that stdout
                import subprocess
                holder = subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(3600)"],
                    stdin=subprocess.DEVNULL, start_new_session=True,
                )
                DATA.joinpath("holder.pid").write_text(str(holder.pid), encoding="utf-8")
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

    class Out:
        """The protocol stream; dies right after the ``done`` of an ``idle`` game (idle death)."""

        def __init__(self, stream):
            self.stream = stream
            self.last = ""

        def write(self, text):
            self.last = text
            return self.stream.write(text)

        def flush(self):
            self.stream.flush()
            if '"ev":"done"' in self.last and "idle" in self.last:
                os._exit(3)  # between two games: no task in flight, no ``bye``

    sys.exit(worker_main(stdin=sys.stdin, stdout=Out(sys.stdout), label=sys.argv[1],
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


_DECKS: list[Path] = []
JAR = "j" * 64
PIN = "p" * 40
NO_JVM_OPTIONS: dict[str, object] = {
    "nested_copy_skip": None,
    "env_options": {},
    "command_options": None,
}


@pytest.fixture(autouse=True)
def _deck_folder(tmp_path: Path) -> None:
    """The deck files of the scripted tasks; the worker checks each against its hash (S1)."""
    folder = tmp_path / "task-decks"
    folder.mkdir()
    _DECKS[:] = [folder]


def _deck_file(name: str) -> str:
    path = _DECKS[0] / name
    if not path.is_file():
        path.write_text(json.dumps({"deck": name}), encoding="utf-8")
    return str(path)


def _tasks(
    seeds: range, table: str = "t", *, styles: tuple[float, float] = (0.5, 0.5)
) -> list[GameTask]:
    return [
        game_pool.plan_task(
            task_id=f"{table}:{seed}",
            seed=seed,
            game_id=f"g-{table}-s{seed}",
            deck_paths=[_deck_file(f"{table}-a.json"), _deck_file(f"{table}-b.json")],
            seat_styles=list(styles),
            jar_sha256=JAR,
            engine_pin=PIN,
            skip_forced_decisions=True,
            jvm_options=NO_JVM_OPTIONS,
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
        json.dumps({**task.to_wire(), "task_id": f"t{n}", "game_id": f"g{n}"})
        for n, task in zip((1, 2, 3), _tasks(range(1, 4)), strict=True)
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
        {
            "game_id": game_id,
            "shut_down": True,
            "engine_thread_alive": False,
            "game_over": True,
            "shutdown_unwind": "none",
        },
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


def _own_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The worker's own pin is ``PIN`` and its environment sets no JVM option variable."""
    monkeypatch.setattr(game_pool, "own_engine_pin", lambda _folder: PIN)
    for name in game_pool.JVM_ENV_OPTION_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_the_session_worker_engine_records_a_game_like_a_game_played_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _own_configuration(monkeypatch)
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
    task = game_pool.plan_task(
        task_id="rec",
        seed=6,
        game_id="ser-base-s6-t0",
        deck_paths=[str(DECK), *map(str, PRECONS)],
        seat_styles=[0.5] * 4,
        jar_sha256=hashlib.sha256(b"jar").hexdigest(),
        engine_pin=PIN,
        skip_forced_decisions=None,
        jvm_options=NO_JVM_OPTIONS,
    )
    summary = engine.play(task.to_wire(), lambda: played.append("played"))
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


# --- P2-4: a given-up worker takes its whole process tree (its bridge JVM) with it --------------


def _process_gone(pid: int) -> bool:
    """Dead or a zombie waiting for its new parent: ``kill(pid, 0)`` succeeds on zombies."""
    stat = Path(f"/proc/{pid}/stat")
    try:
        text = stat.read_text(encoding="utf-8")
    except OSError:
        return True
    return text.rsplit(")", 1)[1].split()[0] == "Z"


def _grandchild_after(pool_run: Callable[[], object], data: Path) -> tuple[object, bool]:
    import os
    import signal
    import time

    pid_file = data / "grandchild.pid"
    outcome = pool_run()
    pid = int(pid_file.read_text(encoding="utf-8"))
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not _process_gone(pid):
            time.sleep(0.05)
        return outcome, _process_gone(pid)
    finally:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)  # never leave a sleeper behind, also when a check fails


posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")


@posix_only
def test_a_worker_given_up_at_the_wall_limit_takes_its_jvm_with_it(tmp_path: Path) -> None:
    pool, _ = _pool(tmp_path, workers=1, budget=8, wall=1.5)

    def run() -> object:
        with pool:
            return pool.run([_tasks(range(1, 2), "hangkid")[0]])

    results, gone = _grandchild_after(run, tmp_path)
    assert results["hangkid:1"]["failure_class"] == "TimeLimit"  # type: ignore[index]
    assert gone, "the process the hung worker started survived the worker"
    # the killed worker never reported the end of its JVM life: counted, unknown stays unknown
    info = pool.summary()
    assert info["jvm_lives_lost"] == 1
    lost = [life for life in info["jvm_lives"] if life["end"] == "worker_lost"]  # type: ignore[union-attr]
    assert lost[0]["games"] is None and lost[0]["life_id"] is None
    assert lost[0]["reason"] == "TimeLimit"


@posix_only
def test_a_worker_that_dies_on_its_own_does_not_leave_its_jvm_running(tmp_path: Path) -> None:
    pool, _ = _pool(tmp_path, workers=1, budget=8)

    def run() -> object:
        with pool:
            return pool.run([_tasks(range(1, 2), "crashkid")[0], *_tasks(range(2, 3))])

    results, gone = _grandchild_after(run, tmp_path)
    assert results["crashkid:1"]["failure_class"] == "WorkerExited"  # type: ignore[index]
    assert results["t:2"]["status"] == "finished"  # type: ignore[index]
    assert gone, "the process the dead worker started was left running"
    assert pool.summary()["jvm_lives_lost"] == 1


# --- P2-A (#1652): a worker that dies while idle does not leave its JVM running -----------------


def _wait_zombie(pid: int) -> None:
    """Until the worker that died on its own is a zombie (ended, not yet reaped)."""
    import time

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline and not _process_gone(pid):
        time.sleep(0.02)
    if not _process_gone(pid):
        pytest.fail(f"worker {pid} did not die after its idle game")


def _idle_lost(pool: GamePool) -> list[dict[str, object]]:
    lives = pool.summary()["jvm_lives"]
    return [life for life in lives if life["end"] == "worker_lost"]  # type: ignore[union-attr]


@posix_only
def test_a_worker_that_dies_between_two_windows_takes_its_jvm_with_it(tmp_path: Path) -> None:
    pool, _ = _pool(tmp_path, workers=1, budget=8)

    def run() -> object:
        with pool:
            first = pool.run([_tasks(range(1, 2), "idlekid")[0]])
            _wait_zombie(int(str(first["idlekid:1"]["pid"])))
            # the next window finds the worker ended before any event of it was read
            return first, pool.run(_tasks(range(2, 3)))

    outcome, gone = _grandchild_after(run, tmp_path)
    first, second = outcome  # type: ignore[misc]
    assert first["idlekid:1"]["status"] == "finished"
    assert second["t:2"]["status"] == "finished"
    assert second["t:2"]["pid"] != first["idlekid:1"]["pid"], "a fresh worker plays the next game"
    assert gone, "the process the idle worker started survived it"
    lost = _idle_lost(pool)
    assert pool.summary()["jvm_lives_lost"] == 1
    assert lost[0]["reason"] == "WorkerExited" and lost[0]["games"] is None


@posix_only
def test_a_worker_that_dies_just_after_its_game_in_a_window_takes_its_jvm_with_it(
    tmp_path: Path,
) -> None:
    pool, _ = _pool(tmp_path, workers=1, budget=8)

    def hold_until_dead(task: GameTask, summary: game_pool.GameSummary) -> None:
        # the hand-out of the next game meets the worker dead before its end of stdout is read
        if task.task_id == "idlekid:1":
            _wait_zombie(int(str(summary["pid"])))

    def run() -> object:
        with pool:
            tasks = [_tasks(range(1, 2), "idlekid")[0], *_tasks(range(2, 3))]
            return pool.run(tasks, on_done=hold_until_dead)

    results, gone = _grandchild_after(run, tmp_path)
    assert results["idlekid:1"]["status"] == "finished"  # type: ignore[index]
    assert results["t:2"]["status"] == "finished"  # type: ignore[index]
    assert gone, "the process the worker started survived its death within the window"
    assert pool.summary()["jvm_lives_lost"] == 1
    assert pool.summary()["worker_processes_started"] == 2


@posix_only
def test_a_worker_that_dies_after_the_last_window_takes_its_jvm_with_it_on_close(
    tmp_path: Path,
) -> None:
    pool, _ = _pool(tmp_path, workers=1, budget=8)

    def run() -> object:
        first = pool.run([_tasks(range(1, 2), "idlekid")[0]])
        _wait_zombie(int(str(first["idlekid:1"]["pid"])))
        pool.close()
        return first

    results, gone = _grandchild_after(run, tmp_path)
    assert results["idlekid:1"]["status"] == "finished"  # type: ignore[index]
    assert gone, "closing the pool reaped the dead worker and left its JVM running"
    lost = _idle_lost(pool)
    assert pool.summary()["jvm_lives_lost"] == 1 and lost[0]["reason"] == "WorkerExited"


@posix_only
def test_a_clean_retire_counts_no_lost_life(tmp_path: Path) -> None:
    pool, _ = _pool(tmp_path, workers=2, budget=8)
    with pool:
        pool.run(_tasks(range(1, 5)))
    info = pool.summary()
    assert info["jvm_lives_lost"] == 0
    assert {life["end"] for life in info["jvm_lives"]} == {"series_closed"}  # type: ignore[union-attr]


# --- #1652 (review of #1654): an ended worker whose end of stdout stays away is given up --------


@posix_only
def test_an_ended_idle_worker_whose_stdout_never_ends_is_given_up_after_the_grace(
    tmp_path: Path,
) -> None:
    import os
    import signal
    import time

    pool, _ = _pool(tmp_path, workers=1, budget=8)
    pool.ended_eof_grace_seconds = 2.0
    tasks = [_tasks(range(1, 2), "idleholder")[0], *_tasks(range(2, 3))]
    marks: dict[str, float] = {}

    def hold_until_dead(task: GameTask, summary: game_pool.GameSummary) -> None:
        # the next hand-out meets the worker ended, while its stdout is still held open
        if task.task_id == "idleholder:1":
            _wait_zombie(int(str(summary["pid"])))
        marks[task.task_id] = time.monotonic()

    stop = threading.Event()
    outcome: dict[str, object] = {}

    def play() -> None:
        try:
            outcome["results"] = pool.run(tasks, on_done=hold_until_dead, should_cancel=stop.is_set)
        except BaseException as exc:  # handed to the test thread below
            outcome["error"] = exc

    holder_file = tmp_path / "holder.pid"
    thread = threading.Thread(target=play, daemon=True)
    try:
        thread.start()
        # a limit of its own: without the grace ``run`` never ends, and the suite must not hang
        thread.join(timeout=30)
        hung = thread.is_alive()
        holder_held = holder_file.is_file() and not _process_gone(
            int(holder_file.read_text(encoding="utf-8"))
        )
        stop.set()  # a hung ``run`` stops handing out games and returns
        thread.join(timeout=10)
    finally:
        pool.close()
        if holder_file.is_file():
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(holder_file.read_text(encoding="utf-8")), signal.SIGKILL)
    assert not hung, "an ended worker whose stdout never ended held its place for good"
    error = outcome.get("error")
    if isinstance(error, BaseException):
        raise error
    # the setup really kept the end of stdout away: the holder outlived the pool's decision
    assert holder_held, "the stdout holder was gone, so the end of stdout was not kept away"
    results = outcome["results"]
    assert isinstance(results, dict)
    assert results["idleholder:1"]["status"] == "finished"
    assert results["t:2"]["status"] == "finished", "the game waiting went to a fresh worker"
    assert results["t:2"]["pid"] != results["idleholder:1"]["pid"]
    # not given up at once: its queued events had the grace to be read
    assert marks["t:2"] - marks["idleholder:1"] >= pool.ended_eof_grace_seconds
    info = pool.summary()
    assert info["worker_processes_started"] == 2
    # given up like a worker whose stdout ended: its open JVM life is counted, never a result
    assert info["jvm_lives_lost"] == 1
    assert _idle_lost(pool)[0]["reason"] == "WorkerExited"


def test_without_waitid_an_ended_worker_is_polled_and_its_group_killed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import signal

    order: list[object] = []
    # macOS without ``os.waitid`` (older Pythons): neither ``waitid`` nor its flags exist
    monkeypatch.delattr(os, "waitid", raising=False)
    monkeypatch.delattr(os, "WNOWAIT", raising=False)
    monkeypatch.setattr(game_pool.sys, "platform", "darwin")
    monkeypatch.setattr(
        os, "killpg", lambda pid, sig: order.append(("killpg", pid, sig)), raising=False
    )
    proc = _FakeProc(log=order, polled=0)
    assert game_pool.reap_ended_process(proc, windows=False) is True  # type: ignore[arg-type]
    # the group is signalled where the end is first seen: after the reap no group signal follows
    assert order == ["poll", ("killpg", 4242, signal.SIGKILL), "kill", "wait"]
    # still running: polled, neither signalled nor killed
    order.clear()
    assert game_pool.reap_ended_process(_FakeProc(log=order), windows=False) is False  # type: ignore[arg-type]
    assert order == ["poll"]


def test_an_ended_worker_is_seen_without_reaping_then_its_group_killed_then_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import signal

    order: list[object] = []

    def waitid(idtype: int, pid: int, options: int) -> object:
        order.append(("waitid", pid, options))
        return SimpleNamespace(si_pid=pid)  # ended, still a zombie

    monkeypatch.setattr(os, "waitid", waitid, raising=False)
    monkeypatch.setattr(os, "P_PID", 1, raising=False)
    monkeypatch.setattr(os, "WEXITED", 4, raising=False)
    monkeypatch.setattr(os, "WNOHANG", 1, raising=False)
    monkeypatch.setattr(os, "WNOWAIT", 0x1000000, raising=False)
    monkeypatch.setattr(
        os, "killpg", lambda pid, sig: order.append(("killpg", pid, sig)), raising=False
    )
    proc = _FakeProc(log=order)
    assert game_pool.reap_ended_process(proc, windows=False) is True  # type: ignore[arg-type]
    assert order == [
        ("waitid", 4242, 4 | 1 | 0x1000000),
        ("killpg", 4242, signal.SIGKILL),
        "kill",
        "wait",
    ]
    # still running: neither signalled nor reaped
    order.clear()
    monkeypatch.setattr(os, "waitid", lambda *a: order.append("waitid") or None, raising=False)
    assert game_pool.reap_ended_process(_FakeProc(log=order), windows=False) is False  # type: ignore[arg-type]
    assert order == ["waitid"]


def test_a_worker_reaped_elsewhere_gets_no_group_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    killed: list[object] = []

    def waitid(*_a: object) -> object:
        raise ChildProcessError("no such child")

    monkeypatch.setattr(os, "waitid", waitid, raising=False)
    monkeypatch.setattr(os, "P_PID", 1, raising=False)
    monkeypatch.setattr(os, "WNOWAIT", 0x1000000, raising=False)
    monkeypatch.setattr(os, "killpg", lambda *a: killed.append(a), raising=False)
    proc = _FakeProc(polled=0)  # ``Popen.poll`` sets 0 when the child was reaped elsewhere
    assert game_pool.reap_ended_process(proc, windows=False) is True  # type: ignore[arg-type]
    assert killed == [], "its id may name another group by now"
    assert proc.calls[0] == "poll"


def test_the_windows_branch_ends_the_tree_of_an_ended_worker_with_taskkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    order: list[object] = []
    monkeypatch.setattr(os, "waitid", lambda *a: order.append("waitid"), raising=False)
    monkeypatch.setattr(game_pool.subprocess, "run", lambda argv, **_k: order.append(list(argv)))
    proc = _FakeProc(log=order, polled=0)
    assert game_pool.reap_ended_process(proc, windows=True) is True  # type: ignore[arg-type]
    assert order == ["poll", ["taskkill", "/T", "/F", "/PID", "4242"], "kill", "wait"]
    order.clear()
    assert game_pool.reap_ended_process(_FakeProc(log=order), windows=True) is False  # type: ignore[arg-type]
    assert order == ["poll"]


class _FakeProc:
    def __init__(
        self,
        returncode: int | None = None,
        *,
        log: list[object] | None = None,
        polled: int | None = None,
    ) -> None:
        self.pid = 4242
        self.returncode = returncode
        self.calls: list[object] = log if log is not None else []
        self._polled = polled

    def poll(self) -> int | None:
        self.calls.append("poll")
        if self.returncode is None:
            self.returncode = self._polled
        return self.returncode

    def kill(self) -> None:
        self.calls.append("kill")

    def wait(self, timeout: float | None = None) -> int:
        self.calls.append("wait")
        return 0


def test_the_posix_branch_kills_the_process_group_of_a_worker_not_yet_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import signal

    killed: list[tuple[int, int]] = []
    ran: list[object] = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: killed.append((pid, sig)), raising=False)
    monkeypatch.setattr(game_pool.subprocess, "run", lambda *a, **k: ran.append(a))
    proc = _FakeProc()
    game_pool.kill_process_tree(proc, windows=False)  # type: ignore[arg-type]
    assert killed == [(4242, signal.SIGKILL)] and ran == []
    assert proc.calls == ["kill", "wait"]
    # a worker already reaped: its id may name another group by now, so no group signal
    killed.clear()
    game_pool.kill_process_tree(_FakeProc(returncode=0), windows=False)  # type: ignore[arg-type]
    assert killed == []


def test_the_windows_branch_ends_the_process_tree_with_taskkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    killed: list[object] = []
    ran: list[list[str]] = []
    monkeypatch.setattr(os, "killpg", lambda *a: killed.append(a), raising=False)
    monkeypatch.setattr(game_pool.subprocess, "run", lambda argv, **_k: ran.append(list(argv)))
    proc = _FakeProc()
    game_pool.kill_process_tree(proc, windows=True)  # type: ignore[arg-type]
    assert ran == [["taskkill", "/T", "/F", "/PID", "4242"]] and killed == []
    assert proc.calls == ["kill", "wait"]


def test_a_missing_taskkill_does_not_stop_the_kill_of_the_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_taskkill(*_a: object, **_k: object) -> None:
        raise FileNotFoundError("taskkill")

    monkeypatch.setattr(game_pool.subprocess, "run", no_taskkill)
    proc = _FakeProc()
    game_pool.kill_process_tree(proc, windows=True)  # type: ignore[arg-type]
    assert proc.calls == ["kill", "wait"]


def test_workers_lead_a_process_group_of_their_own_on_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class _Popen:
        def __init__(self, argv: list[str], **kwargs: object) -> None:
            seen.update(kwargs)
            self.stdout = self.stderr = self.stdin = None

    monkeypatch.setattr(game_pool.subprocess, "Popen", _Popen)
    monkeypatch.setattr(game_pool, "_WINDOWS", False)
    game_pool._ProcessWorker("w1", ["x"], {}, queue.Queue())
    assert seen["start_new_session"] is True
    monkeypatch.setattr(game_pool, "_WINDOWS", True)
    game_pool._ProcessWorker("w2", ["x"], {}, queue.Queue())
    assert seen["start_new_session"] is False


# --- P3: an engine that cannot be built is a pool error, not one lost game per fresh worker ------


def test_a_worker_whose_engine_cannot_be_built_never_says_ready() -> None:
    def broken() -> game_pool.WorkerEngine:
        raise RuntimeError("engine command is broken")

    out = io.StringIO()
    with pytest.raises(RuntimeError, match="broken"):
        worker_main(stdin=io.StringIO(""), stdout=out, label="w1", engine_factory=broken)
    assert [json.loads(line)["ev"] for line in out.getvalue().splitlines()] == ["bye"]


def test_a_broken_engine_command_is_a_pool_error(tmp_path: Path) -> None:
    script = tmp_path / "broken_worker.py"
    script.write_text(
        textwrap.dedent(
            """
            import sys
            from commander_lab.studio.game_pool import worker_main

            def broken():
                raise RuntimeError("engine command is broken")

            sys.exit(worker_main(stdin=sys.stdin, stdout=sys.stdout, label="w",
                                 engine_factory=broken))
            """
        ),
        encoding="utf-8",
    )
    pool = GamePool(tmp_path, workers=1, worker_argv=lambda _l: [sys.executable, str(script)])
    with pytest.raises(GamePoolError, match="ended before it was ready"):
        pool.run(_tasks(range(1, 4)))
    pool.close()
    assert pool.summary()["worker_processes_started"] == 1


# --- P3-A (#1652): drain queued worker events before ended-idle grace drops the worker ----------


@posix_only
def test_p3a_queued_jvm_exit_and_bye_are_drained_before_idle_grace_drops_worker(
    tmp_path: Path,
) -> None:
    pool, _ = _pool(tmp_path, workers=2, budget=8)
    assert game_pool.ENDED_EOF_GRACE_SECONDS == 5.0
    assert pool.ended_eof_grace_seconds == 5.0
    pool.ended_eof_grace_seconds = 0.05
    with pool:
        first = pool.run(_tasks(range(1, 3), "p3a"))
        assert len(first) == 2
        worker_one = pool._workers[0]
        # Worker 1 retires cleanly and finishes writing jvm_exit + bye + EOF before the next look
        # window begins, while more than ended_eof_grace_seconds elapse between windows.
        assert worker_one.send({"op": "retire"})
        worker_one._out.join(timeout=5)
        _wait_zombie(worker_one.proc.pid)
        assert worker_one.end_if_exited() is True
        worker_one.ended_at -= 10.0

        second = pool.run(_tasks(range(3, 5), "p3a"))
        assert len(second) == 2

    info = pool.summary()
    assert info["games_finished"] == 4
    assert info["jvm_lives_lost"] == 0
    lives = info["jvm_lives"]
    assert isinstance(lives, list)
    assert any(
        life.get("life_id") == "w1-1" and life.get("end") == "series_closed" for life in lives
    )
    assert len(lives) == 3


@posix_only
def test_p3a_queued_eof_retires_worker_via_drain_even_when_grace_is_large(
    tmp_path: Path,
) -> None:
    pool, _ = _pool(tmp_path, workers=2, budget=8)
    pool.ended_eof_grace_seconds = 60.0
    with pool:
        first = pool.run(_tasks(range(1, 3), "p3a-eof"))
        assert len(first) == 2
        worker_one = pool._workers[0]
        assert worker_one.send({"op": "retire"})
        worker_one._out.join(timeout=5)
        _wait_zombie(worker_one.proc.pid)
        assert worker_one.end_if_exited() is True

        second = pool.run(_tasks(range(3, 5), "p3a-eof"))
        assert len(second) == 2
        assert worker_one not in pool._workers

    info = pool.summary()
    assert info["games_finished"] == 4
    assert info["jvm_lives_lost"] == 0
    assert info["worker_processes_started"] == 3


def test_p3a_queued_jvm_exit_without_eof_is_kept_when_grace_expires(tmp_path: Path) -> None:
    import time

    pool, _ = _pool(tmp_path, workers=2, budget=8)
    pool.ended_eof_grace_seconds = 0.05
    try:
        pool.run(_tasks(range(1, 3), "p3a-noeof"))
        worker_one = pool._workers[0]
        # Synthetic probe (no held external pipe): marks the live worker ended with expired grace
        # and enqueues jvm_exit without EOF; _idle_worker then calls _lose (known #1652 Pt. 4 count).
        worker_one.ended = True
        worker_one.ended_at = time.monotonic() - 10.0
        pool._events.put(
            (
                worker_one,
                {
                    "ev": "jvm_exit",
                    "life_id": "w1-1",
                    "games": 1,
                    "end": "budget",
                    "disposition": "clean",
                },
            )
        )
        second = pool.run(_tasks(range(3, 5), "p3a-noeof"))
        assert len(second) == 2
        info = pool.summary()
        assert info["jvm_lives_lost"] == 1
        lives = info["jvm_lives"]
        assert isinstance(lives, list)
        assert any(life.get("life_id") == "w1-1" and life.get("end") == "budget" for life in lives)
    finally:
        pool.close()


# --- S1 (#1660): task format, game key, manifest and journal, determinism guard ----------------

from commander_lab.studio import series_record, table_spec  # noqa: E402
from commander_lab.studio.series_record import (  # noqa: E402
    DETERMINISM_VIOLATION,
    DeterminismViolation,
    ManifestMismatch,
    SeriesRecord,
)

_KEY_INPUT: dict[str, object] = {
    "jar_sha256": JAR,
    "engine_pin": PIN,
    "pilot_fingerprints": ("f0", "f1", "f2", "f3"),
    "seat_styles": (0.5, 0.5, 0.5, 0.5),
    "deck_sha256": ("d0", "d1", "d2", "d3"),
    "seed": 7,
    "strategy": "generic",
    "table_options": {"seats": 4, "opponent_mode": "fixed"},
    "skip_forced_decisions": True,
    "round_limit": None,
    "jvm_options": NO_JVM_OPTIONS,
}
_KEY_CHANGES: dict[str, object] = {
    "jar_sha256": "k" * 64,
    "engine_pin": "q" * 40,
    "pilot_fingerprints": ("f0", "f1", "fX", "f3"),
    "seat_styles": (0.5, 0.7, 0.5, 0.5),
    "deck_sha256": ("d0", "d1", "d3", "d2"),  # same decks, other seat order
    "seed": 8,
    "strategy": "control",
    "table_options": {"seats": 4, "opponent_mode": "rotation"},
    "skip_forced_decisions": False,
    "round_limit": 30,
    "jvm_options": {"nested_copy_skip": False, "env_options": {}, "command_options": None},
}


def test_the_same_input_gives_the_same_game_key() -> None:
    assert series_record.game_key(**_KEY_INPUT) == series_record.game_key(**dict(_KEY_INPUT))  # type: ignore[arg-type]


@pytest.mark.parametrize("field", sorted(_KEY_CHANGES))
def test_every_field_of_the_game_key_changes_the_key(field: str) -> None:
    assert set(_KEY_CHANGES) == set(_KEY_INPUT)  # every field is probed
    changed = {**_KEY_INPUT, field: _KEY_CHANGES[field]}
    assert series_record.game_key(**changed) != series_record.game_key(**_KEY_INPUT)  # type: ignore[arg-type]


def test_skip_forced_unknown_is_its_own_value_and_a_key_needs_jar_and_pin() -> None:
    keys = {
        series_record.game_key(**{**_KEY_INPUT, "skip_forced_decisions": value})  # type: ignore[arg-type]
        for value in (None, True, False)
    }
    assert len(keys) == 3
    for blank in ("", " ", "\t\n"):
        with pytest.raises(ValueError, match="JAR"):
            series_record.game_key(**{**_KEY_INPUT, "jar_sha256": blank})  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Pin"):
            series_record.game_key(**{**_KEY_INPUT, "engine_pin": blank})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="je einen Eintrag"):
        series_record.game_key(**{**_KEY_INPUT, "seat_styles": (0.5,)})  # type: ignore[arg-type]


def _games(table: str, seeds: range, key: str | None = "same") -> list[SimpleNamespace]:
    """Planned games of a manifest: id and key (``same``: one key per seed and table)."""
    return [
        SimpleNamespace(
            task_id=f"{table}:{seed}",
            game_id=f"g-{table}-s{seed}",
            game_key=None
            if key is None
            else hashlib.sha256(f"{table}|{seed}".encode()).hexdigest(),
        )
        for seed in seeds
    ]


def _record(tmp_path: Path, tasks: Sequence[object], series: str = "ser1") -> SeriesRecord:
    return SeriesRecord.open(
        tmp_path,
        series,
        games=[{"task_id": t.task_id, "game_id": t.game_id, "game_key": t.game_key} for t in tasks],  # type: ignore[attr-defined]
        table_hash="th",
        table={"seats": 2},
    )


def test_the_manifest_is_written_once_and_never_changed(tmp_path: Path) -> None:
    tasks = _games("man", range(1, 3))
    record = _record(tmp_path, tasks)
    stored = json.loads(record.manifest_path.read_text(encoding="utf-8"))
    assert stored["schema"] == "studio-series-manifest-1" and stored["table_hash"] == "th"
    assert record.manifest_path == tmp_path / "games" / "series" / "ser1" / "manifest.json"
    again = _record(tmp_path, tasks)  # a resume with the same plan
    assert again.manifest == record.manifest
    with pytest.raises(ManifestMismatch):
        _record(tmp_path, _games("man", range(1, 4)))
    with pytest.raises(ValueError, match="Serien-Kennung"):
        series_record.series_folder(tmp_path, "../x")


def test_two_transcript_hashes_for_one_key_are_a_determinism_violation(tmp_path: Path) -> None:
    task = _games("det", range(1, 2))[0]
    twin = SimpleNamespace(task_id="twin", game_id="g-det-twin", game_key=task.game_key)
    record = _record(tmp_path, [task, twin])
    record.record(task.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    record.record(twin.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    with pytest.raises(DeterminismViolation) as caught:
        record.record(twin.game_id, {"status": "finished", "semantic_transcript_sha256": "b" * 64})
    assert caught.value.status == DETERMINISM_VIOLATION and caught.value.game_key == task.game_key
    # the journal keeps the evidence; reading it again (a resume) ends the series the same way
    assert len(record.journal_path.read_text(encoding="utf-8").splitlines()) == 3
    with pytest.raises(DeterminismViolation):
        _record(tmp_path, [task, twin])


def test_a_failed_game_or_a_game_without_key_never_trips_the_guard(tmp_path: Path) -> None:
    task = _games("nk", range(1, 2))[0]
    unkeyed = _games("u", range(1, 2), key=None)[0]
    record = _record(tmp_path, [task, unkeyed])
    record.record(task.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    record.record(task.game_id, {"status": "failed", "semantic_transcript_sha256": "c" * 64})
    record.record(unkeyed.game_id, {"status": "finished", "semantic_transcript_sha256": "d" * 64})
    record.record(unkeyed.game_id, {"status": "finished", "semantic_transcript_sha256": "e" * 64})
    lines = record.journal_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4  # all four results journaled, none of them a violation
    resumed = _record(tmp_path, [task, unkeyed])
    assert set(resumed.results()) == {task.game_id, unkeyed.game_id}
    # never silent: the finished game without a key is counted as unguarded (last result per game)
    assert record.unguarded() == (1, 1) and resumed.unguarded() == (1, 1)


def test_a_finished_game_without_a_transcript_hash_is_counted_as_unguarded(tmp_path: Path) -> None:
    first, second = _games("ug", range(1, 3))
    record = _record(tmp_path, [first, second])
    assert record.unguarded() == (0, 0)  # nothing finished yet: no count, not "all guarded"
    record.record(first.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    record.record(second.game_id, {"status": "finished", "semantic_transcript_sha256": ""})
    assert record.unguarded() == (1, 2)
    assert _record(tmp_path, [first, second]).unguarded() == (1, 2)


def test_the_journal_counts_only_manifest_members_and_survives_a_cut_off_line(
    tmp_path: Path,
) -> None:
    games = _games("jr", range(1, 3))
    record = _record(tmp_path, games)
    record.record(games[0].game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    with pytest.raises(ValueError, match="nicht im Manifest"):
        record.record("foreign", {"status": "finished"})
    with record.journal_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"game_id": "foreign", "summary": {"status": "finished"}}) + "\n")
        handle.write('{"game_id": "g-jr-s2", "sta')  # cut off by a cancel
    resumed = _record(tmp_path, games)
    assert set(resumed.results()) == {games[0].game_id} and resumed.ignored_lines == 2
    assert resumed.results()[games[0].game_id]["semantic_transcript_sha256"] == "a" * 64


def test_a_last_line_without_its_line_end_is_never_a_result_even_when_it_parses(
    tmp_path: Path,
) -> None:
    games = _games("tail", range(1, 3))
    record = _record(tmp_path, games)
    entry = {
        "game_id": games[1].game_id,
        "game_key": games[1].game_key,  # a valid member line: only the missing line end drops it
        "status": "finished",
        "summary": {"status": "finished"},
    }
    record.journal_path.write_text(json.dumps(entry), encoding="utf-8")  # no line end: cut off
    resumed = _record(tmp_path, games)
    assert resumed.results() == {} and resumed.ignored_lines == 1
    assert resumed.key_mismatch_lines == 0
    record.journal_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")  # the control
    assert set(_record(tmp_path, games).results()) == {games[1].game_id}
    record.journal_path.write_text(json.dumps(entry), encoding="utf-8")
    resumed.record(games[0].game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    lines = resumed.journal_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["game_id"] == games[0].game_id


def test_a_violation_appended_after_a_cut_off_line_still_ends_the_resumed_series(
    tmp_path: Path,
) -> None:
    first, second = _games("cut", range(1, 3))
    twin = SimpleNamespace(task_id="twin", game_id="g-cut-twin", game_key=first.game_key)
    record = _record(tmp_path, [first, second, twin])
    record.record(first.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    with record.journal_path.open("a", encoding="utf-8") as handle:
        handle.write('{"game_id": "g-cut-s2", "sta')  # the run ended mid-line
    resumed = _record(tmp_path, [first, second, twin])
    assert resumed.ignored_lines == 1
    with pytest.raises(DeterminismViolation):
        resumed.record(twin.game_id, {"status": "finished", "semantic_transcript_sha256": "b" * 64})
    # the violation is a line of its own, so opening the series again ends it the same way
    with pytest.raises(DeterminismViolation) as caught:
        _record(tmp_path, [first, second, twin])
    assert caught.value.status == DETERMINISM_VIOLATION


def test_a_line_cut_inside_a_multi_byte_character_is_ignored_and_the_series_resumes(
    tmp_path: Path,
) -> None:
    first, second, third = _games("utf", range(1, 4))
    record = _record(tmp_path, [first, second, third])
    record.record(
        first.game_id,
        {"status": "finished", "semantic_transcript_sha256": "a" * 64, "note": "Spielschlüssel"},
    )
    record.record(
        second.game_id,
        {"status": "failed", "failure_message": "Spielschlüssel fehlt", "log": None},
    )
    data = record.journal_path.read_bytes()
    cut = data.rindex("ü".encode()) + 1  # inside the two bytes of the last "ü"
    record.journal_path.write_bytes(data[:cut])
    resumed = _record(tmp_path, [first, second, third])
    assert resumed.ignored_lines == 1 and set(resumed.results()) == {first.game_id}
    assert resumed.results()[first.game_id]["note"] == "Spielschlüssel"  # a whole line keeps it
    # the next result ends the cut line, which becomes a complete line with a broken character
    resumed.record(third.game_id, {"status": "finished", "semantic_transcript_sha256": "c" * 64})
    again = _record(tmp_path, [first, second, third])
    assert again.ignored_lines == 1
    assert set(again.results()) == {first.game_id, third.game_id}


def test_a_complete_line_with_a_broken_character_is_ignored_not_repaired(tmp_path: Path) -> None:
    first, second = _games("bad", range(1, 3))
    record = _record(tmp_path, [first, second])
    record.record(first.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    record.record(second.game_id, {"status": "failed", "failure_message": "Spielschlüssel"})
    data = record.journal_path.read_bytes()
    broken = data.replace("ü".encode(), b"\xc3")  # one byte of the character lost mid-line
    assert broken.endswith(b"\n") and broken != data
    record.journal_path.write_bytes(broken)
    resumed = _record(tmp_path, [first, second])
    assert resumed.ignored_lines == 1 and set(resumed.results()) == {first.game_id}


def test_a_member_line_with_a_key_the_manifest_does_not_name_is_not_counted(
    tmp_path: Path,
) -> None:
    first, second = _games("km", range(1, 3))
    record = _record(tmp_path, [first, second])
    record.record(first.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    foreign = {
        "game_id": second.game_id,
        "game_key": first.game_key,  # a member's id with another game's key
        "status": "finished",
        "semantic_transcript_sha256": "b" * 64,
        "summary": {"status": "finished"},
    }
    with record.journal_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(foreign) + "\n")
    resumed = _record(tmp_path, [first, second])  # no violation: the line is not grouped at all
    assert set(resumed.results()) == {first.game_id}
    assert resumed.key_mismatch_lines == 1 and resumed.ignored_lines == 1


def test_without_hard_links_the_manifest_is_created_exclusively_and_no_temp_is_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    games = _games("nolink", range(1, 3))

    def no_link(source: object, target: object) -> None:
        raise PermissionError("hard links are not supported here")

    monkeypatch.setattr(series_record.os, "link", no_link)
    record = _record(tmp_path, games, series="nolink")
    stored = json.loads(record.manifest_path.read_text(encoding="utf-8"))
    assert [g["game_id"] for g in stored["games"]] == [g.game_id for g in games]
    assert sorted(p.name for p in record.folder.iterdir()) == ["manifest.json"]
    before = record.manifest_path.read_bytes()
    with pytest.raises(ManifestMismatch):
        _record(tmp_path, _games("nolink", range(1, 4)), series="nolink")
    assert record.manifest_path.read_bytes() == before
    assert sorted(p.name for p in record.folder.iterdir()) == ["manifest.json"]

    def other_start_then_no_link(source: object, target: object) -> None:
        # another process created the manifest between the check and the exclusive create
        Path(str(target)).write_text('{"schema": "studio-series-manifest-1", "games": []}')
        raise PermissionError("hard links are not supported here")

    monkeypatch.setattr(series_record.os, "link", other_start_then_no_link)
    with pytest.raises(ManifestMismatch):
        _record(tmp_path, games, series="race2")
    raced = series_record.series_folder(tmp_path, "race2")
    assert json.loads((raced / "manifest.json").read_text())["games"] == []  # never replaced
    assert sorted(p.name for p in raced.iterdir()) == ["manifest.json"]


def test_a_failing_manifest_write_leaves_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(path: object, data: bytes) -> None:
        raise OSError("disk full")

    def no_link(source: object, target: object) -> None:
        raise OSError("hard links are not supported here")

    monkeypatch.setattr(series_record.os, "link", no_link)
    monkeypatch.setattr(series_record, "_create_exclusive", broken)
    with pytest.raises(OSError, match="disk full"):
        _record(tmp_path, _games("tmp", range(1, 2)), series="tmp")
    assert list(series_record.series_folder(tmp_path, "tmp").iterdir()) == []


@pytest.mark.parametrize("content", ["", '{"schema": "studio-series-man'])
def test_an_empty_or_half_written_manifest_is_a_manifest_mismatch(
    tmp_path: Path, content: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(series_record.time, "sleep", lambda _seconds: None)
    folder = series_record.series_folder(tmp_path, "half")
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(content, encoding="utf-8")  # a start that ended early
    with pytest.raises(ManifestMismatch, match="unvollständig"):
        _record(tmp_path, _games("half", range(1, 2)), series="half")
    assert (folder / "manifest.json").read_text(encoding="utf-8") == content  # never rewritten


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("strategy", ""),
        ("strategy", "  "),
        ("pilot_fingerprints", ("f0", "", "f2", "f3")),
        ("deck_sha256", ("d0", "d1", " ", "d3")),
    ],
)
def test_an_empty_strategy_fingerprint_or_deck_hash_gives_no_key(field: str, value: object) -> None:
    with pytest.raises(ValueError, match="leer"):
        series_record.game_key(**{**_KEY_INPUT, field: value})  # type: ignore[arg-type]


def test_two_close_styles_never_share_a_key() -> None:
    near = {**_KEY_INPUT, "seat_styles": (0.5, 0.5000001, 0.5, 0.5)}
    assert series_record.game_key(**near) != series_record.game_key(**_KEY_INPUT)  # type: ignore[arg-type]
    coarse = {**_KEY_INPUT, "seat_styles": (0.2, 0.5, 0.5, 0.5)}
    finer = {**_KEY_INPUT, "seat_styles": (0.3, 0.5, 0.5, 0.5)}
    assert series_record.game_key(**coarse) != series_record.game_key(**finer)  # type: ignore[arg-type]
    same = {**_KEY_INPUT, "seat_styles": (0.5, 0.5, 1 / 2, 0.5)}
    assert series_record.game_key(**same) == series_record.game_key(**_KEY_INPUT)  # type: ignore[arg-type]


def test_two_starts_of_one_series_never_overwrite_the_first_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    games = _games("race", range(1, 3))
    real_link = series_record.os.link

    def other_start_first(source: object, target: object) -> None:
        # another process created the manifest of this series between the check and the link
        Path(str(target)).write_text('{"schema": "studio-series-manifest-1", "games": []}')
        raise FileExistsError(str(target))

    monkeypatch.setattr(series_record.os, "link", other_start_first)
    with pytest.raises(ManifestMismatch):
        _record(tmp_path, games, series="race")
    monkeypatch.setattr(series_record.os, "link", real_link)
    folder = series_record.series_folder(tmp_path, "race")
    assert sorted(p.name for p in folder.iterdir()) == ["manifest.json"]  # no temp file left


def test_the_wall_limit_is_set_per_seat_count_without_changing_the_table_hash() -> None:
    assert [table_spec.game_wall_limit_seconds(n) for n in (2, 3, 4)] == [1800.0] * 3
    for seats in (5, 6):
        with pytest.raises(ValueError, match="S2/F6"):
            table_spec.game_wall_limit_seconds(seats)
    spec = table_spec.TableSpec(seats=3, opponents=["a", "b"])
    assert spec.game_wall_limit_seconds() == 1800.0
    assert "game_wall_limit_seconds" not in spec.canonical()


# --- S1 (#1660), worker side: complete tasks, checks before the game, journal on the pool -----


def test_a_planned_task_carries_hashes_pilots_and_key_and_the_key_follows_the_pilot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _tasks(range(3, 4), "k", styles=(0.5, 0.8))[0]
    assert task.deck_sha256 == tuple(series_record.file_sha256(p) for p in task.deck_paths)
    assert task.seat_styles == (0.5, 0.8)
    assert task.pilot_fingerprints == tuple(map(game_pool.seat_pilot_fingerprint, (0.5, 0.8)))
    assert len(set(task.pilot_fingerprints)) == 2  # the style is part of a seat's fingerprint
    wire = task.to_wire()
    assert wire["game_key"] == task.game_key and wire["seat_styles"] == [0.5, 0.8]
    # other pilot code (same styles, same decks) gives another key (M1)
    monkeypatch.setattr(game_pool, "seat_pilot_fingerprint", lambda style: f"other-{style}")
    assert _tasks(range(3, 4), "k", styles=(0.5, 0.8))[0].game_key != task.game_key
    # without a bridge JAR or engine pin there is no task, never one without its key
    for jar, pin in ((None, PIN), ("", PIN), (JAR, None)):
        with pytest.raises(ValueError, match="Spielschlüssel"):
            game_pool.plan_task(
                task_id="x",
                seed=1,
                game_id="x",
                deck_paths=list(task.deck_paths),
                seat_styles=[0.5, 0.5],
                jar_sha256=jar,
                engine_pin=pin,
                skip_forced_decisions=None,
                jvm_options=NO_JVM_OPTIONS,
            )


def test_the_forced_pass_switch_is_read_from_the_command() -> None:
    prop = "-Dcommanderlab.fullGame.skipForcedDecisions"
    assert game_pool.skip_forced_decisions_of(("java", f"{prop}=true", "-jar", "b")) is True
    assert game_pool.skip_forced_decisions_of(("java", f"{prop}=false", "-jar", "b")) is False
    assert game_pool.skip_forced_decisions_of(("java", "-jar", "b")) is None
    assert game_pool.skip_forced_decisions_of(None) is None


def test_a_manipulated_deck_file_plays_no_game_and_fails_as_infrastructure(tmp_path: Path) -> None:
    tasks = _tasks(range(1, 3), "m")
    Path(tasks[0].deck_paths[1]).write_text('{"deck": "changed"}', encoding="utf-8")
    pool, _ = _pool(tmp_path, workers=1)
    with pool:
        results = pool.run(tasks)
    for task in tasks:  # both use the manipulated file
        got = results[task.task_id]
        assert got["status"] == "failed" and got["failure_class"] == "DeckHashMismatch"
        assert got["failure_kind"] == "infrastructure" and got["log"] is None
        assert "jvm_life_id" not in got  # the engine never played it
        assert got["game_key"] == task.game_key
    assert "DeckHashMismatch" in series_record.INFRASTRUCTURE_FAILURES


def test_a_missing_deck_file_an_incomplete_task_and_a_wrong_fingerprint_are_refused() -> None:
    task = _tasks(range(1, 2), "r")[0]
    assert game_pool.task_refusal(task.to_wire()) is None
    bare = {"op": "play", "task_id": "t", "seed": 1, "game_id": "g", "deck_paths": ["a"]}
    assert game_pool.task_refusal(bare)["failure_class"] == "TaskIncomplete"  # type: ignore[index]
    for field in ("deck_sha256", "seat_styles", "pilot_fingerprints"):
        short = {**task.to_wire(), field: task.to_wire()[field][:1]}  # type: ignore[index]
        assert game_pool.task_refusal(short)["failure_class"] == "TaskIncomplete"  # type: ignore[index]
    for missing in ("jar_sha256", "game_key"):
        # the worker cannot check its JAR, the guard has nothing to compare: no game
        unkeyed = {**task.to_wire(), missing: None}
        assert game_pool.task_refusal(unkeyed)["failure_class"] == "TaskIncomplete"  # type: ignore[index]
    gone = {**task.to_wire(), "deck_paths": [task.deck_paths[0], task.deck_paths[0] + ".gone"]}
    assert game_pool.task_refusal(gone)["failure_class"] == "DeckHashMismatch"  # type: ignore[index]
    wrong = {**task.to_wire(), "pilot_fingerprints": [task.pilot_fingerprints[0], "f" * 64]}
    assert game_pool.task_refusal(wrong)["failure_class"] == "PilotFingerprintMismatch"  # type: ignore[index]
    restyled = {**task.to_wire(), "seat_styles": [0.5, 0.9]}  # style changed, fingerprint kept
    assert game_pool.task_refusal(restyled)["failure_class"] == "PilotFingerprintMismatch"  # type: ignore[index]


def test_the_worker_recomputes_the_game_key_and_refuses_a_task_it_does_not_give() -> None:
    task = _tasks(range(1, 2), "rk")[0]
    wire = task.to_wire()
    assert game_pool.task_key_of(wire) == task.game_key  # the wire carries every key field
    changes: dict[str, object] = {
        "seed": task.seed + 1,
        "strategy": "control",
        "engine_pin": "q" * 40,
        "skip_forced_decisions": False,
        "round_limit": 30,
        "table": {"seats": 2},
        "game_key": "0" * 64,  # any non-empty key the fields do not give
    }
    for field, value in changes.items():
        got = game_pool.task_refusal({**wire, field: value})
        assert got is not None and got["failure_class"] == "GameKeyMismatch", field
        assert got["failure_kind"] == "infrastructure"
    for field in ("strategy", "engine_pin"):
        got = game_pool.task_refusal({**wire, field: None})  # no strategy or pin: no key
        assert got is not None and got["failure_class"] == "GameKeyMismatch", field
    got = game_pool.task_refusal({**wire, "strategy": 7})  # not a strategy name: no key
    assert got is not None and got["failure_class"] == "GameKeyMismatch"
    assert "GameKeyMismatch" in series_record.INFRASTRUCTURE_FAILURES


def _plan(**changes: object) -> GameTask:
    options: dict[str, object] = {
        "task_id": "pk",
        "seed": 5,
        "game_id": "g-pk",
        "deck_paths": [_deck_file("pk-a.json"), _deck_file("pk-b.json")],
        "seat_styles": [0.5, 0.5],
        "jar_sha256": JAR,
        "engine_pin": PIN,
        "skip_forced_decisions": None,
        "jvm_options": NO_JVM_OPTIONS,
        "deck_hashes": {},  # fresh: a changed file is hashed again
    }
    options.update(changes)
    return game_pool.plan_task(**options)  # type: ignore[arg-type]


def _key_of(task: GameTask, **changes: object) -> str:
    """The key ``game_key`` gives for the task's inputs, recomputed independently."""
    inputs: dict[str, object] = {
        "jar_sha256": JAR,
        "engine_pin": PIN,
        "pilot_fingerprints": [game_pool.seat_pilot_fingerprint(0.5)] * 2,
        "seat_styles": [0.5, 0.5],
        "deck_sha256": [series_record.file_sha256(p) for p in task.deck_paths],
        "seed": 5,
        "strategy": "generic",
        "table_options": None,
        "skip_forced_decisions": None,
        "round_limit": None,
        "jvm_options": NO_JVM_OPTIONS,
    }
    inputs.update(changes)
    return series_record.game_key(**inputs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "plan_change", "key_change"),
    [
        ("strategy", {"strategy": "control"}, {"strategy": "control"}),
        ("skip_forced", {"skip_forced_decisions": True}, {"skip_forced_decisions": True}),
        ("skip_forced_off", {"skip_forced_decisions": False}, {"skip_forced_decisions": False}),
        (
            "table",
            {"table": {"seats": 2, "mode": "x"}},
            {"table_options": {"seats": 2, "mode": "x"}},
        ),
        ("round_limit", {"round_limit": 30}, {"round_limit": 30}),
        ("pin", {"engine_pin": "q" * 40}, {"engine_pin": "q" * 40}),
        ("jar", {"jar_sha256": "k" * 64}, {"jar_sha256": "k" * 64}),
        ("seed", {"seed": 6}, {"seed": 6}),
    ],
)
def test_plan_task_puts_every_key_field_into_the_game_key(
    field: str, plan_change: dict[str, object], key_change: dict[str, object]
) -> None:
    base = _plan()
    assert base.game_key == _key_of(base)
    changed = _plan(**plan_change)
    assert changed.game_key != base.game_key, field
    assert changed.game_key == _key_of(changed, **key_change), field
    assert game_pool.task_key_of(changed.to_wire()) == changed.game_key, field


def test_plan_task_puts_the_deck_contents_and_the_pilot_fingerprints_into_the_game_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _plan()
    Path(base.deck_paths[1]).write_text('{"deck": "changed"}', encoding="utf-8")  # same path
    redeck = _plan()
    assert redeck.game_key != base.game_key and redeck.game_key == _key_of(redeck)
    monkeypatch.setattr(game_pool, "seat_pilot_fingerprint", lambda style: f"other-{style}")
    repilot = _plan()  # same styles, other pilot code
    assert repilot.game_key != redeck.game_key
    assert repilot.game_key == _key_of(repilot, pilot_fingerprints=["other-0.5"] * 2)


def _session_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: str = ""
) -> game_pool.SessionWorkerEngine:
    _own_configuration(monkeypatch)
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"jar")
    monkeypatch.setenv(
        "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD",
        f"java -Dcommanderlab.fullGame.gamesPerJvm=2 {flags} -jar {jar} full-game",
    )

    class FakeSession:
        def __init__(self, runner: object, *, id_prefix: str = "") -> None:
            self.runner = runner
            self.lives = ()
            self.pilots: object = None

        def play(self, scenario: object, decks: object, pilots: object):  # type: ignore[no-untyped-def]
            self.pilots = pilots
            recorder = self.runner._recorder_for(scenario)  # type: ignore[attr-defined]
            self.runner.on_played(recorder.game_id)  # type: ignore[attr-defined]
            return _series_result(scenario, 1)

        def close(self) -> tuple[object, ...]:
            return ()

    monkeypatch.setattr(full_game_series, "XmageFullGameSeriesSession", FakeSession)
    return game_pool.SessionWorkerEngine(
        tmp_path, label="s", private_card_repository=False, command=None
    )


def test_the_style_of_each_seat_reaches_the_log_header_and_the_pilots_of_a_pool_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = _session_engine(tmp_path, monkeypatch)
    styles = [0.8, 0.2, 0.5, 0.65]
    task = game_pool.plan_task(
        task_id="st",
        seed=6,
        game_id="ser-style-s6-t0",
        deck_paths=[str(DECK), *map(str, PRECONS)],
        seat_styles=styles,
        jar_sha256=hashlib.sha256(b"jar").hexdigest(),
        engine_pin=PIN,
        skip_forced_decisions=None,
        jvm_options=NO_JVM_OPTIONS,
        strategy="control",
    )
    assert game_pool.task_refusal(task.to_wire()) is None
    summary = engine.play(task.to_wire(), lambda: None)
    assert summary["status"] == "finished"
    from commander_lab.studio import games

    header = games.read_game(tmp_path, "ser-style-s6-t0", start=0, count=1)["header"]
    assert [seat["style"] for seat in header["seats"]] == styles  # type: ignore[index]
    pilots = engine._session.pilots  # type: ignore[attr-defined]
    assert [binding.config.style for binding in pilots] == styles
    # the strategy of the task reaches the pilots and the header too
    assert header["strategy"] == "control"  # type: ignore[index]
    assert {binding.strategy for binding in pilots} == {"control"}


def test_a_task_for_another_bridge_jar_is_refused_by_the_session_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = _session_engine(tmp_path, monkeypatch)
    task = game_pool.plan_task(
        task_id="j",
        seed=6,
        game_id="ser-jar",
        deck_paths=[str(DECK), *map(str, PRECONS)],
        seat_styles=[0.5] * 4,
        jar_sha256="0" * 64,
        engine_pin=PIN,
        skip_forced_decisions=None,
        jvm_options=NO_JVM_OPTIONS,
    )
    summary = engine.play(task.to_wire(), lambda: None)
    assert summary["failure_class"] == "BridgeJarMismatch"
    assert summary["failure_kind"] == "infrastructure"


# --- S1 Rest (#1660): the worker compares pin and switches with its own configuration ------------

_SKIP = "-Dcommanderlab.fullGame.skipForcedDecisions"
_NESTED = "-Dcommanderlab.nestedCopySkip"
_CREATE = series_record.os.O_CREAT | series_record.os.O_EXCL | series_record.os.O_WRONLY


def _task_for(**changes: object) -> GameTask:
    """A task planned for the session worker's jar, with the options ``changes`` overrides."""
    options: dict[str, object] = {
        "task_id": "cfg",
        "seed": 6,
        "game_id": "ser-cfg",
        "deck_paths": [str(DECK), *map(str, PRECONS)],
        "seat_styles": [0.5] * 4,
        "jar_sha256": hashlib.sha256(b"jar").hexdigest(),
        "engine_pin": PIN,
        "skip_forced_decisions": None,
        "jvm_options": NO_JVM_OPTIONS,
    }
    options.update(changes)
    return game_pool.plan_task(**options)  # type: ignore[arg-type]


_D1, _D2 = game_pool.jvm_env_digest("-Dx=1"), game_pool.jvm_env_digest("-Dx=2")
_TOOL_OPTIONS = {
    "nested_copy_skip": None,
    "env_options": {"JAVA_TOOL_OPTIONS": _D1},
    "command_options": None,
}


@pytest.mark.parametrize(
    ("flags", "changes", "named"),
    [
        ("", {"engine_pin": "q" * 40}, "Engine-Pin"),
        ("", {"skip_forced_decisions": True}, "erzwungene"),  # the command does not set it
        (f"{_SKIP}=true", {"skip_forced_decisions": None}, "erzwungene"),
        (f"{_SKIP}=true", {"skip_forced_decisions": False}, "erzwungene"),
        (
            "",
            {
                "jvm_options": {
                    "nested_copy_skip": False,
                    "env_options": {},
                    "command_options": None,
                }
            },
            "JVM-Optionen",
        ),
        (f"{_NESTED}=false", {"jvm_options": NO_JVM_OPTIONS}, "JVM-Optionen"),
        ("", {"jvm_options": _TOOL_OPTIONS}, "JVM-Optionen"),
    ],
)
def test_the_session_worker_refuses_a_task_planned_for_another_pin_or_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flags: str,
    changes: dict[str, object],
    named: str,
) -> None:
    engine = _session_engine(tmp_path, monkeypatch, flags)
    task = _task_for(**changes)
    # the task is consistent in itself (its key follows its fields): only the worker's own
    # configuration differs, and that is what refuses it
    assert game_pool.task_refusal(task.to_wire()) is None
    summary = engine.play(task.to_wire(), lambda: None)
    assert summary["failure_class"] == "GameKeyMismatch" and named in str(
        summary["failure_message"]
    )
    assert summary["failure_kind"] == "infrastructure" and summary["status"] == "failed"
    assert engine._session.pilots is None  # type: ignore[attr-defined]  # the engine never played


def test_the_session_worker_plays_a_task_that_matches_its_own_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = _session_engine(tmp_path, monkeypatch, f"{_SKIP}=true {_NESTED}=false")
    options = {"nested_copy_skip": False, "env_options": {}, "command_options": None}
    task = _task_for(skip_forced_decisions=True, jvm_options=options)
    assert engine.play(task.to_wire(), lambda: None)["status"] == "finished"
    # the worker read its environment at start: a variable set later is not its configuration
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "-Dx=1")
    assert engine.play(task.to_wire(), lambda: None)["status"] == "finished"


def test_the_session_worker_reads_the_jvm_option_variables_of_its_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_engine(tmp_path, monkeypatch)  # installs the scripted session, clears the variables
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", " -Dx=1 ")  # set before the worker starts
    engine = game_pool.SessionWorkerEngine(
        tmp_path, label="s", private_card_repository=False, command=None
    )
    assert engine.play(_task_for().to_wire(), lambda: None)["failure_class"] == "GameKeyMismatch"
    good = _task_for(jvm_options=_TOOL_OPTIONS)
    assert engine.play(good.to_wire(), lambda: None)["status"] == "finished"


def test_the_config_check_reads_pin_command_and_environment_it_is_given() -> None:
    wire = _task_for(skip_forced_decisions=True).to_wire()
    command = ("java", f"{_SKIP}=true", "-jar", "b")
    assert game_pool.config_refusal(wire, engine_pin=PIN, command=command, env={}) is None
    refused = game_pool.config_refusal(wire, engine_pin="z" * 40, command=command, env={})
    assert refused is not None and refused["failure_class"] == "GameKeyMismatch"
    assert game_pool.config_refusal({**wire, "engine_pin": None}, engine_pin=PIN, command=command)


def test_a_task_without_valid_jvm_options_gives_no_key_and_is_refused() -> None:
    wire = _task_for().to_wire()
    for bad in (None, "x", {"nested_copy_skip": None}, {**NO_JVM_OPTIONS, "extra": 1}):
        got = game_pool.task_refusal({**wire, "jvm_options": bad})
        assert got is not None and got["failure_class"] == "GameKeyMismatch", bad


# --- S1 Rest (#1660): which JVM options decide a game (the key) and which do not -----------------


def test_jvm_options_are_read_from_the_command_and_the_environment() -> None:
    read = game_pool.jvm_options_of
    assert read(("java", "-jar", "b"), {}) == NO_JVM_OPTIONS
    assert read(("java", f"{_NESTED}=false", "-jar", "b"), {})["nested_copy_skip"] is False
    assert read(("java", f"{_NESTED}=true", "-jar", "b"), {})["nested_copy_skip"] is True
    # the bridge turns it off for exactly "false" (no trimming, case matters)
    assert read(("java", f"{_NESTED}=False", "-jar", "b"), {})["nested_copy_skip"] is True
    assert read(("java", f"{_NESTED}= false", "-jar", "b"), {})["nested_copy_skip"] is True
    # the JVM takes the last of two equal -D options; what follows -jar is not a JVM option
    twice = ("java", f"{_NESTED}=false", f"{_NESTED}=true", "-jar", "b")
    assert read(twice, {})["nested_copy_skip"] is True
    assert read(("java", "-jar", "b", f"{_NESTED}=false"), {})["nested_copy_skip"] is None
    skip = game_pool.skip_forced_decisions_of
    assert skip(("java", f"{_SKIP}=true", f"{_SKIP}=false", "-jar", "b")) is False
    assert skip(("java", "-jar", "b", f"{_SKIP}=true")) is None
    assert skip(("java", f"{_SKIP}=TRUE", "-jar", "b")) is True
    env = {"JAVA_TOOL_OPTIONS": " -Dx=1 ", "JDK_JAVA_OPTIONS": "  ", "_JAVA_OPTIONS": "-Xss1m"}
    assert read(None, env)["env_options"] == {
        "JAVA_TOOL_OPTIONS": game_pool.jvm_env_digest("-Dx=1"),
        "_JAVA_OPTIONS": game_pool.jvm_env_digest("-Xss1m"),
    }
    # white space is normalised, the order of the options is not (it can matter to the JVM)
    assert game_pool.jvm_env_digest(" -Da   -Db ") == game_pool.jvm_env_digest("-Da -Db")
    assert game_pool.jvm_env_digest("-Da -Db") != game_pool.jvm_env_digest("-Db -Da")


def test_s3_the_forced_pass_switch_is_read_like_boolean_getboolean_without_trimming() -> None:
    """``Boolean.getBoolean``: "true" in any case, nothing trimmed (a trailing space is not true)."""
    skip = game_pool.skip_forced_decisions_of
    for padded in (f"{_SKIP}=true ", f"{_SKIP}= true", f"{_SKIP}=true\t", f"{_SKIP}=\ttrue"):
        assert skip(("java", padded, "-jar", "b")) is False, repr(padded)
    assert skip(("java", f"{_SKIP}=true", "-jar", "b")) is True
    assert skip(("java", f"{_SKIP}=True", "-jar", "b")) is True
    assert skip(("java", f"{_SKIP}=yes", "-jar", "b")) is False
    assert skip(("java", f"{_SKIP}=", "-jar", "b")) is False  # set, but empty: not true
    # the padded option is still the switch's own (no other option leaks into the key)
    assert game_pool.jvm_command_options_digest(("java", f"{_SKIP}=true ", "-jar", "b")) is None


def test_pure_performance_options_are_not_part_of_the_game_key() -> None:
    """gamesPerJvm, heap, collector, AppCDS and the loopback bind do not enter the key (named).

    ``gamesPerJvm`` has to stay out: a game must not depend on its position in its JVM, and the
    determinism guard can only catch that when the same key is played at two positions.
    """
    plain = ("java", "-jar", "b", "full-game")
    tuned = (
        "java",
        "-Dcommanderlab.fullGame.gamesPerJvm=16",
        "-Xmx6g",
        "-XX:+UseSerialGC",
        "-XX:SharedArchiveFile=/x/b.jsa",
        "-Xlog:disable",
        "-Dh2.bindAddress=127.0.0.1",
        "-jar",
        "b",
        "full-game",
    )
    assert game_pool.jvm_options_of(tuned, {}) == game_pool.jvm_options_of(plain, {})
    for gpj in (1, 8, 24):
        command = ("java", f"-Dcommanderlab.fullGame.gamesPerJvm={gpj}", "-jar", "b")
        assert game_pool.jvm_options_of(command, {}) == NO_JVM_OPTIONS
        assert game_pool.skip_forced_decisions_of(command) is None


@pytest.mark.parametrize(
    "options",
    [
        {"nested_copy_skip": False, "env_options": {}, "command_options": None},
        {"nested_copy_skip": True, "env_options": {}, "command_options": None},
        {
            "nested_copy_skip": None,
            "env_options": {"JAVA_TOOL_OPTIONS": _D1},
            "command_options": None,
        },
        {
            "nested_copy_skip": None,
            "env_options": {"JDK_JAVA_OPTIONS": _D1},
            "command_options": None,
        },
        {"nested_copy_skip": None, "env_options": {"_JAVA_OPTIONS": _D1}, "command_options": None},
        {
            "nested_copy_skip": None,
            "env_options": {"JAVA_TOOL_OPTIONS": _D2},
            "command_options": None,
        },
    ],
)
def test_each_jvm_option_that_can_change_a_game_changes_its_key_and_the_manifest(
    tmp_path: Path, options: dict[str, object]
) -> None:
    base, other = _plan(), _plan(jvm_options=options)
    assert other.game_key != base.game_key and other.game_key == _key_of(other, jvm_options=options)
    assert game_pool.task_key_of(other.to_wire()) == other.game_key
    ids = {"task_id": "t", "game_id": "g"}

    def start(key: str | None) -> SeriesRecord:
        games = [{**ids, "game_key": key}]
        return SeriesRecord.open(tmp_path, "mixed", games=games, table_hash=None, table=None)

    start(base.game_key)
    with pytest.raises(ManifestMismatch):  # a resume under other options is not the same series
        start(other.game_key)


def test_the_order_of_the_environment_options_does_not_change_the_key() -> None:
    first = {
        "nested_copy_skip": None,
        "env_options": {"_JAVA_OPTIONS": _D1, "JAVA_TOOL_OPTIONS": _D2},
        "command_options": None,
    }
    second = {
        "nested_copy_skip": None,
        "env_options": {"JAVA_TOOL_OPTIONS": _D2, "_JAVA_OPTIONS": _D1},
        "command_options": None,
    }
    assert _plan(jvm_options=first).game_key == _plan(jvm_options=second).game_key


@pytest.mark.parametrize(
    "bad",
    [
        {"nested_copy_skip": None},
        {**NO_JVM_OPTIONS, "gamesPerJvm": 16},
        {"nested_copy_skip": "false", "env_options": {}, "command_options": None},
        {
            "nested_copy_skip": None,
            "env_options": {"JAVA_TOOL_OPTIONS": 1},
            "command_options": None,
        },
        # the text itself (it can name machine paths) is never a valid value, only its digest
        {
            "nested_copy_skip": None,
            "env_options": {"JAVA_TOOL_OPTIONS": "-javaagent:/home/u/a.jar"},
            "command_options": None,
        },
        {**NO_JVM_OPTIONS, "command_options": "-javaagent:/home/u/a.jar"},  # text, not a digest
        {**NO_JVM_OPTIONS, "command_options": 7},
        {"nested_copy_skip": None, "env_options": {}},  # the field is required
        {**NO_JVM_OPTIONS, "env_options": ["x"]},
    ],
)
def test_a_game_key_takes_exactly_the_known_jvm_option_fields(bad: dict[str, object]) -> None:
    with pytest.raises(
        ValueError, match=r"nested_copy_skip|JVM-Optionen|env_options|command_options"
    ):
        series_record.game_key(**{**_KEY_INPUT, "jvm_options": bad})  # type: ignore[arg-type]


# --- S1 Rest (#1660): the manifest fallback without hard links is a race, not a broken series ----


def _no_hard_links(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_link(source: object, target: object) -> None:
        raise PermissionError("hard links are not supported here")

    monkeypatch.setattr(series_record.os, "link", no_link)


def test_a_second_start_that_meets_the_first_writer_inside_the_fallback_waits_and_joins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two writers, deterministic: A has created the file and not yet written it when B starts."""
    _no_hard_links(monkeypatch)
    games = _games("two", range(1, 3))
    waits: list[float] = []
    started: dict[str, SeriesRecord] = {}

    def a_slow_create(path: Path, data: bytes) -> None:
        fd = series_record.os.open(path, _CREATE)

        def a_writes_now(seconds: float) -> None:
            waits.append(seconds)  # B's first wait: A completes its write
            series_record.os.write(fd, data)
            series_record.os.close(fd)

        monkeypatch.setattr(series_record.time, "sleep", a_writes_now)
        started["b"] = _record(tmp_path, games, series="two")  # B: the file exists, still empty

    monkeypatch.setattr(series_record, "_create_exclusive", a_slow_create)
    started["a"] = _record(tmp_path, games, series="two")
    assert waits == [series_record.MANIFEST_READ_WAIT_SECONDS]  # B waited once, then read it whole
    assert started["a"].manifest == started["b"].manifest
    stored = json.loads(started["a"].manifest_path.read_text(encoding="utf-8"))
    assert [g["game_id"] for g in stored["games"]] == [g.game_id for g in games]
    assert sorted(p.name for p in started["a"].folder.iterdir()) == ["manifest.json"]


def test_a_start_that_meets_a_foreign_manifest_inside_the_race_never_replaces_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A writes the manifest of other games while B waits: B is a mismatch, A's file stays."""
    _no_hard_links(monkeypatch)
    foreign = _games("foreign", range(1, 4))
    mine = _games("mine", range(1, 3))
    waits: list[float] = []

    def foreign_writer(path: Path, data: bytes) -> None:
        fd = series_record.os.open(path, _CREATE)

        def foreign_writes_now(seconds: float) -> None:
            waits.append(seconds)
            series_record.os.write(fd, data)
            series_record.os.close(fd)

        monkeypatch.setattr(series_record.time, "sleep", foreign_writes_now)
        with pytest.raises(ManifestMismatch, match="unveränderlich"):
            _record(tmp_path, mine, series="forn")

    monkeypatch.setattr(series_record, "_create_exclusive", foreign_writer)
    _record(tmp_path, foreign, series="forn")
    folder = series_record.series_folder(tmp_path, "forn")
    stored = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert [g["game_id"] for g in stored["games"]] == [g.game_id for g in foreign]
    assert len(waits) == 1


def test_a_manifest_that_stays_empty_is_reported_after_the_reads_not_after_the_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []
    monkeypatch.setattr(series_record.time, "sleep", waits.append)
    folder = series_record.series_folder(tmp_path, "left")
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_bytes(b"")  # a first start that aborted after its create
    with pytest.raises(ManifestMismatch) as caught:
        _record(tmp_path, _games("left", range(1, 2)), series="left")
    text = str(caught.value)
    assert f"{series_record.MANIFEST_READ_ATTEMPTS} Leseversuchen" in text
    assert "unvollständig" in text and "nie überschrieben" in text
    assert len(waits) == series_record.MANIFEST_READ_ATTEMPTS - 1
    assert (folder / "manifest.json").read_bytes() == b""  # never rewritten


def test_a_manifest_that_is_no_object_is_not_waited_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []
    monkeypatch.setattr(series_record.time, "sleep", waits.append)
    folder = series_record.series_folder(tmp_path, "arr")
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ManifestMismatch, match="kein Objekt"):
        _record(tmp_path, _games("arr", range(1, 2)), series="arr")
    assert waits == []


# --- S1 Rest (#1660): a series recorded before the key version is never resumed or mixed ---------

#: Written by the code of main before this change (``SeriesRecord.open`` and ``game_key`` of
#: ``studio-game-key-1``): a manifest without ``game_key_schema``, one finished game in its journal.
_OLD_KEY_1, _OLD_KEY_2 = (
    "be68bece408961f7b88fccbf3a43535c4f8c924ee9a52325140583de5701d312",
    "78ddb23d74ec02e55af7bd64c7d5bd2204c2da2392cde5906ad866313db27f19",
)
_OLD_MANIFEST = (
    '{"created_at":"2026-11-20T00:00:00Z","games":[{"game_id":"old-base-s1-t0","game_key":"'
    + _OLD_KEY_1
    + '","task_id":"base:1:0"},{"game_id":"old-base-s2-t0","game_key":"'
    + _OLD_KEY_2
    + '","task_id":"base:2:0"}],"schema":"studio-series-manifest-1","series_id":"old1",'
    '"table":null,"table_hash":null}'
)
_OLD_JOURNAL = (
    '{"failure_class":null,"game_id":"old-base-s1-t0","game_key":"'
    + _OLD_KEY_1
    + '","recorded_at":"2026-11-22T00:50:34Z","schema":"studio-series-journal-1",'
    '"semantic_transcript_sha256":"' + "a" * 64 + '","status":"finished","summary":'
    '{"semantic_transcript_sha256":"' + "a" * 64 + '","status":"finished"}}\n'
)


def _old_series(tmp_path: Path) -> Path:
    folder = series_record.series_folder(tmp_path, "old1")
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(_OLD_MANIFEST, encoding="utf-8")
    (folder / "journal.jsonl").write_text(_OLD_JOURNAL, encoding="utf-8")
    return folder


def _new_plan_of_old_games() -> list[dict[str, object]]:
    """What the new code plans for the same two games: the same ids, other keys."""
    games = []
    for seed in (1, 2):
        task = _plan(seed=seed, task_id=f"base:{seed}:0", game_id=f"old-base-s{seed}-t0")
        games.append({"task_id": task.task_id, "game_id": task.game_id, "game_key": task.game_key})
    assert {g["game_key"] for g in games}.isdisjoint({_OLD_KEY_1, _OLD_KEY_2})
    return games


def test_a_series_recorded_with_the_old_key_version_is_refused_honestly_not_as_a_violation(
    tmp_path: Path,
) -> None:
    folder = _old_series(tmp_path)
    manifest_before = (folder / "manifest.json").read_bytes()
    journal_before = (folder / "journal.jsonl").read_bytes()
    with pytest.raises(series_record.KeyVersionMismatch) as caught:
        SeriesRecord.open(
            tmp_path, "old1", games=_new_plan_of_old_games(), table_hash=None, table=None
        )
    text = str(caught.value)
    assert "studio-game-key-1" in text and series_record.GAME_KEY_SCHEMA in text
    assert "nicht vergleichbar" in text and "neue Serie starten" in text
    assert not isinstance(caught.value, DeterminismViolation)
    assert DETERMINISM_VIOLATION not in text
    # nothing is written into the old series: no new game is mixed in, no manifest rewritten
    assert (folder / "manifest.json").read_bytes() == manifest_before
    assert (folder / "journal.jsonl").read_bytes() == journal_before
    assert sorted(p.name for p in folder.iterdir()) == ["journal.jsonl", "manifest.json"]


def test_the_old_series_is_read_as_it_was_recorded_and_shows_no_violation(
    tmp_path: Path,
) -> None:
    _old_series(tmp_path)
    assert series_record.series_violation(tmp_path, "old1") is None  # stored keys, not recomputed
    guard = series_record.series_guard(tmp_path, "old1")
    assert guard == {"violation": False, "unguarded": 0, "finished": 1, "comparable_keys": 0}
    problem = series_record.series_key_problem(tmp_path, "old1")
    assert problem is not None and "neue Serie starten" in problem
    assert series_record.series_key_problem(tmp_path, "unknown") is None  # no manifest


def test_a_series_started_by_the_new_code_names_its_key_version_and_resumes(
    tmp_path: Path,
) -> None:
    games = _games("ver", range(1, 3))
    record = _record(tmp_path, games, series="ver")
    assert record.manifest["game_key_schema"] == series_record.GAME_KEY_SCHEMA
    assert _record(tmp_path, games, series="ver").manifest == record.manifest  # resumes as before
    assert series_record.series_key_problem(tmp_path, "ver") is None


def test_a_manifest_naming_a_future_key_version_is_refused_too(tmp_path: Path) -> None:
    folder = series_record.series_folder(tmp_path, "fut")
    folder.mkdir(parents=True)
    manifest = {**json.loads(_OLD_MANIFEST), "game_key_schema": "studio-game-key-9"}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(series_record.KeyVersionMismatch, match="studio-game-key-9"):
        _record(tmp_path, _games("fut", range(1, 2)), series="fut")


# --- S1 Rest (#1660): no raw JVM option text or command line on disk (AGENTS.md section 12) ------


def test_a_path_like_jvm_option_value_is_never_written_to_the_manifest_journal_or_task(
    tmp_path: Path,
) -> None:
    secret = r"-javaagent:/home/alice/agents/trace.jar -Dwork.dir=C:\Users\bob\lab"
    command = ("java", "-Dcommanderlab.nestedCopySkip=false", "-jar", "/home/alice/b.jar")
    options = game_pool.jvm_options_of(command, {"JAVA_TOOL_OPTIONS": secret})
    task = _plan(jvm_options=options)
    names = ("alice", "bob", "agents", "trace.jar", "work.dir", "-javaagent", "C:", "/home/")
    wire = json.dumps(task.to_wire(), sort_keys=True)
    ids = {"task_id": task.task_id, "game_id": task.game_id, "game_key": task.game_key}
    record = SeriesRecord.open(tmp_path, "priv", games=[ids], table_hash=None, table=None)
    record.record(task.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    refused = game_pool.config_refusal(
        task.to_wire(), engine_pin="z" * 40, command=command, env={"JAVA_TOOL_OPTIONS": secret}
    )
    assert refused is not None
    written = [wire, json.dumps(refused)]
    written += [p.read_text(encoding="utf-8") for p in record.folder.iterdir()]
    assert len(written) == 4  # task, refusal, manifest, journal
    for text in written:
        for name in names:
            assert name not in text, name
    # what is written is the digest of the normalised text, and the key follows it
    assert options["env_options"] == {"JAVA_TOOL_OPTIONS": game_pool.jvm_env_digest(secret)}
    assert task.game_key == _key_of(task, jvm_options=options)
    assert game_pool.jvm_env_digest(secret) in wire


# --- S1 Rest (#1660): the options before -jar of the worker command are in the key --------------

#: One example per entry of ``PERFORMANCE_ONLY_JVM_OPTIONS`` (in its order): none changes a game.
_PERFORMANCE_EXAMPLES = (
    "-Xmx6g",
    "-Xms512m",
    "-Xss4m",
    "-XX:+UseSerialGC",
    "-XX:+UseStringDeduplication",
    "-Xshare:auto",
    "-XX:SharedArchiveFile=/x/y/bridge.jsa",
    "-Xlog:all=warning:stderr",
    "-Dh2.bindAddress=127.0.0.1",
    f"{_SKIP}=true",
    f"{_NESTED}=false",
    "-Dcommanderlab.fullGame.gamesPerJvm=16",
)


def test_every_performance_only_option_is_named_with_a_reason_and_one_example_each() -> None:
    entries = game_pool.PERFORMANCE_ONLY_JVM_OPTIONS
    assert len(entries) == len(_PERFORMANCE_EXAMPLES)
    for (pattern, reason), example in zip(entries, _PERFORMANCE_EXAMPLES, strict=True):
        assert reason.strip() and re.fullmatch(pattern, example, re.DOTALL), pattern
        # the example is left out of the digest, and so only through its own entry
        assert game_pool.jvm_command_options_digest(("java", example, "-jar", "b")) is None


def test_options_that_decide_nothing_do_not_change_the_command_digest() -> None:
    digest = game_pool.jvm_command_options_digest
    plain = ("java", "-Dfoo=1", "-jar", "b", "full-game")
    assert digest(("java", "-jar", "b")) is None
    assert digest(("java", *_PERFORMANCE_EXAMPLES, "-jar", "b")) is None
    # logically equal option sets: performance options anywhere, in any order, other values,
    # another launcher path, other arguments after -jar
    equal = (
        ("java", "-Xmx3g", "-Dfoo=1", "-XX:+UseSerialGC", "-jar", "b", "full-game"),
        ("/opt/jdk/bin/java", "-Dfoo=1", "-Xlog:disable", "-Xss1m", "-jar", "c.jar"),
        ("java", "-XX:+UseG1GC", "-Xms1g", "-Dfoo=1", "-Dh2.bindAddress=0.0.0.0", "-jar", "b"),
        (
            "java",
            f"{_SKIP}=false",
            "-Dfoo=1",
            "-Dcommanderlab.fullGame.gamesPerJvm=24",
            "-jar",
            "b",
        ),
    )
    assert digest(plain) is not None
    for command in equal:
        assert digest(command) == digest(plain), command
    assert game_pool.jvm_options_of(plain, {}) == game_pool.jvm_options_of(equal[0], {})
    # what follows -jar is an argument of the bridge, not a JVM option
    assert digest(("java", "-jar", "b", "-Dfoo=9", "-javaagent:/a.jar")) is None


@pytest.mark.parametrize(
    "different",
    [
        ("java", "-javaagent:/opt/a.jar", "-Dfoo=1", "-jar", "b"),
        ("java", "-javaagent:/opt/b.jar", "-Dfoo=1", "-jar", "b"),
        ("java", "-Dfoo=2", "-jar", "b"),
        ("java", "-Dfoo=1", "-Dbar=1", "-jar", "b"),
        ("java", "-Dfoo=1", "-Dfoo=2", "-jar", "b"),  # the last of two equal -D wins: order counts
        ("java", "-Dfoo=2", "-Dfoo=1", "-jar", "b"),
        ("java", "-Dfoo=1", "-cp", "/x/extra.jar", "-jar", "b"),
        ("java", "-Dfoo=1", "-Xmn256m", "-jar", "b"),  # not on the list: fail-closed, it counts
        ("java", "-Dfoo=1", "-Xmxbig", "-jar", "b"),  # not a heap size: not matched whole
        ("java", "-Dfoo=1", "-XX:+UseSerialGCExtra", "-jar", "b"),
        ("java", "-Dfoo=1", "-Dcommanderlab.nestedCopySkip", "-jar", "b"),  # no "=": not the switch
        ("java", "-Dfoo=1", "-Dfoo=1", "-jar", "b"),  # a repeat is another list
    ],
)
def test_another_agent_property_or_unknown_option_changes_the_digest_and_the_game_key(
    different: tuple[str, ...],
) -> None:
    base = ("java", "-Dfoo=1", "-jar", "b")
    base_digest = game_pool.jvm_command_options_digest(base)
    digest = game_pool.jvm_command_options_digest(different)
    assert digest is not None and digest != base_digest
    # the digest alone reaches the key: the planned game, its wire form and the worker's key agree
    options = game_pool.jvm_options_of(different, {})
    first, second = (
        _plan(jvm_options=game_pool.jvm_options_of(base, {})),
        _plan(jvm_options=options),
    )
    assert second.game_key != first.game_key and second.game_key == _key_of(
        second, jvm_options=options
    )
    assert game_pool.task_key_of(second.to_wire()) == second.game_key


def test_the_order_of_the_command_options_changes_the_digest() -> None:
    """The JVM takes the last of two equal -D options and runs agents in order."""
    digest = game_pool.jvm_command_options_digest
    first = digest(("java", "-Dfoo=1", "-Dfoo=2", "-jar", "b"))
    second = digest(("java", "-Dfoo=2", "-Dfoo=1", "-jar", "b"))
    assert first is not None and second is not None and first != second
    agents = digest(("java", "-javaagent:/a.jar", "-javaagent:/b.jar", "-jar", "b"))
    assert agents != digest(("java", "-javaagent:/b.jar", "-javaagent:/a.jar", "-jar", "b"))


def test_a_command_with_no_option_of_its_own_and_one_with_a_set_option_are_not_equal_in_the_key() -> (
    None
):
    none = game_pool.jvm_options_of(("java", "-Xmx3g", "-jar", "b"), {})
    agent = game_pool.jvm_options_of(("java", "-Xmx3g", "-javaagent:/a.jar", "-jar", "b"), {})
    assert none["command_options"] is None and isinstance(agent["command_options"], str)
    assert _plan(jvm_options=none).game_key != _plan(jvm_options=agent).game_key


def test_a_path_like_command_option_is_never_written_anywhere(tmp_path: Path) -> None:
    command = (
        "/home/alice/jdk/bin/java",
        r"-javaagent:/home/alice/agents/trace.jar=C:\Users\bob\out",
        "-Dwork.dir=/home/alice/lab",
        "-Xmx3g",
        "-jar",
        "/home/alice/b.jar",
        "full-game",
    )
    options = game_pool.jvm_options_of(command, {})
    digest = options["command_options"]
    assert isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest)
    task = _plan(jvm_options=options)
    ids = {"task_id": task.task_id, "game_id": task.game_id, "game_key": task.game_key}
    record = SeriesRecord.open(tmp_path, "cmdpriv", games=[ids], table_hash=None, table=None)
    record.record(task.game_id, {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    # the worker's command lacks the agent: refused, and the refusal text names no option
    refused = game_pool.config_refusal(
        task.to_wire(), engine_pin=PIN, command=("java", "-jar", "b"), env={}
    )
    assert refused is not None and refused["failure_class"] == "GameKeyMismatch"
    with pytest.raises(ValueError) as caught:
        series_record.game_key(
            **{**_KEY_INPUT, "jvm_options": {**options, "command_options": command[1]}}
        )  # type: ignore[arg-type]
    written = [json.dumps(task.to_wire(), sort_keys=True), json.dumps(refused), str(caught.value)]
    written += [p.read_text(encoding="utf-8") for p in record.folder.iterdir()]
    assert len(written) == 5  # task, refusal, error text, manifest, journal
    for text in written:
        for name in (
            "alice",
            "bob",
            "agents",
            "trace.jar",
            "work.dir",
            "-javaagent",
            "C:",
            "/home/",
        ):
            assert name not in text, name
    assert digest in written[0] and task.game_key == _key_of(task, jvm_options=options)


@pytest.mark.parametrize(
    ("worker_flags", "task_command"),
    [
        ("-javaagent:/x/a.jar", ("java", "-jar", "b")),  # the worker has an agent, the task not
        ("", ("java", "-javaagent:/x/a.jar", "-jar", "b")),  # the task has one, the worker not
        ("-javaagent:/x/a.jar", ("java", "-javaagent:/x/other.jar", "-jar", "b")),
        ("-Dfoo=1", ("java", "-Dfoo=2", "-jar", "b")),
    ],
)
def test_the_session_worker_refuses_a_task_planned_for_other_command_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    worker_flags: str,
    task_command: tuple[str, ...],
) -> None:
    engine = _session_engine(tmp_path, monkeypatch, worker_flags)
    task = _task_for(jvm_options=game_pool.jvm_options_of(task_command, {}))
    assert game_pool.task_refusal(task.to_wire()) is None  # in itself consistent
    summary = engine.play(task.to_wire(), lambda: None)
    assert summary["failure_class"] == "GameKeyMismatch" and "Befehl" in str(
        summary["failure_message"]
    )
    assert summary["failure_kind"] == "infrastructure" and summary["status"] == "failed"
    assert engine._session.pilots is None  # type: ignore[attr-defined]  # the engine never played


def test_the_session_worker_plays_a_task_with_the_same_command_options_and_other_performance_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # gamesPerJvm=2 is in the worker's command already; the supervisor's command differs in
    # performance-only options only
    engine = _session_engine(tmp_path, monkeypatch, "-javaagent:/x/a.jar -Xmx1g")
    planned = ("java", "-Xmx6g", "-XX:+UseSerialGC", "-javaagent:/x/a.jar", "-jar", "b")
    task = _task_for(jvm_options=game_pool.jvm_options_of(planned, {}))
    assert engine.play(task.to_wire(), lambda: None)["status"] == "finished"


def test_the_pool_ends_the_series_on_a_determinism_violation(tmp_path: Path) -> None:
    first, second = _tasks(range(1, 3), "dv")
    record = _record(tmp_path, [first, second])
    # an earlier game with the key of ``first`` gave another transcript
    record.record(first.game_id, {"status": "finished", "semantic_transcript_sha256": "0" * 64})
    record = _record(tmp_path, [first, second])
    record._entries.pop(first.game_id)  # make the pool play it again, as #1589 reuse would
    pool, _ = _pool(tmp_path, workers=1)
    with pool, pytest.raises(DeterminismViolation):
        pool.run([first, second], record=record)


def test_a_foreign_log_is_not_counted_and_a_resumed_series_reads_its_journal(
    tmp_path: Path,
) -> None:
    tasks = _tasks(range(1, 4), "res")
    record = _record(tmp_path, tasks)
    pool, _ = _pool(tmp_path, workers=1)
    with pool:
        first = pool.run(tasks[:1], record=record)
    # a foreign game in the series folder and journal, and a line cut off by the cancel
    folder = record.folder
    folder.joinpath("foreign.jsonl").write_text('{"kind":"header"}\n', encoding="utf-8")
    with record.journal_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {"game_id": "foreign", "status": "finished", "summary": {"status": "finished"}}
            )
            + "\n"
        )
        handle.write('{"game_id": "g-res-s2", "sta')
    resumed = _record(tmp_path, tasks)
    assert set(resumed.results()) == {"g-res-s1"} and resumed.ignored_lines == 2
    played: list[str] = []
    pool, _ = _pool(tmp_path, workers=1)
    with pool:
        second = pool.run(tasks, record=resumed, on_done=lambda t, _s: played.append(t.task_id))
    assert second["res:1"] == first["res:1"]  # from the journal, not played again
    assert pool.summary()["games_finished"] == 2  # only the two missing games were played
    assert sorted(played) == ["res:1", "res:2", "res:3"]
    with pytest.raises(GamePoolError, match="not in the manifest"):
        pool_x, _ = _pool(tmp_path, workers=1)
        with pool_x:
            pool_x.run(_tasks(range(9, 10), "stranger"), record=resumed)


def test_an_infrastructure_failure_is_final_on_resume_like_in_the_progress_log(
    tmp_path: Path,
) -> None:
    """A resumed series counts what an uninterrupted one counted: the failure is not replayed."""
    tasks = _tasks(range(1, 3), "inf")
    original = Path(tasks[0].deck_paths[0]).read_text(encoding="utf-8")
    Path(tasks[0].deck_paths[0]).write_text('{"deck": "changed"}', encoding="utf-8")
    record = _record(tmp_path, tasks)
    pool, _ = _pool(tmp_path, workers=1)
    with pool:
        first = pool.run(tasks[:1], record=record)
    assert first["inf:1"]["failure_class"] == "DeckHashMismatch"
    Path(tasks[0].deck_paths[0]).write_text(original, encoding="utf-8")  # the file is repaired
    pool, _ = _pool(tmp_path, workers=1)
    with pool:
        resumed = pool.run(tasks, record=_record(tmp_path, tasks))
    assert resumed["inf:1"] == first["inf:1"]  # from the journal, not played again
    assert resumed["inf:2"]["status"] == "finished"
    assert pool.summary()["games_finished"] == 1


def test_the_pool_default_wall_limit_is_the_four_seat_value() -> None:
    assert game_pool.GAME_WALL_LIMIT_SECONDS == table_spec.game_wall_limit_seconds(4) == 1800.0


def test_the_worker_reads_its_pin_from_the_one_place_the_studio_names_it(tmp_path: Path) -> None:
    from commander_lab.qualification.current_boundary.bridge_launcher import (
        canonical_xmage_engine_pin,
    )

    assert game_pool.own_engine_pin(tmp_path) == canonical_xmage_engine_pin()


@pytest.mark.parametrize("state", [{}, {"pin": None}, {"pin": ""}])
def test_own_engine_pin_refuses_missing_or_blank_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: dict[str, object]
) -> None:
    from commander_lab.studio import launch

    monkeypatch.setattr(launch, "engine_state", lambda _folder: state)
    with pytest.raises(game_pool.GamePoolError, match="kein Engine-Pin bekannt"):
        game_pool.own_engine_pin(tmp_path)


def test_audit_series_folder_handles_valid_violated_and_corrupt_cases(tmp_path: Path) -> None:
    """S1 (#1660): audit_series_folder fails closed on violation, corrupt journal or corrupt manifest."""
    key = "a" * 64
    manifest = {
        "schema": series_record.MANIFEST_SCHEMA,
        "series_id": "s",
        "table_hash": None,
        "table": None,
        "game_key_schema": series_record.GAME_KEY_SCHEMA,
        "games": [
            {"task_id": "t1", "game_id": "g1", "game_key": key},
            {"task_id": "t2", "game_id": "g2", "game_key": key},
        ],
    }

    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (clean / "journal.jsonl").write_text(
        json.dumps(
            {
                "game_id": "g1",
                "game_key": key,
                "status": "finished",
                "semantic_transcript_sha256": "1" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    res_clean = series_record.audit_series_folder(clean)
    assert res_clean.violated is False and res_clean.members == frozenset({"g1", "g2"})

    viol = tmp_path / "viol"
    viol.mkdir()
    (viol / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (viol / "journal.jsonl").write_text(
        json.dumps(
            {
                "game_id": "g1",
                "game_key": key,
                "status": "finished",
                "semantic_transcript_sha256": "1" * 64,
            }
        )
        + "\n"
        + json.dumps(
            {
                "game_id": "g2",
                "game_key": key,
                "status": "finished",
                "semantic_transcript_sha256": "2" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    res_viol = series_record.audit_series_folder(viol)
    assert res_viol.violated is True and res_viol.members == frozenset({"g1", "g2"})

    corrupt_j = tmp_path / "corrupt_j"
    corrupt_j.mkdir()
    (corrupt_j / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (corrupt_j / "journal.jsonl").write_text("{corrupt\n", encoding="utf-8")
    res_cj = series_record.audit_series_folder(corrupt_j)
    assert res_cj.violated is True and res_cj.members == frozenset({"g1", "g2"})

    corrupt_m = tmp_path / "corrupt_m"
    corrupt_m.mkdir()
    (corrupt_m / "manifest.json").write_text("{corrupt", encoding="utf-8")
    res_cm = series_record.audit_series_folder(corrupt_m)
    assert res_cm.violated is True and res_cm.members is None

    no_m = tmp_path / "no_m"
    no_m.mkdir()
    (no_m / "journal.jsonl").write_text("{}\n", encoding="utf-8")
    res_nm = series_record.audit_series_folder(no_m)
    assert res_nm.violated is True and res_nm.members is None


def test_close_recorded_game_propagates_semantic_transcript_hash_for_series_guard(
    tmp_path: Path,
) -> None:
    """S1 (#1660): pool worker summaries must carry semantic_transcript_sha256 so the guard runs."""
    from types import SimpleNamespace

    from commander_lab.studio.play import GameRecorder, close_recorded_game

    transcript_hash = "a" * 64
    recorder = GameRecorder(
        tmp_path,
        "g-hash",
        header={"game_id": "g-hash", "seats": [{"seat": 0}, {"seat": 1}]},
    )
    outcome = SimpleNamespace(
        status="finished",
        winner_seats=(1,),
        decision_count=42,
        forced_decisions_skipped=3,
        engine_version="1.4.62",
        semantic_transcript_sha256=transcript_hash,
        result_payload={"forced_decisions_skipped": 3},
    )
    summary = close_recorded_game(recorder, outcome)  # type: ignore[arg-type]
    assert summary["semantic_transcript_sha256"] == transcript_hash

    key = "k" * 64
    rec = series_record.SeriesRecord.open(
        tmp_path,
        "s-guarded",
        games=[{"game_id": "g-hash", "game_key": key, "seed": 1}],
        table_hash=None,
        table=None,
    )
    rec.record("g-hash", summary)
    guard = series_record.series_guard(tmp_path, "s-guarded")
    assert guard is not None
    assert guard["finished"] == 1
    assert guard["unguarded"] == 0
    assert guard["violation"] is False


def test_hard_kill_mid_jvm_life_keeps_earlier_finished_game_logs_closed(
    tmp_path: Path,
) -> None:
    """#1586: hard process kill mid-JVM leaves earlier finished games closed on disk as finished.

    Runs real ``SessionWorkerEngine.play`` inside a real worker subprocess (budget=4 games per JVM).
    Games 1 and 2 finish inside the same open JVM life; during game 3 the worker process is
    hard-killed (SIGKILL on POSIX, os._exit(9) on Windows) before the JVM ever closes. Games 1 and 2
    must already have closed ``.jsonl.gz`` logs with ``status == 'finished'`` and valid results,
    while the killed in-flight game 3 must not read as finished.
    """
    from commander_lab.studio import games as studio_games

    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"mid-jvm-kill-jar")
    jar_sha = hashlib.sha256(jar.read_bytes()).hexdigest()
    worker_script = tmp_path / "mid_jvm_kill_worker.py"
    worker_script.write_text(
        textwrap.dedent(
            """
            import os, signal, sys
            from pathlib import Path
            from commander_lab.engine.rules import full_game_series
            from commander_lab.engine.rules.full_game import FullGameHiddenInformationAudit
            from commander_lab.engine.rules.full_game_pilot.common import FULL_GAME_EVIDENCE_CLASS
            from commander_lab.engine.rules.full_game_series import (
                build_series_result,
                checked_shutdown_ack,
            )
            from commander_lab.studio import game_pool

            DATA = Path(sys.argv[2])
            JAR = Path(sys.argv[3])
            PIN = "p" * 40
            for key in ("JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS"):
                os.environ.pop(key, None)
            os.environ["COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"] = (
                f"java -Dcommanderlab.fullGame.gamesPerJvm=4 -jar {JAR} full-game"
            )
            game_pool.own_engine_pin = lambda _folder: PIN

            class MidJvmKillSession:
                def __init__(self, runner, *, id_prefix=""):
                    self.runner = runner
                    self.lives = ()
                    self._played = 0
                    self._life_id = f"{id_prefix}-1"

                def play(self, scenario, decks, pilots):
                    self._played += 1
                    recorder = self.runner._recorder_for(scenario)
                    if "killme" in recorder.game_id:
                        # Game 3 is in flight inside the SAME open JVM life: hard-kill the worker!
                        if hasattr(signal, "SIGKILL"):
                            os.kill(os.getpid(), signal.SIGKILL)
                        os._exit(9)
                    self.runner.on_played(recorder.game_id)
                    seed = scenario.seed
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
                        "decision_count": 25 + seed,
                        "outcomes": [{"seat": i, "life": 5, "won": i == seed % 4} for i in range(4)],
                        "transcript": [],
                    }
                    wire_gid = f"{scenario.scenario_id}:{scenario.candidate_id}:{seed}"
                    ack = checked_shutdown_ack(
                        {
                            "game_id": wire_gid,
                            "shut_down": True,
                            "engine_thread_alive": False,
                            "game_over": True,
                            "shutdown_unwind": "none",
                        },
                        game_id=wire_gid,
                    )
                    return build_series_result(
                        scenario,
                        {"engine_version": "1.4.61", "engine_commit": "b" * 40},
                        wire,
                        ack,
                        jvm_life_id=self._life_id,
                        position_in_jvm=self._played,
                        hidden_audit=FullGameHiddenInformationAudit(),
                    )

                def close(self):
                    return ()

            full_game_series.XmageFullGameSeriesSession = MidJvmKillSession
            sys.exit(
                game_pool.worker_main(
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    label=sys.argv[1],
                    engine_factory=lambda: game_pool.SessionWorkerEngine(
                        DATA,
                        label=sys.argv[1],
                        private_card_repository=False,
                        command=None,
                    ),
                )
            )
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "games").mkdir(exist_ok=True)
    deck_paths = [str(DECK), *map(str, PRECONS)]
    tasks = [
        game_pool.plan_task(
            task_id=f"mk:{seed}",
            seed=seed,
            game_id=gid,
            deck_paths=deck_paths,
            seat_styles=[0.5, 0.5, 0.5, 0.5],
            jar_sha256=jar_sha,
            engine_pin=PIN,
            skip_forced_decisions=None,
            jvm_options=NO_JVM_OPTIONS,
            strategy="generic",
        )
        for seed, gid in (
            (1, "g-mk-1"),
            (2, "g-mk-2"),
            (3, "g-mk-killme-3"),
        )
    ]

    pool = GamePool(
        tmp_path,
        workers=1,
        worker_argv=lambda label: [
            sys.executable,
            str(worker_script),
            label,
            str(tmp_path),
            str(jar),
        ],
        game_wall_limit_seconds=30.0,
    )
    with pool:
        results = pool.run(tasks)

    assert results["mk:1"]["status"] == "finished"
    assert results["mk:2"]["status"] == "finished"
    assert results["mk:1"]["jvm_life_id"] == results["mk:2"]["jvm_life_id"]
    assert (results["mk:1"]["position_in_jvm"], results["mk:2"]["position_in_jvm"]) == (1, 2)
    assert results["mk:3"]["status"] == "failed"
    assert results["mk:3"]["failure_class"] == "WorkerExited"

    games_dir = tmp_path / "games"
    for seed, gid in ((1, "g-mk-1"), (2, "g-mk-2")):
        assert not (games_dir / f"{gid}.jsonl").exists()
        assert (games_dir / f"{gid}.jsonl.gz").is_file()
        loaded = studio_games.read_game(tmp_path, gid, start=0, count=1)
        result = loaded["result"]
        assert isinstance(result, dict)
        assert result["status"] == "finished"
        assert result["winner_seats"] == [seed % 4]
        assert result["decision_count"] == 25 + seed
        assert result["jvm_life_id"] == results[f"mk:{seed}"]["jvm_life_id"]
        assert result["position_in_jvm"] == seed
        assert len(str(result["semantic_transcript_sha256"])) == 64

    # Game 3 was killed in flight: its unclosed log was closed with WorkerExited, never finished.
    assert not (games_dir / "g-mk-killme-3.jsonl").exists()
    packed_3 = games_dir / "g-mk-killme-3.jsonl.gz"
    assert packed_3.is_file()
    with gzip.open(packed_3, "rt", encoding="utf-8") as handle:
        tail = json.loads(handle.read().splitlines()[-1])
    assert tail["status"] == "failed"
    assert tail["failure_class"] == "WorkerExited"


def _write_finished_game_log(
    data_folder: Path,
    game_id: str,
    *,
    seed: int,
    seat: int,
    base_deck_id: str,
    transcript_sha: str,
    human_seats: list[int] | None = None,
) -> None:
    games_dir = data_folder / "games"
    games_dir.mkdir(parents=True, exist_ok=True)
    header: dict[str, object] = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "data_class": "SIMULATED_RESULT",
        "game_id": game_id,
        "seed": seed,
        "engine_commit": "e" * 40,
        "bridge_jar_sha256": "j" * 64,
        "bridge_qualification_state": "BRIDGE_AHEAD_OF_QUALIFICATION",
        "covered_by_sealed_epoch": False,
        "pilot": "GenericCommanderPilot 1.0.0",
        "pilot_fingerprint": "f" * 64,
        "decision_policy": "xmage-full-game-policy-1.0.0",
        "seats": [
            {
                "seat": i,
                "deck_id": base_deck_id if i == seat else f"opp-{i}",
                "commanders": ["Chulane, Teller of Tales"],
                "deck_hash": "d" * 64,
            }
            for i in range(4)
        ],
    }
    if human_seats:
        header["human_seats"] = human_seats
    closing = {
        "kind": "result",
        "status": "finished",
        "winner_seats": [seat],
        "decision_count": 42,
        "semantic_transcript_sha256": transcript_sha,
    }
    with gzip.open(games_dir / f"{game_id}.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
        handle.write(json.dumps(closing) + "\n")


def test_find_reusable_baseline_games_enforces_key_version_audit_and_cross_series_determinism(
    tmp_path: Path,
) -> None:
    """#1589: reuse admits only clean studio-game-key-2 logs and fails closed on mismatch."""
    k1, k2, k3, k4 = "1" * 64, "2" * 64, "3" * 64, "4" * 64
    h1, h2, h3, h4 = "a" * 64, "b" * 64, "c" * 64, "d" * 64

    # Clean studio-game-key-2 series with g1 (valid) and g2 (human seat -> must be skipped)
    _write_finished_game_log(
        tmp_path, "s1-base-1", seed=10, seat=0, base_deck_id="old--base", transcript_sha=h1
    )
    _write_finished_game_log(
        tmp_path,
        "s1-base-2",
        seed=11,
        seat=1,
        base_deck_id="old--base",
        transcript_sha=h2,
        human_seats=[1],
    )
    rec1 = series_record.SeriesRecord.open(
        tmp_path,
        "ser-clean",
        games=[
            {"task_id": "base:10:0", "game_id": "s1-base-1", "game_key": k1},
            {"task_id": "base:11:1", "game_id": "s1-base-2", "game_key": k2},
        ],
        table_hash=None,
        table=None,
    )
    rec1.record("s1-base-1", {"status": "finished", "semantic_transcript_sha256": h1})
    rec1.record("s1-base-2", {"status": "finished", "semantic_transcript_sha256": h2})

    # Legacy studio-game-key-1 series -> must be ignored even if key string matches
    _write_finished_game_log(
        tmp_path, "s-leg-3", seed=12, seat=2, base_deck_id="old--base", transcript_sha=h3
    )
    leg_dir = series_record.series_folder(tmp_path, "ser-legacy")
    leg_dir.mkdir(parents=True, exist_ok=True)
    (leg_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": series_record.MANIFEST_SCHEMA,
                "series_id": "ser-legacy",
                "game_key_schema": "studio-game-key-1",
                "games": [{"task_id": "base:12:2", "game_id": "s-leg-3", "game_key": k3}],
            }
        ),
        encoding="utf-8",
    )
    (leg_dir / "journal.jsonl").write_text(
        json.dumps(
            {
                "game_id": "s-leg-3",
                "game_key": k3,
                "status": "finished",
                "semantic_transcript_sha256": h3,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Violated series -> must be ignored fail-closed
    _write_finished_game_log(
        tmp_path, "s-viol-4", seed=13, seat=3, base_deck_id="old--base", transcript_sha=h4
    )
    viol_dir = series_record.series_folder(tmp_path, "ser-viol")
    viol_dir.mkdir(parents=True, exist_ok=True)
    (viol_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": series_record.MANIFEST_SCHEMA,
                "series_id": "ser-viol",
                "game_key_schema": series_record.GAME_KEY_SCHEMA,
                "games": [
                    {"task_id": "a", "game_id": "s-viol-4", "game_key": k4},
                    {"task_id": "b", "game_id": "s-viol-4b", "game_key": k4},
                ],
            }
        ),
        encoding="utf-8",
    )
    (viol_dir / "journal.jsonl").write_text(
        json.dumps(
            {
                "game_id": "s-viol-4",
                "game_key": k4,
                "status": "finished",
                "semantic_transcript_sha256": h4,
            }
        )
        + "\n"
        + json.dumps(
            {
                "game_id": "s-viol-4b",
                "game_key": k4,
                "status": "finished",
                "semantic_transcript_sha256": "9" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    found = series_record.find_reusable_baseline_games(
        tmp_path,
        wanted_keys={(10, 0): k1, (11, 1): k2, (12, 2): k3, (13, 3): k4},
        exclude_series_id="ser-new",
        base_deck_id="new--base",
    )
    assert list(found.keys()) == [(10, 0)]
    item = found[(10, 0)]
    assert item.source_series_id == "ser-clean"
    assert item.source_game_id == "s1-base-1"
    assert item.semantic_transcript_sha256 == h1
    # Rebound deck_id on seat 0 so paired_comparison attributes win credit to the new base arm
    seat0 = next(s for s in item.exposure["seats"] if s["seat"] == 0)  # type: ignore[union-attr]
    assert seat0["deck_id"] == "new--base"

    # Cross-series determinism violation: a second clean series with same k1 but different hash!
    _write_finished_game_log(
        tmp_path, "s2-base-1", seed=10, seat=0, base_deck_id="old--base", transcript_sha="e" * 64
    )
    rec2 = series_record.SeriesRecord.open(
        tmp_path,
        "ser-conflict",
        games=[{"task_id": "base:10:0", "game_id": "s2-base-1", "game_key": k1}],
        table_hash=None,
        table=None,
    )
    rec2.record("s2-base-1", {"status": "finished", "semantic_transcript_sha256": "e" * 64})
    with pytest.raises(series_record.DeterminismViolation):
        series_record.find_reusable_baseline_games(
            tmp_path,
            wanted_keys={(10, 0): k1},
            exclude_series_id="ser-new",
            base_deck_id="new--base",
        )


def test_parallel_window_player_reuses_baseline_games_and_spot_checks_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1589: Series 2 reuses 3/4 base games, replays 1/4 as spot-check, fails closed on mismatch."""
    from commander_lab.studio import launch, paired_comparison, play_batch

    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"reuse-jar-1589")
    cmd = ("java", "-jar", str(jar), "full-game")
    _own_configuration(monkeypatch)
    monkeypatch.setattr(paired_comparison, "canonical_xmage_engine_pin", lambda: PIN)
    monkeypatch.setattr(
        launch, "bridge_jar_sha256", lambda _f, _c: hashlib.sha256(b"reuse-jar-1589").hexdigest()
    )

    loaded_all = play_batch.load_decks([DECK, *PRECONS])
    base_deck = loaded_all[0]
    opp_decks = loaded_all[1:]
    raw_deck = json.loads(DECK.read_text(encoding="utf-8"))
    var1_path = tmp_path / "var1.json"
    var2_path = tmp_path / "var2.json"
    var1_path.write_text(json.dumps({**raw_deck, "deck_id": "v1"}), encoding="utf-8")
    var2_path.write_text(json.dumps({**raw_deck, "deck_id": "v2"}), encoding="utf-8")
    var1_deck, var2_deck = play_batch.load_decks([var1_path, var2_path])
    paths = {
        base_deck.deck_id: DECK,
        var1_deck.deck_id: var1_path,
        var2_deck.deck_id: var2_path,
        **{d.deck_id: p for d, p in zip(opp_decks, PRECONS, strict=True)},
    }

    played_ids: list[str] = []
    tamper_hash = {"on": False}

    def fake_play_recorded_games(
        data_folder: Path,
        deck_paths: list[Path],
        games: Sequence[play_batch.SeriesGame],
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for g in games:
            played_ids.append(g.game_id)
            seat = int(g.game_id.rsplit("-t", 1)[1])
            is_base = "-base-" in g.game_id
            sha = hashlib.sha256(
                f"{g.seed}:{seat}:{'base' if is_base else 'var'}".encode()
            ).hexdigest()
            if tamper_hash["on"] and is_base:
                sha = "f" * 64
            deck_id = (
                base_deck.deck_id
                if is_base
                else (var1_deck.deck_id if "ser-1-" in g.game_id else var2_deck.deck_id)
            )
            _write_finished_game_log(
                Path(data_folder),
                g.game_id,
                seed=g.seed,
                seat=seat,
                base_deck_id=deck_id,
                transcript_sha=sha,
            )
            out.append(
                {
                    "game_id": g.game_id,
                    "status": "finished",
                    "winner_seats": [seat],
                    "decision_count": 42,
                    "semantic_transcript_sha256": sha,
                    "log": str(Path(data_folder) / "games" / f"{g.game_id}.jsonl.gz"),
                }
            )
        return out

    monkeypatch.setattr(play_batch, "play_recorded_games", fake_play_recorded_games)

    # Series 1: plays all 4 base + 4 variant games (0 reused)
    p1 = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="ser-1",
        base_deck=base_deck,
        variant_deck=var1_deck,
        opponents=opp_decks,
        paths_by_deck_id=paths,
        seeds=[100, 101],
        tested_seats=[0, 1],
        budget_pairs=4,
        look_every_pairs=4,
        workers=1,
        games_per_jvm=2,
        command=cmd,
        series_pool=False,
        reuse_baseline=True,
    )
    for seed in (100, 101):
        for seat in (0, 1):
            assert p1("base", seed, seat).get("source") == "played"
            assert p1("variant", seed, seat).get("source") == "played"
    s1_reuse = p1.baseline_reuse_summary()
    assert s1_reuse is not None
    assert (
        s1_reuse["reused_count"],
        s1_reuse["played_count"],
        s1_reuse["spot_checks_verified"],
    ) == (0, 4, 0)

    # Series 2: reuses 3/4 base games and replays 1/4 as mandatory spot-check!
    played_ids.clear()
    p2 = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="ser-2",
        base_deck=base_deck,
        variant_deck=var2_deck,
        opponents=opp_decks,
        paths_by_deck_id=paths,
        seeds=[100, 101],
        tested_seats=[0, 1],
        budget_pairs=4,
        look_every_pairs=4,
        workers=1,
        games_per_jvm=2,
        command=cmd,
        series_pool=False,
        reuse_baseline=True,
    )
    sources = [p2("base", seed, seat).get("source") for seed in (100, 101) for seat in (0, 1)]
    assert sources.count("reused") == 3 and sources.count("played") == 1
    assert p2("base", 100, 0).get("spot_check_verified") is True
    assert p2("base", 100, 1).get("reused_from_series_id") == "ser-1"
    # Only 1 base game (spot-check) + 4 variant games were played by the engine!
    assert sum("-base-" in gid for gid in played_ids) == 1
    s2_reuse = p2.baseline_reuse_summary()
    assert s2_reuse is not None
    assert (
        s2_reuse["reused_count"],
        s2_reuse["played_count"],
        s2_reuse["total_base_games"],
        s2_reuse["spot_checks_verified"],
        s2_reuse["spot_checks_failed"],
        s2_reuse["source_series_ids"],
    ) == (3, 1, 4, 1, 0, ["ser-1"])

    # Corrupt/truncated gzip log must be skipped fail-closed (no zlib/EOF crash)
    corrupt_gz = tmp_path / "games" / "s-corrupt-gz.jsonl.gz"
    corrupt_gz.write_bytes(b"\x1f\x8b\x08\x00corrupt")
    assert series_record._closing_transcript_hash(corrupt_gz) is None

    # Multi-window early stop + workers=2 + Resume with preloaded games:
    # Window 1 = (100, 0), (100, 1); Window 2 = (101, 0), (101, 1).
    # Stopping after Window 1 must report ONLY Window 1 counts (1 reused, 1 spot-check verified)!
    played_ids.clear()
    p_win = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="ser-early",
        base_deck=base_deck,
        variant_deck=var2_deck,
        opponents=opp_decks,
        paths_by_deck_id=paths,
        seeds=[100, 101],
        tested_seats=[0, 1],
        budget_pairs=4,
        look_every_pairs=2,
        workers=2,
        games_per_jvm=1,
        command=cmd,
        series_pool=False,
        reuse_baseline=True,
    )
    w1_b0 = p_win("base", 100, 0)
    w1_b1 = p_win("base", 100, 1)
    assert w1_b0.get("source") == "played" and w1_b0.get("spot_check_verified") is True
    assert w1_b1.get("source") == "reused"
    early_summary = p_win.baseline_reuse_summary()
    assert early_summary is not None
    assert (
        early_summary["reused_count"],
        early_summary["played_count"],
        early_summary["total_base_games"],
        early_summary["spot_checks_planned"],
        early_summary["spot_checks_verified"],
    ) == (1, 1, 2, 1, 1)

    # Resume with preloaded Window 1 games preserves exact n/N and spot_checks_verified!
    p_resumed = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="ser-early",
        base_deck=base_deck,
        variant_deck=var2_deck,
        opponents=opp_decks,
        paths_by_deck_id=paths,
        seeds=[100, 101],
        tested_seats=[0, 1],
        budget_pairs=4,
        look_every_pairs=2,
        workers=2,
        games_per_jvm=1,
        command=cmd,
        preloaded={("base", 100, 0): w1_b0, ("base", 100, 1): w1_b1},
        series_pool=False,
        reuse_baseline=True,
    )
    resumed_summary = p_resumed.baseline_reuse_summary()
    assert resumed_summary is not None
    assert (
        resumed_summary["reused_count"],
        resumed_summary["played_count"],
        resumed_summary["total_base_games"],
        resumed_summary["spot_checks_verified"],
    ) == (1, 1, 2, 1)

    # Series 3 (mutation): spot-check returns tampered hash -> DeterminismViolation fail-closed
    # AND the violating game is recorded in ser-3/journal.jsonl!
    tamper_hash["on"] = True
    p3 = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="ser-3",
        base_deck=base_deck,
        variant_deck=var2_deck,
        opponents=opp_decks,
        paths_by_deck_id=paths,
        seeds=[100, 101],
        tested_seats=[0, 1],
        budget_pairs=4,
        look_every_pairs=4,
        workers=1,
        games_per_jvm=2,
        command=cmd,
        series_pool=False,
        reuse_baseline=True,
    )
    with pytest.raises(series_record.DeterminismViolation):
        p3("base", 100, 0)
    journal_3 = (series_record.series_folder(tmp_path, "ser-3") / "journal.jsonl").read_text(
        encoding="utf-8"
    )
    assert "ser-3-base-s100-t0" in journal_3
