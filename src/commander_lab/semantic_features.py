from __future__ import annotations

import re

from commander_lab.models import CardRole, Color, StructuralCardProfile

SEMANTIC_FEATURE_VERSION = "2026-08-14.3"
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
    return any(
        marker in text
        for marker in (
            "its controller creates",
            "that player creates",
            "target opponent creates",
            "target player creates",
            "a player creates",
            "an opponent creates",
            "each opponent creates",
        )
    )


def _effect_clauses(oracle_text: str | None) -> tuple[str, ...]:
    text = rules_text(oracle_text)
    return tuple(clause.strip() for clause in re.split(r"[.;\n]+", text) if clause.strip())


def self_token_creation(oracle_text: str | None) -> bool:
    """Return True only for token creation controlled by the card's controller.

    Recipient analysis is clause-local so a card that gives an opponent a token in one effect and
    creates a token for you in another does not lose the valid self-token signal.
    """
    for clause in _effect_clauses(oracle_text):
        if "create" not in clause or " token" not in clause:
            continue
        if other_player_resource_recipient(clause):
            continue
        if "you create" in clause or re.search(
            r"(?<!controller )(?<!player )\bcreate (?:a|an|one|two|three|four|x|that many|those) [^.]* token",
            clause,
        ):
            return True
    return False


def self_mana_semantics(oracle_text: str | None, type_line: str | None) -> tuple[bool, bool]:
    """Return ``(repeatable_self_mana, self_acceleration)`` conservatively.

    Mana or Treasure explicitly awarded to an opponent/target player/controller is excluded.
    """
    text = rules_text(oracle_text)
    card_type = (type_line or "").casefold()
    is_land = "land" in card_type
    is_permanent = not ("instant" in card_type or "sorcery" in card_type)
    own_clauses = tuple(
        clause for clause in _effect_clauses(text) if not other_player_resource_recipient(clause)
    )
    activated_mana = any(bool(re.search(r"\{t\}[^.]{0,120}\badd\b", c)) for c in own_clauses)
    triggered_mana = any(
        is_permanent
        and bool(re.search(r"\b(?:whenever|at the beginning|when)\b[^.]{0,160}\badd\b", c))
        for c in own_clauses
    )
    repeatable = is_land or activated_mana or triggered_mana
    land_to_battlefield = any(
        (
            "search your library" in c
            and (
                "land" in c
                or any(
                    f"{subtype} card" in c
                    for subtype in ("plains", "island", "swamp", "mountain", "forest")
                )
            )
            and "battlefield" in c
        )
        or ("put a land card" in c and "onto the battlefield" in c)
        for c in own_clauses
    )
    direct_mana = (
        any(bool(re.search(r"\badd (?:\{|one |two |three |four |x )", c)) for c in own_clauses)
        and not is_land
    )
    self_treasure = ("treasure token" in text or "treasure tokens" in text) and self_token_creation(
        text
    )
    cost_reduction = (
        any(
            marker in text
            for marker in (
                "spells you cast cost",
                "instant and sorcery spells you cast cost",
                "artifact spells you cast cost",
                "creature spells you cast cost",
            )
        )
        and " less to cast" in text
    )
    return repeatable, direct_mana or self_treasure or land_to_battlefield or cost_reduction


def graveyard_hate_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return any(
        marker in text
        for marker in (
            "exile target card from a graveyard",
            "exile all cards from target player's graveyard",
            "exile all cards from target opponent's graveyard",
            "exile target player's graveyard",
            "exile all cards from all graveyards",
            "exile all graveyards",
            "cards in graveyards can't",
            "cards in graveyards lose",
            "opponents can't cast spells from graveyards",
            "from opponents' graveyards",
        )
    )


def removal_targets(oracle_text: str | None) -> frozenset[str]:
    text = rules_text(oracle_text)
    targets: set[str] = set()
    for noun, label in (
        ("artifact", "artifact"),
        ("enchantment", "enchantment"),
        ("creature", "creature"),
        ("planeswalker", "planeswalker"),
        ("permanent", "permanent"),
    ):
        if re.search(rf"\b(?:destroy|exile) target [^.]*\b{noun}\b", text):
            targets.add(label)
        if re.search(rf"\breturn target [^.]*\b{noun}\b[^.]*owner'?s hand", text):
            targets.add(label)
        if re.search(
            rf"\b(?:put|return) target [^.]*\b{noun}\b[^.]*"
            rf"(?:top|bottom) of (?:its|their) owner'?s library",
            text,
        ):
            targets.add(label)
    if re.search(r"target creature gets -(?:\d+|x)/-(?:\d+|x)", text):
        targets.add("creature")
    if "damage to any target" in text or re.search(
        r"deals? (?:\d+|x) damage to target (?:creature|creature or planeswalker|planeswalker or creature)",
        text,
    ):
        targets.update({"creature", "planeswalker"})
    if re.search(r"deals? (?:\d+|x) damage to target attacking or blocking creature", text):
        targets.add("creature")
    if re.search(
        r"(?:deals?|and) (?:\d+|x) damage to target (?!player|opponent)[^.]{0,80}\bcreature\b", text
    ):
        targets.add("creature")
    if re.search(
        r"deals? (?:\d+|x) damage divided [^.]{0,100}(?:any number of|one, two, or three) targets",
        text,
    ):
        targets.update({"creature", "planeswalker"})
    if re.search(r"target creature deals damage to itself equal to its power", text):
        targets.add("creature")
    return frozenset(targets)


def bounce_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return bool(
        re.search(
            r"return (?:up to [^.]{0,30} )?(?:one|two|three|four|five|six|x|target) [^.]{0,90}(?:creature|permanent|artifact|enchantment|planeswalker)[^.]{0,80}owners?' hands?",
            text,
        )
        or re.search(r"return target [^.]{0,90} to its owner's hand", text)
    )


def removal_semantics(oracle_text: str | None) -> bool:
    return bool(removal_targets(oracle_text)) or bounce_semantics(oracle_text)


def redirect_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return bool(
        re.search(r"change the target of target (?:spell|ability)", text)
        or re.search(r"choose new targets? for target (?:spell|ability)", text)
    )


def protection_semantics(oracle_text: str | None) -> bool:
    """Conservative protection that can preserve another own permanent/commander."""
    text = rules_text(oracle_text)
    patterns = (
        r"target [^.]{0,60}(?:creature|permanent)[^.]{0,100}(?:gains?|has) (?:hexproof|indestructible|protection)",
        r"target [^.]{0,60}(?:creature|permanent)[^.]{0,100}phases out",
        r"(?:creatures|permanents|commander creatures) you control [^.]{0,100}(?:gain|have) (?:hexproof|indestructible|protection)",
        r"equipped creature [^.]{0,100}(?:has|gains) (?:hexproof|shroud|ward|indestructible|protection)",
        r"enchanted creature [^.]{0,100}(?:has|gains) (?:hexproof|shroud|ward|indestructible|protection)",
        r"another target creature [^.]{0,100}(?:gains?|has) (?:hexproof|indestructible|protection)",
    )
    damage_prevention = bool(
        re.search(
            r"prevent all damage [^.]{0,120}(?:to you and (?:creatures|permanents) you control|to creatures you control)",
            text,
        )
    )
    return (
        any(re.search(pattern, text) for pattern in patterns)
        or damage_prevention
        or redirect_semantics(text)
    )


def combat_draw_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return "draw" in text and any(
        marker in text
        for marker in (
            "combat damage",
            "attacks",
            "attacking",
            "becomes blocked",
            "isn't blocked",
            "unblocked",
        )
    )


def double_strike_semantics(oracle_text: str | None) -> bool:
    return "double strike" in rules_text(oracle_text)


def stack_interaction_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return bool(
        re.search(r"\bcounter target [^.]{0,80}(?:spell|ability)", text)
        or (
            "for each spell and ability your opponents control" in text
            and "counter it unless" in text
        )
    )


def spellslinger_engine_semantics(oracle_text: str | None) -> bool:
    return bool(
        re.search(
            r"(?:whenever|when) [^.]{0,90}(?:cast|copy) [^.]{0,90}(?:instant|sorcery|noncreature spell)",
            rules_text(oracle_text),
        )
    )


def draw_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return bool(
        re.search(r"\bdraws? (?:a|one|two|three|four|five|x|that many|\d+) cards?\b", text)
        or "draw cards equal to" in text
        or "draw that many cards" in text
    )


def selection_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    if any(
        marker in text
        for marker in (
            "scry ",
            "surveil ",
            "look at the top",
            "reveal the top",
            "look at the top cards",
            "look at the top card",
        )
    ):
        return True
    impulse = bool(
        re.search(r"exile (?:the )?top [^.]{0,60} cards?[^.]{0,160}you may (?:play|cast)", text)
    )
    filtering = bool(
        re.search(r"draws? [^.]{0,40} cards?[^.]{0,80}discard", text)
        or re.search(r"discard [^.]{0,60} cards?[^.]{0,80}draw", text)
    )
    top_access = bool(
        re.search(
            r"(?:exile|reveal) (?:the )?top .{0,260}(?:card|cards).{0,360}"
            r"(?:you may (?:play|cast)|put .{0,80} into your hand)",
            text,
        )
    )
    reveal_until_hand = bool(
        "reveal cards from the top of your library until" in text
        and "put all cards revealed this way into your hand" in text
    )
    return impulse or filtering or top_access or reveal_until_hand


def recursion_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    patterns = (
        r"return target [^.]{0,80} card from your graveyard to your hand",
        r"return target [^.]{0,80} card from your graveyard to the battlefield",
        r"return [^.]{0,80} from your graveyard to your hand",
        r"return [^.]{0,80} from your graveyard to the battlefield",
        r"you may cast [^.]{0,100} from your graveyard",
        r"you may play [^.]{0,100} from your graveyard",
        r"play lands? from your graveyard",
        r"put (?:this|that) card from your graveyard on top of your library",
        r"shuffle [^.]{0,100}(?:your graveyard|cards? from your graveyard)[^.]{0,80}into (?:their owner's|your) library",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def mass_removal_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return any(
        marker in text
        for marker in (
            "destroy all creatures",
            "exile all creatures",
            "destroy all nonland permanents",
            "exile all nonland permanents",
            "destroy all artifacts",
            "destroy all enchantments",
            "return all creatures to their owners' hands",
            "return all nonland permanents to their owners' hands",
        )
    ) or bool(
        re.search(r"(?:destroy|exile) all [^.]{0,60}creatures", text)
        or re.search(r"destroy each [^.]{0,60}nonland permanent", text)
        or re.search(r"return all [^.]{0,60}nonland permanents [^.]{0,60}owner's hand", text)
        or re.search(r"return all [^.]{0,60}creatures [^.]{0,60}owner's hand", text)
        or re.search(r"return all nonland permanents target player controls", text)
        or re.search(r"(?:each|all) creatures? get -(?:\d+|x)/-(?:\d+|x)", text)
        or re.search(r"deals? (?:\d+|x) damage to each creature", text)
    )


def sacrifice_outlet_semantics(oracle_text: str | None) -> bool:
    text = rules_text(oracle_text)
    return bool(
        re.search(r"sacrifice (?:a|an|another|one|two|three|x) [^:]{0,90}:", text)
        or re.search(r"\{[^}]+\}, sacrifice [^:]{0,90}:", text)
    )


def structural_roles_from_oracle(
    oracle_text: str | None, type_line: str | None
) -> frozenset[CardRole]:
    """Conservative functional roles derivable from Oracle text.

    These are structural search labels only. They are not card-power scores and do not claim full
    rules-engine understanding.
    """
    roles: set[CardRole] = set()
    repeatable_mana, acceleration = self_mana_semantics(oracle_text, type_line)
    if "land" in (type_line or "").casefold() or repeatable_mana:
        roles.add(CardRole.MANA_SOURCE)
    if acceleration:
        roles.add(CardRole.RAMP)
    if draw_semantics(oracle_text):
        roles.add(CardRole.DRAW)
    if selection_semantics(oracle_text):
        roles.add(CardRole.SELECTION)
    if removal_semantics(oracle_text):
        roles.add(CardRole.REMOVAL)
    if stack_interaction_semantics(oracle_text):
        roles.add(CardRole.COUNTER)
    if protection_semantics(oracle_text):
        roles.add(CardRole.PROTECTION)
    if mass_removal_semantics(oracle_text):
        roles.add(CardRole.WIPE)
    if recursion_semantics(oracle_text):
        roles.add(CardRole.RECURSION)
    if graveyard_hate_semantics(oracle_text):
        roles.add(CardRole.GRAVEYARD_HATE)
    if self_token_creation(oracle_text):
        roles.add(CardRole.TOKEN_SOURCE)
    if sacrifice_outlet_semantics(oracle_text):
        roles.add(CardRole.SACRIFICE_OUTLET)
    text = rules_text(oracle_text)
    if (
        combat_draw_semantics(text)
        or double_strike_semantics(text)
        or any(
            marker in text
            for marker in (
                "combat damage to a player",
                "combat damage to an opponent",
                "additional combat phase",
                "extra combat phase",
            )
        )
    ):
        roles.add(CardRole.COMBAT_PAYOFF)
    if any(
        marker in text
        for marker in (
            "whenever a land enters",
            "landfall",
            "play an additional land",
            "lands you control",
        )
    ):
        roles.add(CardRole.LAND_SYNERGY)
    if any(
        marker in text
        for marker in (
            "each opponent loses",
            "damage to each opponent",
            "deals damage to each opponent",
            "you win the game",
        )
    ) or bool(
        re.search(
            r"(?:whenever|when) [^.]{0,90}(?:creature you control enters|this creature enters|this creature attacks)[^.]{0,160}deals? [^.]{0,80}damage",
            text,
        )
    ):
        roles.add(CardRole.PAYOFF)
    if "you win the game" in text or "each opponent loses" in text:
        roles.add(CardRole.FINISHER)
    if roles.intersection(
        {CardRole.TOKEN_SOURCE, CardRole.SACRIFICE_OUTLET, CardRole.LAND_SYNERGY, CardRole.RAMP}
    ):
        roles.add(CardRole.ENABLER)
    if bool(re.search(r"\b(?:whenever|at the beginning of)\b", text)) and roles.intersection(
        {CardRole.DRAW, CardRole.TOKEN_SOURCE, CardRole.PAYOFF, CardRole.LAND_SYNERGY}
    ):
        roles.add(CardRole.ENGINE)
    return frozenset(roles)


def sanitize_structural_profile_semantics(
    profile: object, *, oracle_text: str | None, type_line: str | None
) -> StructuralCardProfile:
    """Apply high-risk semantic gates to a StructuralCardProfile without importing tool layers."""
    if not isinstance(profile, StructuralCardProfile):
        raise TypeError("profile must be StructuralCardProfile")
    repeatable_mana, acceleration = self_mana_semantics(oracle_text, type_line)
    roles = set(profile.roles)
    strengths = dict(profile.role_strengths)
    guards = {
        CardRole.MANA_SOURCE: profile.is_land or repeatable_mana,
        CardRole.RAMP: acceleration,
        CardRole.GRAVEYARD_HATE: graveyard_hate_semantics(oracle_text),
        CardRole.REMOVAL: removal_semantics(oracle_text),
        CardRole.PROTECTION: protection_semantics(oracle_text),
        CardRole.TOKEN_SOURCE: self_token_creation(oracle_text),
    }
    for role, allowed in guards.items():
        if not allowed:
            roles.discard(role)
            strengths.pop(role, None)
    return profile.model_copy(update={"roles": frozenset(roles), "role_strengths": strengths})


def produced_self_colors(
    oracle_text: str | None,
    type_line: str | None,
    *,
    oracle_name: str | None = None,
    include_fetchable_land_types: bool = False,
) -> frozenset[Color]:
    text = rules_text(oracle_text)
    type_low = (type_line or "").casefold()
    produced: set[Color] = set()
    subtype_colors = (
        ("plains", Color.WHITE),
        ("island", Color.BLUE),
        ("swamp", Color.BLACK),
        ("mountain", Color.RED),
        ("forest", Color.GREEN),
    )
    for subtype, color in subtype_colors:
        if subtype in type_low:
            produced.add(color)
    if oracle_name == "Command Tower":
        produced.update(ROGSHAI_COLORS)
    if ("treasure token" in text or "treasure tokens" in text) and self_token_creation(text):
        produced.update(ROGSHAI_COLORS)
    if "add" in text:
        for symbol, color in (
            ("w", Color.WHITE),
            ("u", Color.BLUE),
            ("b", Color.BLACK),
            ("r", Color.RED),
            ("g", Color.GREEN),
        ):
            if f"{{{symbol}}}" in text:
                produced.add(color)
        if "any color" in text or "any one color" in text:
            produced.update(ROGSHAI_COLORS)
    if include_fetchable_land_types and "search your library" in text and "land" in text:
        for subtype, color in subtype_colors:
            if subtype in text:
                produced.add(color)
    return frozenset(produced)
