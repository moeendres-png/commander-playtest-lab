#!/usr/bin/env python3
"""QA of the full rating run (922 cards, one rater). No model calls, no usage data unless --usage.

python3 full_qa.py            # validity, blindness, quotes, distributions, top/bottom 30
python3 full_qa.py --usage    # AFTER the ratings are frozen: descriptive comparison with usage_holdout.jsonl
"""
from __future__ import annotations

import collections
import glob
import json
import re
import statistics
import sys
from pathlib import Path

P = Path(__file__).resolve().parent
R = P.parent / "rubric_v2"
CRIT = "EFTRKDH"


def load() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for f in sorted(glob.glob(str(P / "out_full" / "F1_b*.json"))):
        for x in json.load(open(f, encoding="utf-8")):
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
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else float("nan")


def main() -> None:
    rows = load()
    facts = {r["name"]: r for r in (json.loads(l) for l in open(R / "data" / "facts.jsonl", encoding="utf-8"))}
    print(f"Bewertete Karten: {len(rows)} von {len(facts)}; fehlend: {len(set(facts) - set(rows))}")
    bad5 = sum(1 for x in rows.values() if any(x["scores"][k] % 5 for k in CRIT))
    print(f"Nicht Vielfaches von 5: {bad5} von {len(rows)}")
    conf = collections.Counter(x.get("confidence") for x in rows.values())
    print("confidence:", dict(conf))
    # blindness
    kw = re.compile(r"popular|staple|edhrec|commonly played|budget|cedh|played in (most|many)|nearly always played|tier list|meta\b", re.I)
    hits = []
    for c, x in rows.items():
        txt = " ".join([x.get("reason", ""), x.get("uncertainty", "")] + list(x.get("notes", {}).values()))
        m = kw.search(txt)
        if m:
            hits.append((c, txt[max(0, m.start() - 50) : m.end() + 50]))
    print(f"Blindheits-Scan (Stichwortliste): {len(hits)} von {len(rows)}")
    for h in hits[:15]:
        print("  ", h)
    # H distribution
    H = [x["scores"]["H"] for x in rows.values()]
    bins = collections.Counter(min(9, int(h // 10)) for h in H)
    print("H-Verteilung (Zehnerbänder):", {f"{b*10}-{b*10+9}": bins[b] for b in range(10)})
    print(f"H: Median {statistics.median(H)}, Mittel {statistics.fmean(H):.1f}, n={len(H)}")
    for k in CRIT:
        v = [x["scores"][k] for x in rows.values()]
        print(f"  {k}: Mittel {statistics.fmean(v):.1f}, Median {statistics.median(v)}, SD {statistics.pstdev(v):.1f}")
    land = [c for c in rows if "Land" in (facts.get(c, {}).get("type_line") or "")]
    print(f"Länder: {len(land)}; H-Mittel Länder {statistics.fmean(rows[c]['scores']['H'] for c in land):.1f}")
    ordered = sorted(rows, key=lambda c: (-rows[c]["scores"]["H"], c))
    print("\nTop 30 nach H:")
    for c in ordered[:30]:
        print(f"  {rows[c]['scores']['H']:>3} {c}: {rows[c]['reason'][:110]}")
    print("\nBottom 30 nach H:")
    for c in ordered[-30:]:
        print(f"  {rows[c]['scores']['H']:>3} {c}: {rows[c]['reason'][:110]}")
    if "--usage" in sys.argv:
        use = {r["name"]: r for r in (json.loads(l) for l in open(R / "data" / "usage_holdout.jsonl", encoding="utf-8"))}
        sample = next(iter(use.values()))
        print("\nusage_holdout Felder:", list(sample))
        key = next((k for k in ("source_decks", "decks", "deck_count", "n_decks") if k in sample), None)
        if key:
            cs = [c for c in rows if c in use]
            a = [rows[c]["scores"]["H"] for c in cs]
            b = [float(use[c][key]) for c in cs]
            print(f"Spearman H gegen {key} (n={len(cs)} von 922, alle Karten): {pearson(ranks(a), ranks(b)):.3f}")
            pos = [c for c in cs if float(use[c][key]) > 0]
            print(f"  nur Karten mit Nutzung > 0 (n={len(pos)}): {pearson(ranks([rows[c]['scores']['H'] for c in pos]), ranks([float(use[c][key]) for c in pos])):.3f}")
            zero = [c for c in cs if float(use[c][key]) == 0]
            print(f"  Karten ohne Nutzung (n={len(zero)}): H-Mittel {statistics.fmean(rows[c]['scores']['H'] for c in zero):.1f}")


if __name__ == "__main__":
    main()
