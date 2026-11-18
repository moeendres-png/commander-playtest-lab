#!/usr/bin/env python3
"""Quote rule check: is every rule_claims quote literally in the card block shown to the rater?

  python3 quote_check.py --run v2|v2.1|full --batches <out folder of make_batches.py>

Two sources are measured: (a) the rendered card block only, (b) the card block plus Chulane's
Oracle text from GUIDE_v2.md (the guide allows it as a quote source since v2.1). Two
normalisations are measured on both sides: "ws" (lower case, whitespace collapsed) and "punct"
(lower case, punctuation removed, whitespace collapsed; more lenient). Ratings come from
pilot_ratings.jsonl (v2, v2.1) or fullrun_ratings.jsonl (full); retest rows are not counted.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pilot_ratings import ROOT, load_rows

FOLDERS = {"v2": "batches", "v2.1": "batches21", "full": "full"}


def norm_ws(text: str) -> str:
    return " ".join(text.lower().split())


def norm_punct(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def chulane_text() -> str:
    """The quoted commander block of GUIDE_v2.md (lines starting with '> ')."""
    lines = (ROOT / "GUIDE_v2.md").read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("The commander (exact Oracle"))
    block = []
    for ln in lines[start + 1 :]:
        if ln.startswith(">"):
            block.append(ln[1:].strip())
        elif block:
            break
    return " ".join(block)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, choices=tuple(FOLDERS))
    ap.add_argument("--batches", required=True, help="--out folder of make_batches.py")
    args = ap.parse_args()
    root = Path(args.batches)
    name = FOLDERS[args.run]
    manifest = json.loads((root / f"{name}_manifest.json").read_text(encoding="utf-8"))
    raw: dict[tuple[str, str], str] = {}
    for m in manifest:
        text = (root / FOLDERS[args.run] / f"{m['batch']}.md").read_text(encoding="utf-8")
        parts = re.split(r"## Card \d+ of \d+\n\n", text)[1:]
        for card, part in zip(m["cards"], parts, strict=True):
            raw[(m["batch"], card)] = part
    if args.run == "full":
        lines = (ROOT / "fullrun_ratings.jsonl").read_text(encoding="utf-8").splitlines()
        rows = [json.loads(x) for x in lines]
    else:
        rows = load_rows(version=args.run)
    rows = [r for r in rows if not r.get("retest")]
    guide_raw = chulane_text()
    total = sum(len(r.get("rule_claims", [])) for r in rows)
    print(f"run {args.run}: ratings {len(rows)}, quotes {total}")
    for label, norm in (("ws", norm_ws), ("punct", norm_punct)):
        guide = norm(guide_raw)
        in_block = in_either = 0
        for row in rows:
            block = norm(raw[(row["batch"], row["card"])])
            for rc in row.get("rule_claims", []):
                quote = norm(rc.get("quote", ""))
                in_block += bool(quote) and quote in block
                in_either += bool(quote) and (quote in block or quote in guide)
        print(
            f"  [{label}] card block {in_block}/{total}; block or Chulane text {in_either}/{total}"
        )


if __name__ == "__main__":
    main()
