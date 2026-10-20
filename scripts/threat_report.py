#!/usr/bin/env python3
"""Threat analysis: which opponent cards correlate with losses.

Takes a pilot_decision_report JSON output and finds opponent cards that
appear disproportionately often in games the pilot lost.

Usage:
    python scripts/threat_report.py <report.json> [--min-games 5] [--top 20]

For each opponent card:
  - P(loss | opponent played card) vs baseline loss rate
  - Threat score = lift = P(loss|card) / P(loss)
  - Only cards with >= min_games appearances are reported.

This helps tune removal: high-threat cards are priority targets.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_report(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_threats(report: dict, pilot_seat: int = 0) -> list[dict]:
    """Extract per-game: did pilot lose, which opponent cards were played."""
    games = []
    for game in report.get("games", []):
        if game.get("status") != "ok":
            continue
        winner = game.get("winner_seat")
        if winner is None:
            continue
        pilot_lost = winner != pilot_seat
        # Opponent cards (not pilot's seat)
        opp_cards = set()
        for entry in game.get("per_card", []):
            seat = entry.get("seat")
            name = entry.get("card_name") or entry.get("name")
            if seat != pilot_seat and seat is not None and name:
                opp_cards.add(name)
        games.append({"pilot_lost": pilot_lost, "opp_cards": opp_cards})
    return games


def calculate_threats(games: list[dict], min_games: int = 5) -> list[tuple[str, float, int, float]]:
    """Calculate threat scores for opponent cards.

    Returns list of (card, lift, appearances, loss_rate_when_played)
    sorted by lift descending.
    """
    if not games:
        return []

    total_games = len(games)
    total_losses = sum(1 for g in games if g["pilot_lost"])
    baseline_loss_rate = total_losses / total_games if total_games > 0 else 0

    if baseline_loss_rate == 0:
        return []

    # Count appearances and losses per card
    card_appearances = defaultdict(int)
    card_losses = defaultdict(int)

    for game in games:
        for card in game["opp_cards"]:
            card_appearances[card] += 1
            if game["pilot_lost"]:
                card_losses[card] += 1

    # Calculate lift
    results = []
    for card, appearances in card_appearances.items():
        if appearances < min_games:
            continue
        losses = card_losses[card]
        loss_rate = losses / appearances
        lift = loss_rate / baseline_loss_rate if baseline_loss_rate > 0 else 0
        results.append((card, lift, appearances, loss_rate))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Find opponent cards that correlate with losses")
    parser.add_argument("report", type=Path, help="Pilot decision report JSON")
    parser.add_argument(
        "--min-games",
        type=int,
        default=5,
        help="Minimum appearances to report (default: 5)",
    )
    parser.add_argument("--top", type=int, default=20, help="Show top N threats (default: 20)")
    parser.add_argument(
        "--pilot-seat",
        type=int,
        default=0,
        help="Pilot's seat number (default: 0)",
    )
    args = parser.parse_args()

    if not args.report.exists():
        print(f"Error: {args.report} not found", file=sys.stderr)
        return 1

    report = load_report(args.report)
    games = extract_threats(report, pilot_seat=args.pilot_seat)

    if not games:
        print("No valid games found in report", file=sys.stderr)
        return 1

    losses = sum(1 for g in games if g["pilot_lost"])
    print(f"Analyzed {len(games)} games, pilot lost {losses} ({losses / len(games):.1%})")
    print()

    threats = calculate_threats(games, min_games=args.min_games)

    if not threats:
        print(f"No cards with >= {args.min_games} appearances found")
        return 0

    print(f"Top {args.top} threat cards (lift vs baseline loss rate):")
    print()
    print(f"{'Card':<40} {'Lift':>6} {'Games':>6} {'Loss%':>6}")
    print("-" * 60)
    for card, lift, count, loss_rate in threats[: args.top]:
        print(f"{card:<40} {lift:>6.2f} {count:>6} {loss_rate:>5.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
