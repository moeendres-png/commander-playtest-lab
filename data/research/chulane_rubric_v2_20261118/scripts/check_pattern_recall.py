"""Recall scan of the pattern rules: lists cards whose text lines look like a pattern but that no
matching rule hit. Usage: PYTHONPATH=<checkout>/src python3 check_pattern_recall.py [group ...]
(reads ../data/facts.jsonl and ../data/patterns.jsonl). A listing is a to-do list
for the rule author, not a metric."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_patterns as ep

D = Path(__file__).resolve().parent.parent / "data"
facts = [json.loads(ln) for ln in (D / "facts.jsonl").open()]
pats = {json.loads(ln)["oracle_id"]: json.loads(ln) for ln in (D / "patterns.jsonl").open()}


def lines(c):
    out = []
    for f in c["faces"]:
        for ln in ep.normalise_lines(f):
            out.append(ln)
    return out


chk = {
    "bounce_missed": (
        lambda ln: (
            "return" in ln
            and re.search(r"owner'?s'? hands?|owners' hands", ln)
            and not re.search(r"from (?:your|a|the|any|their) graveyard", ln)
        ),
        ["bounce_own_creature", "bounce_any_creature_target", "bounce_self"],
    ),
    "blink_missed": (
        lambda ln: "exile" in ln and "return" in ln and "to the battlefield" in ln,
        ["blink_own"],
    ),
    "etb_missed": (
        lambda ln: (
            re.match(r"^(?:[a-z\' -]{3,24} — )?(?:when|whenever)", ln)
            and re.search(r"\benters\b", ln.split(", ")[0])
        ),
        ["etb_own", "landfall", "etb_other_creature", "etb_other_permanent"],
    ),
    "cast_missed": (
        lambda ln: re.match(r"^(?:[a-z\' -]{3,24} — )?(?:when|whenever) you cast", ln),
        ["cast_trigger_creature", "cast_trigger_any_spell"],
    ),
    "cost_missed": (
        lambda ln: (
            re.search(r"\bcosts? (?:up to )?\{\w+\} less", ln) and not ln.startswith("~ costs")
        ),
        [
            "cost_reduction_creature",
            "cost_reduction_any_spell",
            "cost_reduction_typed_spell",
            "self_cost_reduction",
        ],
    ),
    "landdrop_missed": (
        lambda ln: re.search(
            r"additional land|land cards? from your hand|play lands|lands? from (?:your|the) (?:top|library|graveyard)",
            ln,
        ),
        ["land_extra_drop_or_from_hand"],
    ),
    "wipe_missed": (
        lambda ln: re.search(
            r"all creatures|each creature|all (?:non\w+ )?permanents|each player sacrifices", ln
        ),
        ["wipe_symmetric", "wipe_one_sided", "edict_symmetric"],
    ),
}
which = sys.argv[1:] or list(chk)
for k in which:
    f, rules = chk[k]
    n = 0
    print("###", k)
    for c in facts:
        p = pats[c["oracle_id"]]
        if any(r in p["rule_ids"] for r in rules):
            continue
        for ln in lines(c):
            if f(ln):
                n += 1
                print("  ", c["name"], "|", ln[:170])
                break
    print("  total", n)
