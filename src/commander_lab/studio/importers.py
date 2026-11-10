"""Importers of the Studio: original files in, rows with their source out.

Each importer reads one original file, records it as a source (bound to its SHA-256) and
writes rows that point back to that source. Nothing is invented: a missing value stays NULL
and means unknown, never zero.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .decks import RevisionCard, create_revision
from .store import DataClass, StudioStore, sha256_file

IDENTITY_SHEET = "01_CARD_IDENTITY"
INVENTORY_SHEET = "05_INVENTORY_CURRENT"


def _sheet_rows(path: Path, sheet: str) -> list[dict[str, Any]]:
    workbook = load_workbook(filename=path, read_only=True, data_only=True)
    try:
        if sheet not in workbook.sheetnames:
            raise ValueError(f"{path.name}: sheet {sheet} is missing")
        rows = workbook[sheet].iter_rows(values_only=True)
        header = [str(value) if value is not None else "" for value in next(rows)]
        return [
            dict(zip(header, row, strict=False))
            for row in rows
            if any(value is not None for value in row)
        ]
    finally:
        workbook.close()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _flag(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    return int(str(value).strip().casefold() in {"true", "1", "yes", "ja"})


def _integer(value: Any, *, field: str, card: str) -> int:
    if value is None or value == "":
        raise ValueError(f"{card}: {field} is empty")
    return int(value)


def import_inventory_workbook(store: StudioStore, path: str | Path) -> dict[str, int]:
    """Read card identities and the current inventory from the Owner's inventory workbook."""
    workbook_path = Path(path)
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title=workbook_path.name,
        sha256=sha256_file(workbook_path),
    )
    identities = _sheet_rows(workbook_path, IDENTITY_SHEET)
    inventory = _sheet_rows(workbook_path, INVENTORY_SHEET)
    db = store.connection
    with db:
        for row in identities:
            card_id = _text(row.get("card_id"))
            name = _text(row.get("oracle_name"))
            if card_id is None or name is None:
                raise ValueError(f"{IDENTITY_SHEET}: row without card_id or oracle_name")
            mana_value = row.get("mana_value")
            db.execute(
                "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(card_id) DO UPDATE SET oracle_id=excluded.oracle_id, "
                "oracle_name=excluded.oracle_name, color_identity=excluded.color_identity, "
                "mana_cost=excluded.mana_cost, mana_value=excluded.mana_value, "
                "type_line=excluded.type_line, oracle_text=excluded.oracle_text, "
                "is_basic_land=excluded.is_basic_land, commander_legal=excluded.commander_legal, "
                "legality_verified_at=excluded.legality_verified_at, "
                "identity_evidence=excluded.identity_evidence, source_id=excluded.source_id",
                (
                    card_id,
                    _text(row.get("oracle_id")),
                    name,
                    _text(row.get("color_identity")) or "",
                    _text(row.get("mana_cost")),
                    float(mana_value) if mana_value is not None else None,
                    _text(row.get("type_line")),
                    _text(row.get("oracle_text")),
                    _flag(row.get("is_basic_land")) or 0,
                    _flag(row.get("commander_legal")),
                    _text(row.get("legality_verified_at")),
                    _text(row.get("identity_evidence_type")),
                    source_id,
                ),
            )
        db.execute("DELETE FROM inventory")
        for row in inventory:
            card_id = _text(row.get("card_id"))
            if card_id is None:
                raise ValueError(f"{INVENTORY_SHEET}: row without card_id")
            label = _text(row.get("oracle_name")) or card_id
            lots = row.get("number_of_lots")
            db.execute(
                "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, "
                "available_lower_bound, quantity_exact, lots, last_verified_at, source_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card_id,
                    _integer(row.get("observed_quantity"), field="observed_quantity", card=label),
                    _integer(
                        row.get("physical_owned_quantity_lower_bound"),
                        field="physical_owned_quantity_lower_bound",
                        card=label,
                    ),
                    _integer(
                        row.get("reserved_for_opponents_quantity"),
                        field="reserved_for_opponents_quantity",
                        card=label,
                    ),
                    _integer(
                        row.get("available_for_own_decks_quantity_lower_bound"),
                        field="available_for_own_decks_quantity_lower_bound",
                        card=label,
                    ),
                    _flag(row.get("quantity_exact")) or 0,
                    int(lots) if lots is not None else None,
                    _text(row.get("last_verified_at")),
                    source_id,
                ),
            )
    return {"cards": len(identities), "inventory": len(inventory)}


def import_studio_selection(
    store: StudioStore,
    path: str | Path,
    *,
    deck_id: str,
    name: str,
    commander_names: list[str],
    branch: str = "main",
) -> dict[str, Any]:
    """Turn the unchanged selection export of the earlier HTML studio into a deck revision.

    The file is only read. Entries marked ``reserve`` are kept out of the deck and reported,
    so nothing of the Owner's selection is lost or silently added.
    """
    selection_path = Path(path)
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    state = payload.get("state") if isinstance(payload, dict) else None
    if not isinstance(state, dict) or not isinstance(state.get("deck"), dict):
        raise ValueError(f"{selection_path.name}: no state.deck object")
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title=selection_path.name,
        sha256=sha256_file(selection_path),
        snapshot_date=_text(payload.get("date")),
    )
    cards: list[RevisionCard] = []
    for commander in commander_names:
        commander_id = store.card_id_by_name(commander)
        if commander_id is None:
            raise ValueError(f"commander not found exactly once in the collection: {commander}")
        cards.append(RevisionCard(commander_id, 1, "commander"))
    for card_id, entry in state["deck"].items():
        quantity = int(entry.get("qty", 1)) if isinstance(entry, Mapping) else int(entry)
        cards.append(RevisionCard(str(card_id), quantity, "main"))
    in_deck = set(state["deck"])
    raw_status = state.get("status")
    statuses: dict[str, Any] = raw_status if isinstance(raw_status, dict) else {}
    reserve = sorted(
        card_id
        for card_id, status in statuses.items()
        if card_id not in in_deck
        and (status.get("status") if isinstance(status, Mapping) else status) == "reserve"
    )
    revision_id = create_revision(
        store,
        deck_id=deck_id,
        name=name,
        cards=cards,
        note=f"imported from {selection_path.name}",
        source_id=source_id,
        branch=branch,
    )
    return {"revision_id": revision_id, "main_entries": len(in_deck), "reserve_card_ids": reserve}


def _csv_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def import_corpus_register(store: StudioStore, path: str | Path) -> dict[str, int]:
    """Read the register of source decks (one row per source state, duplicates marked)."""
    register_path = Path(path)
    source_id = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title=register_path.name,
        sha256=sha256_file(register_path),
    )
    count = 0
    with store.connection as db:
        for row in _csv_rows(register_path):
            db.execute(
                "INSERT OR REPLACE INTO corpus_deck(deck_id, cohort, url, platform, play_group, "
                "deck_date, tags, fingerprint, duplicate_of, legality_audit, source_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["deck_id"],
                    row["source_cohort"],
                    row["original_url"],
                    row["source_platform"],
                    row["group"],
                    row["date"] or None,
                    row["source_archetype_tags"],
                    row["fingerprint_scryfall_oracle"],
                    row["exact_duplicate_of"] or None,
                    row["current_legality_name_audit"],
                    source_id,
                ),
            )
            count += 1
    return {"decks": count}


def import_corpus_cards(store: StudioStore, path: str | Path) -> dict[str, int]:
    """Read the normalized card rows of the source decks. Needs the register first."""
    cards_path = Path(path)
    store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title=cards_path.name,
        sha256=sha256_file(cards_path),
    )
    known = {str(row[0]) for row in store.connection.execute("SELECT deck_id FROM corpus_deck")}
    merged: dict[tuple[str, str, str], tuple[str | None, int, str]] = {}
    skipped = 0
    for row in _csv_rows(cards_path):
        if row["deck_id"] not in known:
            skipped += 1
            continue
        key = (row["deck_id"], row["canonical_name"] or row["raw_card_name"], row["section"])
        previous = merged.get(key)
        quantity = int(row["quantity"]) + (previous[1] if previous else 0)
        merged[key] = (row["oracle_id"] or None, quantity, row["normalization_status"])
    with store.connection as db:
        db.execute("DELETE FROM corpus_deck_card")
        db.executemany(
            "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
            "normalization_status) VALUES (?, ?, ?, ?, ?, ?)",
            [(*key, *value) for key, value in merged.items()],
        )
    return {"rows": len(merged), "rows_without_registered_deck": skipped}


def _number(value: str) -> float | None:
    return float(value) if value.strip() else None


def import_edhrec_table(store: StudioStore, path: str | Path) -> dict[str, int]:
    """Read EDHREC card rows: one observation per card and theme page, with numerator,
    denominator, page address and snapshot note. An empty lift stays unknown."""
    table_path = Path(path)
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title=table_path.name,
        sha256=sha256_file(table_path),
    )
    known = {str(row[0]) for row in store.connection.execute("SELECT card_id FROM card")}
    count = 0
    with store.connection as db:
        db.execute("DELETE FROM observation WHERE source_id = ?", (source_id,))
        for row in _csv_rows(table_path):
            card_id = row.get("card_id") or None
            base = (
                card_id if card_id in known else None,
                row["card_name"],
                f"edhrec:{row['theme']}",
            )
            tail = (row["url"], row.get("snapshot_utc") or None, source_id)
            numerator = int(row["num_decks"]) if row["num_decks"].strip() else None
            denominator = int(row["potential_decks"]) if row["potential_decks"].strip() else None
            for metric, value, num, den in (
                ("inclusion_pct", _number(row["inclusion_pct"]), numerator, denominator),
                ("lift", _number(row["lift"]), None, None),
            ):
                db.execute(
                    "INSERT INTO observation(card_id, card_name, cohort, metric, value, "
                    "numerator, denominator, data_class, url, snapshot, source_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        *base,
                        metric,
                        value,
                        num,
                        den,
                        (
                            DataClass.ORIGINAL_SOURCE if value is not None else DataClass.UNKNOWN
                        ).value,
                        *tail,
                    ),
                )
            count += 1
    return {"rows": count}
