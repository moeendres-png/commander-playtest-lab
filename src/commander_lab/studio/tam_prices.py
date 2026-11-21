"""TAM purchase guide values (Richtwerte) from a local Scryfall bulk file (#1637, WP-10a).

Owner decision 2026-11-21 (register ``docs/OWNER_DECISIONS_STUDIO_20261118.md``, entry
"Preise für TAM"; scope and limits by the Co-Lead): a price is shown only for cards that are not
owned, only in the TAM purchase view (Zukauf); the planning functions are only the sum, the
sorting and the budget filter of the TAM purchase list and the marking as a guide value. Prices
never feed suggestions, cut/swap, evidence or maturity, ratings, the tier list, rankings,
simulation figures or the card understanding; Chulane never gets a price.

Stage 1 reads exactly one field, ``prices.eur``, from a Scryfall bulk file the Owner downloaded
(no request from here, no scraping, no Cardmarket API, no ``purchase_uris``). The values go only
into the local store tables ``tam_price_snapshot`` and ``tam_price_eur`` (never committed, never
into ``scryfall_card``). The value is a market guide value of the file, not an offer: it knows
neither a seller country nor a condition and is not the cheapest offer. A card without a usable
value is "unbekannt", never 0. The only reader is :func:`purchase_guide_values`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from datetime import date as calendar_date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import catalog
from .decks import branch_head
from .store import StudioStore, now_utc
from .tam_import import TAM_COMMANDER_NAME

SOURCE_LABEL = "Scryfall prices.eur (lokale Bulk-Datei)"
VALUE_KIND = "Richtwert"
VALUE_RULE = (
    "niedrigster prices.eur-Wert über die spielbaren Papierdrucke dieser Karte in der Bulk-Datei "
    "(Non-Foil; ohne Übergröße, digital, Gold-/Silberrand, Sammlerstücke, Token-Layouts); "
    "prices.eur_foil wird nicht gelesen"
)
NOTICE = (
    "Marktpreis-Richtwert, kein Angebot: kein Händlerangebot, nicht Deutschland, nicht Zustand "
    "EX, nicht das günstigste Angebot."
)
MAX_CARD_IDS = 250
_EUR = re.compile(r"\d{1,6}(?:\.\d{1,2})?", re.ASCII)
_ISO_DATE = re.compile(r"20\d{2}-\d{2}-\d{2}", re.ASCII)
# Printings whose value is no guide for a playable copy (Scryfall card fields ``oversized``,
# ``digital``, ``border_color``, ``set_type``, ``layout``; scryfall.com/docs/api/cards):
# oversized cards, digital-only printings, gold-bordered (World Championship / Collectors'
# Edition) and silver-bordered cards, memorabilia sets and non-card layouts.
_NOT_PLAYABLE_BORDERS = frozenset({"gold", "silver"})
_NOT_PLAYABLE_SET_TYPES = frozenset({"memorabilia", "token", "minigame"})


def _playable_paper(card: dict[str, object]) -> bool:
    return not (
        card.get("oversized") is True
        or card.get("digital") is True
        or card.get("border_color") in _NOT_PLAYABLE_BORDERS
        or card.get("set_type") in _NOT_PLAYABLE_SET_TYPES
        or card.get("layout") in catalog._SKIPPED_LAYOUTS
    )


def _valid_date(text: str, today: calendar_date | None = None) -> str:
    """A real calendar date in ``YYYY-MM-DD`` form, not after tomorrow (UTC); anything else
    (``2026-99-99``, ``2099-12-31``) refuses."""
    if not _ISO_DATE.fullmatch(text):
        raise ValueError(f"bulk date must be YYYY-MM-DD: {text!r}")
    try:
        day = calendar_date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"bulk date is no calendar date: {text!r}") from error
    limit = (today or datetime.now(UTC).date()) + timedelta(days=1)
    if day > limit:
        raise ValueError(f"bulk date lies in the future: {text!r}")
    return text


class NotTamError(ValueError):
    """Guide values are only given for the commander TAM."""


def _cents(value: object) -> int | None:
    """The value in euro cents, or ``None`` (unknown) for a missing, unreadable or
    non-positive value. Never 0."""
    if not isinstance(value, str) or not _EUR.fullmatch(value.strip()):
        return None
    try:
        cents = int(Decimal(value.strip()) * 100)
    except InvalidOperation:  # pragma: no cover - the pattern admits only plain decimals
        return None
    return cents if cents > 0 else None


def import_scryfall_prices(
    store: StudioStore, bulk_path: str | Path, *, bulk_date: str | None = None
) -> dict[str, object]:
    """Replace the local guide values with the ``prices.eur`` field of one Scryfall bulk file
    (or a folder of its ``.jsonl`` parts).

    The date is the bulk file's date: from the file name (``default-cards-20261120...``) or
    ``bulk_date`` (``YYYY-MM-DD``); without either the import is refused, never the file time.
    Per oracle_id the lowest usable ``prices.eur`` over the printings in the file is kept."""
    files = catalog._source_files(Path(bulk_path))
    found = catalog._date_from_name(files[0].name)
    if bulk_date is not None:
        if found is not None and found != bulk_date:
            raise ValueError(
                f"bulk date conflict: --bulk-date {bulk_date} but the file name says {found}"
            )
        date, basis = _valid_date(bulk_date), "angegeben"
    else:
        if found is None:
            raise ValueError(
                "no bulk date: the file name carries no date; pass --bulk-date YYYY-MM-DD "
                "(the date of the Scryfall bulk file)"
            )
        date, basis = _valid_date(found), "Dateiname"
    digest = catalog._source_digest(files)
    best: dict[str, tuple[int, str]] = {}
    seen: set[str] = set()
    for file_path in files:
        for card in catalog._objects(file_path):
            oracle_id = card.get("oracle_id")
            if not isinstance(oracle_id, str) or not oracle_id:
                continue
            seen.add(oracle_id)
            if not _playable_paper(card):
                continue
            prices = card.get("prices")
            cents = _cents(prices.get("eur")) if isinstance(prices, dict) else None
            if cents is None:
                continue
            if oracle_id not in best or cents < best[oracle_id][0]:
                best[oracle_id] = (cents, str(card.get("id") or ""))
    without = len(seen - best.keys())
    with store.connection as db:
        db.execute("DELETE FROM tam_price_eur")
        db.executemany(
            "INSERT INTO tam_price_eur(oracle_id, eur_cents, scryfall_id) VALUES (?, ?, ?)",
            [
                (oracle_id, cents, scryfall_id or None)
                for oracle_id, (cents, scryfall_id) in best.items()
            ],
        )
        db.execute("DELETE FROM tam_price_snapshot")
        db.execute(
            "INSERT INTO tam_price_snapshot(snapshot_id, file_name, file_sha256, bulk_date, "
            "date_basis, imported_at, cards_with_value, cards_without_value) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
            (files[0].name, digest, date, basis, now_utc(), len(best), without),
        )
    return {
        "source": SOURCE_LABEL,
        "bulk_date": date,
        "date_basis": basis,
        "file_sha256": digest,
        "files_read": len(files),
        "cards_with_value": len(best),
        "cards_without_value": without,
    }


def _oracle_of(store: StudioStore, card_id: str) -> str | None:
    if card_id.startswith("scryfall:"):
        return card_id.removeprefix("scryfall:") or None
    row = store.connection.execute(
        "SELECT oracle_id FROM card WHERE card_id = ?", (card_id,)
    ).fetchone()
    return str(row[0]) if row is not None and row[0] else None


def _owned(store: StudioStore, card_id: str, oracle_id: str | None) -> int:
    """Copies owned of this card in any printing (by oracle_id), as the collection states."""
    if oracle_id is not None:
        row = store.connection.execute(
            "SELECT COALESCE(SUM(i.owned_lower_bound), 0) FROM inventory i "
            "JOIN card c ON c.card_id = i.card_id WHERE c.oracle_id = ? OR c.card_id = ?",
            (oracle_id, card_id),
        ).fetchone()
    else:
        row = store.connection.execute(
            "SELECT COALESCE(SUM(owned_lower_bound), 0) FROM inventory WHERE card_id = ?",
            (card_id,),
        ).fetchone()
    return int(row[0] or 0)


def _saved_cards(store: StudioStore, deck_id: str, branch: str) -> list[tuple[str, str]]:
    """(card_id, zone) of the saved revision the branch points to; ``KeyError`` when the deck
    or the branch has no saved revision (a draft alone never counts)."""
    head = branch_head(store.connection, deck_id, branch)
    if head is None:
        raise KeyError(f"{deck_id}/{branch}")
    rows = store.connection.execute(
        "SELECT card_id, zone FROM deck_revision_card WHERE revision_id = ?", (head,)
    ).fetchall()
    return [(str(r[0]), str(r[1])) for r in rows]


def _draft_cards(store: StudioStore, deck_id: str, branch: str) -> list[tuple[str, str]] | None:
    """(card_id, zone) of the stored working draft of the branch, or ``None``."""
    row = store.connection.execute(
        "SELECT cards FROM deck_draft WHERE deck_id = ? AND branch = ?", (deck_id, branch)
    ).fetchone()
    if row is None:
        return None
    raw = json.loads(str(row[0]))
    return [
        (str(item.get("card_id")), str(item.get("zone") or "main"))
        for item in (raw if isinstance(raw, list) else [])
        if isinstance(item, dict) and item.get("card_id")
    ]


def _is_tam_only(store: StudioStore, cards: list[tuple[str, str]]) -> bool:
    """Exactly one commander, a known card, and it is TAM; an unknown commander card refuses."""
    names = [_card_name(store, cid) for cid, zone in cards if zone == "commander"]
    return names == [TAM_COMMANDER_NAME]


def _card_name(store: StudioStore, card_id: str) -> str | None:
    row = store.connection.execute(
        "SELECT oracle_name FROM card WHERE card_id = ?", (card_id,)
    ).fetchone()
    if row is None and card_id.startswith("scryfall:"):
        row = store.connection.execute(
            "SELECT name FROM scryfall_card WHERE oracle_id = ?",
            (card_id.removeprefix("scryfall:"),),
        ).fetchone()
    return str(row[0]) if row is not None and row[0] else None


def purchase_guide_values(
    store: StudioStore,
    deck_id: str,
    branch: str,
    card_ids: Sequence[str],
    *,
    commander: str | None = None,
) -> dict[str, object]:
    """Guide values of the purchase list of a stored TAM deck.

    The commander is the one stored for the deck, never a name the caller sends: the saved
    revision the branch points to must exist (else ``KeyError``) and have exactly TAM as its
    one commander, and so must the working draft when there is one; otherwise
    :class:`NotTamError` (Chulane and every other commander get no price; a draft alone never
    turns a deck into a TAM deck). A ``commander`` the caller names must match. Only cards of
    the working list (draft, else saved revision; main and commander zone) are answered; other
    ids are left out and counted (``not_in_deck``). A card owned in any printing gets ``status="owned"``
    and no value; a card without a value ``status="unknown"``; only ``status="value"`` carries
    ``eur_cents``. Without an imported snapshot every card is unknown and ``snapshot`` is
    ``None``."""
    requested = list(dict.fromkeys(str(card_id) for card_id in card_ids if card_id))
    if len(requested) > MAX_CARD_IDS:
        raise ValueError(f"at most {MAX_CARD_IDS} cards")
    saved = _saved_cards(store, deck_id, branch)
    draft = _draft_cards(store, deck_id, branch)
    deck = saved if draft is None else draft
    if (
        not _is_tam_only(store, saved)
        or not _is_tam_only(store, deck)
        or commander not in (None, TAM_COMMANDER_NAME)
    ):
        raise NotTamError(
            f"Richtwerte nur für ein Deck mit dem Commander TAM ({TAM_COMMANDER_NAME})"
        )
    listed = {cid for cid, zone in deck if zone in ("main", "commander")}
    ids = [card_id for card_id in requested if card_id in listed]
    snap = store.connection.execute(
        "SELECT bulk_date, date_basis, imported_at, file_sha256 FROM tam_price_snapshot "
        "WHERE snapshot_id = 1"
    ).fetchone()
    cards: list[dict[str, object]] = []
    for card_id in ids:
        oracle_id = _oracle_of(store, card_id)
        if _owned(store, card_id, oracle_id) > 0:
            cards.append({"card_id": card_id, "status": "owned"})
            continue
        row = (
            store.connection.execute(
                "SELECT eur_cents FROM tam_price_eur WHERE oracle_id = ?", (oracle_id,)
            ).fetchone()
            if snap is not None and oracle_id is not None
            else None
        )
        if row is None or int(row[0]) <= 0:
            cards.append({"card_id": card_id, "status": "unknown"})
        else:
            cards.append({"card_id": card_id, "status": "value", "eur_cents": int(row[0])})
    return {
        "commander": TAM_COMMANDER_NAME,
        "deck_id": deck_id,
        "branch": branch,
        "not_in_deck": len(requested) - len(ids),
        "kind": VALUE_KIND,
        "source": SOURCE_LABEL,
        "rule": VALUE_RULE,
        "notice": NOTICE,
        "snapshot": (
            {
                "bulk_date": str(snap["bulk_date"]),
                "date_basis": str(snap["date_basis"]),
                "imported_at": str(snap["imported_at"]),
                "file_sha256": str(snap["file_sha256"]),
            }
            if snap is not None
            else None
        ),
        "cards": cards,
    }
