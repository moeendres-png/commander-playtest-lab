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
from pathlib import Path

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


_DECKS_DIR = Path(__file__).resolve().parents[3] / "data" / "decks"

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
        "maindeck",
        "maindeck:",
        "sideboard",
        "sideboard:",
        "maybeboard",
        "maybeboard:",
        "companion",
        "companion:",
        "cuts",
        "cuts:",
    }
)
_SKIPPED_SECTIONS = frozenset({"sideboard", "maybeboard", "cuts", "tokens", "considering"})
_ACTIVE_SECTIONS = frozenset({"commander", "commanders", "deck", "main", "mainboard", "maindeck"})
_CSV_QTY_COLS = ("count", "quantity", "qty", "tradelist count")
_CSV_NAME_COLS = ("name", "card name", "card")
_CSV_SECTION_COLS = ("section", "board", "zone", "category", "categories")


def repo_deck_file_for_commander(
    commander_names: Sequence[str], *, decks_dir: Path | None = None
) -> Path | None:
    """Return the checked-in ``<slug>_current.txt`` file for ``commander_names``, if present."""
    folder = decks_dir if decks_dir is not None else _DECKS_DIR
    if not commander_names or not folder.is_dir():
        return None
    first = commander_names[0].split(",")[0].strip().casefold()
    slug = "".join(ch if ch.isalnum() else "_" for ch in first).strip("_")
    if not slug:
        return None
    candidate = folder / f"{slug}_current.txt"
    return candidate if candidate.is_file() else None


def baseline_decks_for_commander(
    commander_names: Sequence[str], *, decks_dir: Path | None = None
) -> list[dict[str, object]]:
    """Available read-only repository baseline deck files for ``commander_names``."""
    path = repo_deck_file_for_commander(commander_names, decks_dir=decks_dir)
    if path is None:
        return []
    stem = path.stem
    return [
        {
            "revision_id": f"repo:{stem}",
            "label": f"{path.name} (Repo-Stand)",
            "file": path.name,
        }
    ]


def _collection_lookup(
    store: StudioStore,
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    """Name lookup across collection cards (`card_fact` + `inventory`) and public cards (`scryfall_card`)."""
    coll: dict[str, dict[str, object]] = {}
    for row in store.connection.execute(
        "SELECT c.card_id, c.oracle_name, c.engine_name, c.color_identity, "
        "c.commander_legal, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id)"
    ):
        info: dict[str, object] = {
            "card_id": str(row["card_id"]),
            "name": str(row["oracle_name"]),
            "color_identity": str(row["color_identity"] or ""),
            "commander_legal": row["commander_legal"],
            "available": int(row["available_lower_bound"] or 0),
        }
        coll[str(row["oracle_name"]).casefold()] = info
        if row["engine_name"]:
            coll.setdefault(str(row["engine_name"]).casefold(), info)
        for face in str(row["oracle_name"]).split(" // "):
            coll.setdefault(face.strip().casefold(), info)
    public: dict[str, dict[str, object]] = {}
    for row in store.connection.execute(
        "SELECT oracle_id, name, front_name, color_identity, commander_legality FROM scryfall_card"
    ):
        pinfo: dict[str, object] = {
            "name": str(row["name"]),
            "color_identity": str(row["color_identity"] or ""),
            "commander_legal": 1 if row["commander_legality"] == "legal" else 0,
        }
        public[str(row["name"]).casefold()] = pinfo
        if row["front_name"]:
            public.setdefault(str(row["front_name"]).casefold(), pinfo)
        for face in str(row["name"]).split(" // ")[1:]:
            public.setdefault(face.strip().casefold(), pinfo)
    return coll, public


def _detect_format(lines: list[str]) -> str:
    if not lines:
        return "plain"
    cleaned = [ln.lstrip("\ufeff") for ln in lines]
    first_nonempty = next((ln.strip() for ln in cleaned if ln.strip()), "")
    if "," in first_nonempty:
        lowered = [col.strip().strip('"').casefold() for col in first_nonempty.split(",")]
        if any(col in _CSV_NAME_COLS for col in lowered) and (len(lowered) >= 2):
            return "csv"
    has_set_paren = any(" (" in ln and ") " in ln for ln in cleaned)
    has_archidekt_cat = any("[" in ln and ln.rstrip().endswith("]") for ln in cleaned)
    has_x = any(
        ln.lstrip().split(" ", 1)[0].rstrip("xX").isdigit() and "x " in ln.lower() for ln in cleaned
    )
    if has_archidekt_cat:
        return "archidekt"
    if any("*CMDR*" in ln or "*F*" in ln for ln in cleaned):
        return "moxfield"
    if has_set_paren:
        return "arena"
    if has_x:
        return "mtgo"
    return "plain"


_MAX_LINE_CHARS = 300
_MAX_LINES = 2000
_MAX_QUANTITY = 99
_MAX_STRIP_PASSES = 8
_TYPO_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u02bc": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
        "\u202f": " ",
        "\u200b": None,
        "\u200c": None,
        "\u200d": None,
        "\u2060": None,
        "\ufeff": None,
    }
)
_DASH_TRANSLATION = str.maketrans(
    {"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-"}
)
_CURRENCY = (
    r"(?:US\$|CA\$|A\$|[$\u20ac\u00a3\u00a5]"
    r"|(?<![A-Za-z])(?:USD|EUR|EURO|GBP|JPY|CHF|CAD|AUD|SEK|NOK|DKK|PLN|CNY|RMB)(?![A-Za-z]))"
)
# One start per digit run (lookbehind) and a possessive tail keep the scan linear.
_NUMBER = r"(?<![\d.,'])\d+(?:[.,']\d+|\u0020\d{3}(?!\d))*+"
# A number before a currency belongs to that currency only when no further digit follows it:
# in "Sol Ring 1 $1.20" the "$" opens the next amount and the lone 1 stays part of the name.
_AMOUNT = rf"(?:{_CURRENCY}\s*{_NUMBER}|{_NUMBER}\s*{_CURRENCY}(?!\s*\d))"
_AMOUNT_RE = re.compile(rf"\(\s*{_AMOUNT}\s*\)|{_AMOUNT}", re.IGNORECASE)
_PRICE_ANNOTATION = "Betragsangabe (ignoriert)"


def _scrub_amounts(text: str) -> str:
    """Remove every amount token; applied to all text that is returned to the caller."""
    return _AMOUNT_RE.sub("", text)


def _tidy(text: str) -> str:
    return " ".join(text.split()).strip(" \t-\u2010\u2011\u2012\u2013\u2014,;:/|")


def _clean_raw(line: str) -> str:
    return " ".join(_scrub_amounts(line[:_MAX_LINE_CHARS]).split())


_DECORATOR_RES = (
    re.compile(r"\s*\*+[A-Za-z0-9]+\*+\s*$"),
    re.compile(r"\s*\[[^\]]*\]\s*$"),
    re.compile(r"\s*\{[^}]*\}\s*$"),
    re.compile(r"\s*\^[^^]*\^\s*$"),
    re.compile(r"\s+#\S+\s*$"),
    re.compile(r"\s+\([A-Za-z0-9]{2,6}\)(?:\s+[A-Za-z0-9-]+)?\s*$"),
)


def _strip_decklist_decorators(raw_name: str) -> str:
    name = raw_name.strip()
    # Strip trailing Archidekt/Moxfield/Arena markers in any order: *CMDR*, *F*, [Cat], {tag}, ^...^, #tag, (SET) 123.
    # Bounded number of passes on a length-capped name keeps the work linear in the input.
    for _ in range(_MAX_STRIP_PASSES):
        prev = name
        for pattern in _DECORATOR_RES:
            name = pattern.sub("", name)
        name = name.strip()
        if name == prev:
            break
    return name


def resolve_repo_baseline_cards(
    store: StudioStore,
    baseline_id: str,
    commander_names: Sequence[str] | None = None,
    *,
    decks_dir: Path | None = None,
) -> list[RevisionCard]:
    """Load a checked-in ``repo:<stem>`` text decklist into ``RevisionCard`` rows (in-collection pool)."""
    if not baseline_id.startswith("repo:"):
        raise KeyError(baseline_id)
    stem = baseline_id[len("repo:") :].strip()
    if not stem or "/" in stem or "\\" in stem or "\x00" in stem or ".." in stem:
        raise KeyError(baseline_id)
    folder = decks_dir if decks_dir is not None else _DECKS_DIR
    candidate = folder / f"{stem}.txt"
    try:
        if candidate.resolve().parent != folder.resolve() or not candidate.is_file():
            raise KeyError(baseline_id)
    except OSError as error:  # e.g. over-long names: refuse like any other unknown id
        raise KeyError(baseline_id) from error
    text = candidate.read_text(encoding="utf-8")
    if not commander_names:
        # Read commander from file or infer Chulane if present
        cmd_lines: list[str] = []
        in_cmd = False
        for raw in text.splitlines():
            s = raw.strip()
            if not s:
                in_cmd = False
                continue
            low = s.casefold().rstrip(":")
            if low in {"commander", "commanders"}:
                in_cmd = True
                continue
            if low in _ACTIVE_SECTIONS | _SKIPPED_SECTIONS:
                in_cmd = False
                continue
            if in_cmd:
                parts = s.split(" ", 1)
                cmd_lines.append(_strip_decklist_decorators(parts[1] if parts[0].isdigit() else s))
        commander_names = cmd_lines
    parsed = parse_decklist_text(store, commander_names, text)
    return [
        RevisionCard(str(item["card_id"]), int(item["quantity"]), str(item["zone"]))
        for item in parsed["cards"]  # type: ignore[attr-defined]
    ]


def _hit(table: dict[str, dict[str, object]], name: str) -> dict[str, object] | None:
    return table.get(name.casefold()) or table.get(name.split(" // ")[0].strip().casefold())


def _too_long(lineno: int, line: str) -> dict[str, object]:
    tokens = _scrub_amounts(line[:_MAX_LINE_CHARS]).split(" ")
    for index in range(max(0, len(tokens) - 4), len(tokens)):
        if any(ch.isdigit() for ch in tokens[index]):
            tokens = tokens[:index]  # a cut-off amount must not leak as a stray figure
            break
    return {
        "line": lineno,
        "raw": " ".join(tokens),
        "status": "zu lang",
        "reason": f"zu lang (über {_MAX_LINE_CHARS} Zeichen)",
    }


def _bad_quantity(lineno: int, line: str) -> dict[str, object]:
    return {
        "line": lineno,
        "raw": _clean_raw(line),
        "status": "unreadable",
        "reason": f"ungültige Anzahl (erlaubt: 1 bis {_MAX_QUANTITY})",
    }


def parse_decklist_text(
    store: StudioStore,
    commander_names: Sequence[str],
    text: str,
) -> dict[str, object]:
    """Parse decklist text (plain, Arena, MTGO, Moxfield, Archidekt, Deckstats, or CSV)
    against the commander's legal collection pool. Cards not in the collection or outside
    color identity are listed neutrally by name without any price or purchase wording.
    """
    import csv
    import io

    from . import builder

    identity, commander_ids = builder.commander_identity(store, commander_names)
    cmd_set = set(commander_ids)
    cmd_names_cf = {n.casefold() for n in commander_names}
    coll, public = _collection_lookup(store)

    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.translate(_TYPO_TRANSLATION)
    lines = text.splitlines()
    if len(lines) > _MAX_LINES:
        raise ValueError(
            f"Liste zu lang: {len(lines)} Zeilen (höchstens {_MAX_LINES} erlaubt, nichts wurde gelesen)"
        )
    ignored_annotations: list[dict[str, object]] = []
    detected_format = _detect_format(lines)
    matched_qty: dict[str, int] = {}
    matched_info: dict[str, dict[str, object]] = {}
    not_in_collection: list[dict[str, object]] = []
    outside_color_identity: list[dict[str, object]] = []
    unrecognized_lines: list[dict[str, object]] = []
    not_in_collection_qty = 0
    outside_qty = 0
    skipped_section = False

    def _classify_entry(qty: int, raw_name: str, lineno: int, raw_line: str) -> None:
        nonlocal not_in_collection_qty, outside_qty
        scrubbed = _scrub_amounts(raw_name)
        if scrubbed != raw_name:
            ignored_annotations.append({"line": lineno, "annotation": _PRICE_ANNOTATION})
            scrubbed = _tidy(scrubbed)
        name = _strip_decklist_decorators(scrubbed).translate(_DASH_TRANSLATION)
        if not name:
            unrecognized_lines.append(
                {
                    "line": lineno,
                    "raw": _clean_raw(raw_line),
                    "status": "unreadable",
                    "reason": "leerer Kartenname",
                }
            )
            return
        variants = [name]
        if len(name) >= 2 and name[0] == name[-1] == '"' and name[1:-1].strip():
            variants.append(name[1:-1].strip())
        if any(v.casefold() in cmd_names_cf for v in variants):
            return
        found = next((h for v in variants if (h := _hit(coll, v)) is not None), None)
        if found is not None:
            cid = str(found["card_id"])
            if cid in cmd_set:
                return
            legal_ok = found["commander_legal"] == 1
            id_ok = color_set(str(found["color_identity"] or "")) <= identity
            if not legal_ok or not id_ok:
                outside_qty += qty
                outside_color_identity.append(
                    {
                        "name": str(found["name"]),
                        "quantity": qty,
                        "reason": "nicht in Farbidentität"
                        if not id_ok
                        else "nicht Commander-legal",
                    }
                )
                return
            matched_qty[cid] = matched_qty.get(cid, 0) + qty
            matched_info[cid] = found
            return
        pub = next((h for v in variants if (h := _hit(public, v)) is not None), None)
        name = variants[-1]
        if pub is not None:
            id_ok = color_set(str(pub["color_identity"] or "")) <= identity
            legal_ok = pub["commander_legal"] == 1
            if not id_ok or not legal_ok:
                outside_qty += qty
                outside_color_identity.append(
                    {
                        "name": str(pub["name"]),
                        "quantity": qty,
                        "reason": "nicht in Farbidentität"
                        if not id_ok
                        else "nicht Commander-legal",
                    }
                )
                return
            not_in_collection_qty += qty
            not_in_collection.append(
                {
                    "name": str(pub["name"]),
                    "quantity": qty,
                    "status": "nicht in deiner Sammlung",
                }
            )
            return
        not_in_collection_qty += qty
        not_in_collection.append(
            {
                "name": name,
                "quantity": qty,
                "status": "nicht in deiner Sammlung",
            }
        )

    if detected_format == "csv":
        reader = csv.reader(io.StringIO(text))
        headers: list[str] = []
        qty_idx: int | None = None
        name_idx: int | None = None
        section_idx: int | None = None
        for lineno, row in enumerate(reader, 1):
            if not row or all(not cell.strip() for cell in row):
                continue
            if not headers:
                headers = [cell.strip().casefold() for cell in row]
                for i, h in enumerate(headers):
                    if name_idx is None and h in _CSV_NAME_COLS:
                        name_idx = i
                    elif qty_idx is None and h in _CSV_QTY_COLS:
                        qty_idx = i
                    elif section_idx is None and h in _CSV_SECTION_COLS:
                        section_idx = i
                if name_idx is None:
                    name_idx = 1 if len(headers) > 1 else 0
                continue
            if section_idx is not None and section_idx < len(row):
                sec = row[section_idx].strip().casefold()
                if sec in _SKIPPED_SECTIONS:
                    continue
            raw_qty = row[qty_idx].strip() if qty_idx is not None and qty_idx < len(row) else "1"
            raw_name = row[name_idx].strip() if name_idx is not None and name_idx < len(row) else ""
            # Only the quantity and name cells are ever judged or echoed, never the whole row.
            joined = f"{raw_qty},{raw_name}"
            if len(joined) > _MAX_LINE_CHARS:
                unrecognized_lines.append(_too_long(lineno, joined))
                continue
            try:
                qty = int(raw_qty.rstrip("xX") or "1") if len(raw_qty) <= 8 else -1
            except ValueError:
                unrecognized_lines.append(
                    {
                        "line": lineno,
                        "raw": _clean_raw(joined),
                        "status": "unreadable",
                        "reason": "ungültige Anzahl",
                    }
                )
                continue
            if not 1 <= qty <= _MAX_QUANTITY:
                unrecognized_lines.append(_bad_quantity(lineno, joined))
                continue
            _classify_entry(qty, raw_name, lineno, joined)
    else:
        line_re = re.compile(r"^(?:([-+]?\d+)\s*[xX]?\s+)?(.+?)$")
        for lineno, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if len(line) > _MAX_LINE_CHARS:
                unrecognized_lines.append(_too_long(lineno, line))
                continue
            if line.lower().startswith("sb:"):
                continue
            lower = line.casefold().rstrip(":")
            if lower in _SKIPPED_SECTIONS:
                skipped_section = True
                continue
            if lower in _ACTIVE_SECTIONS:
                skipped_section = False
                continue
            if skipped_section:
                continue
            m = line_re.match(line)
            if not m:
                unrecognized_lines.append(
                    {
                        "line": lineno,
                        "raw": _clean_raw(raw_line),
                        "status": "unreadable",
                        "reason": "Format nicht erkannt",
                    }
                )
                continue
            if m.group(1) is not None and len(m.group(1)) > 8:
                unrecognized_lines.append(_bad_quantity(lineno, line))
                continue
            qty = int(m.group(1) or "1")
            if not 1 <= qty <= _MAX_QUANTITY:
                unrecognized_lines.append(_bad_quantity(lineno, line))
                continue
            raw_name = m.group(2).strip()
            if raw_name.casefold() in _SECTION_HEADERS:
                continue
            _classify_entry(qty, raw_name, lineno, raw_line)

    # Return point: no returned text field may carry an amount, whatever path produced it.
    for entry in not_in_collection:
        entry["name"] = _scrub_amounts(str(entry["name"]))
    for entry in unrecognized_lines:
        entry["raw"] = _scrub_amounts(str(entry["raw"]))
        entry["reason"] = _scrub_amounts(str(entry["reason"]))

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
    return {
        "detected_format": detected_format,
        "cards": [{"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone} for c in cards],
        "matched": matched_list,
        "in_collection": matched_list,
        "not_in_collection": not_in_collection,
        "outside_color_identity": outside_color_identity,
        "unrecognized_lines": unrecognized_lines,
        "ignored_annotations": ignored_annotations,
        "summary": {
            "in_collection_cards": sum(matched_qty.values()),
            "not_in_collection_cards": not_in_collection_qty,
            "outside_color_identity_cards": outside_qty,
            "unrecognized_lines": len(unrecognized_lines),
        },
    }
