"""Rule-derived Game-Changer-Band cohorts for corpus decks (Refs #1552).

Decks without a declared bracket remain comparable via a plain, rule-derived count
from each deck's card list and the stored Scryfall Game-Changer list:

- ``gc_band:0``: 0 Game Changers
- ``gc_band:1-3``: 1 to 3 Game Changers
- ``gc_band:4+``: 4 or more Game Changers
- ``gc_band:unknown``: not determinable (a report row only, never a selectable band)

A deck is ``unknown`` when the store carries no Game-Changer marking at all (no card with
``game_changer = 1``: the list is missing, never "0 Game Changers"), or when at least one of
its counted cards is unresolved (no ``scryfall_card`` row by oracle id, name or front face) or
has an unknown marking (``game_changer IS NULL``). Such a deck is never silently assigned to
a band; the count of unresolved cards is reported per deck and band.

A Game-Changer-Band is explicitly **not** a bracket: the official bracket rules
include additional criteria that are not checked here. Bands live alongside
declared brackets and are never mixed with them in one count or universe.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import TypedDict

from .store import COUNTED_SECTIONS, StudioStore

GC_BAND_0 = "gc_band:0"
GC_BAND_1_3 = "gc_band:1-3"
GC_BAND_4_PLUS = "gc_band:4+"
GC_BAND_UNKNOWN = "gc_band:unknown"
# The selectable bands. ``GC_BAND_UNKNOWN`` is a report row only, never a selection.
GC_BANDS: tuple[str, str, str] = (GC_BAND_0, GC_BAND_1_3, GC_BAND_4_PLUS)
GC_BAND_ROWS: tuple[str, str, str, str] = (*GC_BANDS, GC_BAND_UNKNOWN)
GC_BAND_FAMILY = "gc_band"

MARKING_COMPLETE = "complete"
MARKING_PARTIAL = "partial"
MARKING_MISSING = "missing"
MARKING_MISSING_REASON = (
    "Keine Game-Changer-Markierung gespeichert: kein Deck lässt sich einem Band zuordnen "
    "(unbekannt, nicht 0 Game Changer)."
)

GC_BAND_LABELS: dict[str, str] = {
    GC_BAND_0: "0 Game Changer",
    GC_BAND_1_3: "1-3 Game Changer",
    GC_BAND_4_PLUS: "4+ Game Changer",
    GC_BAND_UNKNOWN: "unbekannt (Markierung fehlt/unbekannt oder Karten unaufgelöst)",
}

GC_BAND_DISCLAIMER = (
    "Das Band ist kein Bracket: die offizielle Bracket-Regel kennt weitere Kriterien, "
    "die hier nicht geprüft werden."
)

NO_BRACKET_KEY = "ohne_bracket"
MULTIPLE_BRACKETS_KEY = "multiple"

_PLATFORM_BRACKET_ORIGINS: dict[str, str] = {
    "archidekt": "Archidekt (Selbstauskunft des Deck-Besitzers)",
    "edhrec": "EDHREC (übernommene Plattform-Einstufung / Selbstauskunft)",
    "moxfield": "Moxfield (Selbstauskunft des Deck-Besitzers)",
    "topdeck": "TopDeck (Turnier-Einstufung)",
}


class GcBandDescriptor(TypedDict):
    key: str
    label: str
    provenance: str
    disclaimer: str


class GcBandMetadata(TypedDict):
    list_date: str | None
    list_imported_at: str | None
    marking_status: str
    provenance: str
    disclaimer: str
    game_changer_cards_marked: int
    game_changer_cards_unknown: int
    data_class: str
    bands: list[GcBandDescriptor]


class DeclaredBracketOriginRow(TypedDict):
    platform: str
    origin: str
    decks_with_bracket: int
    decks_without_bracket: int
    decks_total: int


class GcBandCrosstabRow(TypedDict):
    band: str
    label: str
    provenance: str
    by_bracket: dict[str, int]
    total: int
    of: int
    decks_with_unresolved: int
    unresolved_cards: int


class DeckGcDetail(TypedDict):
    band: str
    game_changers: int
    unresolved: int
    marking_unknown: int


class GcBandCrosstab(TypedDict):
    commander: str | None
    total_decks: int
    list_date: str | None
    list_imported_at: str | None
    marking_status: str
    provenance: str
    disclaimer: str
    data_class: str
    game_changer_cards_marked: int
    game_changer_cards_unknown: int
    decks_with_unresolved: int
    unresolved_cards: int
    bracket_columns: list[str]
    rows: dict[str, GcBandCrosstabRow]
    totals_by_bracket: dict[str, int]
    declared_bracket_origins: dict[str, DeclaredBracketOriginRow]


def _connection(store_or_db: StudioStore | sqlite3.Connection) -> sqlite3.Connection:
    return store_or_db.connection if isinstance(store_or_db, StudioStore) else store_or_db


def band_for_count(gc_count: int) -> str:
    """Map a non-negative Game-Changer card count to its derived band key."""
    if gc_count <= 0:
        return GC_BAND_0
    if gc_count <= 3:
        return GC_BAND_1_3
    return GC_BAND_4_PLUS


def _marking_sources(db: sqlite3.Connection) -> list[tuple[str | None, str | None]]:
    """``(snapshot_date, imported_at)`` of the sources that carry the Game-Changer marking
    (the ``scryfall_card`` rows with ``game_changer = 1``), not of every Scryfall source."""
    return [
        (
            str(row[0]).strip()[:10] if row[0] and str(row[0]).strip() else None,
            str(row[1]).strip()[:10] if row[1] and str(row[1]).strip() else None,
        )
        for row in db.execute(
            "SELECT s.snapshot_date, s.imported_at FROM source s WHERE s.source_id IN "
            "(SELECT DISTINCT source_id FROM scryfall_card WHERE game_changer = 1)"
        )
    ]


def game_changer_list_date(store_or_db: StudioStore | sqlite3.Connection) -> str | None:
    """Snapshot date (YYYY-MM-DD) of the source that carries the Game-Changer marking, or
    ``None``.

    Never guessed from ``imported_at`` or wall-clock time when ``snapshot_date`` is absent,
    and never taken from a Scryfall source that carries no marking.
    """
    dates = [snapshot for snapshot, _ in _marking_sources(_connection(store_or_db)) if snapshot]
    return max(dates) if dates else None


def game_changer_list_imported_at(store_or_db: StudioStore | sqlite3.Connection) -> str | None:
    """Import date (YYYY-MM-DD) of the source that carries the Game-Changer marking."""
    dates = [imported for _, imported in _marking_sources(_connection(store_or_db)) if imported]
    return max(dates) if dates else None


def provenance_text(
    list_date: str | None,
    imported_at: str | None = None,
    marking_status: str = MARKING_COMPLETE,
) -> str:
    """Human-readable German provenance string for a Game-Changer-Band cohort."""
    base = "regelabgeleitet aus Deckliste und Game-Changer-Liste"
    if marking_status == MARKING_MISSING:
        return f"{base}: keine Game-Changer-Markierung gespeichert, Band unbekannt"
    if list_date:
        return f"{base} (Markierung vom {list_date})"
    if imported_at:
        return f"{base}; Datum der Markierung unbekannt (Import {imported_at})"
    return f"{base}; Datum der Markierung unbekannt"


def gc_band_metadata(store_or_db: StudioStore | sqlite3.Connection) -> GcBandMetadata:
    """Provenance, list date, disclaimer and Game-Changer coverage of the store."""
    db = _connection(store_or_db)
    marked_row = db.execute("SELECT COUNT(*) FROM scryfall_card WHERE game_changer = 1").fetchone()
    unknown_row = db.execute(
        "SELECT COUNT(*) FROM scryfall_card WHERE game_changer IS NULL"
    ).fetchone()
    marked = int(marked_row[0]) if marked_row is not None and marked_row[0] is not None else 0
    unknown = int(unknown_row[0]) if unknown_row is not None and unknown_row[0] is not None else 0
    status = marking_status(marked, unknown)
    list_date = game_changer_list_date(db)
    imported_at = game_changer_list_imported_at(db)
    provenance = provenance_text(list_date, imported_at, status)
    return {
        "list_date": list_date,
        "list_imported_at": imported_at,
        "marking_status": status,
        "provenance": provenance,
        "disclaimer": GC_BAND_DISCLAIMER,
        "game_changer_cards_marked": marked,
        "game_changer_cards_unknown": unknown,
        "data_class": "DERIVED_DESCRIPTIVE",
        "bands": [
            {
                "key": key,
                "label": GC_BAND_LABELS[key],
                "provenance": provenance,
                "disclaimer": GC_BAND_DISCLAIMER,
            }
            for key in GC_BAND_ROWS
        ],
    }


def marking_status(marked: int, unknown: int) -> str:
    """``missing`` without any card marked ``game_changer = 1`` (the list is absent, never
    "0 Game Changers"), ``partial`` with marked cards and some unknown markings, else
    ``complete``."""
    if marked <= 0:
        return MARKING_MISSING
    if unknown > 0:
        return MARKING_PARTIAL
    return MARKING_COMPLETE


def declared_bracket_origin(platform: str | None) -> str:
    """Return the unambiguous origin of a declared bracket from ``corpus_deck.platform``."""
    cleaned = (platform or "").strip()
    if not cleaned:
        return "unbekannt"
    return _PLATFORM_BRACKET_ORIGINS.get(
        cleaned.casefold(), f"{cleaned} (erklärtes Bracket laut Plattform)"
    )


def deck_gc_details(
    store_or_db: StudioStore | sqlite3.Connection, deck_ids: Sequence[str]
) -> dict[str, DeckGcDetail]:
    """Per deck: distinct Game Changers, unresolved cards, unknown markings and the band.

    A counted card (sections ``COUNTED_SECTIONS``, quantity above zero) resolves to a
    ``scryfall_card`` row by its stored oracle id, else by exact name, else by front-face
    name. Unresolved cards and cards with ``game_changer IS NULL`` make the band
    ``gc_band:unknown``; without any marked card in the store every deck is unknown.
    """
    if not deck_ids:
        return {}
    db = _connection(store_or_db)
    flag_by_oracle: dict[str, int | None] = {}
    by_name: dict[str, str] = {}
    by_front: dict[str, str] = {}
    for row in db.execute("SELECT oracle_id, name, front_name, game_changer FROM scryfall_card"):
        oracle_id = str(row[0])
        flag_by_oracle[oracle_id] = None if row[3] is None else int(row[3])
        name = str(row[1]).strip().casefold()
        if name:
            by_name.setdefault(name, oracle_id)
        front = str(row[2]).strip().casefold()
        if front:
            by_front.setdefault(front, oracle_id)
    list_missing = not any(flag == 1 for flag in flag_by_oracle.values())

    wanted = set(deck_ids)
    hits: dict[str, set[str]] = {}
    unresolved: dict[str, set[str]] = {}
    marking_unknown: dict[str, set[str]] = {}
    section_marks = ", ".join("?" for _ in COUNTED_SECTIONS)
    for row in db.execute(
        f"SELECT deck_id, card_name, oracle_id FROM corpus_deck_card "
        f"WHERE section IN ({section_marks}) AND quantity > 0",
        COUNTED_SECTIONS,
    ):
        deck_id = str(row[0])
        if deck_id not in wanted:
            continue
        name = str(row[1]).strip().casefold()
        stored = str(row[2]) if row[2] else ""
        oracle_id = (
            stored if stored in flag_by_oracle else by_name.get(name) or by_front.get(name) or ""
        )
        if not oracle_id:
            unresolved.setdefault(deck_id, set()).add(name)
            continue
        flag = flag_by_oracle[oracle_id]
        if flag is None:
            marking_unknown.setdefault(deck_id, set()).add(oracle_id)
        elif flag == 1:
            hits.setdefault(deck_id, set()).add(oracle_id)

    details: dict[str, DeckGcDetail] = {}
    for deck_id in deck_ids:
        gc_count = len(hits.get(deck_id, ()))
        open_count = len(unresolved.get(deck_id, ()))
        unknown_count = len(marking_unknown.get(deck_id, ()))
        uncertain = list_missing or open_count > 0 or unknown_count > 0
        details[deck_id] = {
            "band": GC_BAND_UNKNOWN if uncertain else band_for_count(gc_count),
            "game_changers": gc_count,
            "unresolved": open_count,
            "marking_unknown": unknown_count,
        }
    return details


def deck_gc_bands(
    store_or_db: StudioStore | sqlite3.Connection, deck_ids: Sequence[str]
) -> dict[str, str]:
    """Derive the Game-Changer-Band key (``gc_band:unknown`` included) for every deck id."""
    return {
        deck_id: item["band"] for deck_id, item in deck_gc_details(store_or_db, deck_ids).items()
    }


def _selected_decks(
    store_or_db: StudioStore | sqlite3.Connection,
    commander: str | Sequence[str] | None,
    deck_ids: Sequence[str] | None,
) -> list[str]:
    """The given deck ids, else the deduplicated universe decks of the commander (or all)."""
    if deck_ids is not None:
        return list(deck_ids)
    if not isinstance(store_or_db, StudioStore):
        raise TypeError("deck_ids are required when no StudioStore is given")
    # Imported here: universe imports this module at module level.
    from . import universe

    commanders: list[str] = []
    if isinstance(commander, str):
        if commander.strip():
            commanders = [commander.strip()]
    elif commander is not None:
        commanders = sorted({str(name).strip() for name in commander if str(name).strip()})
    spec: dict[str, object] = {"commanders": commanders} if commanders else {}
    return universe.resolve_universe(store_or_db, spec)


def declared_bracket_origins(
    store_or_db: StudioStore | sqlite3.Connection,
    *,
    commander: str | Sequence[str] | None = None,
    deck_ids: Sequence[str] | None = None,
) -> dict[str, DeclaredBracketOriginRow]:
    """Per-platform origin and bracket coverage over the selected decks (no new schema)."""
    db = _connection(store_or_db)
    selected = _selected_decks(store_or_db, commander, deck_ids)
    if not selected:
        return {}
    wanted = set(selected)
    platform_of: dict[str, str] = {}
    for row in db.execute("SELECT deck_id, platform FROM corpus_deck"):
        did = str(row[0])
        if did in wanted:
            platform_of[did] = str(row[1])
    with_bracket: set[str] = set()
    for row in db.execute(
        "SELECT DISTINCT deck_id FROM corpus_cohort WHERE cohort LIKE 'bracket:%'"
    ):
        did = str(row[0])
        if did in wanted:
            with_bracket.add(did)

    totals: dict[str, int] = {}
    declared: dict[str, int] = {}
    for did in selected:
        plat = platform_of.get(did, "")
        totals[plat] = totals.get(plat, 0) + 1
        if did in with_bracket:
            declared[plat] = declared.get(plat, 0) + 1

    result: dict[str, DeclaredBracketOriginRow] = {}
    for plat in sorted(totals):
        total = totals[plat]
        has_b = declared.get(plat, 0)
        result[plat] = {
            "platform": plat,
            "origin": declared_bracket_origin(plat),
            "decks_with_bracket": has_b,
            "decks_without_bracket": total - has_b,
            "decks_total": total,
        }
    return result


def gc_band_crosstab(
    store_or_db: StudioStore | sqlite3.Connection,
    *,
    commander: str | Sequence[str] | None = None,
    deck_ids: Sequence[str] | None = None,
) -> GcBandCrosstab:
    """Cross-tabulate derived Game-Changer-Bands against declared brackets.

    Guarantees ``sum(rows[band]['total'] for band in GC_BAND_ROWS) == total_decks``: a deck
    whose band is not determinable is counted under ``gc_band:unknown``, never under
    ``gc_band:0``. Decks without a declared bracket are counted under ``ohne_bracket``.
    """
    db = _connection(store_or_db)
    selected = _selected_decks(store_or_db, commander, deck_ids)
    meta = gc_band_metadata(db)
    wanted = set(selected)
    details = deck_gc_details(db, selected)

    brackets_of: dict[str, set[str]] = {}
    for row in db.execute(
        "SELECT deck_id, cohort FROM corpus_cohort WHERE cohort LIKE 'bracket:%'"
    ):
        did = str(row[0])
        if did in wanted:
            brackets_of.setdefault(did, set()).add(str(row[1]))

    declared_labels: set[str] = set()
    has_multiple = False
    cells: dict[str, dict[str, int]] = {band: {} for band in GC_BAND_ROWS}
    with_unresolved: dict[str, int] = {band: 0 for band in GC_BAND_ROWS}
    unresolved_cards: dict[str, int] = {band: 0 for band in GC_BAND_ROWS}

    for did in selected:
        band = details[did]["band"]
        if details[did]["unresolved"]:
            with_unresolved[band] += 1
            unresolved_cards[band] += details[did]["unresolved"]
        labels = brackets_of.get(did, set())
        if not labels:
            col = NO_BRACKET_KEY
        elif len(labels) > 1:
            col = MULTIPLE_BRACKETS_KEY
            has_multiple = True
        else:
            col = next(iter(labels))
            declared_labels.add(col)
        cells[band][col] = cells[band].get(col, 0) + 1

    columns = sorted(declared_labels)
    if has_multiple:
        columns.append(MULTIPLE_BRACKETS_KEY)
    columns.append(NO_BRACKET_KEY)

    total_decks = len(selected)
    rows: dict[str, GcBandCrosstabRow] = {}
    totals_by_bracket: dict[str, int] = {col: 0 for col in columns}
    for band in GC_BAND_ROWS:
        by_bracket = {col: cells[band].get(col, 0) for col in columns}
        row_total = sum(by_bracket.values())
        for col, cnt in by_bracket.items():
            totals_by_bracket[col] += cnt
        rows[band] = {
            "band": band,
            "label": GC_BAND_LABELS[band],
            "provenance": meta["provenance"],
            "by_bracket": by_bracket,
            "total": row_total,
            "of": total_decks,
            "decks_with_unresolved": with_unresolved[band],
            "unresolved_cards": unresolved_cards[band],
        }

    commander_label: str | None
    if isinstance(commander, str):
        commander_label = commander.strip() or None
    elif commander is not None:
        cleaned = sorted({str(name).strip() for name in commander if str(name).strip()})
        commander_label = " / ".join(cleaned) if cleaned else None
    else:
        commander_label = None

    return {
        "commander": commander_label,
        "total_decks": total_decks,
        "list_date": meta["list_date"],
        "list_imported_at": meta["list_imported_at"],
        "marking_status": meta["marking_status"],
        "provenance": meta["provenance"],
        "disclaimer": meta["disclaimer"],
        "data_class": meta["data_class"],
        "game_changer_cards_marked": meta["game_changer_cards_marked"],
        "game_changer_cards_unknown": meta["game_changer_cards_unknown"],
        "decks_with_unresolved": sum(with_unresolved.values()),
        "unresolved_cards": sum(unresolved_cards.values()),
        "bracket_columns": columns,
        "rows": rows,
        "totals_by_bracket": totals_by_bracket,
        "declared_bracket_origins": declared_bracket_origins(db, deck_ids=selected),
    }


__all__ = [
    "GC_BANDS",
    "GC_BAND_0",
    "GC_BAND_1_3",
    "GC_BAND_4_PLUS",
    "GC_BAND_DISCLAIMER",
    "GC_BAND_FAMILY",
    "GC_BAND_LABELS",
    "GC_BAND_ROWS",
    "GC_BAND_UNKNOWN",
    "MARKING_COMPLETE",
    "MARKING_MISSING",
    "MARKING_MISSING_REASON",
    "MARKING_PARTIAL",
    "MULTIPLE_BRACKETS_KEY",
    "NO_BRACKET_KEY",
    "DeckGcDetail",
    "DeclaredBracketOriginRow",
    "GcBandCrosstab",
    "GcBandCrosstabRow",
    "GcBandDescriptor",
    "GcBandMetadata",
    "band_for_count",
    "deck_gc_bands",
    "deck_gc_details",
    "declared_bracket_origin",
    "declared_bracket_origins",
    "game_changer_list_date",
    "game_changer_list_imported_at",
    "gc_band_crosstab",
    "gc_band_metadata",
    "marking_status",
    "provenance_text",
]
