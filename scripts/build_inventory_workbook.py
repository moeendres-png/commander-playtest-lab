#!/usr/bin/env python3
"""Rebuild the Owner's inventory workbook (XLSX) from its CSV export.

The canonical collection dataset lives in ``data/research/collection_1655/``
as one CSV per workbook sheet (the XLSX itself is binary and cannot be kept
in this repository's file history through the usual tooling). This script
assembles the CSVs back into the workbook form that the Studio importer
reads:

    python scripts/build_inventory_workbook.py --out /tmp/collection.xlsx
    python -m commander_lab.studio import-inventory /tmp/collection.xlsx

Sheet order follows the original workbook. In the two sheets the importer
reads (``01_CARD_IDENTITY``, ``05_INVENTORY_CURRENT``) numeric-looking cells
are written back as numbers; all other sheets are written as text so no
identifier can be mangled by type inference.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv-dir",
        default="data/research/collection_1655",
        help="folder with one CSV per sheet (default: the repo dataset folder)",
    )
    parser.add_argument("--out", required=True, help="workbook path to write")
    args = parser.parse_args()

    src_dir = Path(__file__).resolve().parents[1] / "src"
    if src_dir.is_dir():
        sys.path.insert(0, str(src_dir))
    from commander_lab.studio import repo_import

    try:
        written = repo_import.build_inventory_workbook(Path(args.csv_dir), Path(args.out))
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print(f"wrote {args.out} with sheets: {', '.join(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
