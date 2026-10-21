"""Play the precon decks in real 4-player pods and group the failures by cause.

Every pod seats four DIFFERENT decks: the full-game validator rejects one deck on several
seats before any JVM starts (``distinct deck identities per seat``), so a sweep that repeats a
deck measures that rejection and never plays a game. The plan covers every selected deck at
least once; when four does not divide the deck count the last pod is filled from the start of
the shuffled list. A pod always seats four decks: the full-game scenario is a four-player game.

    python scripts/precon_pod_sweep.py --jar bridge.jar --out sweep.json --workers 2
    # several pods per bridge JVM (measurement runs only, Owner decision 2026-10-15)
    python scripts/precon_pod_sweep.py --jar bridge.jar --out sweep.json --games-per-jvm 8 --fast
    # only decks that import cleanly (output of an import measurement: {"results": [...]})
    python scripts/precon_pod_sweep.py --jar bridge.jar --out sweep.json \\
        --import-report imports.json
    # any directory of deck files inside the repository, e.g. decks from import_deck.py
    python scripts/precon_pod_sweep.py --jar bridge.jar --out sweep.json \\
        --deck-dir data/decks/custom

A failed pod is a result row, not a crash. The game is played by ``benchmark_xmage_full_games``
(same pilots, private card repository, bridge command). Local runs are measurements, not
qualification evidence; only one sweep should run at a time, because CPU contention turns slow
decisions into ``DECISION_ADVANCE_TIMEOUT`` rows.

With ``--games-per-jvm N`` a worker plays up to N consecutive pods in one bridge JVM: the
start-up cost (JVM, card scan, JIT warm-up) is paid once per chunk instead of once per pod, and
every pod keeps the semantic transcript it has alone in a JVM (checked by comparing sweeps with
``benchmark_xmage_full_games.py compare``-style hash identity). A failed pod ends its JVM and the
rest of the chunk continues in a fresh one. Wall time and CPU of a batched pod are chunk averages.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PRECON_DIR = ROOT / "data/decks/precons"
POD_SIZE = 4
_FAMILY = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b")
_CODE_LIST = re.compile(r"\[([A-Z][A-Z0-9_]*(?:, [A-Z][A-Z0-9_]*)*)\]")
_GENERIC = "ENGINE_FAILURE"


def plan_pods(decks: Sequence[str], pod_size: int = 4, seed: int = 1) -> list[tuple[str, ...]]:
    """Deterministic pods of ``pod_size`` distinct decks that cover every deck."""
    if pod_size < 2:
        raise ValueError("a pod needs at least two decks")
    unique = sorted(set(decks))
    if len(unique) < pod_size:
        raise ValueError(f"{len(unique)} decks cannot fill a pod of {pod_size} distinct decks")
    order = unique[:]
    random.Random(seed).shuffle(order)
    # Fill the last pod from the front of the order; with n >= pod_size the front never
    # overlaps the decks already in the last pod.
    order += order[: (-len(order)) % pod_size]
    return [tuple(order[i : i + pod_size]) for i in range(0, len(order), pod_size)]


def chunk_indices(count: int, size: int, reverse: bool = False) -> list[list[int]]:
    """Consecutive pod indices, ``size`` per bridge JVM (one chunk is one JVM's batch).

    ``reverse`` plays the pods last to first, so a batch run meets other neighbours than
    the forward run did: state a game leaves behind would show up as a different transcript.
    """
    if size < 1:
        raise ValueError("games per JVM must be positive")
    order = list(range(count))[::-1] if reverse else list(range(count))
    return [order[start : start + size] for start in range(0, count, size)]


def failure_family(error: str | None) -> str:
    """The most specific public code of the failure, else the exception type.

    The bridge error carries ``ENGINE_FAILURE [ENGINE_FAILURE, XMAGE_ACTION_EXECUTION_FAILED]``:
    the generic wrapper first, the cause after it. Only those codes are public; which card
    caused the failure stays in the redacted diagnostics.
    """
    if not error:
        return "NONE"
    listed = _CODE_LIST.search(error)
    if listed:
        specific = [c for c in listed.group(1).split(", ") if c != _GENERIC]
        if specific:
            return specific[-1]
    match = _FAMILY.search(error)
    return match.group(0) if match else error.split(":", 1)[0].strip() or "UNKNOWN"


def importable_decks(report_path: Path) -> list[str]:
    """Deck stems whose import row is OK in an import measurement report."""
    rows = json.loads(report_path.read_text(encoding="utf-8"))["results"]
    return sorted(row["deck"] for row in rows if row["status"] == "OK")


def summarize(pods: Sequence[dict[str, Any]]) -> dict[str, Any]:
    families = Counter(failure_family(p.get("error")) for p in pods if p["status"] != "ok")
    ok = sum(1 for p in pods if p["status"] == "ok")
    return {
        "pods": len(pods),
        "pods_ok": ok,
        "pods_failed": len(pods) - ok,
        "families": dict(families),
    }


def run(args: argparse.Namespace) -> int:
    import benchmark_xmage_full_games as bench  # heavy imports, kept off the planning tests

    deck_dir = args.deck_dir.resolve()
    try:
        deck_dir.relative_to(ROOT)
    except ValueError:
        print(f"--deck-dir must be inside the repository ({ROOT})", file=sys.stderr)
        return 2
    if args.import_report:
        names = importable_decks(args.import_report)
    else:
        names = sorted(p.stem for p in deck_dir.glob("*.json"))
    pods = plan_pods(names, POD_SIZE, args.plan_seed)
    if args.limit:
        pods = pods[: args.limit]
    jvm_options = list(args.jvm_option)
    if args.fast:
        jvm_options = bench.fast_jvm_options(args.jar) + jvm_options
    if args.games_per_jvm > 1:
        jvm_options.append(f"-D{bench.GAMES_PER_JVM_PROPERTY}={args.games_per_jvm}")
    command = bench.bridge_command(args.jar, jvm_options)
    setups = [
        bench._setup(tuple((deck_dir / f"{name}.json").relative_to(ROOT) for name in decks))
        for decks in pods
    ]
    rows: list[dict[str, Any]] = []
    lock = threading.Lock()

    def play(indices: Sequence[int]) -> None:
        if len(indices) == 1:
            i = indices[0]
            played = [bench._play(command, f"pod-{i:03d}", setups[i], args.game_seed, True)]
        else:
            jobs = [(f"pod-{i:03d}", setups[i], args.game_seed) for i in indices]
            played = bench._play_batch(command, jobs, True)
        for i, row in zip(indices, played, strict=True):
            row["decks"] = list(pods[i])
        with lock:
            rows.extend(played)
            report = {
                "jar": str(args.jar),
                "jvm_options": jvm_options,
                "games_per_jvm": args.games_per_jvm,
                "game_seed": args.game_seed,
                "plan_seed": args.plan_seed,
            }
            report |= summarize(rows) | {"rows": sorted(rows, key=lambda r: r["pod"])}
            args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(play, chunk_indices(len(pods), args.games_per_jvm, args.reverse)))
    print(json.dumps(summarize(rows)))
    return 0 if all(row["status"] == "ok" for row in rows) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--import-report", type=Path, default=None)
    parser.add_argument("--deck-dir", type=Path, default=PRECON_DIR)
    parser.add_argument("--plan-seed", type=int, default=1, help="shuffle seed of the pod plan")
    parser.add_argument("--game-seed", type=int, default=1, help="Rules seed of every game")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--jvm-option",
        action="append",
        default=[],
        help="extra JVM option before -jar, in the =-form (--jvm-option=-XX:...)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="serial GC and, if present, the jar's AppCDS archive (see benchmark_xmage_full_games)",
    )
    parser.add_argument(
        "--games-per-jvm",
        type=int,
        default=1,
        help="pods per bridge JVM (measurement runs only; default 1)",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="play the pods last to first (batch leak check: other neighbours than a forward run)",
    )
    parser.add_argument("--limit", type=int, default=0, help="play only the first N pods")
    args = parser.parse_args(argv)
    if args.games_per_jvm < 1:
        parser.error("--games-per-jvm must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
