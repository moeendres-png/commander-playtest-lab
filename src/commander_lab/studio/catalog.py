"""Public card data (Scryfall oracle file) in the Studio store, and what is derived from it.

The oracle file is public and carries nothing about the Owner. Card facts shown in the
Studio (color identity, legality, type, text, mana value) come from it once a collection
card is linked; the inventory workbook stays the source for what is owned.
"""

from __future__ import annotations

import csv
import gzip
import json
from collections.abc import Iterator
from pathlib import Path

from .store import DataClass, StudioStore, sha256_file

_SKIPPED_LAYOUTS = frozenset(
    {"token", "double_faced_token", "emblem", "art_series", "planar", "scheme", "vanguard"}
)
_COLOR_ORDER = "WUBRG"


def _objects(path: Path) -> Iterator[dict[str, object]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip().rstrip(",")
            if len(line) < 3:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                yield value


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _letters(value: object) -> str:
    found = {str(item) for item in value} if isinstance(value, list) else set()
    return "".join(letter for letter in _COLOR_ORDER + "C" if letter in found)


def _faces(card: dict[str, object]) -> list[dict[str, object]]:
    faces = card.get("card_faces")
    if not isinstance(faces, list):
        return []
    return [face for face in faces if isinstance(face, dict)]


def _image(holder: dict[str, object]) -> str | None:
    uris = holder.get("image_uris")
    return _text(uris.get("normal")) if isinstance(uris, dict) else None


def _row(card: dict[str, object], source_id: str) -> tuple[object, ...] | None:
    oracle_id = _text(card.get("oracle_id"))
    name = _text(card.get("name"))
    layout = _text(card.get("layout")) or ""
    if oracle_id is None or name is None or layout in _SKIPPED_LAYOUTS:
        return None
    faces = _faces(card)
    text = _text(card.get("oracle_text"))
    if text is None and faces:
        text = "\n//\n".join(str(face.get("oracle_text") or "") for face in faces)
    cost = _text(card.get("mana_cost"))
    if cost is None and faces:
        cost = " // ".join(c for c in (str(f.get("mana_cost") or "") for f in faces) if c) or None
    front = _image(card) or (_image(faces[0]) if faces else None)
    back = _image(faces[1]) if len(faces) > 1 and _image(card) is None else None
    legalities = card.get("legalities")
    legality = str(legalities.get("commander")) if isinstance(legalities, dict) else "unknown"
    keywords = card.get("keywords")
    mana_value = card.get("cmc")
    rank = card.get("edhrec_rank")
    first = faces[0] if faces else card
    changer = card.get("game_changer")
    return (
        oracle_id,
        str(card.get("id")),
        name,
        name.split(" // ")[0],
        layout,
        cost,
        float(mana_value) if isinstance(mana_value, int | float) else None,
        _text(card.get("type_line")),
        text,
        _letters(card.get("color_identity")).replace("C", ""),
        legality,
        rank if isinstance(rank, int) else None,
        json.dumps(keywords if isinstance(keywords, list) else []),
        _letters(card.get("produced_mana")),
        _text(card.get("power")) or _text(first.get("power")),
        _text(card.get("toughness")) or _text(first.get("toughness")),
        int(changer) if isinstance(changer, bool) else None,
        _text(card.get("released_at")),
        front,
        back,
        source_id,
    )


def import_scryfall_oracle(store: StudioStore, path: str | Path) -> dict[str, object]:
    """Read the public oracle card file (``.jsonl`` or ``.jsonl.gz``, one card per line)
    and link the collection to it."""
    file_path = Path(path)
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title=file_path.name,
        sha256=sha256_file(file_path),
        url="https://scryfall.com/docs/api/bulk-data",
    )
    rows = [row for row in (_row(card, source_id) for card in _objects(file_path)) if row]
    with store.connection as db:
        db.execute("DELETE FROM scryfall_card")
        db.executemany(
            "INSERT OR REPLACE INTO scryfall_card VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    report: dict[str, object] = {"oracle_cards": len(rows)}
    report.update(link_collection(store))
    report.update(refresh_corpus_stats(store))
    return report


def link_collection(store: StudioStore) -> dict[str, object]:
    """Give every collection card its oracle id by exact name (full name or front face).

    A name that fits no card or more than one stays unlinked and keeps its workbook facts.
    """
    db = store.connection
    linked = 0
    unlinked: list[str] = []
    with db:
        for card in db.execute("SELECT card_id, oracle_name FROM card").fetchall():
            name = str(card["oracle_name"])
            found = (
                db.execute("SELECT oracle_id FROM scryfall_card WHERE name = ?", (name,)).fetchall()
                or db.execute(
                    "SELECT oracle_id FROM scryfall_card WHERE front_name = ?", (name,)
                ).fetchall()
            )
            if len(found) == 1:
                db.execute(
                    "UPDATE card SET oracle_id = ? WHERE card_id = ?",
                    (found[0]["oracle_id"], card["card_id"]),
                )
                linked += 1
            else:
                unlinked.append(name)
    return {
        "linked": linked,
        "unlinked": sorted(unlinked),
        "fact_differences": fact_differences(store),
    }


def fact_differences(store: StudioStore) -> list[dict[str, str]]:
    """Collection cards whose workbook facts differ from the public card data."""
    found: list[dict[str, str]] = []
    for row in store.connection.execute(
        "SELECT c.oracle_name, c.color_identity AS own_colors, c.commander_legal AS own_legal, "
        "s.color_identity, s.commander_legality FROM card c "
        "JOIN scryfall_card s USING (oracle_id) ORDER BY c.oracle_name"
    ):
        name = str(row["oracle_name"])
        own = "".join(x for x in _COLOR_ORDER if x in str(row["own_colors"] or ""))
        if own != row["color_identity"]:
            found.append(
                {
                    "oracle_name": name,
                    "field": "color_identity",
                    "workbook": own,
                    "public": str(row["color_identity"]),
                }
            )
        if row["own_legal"] is not None and bool(row["own_legal"]) != (
            row["commander_legality"] == "legal"
        ):
            found.append(
                {
                    "oracle_name": name,
                    "field": "commander_legal",
                    "workbook": str(row["own_legal"]),
                    "public": str(row["commander_legality"]),
                }
            )
    return found


def refresh_corpus_stats(store: StudioStore) -> dict[str, object]:
    """Per source deck: lands, creatures and mana value, counted from the public card data.

    A land is a card whose front type line says Land. Cards that are not found in the
    card data are not counted; ``resolved`` says how many cards of the deck were found.
    """
    with store.connection as db:
        db.execute("DELETE FROM corpus_deck_stat")
        db.execute(
            "INSERT INTO corpus_deck_stat "
            "SELECT k.deck_id, SUM(k.quantity), "
            "SUM(CASE WHEN s.oracle_id IS NULL THEN 0 ELSE k.quantity END), "
            "SUM(CASE WHEN s.front_type LIKE '%Land%' THEN k.quantity ELSE 0 END), "
            "SUM(CASE WHEN s.front_type LIKE '%Creature%' THEN k.quantity ELSE 0 END), "
            "SUM(CASE WHEN s.oracle_id IS NOT NULL AND s.front_type NOT LIKE '%Land%' "
            "THEN k.quantity * COALESCE(s.mana_value, 0) ELSE 0 END), "
            "SUM(CASE WHEN s.oracle_id IS NOT NULL AND s.front_type NOT LIKE '%Land%' "
            "THEN k.quantity ELSE 0 END) "
            "FROM corpus_deck_card k LEFT JOIN ("
            "  SELECT oracle_id, mana_value, CASE WHEN INSTR(type_line, ' // ') > 0 "
            "  THEN SUBSTR(type_line, 1, INSTR(type_line, ' // ') - 1) ELSE type_line END "
            "  AS front_type FROM scryfall_card) s ON s.oracle_id = k.oracle_id "
            "WHERE k.section != 'sideboard' GROUP BY k.deck_id"
        )
    return {"corpus_decks_with_stats": store.count("corpus_deck_stat")}


def import_cohort(store: StudioStore, path: str | Path, *, cohort: str) -> dict[str, object]:
    """Name a group of source decks: every ``deck_id`` in the CSV file joins ``cohort``."""
    file_path = Path(path)
    store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title=file_path.name,
        sha256=sha256_file(file_path),
    )
    with file_path.open(encoding="utf-8-sig", newline="") as handle:
        wanted = {row["deck_id"] for row in csv.DictReader(handle) if row.get("deck_id")}
    known = {str(row[0]) for row in store.connection.execute("SELECT deck_id FROM corpus_deck")}
    with store.connection as db:
        db.execute("DELETE FROM corpus_cohort WHERE cohort = ?", (cohort,))
        db.executemany(
            "INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)",
            [(cohort, deck_id) for deck_id in sorted(wanted & known)],
        )
    return {"cohort": cohort, "decks": len(wanted & known), "unknown_decks": len(wanted - known)}
