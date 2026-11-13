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
import sqlite3
from datetime import UTC, date, datetime
from typing import cast

from . import builder, strength_view, universe
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
        details.append(entry)
    return {
        "commanders": len(details),
        "legality_unknown_in_collection": builder.legality_unknown_in_collection(store),
        "details": details,
    }


def data_report(store: StudioStore, *, today: date | None = None) -> dict[str, object]:
    """The counts-only report. ``today`` is only injectable for tests."""
    db = store.connection
    moment = today or datetime.now(UTC).date()
    return {
        "schema": REPORT_SCHEMA,
        "generated_on": moment.isoformat(),
        "privacy": (
            "counts only: no card names (except the commander names the figures are bound to), "
            "no deck addresses, no notes"
        ),
        "collection": _collection(db),
        "scryfall_facts": _scryfall(db, moment),
        "roles": _roles(db),
        "corpus": _corpus(db),
        "observations": _observations(db),
        "universes": _universes(store),
        "commanders": _commanders(store),
        **_marks_and_games(db),
        "not_measured_here": list(NOT_MEASURED),
    }
