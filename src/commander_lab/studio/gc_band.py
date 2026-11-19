"""Rule-derived Game-Changer-Band cohorts for corpus decks (Refs #1552).

Decks without a declared bracket remain comparable via a plain, rule-derived count
from each deck's card list and the stored Scryfall Game-Changer list:

- ``gc_band:0``: 0 Game Changers
- ``gc_band:1-3``: 1 to 3 Game Changers
- ``gc_band:4+``: 4 or more Game Changers

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
GC_BANDS: tuple[str, str, str] = (GC_BAND_0, GC_BAND_1_3, GC_BAND_4_PLUS)
GC_BAND_FAMILY = "gc_band"

GC_BAND_LABELS: dict[str, str] = {
    GC_BAND_0: "0 Game Changer",
    GC_BAND_1_3: "1-3 Game Changer",
    GC_BAND_4_PLUS: "4+ Game Changer",
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


class GcBandCrosstab(TypedDict):
    commander: str | None
    total_decks: int
    list_date: str | None
    provenance: str
    disclaimer: str
    data_class: str
    game_changer_cards_marked: int
    game_changer_cards_unknown: int
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


def game_changer_list_date(store_or_db: StudioStore | sqlite3.Connection) -> str | None:
    """Snapshot date (YYYY-MM-DD) of the stored Scryfall Game-Changer list, or ``None``.

    Never guessed from ``imported_at`` or wall-clock time when ``snapshot_date`` is absent.
    """
    db = _connection(store_or_db)
    row = db.execute(
        "SELECT MAX(s.snapshot_date) FROM source s "
        "WHERE s.source_id IN (SELECT DISTINCT source_id FROM scryfall_card)"
    ).fetchone()
    if row is None or not row[0]:
        return None
    text = str(row[0]).strip()
    return text[:10] if text else None


def provenance_text(list_date: str | None) -> str:
    """Human-readable German provenance string for a Game-Changer-Band cohort."""
    datum = list_date if list_date else "unbekannt"
    return f"regelabgeleitet aus Deckliste und Game-Changer-Liste vom {datum}"


def gc_band_metadata(store_or_db: StudioStore | sqlite3.Connection) -> GcBandMetadata:
    """Provenance, list date, disclaimer and Game-Changer coverage of the store."""
    db = _connection(store_or_db)
    list_date = game_changer_list_date(db)
    provenance = provenance_text(list_date)
    marked_row = db.execute("SELECT COUNT(*) FROM scryfall_card WHERE game_changer = 1").fetchone()
    unknown_row = db.execute(
        "SELECT COUNT(*) FROM scryfall_card WHERE game_changer IS NULL"
    ).fetchone()
    marked = int(marked_row[0]) if marked_row is not None and marked_row[0] is not None else 0
    unknown = int(unknown_row[0]) if unknown_row is not None and unknown_row[0] is not None else 0
    return {
        "list_date": list_date,
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
            for key in GC_BANDS
        ],
    }


def declared_bracket_origin(platform: str | None) -> str:
    """Return the unambiguous origin of a declared bracket from ``corpus_deck.platform``."""
    cleaned = (platform or "").strip()
    if not cleaned:
        return "unbekannt"
    return _PLATFORM_BRACKET_ORIGINS.get(
        cleaned.casefold(), f"{cleaned} (erklärtes Bracket laut Plattform)"
    )


def _deck_gc_counts(db: sqlite3.Connection, deck_ids: Sequence[str]) -> dict[str, int]:
    """Count distinct Game-Changer cards (by ``scryfall_card.oracle_id``) per deck."""
    if not deck_ids:
        return {}
    gc_rows = db.execute(
        "SELECT oracle_id, name, front_name FROM scryfall_card WHERE game_changer = 1"
    ).fetchall()
    if not gc_rows:
        return {deck_id: 0 for deck_id in deck_ids}

    gc_oracle_ids: set[str] = set()
    gc_by_name: dict[str, str] = {}
    for row in gc_rows:
        oracle_id = str(row[0])
        gc_oracle_ids.add(oracle_id)
        name = str(row[1]).strip().casefold()
        if name:
            gc_by_name[name] = oracle_id
        front = str(row[2]).strip().casefold()
        if front and front not in gc_by_name:
            gc_by_name[front] = oracle_id

    wanted = set(deck_ids)
    hits_by_deck: dict[str, set[str]] = {}
    section_marks = ", ".join("?" for _ in COUNTED_SECTIONS)
    for row in db.execute(
        f"SELECT deck_id, card_name, oracle_id FROM corpus_deck_card "
        f"WHERE section IN ({section_marks}) AND quantity > 0",
        COUNTED_SECTIONS,
    ):
        deck_id = str(row[0])
        if deck_id not in wanted:
            continue
        oid = str(row[2]) if row[2] else ""
        if oid and oid in gc_oracle_ids:
            hits_by_deck.setdefault(deck_id, set()).add(oid)
            continue
        matched = gc_by_name.get(str(row[1]).strip().casefold())
        if matched is not None:
            hits_by_deck.setdefault(deck_id, set()).add(matched)
    return {deck_id: len(hits_by_deck.get(deck_id, ())) for deck_id in deck_ids}


def deck_gc_bands(
    store_or_db: StudioStore | sqlite3.Connection, deck_ids: Sequence[str]
) -> dict[str, str]:
    """Derive the Game-Changer-Band key for every deck id in ``deck_ids``."""
    db = _connection(store_or_db)
    counts = _deck_gc_counts(db, deck_ids)
    return {deck_id: band_for_count(counts.get(deck_id, 0)) for deck_id in deck_ids}


def _deduplicated_deck_ids(
    store_or_db: StudioStore | sqlite3.Connection,
    commander: str | Sequence[str] | None = None,
) -> list[str]:
    """Select deduplicated corpus deck ids with counted cards, optionally scoped to a commander."""
    commanders: list[str] = []
    if isinstance(commander, str):
        if commander.strip():
            commanders = [commander.strip()]
    elif commander is not None:
        commanders = sorted({str(name).strip() for name in commander if str(name).strip()})

    if isinstance(store_or_db, StudioStore):
        from . import universe

        spec: dict[str, object] = {"commanders": commanders} if commanders else {}
        return universe.resolve_universe(store_or_db, spec)

    db = store_or_db
    selected = [
        (str(row[0]), str(row[1]))
        for row in db.execute("SELECT deck_id, fingerprint FROM corpus_deck")
    ]
    deck_ids = [deck_id for deck_id, _ in selected]
    if commanders:
        wanted_set = frozenset(commanders)
        bound_sets: dict[str, set[str]] = {}
        for row in db.execute(
            "SELECT key, commander_name FROM commander_binding WHERE kind = 'corpus_deck'"
        ):
            bound_sets.setdefault(str(row[0]), set()).add(str(row[1]))
        deck_ids = [deck_id for deck_id in deck_ids if bound_sets.get(deck_id, set()) == wanted_set]
    section_marks = ", ".join("?" for _ in COUNTED_SECTIONS)
    with_cards = {
        str(row[0])
        for row in db.execute(
            f"SELECT d.deck_id FROM corpus_deck d WHERE EXISTS ("
            f"SELECT 1 FROM corpus_deck_card c "
            f"WHERE c.deck_id = d.deck_id AND c.section IN ({section_marks}) AND c.quantity > 0"
            f")",
            COUNTED_SECTIONS,
        )
    }
    deck_ids = [deck_id for deck_id in deck_ids if deck_id in with_cards]
    fingerprints = dict(selected)
    first_by_fp: dict[str, str] = {}
    for deck_id in sorted(deck_ids):
        fp = fingerprints[deck_id]
        key = fp if fp else f"\x00unknown:{deck_id}"
        first_by_fp.setdefault(key, deck_id)
    return sorted(first_by_fp.values())


def declared_bracket_origins(
    store_or_db: StudioStore | sqlite3.Connection,
    *,
    commander: str | Sequence[str] | None = None,
    deck_ids: Sequence[str] | None = None,
) -> dict[str, DeclaredBracketOriginRow]:
    """Per-platform origin and bracket coverage over the selected decks (no new schema)."""
    db = _connection(store_or_db)
    selected = (
        list(deck_ids)
        if deck_ids is not None
        else _deduplicated_deck_ids(store_or_db, commander=commander)
    )
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

    Guarantees ``sum(rows[band]['total'] for band in GC_BANDS) == total_decks``.
    Decks without a declared bracket are counted under ``ohne_bracket``.
    """
    db = _connection(store_or_db)
    selected = (
        list(deck_ids)
        if deck_ids is not None
        else _deduplicated_deck_ids(store_or_db, commander=commander)
    )
    meta = gc_band_metadata(db)
    wanted = set(selected)
    bands = deck_gc_bands(db, selected)

    brackets_of: dict[str, set[str]] = {}
    for row in db.execute(
        "SELECT deck_id, cohort FROM corpus_cohort WHERE cohort LIKE 'bracket:%'"
    ):
        did = str(row[0])
        if did in wanted:
            brackets_of.setdefault(did, set()).add(str(row[1]))

    declared_labels: set[str] = set()
    has_multiple = False
    cells: dict[str, dict[str, int]] = {band: {} for band in GC_BANDS}

    for did in selected:
        band = bands[did]
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
    for band in GC_BANDS:
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
        "provenance": meta["provenance"],
        "disclaimer": meta["disclaimer"],
        "data_class": meta["data_class"],
        "game_changer_cards_marked": meta["game_changer_cards_marked"],
        "game_changer_cards_unknown": meta["game_changer_cards_unknown"],
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
    "MULTIPLE_BRACKETS_KEY",
    "NO_BRACKET_KEY",
    "DeclaredBracketOriginRow",
    "GcBandCrosstab",
    "GcBandCrosstabRow",
    "GcBandDescriptor",
    "GcBandMetadata",
    "band_for_count",
    "deck_gc_bands",
    "declared_bracket_origin",
    "declared_bracket_origins",
    "game_changer_list_date",
    "gc_band_crosstab",
    "gc_band_metadata",
    "provenance_text",
]
