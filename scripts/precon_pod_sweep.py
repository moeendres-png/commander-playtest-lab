"""Play the precon decks in real 4-player pods and group the failures by cause.

Every pod seats four DIFFERENT decks: the full-game validator rejects one deck on several
seats before any JVM starts (``distinct deck identities per seat``), so a sweep that repeats a
deck measures that rejection and never plays a game. The plan covers every selected deck at
least once; with ``--pod-size`` not dividing the deck count the last pod is filled from the
start of the shuffled list.

    python scripts/precon_pod_sweep.py --jar bridge.jar --out sweep.json --workers 2
    # only decks that import cleanly (output of an import measurement: {"results": [...]})
    python scripts/precon_pod_sweep.py --jar bridge.jar --out sweep.json \\
        --import-report imports.json

A failed pod is a result row, not a crash. The game is played by ``benchmark_xmage_full_games``
(same pilots, private card repository, bridge command). Local runs are measurements, not
qualification evidence; only one sweep should run at a time, because CPU contention turns slow
decisions into ``DECISION_ADVANCE_TIMEOUT`` rows.
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
_FAMILY = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b")


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


def failure_family(error: str | None) -> str:
    """The bridge's own error code when the message carries one, else the exception type."""
    if not error:
        return "NONE"
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

    if args.import_report:
        names = importable_decks(args.import_report)
    else:
        names = sorted(p.stem for p in PRECON_DIR.glob("*.json"))
    pods = plan_pods(names, args.pod_size, args.plan_seed)
    if args.limit:
        pods = pods[: args.limit]
    command = bench.bridge_command(args.jar, [])
    setups = [
        bench._setup(tuple((PRECON_DIR / f"{name}.json").relative_to(ROOT) for name in decks))
        for decks in pods
    ]
    rows: list[dict[str, Any]] = []
    lock = threading.Lock()

    def play(index: int) -> None:
        row = bench._play(command, f"pod-{index:03d}", setups[index], args.game_seed, True)
        row["decks"] = list(pods[index])
        with lock:
            rows.append(row)
            report = {
                "jar": str(args.jar),
                "game_seed": args.game_seed,
                "plan_seed": args.plan_seed,
            }
            report |= summarize(rows) | {"rows": sorted(rows, key=lambda r: r["pod"])}
            args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(play, range(len(pods))))
    print(json.dumps(summarize(rows)))
    return 0 if all(row["status"] == "ok" for row in rows) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--import-report", type=Path, default=None)
    parser.add_argument("--pod-size", type=int, default=4)
    parser.add_argument("--plan-seed", type=int, default=1, help="shuffle seed of the pod plan")
    parser.add_argument("--game-seed", type=int, default=1, help="Rules seed of every game")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0, help="play only the first N pods")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
