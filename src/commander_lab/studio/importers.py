"""Importers of the Studio: original files in, rows with their source out.

Each importer reads one original file, records it as a source (bound to its SHA-256) and
writes rows that point back to that source. Nothing is invented: a missing value stays NULL
and means unknown, never zero.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path

from openpyxl import load_workbook

from .catalog import refresh_corpus_stats
from .decks import RevisionCard, create_revision
from .edhrec_capture_proof import verify_captures
from .store import DataClass, StudioStore, now_utc, rebuild_corpus_deck_role, sha256_file

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


_MERGED = dict[tuple[str, str, str], tuple[str | None, int, str]]
_EXAMPLES = 5


def _read_corpus_part(path: Path, known: set[str]) -> tuple[_MERGED, int]:
    """Rows of one part file, equal (deck, card, section) rows merged, unregistered decks left out."""
    merged: _MERGED = {}
    skipped = 0
    for row in _csv_rows(path):
        if row["deck_id"] not in known:
            skipped += 1
            continue
        key = (row["deck_id"], row["canonical_name"] or row["raw_card_name"], row["section"])
        previous = merged.get(key)
        quantity = int(row["quantity"]) + (previous[1] if previous else 0)
        merged[key] = (row["oracle_id"] or None, quantity, row["normalization_status"])
    return merged, skipped


def _example_ids(deck_ids: Iterable[str]) -> str:
    ordered = sorted(set(deck_ids))
    shown = ", ".join(ordered[:_EXAMPLES])
    return f"{shown} (and {len(ordered) - _EXAMPLES} more)" if len(ordered) > _EXAMPLES else shown


def import_corpus_card_parts(
    store: StudioStore, paths: Sequence[str | Path], *, allow_deck_move: bool = False
) -> dict[str, int]:
    """Read the normalized card rows of the source decks, one or several part files at once.

    Each file is one partition of a larger corpus: it replaces the rows of the decks it holds
    and leaves every other deck alone, so repeating a file is harmless. A deck must live in
    exactly one part (named by the file name). Before anything is written the import checks that

    * no deck is listed in two of the given files,
    * no deck is already held by a part with another file name (a deck split over two
      files, or a part renamed, would otherwise lose rows silently) unless
      ``allow_deck_move`` says the move is intended,
    * every row is readable.

    Decks that an older program version imported have no recorded part and are accepted.
    All files are written in one transaction: if one fails, none is imported.
    """
    files = [Path(path) for path in paths]
    if not files:
        raise ValueError("no card file given")
    if len({file.name for file in files}) != len(files):
        raise ValueError("two of the given files have the same name")
    known = {str(row[0]) for row in store.connection.execute("SELECT deck_id FROM corpus_deck")}
    parts = [(file, *_read_corpus_part(file, known)) for file in files]
    owner_of: dict[str, str] = {}
    shared: set[str] = set()
    for file, merged, _ in parts:
        for deck_id in {key[0] for key in merged}:
            if deck_id in owner_of:
                shared.add(deck_id)
            owner_of[deck_id] = file.name
    if shared:
        raise ValueError(
            f"{len(shared)} deck(s) appear in more than one of the given files: "
            f"{_example_ids(shared)}. A deck must be complete in one file; nothing was imported"
        )
    recorded = {
        str(row[0]): str(row[1])
        for row in store.connection.execute("SELECT deck_id, part_name FROM corpus_deck_part")
    }
    moved = {
        deck_id
        for deck_id, name in owner_of.items()
        if deck_id in recorded and recorded[deck_id] != name
    }
    if moved and not allow_deck_move:
        raise ValueError(
            f"{len(moved)} deck(s) are already held by a part with another file name: "
            f"{_example_ids(moved)}. Import the deck from its original file, or pass "
            "--allow-deck-move if the deck now lives in this file; nothing was imported"
        )
    with store.connection as db:
        for file, merged, _ in parts:
            source_id = store.register_source(
                data_class=DataClass.NORMALIZED_SOURCE,
                title=file.name,
                sha256=sha256_file(file),
            )
            deck_ids = sorted({key[0] for key in merged})
            # Replace only the decks present in this part; other parts stay untouched.
            db.executemany(
                "DELETE FROM corpus_deck_card WHERE deck_id = ?", [(d,) for d in deck_ids]
            )
            db.executemany(
                "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
                "normalization_status) VALUES (?, ?, ?, ?, ?, ?)",
                [(*key, *value) for key, value in merged.items()],
            )
            db.executemany(
                "INSERT OR REPLACE INTO corpus_deck_part(deck_id, part_name, source_id) "
                "VALUES (?, ?, ?)",
                [(deck_id, file.name, source_id) for deck_id in deck_ids],
            )
    # The deck builder must see complete structural comparisons after the final
    # CSV partition, even when Scryfall was imported before the source decks.
    if store.count("scryfall_card"):
        refresh_corpus_stats(store)
    return {
        "rows": sum(len(merged) for _, merged, _ in parts),
        "rows_without_registered_deck": sum(skipped for _, _, skipped in parts),
        "decks": len(owner_of),
        "decks_moved_from_another_part": len(moved),
    }


def import_corpus_cards(
    store: StudioStore, path: str | Path, *, allow_deck_move: bool = False
) -> dict[str, int]:
    """Read the normalized card rows of the source decks from one part file."""
    result = import_corpus_card_parts(store, [path], allow_deck_move=allow_deck_move)
    return {
        "rows": result["rows"],
        "rows_without_registered_deck": result["rows_without_registered_deck"],
    }


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
            rebuild_corpus_deck_role(db)
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


def import_card_marks(store: StudioStore, path: str | Path) -> dict[str, int]:
    """Import card marks (favorite, excluded, note) from CSV or JSON.

    Supports G2 (user-provided markings). Idempotent and validates against known cards.
    """
    marks_path = Path(path)
    if not marks_path.exists():
        raise FileNotFoundError(f"Marks file not found: {marks_path}")

    rows: list[dict[str, object]] = []
    if marks_path.suffix.lower() == ".json":
        data = json.loads(marks_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    rows.append(dict(item))
        elif isinstance(data, dict):
            for cid, details in data.items():
                if isinstance(details, dict):
                    rows.append({"card_id": cid, **details})
                else:
                    rows.append({"card_id": cid, "note": str(details)})
    else:
        for r in _csv_rows(marks_path):
            rows.append(dict(r))

    count = 0
    updated_at = now_utc()
    with store.connection as db:
        for row_dict in rows:
            card_id = str(row_dict.get("card_id") or "").strip()
            card_name = str(row_dict.get("card_name") or row_dict.get("name") or "").strip()
            if not card_id and card_name:
                resolved = store.card_id_by_oracle_or_name(None, card_name)
                if resolved:
                    card_id = resolved
            if not card_id:
                continue

            fav_raw: object = (
                row_dict.get("favorite") if "favorite" in row_dict else row_dict.get("fav", 0)
            )
            excl_raw: object = (
                row_dict.get("excluded") if "excluded" in row_dict else row_dict.get("excl", 0)
            )
            note_raw = str(row_dict.get("note") or row_dict.get("notes") or "")

            try:
                fav = 1 if int(str(fav_raw)) else 0
            except (ValueError, TypeError):
                fav = 1 if str(fav_raw).lower() in ("true", "1", "yes") else 0

            try:
                excl = 1 if int(str(excl_raw)) else 0
            except (ValueError, TypeError):
                excl = 1 if str(excl_raw).lower() in ("true", "1", "yes") else 0

            db.execute(
                "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(card_id) DO UPDATE SET "
                "favorite = excluded.favorite, "
                "excluded = excluded.excluded, "
                "note = excluded.note, "
                "updated_at = excluded.updated_at",
                (card_id, fav, excl, note_raw, updated_at),
            )
            count += 1
    return {"marks_imported": count}


def import_edhrec_capture_manifest(
    store: StudioStore,
    manifest_path: str | Path,
    *,
    raw_folder: str | Path | None = None,
    target_comparison_cards: set[str] | None = None,
) -> dict[str, int]:
    """Import immutable 20 HTTP200 EDHREC public captures with full request/response provenance.

    Refs #1186. Never backfills or overwrites historical C079 timestamps.
    Separates cohorts, computes derived inclusion, verifies SHA-256 integrity,
    and handles unlisted cards as UNKNOWN.
    """
    # Validate all immutable HTTP event metadata and raw bytes before any DB write.
    verified = verify_captures(manifest_path, raw_folder)
    batch_day = verified[0].response_complete_utc[:10]
    if any(event.response_complete_utc[:10] != batch_day for event in verified):
        raise ValueError("Mixed-day EDHREC captures must be imported as separate batches")
    unknown_cohort = f"edhrec_snapshot:{batch_day}:not_listed"

    unique_card_page_pairs: set[tuple[str, str]] = set()
    total_observations = 0
    all_seen_cards: set[str] = set()

    with store.connection as db:
        for capture in verified:
            event_id = capture.event_id
            url = capture.url
            observed_utc = capture.response_complete_utc
            sha256_hash = capture.sha256
            raw_bytes = capture.raw_bytes
            parsed = capture.parsed

            # One immutable event per HTTP request, NOT one event per SHA.
            # Identical bytes can be served at different, genuine capture times.
            source_id = "src:edhrec-event:" + hashlib.sha256(event_id.encode()).hexdigest()[:24]
            db.execute(
                "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, "
                "snapshot_date, url, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    source_id,
                    DataClass.ORIGINAL_SOURCE.value,
                    f"EDHREC:{event_id}",
                    sha256_hash,
                    observed_utc[:10],
                    url,
                    now_utc(),
                ),
            )
            source_state = db.execute(
                "SELECT sha256, url FROM source WHERE source_id = ?", (source_id,)
            ).fetchone()
            if (
                source_state is None
                or source_state["sha256"] != sha256_hash
                or source_state["url"] != url
            ):
                raise ValueError(f"Source event ID reused with different bytes/URL: {event_id}")

            container = parsed.get("container") if isinstance(parsed, dict) else None
            json_dict = container.get("json_dict") if isinstance(container, dict) else None
            cardlists_val = json_dict.get("cardlists") if isinstance(json_dict, dict) else None
            page_cardlists: list[dict[str, object]] = (
                [cl for cl in cardlists_val if isinstance(cl, dict)]
                if isinstance(cardlists_val, list)
                else []
            )
            db.execute(
                "INSERT INTO source_capture_event("
                "event_id, source_url, request_start_utc, response_complete_utc, "
                "raw_response_sha256, http_status, provenance_class, raw_size_bytes, "
                "cardlists_count, automatic_import, source_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(event_id) DO NOTHING",
                (
                    event_id,
                    url,
                    capture.request_start_utc,
                    capture.response_complete_utc,
                    sha256_hash,
                    200,
                    "NEW_HTTP_CAPTURE_ONLY",
                    len(raw_bytes),
                    capture.cardlists_count,
                    0,
                    source_id,
                ),
            )

            # Repeated imports may re-materialize only this event's card metrics.
            # Preserve a previous "not listed" comparison marker if no comparison
            # input was supplied on the repeated run.
            capture_state = db.execute(
                "SELECT source_url, request_start_utc, response_complete_utc, "
                "raw_response_sha256, http_status, raw_size_bytes, cardlists_count, "
                "provenance_class, automatic_import, source_id "
                "FROM source_capture_event WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            expected = (
                url,
                capture.request_start_utc,
                capture.response_complete_utc,
                sha256_hash,
                200,
                len(raw_bytes),
                capture.cardlists_count,
                "NEW_HTTP_CAPTURE_ONLY",
                0,
                source_id,
            )
            if capture_state is None or tuple(capture_state) != expected:
                raise ValueError(f"Immutable HTTP event changed between imports: {event_id}")
            db.execute(
                "DELETE FROM observation WHERE source_id = ? AND cohort <> ?",
                (source_id, unknown_cohort),
            )

            # Determine theme slug from URL
            theme_slug = url.rstrip("/").split("/")[-1].replace(".json", "")
            if theme_slug == "chulane-teller-of-tales":
                theme_slug = "commander_core"
            cohort = f"edhrec_snapshot:{batch_day}:{theme_slug}"
            snapshot_label = f"{event_id} ({observed_utc})"

            seen_in_page: set[str] = set()
            for cl in page_cardlists:
                cardviews = cl.get("cardviews")
                if not isinstance(cardviews, list):
                    continue
                for cv in cardviews:
                    if not isinstance(cv, dict):
                        continue
                    card_name = str(cv.get("name") or "").strip()
                    if not card_name:
                        continue
                    all_seen_cards.add(card_name)
                    if card_name in seen_in_page:
                        continue
                    seen_in_page.add(card_name)
                    unique_card_page_pairs.add((theme_slug, card_name))

                    card_id = store.card_id_by_oracle_or_name(None, card_name)

                    num = int(str(cv["num_decks"])) if cv.get("num_decks") is not None else None
                    den = (
                        int(str(cv["potential_decks"]))
                        if cv.get("potential_decks") is not None
                        else None
                    )
                    lift = float(str(cv["lift"])) if cv.get("lift") is not None else None
                    synergy = float(str(cv["synergy"])) if cv.get("synergy") is not None else None

                    inc = (
                        round((num / den) * 100.0, 2)
                        if num is not None and den is not None and den > 0
                        else None
                    )

                    # 1. Inclusion (derived descriptive)
                    db.execute(
                        "INSERT INTO observation(card_id, card_name, cohort, metric, value, "
                        "numerator, denominator, data_class, url, snapshot, source_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            card_id,
                            card_name,
                            cohort,
                            "inclusion_pct",
                            inc,
                            num,
                            den,
                            DataClass.DERIVED_DESCRIPTIVE.value
                            if inc is not None
                            else DataClass.UNKNOWN.value,
                            url,
                            snapshot_label,
                            source_id,
                        ),
                    )
                    total_observations += 1

                    # 2. Lift (original source)
                    db.execute(
                        "INSERT INTO observation(card_id, card_name, cohort, metric, value, "
                        "numerator, denominator, data_class, url, snapshot, source_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            card_id,
                            card_name,
                            cohort,
                            "lift",
                            lift,
                            None,
                            None,
                            DataClass.ORIGINAL_SOURCE.value
                            if lift is not None
                            else DataClass.UNKNOWN.value,
                            url,
                            snapshot_label,
                            source_id,
                        ),
                    )
                    total_observations += 1

                    # 3. Synergy (if present)
                    if synergy is not None:
                        db.execute(
                            "INSERT INTO observation(card_id, card_name, cohort, metric, value, "
                            "numerator, denominator, data_class, url, snapshot, source_id) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                card_id,
                                card_name,
                                cohort,
                                "synergy_pct",
                                round(synergy * 100.0, 2),
                                None,
                                None,
                                DataClass.ORIGINAL_SOURCE.value,
                                url,
                                snapshot_label,
                                source_id,
                            ),
                        )
                        total_observations += 1

        # Check target comparison cards for unlisted ones
        unlisted_count = 0
        if target_comparison_cards is not None:
            missing_cards = sorted(target_comparison_cards - all_seen_cards)
            first_src_id = (
                "src:edhrec-event:" + hashlib.sha256(verified[0].event_id.encode()).hexdigest()[:24]
            )
            db.execute(
                "DELETE FROM observation WHERE source_id = ? AND cohort = ?",
                (first_src_id, unknown_cohort),
            )
            for missing_name in missing_cards:
                cid = store.card_id_by_oracle_or_name(None, missing_name)
                db.execute(
                    "INSERT INTO observation(card_id, card_name, cohort, metric, value, "
                    "numerator, denominator, data_class, url, snapshot, source_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        cid,
                        missing_name,
                        unknown_cohort,
                        "status",
                        None,
                        None,
                        None,
                        DataClass.UNKNOWN.value,
                        None,
                        "NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN",
                        first_src_id,
                    ),
                )
                unlisted_count += 1
                total_observations += 1

    return {
        "events": len(verified),
        "unique_card_pages": len(unique_card_page_pairs),
        "observations_written": total_observations,
        "unlisted_comparison_cards": unlisted_count if target_comparison_cards is not None else 0,
    }


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except (ValueError, TypeError):
        return None


def import_playgroup_atlas(
    store: StudioStore,
    path: str | Path,
    *,
    source_title: str | None = None,
    snapshot_date: str | None = None,
) -> dict[str, int]:
    """Import Playgroup.gg Card Atlas records into the Studio store.

    Accepts:
    - HTML file of a single card page (e.g. fixtures or scraped pages)
    - JSON file containing a list of card records or a single card record
    - JSONL file (one card record per line)
    - TSV or CSV file conforming to STUDIO_PLAYGROUP_ATLAS_SCHEMA.md
    """
    from .playgroup_parser import (
        parse_playgroup_card_html,
        to_playgroup_slug,
    )

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    source_id = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title=source_title or f"playgroup_atlas:{file_path.name}",
        sha256=sha256_file(file_path),
        snapshot_date=snapshot_date,
        url="https://playgroup.gg/cards",
    )

    records: list[dict[str, object]] = []

    suffix = file_path.suffix.lower()
    if suffix in {".html", ".htm"}:
        html_content = file_path.read_text(encoding="utf-8")
        parsed = parse_playgroup_card_html(html_content, slug=file_path.stem)
        records.append(parsed.to_dict())
    elif suffix in {".tsv", ".csv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with file_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            for row in reader:
                records.append(dict(row))
    else:
        # JSON or JSONL
        content = file_path.read_text(encoding="utf-8").strip()
        if content.startswith("{") or content.startswith("["):
            try:
                loaded = json.loads(content)
                if isinstance(loaded, list):
                    records = [dict(item) for item in loaded if isinstance(item, dict)]
                elif isinstance(loaded, dict):
                    if "cards" in loaded and isinstance(loaded["cards"], list):
                        records = [dict(item) for item in loaded["cards"] if isinstance(item, dict)]
                    elif "records" in loaded and isinstance(loaded["records"], list):
                        records = [
                            dict(item) for item in loaded["records"] if isinstance(item, dict)
                        ]
                    else:
                        records = [loaded]
            except json.JSONDecodeError:
                # Try JSONL fallback
                for line in content.splitlines():
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        else:
            for line in content.splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))

    db = store.connection
    timestamp = now_utc()
    records_imported = 0
    top_commanders_imported = 0
    final_zones_imported = 0

    with db:
        for row in records:
            card_name = _text(row.get("card_name") or row.get("name")) or ""
            oracle_id = _text(row.get("oracle_id"))
            if not oracle_id and card_name:
                found = db.execute(
                    "SELECT oracle_id FROM card WHERE oracle_name = ? "
                    "UNION SELECT oracle_id FROM scryfall_card WHERE name = ?",
                    (card_name, card_name),
                ).fetchone()
                if found:
                    oracle_id = str(found[0])

            if not oracle_id:
                # If still no oracle_id, skip or cannot identify
                continue

            raw_card_id = _text(row.get("card_id"))
            card_id: str | None = None
            if (
                raw_card_id
                and db.execute("SELECT 1 FROM card WHERE card_id = ?", (raw_card_id,)).fetchone()
            ):
                card_id = raw_card_id
            if not card_id:
                card_id = store.card_id_by_oracle_or_name(oracle_id, card_name)
            slug = _text(row.get("slug")) or to_playgroup_slug(card_name)
            format_mode = _text(row.get("format_mode")) or "multiplayer"

            raw_warnings = row.get("quality_warnings")
            if isinstance(raw_warnings, list | tuple):
                warnings_json = json.dumps(list(raw_warnings), ensure_ascii=False)
            elif isinstance(raw_warnings, str):
                if raw_warnings.startswith("["):
                    warnings_json = raw_warnings
                else:
                    warnings_json = json.dumps([raw_warnings], ensure_ascii=False)
            else:
                warnings_json = str(row.get("quality_warnings_json") or "[]")

            insufficient_sample = _flag(row.get("insufficient_sample")) or 0

            db.execute(
                """
                INSERT INTO playgroup_card_atlas (
                    oracle_id, format_mode, card_id, card_name, slug, card_type, set_name,
                    live_inclusion_pct, deck_inclusion_pct, times_brought, decks_running, unique_players,
                    median_cast_turn, drawn_to_played_pct, first_cast_n,
                    turn_1_pct, turn_2_pct, turn_3_pct, turn_4_pct, turn_5_pct, turn_6_to_9_pct, turn_10_plus_pct,
                    p25_cast_turn, p75_cast_turn, max_cast_turn,
                    on_curve_pct, on_curve_count, on_curve_denominator, on_curve_turn,
                    cast_same_turn_as_drawn_pct, turns_in_hand,
                    funnel_brought_n, funnel_players_n, ever_drawn_n, reached_battlefield_n, still_on_board_at_end_n,
                    battlefield_survival_pct,
                    winrate_when_cast_pct, winrate_when_cast_n,
                    winrate_when_in_library_pct, winrate_when_in_library_n,
                    winrate_when_in_hand_pct, winrate_when_in_hand_n,
                    observed_winrate_gap_pp, ci_95_lower_pp, ci_95_upper_pp,
                    conservative_ranking_indicator, final_zones_instances_n,
                    fetch_status, quality_warnings_json, insufficient_sample,
                    retrieved_at_utc, source_id, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?, ?,
                    ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?
                )
                ON CONFLICT(oracle_id, format_mode) DO UPDATE SET
                    card_id = COALESCE(excluded.card_id, playgroup_card_atlas.card_id),
                    card_name = excluded.card_name,
                    slug = excluded.slug,
                    card_type = excluded.card_type,
                    set_name = excluded.set_name,
                    live_inclusion_pct = excluded.live_inclusion_pct,
                    deck_inclusion_pct = excluded.deck_inclusion_pct,
                    times_brought = excluded.times_brought,
                    decks_running = excluded.decks_running,
                    unique_players = excluded.unique_players,
                    median_cast_turn = excluded.median_cast_turn,
                    drawn_to_played_pct = excluded.drawn_to_played_pct,
                    first_cast_n = excluded.first_cast_n,
                    turn_1_pct = excluded.turn_1_pct,
                    turn_2_pct = excluded.turn_2_pct,
                    turn_3_pct = excluded.turn_3_pct,
                    turn_4_pct = excluded.turn_4_pct,
                    turn_5_pct = excluded.turn_5_pct,
                    turn_6_to_9_pct = excluded.turn_6_to_9_pct,
                    turn_10_plus_pct = excluded.turn_10_plus_pct,
                    p25_cast_turn = excluded.p25_cast_turn,
                    p75_cast_turn = excluded.p75_cast_turn,
                    max_cast_turn = excluded.max_cast_turn,
                    on_curve_pct = excluded.on_curve_pct,
                    on_curve_count = excluded.on_curve_count,
                    on_curve_denominator = excluded.on_curve_denominator,
                    on_curve_turn = excluded.on_curve_turn,
                    cast_same_turn_as_drawn_pct = excluded.cast_same_turn_as_drawn_pct,
                    turns_in_hand = excluded.turns_in_hand,
                    funnel_brought_n = excluded.funnel_brought_n,
                    funnel_players_n = excluded.funnel_players_n,
                    ever_drawn_n = excluded.ever_drawn_n,
                    reached_battlefield_n = excluded.reached_battlefield_n,
                    still_on_board_at_end_n = excluded.still_on_board_at_end_n,
                    battlefield_survival_pct = excluded.battlefield_survival_pct,
                    winrate_when_cast_pct = excluded.winrate_when_cast_pct,
                    winrate_when_cast_n = excluded.winrate_when_cast_n,
                    winrate_when_in_library_pct = excluded.winrate_when_in_library_pct,
                    winrate_when_in_library_n = excluded.winrate_when_in_library_n,
                    winrate_when_in_hand_pct = excluded.winrate_when_in_hand_pct,
                    winrate_when_in_hand_n = excluded.winrate_when_in_hand_n,
                    observed_winrate_gap_pp = excluded.observed_winrate_gap_pp,
                    ci_95_lower_pp = excluded.ci_95_lower_pp,
                    ci_95_upper_pp = excluded.ci_95_upper_pp,
                    conservative_ranking_indicator = excluded.conservative_ranking_indicator,
                    final_zones_instances_n = excluded.final_zones_instances_n,
                    fetch_status = excluded.fetch_status,
                    quality_warnings_json = excluded.quality_warnings_json,
                    insufficient_sample = excluded.insufficient_sample,
                    retrieved_at_utc = excluded.retrieved_at_utc,
                    source_id = excluded.source_id,
                    updated_at = excluded.updated_at
                """,
                (
                    oracle_id,
                    format_mode,
                    card_id,
                    card_name,
                    slug,
                    _text(row.get("card_type")),
                    _text(row.get("set_name")),
                    _float_or_none(row.get("live_inclusion_pct")),
                    _float_or_none(row.get("deck_inclusion_pct")),
                    _int_or_none(row.get("times_brought")),
                    _int_or_none(row.get("decks_running")),
                    _int_or_none(row.get("unique_players")),
                    _float_or_none(row.get("median_cast_turn")),
                    _float_or_none(row.get("drawn_to_played_pct")),
                    _int_or_none(row.get("first_cast_n")),
                    _float_or_none(row.get("turn_1_pct")),
                    _float_or_none(row.get("turn_2_pct")),
                    _float_or_none(row.get("turn_3_pct")),
                    _float_or_none(row.get("turn_4_pct")),
                    _float_or_none(row.get("turn_5_pct")),
                    _float_or_none(row.get("turn_6_to_9_pct")),
                    _float_or_none(row.get("turn_10_plus_pct")),
                    _float_or_none(row.get("p25_cast_turn")),
                    _float_or_none(row.get("p75_cast_turn")),
                    _float_or_none(row.get("max_cast_turn")),
                    _float_or_none(row.get("on_curve_pct")),
                    _int_or_none(row.get("on_curve_count")),
                    _int_or_none(row.get("on_curve_denominator")),
                    _text(row.get("on_curve_turn")),
                    _float_or_none(row.get("cast_same_turn_as_drawn_pct")),
                    _float_or_none(row.get("turns_in_hand")),
                    _int_or_none(row.get("funnel_brought_n")),
                    _int_or_none(row.get("funnel_players_n")),
                    _int_or_none(row.get("ever_drawn_n")),
                    _int_or_none(row.get("reached_battlefield_n")),
                    _int_or_none(row.get("still_on_board_at_end_n")),
                    _float_or_none(row.get("battlefield_survival_pct")),
                    _float_or_none(row.get("winrate_when_cast_pct")),
                    _int_or_none(row.get("winrate_when_cast_n")),
                    _float_or_none(row.get("winrate_when_in_library_pct")),
                    _int_or_none(row.get("winrate_when_in_library_n")),
                    _float_or_none(row.get("winrate_when_in_hand_pct")),
                    _int_or_none(row.get("winrate_when_in_hand_n")),
                    _float_or_none(row.get("observed_winrate_gap_pp")),
                    _float_or_none(row.get("ci_95_lower_pp")),
                    _float_or_none(row.get("ci_95_upper_pp")),
                    _text(row.get("conservative_ranking_indicator")),
                    _int_or_none(row.get("final_zones_instances_n")),
                    _text(row.get("fetch_status")) or "OK",
                    warnings_json,
                    insufficient_sample,
                    _text(row.get("retrieved_at_utc")),
                    source_id,
                    timestamp,
                    timestamp,
                ),
            )
            records_imported += 1

            # Top commanders
            top_commanders = row.get("top_commanders")
            if isinstance(top_commanders, str) and top_commanders.startswith("["):
                try:
                    top_commanders = json.loads(top_commanders)
                except Exception:
                    top_commanders = []
            if isinstance(top_commanders, list | tuple):
                db.execute(
                    "DELETE FROM playgroup_top_commander WHERE oracle_id = ? AND format_mode = ?",
                    (oracle_id, format_mode),
                )
                for tc in top_commanders:
                    if isinstance(tc, dict):
                        tc_rank = _int_or_none(tc.get("rank")) or 1
                        tc_name = _text(tc.get("commander_name")) or ""
                        tc_slug = _text(tc.get("commander_slug")) or to_playgroup_slug(tc_name)
                        tc_color = _text(tc.get("color_identity")) or ""
                        tc_count = _int_or_none(tc.get("decks_count")) or 0
                        db.execute(
                            """
                            INSERT INTO playgroup_top_commander (
                                oracle_id, format_mode, rank, commander_name, commander_slug,
                                color_identity, decks_count, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                oracle_id,
                                format_mode,
                                tc_rank,
                                tc_name,
                                tc_slug,
                                tc_color,
                                tc_count,
                                timestamp,
                            ),
                        )
                        top_commanders_imported += 1

            # Final zones
            final_zones = row.get("final_zones")
            if isinstance(final_zones, str) and final_zones.startswith("["):
                try:
                    final_zones = json.loads(final_zones)
                except Exception:
                    final_zones = []
            if isinstance(final_zones, list | tuple):
                db.execute(
                    "DELETE FROM playgroup_final_zone WHERE oracle_id = ? AND format_mode = ?",
                    (oracle_id, format_mode),
                )
                for fz in final_zones:
                    if isinstance(fz, dict):
                        fz_name = _text(fz.get("zone_name")) or ""
                        fz_pct = _float_or_none(fz.get("pct")) or 0.0
                        fz_inst = _int_or_none(fz.get("instances_n"))
                        if fz_name:
                            db.execute(
                                """
                                INSERT INTO playgroup_final_zone (
                                    oracle_id, format_mode, zone_name, pct, instances_n, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (oracle_id, format_mode, fz_name, fz_pct, fz_inst, timestamp),
                            )
                            final_zones_imported += 1

    return {
        "records_imported": records_imported,
        "top_commanders_imported": top_commanders_imported,
        "final_zones_imported": final_zones_imported,
    }
