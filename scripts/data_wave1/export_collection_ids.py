"""Export the collection's Oracle IDs from a Studio store COPY (read only).

Writes one Oracle ID per line, sorted, to ``--out``. The store is opened with ``mode=ro``; use
``--immutable`` only when no Studio process has the file open. Point this at a copy of the data
folder, never at the live store while the Studio is running. The result is the input of
``derive_s1_subsets.py`` and ``validate_s1.py`` (collection of 1.655 cards on 2026-11-18).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common


def export_ids(db_path: Path, out: Path, *, immutable: bool = False) -> int:
    if not db_path.is_file():
        raise common.WaveError(f"store file not found: {db_path}")
    connection = sqlite3.connect(common.sqlite_uri(db_path, immutable=immutable), uri=True)
    try:
        rows = connection.execute(
            "SELECT DISTINCT oracle_id FROM card WHERE oracle_id IS NOT NULL ORDER BY oracle_id"
        ).fetchall()
    finally:
        connection.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"{row[0]}\n" for row in rows), encoding="utf-8", newline="\n")
    return len(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", type=Path, required=True, help="studio.sqlite3 of a COPY")
    parser.add_argument("--out", type=Path, required=True, help="id file to write")
    parser.add_argument("--immutable", action="store_true", help="open with immutable=1")
    args = parser.parse_args(argv)
    try:
        count = export_ids(args.db, args.out, immutable=args.immutable)
    except (common.WaveError, sqlite3.Error) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    print(f"{count} oracle ids written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
