"""Build the pilots' public card-knowledge catalog (#732).

A human player knows what the cards in a Commander game do: their types, mana
value, power and toughness, keywords and printed text. The full-game pilots
receive most cards from the engine by name only, so this script collects that
public printed information from local Scryfall bulk data and writes it to
``data/cards/pilot_card_knowledge.json``. The legacy API mode is for explicitly
public card names only; never send private deck or collection data to it.

The catalog is strategic knowledge for ranking engine-offered options. It is
never a rules authority: XMage alone decides what is legal and what happens.

    python scripts/build_pilot_card_knowledge.py --all-cards --bulk-file public.jsonl.gz \\
        --snapshot-at 2026-11-09  # extend from a local public snapshot; retain existing entries
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
import urllib.request
from collections import Counter
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
NON_DECK_LAYOUTS = frozenset(
    {
        "token",
        "double_faced_token",
        "emblem",
        "art_series",
        "planar",
        "scheme",
        "vanguard",
        "reversible_card",
        "front_card",
    }
)


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


def _bulk_records(path: Path) -> Iterable[dict[str, Any]]:
    """Read one public JSON array, JSON object, or JSONL file, optionally gzipped."""
    with path.open("rb") as probe:
        compressed = probe.read(2) == b"\x1f\x8b"
    opener = gzip.open if compressed else open
    with opener(path, "rt", encoding="utf-8") as handle:
        first = next((line for line in handle if line.strip()), "")
        if not first:
            return
        try:
            first_value = json.loads(first)
        except json.JSONDecodeError:
            first_value = None
        handle.seek(0)
        if not isinstance(first_value, dict):
            payload = json.load(handle)
            entries = payload if isinstance(payload, list) else [payload]
            for value in entries:
                if not isinstance(value, dict):
                    raise ValueError("bulk JSON entries must be objects")
                yield value
        else:
            for line in handle:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("bulk JSONL entries must be objects")
                    yield value


def load_bulk(
    paths: Sequence[Path], skipped: Counter[str] | None = None
) -> dict[str, dict[str, Any]]:
    """Project English paper Commander-eligible cards, rejecting ambiguous identities."""
    by_id: dict[str, dict[str, Any]] = {}
    name_ids: dict[str, str] = {}
    record_count = 0
    exclusions: Counter[str] = Counter()
    for path in paths:
        for card in _bulk_records(path):
            record_count += 1
            if not isinstance(card.get("lang"), str) or not card["lang"]:
                raise ValueError("bulk record must have a language")
            if card.get("lang") != "en":
                exclusions["non_english"] += 1
                continue
            layout = card.get("layout")
            if not isinstance(layout, str) or not layout:
                raise ValueError("bulk record must have a layout")
            if layout in NON_DECK_LAYOUTS:
                exclusions[f"layout:{layout}"] += 1
                continue
            games = card.get("games")
            if not isinstance(games, list) or not all(isinstance(game, str) for game in games):
                raise ValueError("bulk record must have a games list")
            if "paper" not in games:
                exclusions["non_paper"] += 1
                continue
            legalities = card.get("legalities")
            commander = legalities.get("commander") if isinstance(legalities, dict) else None
            if commander == "not_legal":
                exclusions["commander_not_legal"] += 1
                continue
            if commander not in {"legal", "banned", "restricted"}:
                exclusions["commander_unknown"] += 1
                continue
            oracle_id, name = card.get("oracle_id"), card.get("name")
            if (
                not isinstance(oracle_id, str)
                or not oracle_id
                or not isinstance(name, str)
                or not name
            ):
                raise ValueError("English bulk record must have an oracle_id and name")
            projected = project_card(card)
            if oracle_id in by_id and by_id[oracle_id] != projected:
                raise ValueError("conflicting English printings for an Oracle identity")
            if name in name_ids and name_ids[name] != oracle_id:
                raise ValueError("one English name maps to multiple Oracle identities")
            by_id[oracle_id] = projected
            name_ids[name] = oracle_id
    if not record_count or not by_id:
        raise ValueError("bulk input contains no English Oracle records")
    if skipped is not None:
        skipped.update(exclusions)
    return {name: by_id[oracle_id] for name, oracle_id in sorted(name_ids.items())}


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("decks", nargs="*", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--bulk-file",
        type=Path,
        action="append",
        default=[],
        help="local public JSON, JSONL, or gzipped bulk file; may be repeated",
    )
    parser.add_argument(
        "--all-cards",
        action="store_true",
        help="extend English paper cards legal, banned, or restricted in Commander; exclude non-deck layouts, without reading deck or name lists",
    )
    parser.add_argument(
        "--snapshot-at", help="caller-declared bulk snapshot date or ISO-8601 timestamp"
    )
    parser.add_argument(
        "--snapshot-description", help="caller-declared provenance of local bulk parts"
    )
    parser.add_argument(
        "--public-api",
        action="store_true",
        help="explicitly allow network lookup of supplied public names only",
    )
    parser.add_argument(
        "--names-file",
        type=Path,
        action="append",
        default=[],
        help="plain card list, one name per line; use --bulk-file for private lists",
    )
    args = parser.parse_args(argv)
    if args.all_cards and (not args.bulk_file or args.decks or args.names_file):
        parser.error("--all-cards requires --bulk-file and excludes decks and --names-file")
    if (args.snapshot_at or args.snapshot_description) and not args.bulk_file:
        parser.error("snapshot provenance requires --bulk-file")
    if args.public_api and args.bulk_file:
        parser.error("--public-api cannot be combined with --bulk-file")
    if not args.bulk_file and (not args.public_api or not (args.decks or args.names_file)):
        parser.error(
            "provide --bulk-file, or --public-api with explicit public deck or name inputs"
        )
    if args.snapshot_at:
        try:
            datetime.fromisoformat(args.snapshot_at.replace("Z", "+00:00"))
        except ValueError:
            parser.error("--snapshot-at must be an ISO-8601 date or timestamp")
    existing_doc: dict[str, Any] = {}
    prior_sha256 = None
    if args.output.exists():
        prior_sha256 = _sha256(args.output)
        existing_doc = json.loads(args.output.read_text(encoding="utf-8"))
    if not isinstance(existing_doc, dict):
        raise ValueError("existing catalog must be an object")
    existing = existing_doc.get("cards", {})
    if not isinstance(existing, dict):
        raise ValueError("existing catalog must contain a cards object")
    skipped: Counter[str] = Counter()
    bulk = load_bulk(args.bulk_file, skipped) if args.bulk_file else {}
    if args.all_cards:
        fetched = {name: value for name, value in bulk.items() if name not in existing}
        missing: list[str] = []
    else:
        names = sorted(
            set(deck_card_names((*DEFAULT_DECKS, *args.decks) if args.bulk_file else args.decks))
            | {name for path in args.names_file for name in listed_names(path)}
        )
        wanted = [name for name in names if name not in existing]
        if args.bulk_file:
            by_front: dict[str, list[dict[str, Any]]] = {}
            for name, card in bulk.items():
                by_front.setdefault(name.split(" // ")[0], []).append(card)
            fetched = {}
            missing = []
            for name in wanted:
                matches = by_front.get(name.split(" // ")[0], [])
                card = bulk.get(name)
                if card is None and " // " not in name and len(matches) == 1:
                    card = matches[0]
                if card is None:
                    missing.append(name)
                else:
                    fetched[name] = card
        else:
            fetched, missing = fetch_cards(wanted) if wanted else ({}, [])
    cards = {**fetched, **existing}
    document = {
        **existing_doc,
        "schema_version": SCHEMA_VERSION,
        "source": existing_doc.get(
            "source",
            "Scryfall public printed Oracle data"
            if args.bulk_file
            else "Scryfall public card API (printed Oracle data)",
        ),
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": existing_doc.get(
            "purpose",
            (
                "Public printed card facts the full-game pilots rank engine-offered options "
                "with. Strategic knowledge only; XMage is the sole rules authority."
            ),
        ),
        "cards": dict(sorted(cards.items())),
    }
    if args.bulk_file:
        document["source"] = (
            "Retained catalog and local Scryfall bulk snapshot (printed Oracle data)"
            if existing
            else "Local Scryfall bulk snapshot (printed Oracle data)"
        )
        document["bulk_refresh"] = {
            "inputs": sorted(
                ({"file": path.name, "sha256": _sha256(path)} for path in args.bulk_file),
                key=lambda x: (x["file"], x["sha256"]),
            ),
            "declared_snapshot_at": args.snapshot_at,
            "declared_snapshot_description": args.snapshot_description,
            "source_documentation_url": "https://scryfall.com/docs/api/bulk-data",
            "retained_catalog_sha256": prior_sha256,
            "retained_catalog_generated_at": existing_doc.get("generated_at"),
            "retained_catalog_source": existing_doc.get("source"),
            "existing_entries_retained": len(existing),
            "scope": "English paper cards with legal, banned, or restricted Commander status; non-deck layouts excluded",
            "skipped_records": dict(sorted(skipped.items())),
        }
    args.output.write_text(
        json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"{len(cards)} cards ({len(fetched)} added); {len(missing)} missing; {sum(skipped.values())} filtered records"
    )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
