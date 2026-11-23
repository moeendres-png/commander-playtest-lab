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


def v3c_set(p: dict, run: str) -> float:
    """Sensitivität V3c: gesetzte Gewichte ohne N-Abzug."""
    return min(100.0, max(0.0, sum(w * p[f"{run}_{c}"] for c, w in W_V3.items())))


VERSIONS = {
    "H_frei": lambda p, run: float(p[f"{run}_H"]),
    "M5": m5,
    "v3b_formel_N_gleich_100_minus_D": v3b,
    "v3b_gesetzte_gewichte_N_gleich_100_minus_D": v3b_set,
    "v3c_gesetzte_gewichte_ohne_N": v3c_set,
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
        "N_mittelstufen": n_anchor_candidates(pairs, g1, anchor_names),
    }


def n_anchor_candidates(pairs: list[dict], g1: list[dict], anchor_names: set[str]) -> dict:
    """Kandidaten für N-Anker 30/40/60/70: N = 100 - D, nur Spells mit H_pooled >= 28 (Plan I2)."""
    levels = (30, 40, 60, 70)
    by_id = {p["oracle_id"]: p for p in pairs}

    def ok(p: dict) -> bool:
        return (
            p["card"] not in anchor_names and not p["is_land"] and (p["F1_H"] + p["R2_H"]) / 2 >= 28
        )

    triple: dict[int, list[str]] = {lv: [] for lv in levels}
    for g in g1:
        p = by_id.get(g["oracle_id"])
        if p is None or not ok(p):
            continue
        v = sorted([100 - p["F1_D"], 100 - p["R2_D"], 100 - g["scores"]["D"]])
        if v[2] - v[0] <= 5 and v[1] in levels:
            triple[v[1]].append(p["card"])
    pair_eq = {lv: 0 for lv in levels}
    for p in pairs:
        if ok(p) and p["F1_D"] == p["R2_D"] and 100 - p["F1_D"] in levels:
            pair_eq[100 - p["F1_D"]] += 1
    return {
        "stufe1": {str(lv): sorted(v) for lv, v in triple.items()},
        "stufe2_anzahl": {str(lv): n for lv, n in pair_eq.items()},
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


WEIGHT_PROBES = {
    "gleich_0.2": {"E": 0.2, "F": 0.2, "T": 0.2, "R": 0.2, "K": 0.2},
    "gesetzt_0.3_0.3_0.2_0.1_0.1": W_V3,
    "ER_betont_0.3_0.3_0.3_0.05_0.05": {"E": 0.3, "F": 0.3, "R": 0.3, "T": 0.05, "K": 0.05},
    "mitte_0.25_0.25_0.25_0.125_0.125": {"E": 0.25, "F": 0.25, "R": 0.25, "T": 0.125, "K": 0.125},
}


def weighted(p: dict, run: str, w: dict) -> float:
    return min(
        100.0,
        max(0.0, sum(x * p[f"{run}_{c}"] for c, x in w.items()) - 0.2 * (100 - p[f"{run}_D"])),
    )


def weight_probe(pairs: list[dict], usage: dict | None) -> dict:
    """Alle vier vor der Festlegung angesehenen Gewichtungen (Offenlegung, Plan I2)."""
    out = {}
    y = (
        np.array([usage[p["oracle_id"]]["deck_list_count"] for p in pairs], float)
        if usage
        else None
    )
    for name, w in WEIGHT_PROBES.items():
        a = np.array([weighted(p, "F1", w) for p in pairs])
        b = np.array([weighted(p, "R2", w) for p in pairs])
        sd = float(np.std(np.concatenate([a, b])))
        row = {
            "icc21": round(icc21(a, b), 3),
            "mittel_abs_d_durch_sd": round(float(np.abs(b - a).mean()) / sd, 3),
            "sd_gepoolt": round(sd, 2),
        }
        if y is not None:
            row["spearman_R2_quelldecks"] = round(spearman(b, y), 3)
            row["spearman_F1_quelldecks"] = round(spearman(a, y), 3)
        out[name] = row
    a = np.array([v3c_set(p, "F1") for p in pairs])
    b = np.array([v3c_set(p, "R2") for p in pairs])
    sd = float(np.std(np.concatenate([a, b])))
    row = {
        "icc21": round(icc21(a, b), 3),
        "mittel_abs_d_durch_sd": round(float(np.abs(b - a).mean()) / sd, 3),
        "sd_gepoolt": round(sd, 2),
    }
    if y is not None:
        row["spearman_R2_quelldecks"] = round(spearman(b, y), 3)
        row["spearman_F1_quelldecks"] = round(spearman(a, y), 3)
    out["gesetzt_ohne_N_V3c"] = row
    return out


def anchor_old(pairs: list[dict], anchors: dict) -> dict:
    """Alte Anker-MAE nur auf Kriterienzeilen E, F, T, R, K (ohne H und D), je Lauf (zu S5)."""
    by_name = {p["card"]: p for p in pairs}
    res: dict = {}
    for run in ("F1", "R2"):
        errs = {"v1_fixed": [], "uebrige": []}
        for kind in ("spell", "land"):
            for c in CRIT5:
                for row in anchors.get(kind, {}).get(c, []):
                    p = by_name.get(row["card"])
                    if p is None:
                        continue
                    grp = "v1_fixed" if row["kind"] == "v1_fixed" else "uebrige"
                    errs[grp].append(abs(p[f"{run}_{c}"] - row["value"]))
        res[run] = {
            g: {"n_zeilen": len(v), "mae": round(float(np.mean(v)), 2)}
            for g, v in errs.items()
            if v
        }
    crit_cards = {
        row["card"]
        for kind in ("spell", "land")
        for c in ("E", "F", "T", "R", "K", "D")
        for row in anchors.get(kind, {}).get(c, [])
    }
    h_cards = {
        row["card"] for kind in ("spell", "land") for row in anchors.get(kind, {}).get("H", [])
    }
    res["nur_in_H_tabelle"] = sorted(h_cards - crit_cards)
    res["hinweis"] = (
        "R2 sah nie die eigene Ankerzeile; F1 sah sie bei den 'uebrige'-Zeilen (A1 2.6)"
    )
    return res


def pilot_draw(
    pairs: list[dict], unfair: set[str], anchor_names: set[str], rng: random.Random
) -> list[dict]:
    pool = sorted((p for p in pairs if p["card"] not in anchor_names), key=lambda p: p["oracle_id"])
    taken: set[str] = set()

    def take(cands: list[dict], n: int) -> list[dict]:
        cands = [p for p in cands if p["oracle_id"] not in taken]
        got = rng.sample(cands, min(n, len(cands)))
        taken.update(p["oracle_id"] for p in got)
        return got

    out = take([p for p in pool if p["oracle_id"] in unfair], 10)
    hard = [p for p in pool if abs(p["d_H"]) >= 15]
    role = take(
        [p for p in hard if p["primary_role"] in ("token_production", "counters", "tapper")], 8
    )
    big = take([p for p in hard if p["is_creature"] and p["mv_group"] in ("6", "7+")], 8)
    cre = take([p for p in hard if p["is_creature"]], 16)
    non = take([p for p in hard if not p["is_creature"] and not p["is_land"]], 8)
    got_hard = role + big + cre + non
    got_hard += take(hard, 40 - len(got_hard))
    ctrl = [p for p in pool if abs(p["d_H"]) < 5 and not p["is_land"]]
    out += got_hard
    out += take([p for p in ctrl if p["is_creature"]], 15)
    out += take([p for p in ctrl if not p["is_creature"]], 15)
    out += take([p for p in pool if p["is_land"]], 10)
    return out


def clamp_h(p: dict, run: str) -> float:
    ref = v3b_set(p, run)
    return min(ref + 10, max(ref - 10, float(p[f"{run}_H"])))


def dry_run(
    pairs: list[dict],
    unfair: set[str],
    anchor_names: set[str],
    usage: dict | None,
    rng: random.Random,
) -> dict:
    """Pilotförmige Ziehungen aus alten Daten: F1/R2 als zwei Rater unter V3b bzw. V3a-Analogon.

    Orientierung für die Schwellen S1, S2, S3, S7 (Plan §3); zwei statt drei Rater, alte Kriterien.
    s3_kreatur/s3_nicht_kreatur: gleichmäßiger Versatz je Art (S3b, nur berichtet);
    s3_diff_max: größter differenzieller Versatz zwischen Kreatur, Nicht-Kreatur und Land (S3, Punkt);
    s7: Differenz gegen H_pooled (Anzeige-Bedingung, Plan §6).
    """
    versions = {"v3b_gesetzt": v3b_set, "v3a_analog_geklemmtes_H": clamp_h}
    res: dict = {
        "ziehungen": 200,
        "hinweis": "Punktwerte je Ziehung; Anteil = Ziehungen, die die Schwelle erfüllen",
    }
    stats: dict = {
        v: {
            "s1_icc": [],
            "s2": [],
            "s3_kreatur": [],
            "s3_nicht_kreatur": [],
            "s3_diff_max": [],
            "s7": [],
        }
        for v in versions
    }
    for _ in range(200):
        draw = pilot_draw(pairs, unfair, anchor_names, rng)
        h_pool_old = np.array([(p["F1_H"] + p["R2_H"]) / 2 for p in draw])
        y = (
            np.array([usage[p["oracle_id"]]["deck_list_count"] for p in draw], float)
            if usage
            else None
        )
        for v, f in versions.items():
            a = np.array([f(p, "F1") for p in draw])
            b = np.array([f(p, "R2") for p in draw])
            sd = float(np.std(np.concatenate([a, b])))
            d = b - a
            st = stats[v]
            st["s1_icc"].append(icc21(a, b))
            st["s2"].append(float(np.abs(d).mean()) / sd)
            cre = np.array([x for p, x in zip(draw, d, strict=False) if p["is_creature"]])
            non = np.array(
                [
                    x
                    for p, x in zip(draw, d, strict=False)
                    if not p["is_creature"] and not p["is_land"]
                ]
            )
            st["s3_kreatur"].append(abs(float(cre.mean())) / sd)
            st["s3_nicht_kreatur"].append(abs(float(non.mean())) / sd)
            lnd = np.array([x for p, x in zip(draw, d, strict=False) if p["is_land"]])
            means = [float(cre.mean()), float(non.mean()), float(lnd.mean())]
            st["s3_diff_max"].append(
                max(abs(means[i] - means[j]) for i in range(3) for j in range(i + 1, 3)) / sd
            )
            if y is not None:
                st["s7"].append(spearman((a + b) / 2, y) - spearman(h_pool_old, y))
    thresholds = {
        "s1_icc": (">=", 0.87),
        "s2": ("<=", 0.39),
        "s3_kreatur": ("<=", 0.15),
        "s3_nicht_kreatur": ("<=", 0.15),
        "s3_diff_max": ("<=", 0.15),
        "s7": (">=", -0.05),
    }
    for v, st in stats.items():
        row = {}
        for k, vals in st.items():
            if not vals:
                continue
            op, thr = thresholds[k]
            ok = [x >= thr if op == ">=" else x <= thr for x in vals]
            row[k] = {
                "median": round(float(np.median(vals)), 3),
                "p05_p95": [
                    round(float(np.percentile(vals, 5)), 3),
                    round(float(np.percentile(vals, 95)), 3),
                ],
                "anteil_erfuellt": round(sum(ok) / len(ok), 3),
            }
        both = [
            a <= 0.15 and b <= 0.15
            for a, b in zip(st["s3_kreatur"], st["s3_nicht_kreatur"], strict=False)
        ]
        row["s3_beide_arten_anteil_erfuellt"] = round(sum(both) / len(both), 3)
        res[v] = row
    return res


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
    usage = None
    if a.usage:
        res["s7_breite"] = s7_width(pairs, Path(a.usage), rng)
        usage = {r["oracle_id"]: r for r in jl(Path(a.usage))}
    anchors = json.loads((rub / "anchors.json").read_text(encoding="utf-8"))
    res["gewichte_offenlegung"] = weight_probe(pairs, usage)
    res["anker_mae_alt_kriterienzeilen"] = anchor_old(pairs, anchors)
    res["trockenlauf_pilotfoermig"] = dry_run(
        pairs, unfair, anchor_names, usage, random.Random(SEED + 1)
    )
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
