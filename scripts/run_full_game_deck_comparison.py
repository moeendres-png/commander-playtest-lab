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

With ``--stop-when-decided`` the seeds run in blocks of ``--look-every`` seeds
(default 5) in the given order. After each block the finished games are
aggregated, and the run stops early once every variant has a decided verdict
(VARIANT_BETTER or BASELINE_BETTER) at a Bonferroni-split per-look threshold
(significance level divided by the number of planned looks), so the overall
Type I error stays at 5%. The report records the sequential plan under
``sequential`` and the summary says how many of the seeds were played.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from commander_lab.deck_readiness import check_deck, format_deck_report
from commander_lab.engine.rules.full_game import XmageFullGameRunner
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    FullGameBatchRecord,
    FullGameBatchReport,
    XmageFullGameBatchRunner,
    execution_identity_of,
)
from commander_lab.engine.rules.full_game_comparison import (
    DeckComparisonReport,
    DeckComparisonSpec,
    aggregate_comparison,
    plan_comparison_cases,
    sequential_look_alpha,
    sequential_looks_planned,
    sequential_stop_now,
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


# Deck readiness (#834): warn about cards the simulator cannot play well before
# spending hours of full games on a deck.


def print_readiness_summary(
    contenders: tuple[RulesDeckInput, ...], opponents: tuple[RulesDeckInput, ...]
) -> bool:
    """Print the readiness report of every contender and opponent.

    Returns True only when every deck is ready.
    """
    ready = True
    for label, deck in (
        *[("contender", deck) for deck in contenders],
        *[("opponent", deck) for deck in opponents],
    ):
        report = check_deck(deck)
        print(format_deck_report(f"{label} {deck.deck_id}", report))
        ready = ready and report.ready
    return ready


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
            f"baseline-only {row['baseline_only_wins']}, "
            f"identical games {row.get('identical_pairs', 0)}, "
            f"p={row['sign_test_p_value']:.3g})"
        )
    sequential = report_json.get("sequential")
    if sequential is not None:
        lines.append(
            f"stopped after {sequential['seeds_played']} of {len(report_json['seeds'])} seeds"
        )
    return lines


def run_sequential_blocks(
    spec: DeckComparisonSpec,
    cases: tuple[FullGameBatchCase, ...],
    run_block: Callable[[tuple[FullGameBatchCase, ...]], FullGameBatchReport],
    *,
    look_every: int,
    significance_level: float = 0.05,
) -> tuple[DeckComparisonReport, FullGameBatchReport, dict[str, Any]]:
    """Play seeds in blocks of ``look_every`` and stop once decided (#832).

    After each block the finished games are aggregated with the Bonferroni-split
    per-look alpha; the run stops early once every variant has a decided verdict
    at that level. Each look aggregates over the seeds played so far (a
    sub-spec), so unplayed seeds are never counted as censored. The final look
    uses the same threshold. Returns the comparison report, the combined batch
    report over the blocks played, and the ``sequential`` payload for the
    report JSON.
    """
    looks_planned = sequential_looks_planned(len(spec.seeds), look_every)
    per_look_alpha = sequential_look_alpha(significance_level, looks_planned)
    records: list[FullGameBatchRecord] = []
    looks_used = 0
    seeds_played = 0
    seed_list = list(spec.seeds)
    for start in range(0, len(seed_list), look_every):
        block = tuple(seed_list[start : start + look_every])
        report = run_block(tuple(case for case in cases if case.scenario.seed in block))
        records.extend(report.records)
        looks_used += 1
        seeds_played += len(block)
        combined = FullGameBatchReport(
            total_cases=len(records),
            completed_cases=sum(1 for record in records if record.status == "completed"),
            failed_cases=sum(1 for record in records if record.status == "failed"),
            resumed_cases=sum(1 for record in records if record.resumed_from_completed_record),
            records=tuple(records),
        )
        look_spec = spec.model_copy(update={"seeds": tuple(seed_list[:seeds_played])})
        comparison = aggregate_comparison(look_spec, combined, significance_level=per_look_alpha)
        if sequential_stop_now(comparison.paired):
            break
    sequential = {
        "looks_planned": looks_planned,
        "looks_used": looks_used,
        "per_look_alpha": per_look_alpha,
        "stopped_early": seeds_played < len(spec.seeds),
        "seeds_played": seeds_played,
    }
    return comparison, combined, sequential


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
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="refuse to run unless every contender and opponent deck is ready",
    )
    parser.add_argument(
        "--stop-when-decided",
        action="store_true",
        help="play seeds in blocks of --look-every and stop early once every "
        "variant has a decided verdict at the per-look threshold",
    )
    parser.add_argument(
        "--look-every",
        type=int,
        default=5,
        metavar="K",
        help="seeds per interim look with --stop-when-decided (default: 5)",
    )
    args = parser.parse_args(argv)

    contenders = distinct_contenders(
        [load_deck(args.baseline), *(load_deck(path) for path in args.variant)]
    )
    opponents = tuple(load_deck(path) for path in args.opponent)
    decks_ready = print_readiness_summary(contenders, opponents)
    if args.require_ready and not decks_ready:
        print(
            "--require-ready: refusing to run because a deck is not ready",
            file=sys.stderr,
        )
        return 1
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
    if args.look_every < 1:
        parser.error("--look-every must be at least 1")
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
    sequential: dict[str, Any] | None = None
    if args.stop_when_decided:
        looks_planned = sequential_looks_planned(len(spec.seeds), args.look_every)
        print(
            f"sequential: {looks_planned} planned looks of {args.look_every} seeds, "
            f"per-look alpha {sequential_look_alpha(0.05, looks_planned):.4g}"
        )

        def run_block(block_cases: tuple[FullGameBatchCase, ...]) -> FullGameBatchReport:
            seeds = sorted({case.scenario.seed for case in block_cases})
            print(f"look: playing seeds {seeds[0]}-{seeds[-1]} ({len(block_cases)} games)")
            return batch.run(
                block_cases,
                retry_failed=args.retry_failed,
                workers=workers,
                parallelism=args.parallelism,
            )

        comparison, report, sequential = run_sequential_blocks(
            spec, cases, run_block, look_every=args.look_every
        )
    else:
        report = batch.run(
            cases,
            retry_failed=args.retry_failed,
            workers=workers,
            parallelism=args.parallelism,
        )
        comparison = aggregate_comparison(spec, report)
    payload = comparison.model_dump(mode="json")
    if sequential is not None:
        payload["sequential"] = sequential
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
