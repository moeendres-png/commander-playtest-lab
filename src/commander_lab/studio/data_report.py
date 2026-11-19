"""Counts-only report on how complete the Studio store is (Refs #1182).

The report answers "what do we have, what is missing, what is unknown" with numbers: every
figure is a count with its denominator, a missing value is counted as unknown (never as zero),
and no card name (apart from the commander names every figure is bound to), deck address or
note text leaves the database. It can therefore be pasted into an issue or a Drive document.
The universes section follows the same rule: a stored universe profile is identified by its
version, never by its name or by the card names its spec requires — only how many values each
spec dimension selects — and it is counted per commander, never over all commanders at once.

The commanders section gives, per commander, the pool size (legal collection cards inside its
colour identity), the cards excluded because their legality is unknown (listed as unknown,
never as illegal) and the signal layer: rows per signal and the coverage over the pool
(cards with a value / pool size).

``role_fingerprint`` hashes the role tables so that a before/after comparison around an import
shows at a glance whether anything outside the imported scope changed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import UTC, date, datetime
from typing import cast

from . import builder, signals, strength_view, universe
from .corpus_audit import corpus_audit
from .roles import ORIGIN_CROSSWALK, ORIGIN_TAGGER, ROLES
from .store import StudioStore
from .tiers import MODEL_VERSION, TierParams

REPORT_SCHEMA = "studio-data-report-1"
SMALL_DENOMINATOR = 30
SCRYFALL_STALE_AFTER_DAYS = 30

# Things the store cannot measure; stated so that nobody reads their absence as "complete".
NOT_MEASURED = (
    "pilot_knowledge_for_collection",
    "engine_card_support_for_collection",
    "collection_changes_since_last_export",
)


def _scalar(db: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> int:
    row = db.execute(sql, params).fetchone()
    return int(row[0]) if row is not None and row[0] is not None else 0


def _share(count: int, of: int) -> dict[str, int]:
    return {"count": count, "of": of}


def _counter(db: sqlite3.Connection, sql: str) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in db.execute(sql)}


def _digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def role_fingerprint(db: sqlite3.Connection) -> dict[str, object]:
    """Hashes of the role claims (also per origin and scope), the roles the builder reads and
    the per-deck role counts.

    An import that is limited to one scope must leave the hash of every other scope unchanged.
    """
    claims: list[str] = []
    per_scope: dict[str, list[str]] = {}
    for row in db.execute(
        "SELECT oracle_id, role, role_origin, scope_key, source_id FROM card_role_claim"
    ):
        line = f"{row[0]}|{row[1]}|{row[2]}|{row[3]}|{row[4]}"
        claims.append(line)
        per_scope.setdefault(f"{row[2]}/{row[3]}", []).append(line)
    roles = [f"{r[0]}|{r[1]}" for r in db.execute("SELECT oracle_id, role FROM card_role")]
    decks = [
        f"{r[0]}|{r[1]}|{r[2]}"
        for r in db.execute("SELECT deck_id, role, cards FROM corpus_deck_role")
    ]
    return {
        "card_role_claim": _digest(claims),
        "card_role_claim_by_scope": {key: _digest(per_scope[key]) for key in sorted(per_scope)},
        "card_role": _digest(roles),
        "corpus_deck_role": _digest(decks),
    }


def _collection(db: sqlite3.Connection) -> dict[str, object]:
    identities = _scalar(db, "SELECT COUNT(*) FROM card")
    inventory = _scalar(db, "SELECT COUNT(*) FROM inventory")
    return {
        "identities": identities,
        "with_oracle_id": _share(
            _scalar(db, "SELECT COUNT(*) FROM card_fact WHERE oracle_id IS NOT NULL"), identities
        ),
        "with_scryfall_facts": _share(
            _scalar(db, "SELECT COUNT(*) FROM card_fact WHERE fact_source = 'scryfall'"),
            identities,
        ),
        "inventory_rows": inventory,
        "quantity_exact": _share(
            _scalar(db, "SELECT COUNT(*) FROM inventory WHERE quantity_exact != 0"), inventory
        ),
        "quantity_lower_bound_only": _share(
            _scalar(db, "SELECT COUNT(*) FROM inventory WHERE quantity_exact = 0"), inventory
        ),
        "never_verified": _share(
            _scalar(
                db,
                "SELECT COUNT(*) FROM inventory "
                "WHERE last_verified_at IS NULL OR last_verified_at = ''",
            ),
            inventory,
        ),
        "cards_with_reservation": _share(
            _scalar(db, "SELECT COUNT(*) FROM inventory WHERE reserved > 0"), inventory
        ),
    }


def _age_days(snapshot: str | None, today: date) -> int | None:
    if not snapshot:
        return None
    try:
        return (today - date.fromisoformat(snapshot[:10])).days
    except ValueError:
        return None


def _scryfall(db: sqlite3.Connection, today: date) -> dict[str, object]:
    total = _scalar(db, "SELECT COUNT(*) FROM scryfall_card")
    snapshot_row = db.execute(
        "SELECT MAX(s.snapshot_date) FROM source s "
        "WHERE s.source_id IN (SELECT DISTINCT source_id FROM scryfall_card)"
    ).fetchone()
    snapshot = str(snapshot_row[0]) if snapshot_row is not None and snapshot_row[0] else None
    age = _age_days(snapshot, today)
    return {
        "oracle_ids": total,
        "snapshot_date": snapshot,
        "age_days": age,
        "stale_after_days": SCRYFALL_STALE_AFTER_DAYS,
        "stale": None if age is None else age > SCRYFALL_STALE_AFTER_DAYS,
        "commander_legality": _counter(
            db,
            "SELECT commander_legality, COUNT(*) FROM scryfall_card GROUP BY commander_legality",
        ),
        "game_changer": {
            "yes": _scalar(db, "SELECT COUNT(*) FROM scryfall_card WHERE game_changer = 1"),
            "no": _scalar(db, "SELECT COUNT(*) FROM scryfall_card WHERE game_changer = 0"),
            "unknown": _scalar(db, "SELECT COUNT(*) FROM scryfall_card WHERE game_changer IS NULL"),
        },
        "without_image": _share(
            _scalar(
                db,
                "SELECT COUNT(*) FROM scryfall_card WHERE image_front IS NULL OR image_front = ''",
            ),
            total,
        ),
    }


UNKNOWN = "unbekannt"
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ].*)?")
SNAPSHOT_DATE_ORIGIN = (
    "source.snapshot_date, written at import from a date the data states: a retrieval field of "
    "the file, a date in the file or folder name (the author's label, not checked), or a README "
    "cell 'Abruf <Datum>'; a README count, build or filter date, the generation date of a "
    "deck-list file and the import day are never taken; a value stored by an earlier import is "
    "not re-checked (a source keeps its date until a new store or a changed file); a missing "
    "date stays unbekannt"
)


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def source_row_columns(db: sqlite3.Connection) -> list[tuple[str, str]]:
    """Every (table, column) of the store that points at ``source``: a column called
    ``source_id`` or a foreign key to ``source``. Derived from the schema of the connection, so a
    table added later is counted without touching this module. ``source`` itself is not a
    pointer."""
    pairs: list[tuple[str, str]] = []
    names = sorted(
        str(r[0])
        for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    )
    for name in names:
        if name == "source":
            continue
        columns = {str(r[1]) for r in db.execute(f"PRAGMA table_info({_quote(name)})")}
        pointing = {"source_id"} & columns
        for fk in db.execute(f"PRAGMA foreign_key_list({_quote(name)})"):
            if str(fk[2]) == "source":
                pointing.add(str(fk[3]))
        pairs.extend((name, column) for column in sorted(pointing))
    return pairs


def _valid_retrieval_age(snapshot: str | None, today: date) -> int | None:
    """Age in days of a stored retrieval date, or ``None`` when the value is not a valid
    calendar date (ISO form, optionally followed by a time) or lies in the future."""
    if not snapshot or not _ISO_DATE.fullmatch(snapshot):
        return None
    age = _age_days(snapshot, today)
    return age if age is not None and age >= 0 else None


def _source_status(db: sqlite3.Connection, today: date) -> dict[str, object]:
    """Per source (a single deck file excluded, those are counted as one group): rows the store
    holds from it, its date and age in days, or "unbekannt", and whether an address is stored.
    No network access: everything is read from ``source`` and from every table column that
    points at it (:func:`source_row_columns`, derived from the schema, listed in
    ``tables_counted``). ``rows_in_store`` is a count over exactly those tables; a source no
    row points at has a counted 0 (for example a part file registered next to its combined
    source), which is a count, not a missing value.
    The date is ``source.snapshot_date`` (see ``snapshot_date_origin``); it counts as known only
    when it is a valid calendar date that is not in the future.
    Licence and access terms have no column in the store and are therefore listed as not
    recorded, never as free or open."""
    rows_of: dict[str, int] = {}
    pairs = source_row_columns(db)
    for table, column in pairs:
        for source_id, count in db.execute(
            f"SELECT {_quote(column)}, COUNT(*) FROM {_quote(table)} GROUP BY {_quote(column)}"
        ):
            if source_id is not None:
                rows_of[str(source_id)] = rows_of.get(str(source_id), 0) + int(count)
    entries: list[dict[str, object]] = []
    for row in db.execute(
        "SELECT s.source_id, s.title, s.data_class, s.snapshot_date, s.url, s.imported_at "
        "FROM source s WHERE s.source_id NOT IN (SELECT source_id FROM corpus_deck) "
        "ORDER BY s.title, s.source_id"
    ):
        snapshot = str(row["snapshot_date"]) if row["snapshot_date"] else None
        age = _valid_retrieval_age(snapshot, today)
        entries.append(
            {
                "title": row["title"],
                "data_class": row["data_class"],
                "rows_in_store": rows_of.get(str(row["source_id"]), 0),
                "snapshot_date": snapshot if age is not None else UNKNOWN,
                "snapshot_value_not_a_date": snapshot is not None and age is None,
                "age_days": age if age is not None else UNKNOWN,
                "address_stored": bool(row["url"]),
                "imported_at": row["imported_at"],
            }
        )
    total = len(entries)
    unknown = sorted(str(e["title"]) for e in entries if e["snapshot_date"] == UNKNOWN)
    deck_dates = [
        _valid_retrieval_age(str(r[0]) if r[0] else None, today) is not None
        for r in db.execute(
            "SELECT s.snapshot_date FROM source s "
            "WHERE s.source_id IN (SELECT source_id FROM corpus_deck)"
        )
    ]
    deck_total = len(deck_dates)
    deck_known = sum(deck_dates)
    return {
        "scope": "sources that are not a single deck file; deck files are counted as one group",
        "date_known": _share(total - len(unknown), total),
        "date_unknown": len(unknown),
        "date_unknown_of_which_value_not_a_date": sum(
            1 for e in entries if e["snapshot_value_not_a_date"]
        ),
        "date_unknown_titles": unknown,
        "snapshot_date_origin": SNAPSHOT_DATE_ORIGIN,
        "address_stored": _share(sum(1 for e in entries if e["address_stored"]), total),
        "deck_file_sources": {
            "total": deck_total,
            "date_unknown": deck_total - deck_known,
            "date_known": deck_known,
        },
        "licence_and_access": "nicht im Store erfasst (keine Spalte); weder frei noch offen belegt",
        "imported_at_note": (
            "imported_at is the import day, not the retrieval day; only snapshot_date is a retrieval date"
        ),
        "rows_in_store_origin": "sum of rows over all tables_counted that point at the source",
        "tables_counted": sorted({f"{t}.{c}" for t, c in pairs}),
        "details": entries,
    }


def _roles(db: sqlite3.Connection) -> dict[str, object]:
    with_oracle = _scalar(db, "SELECT COUNT(*) FROM card_fact WHERE oracle_id IS NOT NULL")
    with_claim = _scalar(
        db,
        "SELECT COUNT(DISTINCT f.oracle_id) FROM card_fact f "
        "JOIN card_role_claim c ON c.oracle_id = f.oracle_id",
    )
    origins: dict[str, dict[str, int]] = {}
    for row in db.execute(
        "SELECT role_origin, COUNT(*), COUNT(DISTINCT oracle_id) FROM card_role_claim "
        "GROUP BY role_origin"
    ):
        origins[str(row[0])] = {"claims": int(row[1]), "cards": int(row[2])}
    tagger_cards = _scalar(
        db,
        "SELECT COUNT(DISTINCT f.oracle_id) FROM card_fact f "
        "JOIN card_role_claim c ON c.oracle_id = f.oracle_id "
        "WHERE c.role_origin IN (?, ?)",
        (ORIGIN_TAGGER, ORIGIN_CROSSWALK),
    )
    per_role = _counter(
        db,
        "SELECT r.role, COUNT(DISTINCT r.oracle_id) FROM card_role r "
        "JOIN card_fact f ON f.oracle_id = r.oracle_id GROUP BY r.role",
    )
    decks = _scalar(db, "SELECT COUNT(*) FROM corpus_deck")
    return {
        "vocabulary": len(ROLES),
        "collection_with_any_role": _share(with_claim, with_oracle),
        "collection_without_any_role": _share(with_oracle - with_claim, with_oracle),
        "collection_with_tagger_based_role": _share(tagger_cards, with_oracle),
        "by_origin": origins,
        "collection_cards_per_role": {role: per_role.get(role, 0) for role in sorted(ROLES)},
        "corpus_decks_with_role_counts": _share(
            _scalar(db, "SELECT COUNT(DISTINCT deck_id) FROM corpus_deck_role"), decks
        ),
        "fingerprint": role_fingerprint(db),
    }


def _rulings(db: sqlite3.Connection) -> dict[str, object]:
    """Official rulings: rows and cards overall, and how much of the collection (the cards
    that carry an oracle id) has at least one ruling. A card without a row has no ruling
    published or was never imported — the two read apart only in ``rulings_for_card``."""
    total = _scalar(db, "SELECT COUNT(*) FROM card_ruling")
    with_oracle = _scalar(db, "SELECT COUNT(*) FROM card_fact WHERE oracle_id IS NOT NULL")
    covered = _scalar(
        db,
        "SELECT COUNT(DISTINCT f.card_id) FROM card_fact f "
        "JOIN card_ruling r ON r.oracle_id = f.oracle_id",
    )
    span = db.execute("SELECT MIN(published_at), MAX(published_at) FROM card_ruling").fetchone()
    return {
        "rows": total,
        "cards_with_rulings": _scalar(db, "SELECT COUNT(DISTINCT oracle_id) FROM card_ruling"),
        "collection_cards_with_rulings": _share(covered, with_oracle),
        "by_source": _counter(
            db, "SELECT ruling_source, COUNT(*) FROM card_ruling GROUP BY ruling_source"
        ),
        "published_earliest": None if span is None else span[0],
        "published_latest": None if span is None else span[1],
    }


def _corpus(db: sqlite3.Connection) -> dict[str, object]:
    decks = _scalar(db, "SELECT COUNT(*) FROM corpus_deck")
    card_rows = _scalar(db, "SELECT COUNT(*) FROM corpus_deck_card")
    with_rows = _scalar(db, "SELECT COUNT(DISTINCT deck_id) FROM corpus_deck_card")
    return {
        "decks": decks,
        "decks_without_card_rows": _share(decks - with_rows, decks),
        "decks_without_recorded_part": _share(
            _scalar(
                db,
                "SELECT COUNT(DISTINCT k.deck_id) FROM corpus_deck_card k "
                "LEFT JOIN corpus_deck_part p ON p.deck_id = k.deck_id "
                "WHERE p.deck_id IS NULL",
            ),
            with_rows,
        ),
        "mainboard_not_99_cards": _share(
            _scalar(
                db,
                "SELECT COUNT(*) FROM (SELECT deck_id FROM corpus_deck_card "
                "GROUP BY deck_id HAVING SUM(CASE WHEN LOWER(section) = 'mainboard' "
                "THEN quantity ELSE 0 END) != 99)",
            ),
            with_rows,
        ),
        "by_cohort": _counter(db, "SELECT cohort, COUNT(*) FROM corpus_deck GROUP BY cohort"),
        "fingerprint_missing": _share(
            _scalar(db, "SELECT COUNT(*) FROM corpus_deck WHERE fingerprint = ''"), decks
        ),
        "marked_duplicate_of_another": _share(
            _scalar(db, "SELECT COUNT(*) FROM corpus_deck WHERE duplicate_of IS NOT NULL"),
            decks,
        ),
        "date_unknown": _share(
            _scalar(
                db,
                "SELECT COUNT(*) FROM corpus_deck WHERE deck_date IS NULL OR deck_date = ''",
            ),
            decks,
        ),
        "address_missing": _share(
            _scalar(db, "SELECT COUNT(*) FROM corpus_deck WHERE url = ''"), decks
        ),
        "tags_missing": _share(
            _scalar(
                db,
                "SELECT COUNT(*) FROM corpus_deck WHERE tags IN ('', '[]', '{}', 'null')",
            ),
            decks,
        ),
        "card_rows": card_rows,
        "card_rows_without_oracle_id": _share(
            _scalar(db, "SELECT COUNT(*) FROM corpus_deck_card WHERE oracle_id IS NULL"),
            card_rows,
        ),
        "card_rows_by_normalization": _counter(
            db,
            "SELECT normalization_status, COUNT(*) FROM corpus_deck_card "
            "GROUP BY normalization_status",
        ),
    }


def _observations(db: sqlite3.Connection) -> dict[str, object]:
    total = _scalar(db, "SELECT COUNT(*) FROM observation")
    with_denominator = _scalar(db, "SELECT COUNT(*) FROM observation WHERE denominator IS NOT NULL")
    return {
        "rows": total,
        "by_data_class": _counter(
            db, "SELECT data_class, COUNT(*) FROM observation GROUP BY data_class"
        ),
        "time_unknown": _share(
            _scalar(db, "SELECT COUNT(*) FROM observation WHERE snapshot IS NULL OR snapshot = ''"),
            total,
        ),
        "denominator_missing": _share(total - with_denominator, total),
        "denominator_below_threshold": {
            "threshold": SMALL_DENOMINATOR,
            "count": _scalar(
                db,
                "SELECT COUNT(*) FROM observation WHERE denominator IS NOT NULL "
                "AND denominator < ?",
                (SMALL_DENOMINATOR,),
            ),
            "of": with_denominator,
        },
    }


def _marks_and_games(db: sqlite3.Connection) -> dict[str, object]:
    identities = _scalar(db, "SELECT COUNT(*) FROM card")
    return {
        "marks": {
            "favorites": _share(
                _scalar(db, "SELECT COUNT(*) FROM card_mark WHERE favorite != 0"), identities
            ),
            "excluded": _share(
                _scalar(db, "SELECT COUNT(*) FROM card_mark WHERE excluded != 0"), identities
            ),
            "with_note": _share(
                _scalar(db, "SELECT COUNT(*) FROM card_mark WHERE note != ''"), identities
            ),
        },
        "decks": {
            "decks": _scalar(db, "SELECT COUNT(*) FROM deck"),
            "revisions": _scalar(db, "SELECT COUNT(*) FROM deck_revision"),
        },
        "simulation": {
            "runs": _scalar(db, "SELECT COUNT(*) FROM simulation_run"),
            "games_completed": _scalar(
                db, "SELECT COALESCE(SUM(games_completed), 0) FROM simulation_run"
            ),
            "games_failed": _scalar(
                db, "SELECT COALESCE(SUM(games_failed), 0) FROM simulation_run"
            ),
        },
    }


def _selected(spec: dict[str, object], key: str) -> int:
    value = spec.get(key)
    return len(value) if isinstance(value, list) else 0


def _universe_entry(
    store: StudioStore, name: str, commanders: list[str], min_universe: int
) -> dict[str, object]:
    """One profile counted for one commander (or partner pair), with its own denominator."""
    counted = universe.inclusion(store, profile=name, card_names=[], commander_names=commanders)
    return {
        "commanders": commanders,
        "snapshot_id": universe.snapshot_id(store, profile=name, commander_names=commanders),
        "denominator": counted["denominator"],
        "denominator_by_platform": counted["denominator_by_platform"],
        "denominator_by_bracket": counted["denominator_by_bracket"],
        "excluded_no_date": counted["excluded_no_date"],
        "excluded_by_card_filter": counted["excluded_by_card_filter"],
        "min_universe": min_universe,
        "below_min_universe": counted["denominator"] < min_universe,
    }


def _universes(store: StudioStore) -> dict[str, object]:
    """The stored deck universes, counts only: per profile its version, spec shape (how
    many values each dimension selects — never the values) and, **per commander** that has
    bound source decks, the snapshot, denominator with both breakdowns and the decks its
    date and card filters drop.

    A profile is never counted over all commanders at once: that denominator would mix
    the decks of several commanders and ``below_min_universe`` computed from it would be
    meaningless. A profile that names its commanders is reported for exactly that set."""
    details: list[dict[str, object]] = []
    below = 0
    entries_total = 0
    sets = universe.bound_commander_sets(store)
    for profile in universe.list_profiles(store):
        name = str(profile["name"])
        spec = cast("dict[str, object]", profile["spec"])
        min_universe = spec.get("min_universe")
        effective = min_universe if isinstance(min_universe, int) else TierParams().min_universe
        named = spec.get("commanders")
        wanted = (
            [sorted(str(item) for item in named)] if isinstance(named, list) and named else sets
        )
        per_commander = [
            _universe_entry(store, name, commanders, effective) for commanders in wanted
        ]
        below += sum(1 for entry in per_commander if entry["below_min_universe"])
        entries_total += len(per_commander)
        details.append(
            {
                "version": profile["version"],
                "created_at": profile["created_at"],
                "updated_at": profile["updated_at"],
                "spec_dimensions": {
                    "platforms": _selected(spec, "platforms"),
                    "cohorts": _selected(spec, "cohorts"),
                    "commanders": _selected(spec, "commanders"),
                    "must_contain_cards": _selected(spec, "must_contain"),
                    "date_filter": bool(spec.get("date_from") or spec.get("date_to")),
                    "min_main_cards": spec.get("min_main_cards"),
                },
                "min_universe": effective,
                "per_commander": per_commander,
            }
        )
    return {
        "profiles": len(details),
        "model_version": MODEL_VERSION,
        "commander_sets": len(sets),
        "entries": entries_total,
        "below_min_universe": below,
        "details": details,
    }


def _commander_names(db: sqlite3.Connection) -> list[str]:
    names = {
        str(row[0])
        for row in db.execute("SELECT DISTINCT commander_name FROM commander_binding")
        if row[0]
    }
    names |= {
        str(row[0])
        for row in db.execute("SELECT DISTINCT commander_name FROM card_signal")
        if row[0]
    }
    return sorted(names)


def _commanders(store: StudioStore) -> dict[str, object]:
    """Per commander, counts only: the pool (legal collection cards inside the colour
    identity), the cards left out because their legality is unknown (listed as unknown,
    never as illegal) and the signal layer — rows per signal and the coverage over the pool
    (cards with a value / pool size). No collection card name appears; the commander names
    are the keys every figure is bound to."""
    db = store.connection
    details: list[dict[str, object]] = []
    # Read once for the whole sweep, not once per commander: the stored signal rows.
    signal_rows = signals.store_signal_rows_by_commander(store)
    for name in _commander_names(db):
        entry: dict[str, object] = {"commander": name}
        try:
            counts = builder.pool_counts(store, [name])
            coverage = strength_view.signal_coverage(store, name)
        except KeyError:
            entry["in_collection"] = False  # a name without a collection card: no pool
            entry["pool"] = None
            entry["signals"] = {
                signal: {
                    "rows": _scalar(
                        db,
                        "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal = ?",
                        (name, signal),
                    )
                }
                for signal in _counter(
                    db, "SELECT signal, COUNT(*) FROM card_signal GROUP BY signal"
                )
            }
            entry["signal_rate_alarms"] = signals.compute_store_signal_rate_alarms(
                store, commander=name, rows_by_commander=signal_rows
            )
            details.append(entry)
            continue
        entry["in_collection"] = True
        entry["pool"] = {
            "legal_cards": counts["legal"],
            "collection_cards_in_identity": counts["in_identity"],
            "excluded_legality_unknown": counts["legality_unknown"],
            "excluded_not_legal": counts["not_legal"],
        }
        entry["signals"] = {signal: dict(item) for signal, item in coverage.items()}
        entry["signal_rate_alarms"] = signals.compute_store_signal_rate_alarms(
            store, commander=name, rows_by_commander=signal_rows
        )
        details.append(entry)
    return {
        "commanders": len(details),
        "legality_unknown_in_collection": builder.legality_unknown_in_collection(store),
        "details": details,
    }


def data_report(
    store: StudioStore,
    *,
    today: date | None = None,
    commander: str | None = None,
) -> dict[str, object]:
    """The counts-only report. ``today`` is only injectable for tests."""
    from commander_lab.bridge_qualification import bridge_qualification

    from .field_read import store_fallbacks_used

    db = store.connection
    moment = today or datetime.now(UTC).date()
    return {
        "schema": REPORT_SCHEMA,
        "generated_on": moment.isoformat(),
        "privacy": (
            "counts only: no card names (except the commander names the figures are bound to), "
            "no deck addresses, no notes"
        ),
        "bridge_qualification": bridge_qualification(),
        "collection": _collection(db),
        "scryfall_facts": _scryfall(db, moment),
        "source_status": _source_status(db, moment),
        "roles": _roles(db),
        "rulings": _rulings(db),
        "corpus": _corpus(db),
        "corpus_audit": corpus_audit(db, today=moment),
        "observations": _observations(db),
        "universes": _universes(store),
        "commanders": _commanders(store),
        "signal_rate_alarms": signals.compute_store_signal_rate_alarms(store, commander=commander),
        "fallbacks_used": store_fallbacks_used(store),
        **_marks_and_games(db),
        "not_measured_here": list(NOT_MEASURED),
    }


def build_data_report(
    store: StudioStore,
    *,
    today: date | None = None,
    commander: str | None = None,
) -> dict[str, object]:
    """Alias for ``data_report`` (#1416)."""
    return data_report(store, today=today, commander=commander)


def format_data_report(report: dict[str, object]) -> str:
    """Render the data report as human-readable text with visible signal rate alarms (#1416)."""
    lines = [
        "Datenbericht (nur Zählungen):",
        json.dumps(report, indent=2, ensure_ascii=False),
    ]
    raw_fallbacks = report.get("fallbacks_used")
    if isinstance(raw_fallbacks, dict) and raw_fallbacks:
        lines.append("")
        lines.append("Defensive Feld-Fallbacks (#1453):")
        for fb_key, fb_cnt in sorted(raw_fallbacks.items()):
            lines.append(f"- FALLBACK: {fb_key}: {fb_cnt}")
    raw_alarms = report.get("signal_rate_alarms")
    alarms = (
        [item for item in raw_alarms if isinstance(item, dict)]
        if isinstance(raw_alarms, list)
        else []
    )
    if alarms:
        lines.append("")
        lines.append("Raten-Alarme für Kernsignale:")
        for alarm in alarms:
            msg = alarm.get("message")
            if isinstance(msg, str) and msg:
                lines.append(f"- WARNUNG: {msg}")
            else:
                sig = alarm.get("signal_name", "")
                atype = alarm.get("alarm_type", "")
                count = alarm.get("count", 0)
                den = alarm.get("denominator", 0)
                rate = (
                    float(alarm.get("rate", 0.0)) * 100.0
                    if isinstance(alarm.get("rate"), int | float)
                    else 0.0
                )
                thresh = (
                    float(alarm.get("threshold", 0.0)) * 100.0
                    if isinstance(alarm.get("threshold"), int | float)
                    else 0.0
                )
                lines.append(
                    f"- WARNUNG: {sig} ({atype}): {count}/{den} ({rate:.1f} %) > {thresh:.0f} %"
                )
    return "\n".join(lines)
