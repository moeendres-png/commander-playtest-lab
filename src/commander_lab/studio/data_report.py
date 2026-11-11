"""Counts-only report on how complete the Studio store is (Refs #1182).

The report answers "what do we have, what is missing, what is unknown" with numbers: every
figure is a count with its denominator, a missing value is counted as unknown (never as zero),
and no card name, deck address or note text leaves the database. It can therefore be pasted
into an issue or a Drive document.

``role_fingerprint`` hashes the role tables so that a before/after comparison around an import
shows at a glance whether anything outside the imported scope changed.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, date, datetime

from .roles import ORIGIN_CROSSWALK, ORIGIN_TAGGER, ROLES
from .store import StudioStore

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
    }


def data_report(store: StudioStore, *, today: date | None = None) -> dict[str, object]:
    """The counts-only report. ``today`` is only injectable for tests."""
    db = store.connection
    moment = today or datetime.now(UTC).date()
    return {
        "schema": REPORT_SCHEMA,
        "generated_on": moment.isoformat(),
        "privacy": "counts only: no card names, no deck addresses, no notes",
        "collection": _collection(db),
        "scryfall_facts": _scryfall(db, moment),
        "roles": _roles(db),
        "corpus": _corpus(db),
        "observations": _observations(db),
        **_marks_and_games(db),
        "not_measured_here": list(NOT_MEASURED),
    }
