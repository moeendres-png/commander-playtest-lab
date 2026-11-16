"""Check that a game played inside a Studio series is THE SAME GAME as played alone.

Plays the same seeds of one deck against the ``precon`` pod of ``deckbau_eval.py`` twice on the
real rules engine:

  (a) one game per bridge JVM, default JVM options, one ``commander_lab.studio play`` process
      per game (how a Studio series played before), and
  (b) as a Studio series (``BatchSimulation``) with ``--workers`` workers, ``--games-per-jvm``
      games per JVM and the fast JVM options (serial GC, AppCDS archive if the jar has one).

Then it compares, per seed, the semantic transcript SHA-256 (the field
``benchmark_xmage_full_games.py`` records as ``semantic``: ``semantic_transcript_sha256`` of the
full-game result), the winner seats and the decision count, as every game log of the Studio
records them. Exit 0 only if every game is identical and every game of both runs finished.

    python scripts/check_studio_series_identity.py --jar bridge.jar --work /tmp/x/fast-check

Wall and CPU times are printed as a measurement only; the verdict rests on identity alone.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import deckbau_eval  # noqa: E402

from commander_lab.studio.games import read_game  # noqa: E402
from commander_lab.studio.launch import (  # noqa: E402
    ENGINE_COMMAND_ENV,
    command_text,
    series_engine,
)
from commander_lab.studio.simulations import BatchSimulation  # noqa: E402

DEFAULT_DECK = ROOT / "data/decks/deckbau/chulane_current.json"
DEFAULT_JAR = ROOT / "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
BASE_COMMAND = ("java", "-Xmx3g", "-jar", "{jar}", "full-game")


def _cpu_seconds() -> float:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def _fingerprint(data: Path, game_id: str) -> dict[str, Any]:
    """Hash, winners, decisions and status of a recorded game, as its log closes it."""
    result = read_game(data, game_id, start=0, count=0).get("result")
    result = result if isinstance(result, dict) else {}
    return {
        "game_id": game_id,
        "status": result.get("status", "missing"),
        "semantic": result.get("semantic_transcript_sha256"),
        "winners": result.get("winner_seats"),
        "decisions": result.get("decision_count"),
        "failure": result.get("failure_message"),
    }


def play_alone(
    data: Path, deck: Path, opponents: list[Path], seeds: list[int], env: dict[str, str]
) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for seed in seeds:
        game_id = f"identity-a-s{seed}"
        command = [
            sys.executable,
            "-m",
            "commander_lab.studio",
            "--data",
            str(data),
            "play",
            "--seed",
            str(seed),
            "--game-id",
            game_id,
            "--deck",
            str(deck),
        ]
        for opponent in opponents:
            command += ["--deck", str(opponent)]
        subprocess.run(command, env=env, check=False, stdout=subprocess.DEVNULL)
        rows[seed] = _fingerprint(data, game_id)
    return rows


def play_series(
    data: Path,
    deck: Path,
    opponents: list[Path],
    seeds: list[int],
    workers: int,
    games_per_jvm: int,
) -> tuple[dict[int, dict[str, Any]], BatchSimulation]:
    engine = series_engine(data, games_per_jvm)
    if engine is None:
        raise SystemExit("no engine command: set " + ENGINE_COMMAND_ENV)
    batch = BatchSimulation(
        "identity-b",
        data,
        deck_id="chulane",
        revision_id="check",
        pod_name="precon",
        opponent_paths=opponents,
        seeds=seeds,
        workers=workers,
        games_per_jvm=games_per_jvm,
        engine=engine,
    )
    batch.run_worker(None, deck)
    return {seed: _fingerprint(data, batch.game_id_of(seed)) for seed in seeds}, batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK)
    parser.add_argument("--seeds", default="1-6")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--games-per-jvm", type=int, default=3)
    parser.add_argument("--work", type=Path, required=True, help="scratch folder (emptied)")
    parser.add_argument("--out", type=Path, default=None, help="write the comparison as JSON")
    args = parser.parse_args(argv)

    seeds = deckbau_eval.seed_list(args.seeds)
    jar = args.jar.resolve(strict=True)
    deck = args.deck.resolve(strict=True)
    opponents = [(ROOT / path).resolve(strict=True) for path in deckbau_eval.PODS["precon"]]

    work = args.work.resolve()
    shutil.rmtree(work, ignore_errors=True)
    for name in ("a", "b", "cwd", "owner"):
        (work / name).mkdir(parents=True)
    # the bridge keeps its card database under ./db of the working directory
    os.chdir(work / "cwd")
    env = dict(os.environ)
    env["COMMANDER_LAB_OWNER_DATA"] = str(work / "owner")
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH", "")])
    )
    base = tuple(jar.as_posix() if part == "{jar}" else part for part in BASE_COMMAND)
    env[ENGINE_COMMAND_ENV] = command_text(base)
    os.environ.update(env)

    cpu0, wall0 = _cpu_seconds(), time.monotonic()
    alone = play_alone(work / "a", deck, opponents, seeds, env)
    cpu1, wall1 = _cpu_seconds(), time.monotonic()
    series, batch = play_series(
        work / "b", deck, opponents, seeds, args.workers, args.games_per_jvm
    )
    cpu2, wall2 = _cpu_seconds(), time.monotonic()

    print(f"{'seed':>4}  {'hash':<5} {'winner':<6} {'decisions':<9}  semantic transcript (a | b)")
    ok = True
    table: list[dict[str, Any]] = []
    for seed in seeds:
        a, b = alone[seed], series[seed]
        played = a["status"] == "finished" and b["status"] == "finished"
        same_hash = played and a["semantic"] is not None and a["semantic"] == b["semantic"]
        same_winner = played and a["winners"] == b["winners"]
        same_decisions = played and a["decisions"] == b["decisions"]
        ok = ok and same_hash and same_winner and same_decisions
        table.append(
            {
                "seed": seed,
                "hash_equal": same_hash,
                "winner_equal": same_winner,
                "decisions_equal": same_decisions,
                "a": a,
                "b": b,
            }
        )
        flag = lambda value: "yes" if value else "NO"  # noqa: E731
        print(
            f"{seed:>4}  {flag(same_hash):<5} {flag(same_winner):<6} {flag(same_decisions):<9}  "
            f"{str(a['semantic'])[:16]} | {str(b['semantic'])[:16]}"
            + ("" if played else f"  (a: {a['status']}, b: {b['status']})")
        )
    identical = sum(1 for row in table if row["hash_equal"])
    print(f"identical {identical}/{len(seeds)}")
    execution = batch.execution()
    print("series execution:", json.dumps({k: v for k, v in execution.items() if k != "chunks"}))
    print(f"(a) one game per JVM: wall {wall1 - wall0:.1f} s, cpu {cpu1 - cpu0:.1f} s")
    print(
        f"(b) series workers={args.workers} games_per_jvm={args.games_per_jvm}: "
        f"wall {wall2 - wall1:.1f} s, cpu {cpu2 - cpu1:.1f} s (a measurement, not evidence)"
    )
    print("IDENTITY", "PASS" if ok else "FAIL")
    if args.out is not None:
        report = {
            "seeds": seeds,
            "table": table,
            "execution": execution,
            "wall_s": {"a": round(wall1 - wall0, 1), "b": round(wall2 - wall1, 1)},
            "cpu_s": {"a": round(cpu1 - cpu0, 1), "b": round(cpu2 - cpu1, 1)},
            "identical": identical,
        }
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
