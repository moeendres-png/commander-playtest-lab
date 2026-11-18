#!/usr/bin/env python3
"""Single source of the rubric v2 anchors. Writes anchors.json and anchors.md (the anchor block
of GUIDE_v2.md) and checks the anchors against the pool and the pilot sample.

  python3 build_anchors.py --facts out/facts.jsonl --pilot out/pilot_sample.json --out out/

Anchor kinds:
  v1_fixed      the ten v1 anchors that are in the pool. Fixed by the v1 guide: E F T R x 25 (0..4
                -> 0..100), H = (H - 1) / 9 * 100 (the Studio's own transform of the rubric value).
                They are pilot cards (stratum A): the prompt builder removes the card that is being
                rated from its own anchor block (leave-one-anchor-out).
  v1_consensus  non-pilot pool cards whose v1 criterion means (3 raters) are rounded to a multiple
                of 5 on the same scale. Soft anchors for the levels the ten fixed anchors do not
                cover. Checked with --ratings: the SD of the three v1 ratings on the anchored
                criterion is at most 0.6 (v1 units: 0 to 4 for E F T R, 1 to 10 for H), and the
                anchor value is within 3 points of the v1 mean on the new scale.
  v2_proposal   new anchors for criteria that v1 did not have (K, D) or for levels v1 left empty.
                A proposal of the design draft; the Owner confirms or replaces them.
Checks: every anchor card is in the pool; no non-v1_fixed anchor is in the pilot sample.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

V1 = "v1_fixed"
CONS = "v1_consensus"
PROP = "v2_proposal"


def a(card: str, value: int, kind: str, why: str) -> dict:
    return {"card": card, "value": value, "kind": kind, "why": why}


SPELL = {
    "E": [
        a("Divine Favor", 10, CONS, "2 mana Aura: 3 life and +1/+3; clearly overcosted"),
        a("Grizzly Bears", 25, CONS, "vanilla 2/2 for 2; below the format's average for its job"),
        a("Reclamation Sage", 50, CONS, "3 mana 2/1 with a conditional ETB; fair price"),
        a("Fellwar Stone", 50, CONS, "2 mana rock whose colours depend on opponents' lands; fair"),
        a("Cultivate", 50, V1, "v1 fixed (E 2)"),
        a("Kor Skyfisher", 75, CONS, "2 mana 2/3 flier with a bounce ETB; better than most"),
        a("Mind Stone", 75, CONS, "2 mana rock that cashes in for a card later"),
        a("Counterspell", 75, V1, "v1 fixed (E 3)"),
        a("Farseek", 75, V1, "v1 fixed (E 3)"),
        a("Path to Exile", 100, CONS, "1 mana unconditional creature exile"),
        a("Arcane Signet", 100, CONS, "2 mana rock, any colour of the identity, no drawback"),
        a("Sol Ring", 100, V1, "v1 fixed (E 4)"),
        a("Swords to Plowshares", 100, V1, "v1 fixed (E 4)"),
        a("Llanowar Elves", 100, V1, "v1 fixed (E 4)"),
    ],
    "F": [
        a("Winds of Rath", 0, CONS, "destroys all own creatures: works against the plan"),
        a("Pacifism", 25, CONS, "creature-slot removal; no link to cast triggers, lands or bounce"),
        a("Counterspell", 25, V1, "v1 fixed (F 1)"),
        a("Path to Exile", 50, CONS, "good in any deck, nothing special here"),
        a("Arcane Signet", 50, CONS, "good in any deck, nothing special here"),
        a("Sol Ring", 50, V1, "v1 fixed (F 2)"),
        a("Swords to Plowshares", 50, V1, "v1 fixed (F 2)"),
        a("Farseek", 50, V1, "v1 fixed (F 2)"),
        a("Cultivate", 50, V1, "v1 fixed (F 2)"),
        a(
            "Elvish Mystic",
            75,
            CONS,
            "1 mana creature: casting it triggers Chulane, it ramps, it can be replayed",
        ),
        a("Llanowar Elves", 75, V1, "v1 fixed (F 3)"),
        a(
            "Shrieking Drake",
            100,
            CONS,
            "1 mana creature whose ETB bounces an own creature: replays ETBs, re-triggers Chulane",
        ),
        a(
            "Tireless Provisioner",
            100,
            CONS,
            "creature, landfall engine, extra land drops pay off twice",
        ),
    ],
    "T": [
        a("Grizzly Bears", 0, CONS, "no effect on any opponent"),
        a("Elvish Mystic", 25, CONS, "only you, small"),
        a("Sol Ring", 25, V1, "v1 fixed (T 1)"),
        a("Llanowar Elves", 25, V1, "v1 fixed (T 1)"),
        a("Farseek", 25, V1, "v1 fixed (T 1)"),
        a("Cultivate", 25, V1, "v1 fixed (T 1)"),
        a("Path to Exile", 50, CONS, "flexible answer to any one opponent's threat"),
        a("Pacifism", 50, CONS, "answers one opponent's creature"),
        a("Swords to Plowshares", 50, V1, "v1 fixed (T 2)"),
        a("Counterspell", 50, V1, "v1 fixed (T 2)"),
        a("Hornet Queen", 75, CONS, "a board that deters attacks from all three opponents"),
        a(
            "Koma, Cosmos Serpent",
            90,
            CONS,
            "uncounterable, makes a threat every upkeep, answers anything; no pool card reaches 100 on T",
        ),
    ],
    "R": [
        a("Mechanized Production", 0, CONS, "dead without a very specific artifact setup"),
        a("Giant Growth", 25, CONS, "situational combat trick"),
        a("Gilded Lotus", 50, CONS, "5 mana rock: usually useful, but late and slow"),
        a(
            "Kor Skyfisher",
            75,
            CONS,
            "useful in almost every game state; needs a permanent to return",
        ),
        a("Counterspell", 75, V1, "v1 fixed (R 3)"),
        a("Farseek", 75, V1, "v1 fixed (R 3)"),
        a("Cultivate", 75, V1, "v1 fixed (R 3)"),
        a("Llanowar Elves", 75, V1, "v1 fixed (R 3)"),
        a("Arcane Signet", 100, CONS, "never a bad draw"),
        a("Path to Exile", 100, CONS, "never a bad draw"),
        a("Sol Ring", 100, V1, "v1 fixed (R 4)"),
        a("Swords to Plowshares", 100, V1, "v1 fixed (R 4)"),
    ],
    "K": [
        a("Storm Crow", 0, PROP, "no repeatable part, no loop, no combo link"),
        a("Path to Exile", 25, PROP, "one-shot effect, nothing to repeat"),
        a(
            "Mistmeadow Council",
            50,
            PROP,
            "own ETB (draw): can repeat through Chulane's {3},{T} bounce, but at a high price per loop",
        ),
        a(
            "Tireless Provisioner",
            75,
            PROP,
            "repeatable value engine: every land drop (Chulane gives extra ones) pays out",
        ),
        a(
            "Primeval Bounty",
            75,
            PROP,
            "every creature spell, so every Chulane replay, pays out again",
        ),
        a(
            "Shrieking Drake",
            100,
            PROP,
            "1 mana self-bounce: with another ETB creature it re-casts and re-triggers Chulane for almost nothing",
        ),
    ],
    "D": [
        a("Winds of Rath", 0, PROP, "destroys the own creature engine; Wrath-style, symmetric"),
        a(
            "Rites of Flourishing",
            25,
            PROP,
            "symmetric: every opponent draws and lands as much as you",
        ),
        a("Rampaging Baloths", 50, PROP, "6 mana, GG, Wrath-exposed, but leaves tokens behind"),
        a(
            "Elvish Mystic",
            75,
            PROP,
            "dies to every sweeper but costs 1 and is replaceable; one pip",
        ),
        a(
            "Arcane Signet",
            100,
            PROP,
            "no Wrath exposure, no symmetry, no self-damage, no colour strain",
        ),
    ],
    "H": [
        a("Storm Crow", 0, CONS, "v1 H 1.0 (spread 0): does not belong in the deck"),
        a("Gilded Lotus", 25, CONS, "v1 H 3.3: slow, expensive, special builds"),
        a("Negate", 30, CONS, "v1 H 3.7: narrow counter"),
        a("Cultivate", 44, V1, "v1 fixed (H 5)"),
        a("Reality Shift", 50, CONS, "v1 H 5.7: playable, 2 mana exile with a drawback"),
        a("Farseek", 56, V1, "v1 fixed (H 6)"),
        a("Kor Skyfisher", 65, CONS, "v1 H 6.7: good, played in most strong lists"),
        a("Counterspell", 67, V1, "v1 fixed (H 7)"),
        a("Avacyn's Pilgrim", 75, CONS, "v1 H 7.7: excellent"),
        a("Llanowar Elves", 78, V1, "v1 fixed (H 8)"),
        a("Tatyova, Benthic Druid", 80, CONS, "v1 H 8.3: excellent, a landfall draw engine"),
        a("Path to Exile", 85, CONS, "v1 H 8.7: nearly always played"),
        a("Swords to Plowshares", 89, V1, "v1 fixed (H 9)"),
        a("Sol Ring", 100, V1, "v1 fixed (H 10)"),
    ],
}

LAND = {
    "E": [
        a("Maze's End", 0, CONS, "tapped, colourless, a Gate tutor with a high price"),
        a("Reliquary Tower", 10, CONS, "colourless, no effect worth a slot"),
        a("Sungrass Prairie", 25, CONS, "needs {1} each time it taps for mana; a filter"),
        a("Selesnya Guildgate", 25, V1, "v1 fixed (E 1)"),
        a("Tranquil Cove", 35, CONS, "tapped dual with 1 life"),
        a("Adarkar Wastes", 50, CONS, "untapped dual with 1 damage per colour tap"),
        a("Evolving Wilds", 50, V1, "v1 fixed (E 2)"),
        a("Prairie Stream", 75, CONS, "check land: untapped early with two basics"),
        a("Azorius Chancery", 75, CONS, "bounce land: two mana for one land card"),
        a("Simic Growth Chamber", 75, V1, "v1 fixed (E 3)"),
        a("Command Tower", 100, V1, "v1 fixed (E 4)"),
    ],
    "F": [
        a("Maze's End", 15, CONS, "no link to the plan"),
        a("Selesnya Guildgate", 25, V1, "v1 fixed (F 1)"),
        a("Tranquil Cove", 35, CONS, "no link to the plan"),
        a("Adarkar Wastes", 40, CONS, "no link to the plan; colours only"),
        a("Command Tower", 50, V1, "v1 fixed (F 2)"),
        a("Prairie Stream", 50, CONS, "good in any deck"),
        a(
            "Evolving Wilds",
            75,
            V1,
            "v1 fixed (F 3): puts a land onto the battlefield, a landfall trigger",
        ),
        a(
            "Azorius Chancery",
            100,
            CONS,
            "returns a land to the hand: a second land drop per turn cycle, landfall twice",
        ),
        a("Simic Growth Chamber", 100, V1, "v1 fixed (F 4)"),
    ],
    "R": [
        a("Maze's End", 35, CONS, "tapped and colourless"),
        a("Reliquary Tower", 50, CONS, "colourless: hurts WUG costs"),
        a("Sungrass Prairie", 50, CONS, "needs {1} to make coloured mana"),
        a("Selesnya Guildgate", 75, V1, "v1 fixed (R 3)"),
        a("Azorius Chancery", 75, CONS, "tapped, and needs another land to bounce"),
        a("Evolving Wilds", 75, V1, "v1 fixed (R 3)"),
        a("Simic Growth Chamber", 75, V1, "v1 fixed (R 3)"),
        a("Adarkar Wastes", 90, CONS, "untapped, two colours"),
        a("Prairie Stream", 100, CONS, "two colours, untapped from turn 3"),
        a("Command Tower", 100, V1, "v1 fixed (R 4)"),
    ],
    "D": [
        a("Maze's End", 25, PROP, "tapped, colourless, and a bounce cost in the effect"),
        a("Reliquary Tower", 50, PROP, "colourless land strains a three-colour mana base"),
        a("Tranquil Cove", 50, PROP, "enters tapped"),
        a(
            "Azorius Chancery",
            50,
            PROP,
            "tapped and loses a land drop's tempo if no land to bounce",
        ),
        a("Adarkar Wastes", 75, PROP, "1 damage per coloured tap"),
        a(
            "Prairie Stream",
            90,
            PROP,
            "small risk of entering tapped early; no pool land without any cost is outside the pilot",
        ),
    ],
    "H": [
        a("Maze's End", 0, CONS, "v1 H 1.0"),
        a("Cryptic Caves", 10, CONS, "v1 H 2.0: colourless, cashes in for a card late"),
        a("Selesnya Guildgate", 22, V1, "v1 fixed (H 3)"),
        a("Tranquil Cove", 25, CONS, "v1 H 3.3"),
        a("Evolving Wilds", 44, V1, "v1 fixed (H 5)"),
        a("Temple of Plenty", 45, CONS, "v1 H 5.0: tapped, scry 1"),
        a("Prairie Stream", 60, CONS, "v1 H 6.3"),
        a("Azorius Chancery", 75, CONS, "v1 H 7.7"),
        a("Simic Growth Chamber", 78, V1, "v1 fixed (H 8)"),
        a("Command Tower", 100, V1, "v1 fixed (H 10)"),
    ],
}

NAMES = {"E": "E efficiency", "F": "F Chulane synergy", "T": "T table impact", "R": "R reliability",
         "K": "K engine and combo potential", "D": "D low deck cost (100 = no risk)", "H": "H holistic"}  # fmt: skip


def anchor_block(anchors: dict, leave_out: str | None = None, heading: str = "Spells") -> str:
    """Markdown of the anchor tables. ``leave_out``: a card that is being rated is removed from its
    own anchor rows (leave-one-anchor-out) and the block says so."""
    out = [f"#### {heading}"]
    for crit in ("E", "F", "T", "R", "K", "D", "H"):
        rows = anchors.get(crit)
        if not rows:
            continue
        out.append(f"\n**{NAMES[crit]}**\n\n| value | anchor cards (source) |\n|---|---|")
        levels: dict[int, list[dict]] = {}
        for r in rows:
            if leave_out and r["card"] == leave_out:
                continue
            levels.setdefault(r["value"], []).append(r)
        for value in sorted(levels):
            cells = "; ".join(
                f"{r['card']} (v1 fixed)"
                if r["kind"] == V1
                else f"{r['card']} ({'v1 mean' if r['kind'] == CONS else 'proposal'}): {r['why']}"
                for r in levels[value]
            )
            # v2.1: every shown value is a multiple of 5 (the pilot raters copied 44/67/78 style H anchors);
            # the exact v1 value stays in anchors.json and is what the evaluation compares against
            shown = int(5 * round(value / 5))
            out.append(f"| {shown} | {cells} |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True)
    ap.add_argument("--pilot", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--ratings",
        help="v1 ratings.csv; checks the spread and the value of every v1_consensus anchor",
    )
    args = ap.parse_args()
    pool = {
        json.loads(x)["name"] for x in Path(args.facts).read_text(encoding="utf-8").splitlines()
    }
    pilot = {
        c["name"]: c for c in json.loads(Path(args.pilot).read_text(encoding="utf-8"))["cards"]
    }
    v1_anchor_pilot = {n for n, c in pilot.items() if c["stratum"] == "A"}
    problems = []
    for group, table in (("spell", SPELL), ("land", LAND)):
        for crit, rows in table.items():
            for r in rows:
                if r["card"] not in pool:
                    problems.append(f"{group}/{crit}: {r['card']} not in the pool")
                if r["value"] % 5 and r["kind"] != V1 and r["kind"] != CONS:
                    problems.append(
                        f"{group}/{crit}: {r['card']} value {r['value']} not a multiple of 5"
                    )
                if r["kind"] != V1 and r["card"] in pilot:
                    problems.append(
                        f"{group}/{crit}: {r['card']} ({r['kind']}) is in the pilot sample"
                    )
                if r["kind"] == V1 and r["card"] not in v1_anchor_pilot:
                    problems.append(
                        f"{group}/{crit}: v1 anchor {r['card']} is not a stratum A pilot card"
                    )
            for lvl in (0, 25, 50, 75, 100):
                if (
                    crit not in ("T",)
                    and not any(abs(r["value"] - lvl) <= 12 for r in rows)
                    and group == "spell"
                ):
                    problems.append(f"{group}/{crit}: no anchor near level {lvl}")
    if args.ratings:
        import csv
        import statistics

        v1 = {}
        with Path(args.ratings).open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                for c in "EFTRH":
                    v1.setdefault((r["card"], c), []).append(int(r[c]))
        for group, table in (("spell", SPELL), ("land", LAND)):
            for crit, rows in table.items():
                for r in rows:
                    if r["kind"] != CONS or crit not in "EFTRH":
                        continue
                    vals = v1.get((r["card"], crit))
                    if not vals or len(vals) < 3:
                        problems.append(f"{group}/{crit}: {r['card']} has no 3 v1 ratings")
                        continue
                    sd = statistics.stdev(vals)
                    mean = sum(vals) / len(vals)
                    conv = (mean - 1) / 9 * 100 if crit == "H" else mean * 25
                    if sd > 0.6:
                        problems.append(f"{group}/{crit}: {r['card']} v1 spread {sd:.2f} above 0.6")
                    if abs(conv - r["value"]) > 3.01:
                        problems.append(
                            f"{group}/{crit}: {r['card']} value {r['value']} is {conv:.1f} on the v1 mean"
                        )
    if problems:
        raise SystemExit("anchor check failed:\n  " + "\n  ".join(problems))
    out = Path(args.out)
    (out / "anchors.json").write_text(
        json.dumps(
            {"schema": "rubric-v2-anchors-1", "spell": SPELL, "land": LAND},
            indent=1,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    md = (
        anchor_block(SPELL, None, "Spells")
        + "\n"
        + anchor_block(LAND, None, "Lands (judge a land as a land)")
    )
    (out / "anchors.md").write_text(md, encoding="utf-8")
    guide = out / "GUIDE_v2.md"
    if guide.exists():
        text = guide.read_text(encoding="utf-8")
        region = text.partition("<!-- ANCHORS:BEGIN -->\n")[2].partition("<!-- ANCHORS:END -->")[0]
        if region.strip() != md.strip():
            raise SystemExit(
                "GUIDE_v2.md anchor region differs from anchors.md: rebuild the guide block"
            )
    print(
        "anchors ok:", {k: len(v) for k, v in SPELL.items()}, {k: len(v) for k, v in LAND.items()}
    )


if __name__ == "__main__":
    main()
