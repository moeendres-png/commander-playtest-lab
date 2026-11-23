#!/usr/bin/env python3
"""A2: classify the rater uncertainty texts (R2 = wave 1 + wave 2 of the second run, F1 = full run)
and write the list of cards rated low/medium because information was missing.

  python3 a2_uncertainty.py --repo <repo> --out <scratchpad>/phaseA

Writes <out>/A2_low_confidence_cards.jsonl (one line per oracle_id), <out>/A2_uncertainty_stats.json
and <out>/A2_uncertainty_precision_sample.txt (30 tagged texts, seed 7, for the hand check).
Tags are regex based (precision measured by hand on the sample, see report).
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import random
import re
from pathlib import Path

RUB = "data/research/chulane_rubric_v2_20261118"

TAGS = {
    # missing information that the BLOCK could carry (block-caused)
    "mechanic_unexplained": r"unfamiliar|new to me|not familiar|do not (fully )?understand|don't (fully )?understand|(do not|don't) (fully )?know (the|this|how the|what|exactly)|"
    r"i do not know (this|what)|beyond the text|rely (only )?on the reminder|what being \w+ gives|"
    r"exact (rules|timing)|how (cloak|goad|prepare|empower|station|blight)",
    "rules_corner_not_in_rulings": r"not (stated |shown )?in the (shown )?rulings|not in the (text or )?rulings|not (in|shown in) (the )?(block|text)|"
    r"rules corner|rules question|rules point|not in the card block|not shown in the card block|not settled|trigger order|not stated|"
    r"inferred|according to the card text[^.]*not from a shown ruling|block does not (settle|say)",
    "token_or_reference_undefined": r"\b(jace|lander|clue|food|treasure|role|incubator|map) token|token'?s? (abilities|text)|"
    r"emblem|card named|named card|other cards? of the (listed )?combination",
    "combo_partners_not_shown": r"combination|combo (hint|line)|other pieces|listed line|line(s)? with chulane",
    "benchmark_or_castability_mismatch": r"benchmark|peer|on-time|on time figure|castability|land-drop figure|turn three|"
    r"counts it as|printed",
    "other_face_or_layout": r"back face|other face|second face|transform|adventure|prepare spell|front face|flipped side",
    "rulings_cut_off": r"rulings? (shown )?(are |is )?(cut|truncated)|cut off|truncated|only \d+ of \d+ rulings",
    "mana_base_not_visible": r"mana base|forest type|island type|plains type|basic land types?|colou?rless (mana )?sources?|"
    r"\{c\}|sources of|land types?|how many (forests|islands|plains|lands with)",
    # context gap (guide/deck, not the card block)
    "deck_list_not_visible": r"(deck|list)(\'s)? [^.]*(not visible|cannot see|can't see|unknown|i assume|assumed)|"
    r"how many [^.]*(deck|list)|assume[ds]? (the )?(deck|list|described deck)|"
    r"(not visible|cannot see|can't see)[^.]*(deck|list)|in the deck is (not visible|unknown)|"
    r"build decision|final list|deck (holds|runs|has|plays)",
    # not missing information
    "pod_or_game_dependent": r"\bpod\b|opponents?|table|metagame|depends on the game|game state|how often|judgement|estimate",
}
BLOCK_CAUSED = [
    "mechanic_unexplained",
    "rules_corner_not_in_rulings",
    "token_or_reference_undefined",
    "combo_partners_not_shown",
    "benchmark_or_castability_mismatch",
    "other_face_or_layout",
    "rulings_cut_off",
]
CONTEXT = ["deck_list_not_visible", "mana_base_not_visible"]
MISSING = BLOCK_CAUSED + CONTEXT


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def tag(text: str) -> list[str]:
    t = text.lower()
    return [k for k, rx in TAGS.items() if re.search(rx, t)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rub = Path(a.repo) / RUB
    out = Path(a.out)
    rows = []
    for p in sorted(glob.glob(str(rub / "second_run_20261122/rr_output_*.jsonl"))):
        for r in jl(Path(p)):
            rows.append(("R2w1:" + Path(p).stem.split("_")[-1], r))
    for p in sorted(glob.glob(str(rub / "second_run_full_20261122/rater/rr2_output_*.jsonl"))):
        for r in jl(Path(p)):
            rows.append(("R2w2:" + Path(p).stem.split("_")[-1], r))
    for r in jl(rub / "fullrun_ratings.jsonl"):
        rows.append(("F1", r))

    per: dict[str, dict] = {}
    cnt = collections.Counter()
    cnt_card = collections.defaultdict(set)
    conf = collections.Counter()
    tagged_texts = []
    for src, r in rows:
        conf[(src.split(":")[0], r["confidence"])] += 1
        if r["confidence"] == "high":
            continue
        tags = tag(r.get("uncertainty", ""))
        tagged_texts.append((src, r["card"], r["confidence"], r.get("uncertainty", ""), tags))
        for t in tags:
            cnt[(src.split(":")[0][:2], t)] += 1
            cnt_card[t].add(r["oracle_id"])
        miss = [t for t in tags if t in MISSING]
        if not miss:
            continue
        e = per.setdefault(
            r["oracle_id"], {"oracle_id": r["oracle_id"], "card": r["card"], "ratings": []}
        )
        e["ratings"].append(
            {
                "src": src,
                "confidence": r["confidence"],
                "tags": tags,
                "uncertainty": r.get("uncertainty", ""),
            }
        )
    lines = []
    for o, e in sorted(per.items(), key=lambda x: x[1]["card"]):  # noqa: B007
        tags = sorted({t for rr in e["ratings"] for t in rr["tags"] if t in MISSING})
        e["missing_info_tags"] = tags
        e["block_caused"] = any(t in BLOCK_CAUSED for t in tags)
        e["only_context"] = all(t in CONTEXT for t in tags)
        e["any_low"] = any(rr["confidence"] == "low" for rr in e["ratings"])
        lines.append(json.dumps(e, ensure_ascii=False))
    (out / "A2_low_confidence_cards.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    all_cards_lowmed = {r["oracle_id"] for _, r in rows if r["confidence"] != "high"}
    stats = {
        "confidence_counts": {f"{k[0]}:{k[1]}": v for k, v in sorted(conf.items())},
        "cards_with_any_low_or_medium": len(all_cards_lowmed),
        "cards_listed_missing_info": len(per),
        "cards_block_caused": sum(1 for e in per.values() if e["block_caused"]),
        "cards_only_context(deck list/mana base)": sum(
            1 for e in per.values() if e["only_context"]
        ),
        "tag_counts_ratings": {f"{k[0]}:{k[1]}": v for k, v in sorted(cnt.items())},
        "tag_counts_cards": {
            k: len(v) for k, v in sorted(cnt_card.items(), key=lambda x: -len(x[1]))
        },
        "low_ratings": [
            {"src": s, "card": c, "uncertainty": u, "tags": t}
            for s, c, cf, u, t in tagged_texts
            if cf == "low"
        ],
        "untagged_lowmed": sum(1 for x in tagged_texts if not x[4]),
    }
    # F1 vs R2 per card: same block, confidence agreement
    f1c = {r["oracle_id"]: r["confidence"] for s, r in rows if s == "F1"}
    r2c = collections.defaultdict(list)
    for s, r in rows:
        if s != "F1":
            r2c[r["oracle_id"]].append(r["confidence"])
    pair = collections.Counter()
    for o, l in r2c.items():  # noqa: E741
        pair[(f1c[o], l[0])] += 1
    stats["F1_vs_R2_confidence_pairs(first R2 rating)"] = {
        f"F1={a}/R2={b}": v for (a, b), v in sorted(pair.items())
    }
    bc_tags = {
        o: {t for rr in e["ratings"] for t in rr["tags"] if t in BLOCK_CAUSED and rr["src"] == "F1"}
        for o, e in per.items()
    }
    bc_tags_r2 = {
        o: {t for rr in e["ratings"] for t in rr["tags"] if t in BLOCK_CAUSED and rr["src"] != "F1"}
        for o, e in per.items()
    }
    both = [o for o in per if bc_tags[o] and bc_tags_r2[o]]
    stats["block_caused_in_F1_and_R2_same_card"] = len(both)
    stats["block_caused_F1_only"] = sum(1 for o in per if bc_tags[o] and not bc_tags_r2[o])
    stats["block_caused_R2_only"] = sum(1 for o in per if bc_tags_r2[o] and not bc_tags[o])
    (out / "A2_uncertainty_stats.json").write_text(
        json.dumps(stats, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    rng = random.Random(7)
    smp = rng.sample([x for x in tagged_texts if x[4]], 30)
    with open(out / "A2_uncertainty_precision_sample.txt", "w", encoding="utf-8") as fh:
        for i, (s, c, cf, u, t) in enumerate(smp, 1):
            fh.write(f"{i} [{s}] {c} ({cf}) tags={t}\n   {u}\n")
    print(
        json.dumps(
            {k: v for k, v in stats.items() if k != "low_ratings"}, indent=1, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
