"""Build the pilots' public card-knowledge catalog (#732).

A human player knows what the cards in a Commander game do: their types, mana
value, power and toughness, keywords and printed text. The full-game pilots
receive most cards from the engine by name only, so this script collects that
public printed information for every card of the given decks from Scryfall's
public card API and writes it to ``data/cards/pilot_card_knowledge.json``.

The catalog is strategic knowledge for ranking engine-offered options. It is
never a rules authority: XMage alone decides what is legal and what happens.

    python scripts/build_pilot_card_knowledge.py            # the real-deck pod
    python scripts/build_pilot_card_knowledge.py deck.json  # add more decks
    python scripts/build_pilot_card_knowledge.py --names-file names.txt  # one name per line
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.project import load_rules_deck_snapshot

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/cards/pilot_card_knowledge.json"
DEFAULT_DECKS = (
    Path("data/decks/rogshai_current.json"),
    Path("data/decks/opponents/kaervek/current/deck.json"),
    Path("data/opponents/hosts_of_mordor_precon.json"),
    Path("data/opponents/lorehold_spirit_precon.json"),
)
COLLECTION_URL = "https://api.scryfall.com/cards/collection"
BATCH = 75  # Scryfall's documented maximum identifiers per collection request
SCHEMA_VERSION = "pilot-card-knowledge-1.0.0"


def deck_card_names(paths: Iterable[Path]) -> list[str]:
    names: set[str] = set()
    for path in paths:
        deck = load_rules_deck_snapshot(path if path.is_absolute() else ROOT / path)
        names.update(deck.mainboard)
        names.update(deck.commander_names)
    return sorted(names)


def listed_names(path: Path) -> list[str]:
    """Card names of a plain list file; blank lines and '#' comments are skipped."""
    text = (path if path.is_absolute() else ROOT / path).read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def project_card(card: dict[str, Any]) -> dict[str, Any]:
    """Keep only the printed, public facts a pilot ranks with.

    For multi-faced cards the front face describes what is cast or played from
    hand; a split card keeps its full name and combined text.
    """
    faces = card.get("card_faces")
    front = faces[0] if isinstance(faces, list) and faces and "type_line" in faces[0] else card
    layout = str(card.get("layout", "normal"))
    if layout in {"split", "adventure"} and isinstance(faces, list):
        oracle_text = "\n//\n".join(str(face.get("oracle_text", "")) for face in faces)
    else:
        oracle_text = str(front.get("oracle_text", card.get("oracle_text", "")))
    type_line = str(front.get("type_line", card.get("type_line", "")))
    return {
        "name": str(card["name"]),
        "layout": layout,
        "mana_cost": str(front.get("mana_cost", card.get("mana_cost", ""))),
        "mana_value": float(card.get("cmc", 0.0)),
        "type_line": type_line,
        "oracle_text": oracle_text,
        "power": _int_or_none(front.get("power")),
        "toughness": _int_or_none(front.get("toughness")),
        "loyalty": _int_or_none(front.get("loyalty")),
        "keywords": sorted(str(word) for word in card.get("keywords", [])),
        "colors": sorted(str(color) for color in front.get("colors", card.get("colors", []))),
        "color_identity": sorted(str(color) for color in card.get("color_identity", [])),
        "produced_mana": sorted(str(color) for color in card.get("produced_mana", [])),
    }


def fetch_cards(names: Sequence[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    cards: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for start in range(0, len(names), BATCH):
        chunk = names[start : start + BATCH]
        # Scryfall resolves a split card by its first half, not by "A // B".
        identifiers = [{"name": name.split(" // ")[0]} for name in chunk]
        body = json.dumps({"identifiers": identifiers}).encode()
        request = urllib.request.Request(
            COLLECTION_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "commander-playtest-lab/pilot-card-knowledge",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        returned = {str(card["name"]): card for card in payload.get("data", [])}
        for name in chunk:
            card = returned.get(name)
            if card is None:
                # Asked by the front name, a multi-faced card comes back under
                # its full "A // B" name.
                card = next(
                    (
                        value
                        for key, value in returned.items()
                        if key.split(" // ")[0] == name.split(" // ")[0]
                    ),
                    None,
                )
            if card is None:
                missing.append(name)
                continue
            cards[name] = project_card(card)
        time.sleep(0.12)  # Scryfall asks for 50-100 ms between requests
    return cards, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("decks", nargs="*", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--names-file",
        type=Path,
        action="append",
        default=[],
        help="plain card list, one name per line (e.g. the owner collection)",
    )
    args = parser.parse_args(argv)
    existing: dict[str, Any] = {}
    if args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8")).get("cards", {})
    names = sorted(
        set(deck_card_names((*DEFAULT_DECKS, *args.decks)))
        | {name for path in args.names_file for name in listed_names(path)}
    )
    wanted = [name for name in names if name not in existing]
    fetched, missing = fetch_cards(wanted) if wanted else ({}, [])
    cards = {**existing, **fetched}
    document = {
        "schema_version": SCHEMA_VERSION,
        "source": "Scryfall public card API (printed Oracle data)",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": (
            "Public printed card facts the full-game pilots rank engine-offered options "
            "with. Strategic knowledge only; XMage is the sole rules authority."
        ),
        "cards": dict(sorted(cards.items())),
    }
    args.output.write_text(
        json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"{len(cards)} cards ({len(fetched)} fetched); missing: {missing or 'none'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
