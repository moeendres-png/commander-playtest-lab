"""Benchmark real XMage full games and check that a change keeps every game identical.

Plays real 4-player pods with one bridge jar and records, per game, the semantic
transcript SHA-256, decision count, winners, wall time and the CPU time of the bridge
JVM (children of this process). Comparing two result files is the bar every speed
change in docs/performance/XMAGE_FULL_GAME_SPEED_2026-10-12.md had to pass: every
semantic transcript identical, then the timing difference.

    # 4 real pods (the real-4P smoke decks), seeds 1-4
    python scripts/benchmark_xmage_full_games.py run --jar A.jar --out a.json --seeds 1-4
    # 5 pods from the 18 owner-collection coverage decks, seeds 1-2
    python scripts/benchmark_xmage_full_games.py run --jar A.jar --out a.json \\
        --coverage-pods --seeds 1-2
    python scripts/benchmark_xmage_full_games.py compare a.json b.json

Extra JVM options go before -jar (``--jvm-option=-XX:SharedArchiveFile=x.jsa``).
``--workers N`` plays N games at once; then use ``--private-card-repository``, or
parallel JVMs collide on the shared card database at start-up (#739).
``--fast`` adds the launch options of ``fast_jvm_options`` (serial GC, AppCDS archive next to the jar).
``--games-per-jvm N`` (batch measurement runs only, Owner decision 2026-10-15) plays up to N
consecutive games in one bridge process; a failed game ends that process and the rest of
the chunk continues in a fresh one. Wall and CPU of a batched game are the chunk average.
Local timings are measurements, not qualification evidence.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
GAMES_PER_JVM_PROPERTY = "commanderlab.fullGame.gamesPerJvm"

import run_real_4p_full_game_smoke as smoke  # noqa: E402

from commander_lab.engine.rules.full_game import XmageFullGameRunner  # noqa: E402

COVERAGE_DIR = ROOT / "data/coverage_decks/collection"
# Five disjoint-as-possible pods over the 18 coverage decks (sorted file order).
COVERAGE_PODS = ((0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14, 15), (16, 17, 0, 5))


def _seeds(text: str) -> list[int]:
    seeds: list[int] = []
    for part in text.split(","):
        low, _, high = part.partition("-")
        seeds.extend(range(int(low), int(high or low) + 1))
    return seeds


def _pods(coverage: bool) -> list[tuple[str, tuple[Path, ...]]]:
    if not coverage:
        return [("real", tuple(smoke.REAL_DECK_PATHS))]
    decks = sorted(COVERAGE_DIR.glob("*.json"))
    return [
        (f"coverage-{i}", tuple(decks[k].relative_to(ROOT) for k in pod))
        for i, pod in enumerate(COVERAGE_PODS)
    ]


def _setup(paths: tuple[Path, ...]) -> tuple[Any, Any, Any]:
    """Scenario, decks and pilots for one pod (the smoke reads its deck list from module state)."""
    smoke.REAL_DECK_PATHS = paths
    scenario, decks, pilots, _ = smoke.build_real_4p_setup(ROOT)
    return scenario, decks, pilots


def _play(
    command: tuple[str, ...], pod: str, setup: tuple[Any, Any, Any], seed: int, private: bool
) -> dict[str, Any]:
    scenario, decks, pilots = setup
    scenario = scenario.model_copy(update={"seed": seed})
    runner = XmageFullGameRunner(command, private_card_repository=private)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    row: dict[str, Any] = {"pod": pod, "seed": seed}
    try:
        result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
        row |= {
            "status": "ok",
            "semantic": result.semantic_transcript_sha256,
            "decisions": result.decision_count,
            "winners": list(result.winner_seats),
        }
    except Exception as exc:  # a failed game is a result row, not a crash
        row |= {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:400]}
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    row["wall_s"] = round(time.monotonic() - started, 2)
    # Children's CPU is process-wide: exact with one worker, shared across games otherwise.
    row["child_cpu_s"] = round(
        (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime), 2
    )
    print(json.dumps(row), flush=True)
    return row


def _row_of(outcome: Any) -> dict[str, Any]:
    if isinstance(outcome, Exception):  # a failed game is a result row, not a crash
        return {"status": "failed", "error": f"{type(outcome).__name__}: {outcome}"[:400]}
    return {
        "status": "ok",
        "semantic": outcome.semantic_transcript_sha256,
        "decisions": outcome.decision_count,
        "winners": list(outcome.winner_seats),
    }


def _play_batch(
    command: tuple[str, ...],
    jobs: list[tuple[str, tuple[Any, Any, Any], int]],
    private: bool,
) -> list[dict[str, Any]]:
    """Play ``jobs`` one after the other in one bridge process (wall and CPU: chunk average)."""
    runner = XmageFullGameRunner(command, private_card_repository=private)
    games = [
        (setup[0].model_copy(update={"seed": seed}), setup[1], setup[2]) for _, setup, seed in jobs
    ]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    try:
        outcomes: list[Any] = runner.run_batch(games)
    except Exception as exc:
        outcomes = [exc] * len(jobs)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall = round((time.monotonic() - started) / len(jobs), 2)
    cpu = round(
        ((after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)) / len(jobs), 2
    )
    rows = []
    for (pod, _, seed), outcome in zip(jobs, outcomes, strict=True):
        row = {"pod": pod, "seed": seed} | _row_of(outcome)
        row |= {"wall_s": wall, "child_cpu_s": cpu, "batched": len(jobs)}
        print(json.dumps(row), flush=True)
        rows.append(row)
    return rows


def fast_jvm_options(jar: Path) -> list[str]:
    """Launch options that make a bridge JVM cheaper without changing a game.

    Serial GC: the live set is small and the games allocate about 1 GB/s, so one collector
    thread beats G1's concurrent threads (measured -10 % CPU, identical transcripts). With an
    AppCDS archive next to the jar (``<jar>.jsa`` from ``build_xmage_cds_archive.py``) the JVM
    also maps its classes instead of loading them; JVM logging then goes to stderr, because the
    JVM's own warning (a stale archive) would otherwise reach the protocol on stdout.
    """
    options = ["-XX:+UseSerialGC"]
    archive = jar.resolve().with_suffix(".jsa")
    if archive.is_file():
        options += ["-Xlog:disable", "-Xlog:all=warning:stderr", f"-XX:SharedArchiveFile={archive}"]
    return options


def bridge_command(jar: Path, jvm_options: list[str]) -> tuple[str, ...]:
    """The bridge launch command, with the jar as an absolute path.

    ``--private-card-repository`` starts each bridge JVM in its own scratch
    directory, so a relative jar path would no longer resolve and every game would
    end at once with BRIDGE_EXITED.
    """
    return ("java", *jvm_options, "-jar", str(jar.resolve()), "full-game")


def run(args: argparse.Namespace) -> int:
    jvm_options = list(args.jvm_option)
    if args.fast:
        jvm_options = fast_jvm_options(args.jar) + jvm_options
    if args.games_per_jvm > 1:
        jvm_options.append(f"-D{GAMES_PER_JVM_PROPERTY}={args.games_per_jvm}")
    command = bridge_command(args.jar, jvm_options)
    setups = {pod: _setup(paths) for pod, paths in _pods(args.coverage_pods)}
    jobs = [(pod, setup, seed) for pod, setup in setups.items() for seed in args.seeds]
    started = time.monotonic()

    def play(job: tuple[str, tuple[Any, Any, Any], int]) -> dict[str, Any]:
        pod, setup, seed = job
        return _play(command, pod, setup, seed, args.private_card_repository)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        if args.games_per_jvm == 1:
            rows = list(pool.map(play, jobs))
        else:
            size = args.games_per_jvm
            chunks = [jobs[start : start + size] for start in range(0, len(jobs), size)]
            rows = [
                row
                for chunk in pool.map(
                    lambda chunk: _play_batch(command, chunk, args.private_card_repository), chunks
                )
                for row in chunk
            ]
    report = {
        "jar": str(args.jar),
        "jvm_options": jvm_options,
        "games_per_jvm": args.games_per_jvm,
        "workers": args.workers,
        "total_wall_s": round(time.monotonic() - started, 2),
        "games": rows,
    }
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return 0 if all(row["status"] == "ok" for row in rows) else 1


def _games_by_key(report: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    """Games of a benchmark file (``games``) or a pod sweep (``rows``, one game seed)."""
    rows = report["games"] if "games" in report else report["rows"]
    return {(r["pod"], r.get("seed", report.get("game_seed"))): r for r in rows}


def compare(args: argparse.Namespace) -> int:
    base, other = (json.loads(path.read_text(encoding="utf-8")) for path in (args.a, args.b))
    a = _games_by_key(base)
    b = _games_by_key(other)
    keys = sorted(a.keys() & b.keys())
    # A failed game is never identical, not even to another failed game.
    differ = [
        k
        for k in keys
        if a[k]["status"] != "ok"
        or b[k]["status"] != "ok"
        or a[k].get("semantic") != b[k].get("semantic")
    ]
    missing = len(a.keys() ^ b.keys())
    wall = [sum(d[k]["wall_s"] for k in keys) for d in (a, b)]
    cpu = [sum(d[k]["child_cpu_s"] for k in keys) for d in (a, b)]
    print(f"identical {len(keys) - len(differ)}/{len(keys)}")
    for key in differ:
        print("DIFFERENT", key, *(d[key].get("semantic") or d[key]["status"] for d in (a, b)))
    if missing:
        print(f"MISSING {missing} game(s) present in only one file")
    if wall[0] and cpu[0]:
        print(f"wall {wall[0]:.1f} -> {wall[1]:.1f} s ({100 * (wall[1] / wall[0] - 1):+.1f} %)")
        print(f"cpu  {cpu[0]:.1f} -> {cpu[1]:.1f} s ({100 * (cpu[1] / cpu[0] - 1):+.1f} %)")
    return 1 if differ or missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    play = sub.add_parser("run")
    play.add_argument("--jar", type=Path, required=True)
    play.add_argument("--out", type=Path, required=True)
    play.add_argument("--seeds", type=_seeds, default=_seeds("1-4"))
    play.add_argument("--coverage-pods", action="store_true")
    play.add_argument("--jvm-option", action="append", default=[])
    play.add_argument("--workers", type=int, default=1)
    play.add_argument("--games-per-jvm", type=int, default=1)
    play.add_argument(
        "--fast", action="store_true", help="serial GC and, if present, the jar's AppCDS archive"
    )
    play.add_argument("--private-card-repository", action="store_true")
    play.set_defaults(func=run)
    diff = sub.add_parser("compare")
    diff.add_argument("a", type=Path)
    diff.add_argument("b", type=Path)
    diff.set_defaults(func=compare)
    args = parser.parse_args(argv)
    if args.cmd == "run" and args.games_per_jvm < 1:
        parser.error("--games-per-jvm must be positive")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
