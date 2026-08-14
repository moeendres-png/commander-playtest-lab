from __future__ import annotations

import re

from commander_lab.models import Color

SEMANTIC_FEATURE_VERSION = "2026-08-14.2"
ROGSHAI_COLORS = frozenset({Color.WHITE, Color.BLUE, Color.RED})


def rules_text(oracle_text: str | None) -> str:
    """Lower-cased rules text with simple parenthetical reminder text removed."""
    text = (oracle_text or "").casefold()
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\([^()]*\)", " ", text)
    return " ".join(text.split())


def other_player_resource_recipient(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return any(marker in text for marker in ("its controller creates", "that player creates", "target opponent creates", "target player creates", "a player creates", "an opponent creates", "each opponent creates"))


def self_token_creation(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    if "create" not in text or " token" not in text or other_player_resource_recipient(text):
        return False
    return bool("you create" in text or re.search(r"\bcreate (?:a|an|one|two|three|four|x|that many|those) [^.]* token", text))


def self_mana_semantics(oracle_text: str | None, type_line: str | None) -> tuple[bool, bool]:
    """Return (repeatable_self_mana, self_acceleration) conservatively."""
    text = rules_text(oracle_text)
    card_type = (type_line or "").casefold()
    is_land = "land" in card_type
    is_permanent = not ("instant" in card_type or "sorcery" in card_type)
    activated_mana = bool(re.search(r"\{t\}[^.]{0,120}\badd\b", text))
    triggered_mana = bool(is_permanent and re.search(r"\b(?:whenever|at the beginning|when)\b[^.]{0,160}\badd\b", text))
    repeatable = is_land or activated_mana or triggered_mana
    land_to_battlefield = bool("search your library" in text and "land" in text and "battlefield" in text) or bool("put a land card" in text and "onto the battlefield" in text)
    direct_mana = bool(re.search(r"\badd (?:\{|one |two |three |four |x )", text)) and not is_land
    self_treasure = ("treasure token" in text or "treasure tokens" in text) and self_token_creation(text)
    return repeatable, direct_mana or self_treasure or land_to_battlefield


def graveyard_hate_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return any(marker in text for marker in ("exile target card from a graveyard", "exile all cards from target player's graveyard", "exile all cards from target opponent's graveyard", "exile target player's graveyard", "exile all cards from all graveyards", "exile all graveyards", "cards in graveyards can't", "cards in graveyards lose", "opponents can't cast spells from graveyards", "from opponents' graveyards"))


def removal_targets(oracle_text: str | None) -> frozenset[str]:
    text = rules_text(oracle_text)
    targets: set[str] = set()
    for noun, label in (("artifact", "artifact"), ("enchantment", "enchantment"), ("creature", "creature"), ("planeswalker", "planeswalker"), ("permanent", "permanent")):
        if re.search(rf"\b(?:destroy|exile) target [^.]*\b{noun}\b", text):
            targets.add(label)
        if re.search(rf"\breturn target [^.]*\b{noun}\b[^.]*owner'?s hand", text):
            targets.add(label)
    if re.search(r"target creature gets -(?:\d+|x)/-(?:\d+|x)", text):
        targets.add("creature")
    if "damage to any target" in text or re.search(r"deals? (?:\d+|x) damage to target (?:creature|creature or planeswalker|planeswalker or creature)", text):
        targets.update({"creature", "planeswalker"})
    if re.search(r"deals? (?:\d+|x) damage to target attacking or blocking creature", text):
        targets.add("creature")
    if re.search(r"(?:deals?|and) (?:\d+|x) damage to target (?!player|opponent)[^.]{0,80}\bcreature\b", text):
        targets.add("creature")
    return frozenset(targets)


def removal_semantics(oracle_text: str | None) -> bool:
    return bool(removal_targets(oracle_text))


def protection_semantics(oracle_text: str | None) -> bool:
    """Conservative protection that can preserve another own permanent/commander."""
    text = rules_text(oracle_text)
    patterns = (r"target [^.]{0,60}(?:creature|permanent)[^.]{0,100}(?:gains?|has) (?:hexproof|indestructible|protection)", r"target [^.]{0,60}(?:creature|permanent)[^.]{0,100}phases out", r"(?:creatures|permanents|commander creatures) you control [^.]{0,100}(?:gain|have) (?:hexproof|indestructible|protection)", r"equipped creature [^.]{0,100}(?:has|gains) (?:hexproof|shroud|ward|indestructible|protection)", r"enchanted creature [^.]{0,100}(?:has|gains) (?:hexproof|shroud|ward|indestructible|protection)", r"another target creature [^.]{0,100}(?:gains?|has) (?:hexproof|indestructible|protection)")
    return any(re.search(pattern, text) for pattern in patterns)


def combat_draw_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return "draw" in text and any(marker in text for marker in ("combat damage", "attacks", "attacking", "becomes blocked", "isn't blocked", "unblocked"))


def double_strike_semantics(oracle_text: str | None) -> bool:
    return "double strike" in rules_text(oracle_text)


def stack_interaction_semantics(oracle_text: str | None) -> bool:
    return bool(re.search(r"\bcounter target [^.]{0,80}(?:spell|ability)", rules_text(oracle_text)))


def spellslinger_engine_semantics(oracle_text: str | None) -> bool:
    return bool(re.search(r"(?:whenever|when) [^.]{0,90}(?:cast|copy) [^.]{0,90}(?:instant|sorcery|noncreature spell)", rules_text(oracle_text)))


def produced_self_colors(oracle_text: str | None, type_line: str | None, *, oracle_name: str | None = None, include_fetchable_land_types: bool = False) -> frozenset[Color]:
    text = rules_text(oracle_text)
    type_low = (type_line or "").casefold()
    produced: set[Color] = set()
    subtype_colors = (("plains", Color.WHITE), ("island", Color.BLUE), ("swamp", Color.BLACK), ("mountain", Color.RED), ("forest", Color.GREEN))
    for subtype, color in subtype_colors:
        if subtype in type_low:
            produced.add(color)
    if oracle_name == "Command Tower":
        produced.update(ROGSHAI_COLORS)
    if "add" in text:
        for symbol, color in (("w", Color.WHITE), ("u", Color.BLUE), ("b", Color.BLACK), ("r", Color.RED), ("g", Color.GREEN)):
            if f"{{{symbol}}}" in text:
                produced.add(color)
        if "any color" in text or "any one color" in text:
            produced.update(ROGSHAI_COLORS)
    if include_fetchable_land_types and "search your library" in text and "land" in text:
        for subtype, color in subtype_colors:
            if subtype in text:
                produced.add(color)
    return frozenset(produced)
