"""Import complete public deck lists (EDHREC deck-index exports, Archidekt API exports).

The input files are the normalized per-deck JSON documents produced by the local fetch
tooling: one file per deck, card names with quantities, and the source's own metadata
(bracket, save/update date, source URL). Nothing here calls a network API; the files are
read from disk, exactly like every other Studio importer.

Each deck becomes one ``corpus_deck`` row (cohort ``chulane``; the commander these lists
were collected for) plus membership rows in ``corpus_cohort`` so deck universes can be
selected by source, bracket and variant (see ``universe.py``). Sections follow the source
data: a card named in the deck's commander list is ``commander``; Archidekt entries whose
categories name a sideboard or maybeboard keep that section, a flagged companion is
``companion``; everything else is ``main``. Category *definitions* of the source platform
(which categories a deck counts as part of itself) are not part of the normalized files,
so section assignment here follows category names only; the source file's own main-deck
total is preserved in the deck tags for reference.

An exact duplicate (same card multiset in the same sections) that is already stored under
another deck id is marked in ``duplicate_of`` instead of being counted twice; the first
imported copy wins. Re-importing the same folder replaces the decks it contains and
leaves every other deck alone. Legality of the imported lists is ``not_audited``: the
importer records what the source published, it does not judge it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .store import DataClass, StudioStore, sha256_file

COMMANDER_COHORT = "chulane"
COMMANDER_NAME = "Chulane, Teller of Tales"


def _merge_rows(rows: list[tuple[str, str, int]]) -> list[tuple[str, str, int]]:
    """One row per (card, section): sources list the same card in several category
    groups of one section (Archidekt splits by category, EDHREC by print run), while
    ``corpus_deck_card`` is keyed by (deck, card, section) — quantities are summed,
    exactly like the corpus part importer merges its rows."""
    merged: dict[tuple[str, str], int] = {}
    for name, section, quantity in rows:
        merged[(name, section)] = merged.get((name, section), 0) + quantity
    return [(name, section, quantity) for (name, section), quantity in sorted(merged.items())]


def _fingerprint(rows: list[tuple[str, str, int]]) -> str:
    digest = hashlib.sha256()
    for card_name, section, quantity in sorted(rows):
        digest.update(f"{card_name}\x00{section}\x00{quantity}\n".encode())
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: expected one JSON object per deck file")
    return raw


def _edhrec_deck(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    urlhash = str(raw.get("urlhash") or path.stem)
    commanders = {str(name) for name in raw.get("commanders", [])}
    rows: list[tuple[str, str, int]] = []
    for card in raw.get("cards", []):
        name = str(card["name"])
        section = "commander" if name in commanders else "main"
        rows.append((name, section, int(card["quantity"])))
    variant = str(raw.get("variante") or "")
    bracket = raw.get("bracket")
    tags = [f"bracket:{bracket}", f"variant:{variant}", f"sum:{raw.get('karten_summe')}"]
    if raw.get("parse_status"):
        tags.append(f"parse:{raw['parse_status']}")
    return {
        "deck_id": f"edhrec:{urlhash}",
        "url": str(raw.get("source_url") or f"https://edhrec.com/deckpreview/{urlhash}"),
        "platform": "edhrec",
        "deck_date": str(raw.get("savedate") or "")[:10] or None,
        "tags": tags,
        "rows": rows,
        "cohorts": [
            "source:edhrec",
            f"bracket:{bracket}",
            f"variant:{variant}",
            f"commander:{COMMANDER_COHORT}",
        ],
        "title": path.name,
    }


def _archidekt_section(card: dict[str, Any]) -> str:
    categories = [str(c).lower() for c in card.get("categories", [])]
    if card.get("companion"):
        return "companion"
    if "commander" in categories:
        return "commander"
    if "sideboard" in categories:
        return "sideboard"
    if "maybeboard" in categories:
        return "maybeboard"
    return "main"


def _archidekt_deck(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    deck_id = str(raw.get("id") or path.stem)
    rows = [
        (str(card["name"]), _archidekt_section(card), int(card["quantity"]))
        for card in raw.get("cards", [])
    ]
    bracket = raw.get("bracket")
    tags = [
        f"bracket:{bracket}",
        f"sum-main:{raw.get('summe_hauptdeck')}",
        f"sum-total:{raw.get('summe_gesamt')}",
    ]
    return {
        "deck_id": f"archidekt:{deck_id}",
        "url": f"https://archidekt.com/decks/{deck_id}",
        "platform": "archidekt",
        "deck_date": str(raw.get("updated_at") or "")[:10] or None,
        "tags": tags,
        "rows": rows,
        "cohorts": [
            "source:archidekt",
            f"bracket:{bracket}",
            f"commander:{COMMANDER_COHORT}",
        ],
        "title": path.name,
    }


_PARSERS = {"edhrec": _edhrec_deck, "archidekt": _archidekt_deck}


def import_decklists(store: StudioStore, folder: str | Path, *, format: str) -> dict[str, int]:
    """Import every normalized deck file of one source format from ``folder``.

    ``format`` is ``edhrec`` or ``archidekt``. Returns counts of decks written, decks
    marked as exact duplicates of an earlier deck, card rows written and files skipped
    because they carried no cards. The whole folder is written in one transaction.
    """
    parser = _PARSERS.get(format)
    if parser is None:
        raise ValueError(f"unknown deck list format: {format!r} (use edhrec or archidekt)")
    files = sorted(Path(folder).glob("*.json"))
    if not files:
        raise ValueError(f"no deck files found in {folder}")
    decks = [parser(_read_json(file), file) for file in files]
    skipped = 0
    with store.connection as db:
        known_fingerprints: dict[str, str] = {
            str(row[0]): str(row[1])
            for row in db.execute("SELECT fingerprint, deck_id FROM corpus_deck")
        }
        written = duplicates = card_rows = 0
        for deck in decks:
            rows = _merge_rows(deck["rows"])
            if not rows:
                skipped += 1
                continue
            fingerprint = _fingerprint(rows)
            # A deck replaced by its own re-import keeps its identity; a deck whose
            # fingerprint another deck already holds is the duplicate.
            duplicate_of = known_fingerprints.get(fingerprint)
            if duplicate_of == deck["deck_id"]:
                duplicate_of = None
            source_id = store.register_source(
                data_class=DataClass.NORMALIZED_SOURCE,
                title=deck["title"],
                sha256=sha256_file(Path(folder) / deck["title"]),
            )
            db.execute(
                "INSERT OR REPLACE INTO corpus_deck(deck_id, cohort, url, platform, "
                "play_group, deck_date, tags, fingerprint, duplicate_of, legality_audit, "
                "source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    deck["deck_id"],
                    COMMANDER_COHORT,
                    deck["url"],
                    deck["platform"],
                    "community",
                    deck["deck_date"],
                    json.dumps(deck["tags"], ensure_ascii=False),
                    fingerprint,
                    duplicate_of,
                    "not_audited",
                    source_id,
                ),
            )
            db.execute("DELETE FROM corpus_deck_card WHERE deck_id = ?", (deck["deck_id"],))
            db.executemany(
                "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, "
                "quantity, normalization_status) VALUES (?, ?, ?, NULL, ?, ?)",
                [
                    (deck["deck_id"], name, section, quantity, "source_name")
                    for name, section, quantity in rows
                ],
            )
            db.execute("DELETE FROM corpus_cohort WHERE deck_id = ?", (deck["deck_id"],))
            db.executemany(
                "INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)",
                [(cohort, deck["deck_id"]) for cohort in deck["cohorts"]],
            )
            known_fingerprints.setdefault(fingerprint, deck["deck_id"])
            written += 1
            card_rows += len(rows)
            duplicates += 1 if duplicate_of else 0
    return {
        "decks": written,
        "duplicates_marked": duplicates,
        "card_rows": card_rows,
        "files_without_cards": skipped,
    }
