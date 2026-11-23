#!/usr/bin/env python3
"""A2: inventory of defects and gaps in the card_block inputs of card rating H (Chulane).

Read-only. Reproducible (no randomness except the fixed hand-sample seed).

  PYTHONPATH=<repo>/src python3 a2_inventory.py --repo <repo> \
      --mage <xmage-checkout> --out <scratchpad>/phaseA

Writes <out>/A2_metrics.json (all counts, examples, per-defect oracle_id lists) and
<out>/A2_hand_sample.txt (the 40 blocks of the hand sample, seed 20261122).
The low-confidence list is written by a2_uncertainty.py.
"""

from __future__ import annotations

import argparse
import collections
import glob
import importlib.util
import json
import random
import re
from pathlib import Path

RUB = "data/research/chulane_rubric_v2_20261118"
HAND_SEED = 20261122
HAND_N = 40

# Evergreen / long-standing keywords a rater is expected to know (exclusion set, stated in the report).
EVERGREEN = {
    "flying",
    "vigilance",
    "trample",
    "haste",
    "reach",
    "deathtouch",
    "lifelink",
    "first strike",
    "double strike",
    "flash",
    "hexproof",
    "indestructible",
    "menace",
    "defender",
    "ward",
    "shroud",
    "protection",
    "equip",
    "enchant",
    "scry",
    "mill",
    "fight",
    "transform",
    "kicker",
    "flashback",
    "cycling",
    "landcycling",
    "plainscycling",
    "islandcycling",
    "forestcycling",
    "swampcycling",
    "mountaincycling",
    "basic landcycling",
    "crew",
    "convoke",
    "surveil",
    "investigate",
    "landfall",
    "fear",
    "intimidate",
    "islandwalk",
    "forestwalk",
    "swampwalk",
    "plainswalk",
    "mountainwalk",
    "landwalk",
    "affinity",
    "delve",
    "cascade",
    "storm",
    "proliferate",
    "regenerate",
    "flanking",
    "shadow",
    "echo",
    "morph",
    "megamorph",
    "persist",
    "undying",
    "evoke",
    "embalm",
    "eternalize",
    "explore",
    "adapt",
    "monstrosity",
    "bestow",
    "suspend",
    "madness",
    "threshold",
    "metalcraft",
    "infect",
    "wither",
    "toxic",
    "partner",
    "manifest",
    "populate",
    "amass",
    "food",
    "treasure",
    "clue",
    "connive",
    "devour",
    "exalted",
    "prowess",
    "rampage",
    "bushido",
    "ninjutsu",
    "channel",
    "imprint",
    "entwine",
    "buyback",
    "replicate",
    "split second",
    "vanishing",
    "fading",
    "cumulative upkeep",
    "phasing",
    "banding",
    "horsemanship",
    "foretell",
    "learn",
}

# predefined tokens whose rules are not in the text unless a reminder follows
PREDEF_TOKENS = [
    "Clue",
    "Food",
    "Treasure",
    "Map",
    "Blood",
    "Gold",
    "Powerstone",
    "Incubator",
    "Junk",
    "Shard",
    "Lander",
    "Role",
    "Walker",
    "Mutagen",
    "Detective",
    "Gnome",
    "Spirit",
    "Copy",
]
PREDEF_TOKENS = [
    "Clue",
    "Food",
    "Treasure",
    "Map",
    "Blood",
    "Gold",
    "Powerstone",
    "Incubator",
    "Junk",
    "Shard",
    "Lander",
]

MECH_SCAN = {  # text-only mechanics that may be absent from the Scryfall keyword list
    "prepared/prepare": r"\bprepared?\b",
    "blight": r"\bblight\b",
    "cloak": r"\bcloak",
    "empower": r"\bempower\b",
    "station": r"\bstation\b",
    "lander token": r"\blander\b",
    "role token": r"\brole token",
    "ki counter (flip)": r"\bki counter",
    "energy": r"\{e\}",
    "experience": r"experience counter",
    "monarch": r"\bmonarch\b",
    "initiative": r"\binitiative\b",
    "day/night": r"\bit becomes (day|night)\b|\bdaybound\b",
    "venture/dungeon": r"\bventure\b|\bdungeon\b",
    "the ring tempts": r"ring tempts",
    "emblem": r"\bemblem\b",
    "loyalty ability": r"^[+−-]?\d+:",  # noqa: RUF001
}


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_rp(repo: Path):
    path = repo / RUB / "scripts" / "render_prompt.py"
    import sys

    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("rp_a2", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def faces_text(f: dict) -> str:
    return "\n".join(x["oracle_text"] for x in f["faces"])


def camel(name: str) -> str:
    return re.sub(
        r"[^A-Za-z0-9]", "", "".join(w[:1].upper() + w[1:] for w in re.split(r"[\s\-]", name))
    )


def mage_back_pt(mage: Path | None, front: str) -> str | None:
    if not mage:
        return None
    p = mage / "Mage.Sets/src/mage/cards" / front[0].lower() / f"{camel(front)}.java"
    if not p.exists():
        return None
    s = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"getRightHalfCard\(\)\.setPT\((\d+),\s*(\d+)\)", s) or re.search(
        r"new CreatureToken\((\d+),\s*(\d+)", s
    )
    return f"{m.group(1)}/{m.group(2)}" if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--mage", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    repo, out = Path(a.repo), Path(a.out)
    mage = Path(a.mage) if a.mage else None
    rub = repo / RUB
    rp = load_rp(repo)
    facts = {r["oracle_id"]: r for r in jl(rub / "data/facts.jsonl")}
    pats = {r["name"]: r for r in jl(rub / "data/patterns.jsonl")}
    xm = json.loads((repo / "data/cards/xmage_card_facts.json").read_text(encoding="utf-8"))[
        "cards"
    ]
    guide_files = sorted(glob.glob(str(rub / "second_run_full_20261122/rater/rr2_guide_*.md"))) + [  # noqa: RUF005
        str(rub / "second_run_20261122/rr_guide_v2_1_rendered.md")
    ]
    guide = (rub / "second_run_full_20261122/rater/rr2_guide_1.md").read_text(encoding="utf-8")
    guide_l = guide.lower()

    # ---------------------------------------------------------------- inputs
    inputs: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for p in sorted(glob.glob(str(rub / "second_run_20261122/rr_input_*.jsonl"))) + sorted(
        glob.glob(str(rub / "second_run_full_20261122/rater/rr2_input_*.jsonl"))
    ):
        for r in jl(Path(p)):
            inputs[r["oracle_id"]].append((Path(p).name, r["card_block"]))
    ids = sorted(inputs)
    N = len(ids)
    M: dict = {"n_cards": N, "input_lines": sum(len(v) for v in inputs.values())}

    # (h) re-render and compare: R1 vs R2 vs today's generator vs F1 (user_prompt)
    rerender_diff = [
        o
        for o in ids
        if any(b != rp.card_block(facts[o], pats.get(facts[o]["name"])) for _, b in inputs[o])
    ]
    dup = [o for o in ids if len(inputs[o]) > 1]
    dup_diff = [o for o in dup if len({b for _, b in inputs[o]}) > 1]
    f1_wrap_diff = [
        o
        for o in ids
        if rp.user_prompt(facts[o], pats.get(facts[o]["name"])).strip()
        != (rp.USER_FIRST_LINE + "\n\n" + inputs[o][0][1]).strip()
    ]
    M["h"] = {
        "rerender_diff": len(rerender_diff),
        "cards_in_two_inputs": len(dup),
        "two_inputs_differ": len(dup_diff),
        "f1_user_prompt_block_differs": len(f1_wrap_diff),
        "facts_ids_equal_input_ids": set(facts) == set(ids),
    }
    block = {o: inputs[o][0][1] for o in ids}

    D: dict[str, dict] = {}

    def add(key: str, o: str, ex: str | None = None) -> None:
        d = D.setdefault(key, {"ids": [], "examples": []})
        if o not in d["ids"]:
            d["ids"].append(o)
            if len(d["examples"]) < 5:
                d["examples"].append(ex or facts[o]["name"])

    layouts = collections.Counter(facts[o]["layout"] for o in ids)
    M["layouts"] = dict(layouts)

    for o in ids:
        f = facts[o]
        b = block[o]
        name = f["name"]
        txt = faces_text(f)
        tl = f["type_line"]
        front_txt = f["faces"][0]["oracle_text"]
        # ---- (a) multi-face
        if len(f["faces"]) > 1:
            add("a_multiface_all", o)
            back = f["faces"][1]
            if "Creature" in back["type_line"] and "Face 2" in b:
                bpt = mage_back_pt(mage, f["faces"][0]["name"])
                add("a_back_face_pt_missing", o, f"{name} (back {bpt or '?'})")
            # keywords / produced mana unioned across faces, no face label
            for kw in f["keywords"]:
                k = kw.lower()
                in_front = k in front_txt.lower()
                in_other = any(k in x["oracle_text"].lower() for x in f["faces"][1:])
                if in_other and not in_front:
                    add("a_keyword_from_other_face_unlabelled", o, f"{name}: {kw}")
            if (
                f["produced_mana"]
                and "add {" not in front_txt.lower()
                and "add " not in front_txt.lower()
            ):
                add(
                    "a_produced_mana_from_other_face_unlabelled", o, f"{name}: {f['produced_mana']}"
                )
            if back["mana_cost"] is None and f["layout"] in ("transform", "flip"):
                pass  # 'no cost' for a back face is correct
        # ---- hybrid double count in cost symbols
        if f["pips_front"]["hybrid_symbols"]:
            add("f_hybrid_pips_double_counted", o, f"{name} {f['mana_cost']}")
        c = f.get("castability") or {}
        if c.get("x_cost"):
            add("f_castability_x_at_zero_not_said", o, f"{name} {f['mana_cost']}")
        if c.get("hybrid_or_phyrexian_left_out"):
            add("f_castability_hybrid_phyrexian_left_out_not_said", o, f"{name} {f['mana_cost']}")
        tlow = txt.lower()
        if (  # noqa: SIM102
            not f["is_land_front"]
            and re.search(
                r"\bconvoke\b|\baffinity\b|\bimprovise\b|\bdelve\b|costs? \{\d+\} less|costs? \{x\} less|"
                r"less to cast|without paying its mana cost|you may pay .* rather than pay|\bemerge\b|"
                r"\bevoke\b|\bdash\b|\bsurge\b|\bmiracle\b|\bmadness\b|\bforetell\b|\bblitz\b|\bprototype\b",
                tlow,
            )
            and (
                " this spell" in tlow
                or "convoke" in tlow
                or "affinity" in tlow
                or "improvise" in tlow
                or "delve" in tlow
                or "rather than pay" in tlow
                or "evoke" in tlow
                or "dash" in tlow
                or "foretell" in tlow
                or "prototype" in tlow
                or "blitz" in tlow
                or "emerge" in tlow
            )
        ):
            if not re.search(r"spells you cast have (improvise|convoke|affinity)", tlow) and not (
                "cascade" in tlow
                and not re.search(
                    r"\bconvoke\b|\baffinity\b|\bimprovise\b|\bdelve\b|costs? \{\d+\} less|rather than pay|\bevoke\b",
                    tlow,
                )
            ):
                add("f_castability_ignores_alt_cost_or_self_reduction", o)
        # ---- body benchmark
        pb = f.get("peer_benchmark") or {}
        if f["is_creature_front"] and "body_same_mv" not in pb:
            add(
                "f_body_benchmark_missing_for_creature",
                o,
                f"{name} P/T {f['power']}/{f['toughness']}",
            )
        if (
            "body_same_mv" in pb
            and re.search(
                r"(this creature|~|it) enters with (a|an|one|two|three|four|five|x|\d+) [^.]*\+1/\+1 counter|^enters with|\benters with (x|\d+|a|an|one|two|three|four|five) \+1/\+1 counters?",
                tlow,
                flags=re.M,
            )
            and "each other" not in tlow
        ):
            add(
                "f_body_benchmark_ignores_etb_counters",
                o,
                f"{name} printed {f['power']}/{f['toughness']}",
            )
        if (
            "body_same_mv" in pb
            and re.search(r"enters with [^.]*-1/-1 counter|enters with .* counters? on it", tlow)
            and "+1/+1" not in tlow
        ):
            add(
                "f_body_benchmark_ignores_etb_counters",
                o,
                f"{name} printed {f['power']}/{f['toughness']}",
            )
        # peer arithmetic invariants
        if pb.get("kind") == "nonland":
            for r in pb["by_role"]:
                d = r["peers_cheaper_equal_dearer"]
                if d["cheaper"] + d["equal"] + d["dearer"] != r["n_peers"] or not (
                    r["p25_mv"] <= r["median_mv"] <= r["p75_mv"]
                ):
                    add("f_peer_arithmetic_inconsistent", o)
            if len(pb["by_role"]) > 3:
                add("f_peer_roles_cut_at_3", o, f"{name}: {len(pb['by_role'])} roles, 3 shown")
            if "body_same_mv" in pb:
                s = pb["body_same_mv"]["peers_smaller_equal_larger"]
                if sum(s.values()) != pb["body_same_mv"]["n_peers"]:
                    add("f_peer_arithmetic_inconsistent", o)
        # roles
        if not f["roles"]:
            add("f_no_role_label", o)
        # castability line present for all spells?
        if not f["is_land_front"] and not f.get("castability"):
            add("f_castability_missing_spell", o)
        # ---- produced mana vs text (front face, nonland and land)
        add_m = re.findall(
            r"add (\{[wubrgc]\}(?: or \{[wubrgc]\})*|one mana of any|[a-z ]*mana of any)",
            front_txt.lower(),
        )
        if add_m and not f["produced_mana"]:
            add("f_produced_mana_empty_but_text_adds", o, name)
        # ---- (d) special permanents
        if "Planeswalker" in tl:
            add(
                "d_planeswalker_loyalty_missing",
                o,
                f"{name} (loyalty {xm.get(name, {}).get('loyalty')})",
            )
        if "Battle" in tl:
            add("d_battle_defense_missing", o)
        if "Spacecraft" in tl:
            add(
                "d_spacecraft_pt_unconditional",
                o,
                f"{name}: block says P/T {f['power']}/{f['toughness']} without 'only at 8+'",
            )
        if "Vehicle" in tl and "crew" not in tlow:
            add("d_vehicle_without_crew", o)
        if "Saga" in tl:
            add("d_saga", o)
        # ---- (b) mechanics
        for kw in f["keywords"]:
            k = kw.lower()
            if k in EVERGREEN:
                continue
            probe = "cycling" if k.endswith("cycling") else k
            lines = [ln for ln in txt.split("\n") if probe in ln.lower()]
            reminder = any("(" in ln for ln in lines)
            ability_word = re.search(rf"\b{re.escape(kw)}\s*—", txt, flags=re.I) is not None
            in_guide = re.search(rf"\b{re.escape(k)}\b", guide_l) is not None
            add(f"b_kw::{kw}", o)
            if ability_word:
                add(f"b_kw_ability_word_selfexplaining::{kw}", o)
            elif not reminder and not in_guide:
                add(f"b_kw_unexplained::{kw}", o)
                add("b_kw_unexplained_any", o, f"{name}: {kw}")
        for lab, rx in MECH_SCAN.items():
            if re.search(rx, txt, flags=re.I | re.M):
                lines = [ln for ln in txt.split("\n") if re.search(rx, ln, flags=re.I)]
                reminder = any("(" in ln for ln in lines)
                add(f"b_scan::{lab}", o)
                if not reminder:
                    add(f"b_scan_noreminder::{lab}", o)
        # ---- (c) references
        parens = re.findall(r"\(([^)]*)\)", txt)
        for tok in PREDEF_TOKENS:
            if re.search(rf"\b{tok}\b(?: tokens?|,| or)", txt) and not re.search(
                r"\b" + tok + r" token named", txt
            ):
                explained = any(
                    re.search(rf"\b{tok}\b", pz) and "artifact" in pz for pz in parens
                ) or bool(re.search(rf"\b{tok} tokens?[^()]{{0,3}}\(It", txt))
                if not explained:
                    add(f"c_token_no_reminder::{tok}", o)
                    add("c_token_no_reminder_any", o, f"{name}: {tok}")
        if re.search(r"\bnamed\b|choose a card name|chosen name|partner with", txt, flags=re.I):
            m = re.search(r"token named ([^.,]+)", txt)  # noqa: F841
            if re.search(
                r"(\d+/\d+ [^.]*tokens? named|tokens? named [^.]*\d+/\d+|\d+/\d+ named)", txt
            ):
                add("c_named_token_defined_inline", o, name)
            elif re.search(r"\bnamed " + re.escape(name.split(" // ")[0]), txt) or re.search(
                r"creatures? named [^.]*" + re.escape(name.split(",")[0]), txt
            ):
                add("c_self_name_reference_ok", o, name)
            else:
                add(
                    "c_named_reference_undefined",
                    o,
                    name
                    + ": "
                    + (
                        re.search(
                            r"[^.\n]*\b(named|card name|partner with)\b[^.\n]*", txt, flags=re.I
                        ).group(0)[:90]
                    ),
                )
        if re.search(
            r"token that's a copy|becomes a copy|enter as a copy|copy of (target|another|a) ", tlow
        ):
            add("c_copy_effect", o)
        if re.search(r"\bemblem\b", tlow):
            add("c_emblem_defined_inline", o)
        # ---- (e) Chulane-dependent: commander references in text
        if re.search(r"\bcommander\b", tlow):
            add("e_text_mentions_commander", o)
        # ---- (g) rulings
        if f["rulings_n"] > rp.RULINGS_SHOWN:
            add("g_rulings_cut_more_than_4", o, f"{name}: {rp.RULINGS_SHOWN} of {f['rulings_n']}")
        shown = sorted(f["rulings"], key=lambda r: (r["published_at"] or "",))[: rp.RULINGS_SHOWN]
        hidden = sorted(f["rulings"], key=lambda r: (r["published_at"] or "",))[rp.RULINGS_SHOWN :]
        if any(len(r["comment"].replace("\n", " ")) > rp.RULING_CHARS for r in shown):
            add("g_ruling_text_truncated_240", o)
        if hidden and shown and len({r["published_at"] for r in shown + hidden}) == 1:
            add("g_rulings_same_date_arbitrary_selection", o)
        if any(
            re.search(r"For more information|mechanics article|see the [^.]* article", r["comment"])
            for r in shown
        ):
            add("g_ruling_empty_article_pointer", o)
        if f["layout"] == "adventure" and "(" not in txt:
            add("b_adventure_rule_unexplained", o, name)
        if any(
            re.search(
                r"comes into play|removed from the game|in play\b|play this ability", r["comment"]
            )
            for r in shown
        ):
            add("g_ruling_obsolete_wording", o)
        if re.search(r"\bprepared?\b", txt, flags=re.I):
            key = "become prepared (including effects that state"
            full_shown = any(
                key in r["comment"] and len(r["comment"]) <= rp.RULING_CHARS for r in shown
            )
            if not full_shown:
                why = (
                    "shown but cut at 240 chars"
                    if any(key in r["comment"] for r in shown)
                    else "hidden (beyond 4)"
                    if any(key in r["comment"] for r in hidden)
                    else "not in data"
                )
                add("g_prepare_definition_ruling_not_shown_in_full", o, f"{name} ({why})")
        # ---- land facts vs text
        if f["is_land_front"] and f.get("land"):
            ld = f["land"]
            ft = front_txt.lower()
            fetch_txt = bool(
                re.search(
                    r"search (your|their) library for [^.]*(land|forest|island|plains|swamp|mountain)",
                    ft,
                )
            )
            if fetch_txt and not ld["fetches_land"]:
                add("f_land_fetch_flag_wrong", o, f"{name}: 'fetches a land: no'")
            if fetch_txt and not ld["wug_colours_produced"]:
                gets = sorted(
                    {
                        c
                        for c, w in (("G", "forest"), ("W", "plains"), ("U", "island"))
                        if w in ft or "basic land" in ft
                    }
                )
                add(
                    "f_land_colours_none_but_fetches",
                    o,
                    f"{name}: 'makes no' (fetchable: {'/'.join(gets) or '-'})",
                )
            if (
                fetch_txt
                and ld["enters_tapped"] == "untapped"
                and "onto the battlefield tapped" in ft
            ):
                add("f_land_untapped_but_fetched_land_tapped", o, name)
        # ---- pattern relevance
        hits0 = (pats.get(name) or {}).get("hits") or {}
        if "etb_own" in hits0 and not f["is_creature_front"]:
            add("f_pattern_etb_own_on_noncreature", o, f"{name} ({f['type_group']})")
        for rid, hl in hits0.items():
            if hl and hl[0]["line"].startswith("roles by text"):
                add("f_pattern_evidence_is_role_label_not_text", o, f"{name}: {rid}")
        # ---- pattern hits: lines quoted vs '~' substitution and length
        hits = (pats.get(name) or {}).get("hits") or {}
        for rid, hl in hits.items():
            if len(hl) > 1:
                add("f_pattern_more_hits_hidden", o, f"{name}: {rid} (+{len(hl) - 1})")

    # ---------------------------------------------------------------- pattern verdicts from raters
    def outs_r2():
        rows = []
        for p in sorted(glob.glob(str(rub / "second_run_20261122/rr_output_*.jsonl"))) + sorted(
            glob.glob(str(rub / "second_run_full_20261122/rater/rr2_output_*.jsonl"))
        ):
            for r in jl(Path(p)):
                r["_src"] = "R2w1" if "rr_output" in p else "R2w2"
                rows.append(r)
        return rows

    r2 = outs_r2()
    f1 = jl(rub / "fullrun_ratings.jsonl")
    for r in f1:
        r["_src"] = "F1"
    pv = collections.defaultdict(collections.Counter)
    bad_pat_cards = collections.defaultdict(set)
    for r in r2 + f1:
        for pc in r.get("pattern_check", []):
            pv[pc["rule_id"]][pc["verdict"]] += 1
            pv[pc["rule_id"]]["_n"] += 1
            if pc["verdict"] in ("wrong", "irrelevant"):
                bad_pat_cards[pc["verdict"]].add(r["oracle_id"])
    M["pattern_verdicts"] = {k: dict(v) for k, v in sorted(pv.items(), key=lambda x: -x[1]["_n"])}
    wrong_any = bad_pat_cards["wrong"]
    irr_any = bad_pat_cards["irrelevant"]
    for o in sorted(wrong_any):
        add("f_pattern_hit_judged_wrong_by_a_rater", o)
    for o in sorted(irr_any):
        add("f_pattern_hit_judged_irrelevant_by_a_rater", o)
    # pattern_check entries missing / extra vs block
    for r in r2 + f1:
        name = facts[r["oracle_id"]]["name"]
        shown = set(((pats.get(name) or {}).get("hits") or {}).keys())
        got = {pc["rule_id"] for pc in r.get("pattern_check", [])}
        if shown != got:
            add("x_rater_pattern_check_mismatch", r["oracle_id"], f"{name} [{r['_src']}]")

    # ---------------------------------------------------------------- (e) Chulane quotes in claims
    chul = " ".join(
        ln[1:].strip()
        for ln in guide.split("The commander (exact Oracle text):")[1].split("\n\n")[1].splitlines()
        if ln.startswith(">")
    )
    norm = lambda s: " ".join(re.sub(r"[^\w{}]+", " ", s.lower()).split())  # noqa: E731
    chul_n = norm(chul)
    e_cards = {"R2": set(), "F1": set()}
    e_claims = collections.Counter()
    for r in r2 + f1:
        bn = norm(block[r["oracle_id"]])
        for cl in r.get("rule_claims", []):
            q = norm(cl.get("quote", ""))
            inter = cl.get("interaction", "")
            if q and q not in bn and q in chul_n:
                e_cards["F1" if r["_src"] == "F1" else "R2"].add(r["oracle_id"])
                e_claims["F1" if r["_src"] == "F1" else "R2"] += 1
            elif inter.startswith("chulane") and not (q and q in bn):
                e_claims[
                    "chulane_interaction_quote_not_in_block_"
                    + ("F1" if r["_src"] == "F1" else "R2")
                ] += 1
    for o in sorted(e_cards["R2"] | e_cards["F1"]):
        add("e_claim_quotes_chulane_text_not_in_block", o)
    M["e"] = {
        "chulane_text_in_guides": {
            Path(g).name: (chul.split("Vigilance.")[1][:40] in Path(g).read_text(encoding="utf-8"))
            for g in guide_files
        },
        "chulane_text_in_any_block": sum(
            "Teller of Tales" in b or "Whenever you cast a creature spell, draw a card, then" in b
            for b in block.values()
        ),
        "cards_with_claim_quoting_chulane_R2": len(e_cards["R2"]),
        "cards_with_claim_quoting_chulane_F1": len(e_cards["F1"]),
        "cards_with_claim_quoting_chulane_union": len(e_cards["R2"] | e_cards["F1"]),
        "claims": dict(e_claims),
        "rater_outputs_R2": len(r2),
        "rater_outputs_F1": len(f1),
    }

    # ---------------------------------------------------------------- hand sample (f)
    rng = random.Random(HAND_SEED)
    sample = rng.sample(ids, HAND_N)
    with open(out / "A2_hand_sample.txt", "w", encoding="utf-8") as fh:
        for i, o in enumerate(sample, 1):
            fh.write(f"##### {i} {facts[o]['name']}\n{block[o]}\n\n")
    M["hand_sample_ids"] = sample

    # ---------------------------------------------------------------- summary
    M["defects"] = {
        k: {"n": len(v["ids"]), "examples": v["examples"], "ids": v["ids"]}
        for k, v in sorted(D.items())
    }
    (out / "A2_metrics.json").write_text(
        json.dumps(M, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for k, v in sorted(D.items(), key=lambda x: -len(x[1]["ids"])):
        print(f"{len(v['ids']):4d}  {k}  | {'; '.join(v['examples'][:3])[:150]}")
    print(
        json.dumps(
            {k: M[k] for k in ("n_cards", "input_lines", "h", "layouts", "e")},
            indent=1,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
