#!/usr/bin/env python3
"""Add the Oracle data of named cards to data/cards/oracle_subset.json, on demand (#877).

The catalog is a subset on purpose: the cards of the current decks and a few fixtures. The deck
overlays (data/decks/*_card_catalog_overrides.json) are loaded next to it, so their cards count as
known and are not imported again. A card is added when a deck or a comparison needs it, with its
Oracle data from Scryfall. Nothing is imported in bulk and a card the catalog already knows (by name or alias) is never touched.

    python scripts/import_oracle_cards.py deck.json                 # the deck's missing cards
    python scripts/import_oracle_cards.py --name "Mind Stone" --name "Sol Ring"
    python scripts/import_oracle_cards.py --names-file names.txt    # one name per line
    python scripts/import_oracle_cards.py deck.json --dry-run       # print, write nothing

Importing a card does not make it playable: the engine facts (``xmage_card_facts.json``) and
the fork decide that, see ``scripts/deck_readiness.py``. Names in ``--names-file`` end up in a
committed file; do not pass a list of the Owner's collection unless the Owner asked for it.
Exit 0 when every wanted card is in the catalog afterwards, 1 when Scryfall did not know one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commander_lab.cards.normalize import oracle_lookup_key  # noqa: E402
from commander_lab.engine.rules.project import load_rules_deck_snapshot  # noqa: E402

CATALOG = ROOT / "data/cards/oracle_subset.json"
COLLECTION_URL = "https://api.scryfall.com/cards/collection"
BATCH = 75  # Scryfall's documented maximum identifiers per collection request
#: Deck-specific rows that the tools load on top of the catalog (local_snapshots, service_core).
OVERLAY_GLOB = "data/decks/*_card_catalog_overrides.json"
SCOPE_SENTENCE = (
    " Cards added on demand with scripts/import_oracle_cards.py carry their Scryfall provenance;"
    " being in the catalog is not a promise that the engine implements them."
)


def _faces(card: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    faces = card.get("card_faces")
    return list(faces) if faces else [card]


def _is_commander(card: Mapping[str, Any]) -> bool:
    front = _faces(card)[0]
    type_line = front.get("type_line") or card.get("type_line") or ""
    text = " ".join(face.get("oracle_text") or "" for face in _faces(card))
    return ("Legendary" in type_line and "Creature" in type_line) or (
        "can be your commander" in text
    )


def entry_from_scryfall(
    card: Mapping[str, Any], *, retrieved_at: str, source_url: str
) -> dict[str, Any]:
    """One catalog entry from a Scryfall card object.

    A card with several faces (split, adventure, transform, modal) keeps the front face's cost
    (the drift report compares one face's cost); mana value and colours are the card's own when
    Scryfall gives them on the card, as it does for a split card whose halves share one face,
    and the front face's otherwise. Its text is every face, joined by a line that is exactly
    ``//``. The alias is the front-face name, and only that: a face name two cards share would
    make the catalog ambiguous.
    """
    name = str(card["name"])
    front = _faces(card)[0]
    front_name = str(front.get("name") or name)
    cost = front.get("cmc", card.get("cmc"))
    type_line = str(card.get("type_line") or front.get("type_line") or "Unknown")
    is_basic = "Basic Land" in type_line
    text = "\n//\n".join(str(face.get("oracle_text") or "") for face in _faces(card))
    partner = re.findall(r"Partner with ([^\n(]+)", text)
    return {
        "oracle_name": name,
        "oracle_id": card["oracle_id"],
        "aliases": [front_name] if front_name != name else [],
        "mana_cost": front.get("mana_cost") or card.get("mana_cost") or None,
        "mana_value": float(cost) if cost is not None else None,
        "colors": list(front.get("colors") or card.get("colors") or []),
        "color_identity": list(card.get("color_identity") or []),
        "type_line": type_line,
        "oracle_text": text,
        "keywords": list(card.get("keywords") or []),
        "can_be_commander": _is_commander(card),
        "partner_with": [item.strip() for item in partner],
        "legalities": {"commander": (card.get("legalities") or {}).get("commander", "unknown")},
        "is_basic_land": is_basic,
        "max_deck_copies": None if is_basic else 1,
        "data_quality": "authoritative",
        "provenance": [
            {
                "source_type": "scryfall_api",
                "source_name": "Scryfall cards/collection (on-demand import)",
                "source_path": source_url,
                "retrieved_at": retrieved_at,
                "data_as_of": retrieved_at,
                "quality": "authoritative",
                "notes": "Oracle fields as returned by Scryfall for this card.",
            }
        ],
    }


def known_keys(catalog: Mapping[str, Any]) -> set[str]:
    return {
        oracle_lookup_key(name)
        for card in catalog["cards"]
        for name in (card["oracle_name"], *card.get("aliases", []))
    }


def default_overlays(catalog_path: Path) -> list[Path]:
    """The deck overlays that belong to the repository catalog; none for any other file."""
    if catalog_path.resolve() != CATALOG.resolve():
        return []
    return sorted(ROOT.glob(OVERLAY_GLOB))


def overlay_keys(paths: Iterable[Path]) -> set[str]:
    """Names and aliases of the overlay rows. The tools read them next to the catalog, and a card
    present in both with another representation is a "duplicate conflicting card identity"."""
    out: set[str] = set()
    for path in paths:
        out |= known_keys(json.loads(path.read_text(encoding="utf-8")))
    return out


def missing_names(
    catalog: Mapping[str, Any], wanted: Iterable[str], extra_known: Iterable[str] = ()
) -> list[str]:
    """The wanted names neither the catalog nor an overlay knows, in input order, no repeats."""
    known = known_keys(catalog) | set(extra_known)
    out: list[str] = []
    seen: set[str] = set()
    for name in wanted:
        key = oracle_lookup_key(name)
        if key in known or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def merged_catalog(catalog: Mapping[str, Any], entries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The catalog with the entries added, sorted by name; the scope text says so once."""
    out = dict(catalog)
    out["cards"] = sorted([*catalog["cards"], *entries], key=lambda card: card["oracle_name"])
    scope = str(out.get("catalog_scope") or "")
    if entries and SCOPE_SENTENCE.strip() not in scope:
        out["catalog_scope"] = scope + SCOPE_SENTENCE
    return out


def fetch_cards(names: Sequence[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Scryfall card objects for the names (a card with several faces is asked for by its front name)."""
    found: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for start in range(0, len(names), BATCH):
        chunk = list(names[start : start + BATCH])
        identifiers = [{"name": name.split(" // ")[0]} for name in chunk]
        request = urllib.request.Request(
            COLLECTION_URL,
            data=json.dumps({"identifiers": identifiers}).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "commander-playtest-lab/import-oracle-cards",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        returned = {oracle_lookup_key(str(card["name"])): card for card in payload.get("data", [])}
        by_front = {key.split(" // ")[0]: card for key, card in returned.items()}
        for name in chunk:
            key = oracle_lookup_key(name)
            card = returned.get(key) or by_front.get(key.split(" // ")[0])
            if card is None:
                missing.append(name)
            else:
                found[name] = card
        time.sleep(0.12)  # Scryfall asks for 50-100 ms between requests
    return found, missing


def wanted_names(
    decks: Iterable[Path], names: Iterable[str], names_files: Iterable[Path]
) -> list[str]:
    out = list(names)
    for path in names_files:
        out.extend(
            line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    for path in decks:
        deck = load_rules_deck_snapshot(path)
        out.extend((*deck.commander_names, *deck.mainboard, *deck.sideboard))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "decks", nargs="*", type=Path, help="deck JSON files; their missing cards are added"
    )
    parser.add_argument("--name", action="append", default=[], help="one card name (repeatable)")
    parser.add_argument(
        "--names-file", type=Path, action="append", default=[], help="one name per line"
    )
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument(
        "--overlay",
        type=Path,
        action="append",
        default=None,
        help="deck overlay whose cards count as known (default: the repository's deck overlays "
        "when --catalog is the repository catalog)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print what would be added, write nothing"
    )
    args = parser.parse_args(argv)
    if not (args.decks or args.name or args.names_file):
        parser.error("give a deck file, --name or --names-file")

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    overlaid = overlay_keys(
        args.overlay if args.overlay is not None else default_overlays(args.catalog)
    )
    todo = missing_names(catalog, wanted_names(args.decks, args.name, args.names_file), overlaid)
    if not todo:
        print("every wanted card is already in the catalog or its deck overlay")
        return 0
    if args.dry_run:
        print(f"would fetch {len(todo)} card(s): {', '.join(todo)}")
        return 0

    found, missing = fetch_cards(todo)
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entries: dict[str, dict[str, Any]] = {}
    for card in found.values():
        entry = entry_from_scryfall(card, retrieved_at=now, source_url=COLLECTION_URL)
        entries.setdefault(entry["oracle_id"], entry)  # two asked names can be one card
    fresh = [
        e
        for e in entries.values()
        if oracle_lookup_key(e["oracle_name"]) not in known_keys(catalog) | overlaid
    ]
    if fresh:
        args.catalog.write_text(
            json.dumps(merged_catalog(catalog, fresh), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(
        f"added {len(fresh)} card(s): {', '.join(sorted(e['oracle_name'] for e in fresh)) or 'none'}"
    )
    if missing:
        print(f"Scryfall does not know: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
