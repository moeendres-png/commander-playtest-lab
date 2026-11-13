"""The data files the repository itself holds, and the loaders that read them.

``import-all --from-repo`` runs every importer from the files under ``data/research``
(``RepoFiles.discover`` finds them from a root folder, so a test can build a small
repository-shaped folder). The functions here are also what the helper scripts
``scripts/build_inventory_workbook.py``, ``scripts/import_chulane_corpus.py`` and
``scripts/map_corpus_oracle_ids.py`` call, so there is one implementation.

Nothing here reads a network. The public card facts (Scryfall oracle file) are not in the
repository: they stay a file the caller names.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import decklist_import
from .store import StudioStore

SHEET_ORDER = (
    "00_README_STATUS",
    "01_CARD_IDENTITY",
    "02_PHYSICAL_LOTS",
    "03_LOCATIONS",
    "04_INVENTORY_EVENTS",
    "05_INVENTORY_CURRENT",
    "06_SOURCES",
    "07_DATA_QUALITY",
    "08_NONPLAYABLE_OBJECTS",
    "09_PRINTING_DETAILS",
    "10_PHOTO_AUDIT_20261111",
    "11_QA_RECONCILIATION",
)
TYPED_SHEETS = frozenset({"01_CARD_IDENTITY", "05_INVENTORY_CURRENT"})

# (folder below the corpus root, deck list format): five EDHREC variants, five Archidekt brackets
CORPUS_FOLDERS: tuple[tuple[str, str], ...] = (
    ("edhrec/cedh", "edhrec"),
    ("edhrec/core", "edhrec"),
    ("edhrec/exhibition", "edhrec"),
    ("edhrec/optimized", "edhrec"),
    ("edhrec/upgraded", "edhrec"),
    ("archidekt/bracket1", "archidekt"),
    ("archidekt/bracket2", "archidekt"),
    ("archidekt/bracket3", "archidekt"),
    ("archidekt/bracket4", "archidekt"),
    ("archidekt/bracket5", "archidekt"),
)
COLLECTION_FOLDER = "collection_1655"
CORPUS_FOLDER = "chulane_corpus"
ROLES_FOLDER = "roles_1655"
EDHREC_FOLDER = "edhrec_observations_chulane"
PLAYGROUP_FOLDER = "playgroup"


def _typed(value: str) -> int | float | str | None:
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def build_inventory_workbook(csv_dir: Path, out: Path) -> list[str]:
    """Assemble the sheet CSVs of ``csv_dir`` into the workbook the inventory importer reads.

    In the two sheets the importer reads numeric-looking cells become numbers; every other
    sheet is written as text. Returns the sheets written; ValueError when there are none."""
    from openpyxl import Workbook

    workbook = Workbook()
    first = workbook.active
    if first is not None:
        workbook.remove(first)
    written: list[str] = []
    for sheet in SHEET_ORDER:
        csv_path = csv_dir / f"{sheet}.csv"
        if not csv_path.is_file():
            continue
        worksheet = workbook.create_sheet(sheet)
        with csv_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if sheet in TYPED_SHEETS:
                    worksheet.append([_typed(cell) for cell in row])
                else:
                    worksheet.append([cell if cell != "" else None for cell in row])
        written.append(sheet)
    if not written:
        raise ValueError(f"no sheet CSVs found in {csv_dir}")
    out.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(out)
    return written


def import_corpus(store: StudioStore, root: Path) -> dict[str, int]:
    """Import the ten folders of the deck list corpus below ``root``.

    The importer's own commander guard is off (``commander=None``): the corpus holds 22
    Archidekt lists whose stated commander is another card; they belong to this corpus and,
    inside ``importing_for``, stay without a commander binding. Totals over the folders that exist (ValueError when none does)."""
    totals = {"decks": 0, "duplicates_marked": 0, "card_rows": 0, "files_without_cards": 0}
    present = [(name, form) for name, form in CORPUS_FOLDERS if (root / name).is_dir()]
    if not present:
        raise ValueError(f"no corpus folder found below {root}")
    for relative, form in present:
        result = decklist_import.import_decklists(
            store, root / relative, format=form, commander=None
        )
        for key in totals:
            totals[key] += int(result.get(key, 0))
    return totals


def map_corpus_oracle_ids(db: sqlite3.Connection) -> dict[str, int | list[str]]:
    """Fill ``corpus_deck_card.oracle_id`` for names that have none, in three stages: exact
    name in ``card``, exact name in the Scryfall catalog, front face of a two-part catalog name
    (corpus name = front of ``Front // Back``; never the back half). Only unambiguous matches
    are written. Idempotent. Counts, and the unresolved names."""
    names = [
        str(row[0])
        for row in db.execute(
            "SELECT DISTINCT card_name FROM corpus_deck_card WHERE oracle_id IS NULL"
        )
    ]
    by_name: dict[str, str] = {}
    for oracle_id, name in db.execute("SELECT oracle_id, oracle_name FROM card"):
        by_name.setdefault(name, oracle_id)
    for oracle_id, name in db.execute("SELECT oracle_id, name FROM scryfall_card"):
        by_name.setdefault(name, oracle_id)
    front: dict[str, set[str]] = {}
    for oracle_id, name in db.execute("SELECT oracle_id, name FROM scryfall_card"):
        if " // " in name:
            front.setdefault(name.split(" // ")[0], set()).add(oracle_id)
    exact = by_front = 0
    unresolved: list[str] = []
    updates: list[tuple[str, str]] = []
    for name in names:
        oracle_id = by_name.get(name)
        if oracle_id:
            updates.append((oracle_id, name))
            exact += 1
            continue
        candidates = front.get(name) or set()
        if len(candidates) == 1:
            updates.append((next(iter(candidates)), name))
            by_front += 1
            continue
        unresolved.append(name)
    with db:
        db.executemany("UPDATE corpus_deck_card SET oracle_id = ? WHERE card_name = ?", updates)
    mapped = int(
        db.execute("SELECT COUNT(*) FROM corpus_deck_card WHERE oracle_id IS NOT NULL").fetchone()[
            0
        ]
    )
    total = int(db.execute("SELECT COUNT(*) FROM corpus_deck_card").fetchone()[0])
    return {
        "names_to_map": len(names),
        "mapped_exact": exact,
        "mapped_front_face": by_front,
        "unresolved_names": len(unresolved),
        "rows_with_oracle_id": mapped,
        "rows_total": total,
        "unresolved": unresolved,
    }

TAGGER_BULK = Path("deckbuilder_1655") / "card_tagger_bulk_1655.csv"


def _parts(folder: Path, pattern: str) -> list[Path]:
    return sorted(folder.glob(pattern)) if folder.is_dir() else []


@dataclass(frozen=True)
class RepoFiles:
    """The repository's data files, found below one ``data/research`` folder. A missing
    folder gives an empty entry, never an error: the step is then reported as not provided."""

    research: Path
    collection_dir: Path | None = None
    corpus_dir: Path | None = None
    roles: list[Path] = field(default_factory=list)
    edhrec_parts: list[Path] = field(default_factory=list)
    playgroup_parts: list[Path] = field(default_factory=list)
    tagger_bulk: Path | None = None

    @classmethod
    def discover(cls, research: Path) -> RepoFiles:
        collection = research / COLLECTION_FOLDER
        corpus = research / CORPUS_FOLDER
        has_sheets = collection.is_dir() and any(collection.glob("0[0-9]_*.csv"))
        tagger = research / TAGGER_BULK
        return cls(
            research=research,
            collection_dir=collection if has_sheets else None,
            corpus_dir=corpus if corpus.is_dir() else None,
            roles=_parts(research / ROLES_FOLDER, "roles_*.json"),
            edhrec_parts=_parts(research / EDHREC_FOLDER, "edhrec_table_*.csv"),
            playgroup_parts=_parts(research / PLAYGROUP_FOLDER, "playgroup_card_atlas_*.jsonl"),
            tagger_bulk=tagger if tagger.is_file() else None,
        )


__all__ = [
    "CORPUS_FOLDERS",
    "RepoFiles",
    "build_inventory_workbook",
    "import_corpus",
    "map_corpus_oracle_ids",
]
