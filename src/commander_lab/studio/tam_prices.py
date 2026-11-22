"""TAM purchase prices (#1637): Scryfall approximation, Cardmarket entries and page reads.

Owner decision 2026-11-21 (register ``docs/OWNER_DECISIONS_STUDIO_20261118.md``, entry
"Preise für TAM"; scope and limits by the Co-Lead): a price is shown only for cards that are not
owned, only in the TAM purchase view (Zukauf); the planning functions are only the sum, the
sorting and the budget filter of the TAM purchase list and the marking as a guide value. Prices
never feed suggestions, cut/swap, evidence or maturity, ratings, the tier list, rankings,
simulation figures or the card understanding; Chulane never gets a price.

Three kinds of value, shown in this order of precedence and always labelled:

1. ``eingetragen``: a Cardmarket price the Owner read with his filters and typed in (or a CSV
   of such prices); the Studio gives him the filtered link, it never reads that page.
2. The Cardmarket price guide (Preisführer) Cardmarket publishes for download (Owner exception
   2026-11-22): per card the lowest ``low``/``low-foil`` and the lowest ``trend``/``trend-foil``
   over its playable paper printings, joined by the ``cardmarket_id`` of the Scryfall bulk
   file; no filter on seller country or condition (the surcharge for Germany/Excellent cannot
   be known without offer data).
3. The approximation (Näherung) from the Scryfall bulk file: the lowest of ``prices.eur`` and
   ``prices.eur_foil`` (Cardmarket's trend) over the playable paper printings, with its finish
   and printing; used only where no price guide value is there.

Entered prices older than 14 days are shown as stale and never used for the sum, sorting or
filter.
All values live only in the local store tables ``tam_price_snapshot``, ``tam_price_eur``,
``tam_price_print``, ``tam_cardmarket_guide``, ``tam_cardmarket_guide_snapshot`` and
``tam_cardmarket_price`` (never committed, never in ``scryfall_card``); a card without a value is
"unbekannt", never 0. The only reader is :func:`purchase_guide_values`.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from datetime import date as calendar_date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import catalog, tam_cardmarket
from .decks import branch_head
from .store import StudioStore, _repository_root, now_utc
from .tam_cardmarket import Filters
from .tam_import import TAM_COMMANDER_NAME

SOURCE_LABEL = "Scryfall (Cardmarket-Preisführer, kein Filter Deutschland/Excellent)"
VALUE_KIND = "Näherung"
VALUE_RULE = (
    "niedrigster Wert aus prices.eur und prices.eur_foil über die spielbaren Papierdrucke dieser "
    "Karte in der Bulk-Datei (ohne Übergröße, digital, Gold-/Silberrand, Sammlerstücke, "
    "Token-Layouts); Finish und Druck des niedrigsten Werts stehen je Karte dabei"
)
NOTICE = "Richtwert, kein Angebot: kein Händlerangebot, nicht Deutschland, nicht Zustand EX."
CARDMARKET_LABEL = "Cardmarket"
CARDMARKET_NOTICE = (
    "Eingetragen: vom Owner auf Cardmarket mit seinen Filtern abgelesen; älter als 14 Tage "
    "gilt als veraltet und zählt nicht."
)
GUIDE_LABEL = "Cardmarket-Preisführer"
GUIDE_NOTICE = (
    "Cardmarket ab (niedrigster Low-Wert, Foil oder Nicht-Foil) und Trend über alle spielbaren "
    "Drucke; ohne Filter Land/Sprache/Zustand: der Aufschlag für Deutschland, Englisch/Deutsch "
    "und Excellent ist ohne Angebotsdaten nicht belegbar. Ein Preisführer älter als 14 Tage gilt "
    "als veraltet und zählt nicht."
)
STALE_DAYS = 14
MAX_ENTRY_CENTS = 99_999_999
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
    """Replace the local approximations with the fields ``prices.eur`` and ``prices.eur_foil``
    of one Scryfall bulk file (or a folder of its ``.jsonl`` parts).

    The date is the bulk file's date: from the file name (``default-cards-20261120...``) or
    ``bulk_date`` (``YYYY-MM-DD``); without either the import is refused, never the file time.
    Per oracle_id the lowest usable value of both finishes over the playable printings in the
    file is kept with its finish (``nonfoil``/``foil``), set code and collector number."""
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
    best: dict[str, tuple[int, str, str, str, str]] = {}
    prints: dict[int, tuple[str, str, str]] = {}
    seen: set[str] = set()
    for file_path in files:
        for card in catalog._objects(file_path):
            oracle_id = card.get("oracle_id")
            if not isinstance(oracle_id, str) or not oracle_id:
                continue
            seen.add(oracle_id)
            if not _playable_paper(card):
                continue
            cardmarket_id = card.get("cardmarket_id")
            if type(cardmarket_id) is int and cardmarket_id > 0:
                prints[cardmarket_id] = (
                    oracle_id,
                    str(card.get("set") or "")[:12],
                    str(card.get("collector_number") or "")[:12],
                )
            prices = card.get("prices")
            if not isinstance(prices, dict):
                continue
            for field_name, finish in (("eur", "nonfoil"), ("eur_foil", "foil")):
                cents = _cents(prices.get(field_name))
                if cents is None:
                    continue
                if oracle_id not in best or cents < best[oracle_id][0]:
                    best[oracle_id] = (
                        cents,
                        str(card.get("id") or ""),
                        finish,
                        str(card.get("set") or "")[:12],
                        str(card.get("collector_number") or "")[:12],
                    )
    without = len(seen - best.keys())
    with store.connection as db:
        db.execute("DELETE FROM tam_price_eur")
        db.executemany(
            "INSERT INTO tam_price_eur(oracle_id, eur_cents, scryfall_id, finish, set_code, "
            "collector_number) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (oracle_id, cents, scryfall_id or None, finish, set_code or None, number or None)
                for oracle_id, (cents, scryfall_id, finish, set_code, number) in best.items()
            ],
        )
        db.execute("DELETE FROM tam_price_print")
        db.executemany(
            "INSERT INTO tam_price_print(cardmarket_id, oracle_id, set_code, collector_number) "
            "VALUES (?, ?, ?, ?)",
            [
                (cardmarket_id, oracle_id, set_code or None, number or None)
                for cardmarket_id, (oracle_id, set_code, number) in sorted(prints.items())
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
        "printings_with_cardmarket_id": len(prints),
    }


_GUIDE_DATE = re.compile(r"(20\d{2}-\d{2}-\d{2})T", re.ASCII)


def _guide_cents(value: object) -> int | None:
    """A price guide number (euro, JSON number) in cents; missing, non-numeric or <= 0: None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if value != value or value <= 0 or value > 1_000_000:  # NaN, zero, negative, absurd
        return None
    cents = int(Decimal(str(value)) * 100)
    return cents if cents > 0 else None


def _json_list(path: Path, key: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get(key) if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"{path.name}: no list {key!r} (not a Cardmarket {key} file)")
    return data, [item for item in items if isinstance(item, dict)]


def import_cardmarket_priceguide(
    store: StudioStore,
    guide_path: str | Path,
    *,
    products_path: str | Path | None = None,
    guide_date: str | None = None,
) -> dict[str, object]:
    """Replace the local price guide values with one Cardmarket price guide file
    (``price_guide_1.json``, list ``priceGuides``).

    Products are joined to cards by the ``cardmarket_id`` of the playable printings the Scryfall
    import recorded (``import-tam-prices`` first); a product of no known printing is left out.
    With the singles product list (``products_singles_1.json``) a product whose name is not the
    card's name (or its front face) is left out and counted. Per card the lowest ``low`` /
    ``low-foil`` (with finish and printing) and the lowest ``trend`` / ``trend-foil`` are kept.
    The date is the file's ``createdAt`` or ``guide_date``; without either the import is
    refused."""
    path = Path(guide_path)
    for given in (path, None if products_path is None else Path(products_path)):
        if given is not None and given.resolve().is_relative_to(_repository_root()):
            raise ValueError(f"the price guide files must lie outside the repository: {given}")
    data, guides = _json_list(path, "priceGuides")
    created = data.get("createdAt")
    stamp = _GUIDE_DATE.match(created) if isinstance(created, str) else None
    found = stamp.group(1) if stamp is not None else None
    if guide_date is not None:
        if found is not None and found != guide_date:
            raise ValueError(f"guide date conflict: --date {guide_date} but createdAt says {found}")
        date, basis = _valid_date(guide_date), "angegeben"
    elif found is not None:
        date, basis = _valid_date(found), "createdAt"
    else:
        raise ValueError("no guide date: the file has no createdAt; pass --date YYYY-MM-DD")
    prints = {
        int(r[0]): (str(r[1]), str(r[2] or ""), str(r[3] or ""))
        for r in store.connection.execute(
            "SELECT cardmarket_id, oracle_id, set_code, collector_number FROM tam_price_print"
        )
    }
    names: dict[int, str] | None = None
    if products_path is not None:
        _meta, products = _json_list(Path(products_path), "products")
        names = {
            product: str(item.get("name") or "")
            for item in products
            if type(product := item.get("idProduct")) is int
        }
    card_names = {
        str(r[0]): {str(r[1]).casefold(), str(r[2]).casefold()}
        for r in store.connection.execute("SELECT oracle_id, name, front_name FROM scryfall_card")
    }
    low: dict[str, tuple[int, str, str, str]] = {}
    trend: dict[str, int] = {}
    matched = mismatches = 0
    for item in guides:
        product = item.get("idProduct")
        if not isinstance(product, int) or product not in prints:
            continue
        oracle_id, set_code, number = prints[product]
        if names is not None:
            product_name = names.get(product, "").casefold()
            known = card_names.get(oracle_id)
            if known is None or product_name not in known:
                mismatches += 1
                continue
        matched += 1
        for field_name, finish in (("low", "nonfoil"), ("low-foil", "foil")):
            cents = _guide_cents(item.get(field_name))
            if cents is not None and (oracle_id not in low or cents < low[oracle_id][0]):
                low[oracle_id] = (cents, finish, set_code, number)
        for field_name in ("trend", "trend-foil"):
            cents = _guide_cents(item.get(field_name))
            if cents is not None and (oracle_id not in trend or cents < trend[oracle_id]):
                trend[oracle_id] = cents
    cards = sorted(low.keys() | trend.keys())
    digest = catalog._source_digest([path])
    with store.connection as db:
        db.execute("DELETE FROM tam_cardmarket_guide")
        db.executemany(
            "INSERT INTO tam_cardmarket_guide(oracle_id, low_cents, low_finish, low_set_code, "
            "low_collector_number, trend_cents) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    oracle_id,
                    low[oracle_id][0] if oracle_id in low else None,
                    low[oracle_id][1] if oracle_id in low else None,
                    (low[oracle_id][2] or None) if oracle_id in low else None,
                    (low[oracle_id][3] or None) if oracle_id in low else None,
                    trend.get(oracle_id),
                )
                for oracle_id in cards
            ],
        )
        db.execute("DELETE FROM tam_cardmarket_guide_snapshot")
        db.execute(
            "INSERT INTO tam_cardmarket_guide_snapshot(snapshot_id, guide_date, date_basis, "
            "file_sha256, imported_at, products_in_guide, printings_known, printings_matched, "
            "name_mismatches, name_check, cards_with_value) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (date, basis, digest, now_utc(), len(guides), len(prints), matched, mismatches,
             int(names is not None), len(cards)),
        )  # fmt: skip
    return {
        "source": GUIDE_LABEL,
        "guide_date": date,
        "date_basis": basis,
        "file_sha256": digest,
        "products_in_guide": len(guides),
        "printings_known": len(prints),
        "printings_matched": matched,
        "name_mismatches": mismatches,
        "name_check": names is not None,
        "cards_with_value": len(cards),
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


def _tam_working_list(
    store: StudioStore, deck_id: str, branch: str, commander: str | None
) -> set[str]:
    """The card ids (main and commander zone) of the working list of a stored TAM deck.

    The commander is the one stored for the deck, never a name the caller sends: the saved
    revision the branch points to must exist (else ``KeyError``) and have exactly TAM as its
    one commander, and so must the working draft when there is one; otherwise
    :class:`NotTamError` (Chulane and every other commander get no price; a draft alone never
    turns a deck into a TAM deck). A ``commander`` the caller names must match. Every reader and
    writer of this module goes through here."""
    saved = _saved_cards(store, deck_id, branch)
    draft = _draft_cards(store, deck_id, branch)
    deck = saved if draft is None else draft
    if (
        not _is_tam_only(store, saved)
        or not _is_tam_only(store, deck)
        or commander not in (None, TAM_COMMANDER_NAME)
    ):
        raise NotTamError(f"Preise nur für ein Deck mit dem Commander TAM ({TAM_COMMANDER_NAME})")
    return {cid for cid, zone in deck if zone in ("main", "commander")}


def _purchase_card(
    store: StudioStore, deck_id: str, branch: str, card_id: str, commander: str | None
) -> tuple[str, str]:
    """(oracle_id, name) of a card of the TAM working list that is not owned; else
    :class:`NotTamError`, ``KeyError`` or ``ValueError``."""
    if card_id not in _tam_working_list(store, deck_id, branch, commander):
        raise ValueError("die Karte steht nicht in der Deckliste dieser Variante")
    oracle_id = _oracle_of(store, card_id)
    name = _card_name(store, card_id)
    if oracle_id is None or name is None:
        raise ValueError("unbekannte Karte")
    if _owned(store, card_id, oracle_id) > 0:
        raise ValueError("die Karte ist im Besitz: kein Preis")
    return oracle_id, name


def _filters(filters: Filters | str | None) -> Filters:
    """The filters of an entry: given, or from a filter code (``DE/EX/EN+DE``), or the Owner's
    default (Deutschland, Englisch und Deutsch, Excellent)."""
    if isinstance(filters, Filters):
        return filters
    return Filters() if filters is None else tam_cardmarket.filters_from_code(filters)


def _today(today: calendar_date | None) -> calendar_date:
    return today or datetime.now(UTC).date()


def parse_eur_input(text: str) -> int | None:
    """German or plain input in cents: ``12``, ``12,5``, ``12.50``, ``1.234,56``, ``10 €``.
    Empty, zero, negative or unreadable: ``None`` ("unbekannt"), never 0."""
    clean = re.sub(r"\s", "", str(text or "").strip().removesuffix("€"), flags=re.ASCII)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", clean, re.ASCII):
        clean = clean.replace(".", "")
    clean = clean.replace(",", ".", 1)
    if not re.fullmatch(r"\d{1,6}(?:\.\d{1,2})?", clean, re.ASCII):
        return None
    whole, _dot, part = clean.partition(".")
    cents = int(whole) * 100 + int((part + "00")[:2])
    return cents if 0 < cents <= MAX_ENTRY_CENTS else None


def _entry_date(text: str | None, today: calendar_date) -> str:
    """The date of an entry: ``YYYY-MM-DD`` or ``TT.MM.JJJJ``, a real date, not in the future
    (one day of grace for time zones), not before 2000; empty means today."""
    raw = (text or "").strip()
    if not raw:
        return today.isoformat()
    german = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw, re.ASCII)
    if german:
        raw = f"{german.group(3)}-{int(german.group(2)):02d}-{int(german.group(1)):02d}"
    if not _ISO_DATE.fullmatch(raw):
        raise ValueError(f"Datum nicht lesbar: {text!r} (JJJJ-MM-TT oder TT.MM.JJJJ)")
    try:
        day = calendar_date.fromisoformat(raw)
    except ValueError as error:
        raise ValueError(f"kein Kalenderdatum: {text!r}") from error
    if day > today + timedelta(days=1):
        raise ValueError(f"Datum liegt in der Zukunft: {text!r}")
    return raw


def _store_entry(
    store: StudioStore,
    oracle_id: str,
    cents: int | None,
    price_date: str,
    filters: Filters,
    source_url: str | None,
) -> None:
    with store.connection as db:
        if cents is None:
            db.execute("DELETE FROM tam_cardmarket_price WHERE oracle_id = ?", (oracle_id,))
            return
        db.execute(
            "INSERT OR REPLACE INTO tam_cardmarket_price(oracle_id, eur_cents, price_date, "
            "recorded_at, filter_code, source_url) VALUES (?, ?, ?, ?, ?, ?)",
            (oracle_id, cents, price_date, now_utc(), filters.code, source_url),
        )


def save_cardmarket_price(
    store: StudioStore,
    deck_id: str,
    branch: str,
    card_id: str,
    price_text: str,
    *,
    price_date: str | None = None,
    filters: Filters | str | None = None,
    commander: str | None = None,
    today: calendar_date | None = None,
) -> dict[str, object]:
    """Store (or, for an empty, zero or unreadable price, remove) the Cardmarket price the Owner
    entered for one card of the TAM purchase list. Only a card of the stored TAM deck that is
    not owned; the filters name what the price was read under."""
    chosen = _filters(filters)
    oracle_id, name = _purchase_card(store, deck_id, branch, card_id, commander)
    day = _entry_date(price_date, _today(today))
    cents = parse_eur_input(price_text)
    url, kind = tam_cardmarket.card_link(name, chosen)
    _store_entry(store, oracle_id, cents, day, chosen, url)
    return {
        "card_id": card_id,
        "status": "value" if cents is not None else "unknown",
        "eur_cents": cents,
        "price_date": day,
        "filter_code": chosen.code,
        "link_kind": kind,
    }


def import_cardmarket_csv(
    store: StudioStore,
    deck_id: str,
    csv_path: str | Path,
    *,
    branch: str = "main",
    filters: Filters | str | None = None,
    today: calendar_date | None = None,
) -> dict[str, object]:
    """Enter many Cardmarket prices at once from a local ``Name;Preis;Datum`` file (a header
    line is skipped; ``Datum`` may be empty: today). Names are matched to the cards of the TAM
    purchase list (not owned); every other line is reported, not stored. The file must lie
    outside the repository (it holds real prices)."""
    path = Path(csv_path).resolve()
    if path.is_relative_to(_repository_root()):
        raise ValueError(f"the price file must lie outside the repository: {path}")
    chosen = _filters(filters)
    day_today = _today(today)
    listed = _tam_working_list(store, deck_id, branch, None)
    by_name: dict[str, str] = {}
    for card_id in sorted(listed):
        name = _card_name(store, card_id)
        if name is not None:
            by_name.setdefault(name.casefold(), card_id)
    stored = removed = 0
    skipped: list[dict[str, object]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_no, row in enumerate(csv.reader(handle, delimiter=";"), start=1):
            if not row or not "".join(row).strip():
                continue
            name = row[0].strip()
            if line_no == 1 and name.casefold() == "name":
                continue
            match = by_name.get(name.casefold())
            if match is None:
                skipped.append({"line": line_no, "reason": "nicht in der Zukauf-Liste"})
                continue
            try:
                entry = save_cardmarket_price(
                    store, deck_id, branch, match, row[1] if len(row) > 1 else "",
                    price_date=row[2] if len(row) > 2 else None, filters=chosen,
                    today=day_today,
                )  # fmt: skip
            except ValueError as error:
                skipped.append({"line": line_no, "reason": str(error)})
                continue
            if entry["status"] == "value":
                stored += 1
            else:
                removed += 1
    return {"stored": stored, "removed_as_unknown": removed, "skipped": skipped,
            "filter_code": chosen.code}  # fmt: skip


def _entered(store: StudioStore, oracle_id: str, today: calendar_date) -> dict[str, object] | None:
    row = store.connection.execute(
        "SELECT eur_cents, price_date, filter_code, source_url FROM tam_cardmarket_price "
        "WHERE oracle_id = ?",
        (oracle_id,),
    ).fetchone()
    if row is None or int(row["eur_cents"]) <= 0:
        return None
    try:
        age = (today - calendar_date.fromisoformat(str(row["price_date"]))).days
    except ValueError:
        return None
    return {
        "eur_cents": int(row["eur_cents"]),
        "price_date": str(row["price_date"]),
        "filter_code": str(row["filter_code"]),
        "age_days": age,
        "stale": age > STALE_DAYS,
    }


def _guide(store: StudioStore, oracle_id: str) -> dict[str, object] | None:
    row = store.connection.execute(
        "SELECT low_cents, low_finish, low_set_code, low_collector_number, trend_cents "
        "FROM tam_cardmarket_guide WHERE oracle_id = ?",
        (oracle_id,),
    ).fetchone()
    if row is None:
        return None
    low = int(row["low_cents"]) if row["low_cents"] and int(row["low_cents"]) > 0 else None
    trend = int(row["trend_cents"]) if row["trend_cents"] and int(row["trend_cents"]) > 0 else None
    if low is None and trend is None:
        return None
    printing = " ".join(
        part
        for part in (str(row["low_set_code"] or "").upper(), str(row["low_collector_number"] or ""))
        if part
    )
    return {
        "low_cents": low,
        "low_finish": str(row["low_finish"] or "") if low is not None else "",
        "low_printing": printing if low is not None else "",
        "trend_cents": trend,
    }


def purchase_guide_values(
    store: StudioStore,
    deck_id: str,
    branch: str,
    card_ids: Sequence[str],
    *,
    commander: str | None = None,
    today: calendar_date | None = None,
) -> dict[str, object]:
    """Prices of the purchase list of a stored TAM deck (gate: :func:`_tam_working_list`).

    Only cards of the working list (draft, else saved revision; main and commander zone) are
    answered; other ids are left out and counted (``not_in_deck``). A card owned in any printing
    gets ``status="owned"`` and nothing else. For the others: ``status`` says whether the
    Scryfall approximation has a value (``"value"`` with ``eur_cents``, finish and printing) or
    not (``"unknown"``); ``guide`` holds the Cardmarket price guide values (low and trend, with
    finish and printing of the low) when the guide has the card; ``entered`` the price the Owner
    entered, with date, filters and a ``stale`` flag (older than 14 days). Without an imported
    snapshot the corresponding ``snapshot`` / ``guide_snapshot`` is ``None``."""
    requested = list(dict.fromkeys(str(card_id) for card_id in card_ids if card_id))
    if len(requested) > MAX_CARD_IDS:
        raise ValueError(f"at most {MAX_CARD_IDS} cards")
    listed = _tam_working_list(store, deck_id, branch, commander)
    day = _today(today)
    ids = [card_id for card_id in requested if card_id in listed]
    snap = store.connection.execute(
        "SELECT bulk_date, date_basis, imported_at, file_sha256 FROM tam_price_snapshot "
        "WHERE snapshot_id = 1"
    ).fetchone()
    guide_snap = store.connection.execute(
        "SELECT guide_date, date_basis, imported_at, printings_known, printings_matched, "
        "name_mismatches, name_check FROM tam_cardmarket_guide_snapshot WHERE snapshot_id = 1"
    ).fetchone()
    cards: list[dict[str, object]] = []
    for card_id in ids:
        oracle_id = _oracle_of(store, card_id)
        if _owned(store, card_id, oracle_id) > 0:
            cards.append({"card_id": card_id, "status": "owned"})
            continue
        item: dict[str, object] = {"card_id": card_id, "name": _card_name(store, card_id) or ""}
        row = (
            store.connection.execute(
                "SELECT eur_cents, finish, set_code, collector_number FROM tam_price_eur "
                "WHERE oracle_id = ?",
                (oracle_id,),
            ).fetchone()
            if snap is not None and oracle_id is not None
            else None
        )
        if row is None or int(row["eur_cents"]) <= 0:
            item["status"] = "unknown"
        else:
            item["status"] = "value"
            item["eur_cents"] = int(row["eur_cents"])
            item["finish"] = str(row["finish"] or "")
            item["printing"] = " ".join(
                part
                for part in (str(row["set_code"] or "").upper(), str(row["collector_number"] or ""))
                if part
            )
        if oracle_id is not None:
            guide = _guide(store, oracle_id) if guide_snap is not None else None
            if guide is not None:
                item["guide"] = guide
            entered = _entered(store, oracle_id, day)
            if entered is not None:
                item["entered"] = entered
        cards.append(item)
    return {
        "commander": TAM_COMMANDER_NAME,
        "deck_id": deck_id,
        "branch": branch,
        "not_in_deck": len(requested) - len(ids),
        "kind": VALUE_KIND,
        "source": SOURCE_LABEL,
        "rule": VALUE_RULE,
        "notice": NOTICE,
        "cardmarket_label": CARDMARKET_LABEL,
        "cardmarket_notice": CARDMARKET_NOTICE,
        "guide_label": GUIDE_LABEL,
        "guide_notice": GUIDE_NOTICE,
        "stale_days": STALE_DAYS,
        "today": day.isoformat(),
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
        "guide_snapshot": (
            {
                "guide_date": str(guide_snap["guide_date"]),
                "date_basis": str(guide_snap["date_basis"]),
                "imported_at": str(guide_snap["imported_at"]),
                "printings_known": int(guide_snap["printings_known"]),
                "printings_matched": int(guide_snap["printings_matched"]),
                "name_mismatches": int(guide_snap["name_mismatches"]),
                "name_check": bool(guide_snap["name_check"]),
                "age_days": (day - calendar_date.fromisoformat(str(guide_snap["guide_date"]))).days,
                "stale": (day - calendar_date.fromisoformat(str(guide_snap["guide_date"]))).days
                > STALE_DAYS,
            }
            if guide_snap is not None
            else None
        ),
        "cards": cards,
    }
