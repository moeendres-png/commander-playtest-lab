#!/usr/bin/env python3
"""Drift test of the full run: 49 random cards rated a second time (rater F2, same rubric v2.1).

  python3 drift_eval.py --first ../fullrun_ratings.jsonl --second ../fulldrift_ratings.jsonl

Prints, per criterion, the mean absolute difference, the bias (second minus first) and ICC(2,1) over
the cards rated twice, plus the share of cards whose H differs by 15 or more (pre-registered
thresholds 5a: mean |dH| at most 5, share at most 10 %).
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

CRITERIA = "EFTRKDH"


def load(path: Path) -> dict[str, dict]:
    rows = (
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    return {r["card"]: r for r in rows}


def icc21(pairs: list[tuple[float, float]]) -> float:
    n = len(pairs)
    grand = sum(a + b for a, b in pairs) / (2 * n)
    row_means = [(a + b) / 2 for a, b in pairs]
    col_means = [sum(p[j] for p in pairs) / n for j in (0, 1)]
    msr = 2 * sum((m - grand) ** 2 for m in row_means) / (n - 1)
    msc = n * sum((m - grand) ** 2 for m in col_means)
    sse = sum(
        (p[j] - row_means[i] - col_means[j] + grand) ** 2
        for i, p in enumerate(pairs)
        for j in (0, 1)
    )
    mse = sse / (n - 1)
    return (msr - mse) / (msr + mse + 2 * (msc - mse) / n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=Path, required=True)
    ap.add_argument("--second", type=Path, required=True)
    args = ap.parse_args()
    first, second = load(args.first), load(args.second)
    cards = sorted(set(first) & set(second))
    print(f"Karten mit beiden Läufen: {len(cards)}")
    for k in CRITERIA:
        diffs = [second[c]["scores"][k] - first[c]["scores"][k] for c in cards]
        pairs = [(first[c]["scores"][k], second[c]["scores"][k]) for c in cards]
        print(
            f"{k}: mittlere |Diff| {statistics.fmean(abs(d) for d in diffs):.1f}  "
            f"Verzerrung {statistics.fmean(diffs):+.1f}  ICC(2,1) {icc21(pairs):.2f}"
        )
    dh = [abs(second[c]["scores"]["H"] - first[c]["scores"]["H"]) for c in cards]
    big = sum(1 for d in dh if d >= 15)
    rnd = random.Random(1118)
    boots = sorted(statistics.fmean(rnd.choices(dh, k=len(dh))) for _ in range(1000))
    print(
        f"H: mittlere |dH| {statistics.fmean(dh):.2f} [95 %: {boots[25]:.2f}; {boots[974]:.2f}], "
        f"Anteil >= 15: {big}/{len(dh)} = {big / len(dh):.1%}, max {max(dh)}"
    )


if __name__ == "__main__":
    main()
