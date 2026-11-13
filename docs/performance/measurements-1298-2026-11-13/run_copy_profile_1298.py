"""Issue #1298 Stufe 1 driver: deep-stack JFR copy-attribution profile.

Reuses the production measurement driver of #1279/#1281
(scripts/measure_throughput_steady_state.py: same table, same decks, same
BatchRecordingRunner) and only changes the JFR hookup:
  jcmd <pid> JFR.configure stackdepth=512   (before start, as #1298 demands)
  jcmd <pid> JFR.start settings=profile    (profile.jfc already enables
                                            jdk.ObjectAllocationSample)
Modes:
  smoke: seeds [1], 1 game in 1 JVM, JFR from game 1, stop after game 1.
  full:  seeds 1..12, 12 games in 1 JVM, JFR from game 3 (games 1-2 warmup,
         as in #1281), stop after game 12.
No product code is changed by this script; it lives in the measurements dir.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import measure_throughput_steady_state as m  # noqa: E402

from commander_lab.engine.rules.full_game import (  # noqa: E402
    FullGameConformanceResult,
    _RawFullGameClient,
)
from commander_lab.studio.play import load_decks, prepare_game  # noqa: E402

REC_NAME = "copy1298"


class DeepJfrRunner(m.TimedBatchRunner):
    def __init__(self, *args: Any, jfr_start_game: int, jfr_stop_game: int, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.jfr_start_game = jfr_start_game
        self.jfr_stop_game = jfr_stop_game
        self.jcmd_log: list[str] = []

    def _jcmd(self, *cmd_args: str) -> None:
        cmd = ["jcmd", str(self.active_pid), *cmd_args]
        res = subprocess.run(cmd, check=False, capture_output=True, text=True)
        line = f"$ {' '.join(cmd)}\n{res.stdout.strip()}\n{res.stderr.strip()}"
        print(line, flush=True)
        self.jcmd_log.append(line)

    def _open_game(self, client: _RawFullGameClient, scenario: Any, dks: Any) -> Any:
        self.active_pid = client._process.pid if client._process else None
        self._current_game_in_jvm += 1
        self._current_seed = scenario.seed
        if self.jfr_path and self._current_game_in_jvm == self.jfr_start_game and self.active_pid:
            print(
                f"[{self.jvm_id}] JFR.configure stackdepth=512 + JFR.start "
                f"before game {self.jfr_start_game} (PID {self.active_pid})",
                flush=True,
            )
            self._jcmd("JFR.configure", "stackdepth=512")
            self._jcmd(
                "JFR.start",
                f"name={REC_NAME}",
                "settings=profile",
                f"filename={self.jfr_path.resolve()}",
            )
        self._game_t0 = time.perf_counter()
        self._game_cpu0 = m.read_proc_cpu(self.active_pid)
        return super(m.TimedBatchRunner, self)._open_game(client, scenario, dks)

    def _drive(self, client: _RawFullGameClient, policy: Any, **kwargs: Any) -> Any:
        drive_res = super(m.TimedBatchRunner, self)._drive(client, policy, **kwargs)
        t1 = time.perf_counter()
        cpu1 = m.read_proc_cpu(self.active_pid)
        wall_s = round(t1 - self._game_t0, 3)
        cpu_s = round(max(0.0, cpu1 - self._game_cpu0), 3)
        if self.active_pid:
            self.peak_rss_mb = max(self.peak_rss_mb, m.read_proc_vmhwm(self.active_pid))
        if self.jfr_path and self._current_game_in_jvm == self.jfr_stop_game and self.active_pid:
            print(
                f"[{self.jvm_id}] JFR.stop after game {self.jfr_stop_game} (PID {self.active_pid})",
                flush=True,
            )
            self._jcmd("JFR.stop", f"name={REC_NAME}")
            time.sleep(1.0)
        self.game_records.append(
            m.GameRecord(
                run_name=self.run_name,
                worker_id=self.worker_id,
                jvm_id=self.jvm_id,
                game_in_jvm=self._current_game_in_jvm,
                seed=self._current_seed,
                wall_s=wall_s,
                cpu_s=cpu_s,
                winner=None,
                decisions=0,
                semantic_hash="",
                status="pending",
            )
        )
        return drive_res


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["smoke", "full"], required=True)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--jfr-out", type=Path, required=True)
    parser.add_argument("--result-out", type=Path, required=True)
    args = parser.parse_args()

    jar = args.jar.resolve(strict=True)
    decks = load_decks(
        [m.DEFAULT_DECK.resolve(strict=True)]
        + [p.resolve(strict=True) for p in m.DEFAULT_OPPONENTS]
    )

    if args.mode == "smoke":
        seeds = [1]
        games_per_jvm = 1
        start_game, stop_game = 1, 1
    else:
        seeds = list(range(1, 13))
        games_per_jvm = 12
        start_game, stop_game = 3, 12

    jvm_opts = ["-XX:+UseSerialGC", "-Dh2.bindAddress=127.0.0.1", "-Xmx3g"]
    if games_per_jvm > 1:
        jvm_opts.append(f"-Dcommanderlab.fullGame.gamesPerJvm={games_per_jvm}")
    command = ("java", *jvm_opts, "-jar", str(jar), "full-game")
    print(f"JVM Command: {' '.join(command)}", flush=True)

    work_dir = args.work.resolve()
    data_dir = work_dir / "data"
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    args.jfr_out.parent.mkdir(parents=True, exist_ok=True)
    if args.jfr_out.exists():
        args.jfr_out.unlink()

    prepared = [prepare_game(decks, seed=s, game_id=f"copy1298-s{s}") for s in seeds]
    headers = {p.scenario.scenario_id: (p.game_id, p.header) for p in prepared}
    runner = DeepJfrRunner(
        data_dir,
        headers,
        command=command,
        run_name=f"copy1298_{args.mode}",
        jvm_id=f"copy1298-{args.mode}-jvm0",
        worker_id=0,
        jfr_profile=True,
        jfr_path=args.jfr_out,
        jfr_start_game=start_game,
        jfr_stop_game=stop_game,
    )

    t0 = time.perf_counter()
    try:
        outcomes = runner.run_batch([(p.scenario, p.decks, p.pilots) for p in prepared])
    except Exception as exc:
        print(f"run_batch failed: {type(exc).__name__}: {exc}", flush=True)
        outcomes = [exc] * len(prepared)
    total_wall = round(time.perf_counter() - t0, 3)

    games = []
    for rec, outcome in zip(runner.game_records, outcomes, strict=False):
        if isinstance(outcome, FullGameConformanceResult):
            rec.status = "finished"
            rec.winner = outcome.winner_seats[0] - 1 if outcome.winner_seats else None
            rec.decisions = outcome.decision_count
            rec.semantic_hash = outcome.semantic_transcript_sha256
        else:
            rec.status = "failed"
            rec.semantic_hash = f"ERROR: {type(outcome).__name__}: {outcome}"
        games.append(
            {
                "seed": rec.seed,
                "game_in_jvm": rec.game_in_jvm,
                "status": rec.status,
                "winner": rec.winner,
                "decisions": rec.decisions,
                "semantic_hash": rec.semantic_hash,
                "wall_s": rec.wall_s,
                "cpu_s": rec.cpu_s,
            }
        )

    result = {
        "mode": args.mode,
        "command": list(command),
        "total_wall_s": total_wall,
        "peak_rss_mb": round(runner.peak_rss_mb, 2),
        "jfr_file": str(args.jfr_out),
        "jfr_exists": args.jfr_out.is_file(),
        "jfr_size": args.jfr_out.stat().st_size if args.jfr_out.is_file() else 0,
        "jcmd_log": runner.jcmd_log,
        "games": games,
    }
    args.result_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    shutil.rmtree(data_dir, ignore_errors=True)
    ok = all(g["status"] == "finished" for g in games) and result["jfr_exists"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
