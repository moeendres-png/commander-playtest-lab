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
from functools import lru_cache
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


_SEAT_LABEL = re.compile(r"Full Game Seat (\d+)")


def resolve_player(
    raw_id: str | None, label: str, state: Mapping[str, Any]
) -> dict[str, Any] | None:
    """The pilot-view player an engine option refers to.

    The actor-scoped state names every other player by a seat token ("op-N"),
    while option metadata (defenders, player targets) carries the engine's own
    player id. Those never match, so a player is also found by the seat in the
    option's Rules-visible label ("Full Game Seat N" is seat N-1).
    """
    for player in players(state):
        if raw_id and str(player.get("player_id", "")) == raw_id:
            return player
    found = _SEAT_LABEL.findall(label or "")
    if not found:
        return None
    seat = int(found[-1]) - 1
    return next((p for p in players(state) if p.get("seat") == seat), None)


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
    creature = is_creature_entry(item)
    power = item.get("power") if creature and isinstance(item.get("power"), int) else None
    toughness = (
        item.get("toughness") if creature and isinstance(item.get("toughness"), int) else None
    )
    return _entry_value(name, power, toughness, name.casefold() in commander_names(state))


@lru_cache(maxsize=16384)
def _entry_value(name: str, power: int | None, toughness: int | None, is_commander: bool) -> float:
    # A pure function of printed facts and board P/T, asked for every permanent
    # on every decision: computed once per distinct permanent shape.
    return permanent_value(
        card_facts(name), power=power, toughness=toughness, is_commander=is_commander
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


def _alive(player: Mapping[str, Any]) -> bool:
    life = player.get("life")
    return (
        player.get("has_lost") is not True
        and player.get("in_game") is not False
        and (not isinstance(life, int | float) or life > 0)
    )


def player_threat(player: Mapping[str, Any], state: Mapping[str, Any]) -> float:
    """How dangerous one player is to the rest of the table right now.

    What a Commander player looks at when deciding who the archenemy is: the
    value of the permanents on the board (a commander, engines, big creatures
    and planeswalkers count most, lands little), the creature power that can
    attack next turn, the cards still in hand, and the mana to cast them. A
    player close to death threatens less, because the table can finish them.
    """
    if not _alive(player):
        return 0.0
    board_value = 0.0
    lands = 0
    for item in _items(player.get("battlefield")):
        if is_land_entry(item):
            lands += 1
            continue
        board_value += min(12.0, entry_value(item, state))
    power = board_summary(player)["creature_power"]
    hand = player.get("hand_count")
    hand_count = (
        hand
        if isinstance(hand, int) and not isinstance(hand, bool)
        else len(_items(player.get("hand")))
    )
    life = player.get("life")
    life_value = float(life) if isinstance(life, int | float) else 40.0
    threat = board_value * 0.35 + power * 0.25 + lands * 0.15 + hand_count * 0.3
    return threat * (0.6 + 0.4 * min(1.0, max(0.0, life_value) / 40.0))


def table_threats(state: Mapping[str, Any]) -> dict[str, float]:
    """``player_threat`` of every player still in the game, the actor included."""
    return {
        str(player.get("player_id", "")): player_threat(player, state)
        for player in players(state)
        if _alive(player)
    }


def archenemy(state: Mapping[str, Any]) -> str | None:
    """The player the table should be working against, when one clearly leads.

    Clearly means a threat at least a quarter above the next player's; an even
    table has no archenemy (ties are broken by nothing, so no engine order
    leaks in).
    """
    ranked = sorted(table_threats(state).items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] < 4.0:
        return None
    if len(ranked) > 1 and ranked[0][1] < ranked[1][1] * 1.25:
        return None
    return ranked[0][0]


def boardwipe_risk(state: Mapping[str, Any]) -> float:
    """Chance-like 0..1 pressure that the actor's board is the one a wipe answers.

    Hidden hands make this an estimate: the further the actor's board is ahead
    of the average opponent's, and the more cards opponents still hold, the
    likelier someone answers it with a wipe.
    """
    actor_id = str(state.get("actor_id", ""))
    own = 0.0
    others: list[float] = []
    hands: list[int] = []
    for player in players(state):
        if not _alive(player):
            continue
        value = sum(
            min(12.0, entry_value(item, state))
            for item in _items(player.get("battlefield"))
            if not is_land_entry(item)
        )
        if str(player.get("player_id", "")) == actor_id:
            own = value
        else:
            others.append(value)
            hand = player.get("hand_count")
            hands.append(hand if isinstance(hand, int) and not isinstance(hand, bool) else 0)
    if not others or own <= 0.0:
        return 0.0
    lead = (own - sum(others) / len(others)) / (own + 4.0)
    cards = min(1.0, (sum(hands) / len(hands)) / 4.0)
    return max(0.0, min(1.0, lead * cards))


def stack_pressure(state: Mapping[str, Any], own_stack_names: frozenset[str]) -> float:
    """0..1: how much the opponents' objects on the stack call for an answer now."""
    total = 0.0
    for item in _items(state.get("stack")):
        name = str(item.get("name") or "")
        if name.casefold() in own_stack_names:
            continue
        facts = card_facts(name)
        total += facts.mana_value if facts is not None else 2.0
    return min(1.0, total / 8.0)


def creature_board_value(player: Mapping[str, Any], state: Mapping[str, Any]) -> float:
    """Summed value of one player's creatures: what a creature wipe destroys."""
    return sum(
        min(12.0, entry_value(item, state))
        for item in _items(player.get("battlefield"))
        if is_creature_entry(item)
    )


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


def untapped_mana_estimate(state: Mapping[str, Any]) -> float:
    """Mana the actor can still make this turn: floating mana plus untapped lands."""
    actor_id = str(state.get("actor_id", ""))
    actor = next((p for p in players(state) if str(p.get("player_id")) == actor_id), None)
    if actor is None:
        return 0.0
    pool = actor.get("mana_pool")
    floating = (
        sum(float(v) for v in pool.values() if isinstance(v, int | float))
        if isinstance(pool, dict)
        else 0.0
    )
    lands = sum(
        1
        for item in _items(actor.get("battlefield"))
        if is_land_entry(item) and item.get("tapped") is not True
    )
    return max(0.0, floating) + lands


_REACTIVE_ROLES = frozenset(
    {CardRole.REMOVAL, CardRole.COUNTER, CardRole.PROTECTION, CardRole.DRAW, CardRole.SELECTION}
)


def _instant_timing(
    facts: CardFacts, roles: Mapping[CardRole, float], state: Mapping[str, Any]
) -> float:
    """Instant-speed cards are played on the opponents' turns, the way players do.

    An instant that removes, draws or protects is better cast at the end of an
    opponent's turn than in one's own main phase: the mana stays up as a threat
    of interaction, and nothing is revealed before the opponents commit. With
    something on the stack the card answers it and timing does not apply.
    """
    if not facts.is_instant_speed or state.get("stack"):
        return 0.0
    if not (roles.keys() & _REACTIVE_ROLES) and not facts.is_creature:
        return 0.0
    own_turn = str(state.get("active_player_id", "")) == str(state.get("actor_id", ""))
    if own_turn and "main" in str(state.get("phase", "")).casefold():
        return -0.5
    if not own_turn and str(state.get("phase", "")).casefold() == "end":
        return 0.6
    return 0.0


def _curve_bonus(cost: float, state: Mapping[str, Any]) -> float:
    """Reward spending this turn's mana in the actor's own main phase.

    The pilot's mana efficiency (value per mana) on its own prefers the
    one-drop over the five-drop with five lands open and leaves mana unused.
    A spell that uses more of the mana available now gets up to +1.0 impact.
    """
    if str(state.get("active_player_id", "")) != str(state.get("actor_id", "")):
        return 0.0
    if "main" not in str(state.get("phase", "")).casefold():
        return 0.0
    available = untapped_mana_estimate(state)
    if cost <= 0.0 or available <= 0.0:
        return 0.0
    return 1.0 * min(cost, available) / available


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
        curve = _curve_bonus(float(fields["mana_cost"]), state)
        if curve > 0.0:
            fields["immediate_impact"] = min(2.0, float(fields["immediate_impact"]) + curve)
            extra["curve_bonus"] = round(curve, 3)
        timing = _instant_timing(facts, roles, state)
        if timing:
            fields["immediate_impact"] = min(
                2.0, max(0.0, float(fields["immediate_impact"]) + timing)
            )
            extra["instant_timing"] = timing
        withhold = _spell_withhold_reason(facts, roles, state, actor_id, own_stack_names)
        if CardRole.WIPE in roles and withhold is None:
            withhold = _wipe_withhold_reason(facts, state, actor_id)
        if CardRole.COUNTER in roles and withhold is None:
            worth = counter_target_worth(state, own_stack_names)
            if worth is not None:
                # What a counterspell is worth is the spell it answers.
                fields["threat_score"] = worth
        if CardRole.REMOVAL in roles and withhold is None:
            best = best_removal_target_value(facts, state, actor_id)
            if best is not None:
                # Removal is worth what it removes: a commander or an engine
                # is a far better use than a token.
                extra["best_target_value"] = round(best, 3)
                fields["immediate_impact"] = min(
                    2.0, float(fields["immediate_impact"]) + min(1.0, best / 8.0)
                )
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
    if CardRole.COUNTER in roles and "counter target" in text:
        worth = counter_target_worth(state, own_stack_names)
        if worth is not None and worth < _COUNTER_WORTH:
            return "counter_target_not_worth_it"
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
    if only_removal:
        best = best_removal_target_value(facts, state, actor_id)
        if best is not None and best < _REMOVAL_WORTH:
            # Players keep spot removal for a real threat instead of
            # spending it on a token or a mana creature.
            return "no_worthy_removal_target"
    return None


# A permanent below this value (about a vanilla two-drop) is not worth a removal
# spell; a spell below this mana value (with no wipe, removal or finisher role)
# is not worth a counterspell.
_REMOVAL_WORTH = 3.0
_COUNTER_WORTH = 3.0


def best_removal_target_value(
    facts: CardFacts, state: Mapping[str, Any], actor_id: str
) -> float | None:
    """Value of the best opposing permanent this removal could hit, or None if unknown."""
    text = facts.oracle_text.casefold()
    if "target creature" in text:
        wanted = is_creature_entry
    elif re.search(r"target (nonland )?(artifact|enchantment|permanent|planeswalker)", text):

        def wanted(item: Mapping[str, Any]) -> bool:
            return not is_land_entry(item)

    else:
        return None
    values = [
        entry_value(item, state)
        for player in players(state)
        if str(player.get("player_id")) != actor_id and _alive(player)
        for item in _items(player.get("battlefield"))
        if wanted(item)
    ]
    return max(values, default=0.0)


def counter_target_worth(state: Mapping[str, Any], own_stack_names: frozenset[str]) -> float | None:
    """Worth of the opponents' top spell on the stack, or None when unknown."""
    commanders = commander_names(state)
    for item in reversed(_items(state.get("stack"))):
        name = str(item.get("name") or "")
        if name.casefold() in own_stack_names:
            continue
        if name.casefold() in commanders:
            return 10.0
        facts = card_facts(name)
        if facts is None:
            return None
        roles = card_roles(facts)
        if roles.keys() & {CardRole.WIPE, CardRole.FINISHER, CardRole.REMOVAL}:
            return max(_COUNTER_WORTH, facts.mana_value)
        return facts.mana_value
    return None


def _wipe_withhold_reason(facts: CardFacts, state: Mapping[str, Any], actor_id: str) -> str | None:
    """A wipe is for when the table is ahead of the actor, not the other way round."""
    text = facts.oracle_text.casefold()
    one_sided = "you don't control" in text or "your opponents control" in text
    mine = 0.0
    theirs: list[float] = []
    for player in players(state):
        if not _alive(player):
            continue
        value = creature_board_value(player, state)
        if str(player.get("player_id")) == actor_id:
            mine = value
        else:
            theirs.append(value)
    total = sum(theirs)
    if total < 6.0:
        return "wipe_nothing_worth_wiping"
    if one_sided:
        return None
    if max(theirs, default=0.0) <= mine * 1.25 + 2.0 and total <= mine * 2.5 + 6.0:
        return "wipe_hurts_own_board_most"
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
    """The opponent to concentrate attacks on.

    Commander players pressure the archenemy (the biggest threat at the table)
    and finish off a player they can actually remove; spreading damage evenly
    lets everyone survive. So: threat, plus a bonus that grows as a player's
    life gets low. Ties fall to the lower life, then the player id (stable,
    Rules-visible order).
    """
    actor_id = str(state.get("actor_id", ""))
    candidates: list[tuple[float, float, str]] = []
    for player in players(state):
        player_id = str(player.get("player_id", ""))
        life = player.get("life")
        if player_id == actor_id or not isinstance(life, int | float) or not _alive(player):
            continue
        finish = max(0.0, 40.0 - float(life)) * 0.12 + max(0.0, 20.0 - float(life)) * 0.25
        candidates.append((-(player_threat(player, state) + finish), float(life), player_id))
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
    found = permanent_owner(attacker_id, state)
    defender = resolve_player(
        str(meta.get("defender_id") or ""), str(option.get("label") or ""), state
    )
    defender_id = str(defender.get("player_id", "")) if defender is not None else ""
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
    lethal = not able and damage >= life_value
    if lethal:
        score += 3.0  # lethal through an empty or evaded board
    elif "vigilance" not in keywords and _crack_back_danger(state) and toughness >= 2:
        # Crack-back: when one opponent's creatures could take the actor low on
        # their next turn, a creature that can block stays home unless this
        # attack wins something outright.
        score -= 1.2
    score += max(0.0, 20.0 - life_value) * 0.03
    if score > 0.0 and defender_id == focus_defender(state):
        # Spread-out damage lets everyone survive; pressure on one opponent
        # removes a player and shortens the game.
        score += 0.6
    return score, {"attack_power": power, "defender_blockers": len(able)}


def _crack_back_danger(state: Mapping[str, Any]) -> bool:
    """True when one opponent's creatures could bring the actor to 10 life or less."""
    actor_id = str(state.get("actor_id", ""))
    actor = next((p for p in players(state) if str(p.get("player_id")) == actor_id), None)
    if actor is None:
        return False
    life = actor.get("life")
    life_value = float(life) if isinstance(life, int | float) else 40.0
    danger = max(
        (
            board_summary(player)["creature_power"]
            for player in players(state)
            if str(player.get("player_id")) != actor_id and _alive(player)
        ),
        default=0.0,
    )
    return danger > 0.0 and life_value - danger <= 10.0


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
    "archenemy",
    "attack_score",
    "best_removal_target_value",
    "block_score",
    "board_summary",
    "boardwipe_risk",
    "card_view_fields",
    "color_choice_rank",
    "commander_names",
    "counter_target_worth",
    "creature_board_value",
    "entry_value",
    "focus_defender",
    "hand_role_counts",
    "is_creature_entry",
    "is_land_entry",
    "named_choice_rank",
    "needed_colors",
    "permanent_owner",
    "player_threat",
    "priority_view_fields",
    "resolve_player",
    "stack_pressure",
    "table_threats",
    "target_object_bonus",
    "untapped_mana_estimate",
]
