#!/usr/bin/env python3
"""Card synergy analysis: which card pairs win together more often than a seat wins on average.

Takes a pilot_decision_report JSON output and finds card pairs with a higher win rate when
one seat casts both cards than the average seat wins.

Usage:
    python scripts/card_synergy_report.py <report.json> [--min-games 5] [--top 20]

Every seat of every finished game is one sample: the cards that seat cast and whether it won.
For each card pair (A, B):
  - P(seat wins | the seat cast A and B) vs P(seat wins) over all samples
  - Synergy score = lift = P(win|A,B) / P(win)
  - Only pairs with >= min_games samples are reported.

This is exploratory deck-building evidence, not qualification evidence: the same decks recur,
so a pair's lift also reflects the deck it sits in, and a card cast late was cast by a seat
that survived long enough to cast it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pilot_report_samples import ok_games


def load_report(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_seat_samples(report: dict) -> list[dict]:
    """One sample per seat of every finished game: its cast cards and whether it won."""
    samples = []
    for game in ok_games(report):
        for seat, cards in game["cards_by_seat"].items():
            samples.append({"won": seat in game["winners"], "cards": cards})
    return samples


def calculate_synergies(
    samples: list[dict], min_games: int = 5
) -> list[tuple[tuple[str, str], float, int, float]]:
    """Calculate synergy scores for card pairs.

    Returns list of (pair, lift, samples_with_both, win_rate_when_together)
    sorted by lift descending.
    """
    if not samples:
        return []

    baseline_rate = sum(1 for s in samples if s["won"]) / len(samples)
    if baseline_rate == 0:
        return []

    pair_counts: dict[tuple[str, str], int] = defaultdict(int)  # seats that cast both
    pair_wins: dict[tuple[str, str], int] = defaultdict(int)  # ... and won

    for sample in samples:
        for pair in combinations(sorted(sample["cards"]), 2):
            pair_counts[pair] += 1
            if sample["won"]:
                pair_wins[pair] += 1

    results = []
    for pair, count in pair_counts.items():
        if count < min_games:
            continue
        win_rate = pair_wins[pair] / count
        results.append((pair, win_rate / baseline_rate, count, win_rate))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Find card synergies from pilot decision report")
    parser.add_argument("report", type=Path, help="Pilot decision report JSON")
    parser.add_argument(
        "--min-games",
        type=int,
        default=5,
        help="Minimum co-occurrences to report (default: 5)",
    )
    parser.add_argument("--top", type=int, default=20, help="Show top N synergies (default: 20)")
    args = parser.parse_args()

    if not args.report.exists():
        print(f"Error: {args.report} not found", file=sys.stderr)
        return 1

    report = load_report(args.report)
    samples = extract_seat_samples(report)

    if not samples:
        print("No valid games found in report", file=sys.stderr)
        return 1

    wins = sum(1 for s in samples if s["won"])
    print(f"Analyzed {len(samples)} seat samples, {wins} won ({wins / len(samples):.1%})")
    print()

    synergies = calculate_synergies(samples, min_games=args.min_games)

    if not synergies:
        print(f"No pairs with >= {args.min_games} co-occurrences found")
        return 0

    print(f"Top {args.top} card synergies (lift vs the average seat win rate):")
    print()
    print(f"{'Card A':<30} {'Card B':<30} {'Lift':>6} {'Seats':>6} {'Win%':>6}")
    print("-" * 84)
    for (a, b), lift, count, win_rate in synergies[: args.top]:
        print(f"{a:<30} {b:<30} {lift:>6.2f} {count:>6} {win_rate:>5.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
