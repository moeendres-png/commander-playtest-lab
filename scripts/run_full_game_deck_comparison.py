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

A variant need not be a file: ``--swap 'Sol Ring=>Mind Stone'`` exchanges cards of the
baseline in place (``'A=>B;C=>D'`` for several in one variant; repeat ``--swap`` for more
variants). The variant keeps the baseline's card order apart from the slots of the
swapped cards.

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
import math
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from commander_lab.deck_readiness import check_deck, format_deck_report, readiness_payload
from commander_lab.engine.rules.full_game import XmageFullGameRunner
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    FullGameBatchRecord,
    FullGameBatchReport,
    FullGameBatchReportBatched,
    XmageFullGameBatchRunner,
    command_with_games_per_jvm,
    execution_identity_of,
)
from commander_lab.engine.rules.full_game_comparison import (
    DeckComparisonReport,
    DeckComparisonSpec,
    SwapSpecError,
    aggregate_comparison,
    apply_swaps,
    difference_quantiles,
    pairs_needed,
    parse_swaps,
    plan_comparison_cases,
    planned_detectable_difference,
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


def with_deck_hash(deck: RulesDeckInput) -> RulesDeckInput:
    """The deck with a content hash: its own, or derived from its cards."""
    if deck.deck_hash is not None:
        return deck
    return deck.model_copy(
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


def load_deck(path: Path) -> RulesDeckInput:
    return with_deck_hash(load_rules_deck_snapshot(path))


def swap_variants(baseline: RulesDeckInput, swap_texts: list[str]) -> list[RulesDeckInput]:
    """One variant per ``--swap`` text: the baseline with those cards exchanged."""
    variants: list[RulesDeckInput] = []
    seen = {tuple(sorted(baseline.mainboard)): baseline.deck_id}
    for index, text in enumerate(swap_texts, start=1):
        swapped = apply_swaps(baseline, parse_swaps(text))
        variant = with_deck_hash(
            swapped.model_copy(update={"deck_id": f"{baseline.deck_id}#swap{index}"})
        )
        twin = seen.setdefault(tuple(sorted(variant.mainboard)), variant.deck_id)
        if twin != variant.deck_id:
            raise SwapSpecError(f"swap {text!r} plays the same cards as {twin}")
        variants.append(variant)
    return variants


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


def _precision_lines(row: dict[str, Any]) -> list[str]:
    """One extra line per variant with the precision figures (#870).

    Every new key is read with ``.get``: payloads stored before #870 (and the
    optimizer route, which prints the same payload shape) keep printing the
    old lines unchanged. The per-pair sd is recovered from the detectable
    difference, so the summary needs no extra stored field.
    """
    interval = row.get("win_share_difference_interval_95")
    detectable = row.get("detectable_difference_80pct_power")
    difference = row.get("win_share_difference")
    pairs = row.get("pairs_completed")
    if (
        not isinstance(interval, dict)
        or not isinstance(interval.get("low"), (int, float))
        or not isinstance(interval.get("high"), (int, float))
        or not isinstance(detectable, (int, float))
        or not isinstance(difference, (int, float))
        or not isinstance(pairs, int)
        or pairs < 2
    ):
        return []
    # The detectable difference is (t95 + t80) * sd / sqrt(pairs) with pairs - 1 degrees of
    # freedom since #1074; a payload stored before it used the normal 1.96 + 0.8416, so its
    # recovered sd is low by the ratio of the two (about 5% at 24 pairs).
    q95, q80 = difference_quantiles(pairs - 1)
    sd = detectable * math.sqrt(pairs) / (q95 + q80)
    lines = [
        f"{row['variant_deck_id']} vs {row['baseline_deck_id']}: "
        f"difference {difference:+.2f} "
        f"(95% {interval['low']:+.2f}..{interval['high']:+.2f}), "
        f"run could detect >= {detectable:.2f}; "
        f"0.10 needs ~{pairs_needed(0.10, sd)} pairs, "
        f"0.05 needs ~{pairs_needed(0.05, sd)} pairs"
    ]
    if row.get("underpowered"):
        lines.append(f"UNDERPOWERED: {row['verdict']} here is not evidence of no effect")
    return lines


def _cluster_lines(row: dict[str, Any]) -> list[str]:
    """The seed-cluster interval next to the pair interval (#1070, finding LAB-01).

    The four seat rotations of a seed share one shuffle, so the pairs of a seed are not
    independent; the pair-based verdict and interval above treat them as if they were. The
    cluster-robust interval (one cluster per seed, t with G - 1 degrees of freedom) is stored in
    the payload since #1043 but was never printed. This line prints it, and a caution when the
    verdict is decided while that interval contains 0. The verdict itself is unchanged. Every key
    is read with ``.get`` (payloads stored before #1043 print unchanged), and nothing is printed
    when every seed holds a single pair, because the two intervals are then the same.
    """
    interval = row.get("cluster_difference_interval_95")
    detectable = row.get("cluster_detectable_difference_80pct_power")
    difference = row.get("win_share_difference")
    seeds = row.get("seed_clusters_completed")
    pairs = row.get("pairs_completed")
    if (
        not isinstance(interval, dict)
        or not isinstance(interval.get("low"), (int, float))
        or not isinstance(interval.get("high"), (int, float))
        or not isinstance(difference, (int, float))
        or not isinstance(seeds, int)
        or not isinstance(pairs, int)
        or seeds < 2
        or seeds >= pairs
    ):
        return []
    low, high = float(interval["low"]), float(interval["high"])
    line = (
        f"per seed ({seeds} seeds; the seat rotations of a seed share a shuffle): "
        f"difference {difference:+.2f} (95% {low:+.2f}..{high:+.2f})"
    )
    if isinstance(detectable, (int, float)):
        line += f", run could detect >= {detectable:.2f}"
    lines = [line]
    if row.get("verdict") in ("VARIANT_BETTER", "BASELINE_BETTER") and low <= 0.0 <= high:
        lines.append(
            f"CAUTION: {row['verdict']} counts every pair as independent, but the per-seed "
            "interval contains 0; treat the verdict as not yet confirmed"
        )
    return lines


def _cluster_t_lines(row: dict[str, Any]) -> list[str]:
    """The per-seed t test next to the pair sign test (E6 stage 2).

    The seat rotations of one seed share a shuffle and the pair sign test counts them as
    independent, so a decided verdict also needs the cluster-robust t statistic (one cluster per
    seed) to exceed the t quantile of the same level. Nothing is printed for payloads stored
    before the field existed, or when every seed holds a single pair (the pair test then stands
    alone). When the pair test alone was decided and the t test did not confirm it, the line says
    so, because the verdict is then NO_CLEAR_DIFFERENCE although the pair p-value above is small.
    """
    statistic = row.get("cluster_t_statistic")
    pair_verdict = row.get("pair_test_verdict")
    seeds = row.get("seed_clusters_completed")
    pairs = row.get("pairs_completed")
    if not isinstance(seeds, int) or not isinstance(pairs, int) or seeds < 2 or seeds >= pairs:
        return []
    lines: list[str] = []
    if isinstance(statistic, (int, float)):
        lines.append(
            f"per seed t test: t={statistic:+.2f} (df {row.get('cluster_t_df', seeds - 1)}); a "
            "decided verdict needs the pair test and this t to agree"
        )
    if pair_verdict in ("VARIANT_BETTER", "BASELINE_BETTER"):
        lines.append(
            f"NOTE: the pair test alone would say {pair_verdict}; the per-seed t test does not "
            "confirm it, so the verdict stays NO_CLEAR_DIFFERENCE"
        )
    return lines


def _holm_lines(row: dict[str, Any], variants: int) -> list[str]:
    """The Holm correction over the variants of a run (E6 stage 3).

    With two or more variants the verdicts are adjusted for looking at several of them: a
    decided verdict stands only if its Holm-adjusted p-value is below the level. Printed for
    payloads that carry the adjusted value; when Holm held back a decided verdict the line says so,
    because the verdict is then NO_CLEAR_DIFFERENCE although the pair p-value above is small.
    """
    adjusted = row.get("holm_adjusted_p_value")
    withheld = row.get("holm_withheld_verdict")
    if not isinstance(adjusted, (int, float)) or variants < 2:
        return []
    lines = [
        f"Holm over {variants} variants: adjusted p={adjusted:.3g}; a decided verdict needs "
        "this below the level"
    ]
    if withheld in ("VARIANT_BETTER", "BASELINE_BETTER"):
        lines.append(
            f"NOTE: before the correction for several variants this was {withheld}; it is not "
            "confirmed across the variants, so the verdict stays NO_CLEAR_DIFFERENCE"
        )
    return lines


def _placement_lines(row: dict[str, Any]) -> list[str]:
    """One extra line per variant with the finishing-order outcome (#875).

    Every new key is read with ``.get``: payloads stored before #875 keep
    printing the old lines unchanged.
    """
    interval = row.get("placement_difference_interval_95")
    difference = row.get("placement_difference")
    pairs = row.get("placement_pairs")
    if (
        not isinstance(interval, dict)
        or not isinstance(interval.get("low"), (int, float))
        or not isinstance(interval.get("high"), (int, float))
        or not isinstance(difference, (int, float))
        or not isinstance(pairs, int)
        or pairs < 2
    ):
        return []
    return [
        f"finishing order: {row['variant_deck_id']} {difference:+.2f} "
        f"(95% {interval['low']:+.2f}..{interval['high']:+.2f}) over {pairs} pairs"
    ]


def _readiness_lines(report_json: dict[str, Any], variant_id: str) -> list[str]:
    """A PARTIAL line for a variant that differs from the baseline by cards the pilot is not ready for.

    Read with ``.get``: payloads stored before the readiness block print unchanged.
    """
    entry = ((report_json.get("pilot_readiness") or {}).get("variants") or {}).get(variant_id)
    if not isinstance(entry, dict) or entry.get("comparable", True):
        return []

    def names(rows: list[dict[str, str]]) -> str:
        return ", ".join(f"{row['name']} ({row['status']})" for row in rows)

    parts = []
    if entry.get("added_not_ready"):
        parts.append(f"adds {names(entry['added_not_ready'])}")
    if entry.get("removed_not_ready"):
        parts.append(f"removes {names(entry['removed_not_ready'])}")
    return [
        f"PARTIAL: {variant_id} {'; '.join(parts)}: the pilot plays a card it is not ready for "
        "as a spell without cost or role, so this verdict compares that, not the card"
    ]


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
            f"identical pairs {row['identical_pairs']}, "
            f"p={row['sign_test_p_value']:.3g})"
        )
        lines.extend(_precision_lines(row))
        lines.extend(_cluster_lines(row))
        lines.extend(_cluster_t_lines(row))
        lines.extend(_holm_lines(row, len(report_json["paired"])))
        lines.extend(_placement_lines(row))
        lines.extend(_readiness_lines(report_json, row["variant_deck_id"]))
    sequential = report_json.get("sequential")
    if sequential is not None:
        lines.append(
            f"stopped after {sequential['seeds_played']} of {len(report_json['seeds'])} seeds"
        )
    return lines


def _slim_record_for_aggregate(record: FullGameBatchRecord) -> FullGameBatchRecord:
    """Drop everything ``aggregate_comparison`` never reads (#992).

    A real batch record carries the multi-MB game transcript in
    ``result.result_payload`` (measured on an M4 record file: 1.58 MB of
    2.30 MB total); the sequential runner retained every record, so RSS
    grew with the game count (5.25 GB at 495 records, #992). The aggregate
    reads exactly: ``case_id``, ``status``, ``failure_class``, the resumed
    flag (for the report counts), and, for completed records,
    ``result.winner_seats``, ``result.semantic_transcript_sha256``,
    ``result.decision_count`` and ``result.result_payload``'s ``outcomes``
    and ``turn_number``. Everything else is dropped at ingest; the full
    records stay on disk, one file per game, written by the batch layer.
    The byte-identity test in ``test_sequential_runner_memory.py`` guards
    this whitelist: if the aggregate ever reads more, that test fails.
    """
    if record.result is None:
        return record
    payload = record.result.result_payload
    slim_payload = {k: payload[k] for k in ("outcomes", "turn_number") if k in payload}
    return record.model_copy(
        update={
            "result": record.result.model_copy(update={"result_payload": slim_payload}),
        }
    )


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

    Memory (#992): the combined report's records are slimmed at ingest by
    ``_slim_record_for_aggregate`` to the aggregate inputs only, so retained
    memory grows with a small constant per record instead of with the game
    transcripts. The comparison report written to COMPARISON_REPORT.json is
    unchanged: it holds counts, not records.
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
        records.extend(_slim_record_for_aggregate(record) for record in report.records)
        looks_used += 1
        seeds_played += len(block)
        counts: dict[str, Any] = {
            "total_cases": len(records),
            "completed_cases": sum(1 for record in records if record.status == "completed"),
            "failed_cases": sum(1 for record in records if record.status == "failed"),
            "resumed_cases": sum(1 for record in records if record.resumed_from_completed_record),
            "records": tuple(records),
        }
        combined: FullGameBatchReport = (
            FullGameBatchReportBatched(games_per_jvm=report.games_per_jvm, **counts)
            if isinstance(report, FullGameBatchReportBatched)
            else FullGameBatchReport(**counts)
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
    parser.add_argument("--variant", type=Path, action="append", default=[])
    parser.add_argument(
        "--swap",
        action="append",
        default=[],
        metavar="OUT=>IN",
        help="a variant made from the baseline by exchanging cards in place, e.g. "
        "'Sol Ring=>Mind Stone' (several swaps of one variant: 'A=>B;C=>D'); "
        "repeat the option for more variants",
    )
    parser.add_argument("--opponent", type=Path, action="append", required=True)
    parser.add_argument("--seeds", required=True, help="e.g. 1-25 or 3,7,9")
    parser.add_argument("--no-rotate", action="store_true", help="test seat 1 only")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--comparison-id", default=None)
    parser.add_argument("--workers", type=int, default=None, help="default: from cores/memory")
    parser.add_argument("--parallelism", choices=("thread", "process"), default="thread")
    parser.add_argument(
        "--games-per-jvm",
        type=int,
        default=1,
        metavar="N",
        help="play up to N games in one bridge JVM (default 1: a fresh JVM per game). "
        "Faster (about a quarter on 4-player pods, #877); the games of a batch are isolated "
        "by shutdown_game and checked by twin hashes, not by a process boundary, and the "
        "report says so. Measurement runs only; the evidence and gate lanes always use 1.",
    )
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-decisions", type=int, default=50_000)
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--plan-only", action="store_true", help="print the plan and stop")
    parser.add_argument(
        "--games-per-hour",
        type=float,
        default=40.0,
        help="host throughput for the time estimate (default: 40); "
        "measure once on the host, speed depends on the machine",
    )
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

    if not args.variant and not args.swap:
        parser.error("give at least one --variant or --swap")
    if args.games_per_jvm < 1:
        parser.error("--games-per-jvm must be at least 1")
    baseline = load_deck(args.baseline)
    try:
        swapped = swap_variants(baseline, args.swap)
    except SwapSpecError as error:
        parser.error(str(error))
    contenders = distinct_contenders(
        [baseline, *(load_deck(path) for path in args.variant), *swapped]
    )
    for variant, text in zip(swapped, args.swap, strict=True):
        print(f"{variant.deck_id}: {text}")
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
    if args.games_per_hour <= 0:
        parser.error("--games-per-hour must be positive")
    workers = args.workers or default_workers(memory_gb=_available_memory_gb())
    print(
        f"{len(cases)} games: {len(spec.contenders)} contenders x {len(spec.seeds)} seeds x "
        f"{len(spec.tested_seats)} seats, {spec.player_count} players, {workers} workers"
    )
    # Pairs per variant-vs-baseline comparison: each seed x each tested seat.
    pairs = len(spec.seeds) * len(spec.tested_seats)
    detectable = planned_detectable_difference(pairs)
    print(
        f"Time estimate at {args.games_per_hour:g} games/hour: "
        f"{len(cases) / args.games_per_hour:.1f} h"
    )
    print(
        "Detectable win-share difference per variant "
        f"(80% power, {pairs} pairs): \u00b1 {detectable:.2f}. "
        "This figure assumes independent games (per-pair sd 0.63); pairs that "
        "end identically make the real figure smaller, and the run prints its "
        "own figure at the end."
    )
    if args.plan_only:
        return 0

    command = XmageFullGameRunner.command_from_environment()
    if command is None:
        print("set COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD first", file=sys.stderr)
        return 2
    # Always set the property explicitly: a batched run and an ordinary run must never share a
    # run key, whatever the environment command already carries.
    command = command_with_games_per_jvm(command, args.games_per_jvm)
    if args.games_per_jvm > 1:
        print(
            f"games per JVM: {args.games_per_jvm}. State isolation between the games of a "
            "batch is by shutdown_game, not by a process boundary."
        )
    runner = XmageFullGameRunner(
        command,
        max_decisions=args.max_decisions,
        request_timeout_seconds=args.request_timeout,
    )
    batch = XmageFullGameBatchRunner(runner, args.out / "games", games_per_jvm=args.games_per_jvm)
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
    if args.swap:
        payload["swaps"] = {
            variant.deck_id: text for variant, text in zip(swapped, args.swap, strict=True)
        }
    payload["pilot_readiness"] = readiness_payload(contenders, opponents)
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
    if isinstance(report, FullGameBatchReportBatched):
        # Only a batched run says anything about isolation; the one-game-per-JVM report is unchanged.
        payload["batch"]["games_per_jvm"] = report.games_per_jvm
        payload["batch"]["one_isolated_jvm_per_executed_game"] = False
        payload["batch"]["state_isolation_basis"] = report.state_isolation_basis
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "COMPARISON_REPORT.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for line in _summary_lines(payload):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
