"""Which loyalty ability of a planeswalker to use (#989 phase 6).

Every loyalty ability scored the same, so a planeswalker used whichever ability sorted last by
name, and that is the minus one: '-' sorts after '+'. Recorded real pod games, 24 seeds: whenever
a planeswalker offered a plus and a minus ability, the pilot took the minus one every time (83 of
83), Quintorius for -4 ("Spirits you control gain double strike") with no Spirit on the table in
43 of 63 uses and no creature able to attack in 31, and left it with one loyalty.

A player weighs what the ability does now against what it costs the planeswalker: a plus ability
is nearly free, a minus ability must buy something (a creature worth killing, cards, an emblem),
and one that ends the planeswalker must buy a lot. This module values the abilities of one offer
from their printed text and the actor's board.

Pure functions of Rules-visible content: nothing here decides legality.
"""

from __future__ import annotations

import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .full_game_pilot_views import entry_value, is_creature_entry, is_land_entry

# XMage writes the label as "<card> <em dash> <cost>: <text>" and spells a minus cost with a hyphen
# or the minus sign of the printed card; both are read (the hyphen last, so a class never forms a
# range).
_EM_DASH = chr(0x2014)
_MINUS = chr(0x2212) + chr(0x2013) + "-"
_LABEL = re.compile(
    rf"^(?P<source>.+?) {_EM_DASH} (?P<cost>[+{_MINUS}]?\d+|[+{_MINUS}]X): (?P<text>.*)$", re.S
)

_REMOVAL = re.compile(
    r"deals? (?:\d+|x) damage to (?:target|up to|each of up to)[^.]*"
    r"(?:creature|planeswalker|permanent)"
    r"|destroy target (?!land)|exile target (?!card from a graveyard)"
    r"|target creature gets -|gets -\d+/-\d+|gain control of target"
    r"|each opponent sacrifices|target player sacrifices"
    r"|return target [^.]* to its owner's hand|fights"
)
_DAMAGE = re.compile(r"deals? (\d+) damage to target creature")
_SHRINK = re.compile(r"target creature gets -\d+/-(\d+)")
_FACE = re.compile(
    r"damage to (?:any target|target player|each opponent)|each opponent loses|life total becomes"
)
_SWEEP = re.compile(r"damage to each creature|destroy all|each creature")
_DRAW = re.compile(
    r"draw (?:a|an|two|three|four|x|that many|\w+) cards?|look at the top|"
    r"reveal [^.]* put (?:it|them) into your hand|search your library|"
    r"exile the top card of your library"
)
_TOKENS = re.compile(r"create |amass|put [^.]* onto the battlefield")
_MANA = re.compile(r"add \{")
_TEMPORARY = re.compile(r"until end of turn")
_COUNTERS = re.compile(r"\+1/\+1 counter")
_ULTIMATE = re.compile(r"emblem|you win the game|return all creature cards")


# An ability worth less than this is not used: the loyalty it costs buys nothing.
LOYALTY_FLOOR = -0.35


@dataclass(frozen=True, slots=True)
class Loyalty:
    cost: int
    is_x: bool
    text: str


def parse_loyalty_label(label: str) -> Loyalty | None:
    """The loyalty cost and rules text of an option label, or None when it is no such ability."""
    match = _LABEL.match(label)
    if match is None:
        return None
    raw = match.group("cost")
    is_x = raw.endswith("X")
    digits = raw.lstrip("+" + _MINUS).rstrip("X")
    magnitude = int(digits) if digits.isdigit() else 0
    negative = raw[0] in _MINUS
    return Loyalty(-magnitude if negative else magnitude, is_x, match.group("text"))


def _entries(value: object) -> list[Mapping[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _loyalty_of(item: Mapping[str, object]) -> int | None:
    for counter in _entries(item.get("counters")):
        if str(counter.get("type", "")).casefold() == "loyalty":
            count = counter.get("count")
            return count if isinstance(count, int) else None
    return None


def _actor(state: Mapping[str, object]) -> Mapping[str, object] | None:
    actor_id = str(state.get("actor_id", ""))
    for player in _entries(state.get("players")):
        if player.get("is_actor") is True or str(player.get("player_id", "")) == actor_id:
            return player
    return None


def _attackers(actor: Mapping[str, object]) -> int:
    count = 0
    for item in _entries(actor.get("battlefield")):
        power = item.get("power")
        if (
            is_creature_entry(item)
            and item.get("tapped") is not True
            and isinstance(power, int)
            and power > 0
        ):
            count += 1
    return count


def _opposing_creatures(state: Mapping[str, object], actor_id: str) -> list[Mapping[str, object]]:
    found: list[Mapping[str, object]] = []
    for player in _entries(state.get("players")):
        if str(player.get("player_id", "")) == actor_id or player.get("has_lost") is True:
            continue
        found.extend(
            item
            for item in _entries(player.get("battlefield"))
            if is_creature_entry(item) and not is_land_entry(item)
        )
    return found


def _best_target_value(
    creatures: Sequence[Mapping[str, object]], state: Mapping[str, object]
) -> float:
    return max((entry_value(item, state) for item in creatures), default=0.0)


def _within_reach(
    creatures: Sequence[Mapping[str, object]], lowered: str
) -> list[Mapping[str, object]]:
    """The creatures an ability that deals damage or shrinks a creature by a fixed amount can kill."""
    found = _DAMAGE.search(lowered) or _SHRINK.search(lowered)
    if found is None:
        return list(creatures)
    reach = int(found.group(1))
    killable: list[Mapping[str, object]] = []
    for item in creatures:
        toughness = item.get("toughness")
        damage = item.get("damage")
        if (
            not isinstance(toughness, int)
            or toughness - (damage if isinstance(damage, int) else 0) <= reach
        ):
            killable.append(item)
    return killable


def ability_effect(text: str, state: Mapping[str, object], source_name: str) -> float:
    """What the ability does for the actor right now, about -0.6 (nothing to act on) to 2.0."""
    lowered = text.casefold().replace(source_name.casefold(), "this")
    actor = _actor(state)
    actor_id = str(state.get("actor_id", ""))
    opposing = _opposing_creatures(state, actor_id)
    attackers = _attackers(actor) if actor is not None else 0
    phase = str(state.get("phase", ""))
    if _ULTIMATE.search(lowered):
        return 1.2
    if _SWEEP.search(lowered):
        own = 0
        if actor is not None:
            own = sum(1 for item in _entries(actor.get("battlefield")) if is_creature_entry(item))
        return 0.9 if len(opposing) >= max(3, own + 2) else -0.3
    if _REMOVAL.search(lowered):
        targets = _within_reach(opposing, lowered)
        if targets:
            return 0.45 + min(1.55, _best_target_value(targets, state) / 5.0)
        return 0.3 if _FACE.search(lowered) else -0.6
    value = 0.0
    if _DRAW.search(lowered):
        value = max(value, 0.7)
    if _TOKENS.search(lowered):
        value = max(value, 0.75)
    if _MANA.search(lowered):
        turn = state.get("turn_number")
        value = max(value, 0.3 if isinstance(turn, int) and turn > 40 else 0.5)
    if _FACE.search(lowered):
        value = max(value, 0.4)
    if _COUNTERS.search(lowered):
        value = max(value, 0.5 if attackers else 0.1)
    if value > 0.0:
        return value
    if _TEMPORARY.search(lowered):
        # A bonus until end of turn is worth what the creatures that can still attack make of it.
        if phase == "postcombat_main" or attackers == 0:
            return -0.4
        return 0.15 + 0.2 * min(3, attackers)
    return 0.25


def ability_value(label: str, state: Mapping[str, object], source: Mapping[str, object]) -> float:
    """What using the ability is worth: its effect minus what it costs the planeswalker."""
    parsed = parse_loyalty_label(label)
    if parsed is None:
        return 0.0
    loyalty = _loyalty_of(source)
    effect = ability_effect(parsed.text, state, str(source.get("name") or ""))
    if parsed.cost > 0:
        return effect + 0.35 + 0.05 * parsed.cost
    if parsed.cost == 0 and not parsed.is_x:
        return effect + 0.1
    spent = 2 if parsed.is_x else -parsed.cost
    value = effect - 0.14 * spent
    if loyalty is not None and not parsed.is_x and loyalty + parsed.cost <= 0 and effect < 1.5:
        value -= 0.7
    return value


def _source_of(
    option: Mapping[str, object], state: Mapping[str, object]
) -> Mapping[str, object] | None:
    meta = option.get("metadata")
    source_id = str(meta.get("source_object_id", "")) if isinstance(meta, dict) else ""
    actor = _actor(state)
    if actor is None or not source_id:
        return None
    for item in _entries(actor.get("battlefield")):
        if str(item.get("object_id", "")) == source_id:
            return item
    return None


def loyalty_option_value(option: Mapping[str, object], state: Mapping[str, object]) -> float | None:
    """The value of one offered option when it is a loyalty ability of an own planeswalker."""
    parsed = parse_loyalty_label(str(option.get("label", "")))
    if parsed is None:
        return None
    source = _source_of(option, state)
    if source is None or _loyalty_of(source) is None:
        return None
    return ability_value(str(option.get("label", "")), state, source)


def choose_loyalty_ability(
    options: Sequence[Mapping[str, object]], state: Mapping[str, object], rng: random.Random
) -> Mapping[str, object] | None:
    """The best ability among the loyalty abilities of one offer, or None when it has none."""
    valued: list[tuple[float, Mapping[str, object]]] = []
    for option in options:
        value = loyalty_option_value(option, state)
        if value is not None:
            valued.append((round(value, 3), option))
    if not valued:
        return None
    best = max(value for value, _option in valued)
    top = sorted(
        (option for value, option in valued if value == best),
        key=lambda option: str(option.get("label", "")),
    )
    return rng.choice(top)
