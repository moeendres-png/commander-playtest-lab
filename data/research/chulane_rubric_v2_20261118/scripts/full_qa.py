#!/usr/bin/env python3
"""QA of the full rating run (922 cards, one rater). No model calls; usage data only with --usage.

  python3 full_qa.py --ratings <out_full folder | fullrun_ratings.jsonl> --facts <facts.jsonl>
  python3 full_qa.py --ratings ... --facts ... --usage <usage_holdout.jsonl>

--ratings is either the folder of raw files (F1_b*.json, the lead's out_full folder, outside the
repository) or the merged JSONL. Without --usage it checks validity, blindness (keyword list),
the distributions and lists the top and bottom 30. --usage is for AFTER the ratings are frozen:
a descriptive comparison with the local usage_holdout.jsonl (never checked in, never in a
rater prompt); it carries no weight in any index.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import statistics
from pathlib import Path

CRIT = "EFTRKDH"
BLIND_WORDS = re.compile(
    r"popular|staple|edhrec|commonly played|budget|cedh|played in (most|many)"
    r"|nearly always played|tier list|meta\b",
    re.IGNORECASE,
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_ratings(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if path.is_dir():
        for f in sorted(path.glob("F1_b*.json")):
            for x in json.loads(f.read_text(encoding="utf-8")):
                rows[x["card"]] = x
    else:
        for x in read_jsonl(path):
            rows[x["card"]] = x
    return rows


def ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def pearson(a: list[float], b: list[float]) -> float:
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    sa = sum((x - ma) ** 2 for x in a) ** 0.5
    sb = sum((x - mb) ** 2 for x in b) ** 0.5
    if not sa or not sb:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True)) / (sa * sb)


def spearman(a: list[float], b: list[float]) -> float:
    return pearson(ranks(a), ranks(b))


def auc(score: list[float], positive: list[bool]) -> float:
    """Probability that a positive card scores above a negative one (ties count half)."""
    r = ranks(score)
    n_pos = sum(positive)
    n_neg = len(positive) - n_pos
    rank_sum = sum(rk for rk, p in zip(r, positive, strict=True) if p)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def usage_report(rows: dict[str, dict], usage_path: Path) -> None:
    use = {r["name"]: r for r in read_jsonl(usage_path)}
    cards = [c for c in rows if c in use]
    h = [float(rows[c]["scores"]["H"]) for c in cards]
    count = [float(use[c]["deck_list_count"]) for c in cards]
    print(f"\nUsage (descriptive, after freezing; no weight): n={len(cards)} of {len(rows)}")
    print(f"Spearman H against source-deck count (all cards): {spearman(h, count):.3f}")
    used = [i for i, v in enumerate(count) if v > 0]
    unused = [i for i, v in enumerate(count) if v == 0]
    print(
        f"  only cards with usage (n={len(used)}): {spearman([h[i] for i in used], [count[i] for i in used]):.3f}"
    )
    print(
        f"  mean H: without usage (n={len(unused)}) {statistics.fmean(h[i] for i in unused):.1f}, "
        f"with usage (n={len(used)}) {statistics.fmean(h[i] for i in used):.1f}"
    )
    v1 = [float(use[c]["v1"]["H_mean"]) for c in cards]
    print(f"Spearman v2-H against v1-H (n={len(cards)}): {spearman(h, v1):.3f}")
    ref = [bool(use[c]["in_reference_deck"]) for c in cards]
    a_v2, a_v1, a_use = auc(h, ref), auc(v1, ref), auc(count, ref)
    print(
        f"Reference deck AUC ({sum(ref)} against {len(ref) - sum(ref)}): v2-H {a_v2:.3f}, "
        f"v1-H {a_v1:.3f}, source-deck count {a_use:.3f}"
    )
    verdict = "met" if a_v2 >= a_v1 - 0.03 else "not met"
    print(f"Non-inferiority (v2 >= v1 - 0.03): difference {a_v2 - a_v1:+.3f}, {verdict}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratings", required=True, help="out_full folder or fullrun_ratings.jsonl")
    ap.add_argument("--facts", required=True, help="data/facts.jsonl")
    ap.add_argument(
        "--usage", help="usage_holdout.jsonl (local; only after the ratings are frozen)"
    )
    args = ap.parse_args()
    rows = load_ratings(Path(args.ratings))
    facts = {r["name"]: r for r in read_jsonl(Path(args.facts))}
    print(f"Bewertete Karten: {len(rows)} von {len(facts)}; fehlend: {len(set(facts) - set(rows))}")
    bad5 = sum(1 for x in rows.values() if any(x["scores"][k] % 5 for k in CRIT))
    print(f"Nicht Vielfaches von 5: {bad5} von {len(rows)}")
    print("confidence:", dict(collections.Counter(x.get("confidence") for x in rows.values())))
    hits = []
    for card, x in rows.items():
        texts = [x.get("reason", ""), x.get("uncertainty", ""), *x.get("notes", {}).values()]
        txt = " ".join(texts)
        m = BLIND_WORDS.search(txt)
        if m:
            hits.append((card, txt[max(0, m.start() - 50) : m.end() + 50]))
    print(f"Blindheits-Scan (Stichwortliste): {len(hits)} von {len(rows)}")
    for hit in hits:
        print("  ", hit)
    scores = [x["scores"]["H"] for x in rows.values()]
    bins = collections.Counter(min(9, int(h // 10)) for h in scores)
    print("H-Verteilung (Zehnerbänder):", {f"{b * 10}-{b * 10 + 9}": bins[b] for b in range(10)})
    print(
        f"H: Median {statistics.median(scores)}, Mittel {statistics.fmean(scores):.1f}, n={len(scores)}"
    )
    for k in CRIT:
        v = [x["scores"][k] for x in rows.values()]
        print(
            f"  {k}: Mittel {statistics.fmean(v):.1f}, Median {statistics.median(v)}, SD {statistics.pstdev(v):.1f}"
        )
    land = [c for c in rows if "Land" in (facts.get(c, {}).get("type_line") or "")]
    land_mean = statistics.fmean(rows[c]["scores"]["H"] for c in land)
    print(f"Länder: {len(land)}; H-Mittel Länder {land_mean:.1f}")
    ordered = sorted(rows, key=lambda c: (-rows[c]["scores"]["H"], c))
    for title, part in (("Top 30 nach H", ordered[:30]), ("Bottom 30 nach H", ordered[-30:])):
        print(f"\n{title}:")
        for c in part:
            print(f"  {rows[c]['scores']['H']:>3} {c}: {rows[c]['reason'][:110]}")
    if args.usage:
        usage_report(rows, Path(args.usage))


if __name__ == "__main__":
    main()
