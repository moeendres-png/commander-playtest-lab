"""Frage 2: Zerlegung d = R2 - F1 (922 Karten, R2 = Welle 1 + Welle 2, ohne Retest-Charge 8).

PYTHONPATH=<Klon>/src python3 a1_decomp.py      -> $A1_OUT/decomp.json und $A1_OUT/pairs.jsonl
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


def band(h: float) -> str:
    for lo, hi, lab in (
        (95, 100, "95-100"),
        (72, 94, "72-94"),
        (50, 71, "50-71"),
        (28, 49, "28-49"),
        (5, 27, "5-27"),
        (0, 4, "0-4"),
    ):
        if lo <= h <= hi:
            return lab
    return "?"


def mv_group(f):
    if f["is_land_front"]:
        return "Land"
    mv = int(f["mana_value"] or 0)
    return str(mv) if mv <= 6 else "7+"


def summarize(rows, key="d_H"):
    d = np.array([r[key] for r in rows], float)
    if len(d) == 0:
        return {"n": 0}
    return {
        "n": len(d),
        "mean_d": round(float(d.mean()), 2),
        "sd_d": round(float(d.std(ddof=1)), 2) if len(d) > 1 else None,
        "mean_abs": round(float(np.abs(d).mean()), 2),
        "ge10": int((np.abs(d) >= 10).sum()),
        "ge15": int((np.abs(d) >= 15).sum()),
        "icc21_H": round(S.icc21([r["F1_H"] for r in rows], [r["R2_H"] for r in rows]), 3)
        if len(d) >= 3
        else None,
    }


def main() -> None:
    f1, r2, facts = C.load_f1(), C.load_r2(), C.load_facts()
    anch = C.anchors()
    anchor_names = {
        r["card"] for t in (anch["spell"], anch["land"]) for rows in t.values() for r in rows
    }
    m1 = {c["oracle_id"]: c for c in C.manifest_w1()["cards"]}
    m2 = {c["oracle_id"]: c for c in C.manifest_w2()["cards"] if c.get("role") == "pool"}
    pairs = []
    for oid, a in f1.items():
        b = r2[oid]
        f = facts[oid]
        st = (m1.get(oid) or {}).get("stratum") if b["wave"] == 1 else m2[oid]["stratum"]
        row = {
            "oracle_id": oid,
            "card": a["card"],
            "wave": b["wave"],
            "chunk": b["chunk"],
            "seq": b["seq"],
            "n_chunk": b["n_chunk"],
            "stratum": f"w{b['wave']}:{st}",
            "is_anchor": a["card"] in anchor_names,
            "is_land": f["is_land_front"],
            "type_group": f["type_group"],
            "mv_group": mv_group(f),
            "colour_identity": f["colour_identity"] or "C",
            "n_colours": len(f["colour_identity"] or ""),
            "primary_role": f.get("primary_role") or "none",
            "is_creature": f["is_creature_front"],
            "F1_conf": a["confidence"],
            "R2_conf": b["confidence"],
            "F1_reason_len": len(a["reason"]),
            "R2_reason_len": len(b["reason"]),
            "F1_reason": a["reason"],
            "R2_reason": b["reason"],
            "F1_noteH": a["notes"].get("H", ""),
            "R2_noteH": b["notes"].get("H", ""),
            "F1_judged": a["judged_as"],
            "R2_judged": b["judged_as"],
        }
        for k in C.ALL:
            row[f"F1_{k}"] = a["scores"][k]
            row[f"R2_{k}"] = b["scores"][k]
            row[f"d_{k}"] = b["scores"][k] - a["scores"][k]
        row["F1_band"], row["R2_band"] = band(row["F1_H"]), band(row["R2_H"])
        pairs.append(row)
    res: dict = {"N": len(pairs)}
    # je Teilkriterium
    res["per_criterion"] = {}
    for k in C.ALL:
        d = np.array([p[f"d_{k}"] for p in pairs], float)
        res["per_criterion"][k] = {
            "mean_F1": round(float(np.mean([p[f"F1_{k}"] for p in pairs])), 2),
            "mean_R2": round(float(np.mean([p[f"R2_{k}"] for p in pairs])), 2),
            "mean_d": round(float(d.mean()), 2),
            "sd_d": round(float(d.std(ddof=1)), 2),
            "icc21": round(
                S.icc21([p[f"F1_{k}"] for p in pairs], [p[f"R2_{k}"] for p in pairs]), 3
            ),
            "spearman": round(
                S.spearman([p[f"F1_{k}"] for p in pairs], [p[f"R2_{k}"] for p in pairs]), 3
            ),
            "abs_ge10": int((np.abs(d) >= 10).sum()),
            "abs_ge20": int((np.abs(d) >= 20).sum()),
        }
    # Spells/Länder getrennt je Kriterium
    for lab, sel in (("spells", lambda p: not p["is_land"]), ("lands", lambda p: p["is_land"])):
        sub = [p for p in pairs if sel(p)]
        res[f"per_criterion_{lab}"] = {
            k: {
                "n": len(sub),
                "mean_d": round(float(np.mean([p[f"d_{k}"] for p in sub])), 2),
                "icc21": round(
                    S.icc21([p[f"F1_{k}"] for p in sub], [p[f"R2_{k}"] for p in sub]), 3
                ),
            }
            for k in C.ALL
        }
    groups = {
        "F1_band": "F1_band",
        "R2_band": "R2_band",
        "wave": "wave",
        "chunk": "chunk",
        "stratum": "stratum",
        "type_group": "type_group",
        "mv_group": "mv_group",
        "n_colours": "n_colours",
        "is_creature": "is_creature",
        "primary_role": "primary_role",
        "F1_conf": "F1_conf",
        "R2_conf": "R2_conf",
        "is_anchor": "is_anchor",
    }
    res["groups"] = {}
    for g, key in groups.items():
        out = {}
        for val in sorted({str(p[key]) for p in pairs}):
            sub = [p for p in pairs if str(p[key]) == val]
            out[val] = summarize(sub)
        res["groups"][g] = out
    # Mittelband-Gruppe nach H_pooled-Mittel (vermeidet Regression zur Mitte bei Gruppierung nach einem Lauf)
    out = {}
    for p in pairs:
        p["mean_band"] = band(round((p["F1_H"] + p["R2_H"]) / 2))
    for val in sorted({p["mean_band"] for p in pairs}):
        out[val] = summarize([p for p in pairs if p["mean_band"] == val])
    res["groups"]["mean_band"] = out
    # Position in der Charge (Zehnerblöcke wie gelesen; Welle 2 und Welle 1 getrennt)
    pos = {}
    for w in (1, 2):
        for blk in range(10):
            sub = [p for p in pairs if p["wave"] == w and (p["seq"] - 1) // 10 == blk]
            if sub:
                pos[f"w{w}:seq{blk * 10 + 1}-{blk * 10 + 10}"] = summarize(sub)
    res["position_blocks"] = pos
    # Rangkorrelation Position vs d bzw. |d| je Charge
    rc = {}
    for ch in sorted({p["chunk"] for p in pairs}):
        sub = [p for p in pairs if p["chunk"] == ch]
        rc[ch] = {
            "n": len(sub),
            "rho_seq_d": round(S.spearman([p["seq"] for p in sub], [p["d_H"] for p in sub]), 3),
            "rho_seq_absd": round(
                S.spearman([p["seq"] for p in sub], [abs(p["d_H"]) for p in sub]), 3
            ),
            "rho_seq_R2len": round(
                S.spearman([p["seq"] for p in sub], [p["R2_reason_len"] for p in sub]), 3
            ),
            "mean_R2len_first_half": round(
                float(np.mean([p["R2_reason_len"] for p in sub if p["seq"] <= len(sub) / 2])), 1
            ),
            "mean_R2len_second_half": round(
                float(np.mean([p["R2_reason_len"] for p in sub if p["seq"] > len(sub) / 2])), 1
            ),
        }
    res["position_rank_corr"] = rc
    # Länge der Begründung
    lens_r2 = np.array([p["R2_reason_len"] for p in pairs])
    lens_f1 = np.array([p["F1_reason_len"] for p in pairs])
    res["reason_len"] = {
        "F1_median": float(np.median(lens_f1)),
        "R2_median": float(np.median(lens_r2)),
        "rho_R2len_absd": round(S.spearman(lens_r2, [abs(p["d_H"]) for p in pairs]), 3),
        "rho_F1len_absd": round(S.spearman(lens_f1, [abs(p["d_H"]) for p in pairs]), 3),
        "rho_R2len_d": round(S.spearman(lens_r2, [p["d_H"] for p in pairs]), 3),
    }
    q = np.quantile(lens_r2, [0.25, 0.5, 0.75])
    res["groups"]["R2_len_quartile"] = {
        f"Q{i + 1}": summarize(
            [p for p in pairs if (np.searchsorted(q, p["R2_reason_len"], side="right")) == i]
        )
        for i in range(4)
    }
    # Anker-Spells vs Rest-Spells (Welle 2) und Abstand zu den Ankerwerten H
    anchH = {}
    for t in ("spell", "land"):
        for r in anch[t].get("H", []):
            anchH.setdefault(r["card"], r["value"])
    av = []
    for p in pairs:
        if p["card"] in anchH:
            av.append(
                {
                    "card": p["card"],
                    "anchor_H": anchH[p["card"]],
                    "F1_H": p["F1_H"],
                    "R2_H": p["R2_H"],
                    "wave": p["wave"],
                    "is_land": p["is_land"],
                }
            )
    res["anchor_H_cards"] = {
        "n": len(av),
        "mae_F1_to_anchor": round(float(np.mean([abs(x["F1_H"] - x["anchor_H"]) for x in av])), 2),
        "mae_R2_to_anchor": round(float(np.mean([abs(x["R2_H"] - x["anchor_H"]) for x in av])), 2),
        "F1_exact_anchor": sum(x["F1_H"] == x["anchor_H"] for x in av),
        "R2_exact_anchor": sum(x["R2_H"] == x["anchor_H"] for x in av),
        "rows": av,
    }
    # alle Kriterien: wie oft trifft F1 bzw. R2 den Ankerwert der eigenen Zeile exakt?
    hit = {"F1": 0, "R2": 0, "n": 0}
    byname = {p["card"]: p for p in pairs}
    for t in ("spell", "land"):
        for crit, rows in anch[t].items():
            for r in rows:
                p = byname.get(r["card"])
                if not p:
                    continue
                hit["n"] += 1
                hit["F1"] += p[f"F1_{crit}"] == r["value"]
                hit["R2"] += p[f"R2_{crit}"] == r["value"]
    res["anchor_rows_exact_hits"] = hit
    # Welle-2 Anker-Spells vs Rest-Spells: Kriterienprofil
    for lab, sel in (
        ("w2_anchor_spells", lambda p: p["wave"] == 2 and p["is_anchor"] and not p["is_land"]),
        (
            "w2_rest_spells",
            lambda p: (
                p["wave"] == 2
                and not p["is_anchor"]
                and not p["is_land"]
                and p["stratum"] == "w2:rest"
            ),
        ),
    ):
        sub = [p for p in pairs if sel(p)]
        res[lab] = {
            "n": len(sub),
            "mean_F1_H": round(float(np.mean([p["F1_H"] for p in sub])), 2),
            "share_creature": round(float(np.mean([p["is_creature"] for p in sub])), 3),
            "mean_mv": round(
                float(np.mean([facts[p["oracle_id"]]["mana_value"] or 0 for p in sub])), 2
            ),
            **{f"mean_d_{k}": round(float(np.mean([p[f"d_{k}"] for p in sub])), 2) for k in C.ALL},
        }
    # Rest-Spells nach F1-Band (ist der Anker-Unterschied nur ein Band-Effekt?)
    rs = {}
    for b in ("0-4", "5-27", "28-49", "50-71", "72-94"):
        a_ = [
            p["d_H"]
            for p in pairs
            if p["wave"] == 2 and not p["is_land"] and p["is_anchor"] and p["F1_band"] == b
        ]
        r_ = [
            p["d_H"]
            for p in pairs
            if p["wave"] == 2 and not p["is_land"] and not p["is_anchor"] and p["F1_band"] == b
        ]
        rs[b] = {
            "anchor_n": len(a_),
            "anchor_mean_d": round(float(np.mean(a_)), 2) if a_ else None,
            "nonanchor_n": len(r_),
            "nonanchor_mean_d": round(float(np.mean(r_)), 2) if r_ else None,
        }
    res["w2_spells_by_F1band_anchor_vs_not"] = rs
    # Konfidenz-Kreuztabelle
    ct = {}
    for p in pairs:
        ct[f"{p['F1_conf']}|{p['R2_conf']}"] = ct.get(f"{p['F1_conf']}|{p['R2_conf']}", 0) + 1
    res["confidence_crosstab_F1|R2"] = dict(sorted(ct.items()))
    WORK.mkdir(exist_ok=True)
    (WORK / "decomp.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    with (WORK / "pairs.jsonl").open("w") as fh:
        for p in sorted(pairs, key=lambda x: x["oracle_id"]):
            fh.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")
    print(
        json.dumps(
            {k: v for k, v in res.items() if k != "anchor_H_cards"}, indent=1, ensure_ascii=False
        )[:20000]
    )


if __name__ == "__main__":
    main()
