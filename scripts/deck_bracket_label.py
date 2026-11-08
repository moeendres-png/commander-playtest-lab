#!/usr/bin/env python3
"""Print the Game Changers and Commander bans of a deck file (E11). A label, not a bracket rule.

    python scripts/deck_bracket_label.py data/decks/some_deck.json

Reads the committed data/cards/commander_flags.json and the deck file; nothing is sent anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commander_lab.cards.commander_flags import label_deck  # noqa: E402
from commander_lab.engine.rules.project import load_rules_deck_snapshot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("deck", type=Path)
    args = parser.parse_args(argv)
    deck = load_rules_deck_snapshot(args.deck)
    label = label_deck((*deck.commander_names, *deck.mainboard, *deck.sideboard))
    print(json.dumps(label.as_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
