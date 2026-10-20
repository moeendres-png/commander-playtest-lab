#!/usr/bin/env python3
"""Import any Commander decklist into project format.

Supports:
- Plain text list (one card per line, optional quantity prefix: "3x Lightning Bolt" or "3 Lightning Bolt")
- MTGJSON deck format

Usage:
    python scripts/import_deck.py --name "My Deck" --commander "Atraxa, Praetors' Voice" --input deck.txt --output data/decks/custom/my_deck.json
"""

import argparse
import json
import re
import sys
from pathlib import Path


def parse_text_list(text: str) -> list[tuple[str, int]]:
    """Parse a plain text decklist.

    Formats:
        Lightning Bolt
        3x Lightning Bolt
        3 Lightning Bolt
        SB: 2x Negate  (sideboard ignored)
    """
    cards = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("SB:"):
            continue

        # Try "3x Name" or "3 Name"
        m = re.match(r"^(\d+)\s*x?\s+(.+)$", line)
        if m:
            qty = int(m.group(1))
            name = m.group(2).strip()
        else:
            qty = 1
            name = line

        # Skip empty
        if name:
            cards.append((name, qty))

    return cards


def import_deck(
    name: str, commander_names: list[str], cards: list[tuple[str, int]], output: Path
) -> dict:
    """Create project deck format from card list."""

    # Build cards list
    project_cards = []

    # Add commanders first
    for cmd_name in commander_names:
        project_cards.append(
            {
                "oracle_name": cmd_name,
                "quantity": 1,
                "zone": "commander",
                "physical_copy_ids": [],
                "notes": None,
            }
        )

    # Add main deck (excluding commanders to avoid duplicates)
    commander_set = set(commander_names)
    for card_name, qty in cards:
        if card_name in commander_set:
            continue  # Already added as commander
        project_cards.append(
            {
                "oracle_name": card_name,
                "quantity": qty,
                "zone": "main",
                "physical_copy_ids": [],
                "notes": None,
            }
        )

    # Validate total
    total = sum(c["quantity"] for c in project_cards)

    deck = {
        "deck_id": f"custom/{output.stem}",
        "name": name,
        "commander": {
            "commanders": commander_names,
            "uses_partner": len(commander_names) > 1,
            "commander_identity_override": None,
        },
        "cards": project_cards,
        "source": "user_import",
        "total_cards": total,
    }

    # Validate
    if total != 100:
        print(f"WARNING: Deck has {total} cards, expected 100", file=sys.stderr)

    return deck


def main():
    parser = argparse.ArgumentParser(description="Import a Commander decklist")
    parser.add_argument("--name", required=True, help="Deck name")
    parser.add_argument(
        "--commander",
        required=True,
        help="Commander name(s), semicolon-separated for partners (e.g. 'Ishai, Ojutai Dragonspeaker; Rograkh, Son of Rohgahh')",
    )
    parser.add_argument("--input", required=True, type=Path, help="Input file (text list or JSON)")
    parser.add_argument("--output", required=True, type=Path, help="Output JSON path")
    parser.add_argument(
        "--format", choices=["auto", "text", "mtgjson"], default="auto", help="Input format"
    )

    args = parser.parse_args()

    commander_names = [c.strip() for c in args.commander.split(";")]

    # Detect format
    fmt = args.format
    if fmt == "auto":
        fmt = "mtgjson" if args.input.suffix == ".json" else "text"

    # Parse input
    if fmt == "text":
        with open(args.input) as f:
            text = f.read()
        cards = parse_text_list(text)
    elif fmt == "mtgjson":
        with open(args.input) as f:
            data = json.load(f)
        # MTGJSON deck format
        d = data.get("data", data)
        cards = []
        for card in d.get("mainBoard", []):
            cards.append((card.get("name"), card.get("count", 1)))
        # Commander from MTGJSON if not specified
        if not commander_names or commander_names == [""]:
            commander_names = [c.get("name") for c in d.get("commander", [])]
    else:
        print(f"Unknown format: {fmt}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsed {len(cards)} unique cards, {sum(q for _, q in cards)} total")
    print(f"Commander(s): {commander_names}")

    # Create deck
    deck = import_deck(args.name, commander_names, cards, args.output)

    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(deck, f, indent=2)

    print(f"Saved to {args.output}")
    print(f"Total cards: {deck['total_cards']}")


if __name__ == "__main__":
    main()
