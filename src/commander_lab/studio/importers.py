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

from openpyxl import load_workbook

from .catalog import refresh_corpus_stats
from .decks import RevisionCard, create_revision
from .store import DataClass, StudioStore, now_utc, sha256_file

IDENTITY_SHEET = "01_CARD_IDENTITY"
INVENTORY_SHEET = "05_INVENTORY_CURRENT"


def _sheet_rows(path: Path, sheet: str) -> list[dict[str, object]]:
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


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _flag(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    return int(str(value).strip().casefold() in {"true", "1", "yes", "ja"})


def _integer(value: object, *, field: str, card: str) -> int:
    if value is None or value == "":
        raise ValueError(f"{card}: {field} is empty")
    return _whole(value)


def _whole(value: object) -> int:
    return int(value) if isinstance(value, int | float) else int(str(value))


def _real(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value) if isinstance(value, int | float) else float(str(value))


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
                    _real(mana_value),
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
                    _whole(lots) if lots is not None else None,
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
) -> dict[str, object]:
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
    statuses: dict[str, object] = raw_status if isinstance(raw_status, dict) else {}
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
    known = {str(row[0]) for row in store.connection.execute("SELECT card_id FROM card")}
    with store.connection as db:
        for card_id in reserve:
            if card_id not in known:
                continue
            db.execute(
                "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
                "VALUES (?, 0, 0, 'Reserve (Auswahl-Import)', ?) "
                "ON CONFLICT(card_id) DO UPDATE SET "
                "note = CASE WHEN card_mark.note = '' THEN excluded.note ELSE card_mark.note END",
                (card_id, now_utc()),
            )
    return {"revision_id": revision_id, "main_entries": len(in_deck), "reserve_card_ids": reserve}


def import_lab_deck_snapshot(
    store: StudioStore,
    path: str | Path,
    *,
    deck_id: str | None = None,
    name: str | None = None,
    branch: str = "main",
) -> dict[str, object]:
    """Import an on-disk Lab deck snapshot JSON (``DECKBAU_INTERFACE.md``) as a revision."""
    snapshot_path = Path(path)
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cards"), list):
        raise ValueError(f"{snapshot_path.name}: no cards list")
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title=snapshot_path.name,
        sha256=sha256_file(snapshot_path),
    )
    resolved_deck_id = (
        deck_id or str(payload.get("deck_id") or "deck").split("/")[-1].strip() or "deck"
    )
    resolved_name = name or str(payload.get("name") or resolved_deck_id)
    cards: list[RevisionCard] = []
    for entry in payload["cards"]:
        if not isinstance(entry, Mapping):
            continue
        card_name = _text(entry.get("oracle_name"))
        if card_name is None:
            raise ValueError(f"{snapshot_path.name}: card entry without oracle_name")
        card_id = store.card_id_by_oracle_or_name(None, card_name)
        if card_id is None:
            raise ValueError(f"card not found in collection: {card_name}")
        quantity = int(entry.get("quantity", 1))
        zone = str(entry.get("zone") or "main")
        cards.append(RevisionCard(card_id, quantity, zone))
    revision_id = create_revision(
        store,
        deck_id=resolved_deck_id,
        name=resolved_name,
        cards=cards,
        note=f"imported from {snapshot_path.name}",
        source_id=source_id,
        branch=branch,
    )
    return {
        "deck_id": resolved_deck_id,
        "branch": branch,
        "revision_id": revision_id,
        "entries": len(cards),
    }


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


def import_hub_corpus(store: StudioStore, folder: str | Path) -> dict[str, int]:
    """Import the 2026-11-10 objective research hub (994 catalog, card dictionary, compact
    99-card mainboards, Koma cohort, and neutral non-mainboard observations).

    Rules enforced:
    - Only verified Bracket 1 is excluded; Brackets 2-5, unassigned, and UNKNOWN stay in.
    - Duplicate mainboard fingerprints point to their unique representative deck_id.
    - Non-mainboard sections (MAYBEBOARD, CUTS, SIDEBOARD, TOKENS, COMMANDER) are stored in
      ``neutral_board_row`` and never mixed into ``corpus_deck_card`` mainboard frequencies.
    """
    hub_dir = Path(folder)
    catalog_path = hub_dir / "01_DECK_CATALOG_994_SOURCES.csv"
    if not catalog_path.is_file():
        raise ValueError(f"{hub_dir}: 01_DECK_CATALOG_994_SOURCES.csv is missing")
    catalog_source_id = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title=catalog_path.name,
        sha256=sha256_file(catalog_path),
        snapshot_date="2026-11-10",
    )
    db = store.connection
    existing_meta = {
        str(row["deck_id"]): (
            str(row["play_group"]),
            row["deck_date"],
            str(row["legality_audit"]),
        )
        for row in db.execute(
            "SELECT deck_id, play_group, deck_date, legality_audit FROM corpus_deck"
        )
    }
    catalog_rows = [
        row
        for row in _csv_rows(catalog_path)
        if row.get("bracket_user_set", "").strip().upper() not in {"1", "BRACKET_1"}
    ]
    representatives = {
        row["content_fingerprint_sha256"]: row["deck_id"]
        for row in catalog_rows
        if row.get("unique_deck_representative", "").strip().casefold() == "true"
    }
    dictionary: dict[str, tuple[str, str | None, str]] = {}
    for dict_path in sorted(hub_dir.glob("02_CARD_DICTIONARY_*.csv")):
        store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=dict_path.name,
            sha256=sha256_file(dict_path),
            snapshot_date="2026-11-10",
        )
        for row in _csv_rows(dict_path):
            dictionary[row["card_code"]] = (
                row["canonical_name"],
                row["oracle_id"] or None,
                row["source_normalization_status"],
            )
    accepted_ids = {row["deck_id"] for row in catalog_rows}
    merged_cards: dict[tuple[str, str, str], tuple[str | None, int, str]] = {}
    koma_decks: set[str] = set()
    for mb_path in sorted(hub_dir.glob("03_MAINBOARD_99_COMPACT_*.jsonl")):
        store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=mb_path.name,
            sha256=sha256_file(mb_path),
            snapshot_date="2026-11-10",
        )
        with mb_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                deck_id = str(payload["deck_id"])
                if deck_id not in accepted_ids:
                    continue
                for pair in payload["cards"]:
                    code = str(pair[0])
                    qty = int(pair[1])
                    card_name, oracle_id, norm_status = dictionary[code]
                    if card_name == "Koma, Cosmos Serpent":
                        koma_decks.add(deck_id)
                    key = (deck_id, card_name, "mainboard")
                    prev = merged_cards.get(key)
                    merged_cards[key] = (
                        oracle_id,
                        qty + (prev[1] if prev else 0),
                        norm_status,
                    )
    neutral_rows: dict[tuple[str, str, str], tuple[str, str | None, int, str, str]] = {}
    for neutral_path in sorted(hub_dir.glob("06_OTHER_BOARDS_NEUTRAL_*.csv")):
        neutral_source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE,
            title=neutral_path.name,
            sha256=sha256_file(neutral_path),
            snapshot_date="2026-11-10",
        )
        for row in _csv_rows(neutral_path):
            n_key = (row["source_key"], row["section"], row["name"])
            prev_n = neutral_rows.get(n_key)
            qty = int(row["quantity"] or 1) + (prev_n[2] if prev_n else 0)
            neutral_rows[n_key] = (
                row["batch"],
                row["oracle_id"] or None,
                qty,
                row["status"],
                neutral_source_id,
            )
    c087_baseline_ids = {
        row["deck_id"] for row in catalog_rows if row.get("cohort") == "C087_BASELINE_2026_11_10"
    }
    new_2026_ids = {
        row["deck_id"]
        for row in catalog_rows
        if row.get("is_new_vs_baseline", "").strip().casefold() == "true"
    }
    no_koma_ids = accepted_ids - koma_decks
    with db:
        for row in catalog_rows:
            deck_id = row["deck_id"]
            fp = row["content_fingerprint_sha256"]
            is_rep = row.get("unique_deck_representative", "").strip().casefold() == "true"
            dup_of = None if is_rep else representatives.get(fp)
            prev_meta = existing_meta.get(deck_id)
            play_group = prev_meta[0] if prev_meta else "unklassifiziert"
            deck_date = prev_meta[1] if prev_meta else None
            legality_audit = prev_meta[2] if prev_meta else "legal"
            tag = row.get("original_archetype_tag", "")
            if tag == "NOT_LISTED":
                tag = ""
            db.execute(
                "INSERT OR REPLACE INTO corpus_deck(deck_id, cohort, url, platform, play_group, "
                "deck_date, tags, fingerprint, duplicate_of, legality_audit, source_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    deck_id,
                    row["cohort"],
                    row["original_url"],
                    row["platform"] or row["source"],
                    play_group,
                    deck_date,
                    tag,
                    fp,
                    dup_of,
                    legality_audit,
                    catalog_source_id,
                ),
            )
        if merged_cards:
            db.execute("DELETE FROM corpus_deck_card")
            db.executemany(
                "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
                "normalization_status) VALUES (?, ?, ?, ?, ?, ?)",
                [(*key, *val) for key, val in merged_cards.items()],
            )
        for cohort_name, members in (
            ("c087_945", c087_baseline_ids),
            ("new_2026_11_10", new_2026_ids),
            ("koma_in_99", koma_decks),
            ("no_koma_in_99", no_koma_ids),
        ):
            db.execute("DELETE FROM corpus_cohort WHERE cohort = ?", (cohort_name,))
            db.executemany(
                "INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)",
                [(cohort_name, d_id) for d_id in sorted(members)],
            )
        if neutral_rows:
            db.execute("DELETE FROM neutral_board_row")
            db.executemany(
                "INSERT INTO neutral_board_row(source_key, section, card_name, batch, oracle_id, "
                "quantity, status, source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(*key, *val) for key, val in neutral_rows.items()],
            )
        if store.count("card_role") > 0:
            db.execute("DELETE FROM corpus_deck_role")
            db.execute(
                "INSERT INTO corpus_deck_role "
                "SELECT k.deck_id, r.role, SUM(k.quantity) FROM corpus_deck_card k "
                "JOIN card_role r ON r.oracle_id = k.oracle_id "
                "WHERE k.section != 'sideboard' GROUP BY k.deck_id, r.role"
            )
    if store.count("scryfall_card") > 0:
        refresh_corpus_stats(store)
    unique_decks = sum(
        1
        for r in catalog_rows
        if r.get("unique_deck_representative", "").strip().casefold() == "true"
    )
    return {
        "decks": len(catalog_rows),
        "unique_decks": unique_decks,
        "mainboard_rows": len(merged_cards),
        "koma_decks": len(koma_decks),
        "neutral_board_rows": len(neutral_rows),
    }


def import_edhrec_cardrecs_csv(store: StudioStore, path: str | Path) -> dict[str, int]:
    """Import ``cardrecs_alle.csv`` (normalized EDHREC card recommendations across cohorts).

    Preserves exact ``decks_with_card`` (numerator) and ``eligible_decks`` (denominator) per
    cohort without mixing cohorts. ``synergy`` is stored as ``synergy_pct``, separate from
    ``lift``.
    """
    table_path = Path(path)
    source_id = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title=table_path.name,
        sha256=sha256_file(table_path),
    )
    count = 0
    seen: set[tuple[str, str]] = set()
    with store.connection as db:
        db.execute("DELETE FROM observation WHERE source_id = ?", (source_id,))
        for row in _csv_rows(table_path):
            card_name = row["karte"].strip()
            rubrik = row["rubrik"].strip()
            cohort = f"edhrec:{rubrik}"
            if (card_name, cohort) in seen:
                continue
            seen.add((card_name, cohort))
            card_id = store.card_id_by_oracle_or_name(None, card_name)
            numerator = (
                int(float(row["decks_with_card"]))
                if row.get("decks_with_card", "").strip()
                else None
            )
            denominator = (
                int(float(row["eligible_decks"])) if row.get("eligible_decks", "").strip() else None
            )
            tail = (row.get("source_url") or None, row.get("retrieved_at") or None, source_id)
            for metric, raw_val, num, den in (
                ("inclusion_pct", row.get("inclusion_pct", ""), numerator, denominator),
                ("lift", row.get("lift", ""), None, None),
                ("synergy_pct", row.get("synergy", ""), None, None),
            ):
                value = _number(raw_val)
                if metric == "synergy_pct" and value is not None and abs(value) <= 1.0:
                    value = round(value * 100.0, 2)
                db.execute(
                    "INSERT INTO observation(card_id, card_name, cohort, metric, value, "
                    "numerator, denominator, data_class, url, snapshot, source_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        card_id,
                        card_name,
                        cohort,
                        metric,
                        value,
                        num,
                        den,
                        (
                            DataClass.NORMALIZED_SOURCE if value is not None else DataClass.UNKNOWN
                        ).value,
                        *tail,
                    ),
                )
            count += 1
    return {"rows": count}


def _import_one_edhrec_delta_file(store: StudioStore, file_path: Path) -> int:
    source_id = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title=file_path.name,
        sha256=sha256_file(file_path),
        snapshot_date="2026-11-10",
    )
    count = 0
    with store.connection as db, file_path.open(encoding="utf-8") as handle:
        db.execute("DELETE FROM observation WHERE source_id = ?", (source_id,))
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            kind = str(row.get("data_kind") or "")
            oracle_id = _text(row.get("oracle_id"))
            card_name = (
                _text(row.get("oracle_name"))
                or _text(row.get("reported_card_name"))
                or _text(row.get("card_name_on_page"))
                or _text(row.get("card_name_reported"))
            )
            if card_name is None:
                continue
            card_id = store.card_id_by_oracle_or_name(oracle_id, card_name)
            url = _text(row.get("original_url")) or _text(row.get("source_url"))
            if kind == "EDHREC_CARDRECS_BRACKET2_CORE":
                cohort = "edhrec:core_b2_563_index"
                num = (
                    int(row["decks_with_card_reported"])
                    if row.get("decks_with_card_reported") is not None
                    else None
                )
                # eligible_decks_per_card is None (NOT_LISTED_IN_WEB_INDEX_TEXT); never substitute
                # cohort_decks_reported (563) as a verified per-card denominator.
                den = (
                    int(row["eligible_decks_per_card"])
                    if row.get("eligible_decks_per_card") is not None
                    else None
                )
                inc = _real(row.get("inclusion_pct_reported"))
                lift = _real(row.get("lift_reported"))
                syn: float | None = None
                snap = (
                    f"{row.get('source_index_crawled_date') or '2026-11-09'} "
                    f"(cohort_decks={row.get('cohort_decks_reported')}; "
                    f"eligible_decks={row.get('eligible_decks_status') or 'NOT_LISTED'})"
                )
            elif kind in {
                "EDHREC_CARDRECS_BRACKET2_CORE_HISTORIC_NN",
                "EDHREC_CARDRECS_BRACKET3_UPGRADED_HISTORIC_NN",
            }:
                cohort = (
                    "edhrec:core_b2_634_hist"
                    if "BRACKET2" in kind
                    else "edhrec:upgraded_b3_593_hist"
                )
                num = (
                    int(row["decks_with_card_n_shown"])
                    if row.get("decks_with_card_n_shown") is not None
                    else None
                )
                den = (
                    int(row["eligible_decks_N_shown"])
                    if row.get("eligible_decks_N_shown") is not None
                    else None
                )
                inc = _real(row.get("inclusion_pct_shown"))
                lift = _real(row.get("lift_shown"))
                syn = _real(row.get("synergy_pct_shown"))
                snap = str(row.get("retrieval_utc") or "2026-11-10")
            else:
                sub = str(row.get("source_cohort") or "subcohort")
                cohort = f"edhrec:{sub}"
                num = (
                    int(row["decks_with_card_n_shown"])
                    if row.get("decks_with_card_n_shown") is not None
                    else None
                )
                den = (
                    int(row["eligible_decks_N_shown"])
                    if row.get("eligible_decks_N_shown") is not None
                    else None
                )
                inc = _real(row.get("inclusion_pct_shown"))
                lift = _real(row.get("lift_x_reported"))
                syn = _real(row.get("synergy_pct_shown"))
                snap = str(row.get("read_at_utc") or "2026-11-10")
            metrics: list[tuple[str, float | None, int | None, int | None]] = [
                ("inclusion_pct", inc, num, den),
                ("lift", lift, None, None),
            ]
            if syn is not None:
                metrics.append(("synergy_pct", syn, None, None))
            for metric, value, m_num, m_den in metrics:
                db.execute(
                    "INSERT INTO observation(card_id, card_name, cohort, metric, value, "
                    "numerator, denominator, data_class, url, snapshot, source_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        card_id,
                        card_name,
                        cohort,
                        metric,
                        value,
                        m_num,
                        m_den,
                        (
                            DataClass.NORMALIZED_SOURCE if value is not None else DataClass.UNKNOWN
                        ).value,
                        url,
                        snap,
                        source_id,
                    ),
                )
            count += 1
    return count


def import_edhrec_delta_jsonl(store: StudioStore, path: str | Path) -> dict[str, int]:
    """Import ``10_EDHREC_STATISTICS_DELTA_*.jsonl`` (a single file or a hub folder)."""
    target = Path(path)
    files = (
        sorted(target.glob("10_EDHREC_STATISTICS_DELTA_*.jsonl")) if target.is_dir() else [target]
    )
    if not files:
        raise ValueError(f"{target}: no 10_EDHREC_STATISTICS_DELTA_*.jsonl files found")
    total = sum(_import_one_edhrec_delta_file(store, file_path) for file_path in files)
    return {"files": len(files), "rows": total}


def _import_one_simulation_file(
    store: StudioStore,
    file_path: Path,
    *,
    engine_pin: str,
    pilot_policy: str,
) -> dict[str, object]:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("plan"), dict):
        raise ValueError(f"{file_path.name}: not a deckbau_eval simulation report")
    plan = payload["plan"]
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError(f"{file_path.name}: missing summary")
    source_id = store.register_source(
        data_class=DataClass.SIMULATED_RESULT,
        title=file_path.name,
        sha256=sha256_file(file_path),
    )
    pod = str(plan.get("pod") or "unknown")
    deck_id = str(plan.get("deck_id") or "custom/chulane")
    run_id = f"{deck_id}:{pod}:{file_path.stem}"
    games_planned = int(plan.get("games_planned") or 0)
    games_completed = int(summary.get("games_completed") or 0)
    games_failed = int(summary.get("games_failed") or 0)
    wins_fractional = float(summary.get("wins_fractional") or 0.0)
    win_rate = _real(summary.get("win_rate_completed_games"))
    mean_rounds = _real(summary.get("mean_rounds"))
    hrt = summary.get("hand_residence_turns")
    hrt_dict = hrt if isinstance(hrt, dict) else {}
    dwell_raw = str(hrt_dict.get("status") or "UNKNOWN")
    hand_dwell_status = "UNKNOWN" if dwell_raw in {"NOT_MEASURED", "UNKNOWN"} else dwell_raw
    rotted_by_card: dict[str, int] = {}
    for entry in hrt_dict.get("castable_but_uncast", []):
        if isinstance(entry, dict) and entry.get("card"):
            rotted_by_card[str(entry["card"])] = int(entry.get("games_rotted") or 0)
    opportunities = hrt_dict.get("per_card_cast_opportunities", [])
    card_rows: list[tuple[object, ...]] = []
    for entry in opportunities if isinstance(opportunities, list) else []:
        if not isinstance(entry, dict) or not entry.get("card"):
            continue
        c_name = str(entry["card"])
        c_id = store.card_id_by_oracle_or_name(None, c_name)
        card_rows.append(
            (
                run_id,
                c_id,
                c_name,
                games_completed,
                int(entry.get("games_offered") or 0),
                int(entry.get("games_cast_after_offer") or 0),
                rotted_by_card.get(c_name, 0),
                int(entry.get("offered_castable") or 0),
                int(entry.get("cast") or 0),
                _real(entry.get("mean_first_cast_round")),
            )
        )
    with store.connection as db:
        db.execute("DELETE FROM simulation_card WHERE run_id = ?", (run_id,))
        db.execute(
            "INSERT OR REPLACE INTO simulation_run(run_id, deck_id, pod, engine_pin, "
            "pilot_policy, seeds, games_planned, games_completed, games_failed, "
            "wins_fractional, win_rate, mean_rounds, hand_dwell_status, source_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                deck_id,
                pod,
                engine_pin,
                pilot_policy,
                json.dumps(plan.get("seeds") or []),
                games_planned,
                games_completed,
                games_failed,
                wins_fractional,
                win_rate,
                mean_rounds,
                hand_dwell_status,
                source_id,
            ),
        )
        db.executemany(
            "INSERT INTO simulation_card(run_id, card_id, card_name, games_completed, "
            "games_offered, games_cast_after_offer, games_rotted, offered_castable, "
            "cast_count, mean_first_cast_round) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            card_rows,
        )
    return {
        "run_id": run_id,
        "pod": pod,
        "games_completed": games_completed,
        "cards": len(card_rows),
    }


def import_simulation_report(
    store: StudioStore,
    path: str | Path,
    *,
    engine_pin: str = "f4d12f6e80",
    pilot_policy: str = "tuned",
) -> dict[str, object]:
    """Import one ``deckbau_eval.py`` JSON report or a folder of ``chulane_*_seeds*.json`` reports."""
    target = Path(path)
    if target.is_dir():
        files = sorted(
            p for p in target.glob("chulane_*_seeds*.json") if not p.name.endswith("_summary.json")
        )
        if not files:
            raise ValueError(f"{target}: no chulane_*_seeds*.json simulation reports found")
        runs = [
            _import_one_simulation_file(
                store, file_path, engine_pin=engine_pin, pilot_policy=pilot_policy
            )
            for file_path in files
        ]
        return {"runs": len(runs), "details": runs}
    return _import_one_simulation_file(
        store, target, engine_pin=engine_pin, pilot_policy=pilot_policy
    )
