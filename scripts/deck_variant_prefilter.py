"""Deck-variant prefilter: screen variants against a baseline before real games (#852).

Compares each variant deck against the baseline (card diff, readiness, mana,
commander castability) and prints a go/no-go verdict per variant. Afterwards it
prints the planned game count, a time estimate at the host's games/hour
(--games-per-hour), and the win-share difference the planned pairs can detect
(80% power, #873).

The verdict is a filter (cheap screening), not a ranking of variants.

Exit codes: 0 when every variant is PASS_TO_GAMES or WARN, 1 when any variant
is BLOCKED, 2 when a deck file cannot be loaded.

Example:

    PYTHONPATH=src python scripts/deck_variant_prefilter.py \\
        --baseline data/decks/rogshai_current.json \\
        --variant /tmp/variant_a.json --variant /tmp/variant_b.json \\
        --trials 20000 --seeds 1-25 --players 4 --games-per-hour 60
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from commander_lab.deck_profile import load_deck
from commander_lab.deck_variant import (
    PREFILTER_TURNS,
    VERDICT_BLOCKED,
    FilterVerdict,
    VariantComparison,
    compare_variant,
    comparison_to_dict,
)
from commander_lab.engine.rules.full_game_comparison import planned_detectable_difference
from commander_lab.mana_analysis import DEFAULT_CASTABILITY_SEED
from commander_lab.models import RulesDeckInput

#: Default full games per hour for the time estimate. Measure on the host
#: (games / wall-clock hour for this script's planned workload) and override
#: with --games-per-hour; speed depends on the machine, not the script.
DEFAULT_GAMES_PER_HOUR = 40.0


def _parse_seeds(raw: str) -> int:
    """Parse --seeds: either a count ("25") or an inclusive range ("1-25")."""
    text = raw.strip()
    if "-" in text:
        start_raw, end_raw = text.split("-", 1)
        try:
            start, end = int(start_raw), int(end_raw)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"invalid --seeds range {raw!r}: expected 'START-END'"
            ) from None
        if start < 1 or end < start:
            raise argparse.ArgumentTypeError(
                f"invalid --seeds range {raw!r}: need 1 <= START <= END"
            )
        return end - start + 1
    try:
        count = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid --seeds {raw!r}: expected a count or 'START-END'"
        ) from None
    if count < 1:
        raise argparse.ArgumentTypeError("--seeds must be positive")
    return count


def _load_deck_or_none(path: Path) -> RulesDeckInput | None:
    resolved = path if path.is_absolute() else Path.cwd() / path
    try:
        return load_deck(resolved)
    except (OSError, ValueError) as exc:
        print(f"cannot load deck {path}: {exc}", file=sys.stderr)
        return None


def _format_delta_line(label: str, deltas: dict[str, int], *, signed: bool = True) -> str:
    if not deltas:
        return f"  {label}: (no change)"
    parts = " ".join(
        f"{color}: {delta:+d}" if signed else f"{color}: {delta}" for color, delta in deltas.items()
    )
    return f"  {label}: {parts}"


def _format_variant(comparison: VariantComparison, index: int, total: int) -> str:
    lines = [
        f"=== Variant {index}/{total}: {comparison.variant_deck_id} ===",
        "Card diff (variant vs baseline):",
    ]
    if not comparison.added and not comparison.removed:
        lines.append("  (no card changes)")
    for name, count in comparison.added:
        lines.append(f"  + {count}x {name}")
    for name, count in comparison.removed:
        lines.append(f"  - {count}x {name}")
    baseline_state = "READY" if comparison.baseline_ready else "NOT READY"
    variant_state = "READY" if comparison.variant_ready else "NOT READY"
    lines.append(f"Readiness: baseline {baseline_state}, variant {variant_state}")
    if comparison.variant_not_ready_cards:
        lines.append("  variant unknown cards: " + ", ".join(comparison.variant_not_ready_cards))
    lines.append("Mana deltas (variant - baseline):")
    lines.append(f"  lands: {comparison.land_count_delta:+d}")
    lines.append(_format_delta_line("colored sources", comparison.colored_source_delta))
    lines.append(f"  flexible sources: {comparison.flexible_source_delta:+d}")
    lines.append(f"  definitely tapped lands: {comparison.definitely_tapped_land_delta:+d}")
    lines.append(f"  conditionally tapped lands: {comparison.conditionally_tapped_land_delta:+d}")
    lines.append(_format_delta_line("T1 untapped sources", comparison.t1_untapped_source_delta))
    turns = ", ".join(f"T{t}" for t in PREFILTER_TURNS)
    lines.append(f"Commander castability, turns {turns} (baseline -> variant, Δ):")
    for cmd in comparison.castability:
        lines.append(f"  {cmd.name}")
        for mode in ("play", "draw"):
            cells = "  ".join(
                f"T{turn} {cmd.baseline_probability[mode][turn]:.3f}"
                f" -> {cmd.variant_probability[mode][turn]:.3f}"
                f" ({cmd.probability_delta[mode][turn]:+.3f})"
                for turn in PREFILTER_TURNS
            )
            lines.append(f"    {mode}: {cells}")
        expected = "  ".join(
            f"{mode} "
            + (
                "never by T10"
                if cmd.baseline_expected_turn[mode] is None
                or cmd.variant_expected_turn[mode] is None
                else f"{cmd.baseline_expected_turn[mode]:.2f}"
                f" -> {cmd.variant_expected_turn[mode]:.2f}"
                f" ({cmd.expected_turn_delta[mode]:+.2f})"
            )
            for mode in ("play", "draw")
        )
        lines.append(f"    expected turn: {expected}")
    lines.append(f"Verdict: {comparison.verdict} — {comparison.verdict_reason}")
    return "\n".join(lines)


def _plan_summary(
    *,
    variant_count: int,
    seeds: int,
    players: int,
    rotate: bool,
    games_per_hour: float,
) -> tuple[str, int, int, float, float]:
    games = (1 + variant_count) * seeds * (players if rotate else 1)
    # Pairs per variant-vs-baseline comparison: each seed x each tested seat.
    pairs = seeds * (players if rotate else 1)
    hours = games / games_per_hour
    detectable = planned_detectable_difference(pairs)
    seats = f"{players} players" if rotate else "no rotation"
    text = (
        f"Planned games: {games} "
        f"((1 baseline + {variant_count} variant(s)) x {seeds} seed(s) x {seats})\n"
        f"Time estimate at {games_per_hour:g} games/hour: {hours:.1f} h\n"
        f"Detectable win-share difference per variant "
        f"(80% power, {pairs} pairs): \u00b1 {detectable:.2f}"
    )
    return text, games, pairs, hours, detectable


def _json_payload(
    baseline: RulesDeckInput,
    comparisons: list[VariantComparison],
    *,
    trials: int,
    seed: int,
    seed_count: int,
    players: int,
    rotate: bool,
    games: int,
    pairs: int,
    hours: float,
    games_per_hour: float,
    detectable: float,
) -> dict[str, Any]:
    return {
        "baseline": {"deck_id": baseline.deck_id, "name": baseline.name},
        "trials": trials,
        "seed": seed,
        "seed_count": seed_count,
        "players": players,
        "rotate": rotate,
        "variants": [comparison_to_dict(item) for item in comparisons],
        "planned_games": games,
        "planned_pairs_per_variant": pairs,
        "games_per_hour": games_per_hour,
        "time_hours": round(hours, 1),
        "detectable_win_share_difference": round(detectable, 3),
    }


def _worst_verdict(comparisons: list[VariantComparison]) -> FilterVerdict:
    if any(item.verdict == VERDICT_BLOCKED for item in comparisons):
        return VERDICT_BLOCKED
    return "WARN" if any(item.verdict == "WARN" for item in comparisons) else "PASS_TO_GAMES"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--baseline", type=Path, required=True, help="baseline deck JSON")
    parser.add_argument(
        "--variant",
        dest="variants",
        type=Path,
        action="append",
        required=True,
        help="variant deck JSON (repeatable)",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=20_000,
        help="Monte Carlo trials for commander castability (default: 20000)",
    )
    parser.add_argument(
        "--seeds",
        default="1-1",
        type=_parse_seeds,
        help="planned game seeds: a count ('25') or inclusive range ('1-25')",
    )
    parser.add_argument("--players", type=int, default=4, help="players per game for planning")
    parser.add_argument(
        "--no-rotate",
        action="store_true",
        help="plan without seat rotation (one seat per seed instead of --players)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--games-per-hour",
        type=float,
        default=DEFAULT_GAMES_PER_HOUR,
        help="host throughput for the time estimate "
        f"(default: {DEFAULT_GAMES_PER_HOUR:g}); measure once on the host",
    )
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be positive")
    if args.players < 1:
        parser.error("--players must be positive")
    if args.games_per_hour <= 0:
        parser.error("--games-per-hour must be positive")
    seed_count: int = args.seeds

    baseline = _load_deck_or_none(args.baseline)
    loaded_variants = [_load_deck_or_none(path) for path in args.variants]
    if baseline is None or any(deck is None for deck in loaded_variants):
        return 2
    variant_decks: list[RulesDeckInput] = [deck for deck in loaded_variants if deck is not None]

    comparisons = [
        compare_variant(baseline, variant, trials=args.trials, seed=DEFAULT_CASTABILITY_SEED)
        for variant in variant_decks
    ]

    rotate = not args.no_rotate
    plan_text, games, pairs, hours, detectable = _plan_summary(
        variant_count=len(comparisons),
        seeds=seed_count,
        players=args.players,
        rotate=rotate,
        games_per_hour=args.games_per_hour,
    )

    if args.json:
        payload = _json_payload(
            baseline,
            comparisons,
            trials=args.trials,
            seed=DEFAULT_CASTABILITY_SEED,
            seed_count=seed_count,
            players=args.players,
            rotate=rotate,
            games=games,
            pairs=pairs,
            hours=hours,
            games_per_hour=args.games_per_hour,
            detectable=detectable,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Deck-variant prefilter (screening before real games — not a ranking)")
        print(f"Baseline: {baseline.deck_id} — {baseline.name}")
        print(f"Trials: {args.trials}, seed: {DEFAULT_CASTABILITY_SEED}")
        print()
        for index, comparison in enumerate(comparisons, start=1):
            print(_format_variant(comparison, index, len(comparisons)))
            print()
        print(plan_text)

    return 1 if _worst_verdict(comparisons) == VERDICT_BLOCKED else 0


if __name__ == "__main__":
    raise SystemExit(main())
