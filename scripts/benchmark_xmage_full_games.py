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
import hashlib
import json
import re
import resource
import subprocess
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

REFERENCE_DOC = ROOT / "docs/performance/REFERENCE_36_SEEDS_2026-10-31.md"
# Paths whose changes affect pilot decisions or engine behavior and thus invalidate the reference.
REFERENCE_WATCHED_PATHS: tuple[str, ...] = (
    "src/commander_lab/engine/rules/full_game_pilot",
    # The sibling modules ``full_game_pilot_*.py`` are pilot code too; the directory above does
    # not contain them (a pathspec matches whole path components), so they are listed by glob.
    "src/commander_lab/engine/rules/full_game_pilot_*.py",
    "src/commander_lab/agents",
    "engine-bridge/src/main",
    "config/rules_engines.json",
    # Inputs that decide the 36-seed hashes without being pilot code (#1076): the card knowledge
    # the pilot reads, the engine pom, the module that forms the hash, the script that builds
    # pod and pilot configuration, and the four pod decks (listed once, in that script).
    "data/cards/pilot_card_knowledge.json",
    "engine-bridge/pom.xml",
    "src/commander_lab/engine/rules/full_game.py",
    "scripts/run_real_4p_full_game_smoke.py",
    *(str(path) for path in smoke.REAL_DECK_PATHS),
)


def master_seeds(master: str, count: int) -> list[int]:
    """``count`` distinct game seeds derived from ``master`` (SHA-256), in [1, 2**31).

    Seeds 1..N are not a sample anyone chose without looking: a run that is announced with a
    master seed cannot be steered towards seeds on which a change looks good, and rerunning
    the announcement gives the same seeds.
    """
    if count < 1:
        raise ValueError("a seed set needs at least one seed")
    seeds: list[int] = []
    index = 0
    while len(seeds) < count:
        digest = hashlib.sha256(f"{master}:{index}".encode()).digest()
        seed = int.from_bytes(digest[:4], "big") % (2**31 - 1) + 1
        if seed not in seeds:
            seeds.append(seed)
        index += 1
    return seeds


def _seeds(text: str) -> list[int]:
    if text.startswith("hash:"):
        master, _, count = text[len("hash:") :].rpartition(":")
        if not master or not count.isdigit():
            raise ValueError("seed set must look like hash:MASTER:COUNT")
        return master_seeds(master, int(count))
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
    _print_time_comparison(base, other, wall, cpu)
    return 1 if differ or missing else 0


def _print_time_comparison(
    base: dict[str, Any], other: dict[str, Any], wall: list[float], cpu: list[float]
) -> None:
    """Time lines of ``compare``: per-game sums only where they mean something (#1075).

    A game's ``child_cpu_s`` is the RUSAGE_CHILDREN difference of the whole process, so with
    ``--workers N > 1`` every game also counts the CPU of the games that overlap it, and the
    sum of the per-game ``wall_s`` is not elapsed time. Such files compare by ``total_wall_s``
    only; files recorded with different worker counts are not comparable at all.
    """
    workers = [int(doc.get("workers") or 1) for doc in (base, other)]
    batches = [doc.get("games_per_jvm") for doc in (base, other)]
    if workers[0] != workers[1] or batches[0] != batches[1]:
        print(
            f"NOTE workers {workers[0]} -> {workers[1]}, games_per_jvm {batches[0]} -> "
            f"{batches[1]}: the time lines below do not compare like with like"
        )
    if max(workers) > 1:
        print("cpu  n/a (workers > 1: the per-game CPU of overlapping games overlaps)")
        totals = [doc.get("total_wall_s") for doc in (base, other)]
        if all(isinstance(total, (int, float)) and total for total in totals):
            print(
                f"elapsed {totals[0]:.1f} -> {totals[1]:.1f} s "
                f"({100 * (totals[1] / totals[0] - 1):+.1f} %)"
            )
        else:
            print("elapsed n/a (a file has no total_wall_s)")
        return
    if wall[0] and cpu[0]:
        print(f"wall {wall[0]:.1f} -> {wall[1]:.1f} s ({100 * (wall[1] / wall[0] - 1):+.1f} %)")
        print(f"cpu  {cpu[0]:.1f} -> {cpu[1]:.1f} s ({100 * (cpu[1] / cpu[0] - 1):+.1f} %)")


def parse_reference_metadata(doc_path: Path) -> dict[str, str]:
    if not doc_path.is_file():
        raise ValueError(f"Reference doc does not exist: {doc_path}")
    content = doc_path.read_text(encoding="utf-8")
    lab_commit: str | None = None
    xmage_pin: str | None = None
    for line in content.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            key_cell = parts[1]
            val_cell = parts[2]
            if key_cell == "Lab commit":
                m = re.search(r"`([^`]+)`", val_cell)
                if m:
                    lab_commit = m.group(1).strip()
            elif key_cell == "XMage pin":
                m = re.search(r"`([^`]+)`", val_cell)
                if m:
                    xmage_pin = m.group(1).strip()
    if not lab_commit or not xmage_pin:
        raise ValueError(
            f"Reference doc {doc_path} is missing required 'Lab commit' or 'XMage pin' metadata"
        )
    return {"lab_commit": lab_commit, "xmage_pin": xmage_pin}


def check_reference_staleness(
    doc_path: Path = REFERENCE_DOC,
    *,
    target_ref: str = "HEAD",
    repo_root: Path = ROOT,
) -> dict[str, object]:
    metadata = parse_reference_metadata(doc_path)
    reference_commit = metadata["lab_commit"]
    reference_pin = metadata["xmage_pin"]

    diff_cmd = [
        "git",
        "-C",
        str(repo_root),
        "diff",
        "--name-only",
        f"{reference_commit}..{target_ref}",
        "--",
        *REFERENCE_WATCHED_PATHS,
    ]
    proc_diff = subprocess.run(diff_cmd, check=False, capture_output=True, text=True)
    if proc_diff.returncode != 0:
        raise RuntimeError(
            f"git diff failed with exit code {proc_diff.returncode}: {proc_diff.stderr.strip()}"
        )
    changed_files = tuple(
        sorted(line.strip() for line in proc_diff.stdout.splitlines() if line.strip())
    )

    show_cmd = [
        "git",
        "-C",
        str(repo_root),
        "show",
        f"{target_ref}:config/rules_engines.json",
    ]
    proc_show = subprocess.run(show_cmd, check=False, capture_output=True, text=True)
    if proc_show.returncode != 0:
        raise RuntimeError(
            f"git show failed with exit code {proc_show.returncode}: {proc_show.stderr.strip()}"
        )
    raw_rules = json.loads(proc_show.stdout)
    full_pin = raw_rules.get("primary_engine", {}).get("commit", "")
    pin_matches = bool(isinstance(full_pin, str) and full_pin.startswith(reference_pin))

    stale = bool(changed_files or not pin_matches)
    if stale:
        reasons: list[str] = []
        if changed_files:
            reasons.append(
                f"{len(changed_files)} watched file(s) changed: {', '.join(changed_files)}"
            )
        if not pin_matches:
            reasons.append(
                f"XMage pin diverged (target: {full_pin[:10] if isinstance(full_pin, str) else full_pin}, expected prefix: {reference_pin})"
            )
        reason_text = "; ".join(reasons)
        message = (
            f"reference {doc_path.name} (lab {reference_commit}) is stale at "
            f"{target_ref}: {reason_text}; rerun the 36-seed reference before comparing"
        )
    else:
        message = f"reference {doc_path.name} (lab {reference_commit}) is current at {target_ref}"

    return {
        "reference_commit": reference_commit,
        "target_ref": target_ref,
        "reference_pin": reference_pin,
        "pin_matches": pin_matches,
        "changed_files": changed_files,
        "stale": stale,
        "message": message,
    }


def check_reference_cli(args: argparse.Namespace) -> int:
    result = check_reference_staleness(
        doc_path=args.doc,
        target_ref=args.target,
    )
    print(result["message"])
    return 1 if result["stale"] else 0


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
    check_ref = sub.add_parser("check-reference")
    check_ref.add_argument("--doc", type=Path, default=REFERENCE_DOC)
    check_ref.add_argument("--target", default="HEAD")
    check_ref.set_defaults(func=check_reference_cli)
    args = parser.parse_args(argv)
    if args.cmd == "run" and args.games_per_jvm < 1:
        parser.error("--games-per-jvm must be positive")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
