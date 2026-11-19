"""Read-only audit of the counted Chulane corpus decks (Refs #1549).

Per deck it checks four formal points and only counts: nothing is written, deleted or changed
(``corpus_deck.legality_audit`` stays as it is, no deck leaves a denominator). The points are

* ``card_count_not_100``: commander plus main section quantities differ from 100,
* ``commander_not_chulane``: the commander section does not hold Chulane,
* ``card_not_legal``: a commander/main card is banned or not legal in Commander,
* ``outside_identity``: a commander/main card lies outside Chulane's colour identity.

A card without an oracle id, without a Scryfall row or with unknown legality is never counted
as legal: it makes the deck ``unbekannt`` for that point (counted separately), not clean. A deck
is ``befund`` with at least one finding, ``unbekannt`` without a finding but with an
unmeasurable point, otherwise ``ohne_befund``. The report holds counts with denominators and the
date of the card facts, no card names and no deck addresses. Cohort dimensions (source, bracket,
variant) are listed one by one and never crossed; a deck without a value in a dimension is
counted under ``unbekannt``.

Source data is read bound to Chulane only (``builder.bound_to``, ``AGENTS.md`` §1): a deck bound
to another commander, to a pair or to none is not audited and does not raise any count; the
decks outside the binding are reported as their own numbers (``binding``), so the audit N is
the same figure as ``cohort_sizes`` ("Alle") of the deck builder.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .builder import bound_to
from .decklist_import import COMMANDER_NAME
from .decks import color_set

AUDIT_SCHEMA = "studio-corpus-audit-1"
DECK_SECTIONS = ("commander", "main")
REASONS = ("card_count_not_100", "commander_not_chulane", "card_not_legal", "outside_identity")
DIMENSIONS = ("source", "bracket", "variant")
UNKNOWN = "unbekannt"
_ILLEGAL = ("banned", "not_legal")


@dataclass
class DeckAudit:
    """Outcome of one deck: reasons found and the points that could not be measured."""

    reasons: list[str] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)
    has_cards: bool = False

    @property
    def status(self) -> str:
        if self.reasons:
            return "befund"
        return "unbekannt" if self.unmeasured else "ohne_befund"


def _chulane(db: sqlite3.Connection) -> tuple[str | None, frozenset[str] | None]:
    row = db.execute(
        "SELECT oracle_id, color_identity FROM scryfall_card WHERE name = ?", (COMMANDER_NAME,)
    ).fetchone()
    if row is None:
        return None, None
    return str(row[0]), color_set(str(row[1]))


def _bound() -> tuple[str, list[str]]:
    return bound_to("corpus_deck", "d.deck_id", [COMMANDER_NAME])


def audit_decks(db: sqlite3.Connection) -> dict[str, DeckAudit]:
    """Audit every counted deck (``duplicate_of IS NULL``) bound to Chulane; returns deck id to
    outcome. Decks of another commander or without a binding are not read."""
    chulane_id, identity = _chulane(db)
    bound, bound_args = _bound()
    decks = {
        str(r[0]): DeckAudit()
        for r in db.execute(
            f"SELECT d.deck_id FROM corpus_deck d WHERE d.duplicate_of IS NULL{bound}", bound_args
        )
    }
    total: dict[str, int] = defaultdict(int)
    has_chulane: set[str] = set()
    illegal: set[str] = set()
    legality_unknown: set[str] = set()
    outside: set[str] = set()
    identity_unknown: set[str] = set()
    rows = db.execute(
        "SELECT k.deck_id, k.section, k.quantity, k.oracle_id, s.commander_legality, "
        "s.color_identity FROM corpus_deck_card k "
        "LEFT JOIN scryfall_card s ON s.oracle_id = k.oracle_id "
        "WHERE k.section IN (?, ?)",
        DECK_SECTIONS,
    )
    for deck_id, section, quantity, oracle_id, legality, colours in rows:
        if deck_id not in decks:
            continue
        total[deck_id] += int(quantity)
        if section == "commander" and chulane_id is not None and oracle_id == chulane_id:
            has_chulane.add(deck_id)
        if legality in _ILLEGAL:
            illegal.add(deck_id)
        elif legality != "legal":
            legality_unknown.add(deck_id)
        if colours is None or identity is None:
            identity_unknown.add(deck_id)
        elif not color_set(str(colours)) <= identity:
            outside.add(deck_id)
    for deck_id, audit in decks.items():
        if deck_id not in total:
            audit.unmeasured.extend(REASONS)
            continue
        audit.has_cards = True
        if total[deck_id] != 100:
            audit.reasons.append("card_count_not_100")
        if chulane_id is None:
            audit.unmeasured.append("commander_not_chulane")
        elif deck_id not in has_chulane:
            audit.reasons.append("commander_not_chulane")
        if deck_id in illegal:
            audit.reasons.append("card_not_legal")
        elif deck_id in legality_unknown:
            audit.unmeasured.append("card_not_legal")
        if deck_id in outside:
            audit.reasons.append("outside_identity")
        elif deck_id in identity_unknown:
            audit.unmeasured.append("outside_identity")
    return decks


def _bucket() -> dict[str, int]:
    return {"decks": 0, "befund": 0, "unbekannt": 0, "ohne_befund": 0}


def _facts_date(db: sqlite3.Connection, today: date) -> dict[str, object]:
    row = db.execute(
        "SELECT MAX(s.snapshot_date) FROM source s "
        "WHERE s.source_id IN (SELECT DISTINCT source_id FROM scryfall_card)"
    ).fetchone()
    snapshot = str(row[0]) if row is not None and row[0] else None
    age: int | None = None
    if snapshot:
        try:
            age = (today - date.fromisoformat(snapshot[:10])).days
        except ValueError:
            age = None
    return {
        "card_facts_snapshot_date": snapshot or UNKNOWN,
        "card_facts_age_days": age if age is not None else UNKNOWN,
    }


def _binding(db: sqlite3.Connection, bound_decks: int) -> dict[str, object]:
    """Counted decks (``duplicate_of IS NULL``) outside the audit: ``other_commander_decks``
    holds every other binding (another commander, or a pair, also a pair with Chulane) and
    ``unbound_decks`` the decks bound to none. Same arithmetic as ``builder.corpus_binding``."""
    total = int(
        db.execute("SELECT COUNT(*) FROM corpus_deck WHERE duplicate_of IS NULL").fetchone()[0]
    )
    unbound = int(
        db.execute(
            "SELECT COUNT(*) FROM corpus_deck d WHERE d.duplicate_of IS NULL AND NOT EXISTS "
            "(SELECT 1 FROM commander_binding cb WHERE cb.kind = 'corpus_deck' "
            "AND cb.key = d.deck_id)"
        ).fetchone()[0]
    )
    return {
        "commander": COMMANDER_NAME,
        "bound_decks": bound_decks,
        "other_commander_decks": total - bound_decks - unbound,
        "unbound_decks": unbound,
        "of": total,
    }


def corpus_audit(db: sqlite3.Connection, *, today: date) -> dict[str, object]:
    """Counts-only audit section for the data report; never writes. Bound to Chulane."""
    decks = audit_decks(db)
    n_decks = len(decks)
    with_cards = sum(1 for a in decks.values() if a.has_cards)
    bound, bound_args = _bound()
    all_rows = int(
        db.execute(f"SELECT COUNT(*) FROM corpus_deck d WHERE 1{bound}", bound_args).fetchone()[0]
    )
    by_reason = {
        reason: {
            "count": sum(1 for a in decks.values() if reason in a.reasons),
            "of": n_decks,
            "not_measurable": sum(1 for a in decks.values() if reason in a.unmeasured),
        }
        for reason in REASONS
    }
    status = {
        s: sum(1 for a in decks.values() if a.status == s)
        for s in ("befund", "unbekannt", "ohne_befund")
    }
    cohort: dict[str, dict[str, dict[str, int]]] = {dim: {} for dim in DIMENSIONS}
    values: dict[str, dict[str, set[str]]] = {dim: defaultdict(set) for dim in DIMENSIONS}
    for deck_id, name in db.execute(
        "SELECT c.deck_id, c.cohort FROM corpus_cohort c JOIN corpus_deck d USING (deck_id) "
        f"WHERE d.duplicate_of IS NULL{bound}",
        bound_args,
    ):
        dim, _, value = str(name).partition(":")
        if dim in values and deck_id in decks and value:
            values[dim][str(deck_id)].add(value)
    for dim in DIMENSIONS:
        for deck_id, audit in decks.items():
            for value in sorted(values[dim].get(deck_id) or {UNKNOWN}):
                bucket = cohort[dim].setdefault(value, _bucket())
                bucket["decks"] += 1
                bucket[audit.status] += 1
    return {
        "schema": AUDIT_SCHEMA,
        "origin": "corpus_deck_card + scryfall_card (read only, nothing written)",
        "cohort": (
            "commander:chulane (commander_binding, exactly this commander), "
            "counted decks (duplicate_of IS NULL)"
        ),
        "decks_counted": _share_of(n_decks, all_rows),
        "binding": _binding(db, n_decks),
        "decks_with_card_rows": _share_of(with_cards, n_decks),
        "status": {**status, "of": n_decks},
        "by_reason": by_reason,
        "by_cohort_dimension": cohort,
        **_facts_date(db, today),
        "note": (
            "decks with a finding stay in every denominator; "
            "unbekannt means a point could not be measured, not that it passed"
        ),
        "notes": [
            "card_not_legal also counts token rows from the import (not_legal, e.g. Treasure, "
            "Eldrazi, Merfolk); a deck can be listed for a token alone, not only for a banned card",
            "card rows without an oracle id are tokens; they raise the card count and are "
            "counted as they are (nothing is filtered or changed)",
            "companion and sideboard rows are outside the 100 and not counted",
        ],
    }


def _share_of(count: int, of: int) -> dict[str, int]:
    return {"count": count, "of": of}
