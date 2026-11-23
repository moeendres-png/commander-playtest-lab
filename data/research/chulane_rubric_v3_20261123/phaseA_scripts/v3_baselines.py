#!/usr/bin/env python3
"""Vergleichswerte für den Vorab-Plan Bewertung v3, nur aus alten Daten (kein Bewertungslauf).

Rechnet auf den Paaren von Lauf 1 (F1) und Lauf 2 (R2) aus A1 (`pairs.jsonl`):

1. Übereinstimmung F1 gegen R2 für vier H-Fassungen: das freie H, das ungewichtete Mittel M5 der
   Kriterien E, F, T, R, K, die Formel M5 - 0,2 * N und die Formel mit den gesetzten Gewichten des
   Plans (0,3 E, 0,3 F, 0,2 R, 0,1 T, 0,1 K) - 0,2 * N, jeweils mit N = 100 - D (Näherung für das
   neue Nachteil-Kriterium N, nur zur Orientierung). Je Fassung: SD, ICC(2,1) mit Bootstrap-KI, mittlere
   |d|, mittlere |d| / gepoolte SD, Versatz je Kartenart (absolut und in SD-Einheiten).
2. H gegen die Kriterien (alte Vergleichswerte zu S4): Anteile |H - M5| > 10 und > 15.
3. Höchste Korrelation zweier Kriterien (alte Vergleichswerte zu S9).
4. Kandidaten für Konsens-Anker 30/40/50/60/70 je Kriterium (Verfahren wie im Plan §2, I2).
5. Größen der Pilot-Schichten (Plan §3).
6. Breite des Bootstrap-KI für Spearman(H, Quelldeck-Zahl) auf 100 zufälligen Karten (zu S7);
   nur wenn `--usage` angegeben ist (Datei nicht im Repo).

Außerdem schreibt es die Liste der 60 Karten „kaum fair bewertbar“ aus A2 (oracle_id, Name,
Defektklassen) nach `--unfair-out`, damit die Pilot-Schicht ohne den XMage-Checkout reproduzierbar ist.

Aufruf (nach A1/run_all.sh und den A2-Skripten):
  python3 v3_baselines.py --pairs <A1_OUT>/pairs.jsonl --a2 <A2-Ausgabeordner> \
      [--usage <usage_holdout.jsonl>] --out <ordner>/v3_baselines.json [--unfair-out <datei>]
Nur Standardbibliothek und numpy; feste Seeds.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

import numpy as np

SEED = 20261123
LEVELS = (30, 40, 50, 60, 70)
CRIT5 = "EFTRK"
UNFAIR_GROUP_CHECKS = {
    "mechanik": [
        "b_kw_unexplained_any",
        "b_scan_noreminder::prepared/prepare",
        "b_scan_noreminder::loyalty ability",
        "b_scan_noreminder::ki counter (flip)",
        "b_adventure_rule_unexplained",
        "g_prepare_definition_ruling_not_shown_in_full",
    ],
    "land_fakten": [
        "f_land_fetch_flag_wrong",
        "f_land_colours_none_but_fetches",
        "f_land_untapped_but_fetched_land_tapped",
    ],
    "seiten_spezialtypen_verweise": [
        "a_back_face_pt_missing",
        "d_planeswalker_loyalty_missing",
        "d_spacecraft_pt_unconditional",
        "a_keyword_from_other_face_unlabelled",
        "a_produced_mana_from_other_face_unlabelled",
        "c_named_reference_undefined",
        "c_token_no_reminder_any",
    ],
    "hybrid_castability": ["f_hybrid_pips_double_counted"],
}


def repo_root() -> Path:
    return Path(os.environ.get("V3_REPO", Path(__file__).resolve().parents[4]))


def jl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def icc21(a: np.ndarray, b: np.ndarray) -> float:
    x = np.column_stack([a, b]).astype(float)
    n, k = x.shape
    gm = x.mean()
    msr = k * ((x.mean(1) - gm) ** 2).sum() / (n - 1)
    msc = n * ((x.mean(0) - gm) ** 2).sum() / (k - 1)
    sse = ((x - x.mean(1, keepdims=True) - x.mean(0, keepdims=True) + gm) ** 2).sum()
    mse = sse / ((n - 1) * (k - 1))
    return float((msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n))


def rank(v: np.ndarray) -> np.ndarray:
    order = np.argsort(v, kind="mergesort")
    r = np.empty(len(v))
    r[order] = np.arange(len(v), dtype=float)
    vs = v[order]
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and vs[j + 1] == vs[i]:
            j += 1
        r[order[i : j + 1]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.corrcoef(rank(np.asarray(a, float)), rank(np.asarray(b, float)))[0, 1])


def m5(p: dict, run: str) -> float:
    return sum(p[f"{run}_{c}"] for c in CRIT5) / 5


def v3b(p: dict, run: str) -> float:
    return min(100.0, max(0.0, m5(p, run) - 0.2 * (100 - p[f"{run}_D"])))


W_V3 = {"E": 0.3, "F": 0.3, "R": 0.2, "T": 0.1, "K": 0.1}


def v3b_set(p: dict, run: str) -> float:
    """Gesetzte v3b-Gewichte des Plans (I2), N = 100 - D als Näherung."""
    return min(
        100.0,
        max(0.0, sum(w * p[f"{run}_{c}"] for c, w in W_V3.items()) - 0.2 * (100 - p[f"{run}_D"])),
    )


VERSIONS = {
    "H_frei": lambda p, run: float(p[f"{run}_H"]),
    "M5": m5,
    "v3b_formel_N_gleich_100_minus_D": v3b,
    "v3b_gesetzte_gewichte_N_gleich_100_minus_D": v3b_set,
}


def agreement(pairs: list[dict], rng: random.Random) -> dict:
    out = {}
    types = {
        "kreatur": lambda p: p["is_creature"],
        "nicht_kreatur_spell": lambda p: not p["is_creature"] and not p["is_land"],
        "land": lambda p: p["is_land"],
    }
    n = len(pairs)
    for name, f in VERSIONS.items():
        a = np.array([f(p, "F1") for p in pairs])
        b = np.array([f(p, "R2") for p in pairs])
        d = b - a
        sd_pool = float(np.std(np.concatenate([a, b])))
        boots = []
        for _ in range(1000):
            idx = np.array([rng.randrange(n) for _ in range(n)])
            boots.append(icc21(a[idx], b[idx]))
        res = {
            "n": n,
            "sd_F1": round(float(np.std(a)), 2),
            "sd_R2": round(float(np.std(b)), 2),
            "sd_gepoolt": round(sd_pool, 2),
            "mittel_F1": round(float(a.mean()), 2),
            "mittel_R2": round(float(b.mean()), 2),
            "icc21": round(icc21(a, b), 3),
            "icc21_ki95": [
                round(float(np.percentile(boots, 2.5)), 3),
                round(float(np.percentile(boots, 97.5)), 3),
            ],
            "mittel_d": round(float(d.mean()), 2),
            "mittel_abs_d": round(float(np.abs(d).mean()), 2),
            "mittel_abs_d_durch_sd": round(float(np.abs(d).mean()) / sd_pool, 3),
            "n_abs_d_ge15": int((np.abs(d) >= 15).sum()),
            "versatz_je_kartenart": {},
        }
        for t, sel in types.items():
            dd = np.array([x for p, x in zip(pairs, d, strict=False) if sel(p)])
            res["versatz_je_kartenart"][t] = {
                "n": len(dd),
                "mittel_d": round(float(dd.mean()), 2),
                "in_sd": round(float(dd.mean()) / sd_pool, 3),
            }
        out[name] = res
    return out


def h_vs_criteria(pairs: list[dict]) -> dict:
    out = {}
    for run in ("F1", "R2"):
        gap = np.array([p[f"{run}_H"] - m5(p, run) for p in pairs])
        out[run] = {
            "n": len(pairs),
            "mittlere_luecke_H_minus_M5": round(float(gap.mean()), 2),
            "n_abs_luecke_gt10": int((np.abs(gap) > 10).sum()),
            "n_abs_luecke_gt15": int((np.abs(gap) > 15).sum()),
        }
    return out


def criteria_corr(pairs: list[dict]) -> dict:
    out = {}
    for run in ("F1", "R2"):
        m = np.array([[p[f"{run}_{c}"] for c in "EFTRKD"] for p in pairs], float)
        c = np.corrcoef(m.T)
        best = (0.0, "")
        for i in range(6):
            for j in range(i + 1, 6):
                if abs(c[i, j]) > abs(best[0]):
                    best = (float(c[i, j]), "EFTRKD"[i] + "EFTRKD"[j])
        out[run] = {"max_r": round(best[0], 3), "paar": best[1]}
    return out


def anchor_candidates(pairs: list[dict], g1: list[dict], anchor_names: set[str]) -> dict:
    by_id = {p["oracle_id"]: p for p in pairs}
    triple: dict[str, dict[int, list[str]]] = {c: {lv: [] for lv in LEVELS} for c in CRIT5}
    for g in g1:
        p = by_id.get(g["oracle_id"])
        if p is None or p["card"] in anchor_names or p["is_land"]:
            continue
        for c in CRIT5:
            v = sorted([p[f"F1_{c}"], p[f"R2_{c}"], g["scores"][c]])
            if v[2] - v[0] <= 5 and v[1] in LEVELS:
                triple[c][v[1]].append(p["card"])
    pair_eq: dict[str, dict[int, int]] = {c: {lv: 0 for lv in LEVELS} for c in CRIT5}
    for p in pairs:
        if p["card"] in anchor_names or p["is_land"]:
            continue
        for c in CRIT5:
            if p[f"F1_{c}"] == p[f"R2_{c}"] and p[f"F1_{c}"] in LEVELS:
                pair_eq[c][p[f"F1_{c}"]] += 1
    return {
        "stufe1_F1_R2_G1_hoechstens_5_auseinander": {
            c: {str(lv): sorted(v) for lv, v in d.items()} for c, d in triple.items()
        },
        "stufe2_F1_gleich_R2_gleich_Stufe_anzahl": {
            c: {str(lv): n for lv, n in d.items()} for c, d in pair_eq.items()
        },
        "hinweis": "nur Spells, ohne bisherige Ankerkarten; Stufe 2 greift nur für leere Zellen von Stufe 1",
    }


def pilot_pools(pairs: list[dict], unfair: set[str], anchor_names: set[str]) -> dict:
    absd = {p["oracle_id"]: abs(p["d_H"]) for p in pairs}
    non_anchor = [p for p in pairs if p["card"] not in anchor_names]
    return {
        "N": len(pairs),
        "n_abs_d_ge15": sum(1 for v in absd.values() if v >= 15),
        "n_abs_d_lt5": sum(1 for v in absd.values() if v < 5),
        "n_laender": sum(1 for p in pairs if p["is_land"]),
        "n_ankerkarten_v2": sum(1 for p in pairs if p["card"] in anchor_names),
        "n_kaum_fair": len(unfair),
        "nicht_anker": {
            "n_abs_d_ge15": sum(1 for p in non_anchor if abs(p["d_H"]) >= 15),
            "n_abs_d_lt5_ohne_land": sum(
                1 for p in non_anchor if abs(p["d_H"]) < 5 and not p["is_land"]
            ),
            "n_laender": sum(1 for p in non_anchor if p["is_land"]),
            "n_kaum_fair": sum(1 for p in non_anchor if p["oracle_id"] in unfair),
        },
    }


def s7_width(pairs: list[dict], usage_path: Path, rng: random.Random) -> dict:
    us = {r["oracle_id"]: r for r in jl(usage_path)}
    ids = [p["oracle_id"] for p in pairs]
    y = np.array([us[i]["deck_list_count"] for i in ids], float)
    out = {"n_alle": len(ids)}
    for name, f in VERSIONS.items():
        x2 = np.array([f(p, "R2") for p in pairs])
        x1 = np.array([f(p, "F1") for p in pairs])
        out[f"spearman_R2_{name}_alle"] = round(spearman(x2, y), 3)
        out[f"spearman_F1_{name}_alle"] = round(spearman(x1, y), 3)
    widths, diff_widths = [], []
    xh = np.array([p["R2_H"] for p in pairs], float)
    xf = np.array([v3b(p, "R2") for p in pairs])
    for _ in range(50):
        sub = rng.sample(range(len(ids)), 100)
        boots, dboots = [], []
        for _ in range(500):
            idx = [sub[rng.randrange(100)] for _ in range(100)]
            r_h = spearman(xh[idx], y[idx])
            boots.append(r_h)
            dboots.append(spearman(xf[idx], y[idx]) - r_h)
        widths.append(np.percentile(boots, 97.5) - np.percentile(boots, 2.5))
        diff_widths.append(np.percentile(dboots, 97.5) - np.percentile(dboots, 2.5))
    out["ki95_breite_spearman_100_zufallskarten_median"] = round(float(np.median(widths)), 3)
    out["ki95_breite_gepaarte_differenz_100_zufallskarten_median"] = round(
        float(np.median(diff_widths)), 3
    )
    out["wiederholungen"] = "50 Teilmengen x 500 Bootstrap-Ziehungen"
    return out


def unfair_list(a2_dir: Path, pairs: list[dict]) -> tuple[set[str], list[dict]]:
    summary = json.loads((a2_dir / "A2_summary.json").read_text(encoding="utf-8"))
    metrics = json.loads((a2_dir / "A2_metrics.json").read_text(encoding="utf-8"))["defects"]
    ids = set(summary["unfair_ids"])
    names = {p["oracle_id"]: p["card"] for p in pairs}
    rows = []
    for oid in sorted(ids):
        classes = sorted(
            g
            for g, keys in UNFAIR_GROUP_CHECKS.items()
            if any(oid in metrics.get(k, {}).get("ids", []) for k in keys)
        )
        rows.append({"oracle_id": oid, "card": names.get(oid, ""), "defektklassen": classes})
    return ids, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--a2", required=True)
    ap.add_argument("--usage")
    ap.add_argument("--out", required=True)
    ap.add_argument("--unfair-out")
    a = ap.parse_args()
    rng = random.Random(SEED)
    pairs = jl(Path(a.pairs))
    pairs.sort(key=lambda p: p["oracle_id"])
    rub = repo_root() / "data/research/chulane_rubric_v2_20261118"
    g1 = jl(rub / "audit/independent_rater_ratings.jsonl")
    anchor_names = {p["card"] for p in pairs if p["is_anchor"]}
    unfair, unfair_rows = unfair_list(Path(a.a2), pairs)
    res = {
        "quelle": "A1 pairs.jsonl (F1 gegen R2, 922 Karten); G1 audit/independent_rater_ratings.jsonl; A2",
        "seed": SEED,
        "uebereinstimmung_F1_R2": agreement(pairs, rng),
        "H_gegen_kriterien": h_vs_criteria(pairs),
        "kriterien_korrelation": criteria_corr(pairs),
        "anker_kandidaten": anchor_candidates(pairs, g1, anchor_names),
        "pilot_schichten": pilot_pools(pairs, unfair, anchor_names),
    }
    if a.usage:
        res["s7_breite"] = s7_width(pairs, Path(a.usage), rng)
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if a.unfair_out:
        Path(a.unfair_out).write_text(
            json.dumps(
                {
                    "quelle": "A2 a2_summary.py unfair_ids",
                    "n": len(unfair_rows),
                    "karten": unfair_rows,
                },
                indent=1,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {k: v for k, v in res.items() if k != "anker_kandidaten"}, indent=1, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
