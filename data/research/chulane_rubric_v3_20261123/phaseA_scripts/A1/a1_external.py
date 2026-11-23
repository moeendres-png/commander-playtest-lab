"""Frage 4: externe Validität (nur Maßstab, nie Eingabe). F1, R2, H_pooled gegen Nutzungssignale.

  PYTHONPATH=<Klon>/src python3 a1_external.py --usage <usage_holdout.jsonl> [--corpus <chulane_corpus-Ordner>]

usage_holdout.jsonl ist die lokal erzeugte Hold-out-Datei aus extract_facts.py (nicht im Repo; dieselbe
Datei, auf der PILOT_REPORT §9 rechnet). --corpus zählt zusätzlich Quelldecks direkt aus den Repo-Decklisten
(reproduzierbare Gegenprobe). Gepaarter Bootstrap über Karten, 2000 Ziehungen, Seed 20261122.
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

WORK = C.WORK


def corpus_counts(root: Path, names: set[str]) -> tuple[dict[str, int], int, dict[str, int], int]:
    front = {}
    for n in names:
        front[n.lower()] = n
        if " // " in n:
            front[n.split(" // ")[0].lower()] = n
    cnt = dict.fromkeys(names, 0)
    cnt3 = dict.fromkeys(names, 0)
    total = total3 = 0
    for p in sorted(root.rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "cards" not in d:
            continue
        total += 1
        b3 = d.get("bracket") == 3
        total3 += b3
        seen = set()
        for c in d["cards"]:
            nm = front.get(str(c.get("name", "")).lower())
            if nm:
                seen.add(nm)
        for nm in seen:
            cnt[nm] += 1
            cnt3[nm] += b3
    return cnt, total, cnt3, total3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--usage", required=True)
    ap.add_argument("--corpus")
    a = ap.parse_args()
    f1, r2, pooled, facts = C.load_f1(), C.load_r2(), C.load_pooled(), C.load_facts()
    us = {r["oracle_id"]: r for r in C.jl(Path(a.usage))}
    ids = sorted(f1)
    assert set(ids) == set(us)
    H = {
        "F1": np.array([f1[i]["scores"]["H"] for i in ids], float),
        "R2": np.array([r2[i]["scores"]["H"] for i in ids], float),
        "pooled": np.array([pooled[i]["H_pooled"] for i in ids], float),
    }
    v1 = np.array([us[i]["v1"]["H_mean"] for i in ids], float)
    sig = {
        "deck_count_all": np.array([us[i]["deck_list_count"] for i in ids], float),
        "deck_share_b3": np.array(
            [
                (lambda b: b[0] / b[1] if b else 0.0)(us[i]["deck_list_by_bracket"].get("3"))
                for i in ids
            ],
            float,
        ),
        "edhrec_global_incl": np.array(
            [(lambda g: g[0] / g[1] if g else 0.0)(us[i]["edhrec_global_inclusion"]) for i in ids],
            float,
        ),
        "neg_scryfall_rank": np.array(
            [-(us[i]["scryfall_edhrec_rank"] or 10**6) for i in ids], float
        ),
    }
    ref = np.array([us[i]["in_reference_deck"] for i in ids], bool)
    res: dict = {"N": len(ids), "n_ref_deck": int(ref.sum())}
    if a.corpus:
        names = {f1[i]["card"] for i in ids}
        cnt, tot, cnt3, tot3 = corpus_counts(Path(a.corpus), names)  # noqa: RUF059
        cc = np.array([cnt[f1[i]["card"]] for i in ids], float)
        sig["corpus_count_repo"] = cc
        res["corpus_repo"] = {
            "decks": tot,
            "decks_b3": tot3,
            "spearman_vs_holdout_deck_count": round(S.spearman(cc, sig["deck_count_all"]), 4),
        }
    res["reproduce_pilot_report"] = {
        "spearman_F1_vs_deck_count": round(S.spearman(H["F1"], sig["deck_count_all"]), 3),
        "auc_F1_ref": round(S.auc_mw(H["F1"], ref), 3),
        "auc_v1_ref": round(S.auc_mw(v1, ref), 3),
        "auc_deck_count_ref": round(S.auc_mw(sig["deck_count_all"], ref), 3),
    }
    # Gesamt
    res["spearman_all"] = {}
    for sname, y in sig.items():
        pts, diffs = S.boot_paired_spearman(y, H, B=2000)
        res["spearman_all"][sname] = {
            "rho": {k: [round(x, 3) for x in v] for k, v in pts.items()},
            "paired_diff": {k: [round(x, 3) for x in v] for k, v in diffs.items()},
            "v1_rho": round(S.spearman(v1, y), 3),
        }
    # Referenzdeck-AUC mit gepaartem Bootstrap
    rng = np.random.default_rng(20261122)
    n = len(ids)
    pts = {k: S.auc_mw(v, ref) for k, v in H.items()}
    bs = {k: [] for k in H}
    for _ in range(2000):
        i = rng.integers(0, n, n)
        if ref[i].sum() == 0:
            continue
        for k, v in H.items():
            bs[k].append(S.auc_mw(v[i], ref[i]))
    res["auc_ref"] = {
        k: [
            round(pts[k], 3),
            round(float(np.percentile(bs[k], 2.5)), 3),
            round(float(np.percentile(bs[k], 97.5)), 3),
        ]
        for k in H
    }
    res["auc_ref_diff_R2_minus_F1"] = [
        round(pts["R2"] - pts["F1"], 3),
        round(float(np.percentile(np.array(bs["R2"]) - np.array(bs["F1"]), 2.5)), 3),
        round(float(np.percentile(np.array(bs["R2"]) - np.array(bs["F1"]), 97.5)), 3),
    ]
    # je Schicht/Kartenart (Signal: deck_count_all)
    pairs = {
        json.loads(x)["oracle_id"]: json.loads(x)
        for x in (WORK / "pairs.jsonl").read_text().splitlines()
    }
    sub_defs = {
        "Spells": lambda i: not facts[i]["is_land_front"],
        "Länder": lambda i: facts[i]["is_land_front"],
        "Kreaturen": lambda i: facts[i]["is_creature_front"],
        "Nichtkreatur-Spells": lambda i: (
            not facts[i]["is_creature_front"] and not facts[i]["is_land_front"]
        ),
        "mit Nutzung (>0)": lambda i: us[i]["deck_list_count"] > 0,
        "Welle 1": lambda i: pairs[i]["wave"] == 1,
        "Welle 2": lambda i: pairs[i]["wave"] == 2,
        "|d|>=15": lambda i: abs(pairs[i]["d_H"]) >= 15,
    }
    for st in sorted({p["stratum"] for p in pairs.values()}):
        sub_defs[f"Schicht {st}"] = (lambda s_: lambda i: pairs[i]["stratum"] == s_)(st)
    res["spearman_subsets_deck_count"] = {}
    for lab, fn in sub_defs.items():
        idx = np.array([fn(i) for i in ids])
        pts, diffs = S.boot_paired_spearman(
            sig["deck_count_all"][idx], {k: v[idx] for k, v in H.items()}, B=1000
        )
        res["spearman_subsets_deck_count"][lab] = {
            "n": int(idx.sum()),
            "rho": {k: [round(x, 3) for x in v] for k, v in pts.items()},
            "diff_F1-R2": [round(x, 3) for x in diffs["F1-R2"]],
        }
    # Vorzeichen: wer liegt bei den großen Abweichungen näher am Nutzungsrang? (Rang-Perzentile)
    big = [i for i in ids if abs(pairs[i]["d_H"]) >= 15]
    pr = S.rank(sig["deck_count_all"]) / (n - 1)
    rf, rr = S.rank(H["F1"]) / (n - 1), S.rank(H["R2"]) / (n - 1)
    pos = {i: k for k, i in enumerate(ids)}
    closer = {"F1": 0, "R2": 0, "tie": 0}
    for i in big:
        k = pos[i]
        a_, b_ = abs(rf[k] - pr[k]), abs(rr[k] - pr[k])
        closer["F1" if a_ < b_ else "R2" if b_ < a_ else "tie"] += 1
    res["big_diffs_closer_to_usage_rank"] = {"n": len(big), **closer}
    # Mittelwert der Nutzung je Richtung der Abweichung
    for lab, cond in (
        ("R2_lower_by15", lambda i: pairs[i]["d_H"] <= -15),
        ("R2_higher_by15", lambda i: pairs[i]["d_H"] >= 15),
    ):
        sel = [i for i in ids if cond(i)]
        res[f"usage_{lab}"] = {
            "n": len(sel),
            "median_deck_count": float(np.median([us[i]["deck_list_count"] for i in sel])),
            "share_ref_deck": round(float(np.mean([us[i]["in_reference_deck"] for i in sel])), 3),
        }
    res["usage_all_median_deck_count"] = float(np.median(sig["deck_count_all"]))
    (WORK / "external.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
