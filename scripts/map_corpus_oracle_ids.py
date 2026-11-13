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

    src_dir = Path(__file__).resolve().parents[1] / "src"
    if src_dir.is_dir():
        sys.path.insert(0, str(src_dir))
    from commander_lab.studio import repo_import

    db = sqlite3.connect(db_path)
    result = repo_import.map_corpus_oracle_ids(db)
    print("Unmapped distinct names:", result["names_to_map"])
    print(
        "Mapped: exact",
        result["mapped_exact"],
        "| front-face fallback",
        result["mapped_front_face"],
        "| unresolved:",
        result["unresolved_names"],
    )
    rows, total = int(result["rows_with_oracle_id"]), int(result["rows_total"])  # type: ignore[call-overload]
    print(f"Rows with oracle_id: {rows} of {total} ({rows / total * 100:.2f} %)")
    print("Unresolved names (first 20):", list(result["unresolved"])[:20])  # type: ignore[call-overload]
    return 0


if __name__ == "__main__":
    sys.exit(main())
