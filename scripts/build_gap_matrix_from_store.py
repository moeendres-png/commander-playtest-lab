#!/usr/bin/env python3
"""Write the coverage-gap matrix of a commander's pool from a Studio store (#1545).

Usage: build_gap_matrix_from_store.py <store-folder> [--commander NAME] [--out FILE]

The folder holds ``studio.sqlite3``; use a copy. Counts only, no network, no card names.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from commander_lab.studio.gap_matrix import build_gap_matrix
from commander_lab.studio.store import StudioStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", help="folder that contains studio.sqlite3 (a copy)")
    parser.add_argument("--commander", default="Chulane, Teller of Tales")
    parser.add_argument("--out", help="write the JSON here instead of stdout")
    args = parser.parse_args(argv)
    store = StudioStore.open(args.store)
    try:
        text = json.dumps(build_gap_matrix(store, args.commander), indent=2, ensure_ascii=False)
    finally:
        store.close()
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
