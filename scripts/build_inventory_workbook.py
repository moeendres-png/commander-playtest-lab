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
import csv
from pathlib import Path

SHEET_ORDER = [
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
]
TYPED_SHEETS = {"01_CARD_IDENTITY", "05_INVENTORY_CURRENT"}


def _typed(value: str):
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv-dir",
        default="data/research/collection_1655",
        help="folder with one CSV per sheet (default: the repo dataset folder)",
    )
    parser.add_argument("--out", required=True, help="workbook path to write")
    args = parser.parse_args()

    from openpyxl import Workbook

    csv_dir = Path(args.csv_dir)
    workbook = Workbook()
    workbook.remove(workbook.active)
    written = []
    for sheet in SHEET_ORDER:
        csv_path = csv_dir / f"{sheet}.csv"
        if not csv_path.is_file():
            continue
        ws = workbook.create_sheet(sheet)
        with csv_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if sheet in TYPED_SHEETS:
                    ws.append([_typed(cell) for cell in row])
                else:
                    ws.append([cell if cell != "" else None for cell in row])
        written.append(sheet)
    if not written:
        raise SystemExit(f"no sheet CSVs found in {csv_dir}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(out)
    print(f"wrote {out} with sheets: {', '.join(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
