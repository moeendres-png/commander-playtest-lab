"""Deck revisions: immutable 100-card snapshots with a content hash, and their data checks.

The checks here are construction checks on data (count, singleton, color identity, ownership).
They do not adjudicate Magic rules; the pinned Rules Core's deck import stays the binding
readiness check before a game.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .store import StudioStore, now_utc

DECK_SIZE = 100
_COLORS = frozenset("WUBRG")


@dataclass(frozen=True)
class RevisionCard:
    card_id: str
    quantity: int = 1
    zone: str = "main"


@dataclass(frozen=True)
class DeckIssue:
    """One finding of the data check. ``severity`` is ``error`` or ``warning``."""

    code: str
    severity: str
    message: str
    card_id: str | None = None


def color_set(color_identity: str | None) -> frozenset[str]:
    return frozenset(letter for letter in (color_identity or "") if letter in _COLORS)


def deck_hash(cards: Iterable[RevisionCard]) -> str:
    """Content hash of a revision: independent of input order, sensitive to every card."""
    canonical = sorted((card.zone, card.card_id, card.quantity) for card in cards)
    payload = json.dumps(canonical, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _merge(cards: Iterable[RevisionCard]) -> list[RevisionCard]:
    merged: dict[tuple[str, str], int] = {}
    for card in cards:
        if card.quantity <= 0:
            raise ValueError(f"quantity must be positive: {card.card_id}")
        if card.zone not in {"main", "commander"}:
            raise ValueError(f"unknown zone: {card.zone}")
        merged[(card.zone, card.card_id)] = merged.get((card.zone, card.card_id), 0) + card.quantity
    return [RevisionCard(card_id, qty, zone) for (zone, card_id), qty in sorted(merged.items())]


def create_revision(
    store: StudioStore,
    *,
    deck_id: str,
    name: str,
    cards: Iterable[RevisionCard],
    parent_revision_id: str | None = None,
    note: str = "",
    source_id: str | None = None,
    branch: str = "main",
) -> str:
    """Store a new immutable revision and move ``branch`` to it. Returns the revision id.

    The same content under the same deck gives the same id, so storing it twice changes
    nothing. An incomplete or illegal list may be stored: a deck under construction is a
    revision too. ``validate_revision`` says what is wrong with it.
    """
    merged = _merge(cards)
    digest = deck_hash(merged)
    revision_id = f"{deck_id}@{digest[:16]}"
    db = store.connection
    known = {str(row[0]) for row in db.execute("SELECT card_id FROM card")}
    missing = sorted({card.card_id for card in merged} - known)
    if missing:
        raise ValueError(f"unknown card ids: {missing[:5]}")
    with db:
        db.execute(
            "INSERT OR IGNORE INTO deck(deck_id, name, created_at) VALUES (?, ?, ?)",
            (deck_id, name, now_utc()),
        )
        exists = db.execute(
            "SELECT 1 FROM deck_revision WHERE revision_id = ?", (revision_id,)
        ).fetchone()
        if exists is None:
            db.execute(
                "INSERT INTO deck_revision(revision_id, deck_id, parent_revision_id, deck_hash, "
                "note, source_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (revision_id, deck_id, parent_revision_id, digest, note, source_id, now_utc()),
            )
            db.executemany(
                "INSERT INTO deck_revision_card(revision_id, card_id, zone, quantity) "
                "VALUES (?, ?, ?, ?)",
                [(revision_id, card.card_id, card.zone, card.quantity) for card in merged],
            )
        db.execute(
            "INSERT INTO deck_branch(deck_id, branch, revision_id) VALUES (?, ?, ?) "
            "ON CONFLICT(deck_id, branch) DO UPDATE SET revision_id = excluded.revision_id",
            (deck_id, branch, revision_id),
        )
    return revision_id


_ROW_COLUMNS = (
    "rc.card_id, rc.zone, rc.quantity, c.oracle_name, c.engine_name, "
    "c.color_identity, c.is_basic_land, c.commander_legal, c.type_line, c.oracle_text, "
    "c.mana_cost, c.mana_value, c.produced_mana, c.layout, "
    "i.available_lower_bound, i.reserved "
)


def revision_rows(store: StudioStore, revision_id: str) -> list[sqlite3.Row]:
    rows = store.connection.execute(
        f"SELECT {_ROW_COLUMNS} FROM deck_revision_card rc JOIN card_fact c USING (card_id) "
        "LEFT JOIN inventory i USING (card_id) WHERE rc.revision_id = ? "
        "ORDER BY rc.zone, c.oracle_name",
        (revision_id,),
    ).fetchall()
    if not rows:
        raise KeyError(revision_id)
    return rows


def list_rows(store: StudioStore, cards: Iterable[RevisionCard]) -> list[sqlite3.Row]:
    """The same rows as ``revision_rows`` for a list that is not stored as a revision."""
    db = store.connection
    db.execute(
        "CREATE TEMP TABLE IF NOT EXISTS work_list "
        "(card_id TEXT NOT NULL, zone TEXT NOT NULL, quantity INTEGER NOT NULL)"
    )
    db.execute("DELETE FROM work_list")
    db.executemany(
        "INSERT INTO work_list(card_id, zone, quantity) VALUES (?, ?, ?)",
        [(card.card_id, card.zone, card.quantity) for card in _merge(cards)],
    )
    return db.execute(
        f"SELECT {_ROW_COLUMNS} FROM work_list rc JOIN card_fact c USING (card_id) "
        "LEFT JOIN inventory i USING (card_id) ORDER BY rc.zone, c.oracle_name"
    ).fetchall()


def _any_number_allowed(row: sqlite3.Row) -> bool:
    text = str(row["oracle_text"] or "")
    return bool(row["is_basic_land"]) or "A deck can have any number of cards named" in text


def validate_revision(
    store: StudioStore, revision_id: str, *, owned_only: bool = True
) -> list[DeckIssue]:
    """Data check of one revision. An empty list means: nothing found."""
    return validate_rows(revision_rows(store, revision_id), owned_only=owned_only)


def validate_rows(rows: Sequence[sqlite3.Row], *, owned_only: bool = True) -> list[DeckIssue]:
    """Data check of deck rows (from ``revision_rows`` or ``list_rows``)."""
    issues: list[DeckIssue] = []
    commanders = [row for row in rows if row["zone"] == "commander"]
    total = sum(int(row["quantity"]) for row in rows)
    if total != DECK_SIZE:
        issues.append(
            DeckIssue("deck_size", "error", f"{total} cards, a Commander deck has {DECK_SIZE}")
        )
    if not 1 <= sum(int(row["quantity"]) for row in commanders) <= 2:
        issues.append(DeckIssue("commander_count", "error", "one or two commanders are needed"))
    identity: frozenset[str] = frozenset()
    for row in commanders:
        identity |= color_set(row["color_identity"])
        type_line = str(row["type_line"] or "")
        if type_line and "Legendary" not in type_line:
            issues.append(
                DeckIssue(
                    "commander_type",
                    "warning",
                    f"{row['oracle_name']}: type line is not legendary; commander eligibility "
                    "is decided by the Rules Core",
                    row["card_id"],
                )
            )
    per_card: dict[str, int] = {}
    for row in rows:
        per_card[row["card_id"]] = per_card.get(row["card_id"], 0) + int(row["quantity"])
    seen: set[str] = set()
    for row in rows:
        card_id = str(row["card_id"])
        name = str(row["oracle_name"])
        if card_id in seen:
            continue
        seen.add(card_id)
        quantity = per_card[card_id]
        if commanders and not color_set(row["color_identity"]) <= identity:
            issues.append(
                DeckIssue(
                    "color_identity", "error", f"{name}: outside the commander's colors", card_id
                )
            )
        if quantity > 1 and not _any_number_allowed(row):
            issues.append(DeckIssue("singleton", "error", f"{name}: {quantity} copies", card_id))
        legal = row["commander_legal"]
        if legal is None:
            issues.append(
                DeckIssue("legality_unknown", "warning", f"{name}: legality unknown", card_id)
            )
        elif not legal:
            issues.append(
                DeckIssue("not_legal", "error", f"{name}: not legal in Commander", card_id)
            )
        if owned_only:
            available = row["available_lower_bound"]
            if available is None:
                issues.append(
                    DeckIssue("not_owned", "error", f"{name}: not in the collection", card_id)
                )
            elif quantity > int(available):
                issues.append(
                    DeckIssue(
                        "not_available",
                        "error",
                        f"{name}: {quantity} needed, {available} free"
                        + (f" ({row['reserved']} reserved)" if row["reserved"] else ""),
                        card_id,
                    )
                )
    return issues


def lab_snapshot(
    store: StudioStore, revision_id: str, *, name: str | None = None
) -> dict[str, object]:
    """The revision in the on-disk deck snapshot format of ``DECKBAU_INTERFACE.md``."""
    rows = revision_rows(store, revision_id)
    header = store.connection.execute(
        "SELECT d.deck_id, d.name, r.deck_hash FROM deck_revision r JOIN deck d USING (deck_id) "
        "WHERE r.revision_id = ?",
        (revision_id,),
    ).fetchone()
    commanders = [str(row["engine_name"]) for row in rows if row["zone"] == "commander"]
    return {
        "deck_id": str(header["deck_id"]),
        "name": name or str(header["name"]),
        "studio_revision_id": revision_id,
        "studio_deck_hash": str(header["deck_hash"]),
        "commander": {
            "commanders": commanders,
            "uses_partner": len(commanders) > 1,
            "commander_identity_override": None,
        },
        "cards": [
            {
                "oracle_name": str(row["engine_name"]),
                "quantity": int(row["quantity"]),
                "zone": str(row["zone"]),
            }
            for row in rows
        ],
    }
