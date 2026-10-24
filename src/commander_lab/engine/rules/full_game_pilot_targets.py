"""Whose side a target belongs on, and how close a player is to dead (#989 phase 1).

XMage names the outcome of every targeted effect (``Outcome``, lower-cased by the bridge) and
flags it good or bad for whoever it lands on; its own computer player aims a good outcome at its
own side and a bad one at an opponent's. The pilot read only two of those names ("benefit" and
"detriment"), so a ``destroypermanent`` was aimed by value alone and could land on the pilot's own
Wizard token while an opponent's Birds of Paradise was on offer, and a +4/+4 or a Fertile Ground
went to an opponent's creature or land. Real games, nine precon pods: 44 of 172 target choices
with a side to take went to the wrong one.

Pure functions of the rules-visible request and state; nothing here decides legality.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from commander_lab.agents.card_knowledge import card_facts

Side = Literal["own", "opponent"]

# The outcomes whose engine flag says what the target gets. ``Outcome.isGood`` in the pinned
# XMage: good for the target's controller (aim at the own side) or bad (aim at an opponent's).
# Left out on purpose: neutral and vote (no side), copy, put-in-play and play-for-free (the
# target is a card to take from anywhere, not a side), extra turn and win (no target).
_OWN_SIDE = frozenset(
    {
        "benefit",
        "benefit_to_controller",
        "boostcreature",
        "addability",
        "gainlife",
        "becomecreature",
        "drawcard",
        "protect",
        "regenerate",
        "preventdamage",
        "redirectdamage",
        "transform",
        "untap",
    }
)
_OPPONENT_SIDE = frozenset(
    {
        "detriment",
        "detriment_to_controller",
        "damage",
        "destroypermanent",
        "exile",
        "tap",
        "unboostcreature",
        "loseability",
        "loselife",
        "gaincontrol",
        "discard",
        "returntohand",
        "preventcast",
        "removal",
    }
)

# Cards whose outcome label does not describe what the target gets, by (card, outcome). Collective
# Effort's "put a +1/+1 counter on each creature target player controls" is tagged with the
# ``unboostcreature`` of its first mode (its destroy modes are tagged right); Terastodon gives
# each destroyed permanent's controller a 3/3, so destroying lands of one's own is a real line and
# stays with the value ranking.
_SIDE_OVERRIDES: dict[tuple[str, str], Side | None] = {
    ("collective effort", "unboostcreature"): "own",
    ("terastodon", "destroypermanent"): None,
}

# "You draw X cards, where X is the creature cards in target player's graveyard" (Corpse Augur):
# the target is picked by what lies in its graveyard, not by whose side it is on.
_GRAVEYARD_COUNT = re.compile(r"in target player's graveyard")

# Damage and life loss are the outcomes where a total near zero decides the choice; discard,
# exile and the rest do not care how much life the target has left.
_LIFE_OUTCOMES = frozenset({"damage", "loselife"})

# Life at which the clock starts (a player above it is not close to anything) and the score of a
# player at zero life. The clock is quadratic in the distance below the start: slow near the
# start, fast near death. At 10 life it is worth a creature of value 6, at 5 life more than any.
_CLOCK_START = 20.0
_CLOCK_SCALE = 12.0

# The outcomes that take the target off the table whatever its toughness; a commander that is
# killing the actor is worth answering with these, not with a ping.
_REMOVAL_OUTCOMES = frozenset(
    {"destroypermanent", "exile", "returntohand", "gaincontrol", "removal", "detriment"}
)

# Commander damage: a commander that has dealt this much to the actor kills it on the next hit.
_COMMANDER_LETHAL = 21.0
_COMMANDER_CLOCK_WEIGHT = 6.0
_COMMANDER_LETHAL_BONUS = 8.0


def target_side(outcome: str, source_name: str = "") -> Side | None:
    """The side an effect's target should be on, or None when the outcome names none."""
    name = source_name.casefold()
    if (name, outcome) in _SIDE_OVERRIDES:
        return _SIDE_OVERRIDES[(name, outcome)]
    if outcome == "drawcard" and _counts_graveyard(name):
        return None
    if outcome in _OWN_SIDE:
        return "own"
    if outcome in _OPPONENT_SIDE:
        return "opponent"
    return None


def _counts_graveyard(source_name: str) -> bool:
    facts = card_facts(source_name) if source_name else None
    return facts is not None and _GRAVEYARD_COUNT.search(facts.oracle_text.casefold()) is not None


def life_clock(life: float) -> float:
    """How close a life total is to dead, growing faster the lower it falls."""
    below = max(0.0, _CLOCK_START - max(0.0, life)) / _CLOCK_START
    return _CLOCK_SCALE * below * below


def has_life_clock(outcome: str) -> bool:
    """Whether a player target of this outcome is ranked by how little life it has left."""
    return outcome in _LIFE_OUTCOMES


def _items(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def commander_damage_taken(state: Mapping[str, Any], actor_id: str, owner_id: str) -> float:
    """The most commander damage one commander of ``owner_id`` has dealt to the actor."""
    taken = 0.0
    for entry in _items(state.get("commander_status")):
        if str(entry.get("owner_id")) != owner_id:
            continue
        for row in _items(entry.get("commander_damage_to_player")):
            total = row.get("total")
            if (
                str(row.get("player_id")) == actor_id
                and isinstance(total, int | float)
                and not isinstance(total, bool)
            ):
                taken = max(taken, float(total))
    return taken


def commander_damage_dealt(
    state: Mapping[str, Any], actor_id: str, player_id: str
) -> dict[str, float]:
    """Commander damage the actor's commanders have dealt to one player, by commander name."""
    dealt: dict[str, float] = {}
    for entry in _items(state.get("commander_status")):
        if str(entry.get("owner_id")) != actor_id:
            continue
        for row in _items(entry.get("commander_damage_to_player")):
            total = row.get("total")
            if (
                str(row.get("player_id")) == player_id
                and isinstance(total, int | float)
                and not isinstance(total, bool)
            ):
                name = str(entry.get("name") or "")
                dealt[name] = max(dealt.get(name, 0.0), float(total))
    return dealt


def commander_clock_bonus(
    item: Mapping[str, Any],
    controller_id: str,
    state: Mapping[str, Any],
    actor_id: str,
    outcome: str,
) -> float:
    """What it is worth to answer an opposing commander that is already killing the actor.

    A commander that has dealt damage to the actor is on a clock: the bonus grows with the
    damage taken and jumps when one more hit of its current power makes 21. Zero for anything
    that is not a commander under its owner's control, and for the actor's own.
    """
    if controller_id == actor_id or outcome not in _REMOVAL_OUTCOMES:
        return 0.0
    name = str(item.get("name") or "").casefold()
    owns = any(
        str(entry.get("owner_id")) == controller_id
        and str(entry.get("name") or "").casefold() == name
        for entry in _items(state.get("commander_status"))
    )
    taken = commander_damage_taken(state, actor_id, controller_id) if owns else 0.0
    if taken <= 0.0:
        return 0.0
    power = item.get("power")
    next_hit = (
        float(power) if isinstance(power, int | float) and not isinstance(power, bool) else 0.0
    )
    bonus = _COMMANDER_CLOCK_WEIGHT * min(1.0, taken / _COMMANDER_LETHAL)
    if taken + max(0.0, next_hit) >= _COMMANDER_LETHAL:
        bonus += _COMMANDER_LETHAL_BONUS
    return bonus
