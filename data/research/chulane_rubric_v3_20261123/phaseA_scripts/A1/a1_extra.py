"""Ergänzungen: (1) Zerlegung der H-Verschiebung in Kriterien-Anteil und H-Schritt, (2) partielle Spearman
gegen Chulane-Deckanteil kontrolliert für globale Beliebtheit, (3) Reihenfolge-Check je Charge, (4) Farbe,
(5) Anteil H<=10 mit D>=75 je Lauf, (6) pattern_check-Feld `why` gegen das Schema.

  PYTHONPATH=<Klon>/src python3 a1_extra.py --usage <usage_holdout.jsonl>   (nach a1_decomp.py) -> $A1_OUT/extra.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a1_common as C
import a1_stats as S
import a1_struct as ST

WORK = C.WORK


def partial_spearman(x, y, z) -> float:
    rx, ry, rz = S.rank(x), S.rank(y), S.rank(z)
    Z = np.column_stack([np.ones(len(rz)), rz])
    ex = rx - Z @ np.linalg.lstsq(Z, rx, rcond=None)[0]
    ey = ry - Z @ np.linalg.lstsq(Z, ry, rcond=None)[0]
    return float(np.corrcoef(ex, ey)[0, 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--usage", required=True)
    a = ap.parse_args()
    P = [json.loads(x) for x in (WORK / "pairs.jsonl").read_text().splitlines()]
    P.sort(key=lambda p: p["oracle_id"])
    res: dict = {}
    # (1) Zerlegung
    dX = np.array([[p[f"d_{k}"] for k in C.CRIT] for p in P], float)
    dH = np.array([p["d_H"] for p in P], float)
    fits = {}
    for lab, rows in (("F1", list(C.load_f1().values())), ("R2", list(C.load_r2().values()))):
        X = np.array([[r["scores"][k] for k in C.CRIT] for r in rows], float)
        h = np.array([r["scores"]["H"] for r in rows], float)
        fits[lab] = S.ols(X, h)[0]
    # gemeinsame Gewichte (beide Läufe gestapelt)
    Xa = np.array(
        [[p[f"F1_{k}"] for k in C.CRIT] for p in P] + [[p[f"R2_{k}"] for k in C.CRIT] for p in P],
        float,
    )
    ha = np.array([p["F1_H"] for p in P] + [p["R2_H"] for p in P], float)
    fits["stacked"] = S.ols(Xa, ha)[0]
    # mit Lauf-Dummy: Intercept-Verschiebung = H-Schritt bei gleichen Kriterien
    Xd = np.column_stack([Xa, np.r_[np.zeros(len(P)), np.ones(len(P))]])
    bd, r2d, _ = S.ols(Xd, ha)
    res["decomp"] = {}
    for lab, b in fits.items():
        pred = dX @ b[1:]
        resid = dH - pred
        res["decomp"][lab] = {
            "weights": {k: round(float(w), 3) for k, w in zip(C.CRIT, b[1:], strict=False)},
            "mean_dH_obs": round(float(dH.mean()), 2),
            "mean_dH_pred_from_criteria": round(float(pred.mean()), 2),
            "mean_residual_H_step": round(float(resid.mean()), 2),
            "sd_dH": round(float(dH.std(ddof=1)), 2),
            "sd_pred": round(float(pred.std(ddof=1)), 2),
            "sd_resid": round(float(resid.std(ddof=1)), 2),
            "corr_dH_pred": round(float(np.corrcoef(dH, pred)[0, 1]), 3),
            "n_abs_pred_ge15": int((np.abs(pred) >= 15).sum()),
            "n_abs_obs_ge15": int((np.abs(dH) >= 15).sum()),
            "n_abs_pred_minus_mean_ge15": int((np.abs(pred - pred.mean() + dH.mean()) >= 15).sum()),
            "var_share_pred": round(float(pred.var(ddof=1) / dH.var(ddof=1)), 3),
        }
    res["run_dummy_model"] = {
        "R2_minus_F1_at_equal_criteria": round(float(bd[-1]), 2),
        "R2": round(r2d, 3),
    }
    # Kreaturen vs Nichtkreaturen: H-Schritt
    for lab, sel in (
        ("creatures", lambda p: p["is_creature"]),
        ("noncreature_spells", lambda p: not p["is_creature"] and not p["is_land"]),
        ("lands", lambda p: p["is_land"]),
    ):
        idx = np.array([sel(p) for p in P])
        pred = dX[idx] @ fits["stacked"][1:]
        res["decomp"][f"stacked_{lab}"] = {
            "n": int(idx.sum()),
            "mean_dH": round(float(dH[idx].mean()), 2),
            "pred": round(float(pred.mean()), 2),
            "resid": round(float((dH[idx] - pred).mean()), 2),
        }
    # (2) partielle Spearman
    us = {r["oracle_id"]: r for r in C.jl(Path(a.usage))}
    ids = [p["oracle_id"] for p in P]
    deck = np.array([us[i]["deck_list_count"] for i in ids], float)
    glob = np.array(
        [(lambda g: g[0] / g[1] if g else 0.0)(us[i]["edhrec_global_inclusion"]) for i in ids],
        float,
    )
    rank_ = np.array([-(us[i]["scryfall_edhrec_rank"] or 10**6) for i in ids], float)
    v1 = np.array([us[i]["v1"]["H_mean"] for i in ids], float)
    pooled = C.load_pooled()
    series = {
        "F1": np.array([p["F1_H"] for p in P], float),
        "R2": np.array([p["R2_H"] for p in P], float),
        "pooled": np.array([pooled[i]["H_pooled"] for i in ids], float),
        "v1": v1,
    }
    res["partial_spearman_deck_count"] = {}
    rng = np.random.default_rng(20261122)
    n = len(ids)
    for ctrl_lab, ctrl in (("ctrl_edhrec_global_incl", glob), ("ctrl_scryfall_rank", rank_)):
        pts = {k: partial_spearman(v, deck, ctrl) for k, v in series.items()}
        bs = {k: [] for k in series}
        for _ in range(1000):
            i = rng.integers(0, n, n)
            for k, v in series.items():
                bs[k].append(partial_spearman(v[i], deck[i], ctrl[i]))
        d = np.array(bs["R2"]) - np.array(bs["F1"])
        res["partial_spearman_deck_count"][ctrl_lab] = {
            k: [
                round(pts[k], 3),
                round(float(np.percentile(bs[k], 2.5)), 3),
                round(float(np.percentile(bs[k], 97.5)), 3),
            ]
            for k in series
        } | {
            "R2-F1": [
                round(pts["R2"] - pts["F1"], 3),
                round(float(np.percentile(d, 2.5)), 3),
                round(float(np.percentile(d, 97.5)), 3),
            ]
        }
    res["spearman_global_vs_deck"] = round(S.spearman(glob, deck), 3)
    res["spearman_H_vs_global"] = {k: round(S.spearman(v, glob), 3) for k, v in series.items()}
    # (3) Reihenfolge-Check
    oc = {}
    for ch in sorted({p["chunk"] for p in P}):
        sub = sorted([p for p in P if p["chunk"] == ch], key=lambda p: p["seq"])
        oc[ch] = {
            "rho_seq_F1H": round(S.spearman([p["seq"] for p in sub], [p["F1_H"] for p in sub]), 3),
            "rho_seq_is_creature": round(
                S.spearman([p["seq"] for p in sub], [float(p["is_creature"]) for p in sub]), 3
            ),
            "rho_seq_d": round(S.spearman([p["seq"] for p in sub], [p["d_H"] for p in sub]), 3),
            "rho_seq_resid_d_given_F1H": None,
        }
        # d bereinigt um F1_H (lineare Regression), dann Rang gegen seq
        f = np.array([p["F1_H"] for p in sub], float)
        d = np.array([p["d_H"] for p in sub], float)
        Z = np.column_stack([np.ones(len(f)), f])
        e = d - Z @ np.linalg.lstsq(Z, d, rcond=None)[0]
        oc[ch]["rho_seq_resid_d_given_F1H"] = round(S.spearman([p["seq"] for p in sub], e), 3)
        Z2 = np.column_stack([np.ones(len(f)), f, [float(p["is_creature"]) for p in sub]])
        e2 = d - Z2 @ np.linalg.lstsq(Z2, d, rcond=None)[0]
        oc[ch]["rho_seq_resid_d_given_F1H_creature"] = round(
            S.spearman([p["seq"] for p in sub], e2), 3
        )
        h = len(sub) // 2
        oc[ch]["mean_abs_d_first_half"] = round(float(np.mean([abs(p["d_H"]) for p in sub[:h]])), 2)
        oc[ch]["mean_abs_d_second_half"] = round(
            float(np.mean([abs(p["d_H"]) for p in sub[h:]])), 2
        )
    res["order_check"] = oc
    # (4) Farbe
    col = {}
    for v in sorted({p["colour_identity"] for p in P}):
        sub = [p for p in P if p["colour_identity"] == v]
        col[v] = {
            "n": len(sub),
            "mean_d": round(float(np.mean([p["d_H"] for p in sub])), 2),
            "mean_abs": round(float(np.mean([abs(p["d_H"]) for p in sub])), 2),
            "ge15": sum(abs(p["d_H"]) >= 15 for p in sub),
        }
    res["by_colour_identity"] = col
    # (5) H<=10 mit D>=75
    dd = {}
    for lab, rows in ST.runs().items():
        low = [r for r in rows if r["scores"]["H"] <= 10]
        dd[lab] = {
            "n_H_le10": len(low),
            "D_ge75": sum(r["scores"]["D"] >= 75 for r in low),
            "n_all": len(rows),
            "D_ge75_all": sum(r["scores"]["D"] >= 75 for r in rows),
        }
    res["H_le10_with_D_ge75"] = dd
    # (6) Schema
    sch = json.loads((C.W2 / "rater/rr2_output_schema.json").read_text())
    pc = sch["properties"]["pattern_check"]["items"]
    res["schema_pattern_check_items"] = {
        "additionalProperties": pc.get("additionalProperties"),
        "properties": sorted(pc.get("properties", {})),
    }
    r2 = C.load_r2()
    res["r2_rows_with_pattern_why"] = sum(
        any("why" in x for x in r["pattern_check"]) for r in r2.values()
    )
    res["f1_rows_with_pattern_why"] = sum(
        any("why" in x for x in r["pattern_check"]) for r in C.load_f1().values()
    )
    (WORK / "extra.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
