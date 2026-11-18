#!/usr/bin/env python3
"""Formal check of the raw full-run files: card order, JSON and scores (multiples of 5).

  python3 validate_full.py --out <dir> [--write-ratings fullrun_partial_ratings.jsonl]

<dir> is the --out of make_batches.py (run full): it holds full_manifest.json and the raw rating
files out_full/<batch>.json. That folder is filled by the lead and is not part of the repository.
Batches without a raw file yet are not counted as problems. --write-ratings merges the valid
batches into one JSONL file (one rating per line with rater F1, batch and version v2.1), the
format of ../fullrun_partial_ratings.jsonl.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CRITERIA = "EFTRKDH"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--write-ratings", help="merge the valid batches into this JSONL file")
    args = ap.parse_args()
    out = Path(args.out)
    manifest = json.loads((out / "full_manifest.json").read_text(encoding="utf-8"))
    ok = 0
    merged: list[dict] = []
    bad: list[tuple[str, str]] = []
    for m in manifest:
        batch = m["batch"]
        path = out / "out_full" / f"{batch}.json"
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            bad.append((batch, "json"))
            continue
        if [x.get("card") for x in rows] != m["cards"]:
            bad.append((batch, "cards"))
        elif any(x["scores"].get(k) is None or x["scores"][k] % 5 for x in rows for k in CRITERIA):
            bad.append((batch, "scores"))
        else:
            ok += 1
            merged += [{"rater": m["rater"], "batch": batch, "version": "v2.1", **x} for x in rows]
    if args.write_ratings:
        lines = [json.dumps(r, ensure_ascii=False) + "\n" for r in merged]
        Path(args.write_ratings).write_text("".join(lines), encoding="utf-8")
    print("fertig+gültig", ok, "von", len(manifest), "; Probleme", bad)


if __name__ == "__main__":
    main()
