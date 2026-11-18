#!/usr/bin/env python3
"""Formal check of the pilot ratings: card order per batch (with a manifest) and scores.

  python3 validate.py [--run v2|v2.1|all] [--manifest <out>/batches_manifest.json]
                      [--ratings fullrun_ratings.jsonl --partial]

Without --manifest only the scores are checked (multiples of 5 from 0 to 100 for E, F, T, R, K,
D, H). The manifest comes from make_batches.py; --partial ignores manifest batches that have no
rating yet (the partial full run).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pilot_ratings import RATINGS, load_rows

CRITERIA = "EFTRKDH"


def bad_score(row: dict) -> bool:
    scores = row.get("scores", {})
    return any(
        scores.get(k) is None or scores[k] % 5 or not 0 <= scores[k] <= 100 for k in CRITERIA
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="v2", choices=("v2", "v2.1", "all"))
    ap.add_argument("--manifest", help="batches_manifest.json written by make_batches.py")
    ap.add_argument("--ratings", default=str(RATINGS), help="default: pilot_ratings.jsonl")
    ap.add_argument("--partial", action="store_true")
    args = ap.parse_args()
    batches: dict[str, list[dict]] = {}
    for row in load_rows(Path(args.ratings), None if args.run == "all" else args.run):
        batches.setdefault(row["batch"], []).append(row)
    expected: dict[str, list[str]] = {}
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        expected = {m["batch"]: m["cards"] for m in manifest}
    ok: list[str] = []
    bad: list[tuple[str, str]] = []
    for batch in sorted(set(batches) | set(expected)):
        rows = batches.get(batch)
        if rows is None:
            if args.partial:
                continue
            bad.append((batch, "missing"))
            continue
        got = [r["card"] for r in rows]
        if batch in expected and got != expected[batch]:
            bad.append((batch, f"cards {len(got)}/{len(expected[batch])}"))
            continue
        flagged = [r["card"] for r in rows if bad_score(r)]
        if flagged:
            bad.append((batch, f"bad scores {flagged}"))
            continue
        ok.append(batch)
    print("ok", len(ok), "bad", bad)


if __name__ == "__main__":
    main()
