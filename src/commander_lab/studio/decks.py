"""Deck revisions: immutable 100-card snapshots with a content hash, and their data checks.

The checks here are construction checks on data (count, singleton, color identity, ownership).
They do not adjudicate Magic rules; the pinned Rules Core's deck import stays the binding
readiness check before a game.
"""

from __future__ import annotations

import hashlib
import json
import re
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
    # The work list is a connection-private TEMP table. Filling it opens a transaction; when
    # none was open before, it is closed right away (it holds only this temp table), so the
    # per-store-state cache (``cache.cached``, which stands aside during an open transaction)
    # keeps serving later reads of the same request.
    was_open = db.in_transaction
    db.execute(
        "CREATE TEMP TABLE IF NOT EXISTS work_list "
        "(card_id TEXT NOT NULL, zone TEXT NOT NULL, quantity INTEGER NOT NULL)"
    )
    db.execute("DELETE FROM work_list")
    db.executemany(
        "INSERT INTO work_list(card_id, zone, quantity) VALUES (?, ?, ?)",
        [(card.card_id, card.zone, card.quantity) for card in _merge(cards)],
    )
    if not was_open:
        db.commit()
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
            DeckIssue("deck_size", "error", f"{total} Karten (ein Commander-Deck hat {DECK_SIZE})")
        )
    if not 1 <= sum(int(row["quantity"]) for row in commanders) <= 2:
        issues.append(DeckIssue("commander_count", "error", "1 oder 2 Commander sind erforderlich"))
    identity: frozenset[str] = frozenset()
    for row in commanders:
        identity |= color_set(row["color_identity"])
        type_line = str(row["type_line"] or "")
        if type_line and "Legendary" not in type_line:
            issues.append(
                DeckIssue(
                    "commander_type",
                    "warning",
                    f"{row['oracle_name']}: Typzeile ist nicht legendär; die Commander-Eignung "
                    "entscheidet der Regelkern",
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
                    "color_identity",
                    "error",
                    f"{name}: außerhalb der Farbidentität des Commanders",
                    card_id,
                )
            )
        if quantity > 1 and not _any_number_allowed(row):
            issues.append(
                DeckIssue("singleton", "error", f"{name}: {quantity} Kopien im Deck", card_id)
            )
        legal = row["commander_legal"]
        if legal is None:
            issues.append(
                DeckIssue(
                    "legality_unknown", "warning", f"{name}: Commander-Legalität unbekannt", card_id
                )
            )
        elif not legal:
            issues.append(
                DeckIssue("not_legal", "error", f"{name}: in Commander nicht legal", card_id)
            )
        if owned_only:
            available = row["available_lower_bound"]
            if available is None:
                issues.append(
                    DeckIssue("not_owned", "error", f"{name}: nicht in deiner Sammlung", card_id)
                )
            elif quantity > int(available):
                issues.append(
                    DeckIssue(
                        "not_available",
                        "error",
                        f"{name}: {quantity} benötigt, {available} frei"
                        + (f" ({row['reserved']} reserviert)" if row["reserved"] else ""),
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


_SECTION_HEADERS = frozenset(
    {
        "commander",
        "commander:",
        "commanders",
        "commanders:",
        "deck",
        "deck:",
        "main",
        "main:",
        "mainboard",
        "mainboard:",
        "sideboard",
        "sideboard:",
        "maybeboard",
        "maybeboard:",
    }
)


# Trailing annotations of common export formats, removed before the name is matched and
# reported per line (never silently): Moxfield foil/etched marks, Archidekt categories,
# Deckstats commander marks, inline comments.
_ANNOTATIONS = (
    ("Archidekt-Kategorie", re.compile(r"\s*\[[^\]]*\]")),
    ("Archidekt-Markierung", re.compile(r"\s*\^[^^]*\^")),
    ("Foil/Etched-Markierung", re.compile(r"\s*\*(?:F|E|CMDR)\*", re.I)),
    ("Kommentar", re.compile(r"\s+#.*$")),
)
_PRINTING = re.compile(r"\s+\(([A-Za-z0-9]{2,6})\)(?:\s+[A-Za-z0-9-]+[a-z★]?)?\s*$")
_LINE = re.compile(r"^(?:(\d+)\s*[xX]?\s+)?(.+?)\s*$")
_SKIP_SECTIONS = {"sideboard", "maybeboard", "cuts", "considering", "tokens"}
_MAIN_SECTIONS = {"deck", "main", "mainboard", "companion"}
_COMMANDER_SECTIONS = {"commander", "commanders"}


def parse_decklist_text(
    store: StudioStore,
    commander_names: Sequence[str],
    text: str,
) -> dict[str, object]:
    """Parse a pasted deck list against the collection, line by line (#1404 D5, option 4).

    Accepts plain ``1 Card`` / ``1x Card`` lines and the usual export forms: a printing in
    brackets (``(C21) 263``), Moxfield ``*F*``/``*E*``, Archidekt ``[Category]`` and ``^Tag^``,
    Deckstats ``*CMDR*``, section headers (Commander, Deck, Sideboard, Maybeboard ...) and
    comment lines. Every non-empty line gets a status; nothing is dropped silently:

    ``matched`` (in the collection, legal, inside the colour identity, enough free copies),
    ``insufficient`` (fewer free copies than asked: the free ones are taken),
    ``outside_identity``, ``not_legal``, ``not_in_collection`` (no purchase wording),
    ``commander`` (the chosen commander itself), ``other_commander`` (a commander line naming
    another card), ``skipped_section`` (sideboard and the like), ``unreadable``.
    Printings and annotations are reported as ignored. Only ``matched`` and ``insufficient``
    cards enter the list; the page shows the preview before anything is taken over.
    """
    from . import builder

    identity, commander_ids = builder.commander_identity(store, commander_names)
    cmd_set = set(commander_ids)
    by_name: dict[str, dict[str, object]] = {}
    for row in store.connection.execute(
        "SELECT c.card_id, c.oracle_name, c.engine_name, c.color_identity, "
        "c.commander_legal, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id)"
    ):
        info = {
            "card_id": str(row["card_id"]),
            "name": str(row["oracle_name"]),
            "available": int(row["available_lower_bound"] or 0),
            "legal": row["commander_legal"],
            "in_identity": color_set(row["color_identity"]) <= identity,
        }
        by_name.setdefault(str(row["oracle_name"]).casefold(), info)
        if row["engine_name"]:
            by_name.setdefault(str(row["engine_name"]).casefold(), info)
        by_name.setdefault(str(row["oracle_name"]).split(" // ")[0].strip().casefold(), info)

    lines: list[dict[str, object]] = []
    matched_qty: dict[str, int] = {}
    matched_info: dict[str, dict[str, object]] = {}
    section = "main"
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        header = line.casefold().rstrip(":").strip()
        if header in _SKIP_SECTIONS | _MAIN_SECTIONS | _COMMANDER_SECTIONS:
            section = (
                "skip"
                if header in _SKIP_SECTIONS
                else "commander"
                if header in _COMMANDER_SECTIONS
                else "main"
            )
            continue
        ignored: list[str] = []
        body = line
        commander_mark = bool(re.search(r"\*CMDR\*", body, re.I))
        for label, pattern in _ANNOTATIONS:
            if pattern.search(body):
                ignored.append(label)
                body = pattern.sub("", body)
        printing = _PRINTING.search(body)
        if printing:
            ignored.append(f"Druckangabe ({printing.group(1).upper()})")
            body = body[: printing.start()]
        match = _LINE.match(body.strip())
        entry: dict[str, object] = {"line": number, "text": line, "ignored": ignored}
        if not match or not match.group(2).strip() or (match.group(1) and int(match.group(1)) <= 0):
            lines.append({**entry, "status": "unreadable"})
            continue
        quantity = int(match.group(1) or "1")
        name = match.group(2).strip()
        if name.casefold() in _SECTION_HEADERS:
            continue
        entry.update({"name": name, "quantity": quantity})
        if section == "skip":
            lines.append({**entry, "status": "skipped_section"})
            continue
        found = by_name.get(name.casefold()) or by_name.get(
            name.split(" // ")[0].strip().casefold()
        )
        if found is None:
            lines.append({**entry, "status": "not_in_collection"})
            continue
        card_id = str(found["card_id"])
        entry.update({"card_id": card_id, "name": found["name"]})
        if card_id in cmd_set:
            lines.append({**entry, "status": "commander"})
            continue
        if section == "commander" or commander_mark:
            lines.append({**entry, "status": "other_commander"})
            continue
        if found["legal"] != 1:
            lines.append({**entry, "status": "not_legal"})
            continue
        if not found["in_identity"]:
            lines.append({**entry, "status": "outside_identity"})
            continue
        already = matched_qty.get(card_id, 0)
        free = int(str(found["available"])) - already
        take = max(0, min(quantity, free))
        if take < quantity:
            lines.append(
                {**entry, "status": "insufficient", "taken": take, "available": found["available"]}
            )
        else:
            lines.append({**entry, "status": "matched", "taken": take})
        if take:
            matched_qty[card_id] = already + take
            matched_info[card_id] = found

    cards = [RevisionCard(cid, 1, "commander") for cid in commander_ids] + [
        RevisionCard(cid, qty, "main") for cid, qty in matched_qty.items()
    ]
    matched_list = [
        {
            "card_id": cid,
            "name": matched_info[cid]["name"],
            "quantity": qty,
            "available": matched_info[cid]["available"],
        }
        for cid, qty in matched_qty.items()
    ]

    def of_status(status: str) -> list[dict[str, object]]:
        return [
            {
                "name": item.get("name", item["text"]),
                "quantity": item.get("quantity", 0),
                "line": item["line"],
            }
            for item in lines
            if item["status"] == status
        ]

    counts: dict[str, int] = {}
    for item in lines:
        counts[str(item["status"])] = counts.get(str(item["status"]), 0) + 1
    not_in_collection = [
        {**item, "status": "nicht in deiner Sammlung"} for item in of_status("not_in_collection")
    ]
    return {
        "cards": [{"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone} for c in cards],
        "matched": matched_list,
        "in_collection": matched_list,
        "not_in_collection": not_in_collection,
        "outside_color_identity": of_status("outside_identity"),
        "not_legal": of_status("not_legal"),
        "insufficient": of_status("insufficient"),
        "unreadable": of_status("unreadable"),
        "lines": lines,
        "line_counts": counts,
        "summary": {
            "in_collection_cards": sum(matched_qty.values()),
            "not_in_collection_cards": sum(int(str(i["quantity"])) for i in not_in_collection),
            "lines": len(lines),
            "list_cards": sum(matched_qty.values()) + len(commander_ids),
        },
    }
