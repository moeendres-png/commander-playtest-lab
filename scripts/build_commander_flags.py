#!/usr/bin/env python3
"""Derive data/cards/commander_flags.json from a stored Scryfall Oracle bulk file (E11).

    python scripts/build_commander_flags.py --bulk /path/oracle-cards-20261031090154.jsonl.gz
    python scripts/build_commander_flags.py --bulk BULK --check     # exit 1 when the file differs

The bulk file is read from disk; this script makes no network call. Download the bulk file once
(a plain GET of Scryfall's public bulk-data, no deck or card list in the request) and keep it
outside the repository. Exit 0 on success or when ``--check`` finds the committed file current.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commander_lab.cards.commander_flags import DEFAULT_FLAGS_PATH, derive_flags  # noqa: E402


def render(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bulk", type=Path, required=True, help="oracle-cards-<stamp>.jsonl[.gz]")
    parser.add_argument("--out", type=Path, default=DEFAULT_FLAGS_PATH)
    parser.add_argument("--check", action="store_true", help="write nothing; fail when stale")
    args = parser.parse_args(argv)

    text = render(derive_flags(args.bulk))
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            print(
                f"{args.out} differs from the file derived from {args.bulk.name}", file=sys.stderr
            )
            return 1
        print(f"{args.out} matches {args.bulk.name}")
        return 0
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out} from {args.bulk.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
