#!/usr/bin/env python3
"""Print the pilot mulligan keep-rate table for a deck (#850).

Measures what share of seeded random 7-card opening hands the pilot keeps,
broken down by land count, plus the overall keep rate and the expected number
of mulligans before keeping (free first mulligan, forced keep after 3).

    python scripts/mulligan_keep_table.py --deck data/decks/rogshai_current.json
    python scripts/mulligan_keep_table.py --deck FILE --hands 4000 --seed 7 \\
        --strength average --mode deterministic

Exit code 0 on success.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.full_game_pilot_views import card_view_fields
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import (
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
)

HAND_SIZE = 7
MAX_MULLIGANS = 3  # rules core forces a keep after 3 mulligans


def _hand_views(names: list[str]) -> list[PilotActionView]:
    """One PilotActionView per card, exactly like _hand_action in state.py."""
    return [
        PilotActionView(
            action_id=f"hand-{index}",
            action_kind="card",
            card_name=name,
            floor_value=0.5,
            immediate_impact=0.3,
            **card_view_fields(name),
        )
        for index, name in enumerate(names)
    ]


def _land_count(views: list[PilotActionView]) -> int:
    return sum(bool(view.metadata.get("is_land", False)) for view in views)


def keep_table(
    *,
    deck_path: Path,
    hands: int,
    seed: int,
    strength: PilotStrength,
    mode: PilotDecisionMode,
) -> dict[str, object]:
    deck = load_rules_deck_snapshot(deck_path)
    library = list(deck.mainboard)
    if len(library) < HAND_SIZE:
        raise ValueError(f"deck library has only {len(library)} cards")
    pilot = build_pilot(PilotConfig(strength=strength, mode=mode), strategy="generic")
    draw_rng = random.Random(seed)
    decide_rng = random.Random(seed)

    kept = [0] * (HAND_SIZE + 1)
    total = [0] * (HAND_SIZE + 1)
    mulligans_taken = 0
    for _ in range(hands):
        hand = draw_rng.sample(library, HAND_SIZE)
        views = _hand_views(hand)
        keep, _ = pilot.should_keep_opening_hand(
            views,
            mulligans=0,
            free_first=True,
            commander_names=deck.commander_names,
            rng=decide_rng,
        )
        total[_land_count(views)] += 1
        if keep:
            kept[_land_count(views)] += 1
            continue
        # Mulligan chain: fresh 7-card hand, forced keep after 3 mulligans.
        taken = 0
        for mulligans in range(1, MAX_MULLIGANS + 1):
            hand = draw_rng.sample(library, HAND_SIZE)
            views = _hand_views(hand)
            keep, _ = pilot.should_keep_opening_hand(
                views,
                mulligans=mulligans,
                free_first=True,
                commander_names=deck.commander_names,
                rng=decide_rng,
            )
            taken = mulligans
            if keep:
                break
        mulligans_taken += taken

    total_kept = sum(kept)
    return {
        "deck": str(deck_path),
        "hands": hands,
        "seed": seed,
        "strength": strength.value,
        "mode": mode.value,
        "by_lands": [
            {"lands": n, "hands": total[n], "kept": kept[n]} for n in range(HAND_SIZE + 1)
        ],
        "overall_keep_rate": total_kept / hands if hands else 0.0,
        "expected_mulligans": mulligans_taken / hands if hands else 0.0,
    }


def format_table(report: dict[str, object]) -> str:
    lines = [
        f"deck: {report['deck']}",
        f"strength: {report['strength']}, mode: {report['mode']}, "
        f"hands: {report['hands']}, seed: {report['seed']}, free_first: True",
        "",
        "| lands | hands | kept |",
        "|-------|-------|------|",
    ]
    for row in report["by_lands"]:  # type: ignore[union-attr]
        hands = row["hands"]
        rate = row["kept"] / hands if hands else 0.0
        lines.append(f"| {row['lands']}     | {hands:<5} | {rate:5.1%} |")
    lines.append("")
    lines.append(f"overall keep rate: {report['overall_keep_rate']:.1%}")  # type: ignore[str-format]
    lines.append(f"expected mulligans: {report['expected_mulligans']:.2f}")  # type: ignore[str-format]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck", type=Path, required=True, help="Rules deck snapshot JSON")
    parser.add_argument("--hands", type=int, default=4000, help="Seeded 7-card hands to draw")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed (deterministic)")
    parser.add_argument(
        "--strength",
        type=str,
        default=PilotStrength.AVERAGE.value,
        choices=[strength.value for strength in PilotStrength],
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=PilotDecisionMode.DETERMINISTIC.value,
        choices=[mode.value for mode in PilotDecisionMode],
    )
    args = parser.parse_args(argv)
    report = keep_table(
        deck_path=args.deck,
        hands=args.hands,
        seed=args.seed,
        strength=PilotStrength(args.strength),
        mode=PilotDecisionMode(args.mode),
    )
    print(format_table(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
