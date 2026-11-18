#!/usr/bin/env python3
"""Renders the batch prompts of the pilot runs (7 cards per call, own random order per rater).

  python3 make_batches.py --out <dir> [--run v2|v2.1]

Writes <dir>/batches[21]/<batch>.md and <dir>/batches[21]_manifest.json. Run v2 (raters H1, H2,
S1, S2) is the whole pilot plus 8 retest cards per rater; run v2.1 (raters T1, T2) is the targeted
re-measurement of the 10 anchors, the 8 retest cards and one more card, in batches of 6.
The card ids c00 to c62 follow the card order of pilot_sample.json. Nothing from the usage
holdout is read.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import render_prompt as rp

ROOT = Path(__file__).resolve().parent.parent
EXTRA_V21_CARD = "Tam's Resistance"
HEAD = (
    "\n\n# CARDS TO RATE (BATCH)\n\nBelow are several cards. Rate EACH card independently, as if "
    "you saw it alone: do not compare cards with each other and do not calibrate one card against "
    "another in this batch, only against the anchors and the guide. Write ONE JSON object per "
    "card (schema as in the output rules); put all objects, in the order given, in ONE JSON array "
    "in the output file.\n\n"
)


class LeaveOut:
    """Stand-in for the card names left out of the anchor tables (leave-one-anchor-out)."""

    def __init__(self, names: list[str]) -> None:
        self.names = set(names)

    def __bool__(self) -> bool:
        return bool(self.names)

    def __eq__(self, other: object) -> bool:
        return other in self.names


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--run", default="v2", choices=("v2", "v2.1"))
    args = ap.parse_args()
    v21 = args.run == "v2.1"
    out = Path(args.out)
    batch_dir = out / ("batches21" if v21 else "batches")
    batch_dir.mkdir(parents=True, exist_ok=True)

    guide = (ROOT / "GUIDE_v2.md").read_text(encoding="utf-8")
    anchors = json.loads((ROOT / "anchors.json").read_text(encoding="utf-8"))
    anchor_names = {
        a["card"]
        for table in (anchors["spell"], anchors["land"])
        for rows in table.values()
        for a in rows
        if a["kind"] == "v1_fixed"
    }
    pilot = json.loads((ROOT / "pilot_sample.json").read_text(encoding="utf-8"))
    name_of = {f"c{i:02d}": c["name"] for i, c in enumerate(pilot["cards"])}
    id_of = {name: cid for cid, name in name_of.items()}
    retest = [id_of[n] for n in pilot["retest_cards"]]
    facts = {r["name"]: r for r in rp.load_jsonl(ROOT / "data" / "facts.jsonl")}
    pats = {r["name"]: r for r in rp.load_jsonl(ROOT / "data" / "patterns.jsonl")}

    def system_prompt(names: list[str]) -> str:
        left_out = [n for n in names if n in anchor_names]
        return rp.system_prompt(guide, anchors, LeaveOut(left_out) if left_out else None)

    plan: list[tuple[str, list[str], bool]] = []  # (batch id, card ids, retest)
    if v21:
        chosen = set(retest)
        chosen |= {id_of[c["name"]] for c in pilot["cards"] if c["v1_is_anchor"]}
        chosen.add(id_of[EXTRA_V21_CARD])
        ids = sorted(chosen)
        for rater in ("T1", "T2"):
            order = ids[:]
            random.Random(f"1118-{rater}").shuffle(order)
            for i in range(0, len(order), 6):
                plan.append((f"{rater}_b{i // 6:02d}", order[i : i + 6], False))
    else:
        ids = list(name_of)
        for rater in ("H1", "H2", "S1", "S2"):
            order = ids[:]
            random.Random(f"1118-{rater}").shuffle(order)
            chunks = [order[i : i + 7] for i in range(0, len(order), 7)] + [retest]
            for bi, chunk in enumerate(chunks):
                last = bi == len(chunks) - 1
                plan.append((f"{rater}_b{bi:02d}{'_retest' if last else ''}", chunk, last))

    manifest = []
    for batch, chunk, is_retest in plan:
        names = [name_of[c] for c in chunk]
        body = system_prompt(names) + HEAD
        for k, name in enumerate(names, 1):
            card = rp.user_prompt(facts[name], pats.get(name)).strip()
            body += f"## Card {k} of {len(names)}\n\n{card}\n\n"
        (batch_dir / f"{batch}.md").write_text(body, encoding="utf-8")
        manifest.append(
            {"batch": batch, "rater": batch.split("_")[0], "cards": names, "retest": is_retest}
        )
    name = "batches21_manifest.json" if v21 else "batches_manifest.json"
    (out / name).write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(len(manifest), "batches")


if __name__ == "__main__":
    main()
