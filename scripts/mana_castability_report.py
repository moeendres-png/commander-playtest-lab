"""Commander castability report: P(commander castable by turn N) via seeded Monte Carlo (#833).

Loads a deck snapshot with the same loader the deck-comparison script uses
(``load_rules_deck_snapshot``), resolves it to a structural profile (project
manifest when the deck id is known, XMage card facts otherwise), and prints one
table per commander with the play/draw cast probabilities for turns 2..10 plus
the expected earliest castable turn.

Example:

    PYTHONPATH=src python scripts/mana_castability_report.py \\
        --deck data/decks/rogshai_current.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from commander_lab.deck_profile import ROOT, load_deck, structural_profile
from commander_lab.mana_analysis import (
    DEFAULT_CASTABILITY_SEED,
    CommanderCastability,
    ManaAnalyzer,
)
from commander_lab.models import RulesDeckInput, StructuralDeckProfile


def _json_payload(
    deck: RulesDeckInput,
    profile: StructuralDeckProfile,
    source: str,
    result: CommanderCastability,
    *,
    trials: int,
) -> dict[str, object]:
    """One JSON document with the same numbers the text tables print (#844)."""
    return {
        "deck_id": deck.deck_id,
        "name": deck.name,
        "structural_profile_source": source,
        "trials": trials,
        "seed": DEFAULT_CASTABILITY_SEED,
        "probability": {
            name: {
                mode: {str(turn): result.probability[name][mode][turn] for turn in range(2, 11)}
                for mode in ("play", "draw")
            }
            for name in profile.commander_names
        },
        "expected_turn": {
            name: {mode: result.expected_turn[name][mode] for mode in ("play", "draw")}
            for name in profile.commander_names
        },
    }


def _commander_line(profile: StructuralDeckProfile, name: str) -> str:
    card = next(card for card in profile.cards if card.oracle_name == name)
    pips = ", ".join(
        f"{color.value}:{count}"
        for color, count in sorted(card.color_requirements.items(), key=lambda item: item[0].value)
    )
    return f"{name} (MV {card.mana_value:g}, pips {{{pips}}})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--deck", type=Path, required=True, help="rules deck snapshot JSON")
    parser.add_argument(
        "--trials",
        type=int,
        default=20_000,
        help="Monte Carlo trials (default: 20000)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be positive")

    deck_path = args.deck if args.deck.is_absolute() else Path.cwd() / args.deck
    deck = load_deck(deck_path)
    profile, source = structural_profile(deck)
    analyzer = ManaAnalyzer(ROOT)
    result = analyzer.commander_castability(profile, trials=args.trials)

    if args.json:
        payload = _json_payload(deck, profile, source, result, trials=args.trials)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(f"Deck: {deck.deck_id} — {deck.name}")
    print(f"Structural profile: {source}")
    print(f"Trials: {args.trials}, seed: {DEFAULT_CASTABILITY_SEED}")
    print()
    for name in profile.commander_names:
        print(f"Commander: {_commander_line(profile, name)}")
        header = "mode  " + "  ".join(f"T{t:<5d}" for t in range(2, 11))
        print(header)
        for mode in ("play", "draw"):
            row = "  ".join(f"{result.probability[name][mode][t]:<7.3f}" for t in range(2, 11))
            print(f"{mode:<6}{row}")
        expected = result.expected_turn[name]
        play = f"{expected['play']:.2f}" if expected["play"] is not None else "never by T10"
        draw = f"{expected['draw']:.2f}" if expected["draw"] is not None else "never by T10"
        print(f"expected earliest castable turn: play {play}, draw {draw}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
