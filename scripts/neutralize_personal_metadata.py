#!/usr/bin/env python3
"""Strip personal metadata from tracked collection, deck and provenance data.

The collection stays one flat card list and decks keep their cards and structure;
what goes is everything that only describes people or purchases: personal names,
per-person storage boxes, purchase dates, sellers, offer ids and product origins.

Usage: ``python3 scripts/neutralize_personal_metadata.py [--check]``.
``--check`` exits non-zero when a target file still carries such metadata.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Keys that only record who stores a card where or how it was bought.
DROPPED_KEYS = frozenset(
    {"box", "box_or_location", "box_or_source", "source_category", "origin", "product"}
)
# Purchase states that are not part of the collection model (PurchaseStatus).
DROPPED_PURCHASE_STATES = frozenset({"owned_legacy", "arrived"})

# Ordered literal rewrites for names inside free text.
TEXT_REWRITES: tuple[tuple[str, str], ...] = (
    ("Moritz Endres / project files", "Owner / project files"),
    ("Moritz Endres", "Owner"),
    ("Kaervek – Leon", "Kaervek"),
    ("Alen – High Perfect Morcant", "High Perfect Morcant"),
    ("Alen's Morcant Elves", "Morcant Elves"),
    ("Alen Morcant", "Morcant"),
    ("Path und Gaze physisch von Moritz übergeben", "Path und Gaze aus der Sammlung"),
    ("while stored in Alens Box", "while it is in the collection"),
    (" (Leons Box)", ""),
    ("from Leons Box added", "from the collection added"),
    ("Warstorm Surge from Leons Box.", "Warstorm Surge from the collection."),
    ("1× historisch an Alen abgegeben", "1× historisch abgegeben"),
    ('hostname="MoritzPC"', 'hostname="localhost"'),
)
# "lokal: <workbook>; Zeilen <sheet>!<row> | " prefixes name a person's box sheet.
LOCAL_ROW_SOURCE = re.compile(r"lokal: [^|]*\| ")
# Free-text source notes that record purchases, sellers or a person's box.
PERSONAL_SOURCE_NOTE = re.compile(r"Nutzerangabe|Kauf|Cardmarket|Box|Goodies")

JSON_TARGETS = (
    "data/canonical_import/2026-08-07/inventory.json",
    "data/canonical_import/2026-08-07/opponents.json",
    "data/collections/current_deck_allocations.json",
    "data/collections/current/J_P5_DECK_BUILD_CONSTRAINTS_CURRENT.json",
    "data/decks/opponents/kaervek/current/deck.json",
    "data/decks/opponents/kaervek/current/provenance.json",
    "data/provenance/kaervek_current_sync.json",
    "data/enrichment/ORACLE_FACT_COMPLETENESS_CLOSURE_2026-08-15.json",
    "data/opponents/current_structural_profiles.json",
    "data/rules/card_rules_coverage.json",
    "data/rules/unsupported_card_register.json",
    "data/meta/provenance/meta-2026-08-05-phase12-1-sources.json",
    "data/meta/provenance/meta-2026-08-13-whole-deck-phase2-1-sources.json",
    "data/meta/provenance/meta_seed_sources.json",
    "data/meta/snapshots/meta-2026-08-05-phase12-1.json",
    "data/meta/snapshots/meta-2026-08-13-whole-deck-phase2-1.json",
    "data/provenance/provenance_graph.json",
    "data/provenance/source_registry.json",
    "docs/meta/META_KNOWLEDGE_BASE_SNAPSHOT.json",
    "docs/meta/META_KNOWLEDGE_BASE_SOURCES.json",
    "artifacts/meta_knowledge_base/META_KNOWLEDGE_BASE_SNAPSHOT.json",
    "artifacts/meta_knowledge_base/META_KNOWLEDGE_BASE_SOURCES.json",
    "artifacts/phase12_14/CARD_RULES_COVERAGE.json",
    "artifacts/phase12_14/PHASE12_14_RESULT.json",
    "artifacts/phase12_14/UNSUPPORTED_CARD_REGISTER.json",
    "artifacts/phase12_20/final_package/CARD_RULES_COVERAGE.json",
)
TEXT_TARGETS = (
    "CHANGELOG.md",
    "artifacts/phase12_15/PHASE12_15_REPORT.md",
    "docs/archive/b8_takeover_20261003/GREEN-progress.xml",
    "docs/archive/b8_takeover_20261003/RED-progress.xml",
    "docs/archive/ci479_review_pr513_20261003/B12-review-GREEN.xml",
    "docs/archive/ci479_review_pr513_20261003/B12-review-RED.xml",
    "docs/archive/ci479_review_pr518_20261003/B8-review-GREEN.xml",
    "docs/archive/ci479_review_pr518_20261003/B8-review-RED.xml",
    "docs/archive/ci479_review_pr519_20261003/B10-review-GREEN.xml",
)

# Anything still matching this after neutralization is a leak.
LEAK = re.compile(
    r"Moritz|Endres|\bLeons?\b|\bAlens?\b|s Box\b|Kartenkauf|Cardmarket|Einzelkauf|Altbestand"
)


def rewrite_text(value: str) -> str:
    for old, new in TEXT_REWRITES:
        value = value.replace(old, new)
    return LOCAL_ROW_SOURCE.sub("", value)


def neutralize(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key in DROPPED_KEYS:
                continue
            if key == "purchase_status" and item in DROPPED_PURCHASE_STATES:
                continue
            if key == "source_id" and isinstance(item, str) and PERSONAL_SOURCE_NOTE.search(item):
                continue
            out[rewrite_text(key)] = neutralize(item)
        return out
    if isinstance(value, list):
        return [neutralize(item) for item in value]
    if isinstance(value, str):
        return rewrite_text(value)
    return value


def _layout(text: str) -> tuple[int | None, bool]:
    """Recover indent and ASCII escaping so a rewrite keeps the file's style."""
    payload = json.loads(text)
    for indent in (2, 1, 4, None):
        for ascii_only in (False, True):
            rendered = json.dumps(payload, indent=indent, ensure_ascii=ascii_only)
            if rendered.rstrip("\n") == text.rstrip("\n"):
                return indent, ascii_only
    raise ValueError("unrecognised JSON layout")


def render_json(text: str) -> str:
    try:
        indent, ascii_only = _layout(text)
    except ValueError:
        # Hand-formatted or compact records: rewrite names in place, keep layout.
        return rewrite_text(text)
    payload = neutralize(json.loads(text))
    trailer = "\n" if text.endswith("\n") else ""
    return json.dumps(payload, indent=indent, ensure_ascii=ascii_only) + trailer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    leaks: list[str] = []
    for relative in JSON_TARGETS + TEXT_TARGETS:
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new = render_json(text) if relative.endswith(".json") else rewrite_text(text)
        if args.check:
            if new != text or LEAK.search(new):
                leaks.append(relative)
            continue
        if new != text:
            path.write_text(new, encoding="utf-8")
        if LEAK.search(new):
            leaks.append(relative)
    for relative in leaks:
        print(f"personal metadata remains: {relative}", file=sys.stderr)
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
