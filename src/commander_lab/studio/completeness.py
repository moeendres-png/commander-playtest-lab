"""Completeness report of the Studio store for one commander (written by ``import-all``).

For every data layer the report counts how many of the commander's legal cards have data of
that layer (``n`` of ``of``) and the same for the whole collection. ``of`` is computed from the
store: the collection cards that are Commander-legal and inside the commander's color
identity, never assumed. A card counts for a layer only when the store holds a value for it;
an unknown value (NULL) is not data. Statuses: VOLLSTÄNDIG (all cards), TEILWEISE (some),
FEHLT (rows of the layer exist, none for these cards) and NICHT GELIEFERT (the store holds no
row of the layer at all).

The counts say nothing about the quality of the data. The report holds no card names and no
deck lists, only counts, source titles and dates, so it can be pasted into an issue.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from . import research_import, universe
from .queries import legal_pool
from .signals import (
    SIGNAL_BRACKET,
    SIGNAL_COMBO_DECKS,
    SIGNAL_EDHTOP16,
    SIGNAL_GLOBAL,
    SIGNAL_INCLUSION,
    SIGNAL_SALT,
    SIGNAL_SYNERGY,
    SIGNAL_TOURNAMENT,
    SIGNAL_VARIANTS,
)
from .store import StudioStore

REPORT_SCHEMA = "studio-import-report-1"
REPORT_FILE = "import_report.json"
COMPLETE = "VOLLSTÄNDIG"
PARTIAL = "TEILWEISE"
MISSING = "FEHLT"
NOT_DELIVERED = "NICHT GELIEFERT"


class LayerRow(TypedDict):
    layer: str
    title: str
    n: int | None
    of: int | None
    collection_n: int
    collection_of: int
    status: str
    source: str
    capture_date: str | None
    capture_basis: str
    note: str


@dataclass(frozen=True)
class _Card:
    card_id: str
    oracle_id: str | None
    names: frozenset[str]


@dataclass(frozen=True)
class _Layer:
    key: str
    title: str
    readme_keys: tuple[str, ...]
    note: str = ""


@dataclass
class _Data:
    """What a layer holds: the names and oracle ids it has a value for, the card ids it
    names directly, the number of rows of the layer in the whole store, its sources."""

    names: set[str]
    oracle_ids: set[str]
    card_ids: set[str]
    rows_in_store: int
    sources: list[tuple[str, str | None]]


def _signal_data(
    db: sqlite3.Connection, signals: Sequence[str], commander: str, *, per_commander: bool
) -> _Data:
    marks = ",".join("?" * len(signals))
    scope = " AND commander_name = ?" if per_commander else " AND commander_name = ''"
    args: list[str] = [*signals] + ([commander] if per_commander else [])
    names = {
        str(r[0])
        for r in db.execute(
            f"SELECT DISTINCT card_name FROM card_signal WHERE signal IN ({marks}){scope} "
            "AND value IS NOT NULL",
            args,
        )
    }
    rows = int(
        db.execute(
            f"SELECT COUNT(*) FROM card_signal WHERE signal IN ({marks})", signals
        ).fetchone()[0]
    )
    sources = [
        (str(r[0]), r[1])
        for r in db.execute(
            "SELECT DISTINCT s.title, s.snapshot_date FROM card_signal c "
            f"JOIN source s USING (source_id) WHERE c.signal IN ({marks}){scope} "
            "AND c.value IS NOT NULL ORDER BY s.title",
            args,
        )
    ]
    return _Data(names, set(), set(), rows, sources)


def _like_signal_data(db: sqlite3.Connection, prefix: str, commander: str) -> _Data:
    kinds = [
        str(r[0])
        for r in db.execute(
            "SELECT DISTINCT signal FROM card_signal WHERE signal LIKE ?", (prefix + ":%",)
        )
    ]
    return _signal_data(db, kinds or [prefix + ":none"], commander, per_commander=True)


def _merge(parts: Sequence[_Data]) -> _Data:
    merged = _Data(set(), set(), set(), 0, [])
    for part in parts:
        merged.names |= part.names
        merged.oracle_ids |= part.oracle_ids
        merged.card_ids |= part.card_ids
        merged.rows_in_store += part.rows_in_store
        merged.sources += part.sources
    return merged


def _roles(db: sqlite3.Connection) -> _Data:
    ids = {str(r[0]) for r in db.execute("SELECT DISTINCT oracle_id FROM card_role")}
    sources = [
        (str(r[0]), r[1])
        for r in db.execute(
            "SELECT DISTINCT s.title, s.snapshot_date FROM card_role r "
            "JOIN source s USING (source_id) ORDER BY s.title"
        )
    ]
    return _Data(set(), ids, set(), len(ids), sources)


def _rulings(db: sqlite3.Connection) -> _Data:
    ids = {str(r[0]) for r in db.execute("SELECT DISTINCT oracle_id FROM card_ruling")}
    sources = [
        (str(r[0]), r[1])
        for r in db.execute(
            "SELECT DISTINCT s.title, s.snapshot_date FROM card_ruling r "
            "JOIN source s USING (source_id) ORDER BY s.title"
        )
    ]
    return _Data(set(), ids, set(), len(ids), sources)


def _corpus(db: sqlite3.Connection, commander: str) -> _Data:
    names: set[str] = set()
    ids: set[str] = set()
    for row in db.execute(
        "SELECT DISTINCT k.card_name, k.oracle_id FROM corpus_deck_card k "
        "JOIN commander_binding b ON b.kind = 'corpus_deck' AND b.key = k.deck_id "
        "AND b.commander_name = ? WHERE k.section != 'sideboard'",
        (commander,),
    ):
        names.add(str(row[0]))
        if row[1] is not None:
            ids.add(str(row[1]))
    total = int(db.execute("SELECT COUNT(*) FROM corpus_deck_card").fetchone()[0])
    sources: list[tuple[str, str | None]] = [
        (str(r[0]), None)
        for r in db.execute(
            "SELECT DISTINCT s.title FROM corpus_deck d JOIN source s USING (source_id) "
            "JOIN commander_binding b ON b.kind = 'corpus_deck' AND b.key = d.deck_id "
            "AND b.commander_name = ? ORDER BY s.title LIMIT 50",
            (commander,),
        )
    ]
    return _Data(names, ids, set(), total, sources)


def _playgroup(db: sqlite3.Connection) -> _Data:
    ids = {
        str(r[0])
        for r in db.execute("SELECT oracle_id FROM playgroup_card_atlas WHERE fetch_status = 'OK'")
    }
    total = int(db.execute("SELECT COUNT(*) FROM playgroup_card_atlas").fetchone()[0])
    sources = [
        (str(r[0]), r[1])
        for r in db.execute(
            "SELECT DISTINCT s.title, s.snapshot_date FROM playgroup_card_atlas p "
            "JOIN source s USING (source_id) ORDER BY s.title"
        )
    ]
    return _Data(set(), ids, set(), total, sources)


def _universe(store: StudioStore, commander: str) -> _Data:
    names: set[str] = set()
    profiles = 0
    for profile in universe.list_profiles(store):
        spec = profile["spec"]
        wanted = spec.get("commanders") if isinstance(spec, dict) else None
        if isinstance(wanted, list) and wanted and [str(w) for w in wanted] != [commander]:
            continue
        try:
            counted = universe.inclusion(
                store, profile=str(profile["name"]), commander_names=[commander]
            )
        except ValueError:
            continue
        profiles += 1
        names |= {row["card_name"] for row in counted["rows"] if row["hits"] > 0}
    return _Data(names, set(), set(), profiles, [])


_LAYERS: tuple[_Layer, ...] = (
    _Layer("inventory", "Bestand (Sammlung)", ()),
    _Layer("public_card_facts", "Öffentliche Kartendaten (Scryfall)", ()),
    _Layer("commander_legality", "Commander-Legalität bekannt", ()),
    _Layer("roles", "Rollen (Tagger)", ("card_tagger_bulk",)),
    _Layer(
        "commander_inclusion", "Einsatzrate beim Commander (EDHREC)", ("commander_card_signals",)
    ),
    _Layer("bracket_inclusion", "Einsatzrate je Bracket (EDHREC)", ("commander_bracket_signals",)),
    _Layer("global_inclusion", "Einsatzrate global (EDHREC)", ("card_global_signals",)),
    _Layer("synergy", "Synergie (EDHREC)", ("commander_card_signals",)),
    _Layer(
        "combos",
        "Combos (Spellbook, EDHREC)",
        ("spellbook_card_links", "edhrec_chulane_combos"),
        "Spellbook: Anzahl bekannter Varianten (0 ist ein veröffentlichter Wert); "
        "EDHREC: beobachtete Combo-Listen des Commanders",
    ),
    _Layer(
        "salt",
        "Salt (EDHREC)",
        ("edhrec_salt",),
        "nur die veröffentlichte Top-Liste; eine Karte ohne Eintrag hat keinen Wert (nicht 0)",
    ),
    _Layer(
        "tournament",
        "Turnier (Listen, Spielrate)",
        ("topdeck_chulane_decks", "edhtop16_commander_signals"),
    ),
    _Layer(
        "rulings",
        "Regelauskünfte (Rulings)",
        ("card_rulings",),
        "die Quelle führt nur Karten mit Rulings; eine Karte ohne Eintrag hat keine veröffentlicht",
    ),
    _Layer("corpus_decks", "Quell-Decks des Commanders (Korpus)", ()),
    _Layer("universe_profiles", "Deck-Universen (gespeicherte Profile)", ()),
    _Layer("playgroup", "Playgroup-Kartenatlas", ()),
)


def _scryfall_date(title: str) -> str | None:
    match = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", title)
    return "-".join(match.groups()) if match else None


def _status(n: int, of: int, rows_in_store: int) -> str:
    if of > 0 and n == of:
        return COMPLETE
    if n > 0:
        return PARTIAL
    return NOT_DELIVERED if rows_in_store == 0 else MISSING


def _capture(
    sources: list[tuple[str, str | None]], readme: Path | None, keys: tuple[str, ...]
) -> tuple[str | None, str]:
    stamped = sorted({str(day)[:10] for _, day in sources if day})
    if stamped:
        return stamped[-1], "Quelle"
    if readme is not None:
        found = [d for key in keys if (d := research_import.capture_date(readme, key))]
        if found:
            return max(found), "README der Lieferung"
    return None, "unbekannt"


def _source_text(sources: list[tuple[str, str | None]]) -> str:
    titles = sorted({title for title, _ in sources})
    if len(titles) > 3:
        return ", ".join(titles[:3]) + f" (+{len(titles) - 3})"
    return ", ".join(titles)


def _cards(db: sqlite3.Connection, card_ids: Sequence[str] | None) -> list[_Card]:
    rows = db.execute(
        "SELECT f.card_id, f.oracle_id, f.oracle_name, f.engine_name FROM card_fact f "
        "JOIN inventory i USING (card_id) ORDER BY f.card_id"
    ).fetchall()
    wanted = set(card_ids) if card_ids is not None else None
    cards: list[_Card] = []
    for row in rows:
        if wanted is not None and row["card_id"] not in wanted:
            continue
        name = str(row["oracle_name"])
        names = {name, str(row["engine_name"]), name.split(" // ")[0]}
        cards.append(_Card(str(row["card_id"]), row["oracle_id"], frozenset(names)))
    return cards


def _count(cards: Sequence[_Card], data: _Data) -> int:
    return sum(
        1
        for card in cards
        if card.card_id in data.card_ids
        or (card.oracle_id is not None and card.oracle_id in data.oracle_ids)
        or bool(card.names & data.names)
    )


def _simple_layers(store: StudioStore) -> dict[str, _Data]:
    """Layers read from the card rows themselves (not from signal or claim tables)."""
    db = store.connection
    facts = db.execute("SELECT card_id, fact_source, commander_legal FROM card_fact").fetchall()
    inventory = {str(r[0]) for r in db.execute("SELECT card_id FROM inventory")}
    scryfall = {str(r["card_id"]) for r in facts if r["fact_source"] == "scryfall"}
    legality = {str(r["card_id"]) for r in facts if r["commander_legal"] is not None}
    inv_sources = [
        (str(r[0]), r[1])
        for r in db.execute(
            "SELECT DISTINCT s.title, MAX(i.last_verified_at) FROM inventory i "
            "JOIN source s USING (source_id) GROUP BY s.title"
        )
    ]
    sf_sources = [
        (str(r[0]), _scryfall_date(str(r[0])))
        for r in db.execute(
            "SELECT DISTINCT s.title FROM scryfall_card c JOIN source s USING (source_id)"
        )
    ]
    return {
        "inventory": _Data(set(), set(), inventory, len(inventory), inv_sources),
        "public_card_facts": _Data(
            set(), set(), scryfall, store.count("scryfall_card"), sf_sources
        ),
        "commander_legality": _Data(
            set(), set(), legality, len(legality), sf_sources or inv_sources
        ),
    }


def _layer_data(store: StudioStore, commander: str) -> dict[str, _Data]:
    db = store.connection
    data = _simple_layers(store)
    data["roles"] = _roles(db)
    data["commander_inclusion"] = _signal_data(
        db, [SIGNAL_INCLUSION], commander, per_commander=True
    )
    data["bracket_inclusion"] = _like_signal_data(db, SIGNAL_BRACKET, commander)
    data["global_inclusion"] = _signal_data(db, [SIGNAL_GLOBAL], commander, per_commander=False)
    data["synergy"] = _signal_data(db, [SIGNAL_SYNERGY], commander, per_commander=True)
    data["combos"] = _merge(
        [
            _signal_data(db, [SIGNAL_VARIANTS], commander, per_commander=False),
            _signal_data(db, [SIGNAL_COMBO_DECKS], commander, per_commander=True),
        ]
    )
    data["salt"] = _signal_data(db, [SIGNAL_SALT], commander, per_commander=False)
    data["tournament"] = _merge(
        [
            _signal_data(db, [SIGNAL_TOURNAMENT], commander, per_commander=True),
            _signal_data(db, [SIGNAL_EDHTOP16], commander, per_commander=True),
        ]
    )
    data["rulings"] = _rulings(db)
    data["corpus_decks"] = _corpus(db, commander)
    data["universe_profiles"] = _universe(store, commander)
    data["playgroup"] = _playgroup(db)
    return data


def build_layers(
    store: StudioStore, commander: str, *, readme: Path | None = None
) -> tuple[list[LayerRow], int | None, int]:
    """Per layer: cards with data of the commander's legal cards and of the whole collection.

    Returns the rows, the number of legal cards (None when the commander is not in the
    collection) and the number of collection cards."""
    db = store.connection
    everything = _cards(db, None)
    try:
        pool_ids = [str(row["card_id"]) for row in legal_pool(store, [commander])]
    except KeyError:
        pool_ids = []
        pool: list[_Card] | None = None
    else:
        pool = _cards(db, pool_ids)
    data = _layer_data(store, commander)
    rows: list[LayerRow] = []
    for layer in _LAYERS:
        held = data[layer.key]
        n_all = _count(everything, held)
        n_pool = _count(pool, held) if pool is not None else None
        of = len(pool) if pool is not None else None
        basis = n_pool if n_pool is not None else n_all
        status = _status(basis, of if of is not None else len(everything), held.rows_in_store)
        if layer.key == "rulings" and held.rows_in_store > 0 and of:
            status = COMPLETE  # the source lists only cards with rulings
        capture, basis_text = _capture(held.sources, readme, layer.readme_keys)
        rows.append(
            {
                "layer": layer.key,
                "title": layer.title,
                "n": n_pool,
                "of": of,
                "collection_n": n_all,
                "collection_of": len(everything),
                "status": status,
                "source": _source_text(held.sources),
                "capture_date": capture,
                "capture_basis": basis_text,
                "note": layer.note,
            }
        )
    return rows, of, len(everything)


def legality_details(store: StudioStore) -> dict[str, int]:
    """Collection cards by legality knowledge: legal, not legal, unknown (excluded from pools)."""
    row = store.connection.execute(
        "SELECT SUM(CASE WHEN f.commander_legal = 1 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN f.commander_legal = 0 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN f.commander_legal IS NULL THEN 1 ELSE 0 END) "
        "FROM card_fact f JOIN inventory i USING (card_id)"
    ).fetchone()
    return {
        "legal": int(row[0] or 0),
        "not_legal": int(row[1] or 0),
        "unknown": int(row[2] or 0),
    }


def format_table(report: dict[str, object]) -> str:
    """The report as text, one line per layer."""
    layers = report.get("layers")
    lines = [
        f"Vollständigkeit für {report.get('commander')}: "
        f"{report.get('legal_pool_cards')} legale Karten im Pool, "
        f"{report.get('collection_cards')} Karten in der Sammlung",
        f"{'Schicht':<40} {'Commander':>14} {'Sammlung':>14}  {'Status':<15} Quelle / Stand",
    ]
    if isinstance(layers, list):
        for row in layers:
            if not isinstance(row, dict):
                continue
            of, n = row["of"], row["n"]
            own = f"{n} von {of}" if of is not None else "n/a"
            whole = f"{row['collection_n']} von {row['collection_of']}"
            stand = row["capture_date"] or "Stand unbekannt"
            lines.append(
                f"{row['title']:<40} {own:>14} {whole:>14}  {row['status']:<15} "
                f"{row['source'] or '-'} / {stand}"
            )
    return "\n".join(lines)


def report_path(folder: Path) -> Path:
    return folder / REPORT_FILE


def write_report(folder: Path, report: dict[str, object]) -> Path:
    target = report_path(folder)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def read_report(folder: Path) -> dict[str, object] | None:
    """The last written report, or None when there is none (or it is not readable)."""
    target = report_path(folder)
    if not target.is_file():
        return None
    try:
        loaded = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None
