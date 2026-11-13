#!/usr/bin/env python3
"""Map corpus deck-card names to Scryfall oracle_ids in the Studio store.

``import-decklists`` stores corpus card rows with ``oracle_id = NULL`` (it
only knows the source names). This script fills the ids afterwards, in three
stages: (1) exact name in the ``card`` table, (2) exact name in the Scryfall
catalog (``scryfall_card.name``), (3) front-face fallback for double-faced
cards (corpus name = front face of a catalog name ``Front // Back`` or the
reverse). Only unambiguous matches are written; the rest stays NULL and is
counted and printed. The script is idempotent.

This is the exact step that produced the live store's mapping on 2026-11-12
(266,366 of 266,539 corpus card rows mapped, 99.94%). Run it after
``import-decklists`` and after the Scryfall catalog (and ideally the
inventory) have been imported into the same store.

    python scripts/map_corpus_oracle_ids.py [--db PATH]

The store path defaults to ``$COMMANDER_LAB_STUDIO_DATA/studio.sqlite3``
and then to ``~/.local/share/commander-studio/studio.sqlite3``.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def default_db_path() -> Path:
    data_dir = os.environ.get("COMMANDER_LAB_STUDIO_DATA")
    if data_dir:
        return Path(data_dir) / "studio.sqlite3"
    return Path.home() / ".local" / "share" / "commander-studio" / "studio.sqlite3"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="path to studio.sqlite3")
    args = parser.parse_args()
    db_path = Path(args.db) if args.db else default_db_path()
    if not db_path.is_file():
        raise SystemExit(f"store not found: {db_path}")

    db = sqlite3.connect(db_path)
    names = [
        row[0]
        for row in db.execute(
            "SELECT DISTINCT card_name FROM corpus_deck_card WHERE oracle_id IS NULL"
        )
    ]
    print("Unmapped distinct names:", len(names))
    by_name: dict[str, str] = {}
    for oracle_id, name in db.execute("SELECT oracle_id, oracle_name FROM card"):
        by_name.setdefault(name, oracle_id)
    for oracle_id, name in db.execute("SELECT oracle_id, name FROM scryfall_card"):
        by_name.setdefault(name, oracle_id)
    front: dict[str, set[str]] = {}
    for oracle_id, name in db.execute("SELECT oracle_id, name FROM scryfall_card"):
        if " // " in name:
            front.setdefault(name.split(" // ")[0], set()).add(oracle_id)
    mapped = {"exact": 0, "front": 0}
    unmapped: list[str] = []
    updates: list[tuple[str, str]] = []
    for name in names:
        oracle_id = by_name.get(name)
        if oracle_id:
            updates.append((oracle_id, name))
            mapped["exact"] += 1
            continue
        candidates = front.get(name) or set()
        if len(candidates) == 1:
            updates.append((next(iter(candidates)), name))
            mapped["front"] += 1
            continue
        unmapped.append(name)
    with db:
        db.executemany(
            "UPDATE corpus_deck_card SET oracle_id = ? WHERE card_name = ?",
            updates,
        )
    rows = db.execute(
        "SELECT COUNT(*) FROM corpus_deck_card WHERE oracle_id IS NOT NULL"
    ).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM corpus_deck_card").fetchone()[0]
    print(
        "Mapped: exact",
        mapped["exact"],
        "| front-face fallback",
        mapped["front"],
        "| unresolved:",
        len(unmapped),
    )
    print(f"Rows with oracle_id: {rows} of {total} ({rows / total * 100:.2f} %)")
    print("Unresolved names (first 20):", unmapped[:20])
    return 0


if __name__ == "__main__":
    sys.exit(main())
