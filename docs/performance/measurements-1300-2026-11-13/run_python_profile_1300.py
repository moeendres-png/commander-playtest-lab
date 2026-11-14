"""Issue #1300 (E5) step 1 driver: Python-side profile of a Studio series.

Reuses the production measurement driver of #1279/#1281
(scripts/measure_throughput_steady_state.py: same table, same decks, same
BatchRecordingRunner -> studio GameRecorder path) and only drives a fixed
seed set in one JVM, recording wall / process-CPU / children-CPU around it.
Run it under ``python -m cProfile -o <file>`` for the profiled measurement,
or plain for the unprofiled companion run.

Modes:
  smoke: seeds [1], 1 game in 1 JVM.
  full:  seeds 1..8, 8 games in 1 JVM (--workers 1 --games-per-jvm 8 --fast).

No product code is changed by this script; it lives in the measurements dir.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import measure_throughput_steady_state as m  # noqa: E402

from commander_lab.studio.play import load_decks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["smoke", "full"], required=True)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
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
    else:
        seeds = list(range(1, 9))
        games_per_jvm = 8

    jvm_opts = ["-XX:+UseSerialGC", "-Dh2.bindAddress=127.0.0.1", "-Xmx3g"]
    if games_per_jvm > 1:
        jvm_opts.append(f"-Dcommanderlab.fullGame.gamesPerJvm={games_per_jvm}")
    command = ("java", *jvm_opts, "-jar", str(jar), "full-game")
    print(f"JVM Command: {' '.join(command)}", flush=True)

    work_dir = args.work.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    wall0 = time.perf_counter()
    cpu0 = time.process_time()
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    game_records, jvm_record = m.run_chunk(
        0,
        seeds,
        f"py1300_{args.mode}",
        0,
        command,
        work_dir,
        decks,
    )
    wall_s = round(time.perf_counter() - wall0, 3)
    py_cpu_s = round(time.process_time() - cpu0, 3)
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    children_cpu_s = round((ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime), 3)

    games = [
        {
            "seed": rec.seed,
            "game_in_jvm": rec.game_in_jvm,
            "status": rec.status,
            "winner": rec.winner,
            "decisions": rec.decisions,
            "semantic_hash": rec.semantic_hash,
            "wall_s": rec.wall_s,
            "jvm_cpu_s": rec.cpu_s,
        }
        for rec in game_records
    ]
    result = {
        "mode": args.mode,
        "command": list(command),
        "total_wall_s": wall_s,
        "python_process_cpu_s": py_cpu_s,
        "children_cpu_s": children_cpu_s,
        "peak_rss_mb": jvm_record.peak_rss_mb,
        "games": games,
    }
    args.result_out.parent.mkdir(parents=True, exist_ok=True)
    args.result_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if all(g["status"] == "finished" for g in games) else 1


if __name__ == "__main__":
    raise SystemExit(main())
