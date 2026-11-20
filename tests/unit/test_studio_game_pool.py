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

JAR = "j" * 64
PIN = "p" * 40
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
    with pytest.raises(ValueError, match="JAR"):
        series_record.game_key(**{**_KEY_INPUT, "jar_sha256": ""})  # type: ignore[arg-type]
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
    assert set(_record(tmp_path, [task, unkeyed]).results()) == {task.game_id, unkeyed.game_id}


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


def test_the_wall_limit_is_set_per_seat_count_without_changing_the_table_hash() -> None:
    assert [table_spec.game_wall_limit_seconds(n) for n in (2, 3, 4)] == [1800.0] * 3
    for seats in (5, 6):
        with pytest.raises(ValueError, match="S2/F6"):
            table_spec.game_wall_limit_seconds(seats)
    spec = table_spec.TableSpec(seats=3, opponents=["a", "b"])
    assert spec.game_wall_limit_seconds() == 1800.0
    assert "game_wall_limit_seconds" not in spec.canonical()
