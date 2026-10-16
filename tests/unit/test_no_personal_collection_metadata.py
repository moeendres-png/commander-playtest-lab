"""Collection and deck data stay neutral: no storage boxes, purchases or sellers.

The collection is one flat card list and decks keep their cards and structure; who
stores a card where, when it was bought and from whom is not project data.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

SCANNED = (
    "data/canonical_import",
    "data/collections",
    "data/decks",
    "data/rules",
    "data/opponents",
    "data/provenance",
    "data/enrichment",
)
PERSONAL_KEYS = frozenset(
    {"box", "box_or_location", "box_or_source", "source_category", "origin", "product"}
)
PURCHASE_TEXT = re.compile(r"Kartenkauf|Kaufdatum|Cardmarket|Einzelkauf|\bBox \d")


def _keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def _json_files() -> Iterator[Path]:
    for relative in SCANNED:
        yield from sorted((ROOT / relative).rglob("*.json"))


def test_collection_and_deck_data_carry_no_personal_storage_or_purchase_keys() -> None:
    offenders = {
        str(path.relative_to(ROOT)): sorted(set(_keys(payload)) & PERSONAL_KEYS)
        for path in _json_files()
        for payload in [json.loads(path.read_text(encoding="utf-8"))]
        if set(_keys(payload)) & PERSONAL_KEYS
    }
    assert offenders == {}


def test_collection_and_deck_data_carry_no_purchase_records() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in _json_files()
        if PURCHASE_TEXT.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
