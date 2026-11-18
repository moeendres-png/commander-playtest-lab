#!/usr/bin/env python3
"""Rule-based Chulane patterns for the rubric v2 (design draft, see patterns_spec.md).

Reads ``facts.jsonl`` (from ``extract_facts.py``) and writes

  patterns.jsonl         per Oracle id: the rules that hold, each with its evidence text
  pattern_summary.json   hits per rule over the pool (n of 922), split lands / creatures / others
  pattern_sample.json    (with --sample N) N random hits per rule, for the manual precision check

Usage:  PYTHONPATH=<checkout>/src python3 extract_patterns.py --facts <out>/facts.jsonl \
            --out <out> [--usage-holdout <out>/usage_holdout.jsonl] [--sample 20 --seed 1118]

The rules read the Oracle text only (reminder text removed, lower case, card name and "this
creature" replaced by "~"). A hit is a HINT with the matching line as evidence, never a verdict;
the rater keeps the judgement. Rules are versioned: any change of a regular expression or of a
rule's scope raises PATTERN_RULES_VERSION.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

PATTERN_RULES_VERSION = "chulane-patterns-1"

SELF_NOUN = r"(?:creature|permanent|artifact|enchantment|land|planeswalker|vehicle|equipment|aura|saga|class|battle|spell|token|card)"
TRIGGER = r"^(?:when|whenever|at the beginning)\b"
OPP_QUAL = r"(?:you don't control|an opponent controls|your opponents control|opponents control|target opponent controls|target player controls|each opponent controls|defending player controls)"
DRAW_EFFECT = r"\byou (?:may )?draw (?:a|an|one|two|three|that many|x|\w+) cards?\b|\bdraws? (?:a|an|one|two|three|that many|x|\w+) cards?\b|\bdraw cards\b|\byou may draw\b"
ADD_MANA = r"\badd\b[^.\n]*\{[wubrgc0-9x]"


@dataclass(frozen=True)
class Rule:
    id: str
    group: str
    description: str
    kind: str  # "positive" | "anti" | "info"


RULES: list[Rule] = [
    Rule(
        "etb_own",
        "etb",
        "Own enter-the-battlefield trigger of a permanent (When ~ enters ...; also '~ or another X enters'), apart from landfall; Auras, lands and non-creatures count (field creature in the summary).",
        "positive",
    ),
    Rule("etb_own_draw", "etb", "Own ETB trigger whose effect draws cards.", "positive"),
    Rule(
        "etb_other_creature",
        "etb",
        "Trigger of ANOTHER permanent when a creature enters (Whenever another creature you control enters ...).",
        "positive",
    ),
    Rule(
        "etb_other_permanent",
        "etb",
        "Trigger when another permanent that is not literally 'creature' or 'land' enters (token, artifact, Gate, a creature subtype such as 'a spider'); may include creatures.",
        "info",
    ),
    Rule(
        "landfall",
        "land",
        "Landfall: ability word or trigger when a land enters (own, or any player's); includes landfall conditions on spells.",
        "positive",
    ),
    Rule(
        "land_extra_drop_or_from_hand",
        "land",
        "Additional land drop, or puts a land card from the hand onto the battlefield.",
        "positive",
    ),
    Rule(
        "land_onto_battlefield_effect",
        "land",
        "Searches for a land and puts it onto the battlefield, or puts a land from a graveyard onto it (lands that enter without a land drop).",
        "positive",
    ),
    Rule(
        "bounce_own_creature",
        "bounce",
        "Returns a creature or permanent YOU control (chosen or each; a creature among the legal choices) to its owner's hand.",
        "positive",
    ),
    Rule(
        "bounce_any_creature_target",
        "bounce",
        "Returns a target creature or permanent to its owner's hand without limiting it to opponents (own creature can be chosen, rule text only).",
        "positive",
    ),
    Rule(
        "bounce_own_land",
        "bounce",
        "Returns a land you control to its owner's hand (bounce land; the land can be played again).",
        "positive",
    ),
    Rule(
        "bounce_own_other_permanent",
        "bounce",
        "Returns an artifact or enchantment you control to its owner's hand (not a creature).",
        "info",
    ),
    Rule(
        "bounce_mass_includes_own",
        "bounce",
        "Returns all (nonland) permanents or all creatures to their owners' hands, own included.",
        "info",
    ),
    Rule("bounce_self", "bounce", "Returns ITSELF to its owner's hand.", "positive"),
    Rule(
        "blink_own",
        "bounce",
        "Exiles a creature or permanent (you control, or any target; field scope) or itself and returns it to the battlefield (flicker); a land target counts as blink of a land.",
        "positive",
    ),
    Rule(
        "cast_trigger_creature",
        "cast",
        "Trigger on casting a creature spell (Whenever you cast a creature spell ...).",
        "positive",
    ),
    Rule(
        "cast_trigger_any_spell",
        "cast",
        "Trigger on casting any spell (unrestricted), which includes creature spells.",
        "positive",
    ),
    Rule(
        "cast_trigger_other_type",
        "cast",
        "Trigger on casting a restricted kind of spell (instant/sorcery, artifact, a tribe, mana value restriction ...): does not fire on every creature spell.",
        "info",
    ),
    Rule(
        "cast_creature_draw",
        "cast",
        "Cast trigger on a creature spell (or any spell) whose effect draws a card.",
        "positive",
    ),
    Rule(
        "mana_creature_cheap",
        "mana",
        "Creature with mana value at most 2 that adds mana (or untaps a land for mana).",
        "positive",
    ),
    Rule(
        "mana_creature_other",
        "mana",
        "Creature with mana value 3 or more that adds mana (or untaps a land for mana).",
        "positive",
    ),
    Rule("cost_reduction_creature", "cost", "Creature spells you cast cost less.", "positive"),
    Rule("cost_reduction_any_spell", "cost", "All spells you cast cost less.", "positive"),
    Rule(
        "cost_reduction_typed_spell",
        "cost",
        "A type or subtype of spells other than creatures costs less (instant/sorcery, a tribe).",
        "info",
    ),
    Rule(
        "self_cost_reduction",
        "cost",
        "The card makes itself cheaper (convoke, delve, affinity, improvise, this spell costs less).",
        "info",
    ),
    Rule(
        "etb_doubler",
        "engine",
        "Makes triggers of permanents entering trigger an additional time.",
        "positive",
    ),
    Rule("untapper", "engine", "Untaps permanents (can untap Chulane or mana sources).", "info"),
    Rule(
        "noncreature_draw_or_ramp",
        "anti",
        "Non-creature, non-land card that draws or ramps: it does not trigger Chulane (neutral to weak anti-synergy, not a penalty by itself).",
        "anti",
    ),
    Rule(
        "wipe_symmetric",
        "anti",
        "Destroys, exiles or shrinks all creatures (or all permanents) with no opponent restriction: hits the own creatures.",
        "anti",
    ),
    Rule(
        "wipe_one_sided",
        "anti",
        "Mass removal restricted to opponents' creatures (spares the own).",
        "info",
    ),
    Rule("edict_symmetric", "anti", "Each player sacrifices creatures: the own too.", "anti"),
    Rule(
        "symmetric_benefit",
        "anti",
        "Gives each player a benefit (draw, land, mana, life ...): opponents profit equally.",
        "anti",
    ),
    Rule(
        "self_life_loss",
        "anti",
        "Costs the controller life or deals damage to the controller.",
        "anti",
    ),
    Rule(
        "creature_dependent",
        "anti",
        "Needs creatures to do anything (Aura, Equipment, anthem, 'for each creature you control').",
        "anti",
    ),
]
RULE_IDS = [r.id for r in RULES]


_LEAK_KEYS = re.compile(
    r"edhrec|deck_list|decklist|rubric|h_mean|times_brought|playgroup|inclusion|price|usage|popular|v1",
    re.I,
)


def _assert_no_leak(obj) -> None:
    """Leak guard: no key of a pattern record may name usage, popularity, price or a v1 rating."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _LEAK_KEYS.search(str(k)):
                raise SystemExit(f"leak guard: key {k!r} looks like usage, popularity, price or v1")
            _assert_no_leak(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_leak(v)


def strip_reminder(text: str) -> str:
    """Parenthesised reminder text removed, nested pairs included (same logic as roles.py)."""
    pat = re.compile(r"\([^()]*\)")
    while True:
        new = pat.sub(" ", text)
        if new == text:
            return new
        text = new


def self_names(face_name: str) -> list[str]:
    names = {face_name.lower()}
    for sep in (",", " of ", " the "):
        if sep in face_name:
            names.add(face_name.split(sep)[0].lower().strip())
    return sorted((n for n in names if len(n) >= 3), key=len, reverse=True)


def normalise_lines(face: dict) -> list[str]:
    """Lines of the face text: reminder text removed, lower case, own name and 'this creature'
    replaced by '~', ability-word prefix ('Landfall — ') kept in the line."""
    text = strip_reminder(face["oracle_text"] or "").lower()
    for n in self_names(face["name"]):
        text = re.sub(rf"(?<![\w'-]){re.escape(n)}(?![\w'-])", "~", text)
    text = re.sub(rf"\bthis {SELF_NOUN}\b", "~", text)
    lines = []
    for raw in text.split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            lines.append(line)
    return lines


def cause_and_effect(line: str) -> tuple[str, str] | None:
    """For a triggered line: (cause clause, effect). An ability-word prefix is cut first."""
    body = re.sub(r"^[a-z'~ -]{3,30} — (?=(?:when|whenever|at the beginning))", "", line)
    if not re.match(TRIGGER, body):
        return None
    head, sep, rest = body.partition(", ")
    return (head, rest) if sep else (body, "")


def is_permanent_face(face: dict) -> bool:
    types = (face["type_line"] or "").split("—")[0]
    return not ("Instant" in types or "Sorcery" in types)


def snippet(line: str, n: int = 220) -> str:
    return line if len(line) <= n else line[: n - 1] + "…"


def scan_face(card: dict, face: dict, face_index: int) -> dict[str, list[dict]]:
    hits: dict[str, list[dict]] = defaultdict(list)
    lines = normalise_lines(face)
    permanent = is_permanent_face(face)
    is_creature_face = "Creature" in (face["type_line"] or "").split("—")[0]
    mv = card["mana_value"] or 0
    sentences: list[tuple[str, str]] = []  # (sentence, line)

    def hit(rule: str, line: str, **extra) -> None:
        d = {"face": face_index, "line": snippet(line)}
        d.update(extra)
        if d not in hits[rule]:
            hits[rule].append(d)

    for line in lines:
        for s in re.split(r"(?<=[.])\s+", line):
            sentences.append((s.strip(), line))
        if line.startswith("landfall") and "whenever" not in line:
            hit("landfall", line, scope="own", form="spell_condition")
        ce = cause_and_effect(line)
        if ce:
            cause, effect = ce
            # ---- ETB / landfall ----
            enters = re.search(r"\benters\b", cause)
            if enters:
                own_subject = re.match(
                    r"^(?:when|whenever) ~ enters(?: the battlefield)?(?: untapped)?(?:$|\s+(?:or|and)\s)",
                    cause,
                ) or re.match(
                    r"^(?:when|whenever) ~ enters(?: the battlefield)?(?: untapped)?$", cause
                )
                own_or_other = re.match(r"^(?:when|whenever) ~ or another [^,]* enters\b", cause)
                landfall_cause = re.search(
                    r"\b(?:an?|another) (?:nonbasic |basic )?land(?: you control)? enters\b|\blands? (?:you control )?enters?\b|\bland enters under your control\b",
                    cause,
                )
                if landfall_cause and not re.search(OPP_QUAL, cause):
                    scope = (
                        "own"
                        if ("you control" in cause or "under your control" in cause)
                        else "any"
                    )
                    hit("landfall", line, scope=scope)
                elif line.startswith("landfall") and "enters" in cause:
                    hit("landfall", line, scope="own")
                elif own_or_other and permanent:
                    hit("etb_own", line, shared_with_other=True)
                    hit(
                        "etb_other_creature"
                        if re.search(r"\bcreature\b", cause)
                        else "etb_other_permanent",
                        line,
                    )
                elif own_subject and permanent:
                    hit("etb_own", line)
                    if re.search(DRAW_EFFECT, effect) and not re.search(
                        r"\b(?:target )?(?:opponent|each opponent|that player|target player)s? draws?\b",
                        effect,
                    ):
                        hit("etb_own_draw", line)
                elif re.search(r"\bcreatures?\b", cause) and "~ enters" not in cause.replace(
                    "~ or another", ""
                ):
                    hit("etb_other_creature", line)
                elif (
                    re.search(
                        r"\byou control enters\b|\bunder your control\b|\b(?:token|artifact|enchantment|permanent|gate|equipment|aura|vehicle|treasure|clue)\b",
                        cause,
                    )
                    and "~ enters" not in cause
                ):
                    hit("etb_other_permanent", line)
                elif re.match(r"^(?:when|whenever) ~ or another", cause) and "creature" in cause:
                    hit("etb_other_creature", line)
            # ---- cast triggers ----
            if re.match(r"^(?:when|whenever) you cast\b", cause):
                clause = cause.replace("noncreature", "")
                kind = None
                if re.search(
                    r"\bcreature\b[^,]*?\bspells?\b|\bcreature spells?\b", clause
                ) and not re.search(r"\bspells? with\b[^,]*\bcreature\b", clause):
                    kind = "creature"
                    hit("cast_trigger_creature", line)
                elif re.match(
                    r"^(?:when|whenever) you cast (?:a|an|your first) spell(?: each turn| from your hand)?$",
                    cause,
                ):
                    kind = "any"
                    hit("cast_trigger_any_spell", line)
                if (
                    kind is None
                    and "~" not in cause.replace("targets ~", "")
                    and not re.search(r"you cast ~", cause)
                ):
                    hit("cast_trigger_other_type", line)
                if (
                    kind
                    and re.search(DRAW_EFFECT, effect)
                    and not re.search(
                        r"\b(?:opponent|each opponent|that player|target player)s? draws?\b", effect
                    )
                ):
                    hit("cast_creature_draw", line, trigger=kind)

    # ---- sentence-level rules (any ability line) ----
    for s, line in sentences:
        s_nogr = s
        # land drops
        if re.search(
            r"play (?:up to )?(?:one|two|three|an?) additional lands?|additional lands? (?:on each of your turns|each turn|this turn)|put (?:up to )?(?:a|one|two|three|that many) lands? cards? from your hand onto the battlefield|you may put a land card from your hand|put a land card from your hand onto the battlefield",
            s_nogr,
        ):
            hit(
                "land_extra_drop_or_from_hand",
                line,
                symmetric=bool(re.search(r"each player|all players|players may", s_nogr)),
            )
        if re.search(
            r"search your library for [^.]*\blands?\b[^.]*(?:onto|on) the battlefield|put (?:target )?(?:a )?land card[^.]*from (?:your|a|the) graveyard onto the battlefield|put (?:a|up to \w+) lands? cards? onto the battlefield",
            s_nogr,
        ):
            hit("land_onto_battlefield_effect", line)
        # bounce
        gy = re.search(r"from (?:your|a|the|any|their) graveyard|card from", s_nogr)
        if not gy and re.search(r"owner'?s'? hands?|owners' hands", s_nogr) and "return" in s_nogr:
            if re.search(OPP_QUAL, s_nogr) and "you control" not in s_nogr.replace(
                "you don't control", ""
            ):
                pass
            elif re.search(
                r"\breturn (?:a|an|another|target|each) (?:other )?(?:tapped |untapped |basic )?lands? you control\b[^.]*to (?:its|their) owners?'?s?'? hands?",
                s_nogr,
            ):
                hit("bounce_own_land", line)
            elif re.search(
                r"\breturn (?:a|an|another|target) (?:[a-z-]+ ){0,2}?(?:artifacts?|enchantments?) you control\b[^.]*to (?:its|their) owners?'?s?'? hands?",
                s_nogr,
            ):
                hit("bounce_own_other_permanent", line)
            elif re.search(
                r"\breturn (?:another |a |an |up to (?:one|two|three|x) |each |all )?(?:other )?(?:target )?(?:[a-z-]+ ){0,3}?(?:creatures?|permanents?)(?: with [^.]*?)? you control\b[^.]*?to (?:its|their) owners?'?s?'? hands?",
                s_nogr,
            ) or re.search(
                r"\breturn (?:another |a |an |each |all )?(?:other )?(?:target )?creatures? you control to (?:its|their) owner",
                s_nogr,
            ):
                hit("bounce_own_creature", line)
            elif (
                re.search(
                    r"\breturn (?:another |up to (?:one|two|three|x) |(?:two|three|four|five|six|x) )?(?:other )?(?:target )?(?:nonland |non\w+ )?(?:creatures?|permanents?)(?: or [a-z]+)? to (?:its|their) owners?'?s?'? hands?",
                    s_nogr,
                )
                and not re.search(OPP_QUAL, s_nogr)
            ) or (
                re.search(r"\breturn those creatures to their owners' hands", s_nogr)
                and re.search(r"\btarget creatures\b", line)
            ):
                hit("bounce_any_creature_target", line)
            elif re.search(
                r"\breturn (?:all|each) (?:other )?(?:nonland )?(?:creatures|permanents)\b[^.]*to (?:its|their) owners?'?s?'? hands?",
                s_nogr,
            ) and not re.search(r"target player controls|target opponent controls", s_nogr):
                hit("bounce_mass_includes_own", line)
        if (
            not gy
            and re.search(r"\breturn ~ to (?:its owner's|your) hand", s_nogr)
            and not re.search(
                r"\bdies\b|is put into a graveyard|leaves the battlefield|is destroyed",
                s_nogr.split("return ~")[0],
            )
        ):
            hit("bounce_self", line)
        # cost reduction
        m = re.search(
            r"((?:[a-z, -]+ )?spells?)(?: you cast(?: of the chosen type)?)? (?:cost|costs) (?:up to )?\{\w+\}(?: or \{\w+\})? less",
            s_nogr,
        )
        if m and not s_nogr.startswith("~ costs") and not s_nogr.startswith("this spell"):
            subj = m.group(1).strip()
            if "creature" in subj and "noncreature" not in subj:
                hit("cost_reduction_creature", line, subject=subj)
            elif "of the chosen type" not in s_nogr and (
                subj in ("spells", "spell")
                or subj.startswith("spells you cast")
                or re.match(r"^(?:each )?spells?$", subj)
            ):
                hit("cost_reduction_any_spell", line, subject=subj)
            else:
                hit("cost_reduction_typed_spell", line, subject=subj)
        if re.search(
            r"^~ costs? (?:up to )?\{\w+\} less to cast|^this spell costs|costs? \{\w+\} less to cast for each|costs? \{\w+\} less to cast if",
            s_nogr,
        ):
            hit("self_cost_reduction", line)
        # engine
        if re.search(
            r"trigger(?:s)? an additional time|triggers? (?:one )?additional time|additional time",
            s_nogr,
        ) and re.search(r"enter|dies|abilit", s_nogr):
            hit("etb_doubler", line)
        if (
            re.search(
                r"\buntap (?:target|all|each|up to|another|that|those|it|a |an |two|three)", s_nogr
            )
            and "~ doesn't untap" not in s_nogr
            and "doesn't untap" not in s_nogr
            and "don't untap" not in s_nogr
        ):
            hit("untapper", line)
        # anti
        subj_opp = re.search(OPP_QUAL, s_nogr)
        if re.search(
            r"(?:destroy|exile) all (?:non\w+ )?(?:creatures|permanents|nonland permanents|artifacts, creatures)|all creatures get -[\dx]+/-[1-9x]|each creature gets -[\dx]+/-[1-9x]|deals? [\dx]+ damage to each creature(?! (?:with|without|that|of|you don't|your opp|target))|destroy each creature|destroys? all creatures",
            s_nogr,
        ) or (
            re.search(r"(?:creatures|all creatures) (?:get|gets) -[\dx]+/-[1-9x]", s_nogr)
            and "you control get" not in s_nogr
        ):
            if subj_opp or re.search(r"creatures? (?:you don't|your opponents)", s_nogr):
                hit("wipe_one_sided", line)
            else:
                hit("wipe_symmetric", line)
        if (
            re.search(
                r"(?:creatures|creature) (?:your opponents|opponents|target player|target opponent|each opponent)\b[^.]*(?:control|controls)[^.]*(?:get|gets) -[\dx]+/-[1-9x]",
                s_nogr,
            )
            or re.search(
                r"(?:destroy|exile) all creatures (?:you don't control|your opponents control|target (?:player|opponent) controls)",
                s_nogr,
            )
            or re.search(
                r"deals? \d+ damage to each creature (?:you don't control|your opponents control|target opponent controls)",
                s_nogr,
            )
        ):
            hit("wipe_one_sided", line)
        if re.search(
            r"each player sacrifices (?:a|an|all|each|x|\w+) (?:\w+ )?creatures?|all players sacrifice|sacrifice all creatures",
            s_nogr,
        ):
            hit("edict_symmetric", line)
        if re.search(
            r"\beach player (?:may )?(?:draws?|searches|puts?|creates?|gains?|untaps?|scrys?|adds?|plays?|reveals)|\ball players (?:may )?(?:draw|search|gain)|each player may (?:put|play|search|draw)",
            s_nogr,
        ) and not re.search(r"\beach opponent\b", s_nogr[:0]):
            hit("symmetric_benefit", line)
        if re.search(
            r"\byou lose (?:\d+|x|half|that much|an amount)\b[^.]*life|\bpay (?:\d+|x|half your) life|~ deals? (?:\d+|x|that much) damage to you\b|you lose life equal",
            s_nogr,
        ) and not re.search(
            r"\b(?:target opponent|each opponent|that player|target player) loses",
            s_nogr[: s_nogr.find("you lose")] if "you lose" in s_nogr else "",
        ):
            hit("self_life_loss", line)
        if re.search(
            r"\bcreatures you control (?:get|gets|have|has|gain|gains|can)\b|\bequipped creature\b|\benchanted creature (?:gets|get) \+|\bfor each creature you control\b|\bnumber of creatures you control\b|\bwhere x is the number of creatures\b",
            s_nogr,
        ):
            hit("creature_dependent", line)

    # ---- blink (line level: the exile and the return can be two sentences) ----
    for line in lines:
        if (
            re.search(r"\bexile\b", line)
            and re.search(
                r"\breturn (?:it|that card|them|those cards|the exiled cards?|~)(?=[\s,])[^.]*\bto the battlefield\b",
                line,
            )
            and not re.search(r"graveyard|leaves the battlefield|dies", line)
            and not re.search(OPP_QUAL, line.replace("you don't control", "x"))
        ):
            own = re.search(r"\byou control\b|exile ~", line)
            anyt = (
                re.search(
                    r"exile (?:another |up to \w+ |x |\w+ )?(?:other )?(?:target )?(?:creatures?|permanents?|nonland permanents?)",
                    line,
                )
                and "target" in line
            )
            if own or anyt:
                kind = (
                    "land"
                    if re.search(r"(?:target|another) land", line)
                    else "creature_or_permanent"
                )
                hit("blink_own", line, scope="own" if own else "any", target=kind)
    # ---- mana creature: an activated or tap ability that adds mana (any cost), or untaps a land ----
    if is_creature_face:
        for line in lines:
            if re.match(r"^(?:when|whenever|at the beginning)\b", line):
                continue
            if re.search(
                r"^[^:]{0,40}\{t\}[^:]{0,40}: .*\badd\b[^.]*\{|^[^:]{0,40}\{t\}[^:]{0,40}: add (?:one|two|three|x|\{)|\{t\}: untap target (?:\w+ )?(?:land|forest|island|plains|swamp|mountain)",
                line,
            ):
                hit(
                    "mana_creature_cheap" if mv <= 2 else "mana_creature_other", line, mana_value=mv
                )
                break
    return hits


def scan_card(card: dict) -> dict:
    hits: dict[str, list[dict]] = defaultdict(list)
    for i, face in enumerate(card["faces"]):
        for rule, lst in scan_face(card, face, i).items():
            for h in lst:
                if h not in hits[rule]:
                    hits[rule].append(h)
    # anti: non-creature, non-land cards that draw or ramp (uses the Studio's own role rules)
    front = card["faces"][0]
    if not card["is_creature_front"] and not card["is_land_front"] and card["has_oracle_text"]:
        from commander_lab.studio import roles  # imported late: needs PYTHONPATH=<checkout>/src

        found = roles.classify_oracle_roles(front["type_line"] or "", front["oracle_text"] or "")
        flagged = [
            r for r in found if r in ("card_draw", "card_advantage", "cantrip", "ramp", "land_ramp")
        ]
        if flagged:
            hits["noncreature_draw_or_ramp"].append(
                {
                    "face": 0,
                    "line": f"roles by text: {', '.join(flagged)}",
                    "type_line": front["type_line"],
                }
            )
    # keywords of the cards (not text lines)
    kw = {k.lower() for k in card.get("keywords", [])}
    if (
        kw & {"convoke", "delve", "affinity", "improvise", "emerge", "undaunted"}
        and "self_cost_reduction" not in hits
    ):
        hits["self_cost_reduction"].append(
            {
                "face": 0,
                "line": "keyword: "
                + ", ".join(
                    sorted(
                        kw & {"convoke", "delve", "affinity", "improvise", "emerge", "undaunted"}
                    )
                ),
            }
        )
    # Equipment depends on creatures even without a text line that says so
    tl = front["type_line"] or ""
    if "Equipment" in tl and "creature_dependent" not in hits:
        hits["creature_dependent"].append({"face": 0, "line": f"type line: {tl}"})
    return dict(hits)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--usage-holdout", default=None, help="only to count hits among cards with 0 source decks"
    )
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1118)
    args = ap.parse_args()

    cards = [json.loads(line) for line in Path(args.facts).read_text(encoding="utf-8").splitlines()]
    zero: set[str] = set()
    if args.usage_holdout:
        for line in Path(args.usage_holdout).read_text(encoding="utf-8").splitlines():
            u = json.loads(line)
            if u["deck_list_count"] == 0:
                zero.add(u["oracle_id"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    per_rule: dict[str, list[dict]] = defaultdict(list)
    with (out / "patterns.jsonl").open("w", encoding="utf-8") as fh:
        for card in sorted(cards, key=lambda c: c["oracle_id"]):
            hits = scan_card(card)
            rec = {
                "pattern_rules_version": PATTERN_RULES_VERSION,
                "oracle_id": card["oracle_id"],
                "name": card["name"],
                "rule_ids": sorted(hits),
                "hits": {k: hits[k] for k in sorted(hits)},
            }
            _assert_no_leak(rec)
            fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
            for r in hits:
                per_rule[r].append({"card": card, "hits": hits[r]})
    summary = {
        "pattern_rules_version": PATTERN_RULES_VERSION,
        "pool": len(cards),
        "zero_source_decks": len(zero),
        "rules": {},
    }
    for rule in RULES:
        rows = per_rule.get(rule.id, [])
        summary["rules"][rule.id] = {
            "group": rule.group,
            "kind": rule.kind,
            "description": rule.description,
            "hits": len(rows),
            "of": len(cards),
            "creatures": sum(1 for r in rows if r["card"]["is_creature_front"]),
            "lands": sum(1 for r in rows if r["card"]["is_land_front"]),
            "in_zero_source_decks": (
                sum(1 for r in rows if r["card"]["oracle_id"] in zero) if zero else None
            ),
        }
    any_pos = {
        c["card"]["oracle_id"]
        for rid in [
            r.id for r in RULES if r.kind == "positive" and r.id not in ("etb_own", "landfall")
        ]
        for c in per_rule.get(rid, [])
    }
    summary["cards_with_any_positive_rule_except_etb_own_landfall"] = len(any_pos)
    (out / "pattern_summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.sample:
        sample = {}
        for rule in RULES:
            rows = sorted(per_rule.get(rule.id, []), key=lambda r: r["card"]["oracle_id"])
            rng = random.Random(f"{args.seed}:{rule.id}")
            pick = rows if len(rows) <= args.sample else rng.sample(rows, args.sample)
            sample[rule.id] = [
                {
                    "name": r["card"]["name"],
                    "type_line": r["card"]["type_line"],
                    "mv": r["card"]["mana_value"],
                    "evidence": r["hits"][0]["line"],
                    "hits": len(r["hits"]),
                }
                for r in sorted(pick, key=lambda r: r["card"]["name"])
            ]
        (out / "pattern_sample.json").write_text(
            json.dumps(sample, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({k: v["hits"] for k, v in summary["rules"].items()}, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
