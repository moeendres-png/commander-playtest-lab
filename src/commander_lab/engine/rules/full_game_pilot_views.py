"""Card-aware pilot views for the XMage full-game policy (#732).

The engine offers the legal options; the pilot only ranks them. This module
turns an engine option plus the actor-scoped pilot view into the strategic
facts a human player would weigh: what the card is (from the public printed
card catalog), how big the creatures on the table are, which blocks trade and
which are chump blocks, which colour a payment still needs.

Pure functions of Rules-visible content: no engine identifiers order anything
and nothing here decides legality, so twin determinism and the engine's sole
rules authority are unchanged.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from commander_lab.agents.card_knowledge import (
    COLOR_WORDS,
    CardFacts,
    card_facts,
    card_roles,
    curated_profile,
    evasion,
    is_basic_land_name,
    permanent_value,
)
from commander_lab.models import CardRole

_COLOR_SYMBOL = {word.casefold(): symbol for symbol, word in COLOR_WORDS.items()}
_PIP = re.compile(r"\{([WUBRG])(?:/[WUBRGP])?\}")


def _items(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def players(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _items(state.get("players"))


def commander_names(state: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(
        str(entry.get("name", "")).casefold()
        for entry in _items(state.get("commander_status"))
        if entry.get("name")
    )


def permanent_owner(object_id: str, state: Mapping[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """(controller player id, battlefield entry) for a permanent id."""
    for player in players(state):
        for item in _items(player.get("battlefield")):
            if str(item.get("object_id", "")) == object_id:
                return str(player.get("player_id", "")), item
    return None


def is_land_entry(item: Mapping[str, Any]) -> bool:
    facts = card_facts(str(item.get("name") or ""))
    if facts is not None:
        return facts.is_land
    return is_basic_land_name(str(item.get("name") or ""))


def is_creature_entry(item: Mapping[str, Any]) -> bool:
    facts = card_facts(str(item.get("name") or ""))
    if facts is not None and facts.is_creature:
        return True
    # Tokens and animated permanents are unknown to the printed catalog; a
    # non-land with positive toughness on the board is treated as a creature.
    toughness = item.get("toughness")
    return (
        not is_land_entry(item)
        and isinstance(toughness, int)
        and toughness > 0
        and (facts is None or "creature" in " ".join(item.get("abilities") or ()).casefold())
    )


def creature_power(item: Mapping[str, Any]) -> int:
    value = item.get("power")
    return value if isinstance(value, int) and value > 0 else 0


def creature_toughness_left(item: Mapping[str, Any]) -> int:
    toughness = item.get("toughness")
    damage = item.get("damage")
    left = (toughness if isinstance(toughness, int) else 0) - (
        damage if isinstance(damage, int) else 0
    )
    return max(0, left)


def entry_value(item: Mapping[str, Any], state: Mapping[str, Any]) -> float:
    name = str(item.get("name") or "")
    power = item.get("power") if isinstance(item.get("power"), int) else None
    toughness = item.get("toughness") if isinstance(item.get("toughness"), int) else None
    return permanent_value(
        card_facts(name),
        power=power if is_creature_entry(item) else None,
        toughness=toughness if is_creature_entry(item) else None,
        is_commander=name.casefold() in commander_names(state),
    )


def board_summary(player: Mapping[str, Any]) -> dict[str, float]:
    """Creature power, non-land permanent count and land count of one player."""
    power = 0.0
    nonland = 0.0
    lands = 0
    for item in _items(player.get("battlefield")):
        if is_land_entry(item):
            lands += 1
            continue
        nonland += 1
        if is_creature_entry(item):
            power += creature_power(item)
    return {"creature_power": power, "nonland_permanents": nonland, "lands": float(lands)}


def hand_role_counts(names: Iterable[str]) -> dict[CardRole, int]:
    counts: Counter[CardRole] = Counter()
    for name in names:
        facts = card_facts(name)
        if facts is None:
            continue
        for role in card_roles(facts):
            counts[role] += 1
    return dict(counts)


def card_view_fields(name: str) -> dict[str, Any]:
    """PilotActionView fields for a card known by name (hand, cast option)."""
    facts = card_facts(name)
    if facts is None:
        return {"metadata": {"is_land": is_basic_land_name(name)}}
    roles = card_roles(facts)
    return {
        "mana_cost": facts.mana_value,
        "roles": frozenset(roles),
        "role_strengths": dict(roles),
        "base_power": float(max(0, facts.power or 0)),
        "metadata": {"is_land": facts.is_land},
    }


def _engine_cost(meta: Mapping[str, Any]) -> float | None:
    keys = [key for key in meta if key.startswith("mana_cost_")]
    if not keys:
        return None
    total = 0
    for key in keys:
        value = meta.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            total += value
    return float(total)


def _opponent_has(state: Mapping[str, Any], actor_id: str, predicate: Any) -> bool:
    return any(
        predicate(item)
        for player in players(state)
        if str(player.get("player_id")) != actor_id and not player.get("has_lost")
        for item in _items(player.get("battlefield"))
    )


def priority_view_fields(
    option: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    own_stack_names: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], str | None]:
    """Card-aware view fields for one priority option, plus a withhold reason.

    The withhold reason names a self-defeating choice a player would not make
    (countering only one's own spells, spending single-target removal when no
    opponent has anything to remove). Withheld options stay engine-offered;
    the seat can always pass instead.
    """
    meta_raw = option.get("metadata")
    meta: Mapping[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
    option_type = str(option.get("option_type", ""))
    ability_type = str(meta.get("ability_type", ""))
    source_name = str(meta.get("source_name") or option.get("label") or "")
    label = str(option.get("label", "")).casefold()
    facts = card_facts(source_name)
    actor_id = str(state.get("actor_id", ""))
    fields: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    engine_cost = _engine_cost(meta)

    if option_type == "play_land" or ability_type == "play_land":
        fields.update(floor_value=1.6, immediate_impact=1.2, mana_cost=0.0)
        extra["is_land"] = True
        return {**fields, "metadata": extra}, None

    if ability_type == "spell" and facts is not None:
        roles = card_roles(facts)
        fields.update(
            mana_cost=engine_cost if engine_cost is not None else facts.mana_value,
            roles=frozenset(roles),
            role_strengths=dict(roles),
            base_power=float(max(0, facts.power or 0)),
        )
        impact = 0.45
        if facts.is_creature:
            impact = min(1.4, 0.45 + max(0, facts.power or 0) * 0.08)
        if facts.is_planeswalker:
            impact = 1.1
        if roles.keys() & {CardRole.REMOVAL, CardRole.WIPE, CardRole.DRAW, CardRole.RAMP}:
            impact = max(impact, 0.7)
        fields["immediate_impact"] = impact
        fields["floor_value"] = 0.65
        profile = curated_profile(facts.name)
        if profile is not None:
            # The curated profile's judgment of this card wins over the
            # generic estimate from its type and power.
            floor = profile.get("floor_value")
            curated_impact = profile.get("immediate_impact")
            if isinstance(floor, int | float):
                fields["floor_value"] = min(3.0, max(0.0, float(floor)))
            if isinstance(curated_impact, int | float):
                fields["immediate_impact"] = min(2.0, max(0.0, float(curated_impact)))
        withhold = _spell_withhold_reason(facts, roles, state, actor_id, own_stack_names)
        if CardRole.WIPE in roles:
            own = next((p for p in players(state) if str(p.get("player_id")) == actor_id), {})
            mine = board_summary(own)["creature_power"]
            theirs = max(
                (
                    board_summary(p)["creature_power"]
                    for p in players(state)
                    if str(p.get("player_id")) != actor_id
                ),
                default=0.0,
            )
            if mine >= theirs:
                withhold = withhold or "wipe_hurts_own_board_most"
        return {**fields, "metadata": extra}, withhold

    if option_type in {"activated_ability"} and ability_type != "spell":
        fields.update(floor_value=0.45, immediate_impact=0.35)
        if engine_cost is not None:
            fields["mana_cost"] = engine_cost
        if label.split(" — ")[-1].startswith("equip") or " equip " in f" {label} ":
            # Moving equipment back and forth is the #718 loop shape; it is
            # worth less than developing the board.
            fields.update(floor_value=0.3, immediate_impact=0.25)
        if "draw a card" in label or "cycling" in label:
            fields["roles"] = frozenset({CardRole.DRAW})
            fields["role_strengths"] = {CardRole.DRAW: 0.6}
        return {**fields, "metadata": extra}, None

    return {**fields, "metadata": extra}, None


def _spell_withhold_reason(
    facts: CardFacts,
    roles: Mapping[CardRole, float],
    state: Mapping[str, Any],
    actor_id: str,
    own_stack_names: frozenset[str],
) -> str | None:
    text = facts.oracle_text.casefold()
    if "as an additional cost to cast this spell, discard a card" in text:
        # The spell itself is in hand; the discard needs another card. A real
        # game had the cast reversed after its mana was already paid.
        actor = next((p for p in players(state) if str(p.get("player_id")) == actor_id), {})
        hand = actor.get("hand_count")
        hand_size = hand if isinstance(hand, int) else len(_items(actor.get("hand")))
        if hand_size < 2:
            return "additional_discard_cost_unpayable"
    if CardRole.COUNTER in roles and "counter target" in text:
        stack_names = {
            str(item.get("name", "")).casefold()
            for item in _items(state.get("stack"))
            if item.get("name")
        }
        if stack_names and stack_names <= own_stack_names:
            return "counter_only_own_stack"
    other = set(roles) - {CardRole.REMOVAL}
    only_removal = CardRole.REMOVAL in roles and not other
    if (
        only_removal
        and "target creature" in text
        and not _opponent_has(state, actor_id, is_creature_entry)
    ):
        return "no_opponent_creature_to_remove"
    if (
        only_removal
        and re.search(r"target (artifact|enchantment)", text)
        and not _opponent_has(state, actor_id, lambda item: not is_land_entry(item))
    ):
        return "no_opponent_permanent_to_remove"
    return None


def target_object_bonus(
    option: Mapping[str, Any],
    state: Mapping[str, Any],
    outcome: str,
    *,
    own_stack_names: frozenset[str] = frozenset(),
) -> float:
    """How good a specific object is as this target, beyond whose it is.

    Removal and other detrimental effects want the most valuable opposing
    permanent (a commander or a big threat, not a basic land); beneficial
    effects want one's own most valuable permanent. Spells on the stack that
    the actor itself cast are never the right counter target.
    """
    meta_raw = option.get("metadata")
    meta: Mapping[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
    object_id = str(meta.get("object_id") or option.get("option_id") or "")
    found = permanent_owner(object_id, state)
    actor_id = str(state.get("actor_id", ""))
    beneficial = outcome in {"benefit", "benefit_to_controller"}
    if found is None:
        name = str(meta.get("name") or option.get("label") or "").casefold()
        if meta.get("zone") == "stack" or name in own_stack_names:
            return -6.0 if (name in own_stack_names and not beneficial) else 0.0
        return 0.0
    controller, item = found
    value = min(12.0, entry_value(item, state))
    mine = controller == actor_id
    if beneficial:
        return value * 0.5 if mine else -value * 0.5
    return value * 0.5 if not mine else -value * 0.5


def _blockers_of(player: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in _items(player.get("battlefield"))
        if is_creature_entry(item) and item.get("tapped") is not True
    ]


def focus_defender(state: Mapping[str, Any]) -> str | None:
    """The opponent to concentrate attacks on: lowest life, then biggest board."""
    actor_id = str(state.get("actor_id", ""))
    candidates: list[tuple[float, float, str]] = []
    for player in players(state):
        player_id = str(player.get("player_id", ""))
        life = player.get("life")
        if player_id == actor_id or not isinstance(life, int | float) or life <= 0:
            continue
        if player.get("has_lost") is True or player.get("in_game") is False:
            continue
        candidates.append((float(life), -board_summary(player)["creature_power"], player_id))
    return min(candidates)[2] if candidates else None


def attack_score(
    option: Mapping[str, Any], state: Mapping[str, Any]
) -> tuple[float, dict[str, Any]]:
    """Score one 'attacker attacks defender' option; <= 0 means better to hold.

    Safe attacks (no untapped potential blocker of that defender can kill the
    attacker, or the attacker is evasive against all of them) are good, more
    so against a low-life defender. An attack into a blocker that kills the
    attacker without dying is bad. Zero-power attackers do nothing.
    """
    meta_raw = option.get("metadata")
    meta: Mapping[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
    attacker_id = str(meta.get("object_id") or "")
    defender_id = str(meta.get("defender_id") or "")
    found = permanent_owner(attacker_id, state)
    defender = next((p for p in players(state) if str(p.get("player_id")) == defender_id), None)
    if found is None or defender is None:
        return 0.2, {"combat_unknown": True}
    _controller, attacker = found
    power = creature_power(attacker)
    toughness = creature_toughness_left(attacker)
    if power <= 0:
        return -1.0, {"attack_power": 0}
    facts = card_facts(str(attacker.get("name") or ""))
    keywords = evasion(facts, tuple(attacker.get("abilities") or ()))
    blockers = _blockers_of(defender)
    able: list[dict[str, Any]] = []
    for blocker in blockers:
        blocker_keywords = evasion(
            card_facts(str(blocker.get("name") or "")), tuple(blocker.get("abilities") or ())
        )
        if "unblockable" in keywords:
            continue
        if "flying" in keywords and not blocker_keywords & {"flying", "reach"}:
            continue
        able.append(blocker)
    if "menace" in keywords and len(able) < 2:
        able = []
    killers = [
        blocker
        for blocker in able
        if creature_power(blocker) >= toughness
        or "deathtouch"
        in evasion(
            card_facts(str(blocker.get("name") or "")), tuple(blocker.get("abilities") or ())
        )
    ]
    if "indestructible" in keywords:
        killers = []
    if killers and not (keywords & {"first strike", "double strike"}):
        # A blocker that kills us and survives our damage is a losing attack.
        bad = [b for b in killers if creature_toughness_left(b) > power]
        if bad:
            return -0.8, {"attack_power": power, "attack_risk": "loses_to_blocker"}
        score = 0.15  # an even trade at best
    else:
        score = 0.6 + power * 0.08
    life = defender.get("life")
    life_value = float(life) if isinstance(life, (int, float)) else 40.0
    damage = power * (2 if "double strike" in keywords else 1)
    if not able and damage >= life_value:
        score += 3.0  # lethal through an empty or evaded board
    score += max(0.0, 20.0 - life_value) * 0.03
    if score > 0.0 and defender_id == focus_defender(state):
        # Spread-out damage lets everyone survive; pressure on one opponent
        # removes a player and shortens the game.
        score += 0.6
    return score, {"attack_power": power, "defender_blockers": len(able)}


def block_score(
    option: Mapping[str, Any], state: Mapping[str, Any]
) -> tuple[float, dict[str, Any]]:
    """Score one 'blocker blocks attacker' option; <= 0 means do not block."""
    meta_raw = option.get("metadata")
    meta: Mapping[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
    blocker_found = permanent_owner(str(meta.get("blocker_id") or ""), state)
    attacker_found = permanent_owner(str(meta.get("attacker_id") or ""), state)
    if blocker_found is None or attacker_found is None:
        return 0.0, {"combat_unknown": True}
    _, blocker = blocker_found
    _, attacker = attacker_found
    attacker_power = creature_power(attacker)
    attacker_keywords = evasion(
        card_facts(str(attacker.get("name") or "")), tuple(attacker.get("abilities") or ())
    )
    blocker_keywords = evasion(
        card_facts(str(blocker.get("name") or "")), tuple(blocker.get("abilities") or ())
    )
    if "double strike" in attacker_keywords:
        attacker_power *= 2
    blocker_survives = (
        creature_toughness_left(blocker) > attacker_power or "indestructible" in blocker_keywords
    ) and "deathtouch" not in attacker_keywords
    kills_attacker = (
        creature_power(blocker) >= creature_toughness_left(attacker)
        or "deathtouch" in blocker_keywords
    ) and "indestructible" not in attacker_keywords
    if "first strike" in attacker_keywords and not blocker_survives:
        kills_attacker = False
    actor = next(
        (p for p in players(state) if str(p.get("player_id")) == str(state.get("actor_id"))), {}
    )
    life = actor.get("life")
    life_value = float(life) if isinstance(life, (int, float)) else 40.0
    blocker_value = entry_value(blocker, state)
    attacker_value = entry_value(attacker, state)
    if blocker_survives and kills_attacker:
        score = 2.0 + attacker_value * 0.1
    elif blocker_survives:
        score = 0.8
    elif kills_attacker:
        score = 0.3 + (attacker_value - blocker_value) * 0.2
    else:
        # Chump block: only when this attacker's damage is lethal or nearly so.
        score = 1.5 if attacker_power >= life_value or life_value - attacker_power <= 5 else -1.0
        if "trample" in attacker_keywords:
            score = -1.0
    if attacker_power == 0:
        score = min(score, 0.1)
    if "menace" in attacker_keywords:
        # Each blocker is declared on its own; a lone blocker cannot block a
        # menace creature, and a real game looped re-proposing that block.
        score = -1.0
    return score, {"block_survives": blocker_survives, "block_kills": kills_attacker}


def needed_colors(unpaid_mana: str) -> Counter[str]:
    return Counter(_PIP.findall(unpaid_mana or ""))


def color_choice_rank(
    options: list[dict[str, Any]],
    *,
    unpaid_mana: str,
    hand_names: Iterable[str],
    identity: Iterable[str],
) -> list[tuple[float, str]]:
    """Rank colour options for a mana colour pick: the pending cost first.

    Returns (score, option label) pairs; ties keep the label order, which is
    Rules-visible. Colours outside every known need score zero.
    """
    pending = needed_colors(unpaid_mana)
    hand: Counter[str] = Counter()
    for name in hand_names:
        facts = card_facts(name)
        if facts is not None and not facts.is_land:
            hand.update(_PIP.findall(facts.mana_cost))
    own_identity = set(identity)
    ranked: list[tuple[float, str]] = []
    for option in options:
        label = str(option.get("label", ""))
        symbol = _COLOR_SYMBOL.get(label.strip().casefold())
        if symbol is None:
            ranked.append((0.0, label))
            continue
        score = (
            pending[symbol] * 10.0 + hand[symbol] * 1.0 + (0.5 if symbol in own_identity else 0.0)
        )
        ranked.append((score, label))
    return ranked


def named_choice_rank(
    options: list[dict[str, Any]],
    *,
    prompt: str,
    state: Mapping[str, Any],
    own_names: Iterable[str],
) -> list[tuple[float, str]]:
    """Rank a named choice (colour for protection, creature type, ...).

    Protection-style colour choices favour the colour most present among the
    opponents' permanents; a creature-type choice favours the type most common
    among the actor's own creatures. Anything else gets no preference.
    """
    text = prompt.casefold()
    actor_id = str(state.get("actor_id", ""))
    ranked: list[tuple[float, str]] = []
    if "color" in text or "colour" in text:
        tally: Counter[str] = Counter()
        mine = "protection" not in text and "from" not in text
        for player in players(state):
            if (str(player.get("player_id")) == actor_id) != mine:
                continue
            for item in _items(player.get("battlefield")):
                facts = card_facts(str(item.get("name") or ""))
                if facts is not None and not facts.is_land:
                    tally.update(facts.colors)
        for option in options:
            label = str(option.get("label", ""))
            symbol = _COLOR_SYMBOL.get(label.strip().casefold(), "")
            ranked.append((float(tally[symbol]), label))
        return ranked
    if "creature type" in text or "type" in text:
        types: Counter[str] = Counter()
        for name in own_names:
            facts = card_facts(name)
            if facts is not None and facts.is_creature:
                types.update(word.casefold() for word in facts.subtypes)
        for option in options:
            label = str(option.get("label", ""))
            ranked.append((float(types[label.strip().casefold()]), label))
        return ranked
    return [(0.0, str(option.get("label", ""))) for option in options]


__all__ = [
    "attack_score",
    "block_score",
    "board_summary",
    "card_view_fields",
    "color_choice_rank",
    "commander_names",
    "entry_value",
    "focus_defender",
    "hand_role_counts",
    "is_creature_entry",
    "is_land_entry",
    "named_choice_rank",
    "needed_colors",
    "permanent_owner",
    "priority_view_fields",
    "target_object_bonus",
]
