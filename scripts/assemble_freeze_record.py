#!/usr/bin/env python3
"""Assemble and judge the XMage architecture-freeze record of one sealed epoch (#662).

Writes ``FREEZE_RECORD_XMAGE.json`` (the assembly document: record, computed
eligibility, reasons and proof ledger) into ``--out`` or prints it. Never selects a
provider and never claims a Freeze; an eligible record is an Owner decision input.

    scripts/assemble_freeze_record.py EPOCH_DIR [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary.freeze_record import (  # noqa: E402
    assemble_freeze_record,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("epoch", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    result = assemble_freeze_record(
        args.epoch.resolve(), repo_root=REPO_ROOT, expected_pin=config["primary_engine"]["commit"]
    )
    text = json.dumps(result.to_document(), indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "FREEZE_RECORD_XMAGE.json").write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    print(
        f"freeze_eligible={result.eligible} reasons={len(result.reasons)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
