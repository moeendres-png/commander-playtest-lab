"""Source freshness per source layer: counts and real dates read from the ``source`` table.

Only a real calendar date (``YYYY-MM-DD`` with an optional time) counts as a date. A
``universe:<id>`` label is an identifier: counted apart, never part of the oldest/newest span.
Any other snapshot text ("2026-11", "12.11.2026") cannot be evaluated and counts as undated. A
layer without any real date says so; no date is ever invented. The date is what the importer
registered (file name or default), not checked against the content."""

from __future__ import annotations

import datetime
import re
import sqlite3
from typing import TypedDict

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ].*)?$")

# (layer label, title test) in the order shown; the first matching rule wins.
LAYER_ORDER = (
    "Quelldecks",
    "EDHREC Commander",
    "EDHREC Bracket",
    "EDHREC Themen",
    "Playgroup",
    "TopDeck / EDHTop16",
    "Universum-Kohorten",
    "Spellbook",
    "Scryfall-Fakten",
    "Rulings",
    "Rollen",
    "Sammlung",
    "Weitere Quellen",
)


class SourceLayer(TypedDict):
    layer: str
    sources: int
    dated: int
    with_identifier: int
    oldest: str | None
    newest: str | None
    undated_note: str | None


def is_iso_date(value: object) -> bool:
    """True only for a real calendar date (``2026-11-12``, ``2026-11-12T10:00``); ``2026-13-45``,
    ``2026-11`` and ``12.11.2026`` are not."""
    if not isinstance(value, str) or _ISO_DATE.match(value) is None:
        return False
    try:
        datetime.date.fromisoformat(value[:10])
    except ValueError:
        return False
    return True


def is_identifier(value: object) -> bool:
    """A ``universe:<id>`` label: an identifier, not a date."""
    return isinstance(value, str) and value.startswith("universe:")


def date_part(value: str) -> str:
    return value[:10]


def recent_dated_sources(connection: sqlite3.Connection, limit: int = 25) -> list[dict[str, str]]:
    """The ``limit`` newest-imported sources with a real date (oldest first), a sample for the
    page, never the full list. Same date check as the layer counts; ties by ``source_id``."""
    found: list[dict[str, str]] = []
    for title, data_class, sha, snapshot, imported in connection.execute(
        "SELECT title, data_class, SUBSTR(sha256, 1, 12), snapshot_date, imported_at "
        "FROM source WHERE snapshot_date IS NOT NULL ORDER BY imported_at DESC, source_id"
    ):
        if is_iso_date(snapshot):
            found.append(
                {
                    "title": str(title),
                    "data_class": str(data_class),
                    "sha256": str(sha),
                    "snapshot_date": str(snapshot),
                    "imported_at": str(imported),
                }
            )
            if len(found) >= limit:
                break
    found.reverse()
    return found


def layer_of(title: str, *, is_corpus_deck: bool = False) -> str:
    """The source layer of a source row: ``Quelldecks`` by observation (a deck row of the corpus
    names the source), everything else by the title the importer registered."""
    if is_corpus_deck:
        return "Quelldecks"
    name = title.casefold()
    if "#universe:" in name:
        return "Universum-Kohorten"
    if name.startswith(("topdeck_", "edhtop16")):
        return "TopDeck / EDHTop16"
    if name.startswith("commander_bracket_signals"):
        return "EDHREC Bracket"
    if "theme" in name and name.startswith(("edhrec", "commander_")):
        return "EDHREC Themen"
    if name.startswith(("edhrec", "commander_card_signals")):
        return "EDHREC Commander"
    if name.startswith("playgroup"):
        return "Playgroup"
    if name.startswith("spellbook"):
        return "Spellbook"
    if name.startswith("card_rulings"):
        return "Rulings"
    if name.startswith("roles_"):
        return "Rollen"
    if name.startswith("collection."):
        return "Sammlung"
    if name.startswith(("card_tagger", "oracle.")):
        return "Scryfall-Fakten"
    return "Weitere Quellen"


def source_layers(connection: sqlite3.Connection) -> list[SourceLayer]:
    """One row per layer that has sources: count, ``dated`` of ``sources`` with a real date,
    sources carrying only an identifier, oldest/newest real date (``None`` when the layer has
    none, with ``undated_note`` saying the date is not in the store)."""
    acc: dict[str, dict[str, object]] = {}
    for title, snapshot, deck_backed in connection.execute(
        "SELECT title, snapshot_date, source_id IN (SELECT DISTINCT source_id FROM corpus_deck) "
        "FROM source"
    ):
        row = acc.setdefault(
            layer_of(str(title), is_corpus_deck=bool(deck_backed)),
            {"sources": 0, "dated": 0, "ident": 0, "oldest": None, "newest": None},
        )
        row["sources"] = int(str(row["sources"])) + 1
        if is_iso_date(snapshot):
            day = date_part(str(snapshot))
            row["dated"] = int(str(row["dated"])) + 1
            if row["oldest"] is None or day < str(row["oldest"]):
                row["oldest"] = day
            if row["newest"] is None or day > str(row["newest"]):
                row["newest"] = day
        elif is_identifier(snapshot):
            row["ident"] = int(str(row["ident"])) + 1
    layers: list[SourceLayer] = []
    for label in LAYER_ORDER:
        entry = acc.get(label)
        if entry is None:
            continue
        dated = int(str(entry["dated"]))
        layers.append(
            {
                "layer": label,
                "sources": int(str(entry["sources"])),
                "dated": dated,
                "with_identifier": int(str(entry["ident"])),
                "oldest": None if entry["oldest"] is None else str(entry["oldest"]),
                "newest": None if entry["newest"] is None else str(entry["newest"]),
                "undated_note": None if dated else "Datum nicht im Store",
            }
        )
    return layers


def freshness(connection: sqlite3.Connection) -> dict[str, object]:
    """The store-wide figures: ``with_snapshot_date`` counts real dates only; oldest/newest are
    over real dates; ``with_identifier`` counts sources whose label is no date."""
    total = 0
    dated: list[str] = []
    ident = 0
    for (snapshot,) in connection.execute("SELECT snapshot_date FROM source"):
        total += 1
        if is_iso_date(snapshot):
            dated.append(date_part(str(snapshot)))
        elif is_identifier(snapshot):
            ident += 1
    return {
        "total_sources": total,
        "with_snapshot_date": len(dated),
        "with_identifier": ident,
        "oldest_snapshot": min(dated) if dated else None,
        "newest_snapshot": max(dated) if dated else None,
    }
