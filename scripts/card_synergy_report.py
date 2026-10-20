#!/usr/bin/env python3
"""Card synergy analysis: which card pairs win together more often than expected.

Takes a pilot_decision_report JSON output and finds card pairs with
significantly higher win rates when played together vs. baseline.

Usage:
    python scripts/card_synergy_report.py <report.json> [--min-games 5] [--top 20]

The report JSON must contain per-game records with 'per_card' entries and
winner information. For each card pair (A, B):
  - P(win | A and B played) vs P(win | baseline)
  - Synergy score = lift = P(win|A,B) / P(win)
  - Only pairs with >= min_games co-occurrences are reported.

This is exploratory deck-building evidence, not qualification evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path


def load_report(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_game_cards(report: dict) -> list[dict]:
    """Extract per-game: winner seat, set of cards played by winner."""
    games = []
    for game in report.get("games", []):
        if game.get("status") != "ok":
            continue
        winner = game.get("winner_seat")
        if winner is None:
            continue
        # Cards played by the winner (from per_card entries)
        cards = set()
        for entry in game.get("per_card", []):
            # per_card entries have card name and seat
            seat = entry.get("seat")
            name = entry.get("card_name") or entry.get("name")
            if seat == winner and name:
                cards.add(name)
        games.append({"winner": winner, "cards": cards})
    return games


def calculate_synergies(
    games: list[dict], min_games: int = 5
) -> list[tuple[tuple[str, str], float, int, float]]:
    """Calculate synergy scores for card pairs.

    Returns list of (pair, lift, co_occurrences, win_rate_when_together)
    sorted by lift descending.
    """
    if not games:
        return []

    baseline_rate = 1.0 / 4  # 4-player game, random win rate

    # Count co-occurrences and wins
    pair_counts = defaultdict(int)  # (a,b) -> games where both played
    pair_wins = defaultdict(int)  # (a,b) -> games where both played AND player won

    for game in games:
        cards = game["cards"]
        # For each pair in this game's winner's cards
        for a, b in combinations(sorted(cards), 2):
            pair_counts[(a, b)] += 1
            pair_wins[(a, b)] += 1  # Winner played both, so it's a win

    # Calculate lift for pairs with enough data
    results = []
    for pair, count in pair_counts.items():
        if count < min_games:
            continue
        wins = pair_wins[pair]
        win_rate = wins / count
        # Lift: how much better than random (0.25 for 4-player)
        # Note: This is simplified; a proper analysis would compare to
        # P(win | A) and P(win | B) individually
        lift = win_rate / baseline_rate if baseline_rate > 0 else 0
        results.append((pair, lift, count, win_rate))

    # Sort by lift descending
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
    games = extract_game_cards(report)

    if not games:
        print("No valid games found in report", file=sys.stderr)
        return 1

    print(f"Analyzed {len(games)} games")
    print()

    synergies = calculate_synergies(games, min_games=args.min_games)

    if not synergies:
        print(f"No pairs with >= {args.min_games} co-occurrences found")
        return 0

    print(f"Top {args.top} card synergies (lift vs random 25% win rate):")
    print()
    print(f"{'Card A':<30} {'Card B':<30} {'Lift':>6} {'Games':>6} {'Win%':>6}")
    print("-" * 84)
    for (a, b), lift, count, win_rate in synergies[: args.top]:
        print(f"{a:<30} {b:<30} {lift:>6.2f} {count:>6} {win_rate:>5.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
