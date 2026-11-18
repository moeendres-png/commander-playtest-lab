"""Deterministic, versioned Oracle-text rules for Chulane, Teller of Tales (Phase B2 / E1).

This module reads only public card facts (``type_line``, ``oracle_text``, ``mana_value``,
``produced_mana``) and extracts explicit mechanical matches relevant to Chulane's cast-creature
/ bounce / landfall loop.

Design invariants (``AGENTS.md`` & ``docs/OWNER_DECISIONS_STUDIO_20261112.md``):
- Weight in the usage-based ``strength`` index is strictly ``0``; this is an independent,
  descriptive second axis, never a tier or score replacement.
- Every positive match carries its ``rule_id`` and the exact ``matched_phrase`` from the card.
- ``own_etb_trigger`` and ``foreign_trigger`` are explicitly separated so triggers on other
  permanents entering (e.g. Beast Whisperer / Soul of the Harvest) are not misclassified as
  self-ETBs.
"""

from __future__ import annotations

import re
from typing import TypedDict

CHULANE_TEXTFIT_RULES_VERSION = "chulane-textfit-1"
CHULANE_TEXTFIT_TOTAL_RULES = 5

_SELF_OR_OWN_BOUNCE = re.compile(
    r"\breturn\b[^.\n]*\b(?:a|another|up to one|target)?\s*(?:creature|permanent)s?\s+you control\b"
    r"[^.\n]*\bto (?:its|their) owner'?s? hands?\b"
    r"|\breturn\b[^.\n]*\bto (?:its|their) owner'?s? hand\b",
    re.IGNORECASE,
)
_OPPONENT_ONLY_BOUNCE = re.compile(
    r"\breturn\b[^.\n]*\ban opponent controls\b[^.\n]*\bto (?:its|their) owner'?s? hand\b",
    re.IGNORECASE,
)
_BLINK = re.compile(
    r"\bexile\b[^.\n]*\b(?:then\s+)?return\b[^.\n]*\bto the battlefield\b",
    re.IGNORECASE,
)
_LANDFALL_OR_EXTRA_LAND = re.compile(
    r"\blandfall\b"
    r"|\bwhenever (?:a|one or more) lands?(?: you control)? enters?\b"
    r"|\bplay (?:an|one or more|two|three|\d+) additional lands?\b"
    r"|\bput a land card from your hand onto the battlefield\b",
    re.IGNORECASE,
)
_ADD_MANA = re.compile(r"\badd\b[^.\n]*\{", re.IGNORECASE)
_FOREIGN_ETB = re.compile(
    r"\bwhenever\s+(?:another|a|an|one or more)\s+(?:(?:other|nontoken|token|face-down)\s+)*"
    r"(?:creature|creatures|permanent|permanents|artifact|enchantment|land|opponent)"
    r"[^.\n]*\benters\b",
    re.IGNORECASE,
)
_ANY_ETB = re.compile(r"\b(?:when|whenever)\b[^.\n]*\benters\b", re.IGNORECASE)


class TextfitMatch(TypedDict):
    rule_id: str
    label: str
    matched_phrase: str


class ChulaneTextfitResult(TypedDict):
    version: str
    weight_in_index: int
    is_creature_spell: bool
    self_bounce_or_blink: bool
    landfall_or_extra_land: bool
    cheap_mana_dork: bool
    own_etb_trigger: bool
    foreign_trigger: bool
    foreign_phrase: str | None
    matched_count: int
    total_rules: int
    matches: list[TextfitMatch]


def is_chulane_commander(commander: str) -> bool:
    """Return True when the active commander is Chulane, Teller of Tales."""
    return "chulane" in commander.casefold()


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    hit = pattern.search(text)
    return hit.group(0).strip() if hit else None


def evaluate_chulane_textfit(
    *,
    type_line: str,
    oracle_text: str,
    mana_value: float | int | None,
    produced_mana: str = "",
) -> ChulaneTextfitResult:
    """Deterministically evaluate Chulane-relevant mechanical text features for one card."""
    front_type = type_line.split(" // ")[0]
    text = oracle_text or ""
    matches: list[TextfitMatch] = []

    is_creature = "Creature" in front_type
    if is_creature:
        matches.append(
            {
                "rule_id": "is_creature_spell",
                "label": "Kreaturen-Zauber",
                "matched_phrase": front_type.strip(),
            }
        )

    bounce_phrase: str | None = None
    blink_hit = _first_match(_BLINK, text)
    if blink_hit:
        bounce_phrase = blink_hit
    else:
        bounce_hit = _first_match(_SELF_OR_OWN_BOUNCE, text)
        if bounce_hit and not _OPPONENT_ONLY_BOUNCE.search(bounce_hit):
            bounce_phrase = bounce_hit
    has_bounce_or_blink = bounce_phrase is not None
    if bounce_phrase is not None:
        matches.append(
            {
                "rule_id": "self_bounce_or_blink",
                "label": "Self-Bounce / Blink",
                "matched_phrase": bounce_phrase,
            }
        )

    landfall_phrase = _first_match(_LANDFALL_OR_EXTRA_LAND, text)
    has_landfall_or_extra = landfall_phrase is not None
    if landfall_phrase is not None:
        matches.append(
            {
                "rule_id": "landfall_or_extra_land",
                "label": "Landfall / Extra-Land",
                "matched_phrase": landfall_phrase,
            }
        )

    mana_phrase: str | None = None
    if is_creature and mana_value is not None and float(mana_value) <= 2.0:
        if produced_mana:
            mana_phrase = f"produced_mana={produced_mana}"
        else:
            mana_phrase = _first_match(_ADD_MANA, text)
    is_cheap_dork = mana_phrase is not None
    if mana_phrase is not None:
        matches.append(
            {
                "rule_id": "cheap_mana_dork",
                "label": "Günstiger Mana-Dork (MV ≤ 2)",
                "matched_phrase": mana_phrase,
            }
        )

    foreign_phrase: str | None = None
    own_etb_phrase: str | None = None
    for sentence_match in _ANY_ETB.finditer(text):
        phrase = sentence_match.group(0).strip()
        if _FOREIGN_ETB.search(phrase):
            if foreign_phrase is None:
                foreign_phrase = phrase
        else:
            if own_etb_phrase is None:
                own_etb_phrase = phrase

    has_own_etb = own_etb_phrase is not None
    has_foreign = foreign_phrase is not None
    if own_etb_phrase is not None:
        matches.append(
            {
                "rule_id": "own_etb_trigger",
                "label": "Eigener ETB-Trigger",
                "matched_phrase": own_etb_phrase,
            }
        )

    return {
        "version": CHULANE_TEXTFIT_RULES_VERSION,
        "weight_in_index": 0,
        "is_creature_spell": is_creature,
        "self_bounce_or_blink": has_bounce_or_blink,
        "landfall_or_extra_land": has_landfall_or_extra,
        "cheap_mana_dork": is_cheap_dork,
        "own_etb_trigger": has_own_etb,
        "foreign_trigger": has_foreign,
        "foreign_phrase": foreign_phrase,
        "matched_count": len(matches),
        "total_rules": CHULANE_TEXTFIT_TOTAL_RULES,
        "matches": matches,
    }
