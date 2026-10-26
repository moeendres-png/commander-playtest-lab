"""A spell that costs less against the right target: pay for it only where it can be paid (#989 phase 5c).

Bitter Downfall ({3}{B}) "costs {3} less to cast if it targets a creature that was dealt damage this
turn". The engine offers the cast whenever the cheaper price is payable, because it cannot know the
target yet. The pilot then picked its target by value, took a creature that was not damaged, and the
payment asked for the full {3}{B}: 62 of the 93 cancelled payments in 24 recorded real games were
this card, and the removal was never cast.

This module reads that rule off the card text and says two things about the board: which of the
opponents' creatures were damaged this turn, and what the spell costs with and without the
discount. Pure functions of the rules-visible state; nothing here decides legality.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from commander_lab.agents.card_knowledge import card_facts

from .full_game_pilot_views import is_creature_entry, players

_DISCOUNT_RE = re.compile(
    r"This spell costs \{(?P<less>\d+)\} less to cast if it targets a creature that was dealt"
    r" damage this turn\.",
    re.IGNORECASE,
)
_SYMBOL_RE = re.compile(r"\{([^{}]*)\}")
_REDUCER_RE = re.compile(r"\bcosts?\b[^.]*\bless\b", re.IGNORECASE)


@dataclass(frozen=True)
class DamagedTargetDiscount:
    """The two prices of a spell that is cheaper against a creature dealt damage this turn."""

    full: str
    reduced: str


def _reduced_cost(mana_cost: str, less: int) -> str | None:
    """The printed cost with ``less`` taken off its generic part, or None when it cannot be read."""
    symbols = _SYMBOL_RE.findall(mana_cost)
    if not symbols:
        return None
    generic = sum(int(symbol) for symbol in symbols if symbol.isdigit())
    rest = [f"{{{symbol}}}" for symbol in symbols if not symbol.isdigit()]
    left = max(0, generic - less)
    return (f"{{{left}}}" if left else "") + "".join(rest) or "{0}"


def damaged_target_discount(name: str) -> DamagedTargetDiscount | None:
    """The prices of a spell whose only cost change is "costs {N} less ... a creature dealt damage".

    None for every other card, and for a card whose cost has other changes (the text would then
    name more than the one sentence), so the pilot keeps its old behaviour there.
    """
    facts = card_facts(name) if name else None
    if facts is None or not facts.mana_cost:
        return None
    match = _DISCOUNT_RE.search(facts.oracle_text)
    if match is None or "less" in _DISCOUNT_RE.sub("", facts.oracle_text):
        return None
    reduced = _reduced_cost(facts.mana_cost, int(match["less"]))
    return None if reduced is None else DamagedTargetDiscount(facts.mana_cost, reduced)


def board_lowers_costs(state: Mapping[str, object], actor_id: str) -> bool:
    """Whether a permanent of the actor's states that spells cost less (a cost reducer).

    The model counts the printed price only; a reducer on the table makes a price it calls
    unpayable payable, so the caller does not judge then.
    """
    for player in players(state):
        if str(player.get("player_id")) != actor_id:
            continue
        battlefield = player.get("battlefield")
        for item in battlefield if isinstance(battlefield, list) else ():
            rules = item.get("abilities") if isinstance(item, dict) else None
            for rule in rules if isinstance(rules, list) else ():
                if isinstance(rule, str) and _REDUCER_RE.search(rule):
                    return True
    return False


def damaged_opposing_creatures(state: Mapping[str, object], actor_id: str) -> frozenset[str]:
    """Object ids of the creatures the actor's opponents control that carry damage this turn.

    Damage stays marked on a creature until the turn ends, so marked damage is proof that the
    creature was dealt damage this turn. A creature that was dealt damage and healed (regenerated)
    is not counted: the answer errs towards "no discount".
    """
    found: set[str] = set()
    for player in players(state):
        if str(player.get("player_id")) == actor_id:
            continue
        battlefield = player.get("battlefield")
        for item in battlefield if isinstance(battlefield, list) else ():
            if not isinstance(item, dict):
                continue
            damage = item.get("damage")
            if (
                isinstance(damage, int)
                and not isinstance(damage, bool)
                and damage > 0
                and is_creature_entry(item)
            ):
                found.add(str(item.get("object_id") or ""))
    found.discard("")
    return frozenset(found)
