"""Bench real 4P XMage full games: wall time, child CPU time, semantic transcript hash.

usage: bench4p.py JAR OUT.json SEED [SEED...]   (extra JVM flags via BENCH_JVM_FLAGS)
"""

from __future__ import annotations

import json
import os
import resource
import shlex
import sys
import time
from pathlib import Path

ROOT = Path("/home/user/commander-playtest-lab")
sys.path.insert(0, str(ROOT / "scripts"))
os.chdir(ROOT)

import run_real_4p_full_game_smoke as smoke  # noqa: E402
from run_real_4p_full_game_smoke import build_real_4p_setup  # noqa: E402

if os.environ.get("BENCH_DECKS"):
    smoke.REAL_DECK_PATHS = tuple(Path(p) for p in os.environ["BENCH_DECKS"].split(","))

import subprocess  # noqa: E402

from commander_lab.engine.rules.full_game import XmageFullGameRunner  # noqa: E402

if os.environ.get("TRAIN_WAIT"):
    _orig_wait = subprocess.Popen.wait

    def _wait(self, timeout=None):
        return _orig_wait(self, timeout=None if timeout is None else max(timeout, 300))

    subprocess.Popen.wait = _wait


def main() -> None:
    jar, out, *seeds = sys.argv[1:]
    flags = shlex.split(os.environ.get("BENCH_JVM_FLAGS", ""))
    command = ("java", *flags, "-jar", jar, "full-game")
    scenario, decks, pilots, _ = build_real_4p_setup(ROOT)
    rows = []
    for seed in seeds:
        sc = scenario.model_copy(update={"seed": int(seed)})
        runner = XmageFullGameRunner(
            command,
            max_decisions=50_000,
            private_card_repository=bool(os.environ.get("BENCH_PRIVATE")),
        )
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        t0 = time.monotonic()
        try:
            r = runner.run(scenario=sc, decks=decks, pilots=pilots)
            if os.environ.get("BENCH_DUMP"):
                Path(os.environ["BENCH_DUMP"] + f"_{seed}.json").write_text(
                    json.dumps(
                        XmageFullGameRunner.semantic_transcript(r.result_payload),
                        indent=0,
                        default=str,
                    )
                )
            row = {
                "pod": os.environ.get("BENCH_POD", ""),
                "seed": int(seed),
                "status": "ok",
                "semantic": r.semantic_transcript_sha256,
                "decisions": r.decision_count,
                "winners": list(r.winner_seats),
            }
        except Exception as exc:
            diag = getattr(exc, "diagnostics", None) or getattr(
                getattr(exc, "__cause__", None), "diagnostics", None
            )
            if diag and os.environ.get("BENCH_DIAG"):
                Path(os.environ["BENCH_DIAG"] + f"_{seed}.txt").write_text(
                    "\n".join(map(str, diag))
                )
            row = {
                "pod": os.environ.get("BENCH_POD", ""),
                "seed": int(seed),
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}"[:400],
            }
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        row["wall_s"] = round(time.monotonic() - t0, 2)
        row["child_cpu_s"] = round(
            (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime), 2
        )
        print(json.dumps(row), flush=True)
        rows.append(row)
    Path(out).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
