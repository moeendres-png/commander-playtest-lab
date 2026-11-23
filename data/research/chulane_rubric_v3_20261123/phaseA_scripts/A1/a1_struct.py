"""Frage 3: Struktur H gegen Teilkriterien je Lauf; Anker-Sichtbarkeit (Ergänzung zu Frage 2).

PYTHONPATH=<Klon>/src python3 a1_struct.py   -> $A1_OUT/struct.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a1_common as C
import a1_stats as S

WORK = C.WORK


def runs() -> dict[str, list[dict]]:
    r2 = C.load_r2()
    return {
        "F1": list(C.load_f1().values()),
        "R2_W1": [r for r in r2.values() if r["wave"] == 1],
        "R2_W2": [r for r in r2.values() if r["wave"] == 2],
        "R2_retest8": list(C.load_retest().values()),
        "F2": C.jl(C.RUB / "fulldrift_ratings.jsonl"),
        "G1": C.jl(C.RUB / "audit/independent_rater_ratings.jsonl"),
        "V22": C.jl(C.RUB / "audit/guide_v22_test_ratings.jsonl"),
        "Pilot_all": C.jl(C.RUB / "pilot_ratings.jsonl"),
    }


def analyse(rows: list[dict]) -> dict:
    X = np.array([[r["scores"][k] for k in C.CRIT] for r in rows], float)
    h = np.array([r["scores"]["H"] for r in rows], float)
    m = X.mean(1)
    gap = h - m
    beta, r2, _ = S.ols(X, h)
    beta_m, r2_m, _ = S.ols(m[:, None], h)
    # ohne D
    beta_nd, r2_nd, _ = S.ols(X[:, [0, 1, 2, 3, 4]], h)  # noqa: RUF059
    low = h <= 10
    return {
        "n": len(rows),
        "below_mean_gt25": int((gap < -25).sum()),
        "above_mean_gt25": int((gap > 25).sum()),
        "abs_gap_gt25": int((np.abs(gap) > 25).sum()),
        "abs_gap_gt15": int((np.abs(gap) > 15).sum()),
        "mean_gap_H_minus_mean": round(float(gap.mean()), 2),
        "sd_gap": round(float(gap.std(ddof=1)), 2),
        "ols_intercept": round(float(beta[0]), 2),
        "ols_weights": {k: round(float(b), 3) for k, b in zip(C.CRIT, beta[1:], strict=False)},
        "ols_R2": round(r2, 3),
        "ols_mean_only": {
            "a": round(float(beta_m[0]), 2),
            "b": round(float(beta_m[1]), 3),
            "R2": round(r2_m, 3),
        },
        "ols_without_D_R2": round(r2_nd, 3),
        "corr_with_H": {
            k: round(float(np.corrcoef(X[:, i], h)[0, 1]), 3) for i, k in enumerate(C.CRIT)
        },
        "mean_D_when_H_le10": round(float(X[low, 5].mean()), 1) if low.any() else None,
        "n_H_le10": int(low.sum()),
        "mean_D_when_H_ge50": round(float(X[h >= 50, 5].mean()), 1) if (h >= 50).any() else None,
        "mean_scores": {k: round(float(X[:, i].mean()), 1) for i, k in enumerate(C.CRIT)}
        | {"H": round(float(h.mean()), 1)},
    }


def main() -> None:
    res = {"runs": {}}
    R = runs()
    for k, rows in R.items():
        res["runs"][k] = analyse(rows)
    # gleiche Karten: F1 eingeschränkt auf die Karten von R2_W2 bzw. W1 (Vergleich auf gleicher Menge)
    f1 = C.load_f1()
    for w in ("R2_W1", "R2_W2"):
        ids = [r["oracle_id"] for r in R[w]]
        res["runs"][f"F1_on_{w}_cards"] = analyse([f1[i] for i in ids])
    # Anker-Sichtbarkeit: exakte Treffer der eigenen Ankerzeilen, getrennt nach "F1 sah die eigene Zeile"
    anch = C.anchors()
    r2 = C.load_r2()
    byname_f1 = {r["card"]: r for r in f1.values()}
    byname_r2 = {r["card"]: r for r in r2.values()}
    out = {}
    for vis_lab, cond in (
        ("v1_fixed (F1 ohne eigene Zeile)", lambda r: r["kind"] == "v1_fixed"),
        ("übrige Anker (F1 sah eigene Zeile)", lambda r: r["kind"] != "v1_fixed"),
    ):
        n = hf = hr = 0
        af = ar = 0.0
        for t in ("spell", "land"):
            for crit, rows in anch[t].items():
                for r in rows:
                    if not cond(r):
                        continue
                    # Karten, die in irgendeiner Zeile v1_fixed sind, zählen zu v1_fixed
                    a, b = byname_f1[r["card"]], byname_r2[r["card"]]
                    n += 1
                    hf += a["scores"][crit] == r["value"]
                    hr += b["scores"][crit] == r["value"]
                    af += abs(a["scores"][crit] - r["value"])
                    ar += abs(b["scores"][crit] - r["value"])
        out[vis_lab] = {
            "anchor_rows": n,
            "F1_exact": hf,
            "R2_exact": hr,
            "F1_mae": round(af / n, 2),
            "R2_mae": round(ar / n, 2),
        }
    res["anchor_visibility"] = out
    WORK.mkdir(exist_ok=True)
    (WORK / "struct.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
