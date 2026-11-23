#!/usr/bin/env python3
"""A2: group the per-check results (A2_metrics.json) into report defects and compute the totals.

  python3 a2_summary.py --out <scratchpad>/phaseA        (after a2_inventory.py and a2_uncertainty.py)

Writes <out>/A2_summary.json. Impact: 1 = rater can rate fairly without it (ja), 2 = unklar, 3 = nein.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

GROUPS = {
    # id: (title, check keys, impact)
    "R1_rulings_cut": (
        "Rulings abgeschnitten (max. 4, 240 Zeichen)",
        ["g_rulings_cut_more_than_4", "g_ruling_text_truncated_240"],
        1.5,
    ),
    "P1_pattern_noise": (
        "Pattern-Hits irreführend (etb_own auf Nicht-Kreatur, Beleg = Rollenlabel)",
        ["f_pattern_etb_own_on_noncreature", "f_pattern_evidence_is_role_label_not_text"],
        1,
    ),
    "P2_pattern_rater_wrong": (
        "Pattern-Hit von einem Rater als wrong beurteilt",
        ["f_pattern_hit_judged_wrong_by_a_rater"],
        1,
    ),
    "M1_mechanic_unexplained": (
        "Mechanik ohne Erklärung (kein Reminder, nicht im Guide)",
        [
            "b_kw_unexplained_any",
            "b_scan_noreminder::prepared/prepare",
            "b_scan_noreminder::loyalty ability",
            "b_scan_noreminder::ki counter (flip)",
            "b_adventure_rule_unexplained",
            "g_prepare_definition_ruling_not_shown_in_full",
        ],
        2.5,
    ),
    "C1_castability": (
        "Castability: Hybrid doppelt/ignoriert, X=0 nicht gesagt, Verbilligung ignoriert",
        [
            "f_hybrid_pips_double_counted",
            "f_castability_hybrid_phyrexian_left_out_not_said",
            "f_castability_x_at_zero_not_said",
            "f_castability_ignores_alt_cost_or_self_reduction",
        ],
        1.5,
    ),
    "L1_land_facts": (
        "Land-Fakten falsch (fetches/Farben/untapped bei Fetchländern)",
        [
            "f_land_fetch_flag_wrong",
            "f_land_colours_none_but_fetches",
            "f_land_untapped_but_fetched_land_tapped",
        ],
        2,
    ),
    "B1_body_counters": (
        "Körper-Benchmark ignoriert ETB-Zählmarken / fehlt",
        ["f_body_benchmark_ignores_etb_counters", "f_body_benchmark_missing_for_creature"],
        1,
    ),
    "S1_faces_special": (
        "Doppelkarten/Spezialtypen + Verweise: Rückseiten-P/T, Loyalty, Spacecraft-P/T, Keywords/Mana ohne Seitenangabe, 'card named X', Token ohne Reminder",
        [
            "a_back_face_pt_missing",
            "d_planeswalker_loyalty_missing",
            "d_spacecraft_pt_unconditional",
            "a_keyword_from_other_face_unlabelled",
            "a_produced_mana_from_other_face_unlabelled",
            "c_named_reference_undefined",
            "c_token_no_reminder_any",
        ],
        2.5,
    ),
    "Q1_roles_cut": (
        "Peer-Rollen auf 3 gekürzt / keine Rolle (Nichtland)",
        ["f_peer_roles_cut_at_3"],
        1,
    ),
    "E1_chulane_grader": (
        "Chulane-Text nicht im Block (Prüfer-Seite; Claims zitieren Chulane)",
        ["e_claim_quotes_chulane_text_not_in_block"],
        2,
    ),
}
UNFAIR_RISK = ["M1_mechanic_unexplained", "L1_land_facts", "S1_faces_special"]
HYBRID_KEYS = ["f_hybrid_pips_double_counted"]
BLOCK = [g for g in GROUPS if g != "E1_chulane_grader"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    M = json.loads((out / "A2_metrics.json").read_text(encoding="utf-8"))
    D = M["defects"]
    U = json.loads((out / "A2_uncertainty_stats.json").read_text(encoding="utf-8"))  # noqa: F841
    low = [
        json.loads(x)
        for x in (out / "A2_low_confidence_cards.jsonl").read_text(encoding="utf-8").splitlines()
        if x
    ]
    res = {}
    sets = {}
    for g, (title, keys, imp) in GROUPS.items():
        s = set()
        ex = []
        for k in keys:
            if k in D:
                s |= set(D[k]["ids"])
                ex += D[k]["examples"]
        sets[g] = s
        res[g] = {
            "title": title,
            "n": len(s),
            "impact": imp,
            "score": round(len(s) * imp, 1),
            "examples": ex[:5],
            "checks": {k: D[k]["n"] for k in keys if k in D},
        }
    # rater-reported (uncertainty) block-caused, and deck-context
    blockc = {e["oracle_id"] for e in low if e["block_caused"]}
    deck = {e["oracle_id"] for e in low if "deck_list_not_visible" in e["missing_info_tags"]}
    mana = {e["oracle_id"] for e in low if "mana_base_not_visible" in e["missing_info_tags"]}
    ctx = deck | mana
    rules = {
        e["oracle_id"]
        for e in low
        if any("rules_corner_not_in_rulings" in r["tags"] for r in e["ratings"])
    }
    res["K1_deck_context"] = {
        "title": "Deck-/Manabasis-Kontext fehlt (Liste, Typen, Basics, Land-Typen) – Rater-gemeldet",  # noqa: RUF001
        "n": len(ctx),
        "impact": 2,
        "score": len(ctx) * 2,
        "n_deck": len(deck),
        "n_mana": len(mana),
    }
    res["K3_rules_corner"] = {
        "title": "Allgemeine Regel fehlt (nicht in Text/Rulings) – Rater-gemeldet",  # noqa: RUF001
        "n": len(rules),
        "impact": 1.5,
        "score": len(rules) * 1.5,
    }
    any_block = set().union(*[sets[g] for g in BLOCK])
    unfair = set().union(*[sets[g] for g in UNFAIR_RISK]) | set(
        D["f_hybrid_pips_double_counted"]["ids"]
    )
    summary = {
        "groups_ranked": sorted(res.items(), key=lambda x: -x[1]["score"]),
        "n_any_block_defect_detected": len(any_block),
        "n_any_block_defect_excl_soft(pattern_noise,roles_cut,body)": len(
            set().union(
                *[
                    sets[g]
                    for g in BLOCK
                    if g
                    not in (
                        "P1_pattern_noise",
                        "Q1_roles_cut",
                        "B1_body_counters",
                        "P2_pattern_rater_wrong",
                    )
                ]
            )
        ),
        "n_unfair_risk_detected(impact unklar/nein)": len(unfair),
        "n_rater_reported_block_caused": len(blockc),
        "n_unfair_risk_or_rater_block_caused": len(unfair | blockc),
        "n_rater_reported_any_missing_info_incl_deck": len(low),
        "n_any_issue_incl_context_excl_chulane": len(any_block | {e["oracle_id"] for e in low}),
        "n_chulane_text_not_in_block_structural": M["n_cards"],
        "unfair_ids": sorted(unfair),
    }
    (out / "A2_summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for g, r in summary["groups_ranked"]:
        print(f"{r['score']:7.1f} n={r['n']:4d} imp={r['impact']}  {g}: {r['title']}")
    print({k: v for k, v in summary.items() if k.startswith("n_")})


if __name__ == "__main__":
    main()
