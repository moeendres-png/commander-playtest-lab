"""A spell with a mandatory extra mana cost is cast only where both prices can be paid (#1067).

Louisoix's Sacrifice ({U}) says "As an additional cost to cast this spell, sacrifice a legendary
creature or pay {2}." The engine offers the cast while the printed {U} is payable and asks for the
extra cost afterwards. The pilot cast it with one untapped land, paid the {U}, was asked for the
{2} and cancelled: 19 of the 29 cancelled payments in 24 recorded real games on main were this
card, each with the mana of the first payment gone and the counterspell never cast.

This module reads that rule off the card text. Pure functions of the card text and the
rules-visible state; nothing here decides legality, and a card or alternative it cannot read is
left to the pilot.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from commander_lab.agents.card_knowledge import card_facts

from .full_game_pilot_views import players

_EXTRA_COST_RE = re.compile(
    r"As an additional cost to cast this spell, (?P<alt>[^.\n{}]*? or )?pay"
    r" (?P<cost>(?:\{[^{}]+\})+)\s*(?:\.|$)",
    re.IGNORECASE | re.MULTILINE,
)
_REVEAL_RE = re.compile(r"^reveal an? (?P<kind>[\w' -]+?) card from your hand or $", re.IGNORECASE)
_SACRIFICE_RE = re.compile(r"^sacrifice [^.\n]* or $", re.IGNORECASE)


@dataclass(frozen=True)
class AdditionalManaCost:
    """The mandatory extra mana of a spell and the free alternative the text names, if any."""

    mana: str
    reveal_kind: str | None = None


def additional_mana_cost(name: str) -> AdditionalManaCost | None:
    """The extra mana a spell must pay on top of its printed cost, from its text alone.

    Read are "pay {N}", "sacrifice ... or pay {N}" and "reveal a <kind> card from your hand or pay
    {N}". The pilot never picks a sacrifice to save mana, so that alternative is not counted as
    one. None for every other card, including an optional cost ("you may pay") and an alternative
    the model does not know ("discard a card or pay {1}").
    """
    facts = card_facts(name) if name else None
    if facts is None or not facts.mana_cost:
        return None
    match = _EXTRA_COST_RE.search(facts.oracle_text)
    if match is None:
        return None
    alternative = match["alt"]
    if alternative is None or _SACRIFICE_RE.match(alternative):
        return AdditionalManaCost(match["cost"])
    reveal = _REVEAL_RE.match(alternative)
    if reveal is None:
        return None
    return AdditionalManaCost(match["cost"], reveal["kind"].casefold())


def reveal_alternative_in_hand(
    state: Mapping[str, object], actor_id: str, spell_name: str, kind: str
) -> bool | None:
    """Whether the actor's hand holds, besides the spell, a card of ``kind`` to reveal.

    None when the hand is not reported, so the caller does not judge.
    """
    actor = next((p for p in players(state) if str(p.get("player_id")) == actor_id), None)
    hand = actor.get("hand") if actor is not None else None
    if not isinstance(hand, list):
        return None
    names = [str(card.get("name") or "") for card in hand if isinstance(card, dict)]
    if spell_name in names:
        names.remove(spell_name)
    for name in names:
        facts = card_facts(name)
        if facts is None:
            return None
        if kind in facts.type_line.casefold():
            return True
    return False
