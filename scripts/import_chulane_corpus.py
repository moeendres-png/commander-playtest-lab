#!/usr/bin/env python3
"""Import the Chulane decklist corpus from ``data/research/chulane_corpus/``.

The corpus is ten folders (five EDHREC variants, five Archidekt
brackets). The Studio CLI's ``import-decklists`` reads one folder at a
time and always applies its commander guard with the legacy default
commander — which refuses 22 Archidekt lists whose stated commander is
a different card (they carry Chulane in the mainboard; the harvest
collected them as Chulane lists, and the store's corpus contains them
without a commander binding). This script drives the same importer
API (``decklist_import.import_decklists``) folder by folder with the
guard deliberately off (``commander=None``), which is the route that
reproduces the live store's corpus exactly.

    python scripts/import_chulane_corpus.py [--data DIR] [--root FOLDER]

Acceptance after a run on an empty store: ``corpus_deck`` = 3,004
(2,845 canonical), ``corpus_deck_card`` = 266,539, ``corpus_cohort``
= 11,297. Afterwards fill ``corpus_deck_card.oracle_id`` with
``scripts/map_corpus_oracle_ids.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

FOLDERS: list[tuple[str, str]] = [
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
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", default=None, help="Studio data folder (default: the store's own resolution)"
    )
    parser.add_argument(
        "--root",
        default="data/research/chulane_corpus",
        help="corpus root folder (default: the repo dataset folder)",
    )
    args = parser.parse_args()

    src_dir = Path(__file__).resolve().parents[1] / "src"
    if src_dir.is_dir():
        sys.path.insert(0, str(src_dir))
    from commander_lab.studio import decklist_import
    from commander_lab.studio.store import StudioStore

    root = Path(args.root)
    store = StudioStore.open(args.data)
    totals = {"decks": 0, "duplicates_marked": 0, "card_rows": 0, "files_without_cards": 0}
    for relative, fmt in FOLDERS:
        folder = root / relative
        result = decklist_import.import_decklists(store, folder, format=fmt, commander=None)
        print(f"{relative} [{fmt}]: {result}")
        for key in totals:
            totals[key] += int(result.get(key, 0))
    print("TOTAL:", totals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
