"""Compare a baseline deck with one or more variants on real XMage full games (#731).

Every contender plays the same pods (same seeds, same opponents, every seat when
seats rotate), so the result is a paired comparison. Games run in parallel, one
fresh bridge JVM per game, and finished games are reused when the command is
run again with the same output directory.

Example (four-player pods, 25 seeds x 4 seats x 2 contenders = 200 games):

    export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar full-game"
    python scripts/run_full_game_deck_comparison.py \\
        --baseline data/decks/rogshai_current.json \\
        --variant my_variant.json \\
        --opponent data/decks/opponents/kaervek/current/deck.json \\
        --opponent data/opponents/hosts_of_mordor_precon.json \\
        --opponent data/opponents/lorehold_spirit_precon.json \\
        --seeds 1-25 --out artifacts/deck-comparison/rogshai-vs-variant

The report is exploratory deck-building evidence for this pilot policy and
engine pin. It is not official campaign or holdout evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.full_game import XmageFullGameRunner
from commander_lab.engine.rules.full_game_batch import (
    XmageFullGameBatchRunner,
    execution_identity_of,
)
from commander_lab.engine.rules.full_game_comparison import (
    DeckComparisonSpec,
    aggregate_comparison,
    plan_comparison_cases,
)
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import RulesDeckInput
from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)
from commander_lab.storage import sha256_value

# One real 4P game keeps a bridge JVM at roughly 1.5 GB resident. Throughput
# on a 4-core host (#731, six real 4P games): 1/2/3/4/6 workers gave
# 22/36/39/56/43 games per hour, so one worker per core is the sweet spot.
_GB_PER_WORKER = 2.0
_CORES_PER_WORKER = 1.0


def parse_seeds(text: str) -> tuple[int, ...]:
    """``"1-25"``, ``"3,7,9"`` or a mix such as ``"1-5,9"``."""
    seeds: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low, high = (int(value) for value in part.split("-", 1))
            if high < low:
                raise ValueError(f"reversed seed range: {part}")
            seeds.extend(range(low, high + 1))
        else:
            seeds.append(int(part))
    if not seeds:
        raise ValueError("no seeds given")
    return tuple(seeds)


def _available_memory_gb() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        return None
    return None


def default_workers(cpu_count: int | None = None, memory_gb: float | None = None) -> int:
    """As many concurrent games as cores and memory carry, at least one."""
    cpus = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    by_cpu = int(cpus / _CORES_PER_WORKER)
    by_memory = int(memory_gb / _GB_PER_WORKER) if memory_gb is not None else by_cpu
    return max(1, min(by_cpu, by_memory))


def load_deck(path: Path) -> RulesDeckInput:
    deck = load_rules_deck_snapshot(path)
    if deck.deck_hash is None:
        deck = deck.model_copy(
            update={
                "deck_hash": sha256_value(
                    {
                        "deck_id": deck.deck_id,
                        "commander_names": list(deck.commander_names),
                        "mainboard": list(deck.mainboard),
                        "sideboard": list(deck.sideboard),
                    }
                )
            }
        )
    return deck


def distinct_contenders(decks: list[RulesDeckInput]) -> tuple[RulesDeckInput, ...]:
    """Give a variant that reuses the baseline's deck id its own id."""
    seen: set[str] = set()
    result: list[RulesDeckInput] = []
    for index, deck in enumerate(decks):
        if deck.deck_id in seen:
            deck = deck.model_copy(update={"deck_id": f"{deck.deck_id}#variant{index}"})
        seen.add(deck.deck_id)
        result.append(deck)
    return tuple(result)


def _summary_lines(report_json: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for row in report_json["contenders"]:
        share = row["win_share"]
        interval = row["win_share_interval_95"]
        lines.append(
            f"{row['deck_id']}: {row['wins']:.1f}/{row['games_completed']} wins"
            + (
                f" ({share:.1%}, 95% {interval['low']:.1%}-{interval['high']:.1%})"
                if isinstance(share, float)
                else ""
            )
            + f", failed {row['games_failed']}"
        )
    for row in report_json["paired"]:
        lines.append(
            f"{row['variant_deck_id']} vs {row['baseline_deck_id']}: {row['verdict']} "
            f"(pairs {row['pairs_completed']}, variant-only {row['variant_only_wins']}, "
            f"baseline-only {row['baseline_only_wins']}, p={row['sign_test_p_value']:.3g})"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--variant", type=Path, action="append", required=True)
    parser.add_argument("--opponent", type=Path, action="append", required=True)
    parser.add_argument("--seeds", required=True, help="e.g. 1-25 or 3,7,9")
    parser.add_argument("--no-rotate", action="store_true", help="test seat 1 only")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--comparison-id", default=None)
    parser.add_argument("--workers", type=int, default=None, help="default: from cores/memory")
    parser.add_argument("--parallelism", choices=("thread", "process"), default="thread")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-decisions", type=int, default=50_000)
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--plan-only", action="store_true", help="print the plan and stop")
    args = parser.parse_args(argv)

    contenders = distinct_contenders(
        [load_deck(args.baseline), *(load_deck(path) for path in args.variant)]
    )
    opponents = tuple(load_deck(path) for path in args.opponent)
    spec = DeckComparisonSpec(
        comparison_id=args.comparison_id or f"deck-comparison:{contenders[0].deck_id}",
        contenders=contenders,
        opponents=opponents,
        seeds=parse_seeds(args.seeds),
        rotate_seats=not args.no_rotate,
        xmage_commit=canonical_xmage_engine_pin(),
    )
    cases = plan_comparison_cases(spec)
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be at least 1")
    workers = args.workers or default_workers(memory_gb=_available_memory_gb())
    print(
        f"{len(cases)} games: {len(spec.contenders)} contenders x {len(spec.seeds)} seeds x "
        f"{len(spec.tested_seats)} seats, {spec.player_count} players, {workers} workers"
    )
    if args.plan_only:
        return 0

    command = XmageFullGameRunner.command_from_environment()
    if command is None:
        print("set COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD first", file=sys.stderr)
        return 2
    runner = XmageFullGameRunner(
        command,
        max_decisions=args.max_decisions,
        request_timeout_seconds=args.request_timeout,
    )
    batch = XmageFullGameBatchRunner(runner, args.out / "games")
    report = batch.run(
        cases,
        retry_failed=args.retry_failed,
        workers=workers,
        parallelism=args.parallelism,
    )
    comparison = aggregate_comparison(spec, report)
    payload = comparison.model_dump(mode="json")
    payload["engine"] = {
        "xmage_commit": spec.xmage_commit,
        "execution_identity": execution_identity_of(runner),
        "max_decisions": args.max_decisions,
    }
    payload["batch"] = {
        "total_cases": report.total_cases,
        "completed_cases": report.completed_cases,
        "failed_cases": report.failed_cases,
        "resumed_cases": report.resumed_cases,
        "workers": workers,
        "parallelism": args.parallelism,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "COMPARISON_REPORT.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for line in _summary_lines(payload):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
