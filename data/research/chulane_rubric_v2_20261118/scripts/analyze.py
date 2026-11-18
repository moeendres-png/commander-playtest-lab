#!/usr/bin/env python3
"""Pilot evaluation for rubric v2 (pre-registered in calibration_plan.md). Pure python, no numpy.

Usage: python3 analyze.py [--raters H1,H2,S1,S2] [--summary-out PATH]
Reads pilot_ratings.jsonl (run v2; the first 63 ratings per rater, the retest rows are the drift
sample), pilot_sample.json (only strata/anchor flags and v1 reference, never shown to raters),
anchors.json and the v1 summary.csv of ../chulane_rubric_20261114/.
All numbers carry n. Intervals: bootstrap over cards, 2000 draws, seed 1118 (ICC 500 draws).
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path

from pilot_ratings import ROOT as R
from pilot_ratings import load_rows, split_by_rater

CRIT = "EFTRKDH"
V1CSV = R.parent / "chulane_rubric_20261114" / "summary.csv"


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
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if sa == 0 or sb == 0:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True)) / (sa * sb)


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def icc2(matrix: list[list[float]]) -> tuple[float, float]:
    """ICC(2,1) and ICC(2,k) (Shrout & Fleiss), matrix rows = cards, columns = raters."""
    n, k = len(matrix), len(matrix[0])
    gm = sum(map(sum, matrix)) / (n * k)
    rm = [sum(r) / k for r in matrix]
    cm = [sum(matrix[i][j] for i in range(n)) / n for j in range(k)]
    ssr = k * sum((m - gm) ** 2 for m in rm)
    ssc = n * sum((m - gm) ** 2 for m in cm)
    sst = sum((x - gm) ** 2 for r in matrix for x in r)
    sse = sst - ssr - ssc
    msr, msc = ssr / (n - 1), ssc / (k - 1) if k > 1 else 0.0
    mse = sse / ((n - 1) * (k - 1))
    d1 = msr + (k - 1) * mse + k * (msc - mse) / n
    d2 = msr + (msc - mse) / n
    return (msr - mse) / d1 if d1 else float("nan"), (msr - mse) / d2 if d2 else float("nan")


def boot(fn, n: int, draws: int = 2000, seed: int = 1118) -> tuple[float, float]:
    rnd = random.Random(seed)
    vals = []
    for _ in range(draws):
        idx = [rnd.randrange(n) for _ in range(n)]
        try:
            v = fn(idx)
        except ZeroDivisionError:
            continue
        if v == v:
            vals.append(v)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def h_formula(h110: float) -> float:
    return (h110 - 1) / 9 * 100


def main() -> None:
    raters = ["H1", "H2", "S1", "S2"]
    if "--raters" in sys.argv:
        raters = sys.argv[sys.argv.index("--raters") + 1].split(",")
    pilot = json.loads((R / "pilot_sample.json").read_text(encoding="utf-8"))
    cards = [c["name"] for c in pilot["cards"]]
    isanchor = {c["name"]: c["v1_is_anchor"] for c in pilot["cards"]}
    v1 = {r["card"]: r for r in csv.DictReader(V1CSV.open(encoding="utf-8"))}
    rows = load_rows(version="v2")
    data = {r: split_by_rater(rows, r) for r in raters}
    have = [r for r in raters if len(data[r][0]) == 63]
    print(
        f"Raters complete (63 Karten): {have}; Karten je Rater: { {r: len(data[r][0]) for r in raters} }"
    )
    sc = {
        r: {c: {k: data[r][0][c]["scores"][k] for k in CRIT} for c in cards if c in data[r][0]}
        for r in raters
    }
    out = {}

    def mat(rs, crit, cs):
        return [[sc[r][c][crit] for r in rs] for c in cs]

    # 1. ICC per criterion
    print("\n== 1. ICC(2,1) / ICC(2,k) je Kriterium (n=63 Karten) ==")
    groups = {"H-Stufe(H1,H2)": ["H1", "H2"], "S-Stufe(S1,S2)": ["S1", "S2"], "alle vier": raters}
    for gname, rs in groups.items():
        if not all(r in have for r in rs):
            print(f"{gname}: nicht vollständig, übersprungen")
            continue
        row = []
        for k in CRIT:
            m = mat(rs, k, cards)
            i1, ik = icc2(m)
            lo, hi = boot(lambda idx, m=m: icc2([m[i] for i in idx])[0], len(m), draws=500)
            row.append(f"{k} {i1:.2f} [{lo:.2f};{hi:.2f}] (k={len(rs)}: {ik:.2f})")
            out[f"icc1_{gname}_{k}"] = round(i1, 3)
        print(f"{gname}: " + " | ".join(row))
    # 2. model effect
    if all(r in have for r in ("H1", "H2", "S1", "S2")):
        print("\n== 2. H-Stufe-Mittel gegen S-Stufe-Mittel (n=63) ==")
        for k in CRIT:
            hm = [statistics.fmean([sc["H1"][c][k], sc["H2"][c][k]]) for c in cards]
            sm = [statistics.fmean([sc["S1"][c][k], sc["S2"][c][k]]) for c in cards]
            rho = spearman(hm, sm)
            mad = statistics.fmean(abs(a - b) for a, b in zip(hm, sm, strict=True))
            bias = statistics.fmean(a - b for a, b in zip(hm, sm, strict=True))
            lo, hi = boot(
                lambda idx, hm=hm, sm=sm: spearman([hm[i] for i in idx], [sm[i] for i in idx]),
                63,
                draws=500,
            )
            print(
                f"{k}: Spearman {rho:.2f} [{lo:.2f};{hi:.2f}]  MAD {mad:.1f}  Verzerrung (H-Stufe minus S-Stufe) {bias:+.1f}"
            )
    # 3. anchor consistency (v1 fixed anchors, leave-one-out)
    anc = [c for c in cards if isanchor[c]]
    print(f"\n== 3. Anker (n={len(anc)} v1-Anker, leave-one-anchor-out) ==")
    A = json.loads((R / "anchors.json").read_text(encoding="utf-8"))
    fixed: dict[str, dict[str, float]] = {}
    for part in ("spell", "land"):
        for crit, rows in A[part].items():
            for a in rows:
                if a["kind"] == "v1_fixed":
                    fixed.setdefault(a["card"], {})[crit] = a["value"]
    for r in raters:
        have_a = [c for c in anc if c in sc[r]]
        if not have_a:
            continue
        for k in "EFTRH":
            errs = [abs(sc[r][c][k] - fixed[c][k]) for c in have_a if c in fixed and k in fixed[c]]
            if errs:
                print(
                    f"{r} {k}: MAE {statistics.fmean(errs):.1f} max {max(errs):.0f} (n={len(errs)})"
                )
    # 4. vs v1 on 53 non-anchors
    print("\n== 4. v2-H und E/F/T/R gegen v1 (53 Nicht-Anker) ==")
    non = [c for c in cards if not isanchor[c] and c in v1]
    for gname, rs in groups.items():
        if not all(r in have for r in rs):
            continue
        for k, vk in (
            ("H", "H_mean"),
            ("E", "E_mean"),
            ("F", "F_mean"),
            ("T", "T_mean"),
            ("R", "R_mean"),
        ):
            x = [statistics.fmean(sc[r][c][k] for r in rs) for c in non]
            y = [h_formula(float(v1[c][vk])) if k == "H" else float(v1[c][vk]) * 25 for c in non]
            rho = spearman(x, y)
            mad = statistics.fmean(abs(a - b) for a, b in zip(x, y, strict=True))
            print(f"{gname} {k}: Spearman {rho:.2f}  MAD {mad:.1f}  (n={len(non)})")
    # 5. drift
    print("\n== 5. Drift (Test-Retest, 8 Karten je Rater) ==")
    for r in raters:
        rt = data[r][1]
        if not rt:
            continue
        d = {
            k: statistics.fmean(abs(rt[c]["scores"][k] - sc[r][c][k]) for c in rt if c in sc[r])
            for k in CRIT
        }
        big = sum(1 for c in rt if c in sc[r] and abs(rt[c]["scores"]["H"] - sc[r][c]["H"]) >= 15)
        print(
            f"{r}: mittlere |Differenz| "
            + " ".join(f"{k} {v:.1f}" for k, v in d.items())
            + f" | H-Differenz>=15: {big}/{len(rt)}"
        )
    # 6. spread
    if len(have) >= 2:
        sds = [statistics.pstdev([sc[r][c]["H"] for r in have]) for c in cards]
        print(
            f"\n== 6. Streuung H über {len(have)} Rater: Karten mit SD >= 20: {sum(1 for s in sds if s >= 20)}/63 =="
        )
    # 7. validity
    print("\n== 7. Formale Gültigkeit ==")
    for r in raters:
        n = len(data[r][0]) + len(data[r][1])
        bad = sum(
            1 for src in data[r] for x in src.values() if any(x["scores"][k] % 5 for k in CRIT)
        )
        conf = {}
        for x in data[r][0].values():
            conf[x.get("confidence")] = conf.get(x.get("confidence"), 0) + 1
        print(
            f"{r}: {n} Bewertungen, davon nicht Vielfaches von 5: {bad}; confidence {conf}; rule_claims Mittel {statistics.fmean(len(x.get('rule_claims', [])) for x in data[r][0].values()):.1f}"
        )
    if "--summary-out" in sys.argv:
        target = Path(sys.argv[sys.argv.index("--summary-out") + 1])
        target.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
