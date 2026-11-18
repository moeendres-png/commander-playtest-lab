#!/usr/bin/env python3
"""Stratified pilot sample (about 60 cards) for the rubric v2 calibration (see calibration_plan.md).

Strata (all counts n of 922 pool cards, seed fixed; the draw is a pure function of the inputs):
  A  anchors      the 10 v1 anchors that are in the pool (fixed v1 H)
  B  reference    20 cards of the reference deck chulane-current@41f393530bb16ee9 (not anchors)
  C  used         15 tier-D cards with usage > 0, not in the reference deck
  D  zero         15 cards without usage
  E  coverage     up to 4 extra cards so that >= 2 multi-face cards and >= 1 Game Changer are in

Inside B, C, D the quota is spread over buckets (land, mana, creature with own ETB, other creature,
non-creature spell) so no bucket is empty; D also takes cards that carry a positive Chulane pattern
and vanilla creatures. A final coverage check lists lands, vanilla creatures and multi-face cards.

  PYTHONPATH=<checkout>/src python3 make_pilot_sample.py --store <copy> --repo <checkout> \
      --facts out/facts.jsonl --patterns out/patterns.jsonl --usage out/usage_holdout.jsonl \
      --out out/pilot_sample.json [--seed 1118]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

COMMANDER = "Chulane, Teller of Tales"
MANA_ROLES = {"mana_dork", "mana_rock", "ramp", "land_ramp"}
POSITIVE_RULES = {
    "bounce_own_creature", "bounce_any_creature_target", "bounce_own_land", "blink_own",
    "cast_trigger_creature", "cast_creature_draw", "land_extra_drop_or_from_hand", "landfall",
    "etb_other_creature", "etb_own_draw", "mana_creature_cheap", "bounce_self",
    "land_onto_battlefield_effect",
}  # fmt: skip

QUOTA = {
    "B": {"land": 3, "mana": 4, "creature_etb": 5, "creature_other": 3, "noncreature": 5},
    "C": {"land": 3, "mana": 2, "creature_etb": 3, "creature_other": 3, "noncreature": 4},
    "D": {"land": 1, "mana": 1, "creature_etb": 3, "creature_other": 5, "noncreature": 5},
}


def bucket(f: dict, p: dict) -> str:
    if f["is_land_front"]:
        return "land"
    roles = {r["role"] for r in f["roles"]}
    if roles & MANA_ROLES and (
        f["is_creature_front"] or f["type_group"] in ("Artifact", "Sorcery", "Instant")
    ):
        return "mana"
    if f["is_creature_front"]:
        return "creature_etb" if "etb_own" in p["rule_ids"] else "creature_other"
    return "noncreature"


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("store", "repo", "facts", "patterns", "usage", "out"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--seed", type=int, default=1118)
    args = ap.parse_args()
    sys.path.insert(0, str(Path(args.repo) / "src"))
    from commander_lab.studio import strength, strength_view
    from commander_lab.studio.store import StudioStore

    load = lambda p: [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines()]  # noqa: E731
    facts = {r["name"]: r for r in load(args.facts)}
    pats = {r["name"]: r for r in load(args.patterns)}
    usage = {r["name"]: r for r in load(args.usage)}
    res = strength_view.compute(
        StudioStore.open(Path(args.store)), COMMANDER, strength.StrengthSettings()
    )
    tier = {c["name"]: c["tier"] for c in res["cards"]}

    chosen: dict[str, dict] = {}
    rng = random.Random(args.seed)

    def add(name: str, stratum: str, why: str) -> None:
        if name not in chosen:
            chosen[name] = {"name": name, "oracle_id": facts[name]["oracle_id"], "stratum": stratum,
                            "bucket": bucket(facts[name], pats[name]), "why": why}  # fmt: skip

    anchors = sorted(n for n, u in usage.items() if u["v1"]["anchor"])
    for n in anchors:
        add(
            n,
            "A",
            "v1 anchor in the pool (fixed v1 value; checks that v2 reproduces the order of the anchors)",
        )

    def pick(stratum: str, names: list[str], why: str) -> None:
        by_bucket: dict[str, list[str]] = defaultdict(list)
        for n in sorted(names):
            if n not in chosen:
                by_bucket[bucket(facts[n], pats[n])].append(n)
        for b, quota in QUOTA[stratum].items():
            pool = by_bucket.get(b, [])
            rng.shuffle(pool)
            for n in pool[:quota]:
                add(n, stratum, f"{why}; bucket {b}")

    ref = [n for n, u in usage.items() if u["in_reference_deck"] and n not in chosen]
    pick("B", ref, "reference deck card")

    used_d = [
        n
        for n, u in usage.items()
        if tier.get(n) == "D" and u["deck_list_count"] > 0 and not u["in_reference_deck"]
    ]
    # tier-D lands with the fewest source decks first: they test the land anchors with little usage
    low_lands = sorted(
        (n for n in used_d if facts[n]["is_land_front"]),
        key=lambda n: (usage[n]["deck_list_count"], n),
    )[:3]
    for n in low_lands:
        add(
            n,
            "C",
            "stratum C land (lower tier band); bucket land",
        )
    pick(
        "C",
        [n for n in used_d if n not in low_lands and not facts[n]["is_land_front"]],
        "stratum C (lower tier band, not in the reference deck)",
    )

    zero = [n for n, u in usage.items() if u["deck_list_count"] == 0]
    zero_lands = sorted(n for n in zero if facts[n]["is_land_front"])
    for n in zero_lands[:1]:
        add(n, "D", "stratum D land; bucket land")
    # positive Chulane patterns hidden among the zero-usage cards: test whether the rater finds them
    hidden = sorted(
        n
        for n in zero
        if set(pats[n]["rule_ids"]) & POSITIVE_RULES and not facts[n]["is_land_front"]
    )
    rng.shuffle(hidden)
    for n in hidden[:5]:
        add(
            n,
            "D",
            "stratum D; carries a positive Chulane pattern ("
            + ", ".join(sorted(set(pats[n]["rule_ids"]) & POSITIVE_RULES))
            + ")",
        )
    vanilla = sorted(n for n in zero if not facts[n]["has_oracle_text"])
    rng.shuffle(vanilla)
    for n in vanilla[:2]:
        add(n, "D", "stratum D; creature without rules text (vanilla)")
    rest = [n for n in zero if n not in chosen and not (set(pats[n]["rule_ids"]) & POSITIVE_RULES)]
    rng.shuffle(rest)
    for n in rest:
        if sum(1 for c in chosen.values() if c["stratum"] == "D") >= 15:
            break
        add(n, "D", "stratum D; no positive pattern (plain)")

    # Coverage extras (stratum E, at most 4 cards beyond the 60): at least 2 multi-face cards (the
    # pool has 12) and at least 1 Game Changer (Bracket 3 allows at most three)
    multi_have = [n for n in chosen if len(facts[n]["faces"]) > 1]
    spare_multi = sorted(n for n in facts if len(facts[n]["faces"]) > 1 and n not in chosen)
    rng.shuffle(spare_multi)
    for n in spare_multi[: max(0, 2 - len(multi_have))]:
        add(n, "E", "coverage: multi-face card (" + facts[n]["layout"] + ")")
    if not any(facts[n]["game_changer"] for n in chosen):
        gcs = sorted(n for n in facts if facts[n]["game_changer"] and n not in chosen)
        rng.shuffle(gcs)
        for n in gcs[:2]:
            add(n, "E", "coverage: Game Changer (Bracket 3 limit)")
    # Coverage: multi-face cards (the pool has 12); make sure at least 2 are in the sample
    multi = [n for n in chosen if len(facts[n]["faces"]) > 1]
    sample = sorted(chosen.values(), key=lambda c: (c["stratum"], c["name"]))
    cov = {
        "n_cards": len(sample),
        "by_stratum": dict(Counter(c["stratum"] for c in sample)),
        "by_bucket": dict(Counter(c["bucket"] for c in sample)),
        "lands": sum(facts[c["name"]]["is_land_front"] for c in sample),
        "vanilla_creatures": sum((not facts[c["name"]]["has_oracle_text"]) for c in sample),
        "multi_face": sorted(multi),
        "with_own_etb": sum("etb_own" in pats[c["name"]]["rule_ids"] for c in sample),
        "game_changers": sorted(c["name"] for c in sample if facts[c["name"]]["game_changer"]),
    }
    for c in sample:
        u = usage[c["name"]]
        c["v1_H_mean"] = u["v1"]["H_mean"]
        c["v1_is_anchor"] = u["v1"]["anchor"]
    # Test-retest cards (drift): 2 per stratum A, B, C, D, fixed here before any rating exists
    rr = random.Random(f"{args.seed}:retest")
    retest = []
    for st in "ABCD":
        names = sorted(c["name"] for c in sample if c["stratum"] == st)
        retest += rr.sample(names, 2)
    out = {
        "schema": "rubric-v2-pilot-sample-1",
        "retest_cards": sorted(retest),
        "seed": args.seed,
        "RATER_VISIBLE": False,
        "note": "v1 values are for calibration only. No usage counts are stored here, but strata C and D separate cards with usage (C, tier D) from cards without usage (D) as a category. Raters never see this file: the rater prompt gets the card id and nothing else of this file. usage_holdout.jsonl is local and never checked in.",
        "reference_deck": "chulane-current@41f393530bb16ee9",
        "v1_reference_rule": "v1 H_mean (summary.csv) is the reference for Spearman except for the 10 anchors, whose v1 H is fixed by the guide and therefore not an independent rating",
        "quota": QUOTA,
        "coverage": cov,
        "cards": sample,
    }
    Path(args.out).write_text(
        json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(cov, sort_keys=True))


if __name__ == "__main__":
    main()
