"""Mana kept back for an instant that answers an opponent (#989 phase 4a-2).

A player with a counterspell or a cheap removal spell in hand does not always spend the last of
the mana in the own main phase: the open mana is what lets the instant be cast on an opponent's
turn. The pilot spent everything it could. In 24 recorded real games the seat held such an
instant at 660 passes of its own main phase and had too little mana left for it at 468 of them,
and not one instant was cast in an opponent's end step.

This module reads three things off the table: which counterspells and removal instants the seat
holds that are worth keeping mana for, whether a cast is a plan for the turn rather than an
optional extra, and how many turns in a row the seat has already held mana back. Pure functions
of the rules-visible state; whether a price can be paid is decided by the caller with the
payment plan.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from commander_lab.agents.card_knowledge import card_facts, card_roles
from commander_lab.models import CardRole

from .full_game_pilot_views import best_removal_target_value, board_summary, players

# An instant dearer than this is not worth holding the mana of a whole turn for.
HOLD_MAX_MANA_VALUE = 3
# A seat with fewer non-land permanents than this develops its board first.
THIN_BOARD = 2
# Own turns in a row a seat holds mana back before it develops one turn: an instant that never
# finds its moment (no target, no spell worth countering) must not stall the seat for good.
HOLD_TURNS_IN_A_ROW = 2
# Casts that are the plan of the turn, never held back: they make mana, or answer the table now.
_PLAN_ROLES = frozenset({CardRole.RAMP, CardRole.MANA_SOURCE, CardRole.WIPE})
_MAIN_STEPS = frozenset({"precombat_main", "postcombat_main"})


@dataclass(frozen=True)
class HeldInstant:
    """A counterspell or removal instant in the seat's hand."""

    name: str
    kind: Literal["counter", "removal"]


def _actor(state: Mapping[str, object], actor_id: str) -> Mapping[str, object]:
    for player in players(state):
        if str(player.get("player_id")) == actor_id:
            return player
    return {}


def own_main_phase(state: Mapping[str, object]) -> bool:
    """The seat's own main phase, with nothing on the stack."""
    return (
        str(state.get("active_player_id", "")) == str(state.get("actor_id", ""))
        and str(state.get("step", "")).casefold() in _MAIN_STEPS
        and not state.get("stack")
    )


def thin_board(state: Mapping[str, object], actor_id: str) -> bool:
    """Whether the seat has too few non-land permanents to hold mana back yet."""
    nonland = board_summary(_actor(state, actor_id))["nonland_permanents"]
    return nonland < THIN_BOARD


def _opponent_holds_cards(state: Mapping[str, object], actor_id: str) -> bool:
    """Whether an opponent that is still in the game has a card in hand to cast."""
    for player in players(state):
        if str(player.get("player_id")) == actor_id or player.get("has_lost") is True:
            continue
        count = player.get("hand_count")
        if not isinstance(count, int) or isinstance(count, bool) or count > 0:
            return True
    return False


def held_instants(state: Mapping[str, object], actor_id: str) -> tuple[HeldInstant, ...]:
    """The counterspells and removal instants in the seat's hand that have a use right now.

    A counterspell is worth keeping mana for while an opponent has cards to cast, a removal
    spell while an opposing permanent is there to hit. Draw spells, protection and flash
    creatures are better cast with the mana that is left over, so they do not hold anything.
    Cheapest first.
    """
    hand = _actor(state, actor_id).get("hand")
    found: list[tuple[float, HeldInstant]] = []
    for item in hand if isinstance(hand, list) else ():
        facts = card_facts(str(item.get("name") or "")) if isinstance(item, dict) else None
        if (
            facts is None
            or not facts.is_instant_speed
            or facts.is_land
            or facts.is_creature
            or facts.mana_value > HOLD_MAX_MANA_VALUE
        ):
            continue
        roles = card_roles(facts)
        if CardRole.COUNTER in roles:
            if _opponent_holds_cards(state, actor_id):
                found.append((facts.mana_value, HeldInstant(facts.name, "counter")))
        elif (
            CardRole.REMOVAL in roles
            and (best_removal_target_value(facts, state, actor_id) or 0.0) > 0
        ):
            found.append((facts.mana_value, HeldInstant(facts.name, "removal")))
    return tuple(held for _, held in sorted(found, key=lambda pair: (pair[0], pair[1].name)))


def is_plan_of_the_turn(
    state: Mapping[str, object], actor_id: str, source_name: str, source_object_id: str
) -> bool:
    """Whether a cast is the seat's plan for the turn: its commander, mana, a wipe, an instant.

    An instant is not judged here: the timing rules and the pilot's own scores place it. A card
    the pilot has no facts about is not judged either.
    """
    command = _actor(state, actor_id).get("command")
    for item in command if isinstance(command, list) else ():
        if (
            isinstance(item, dict)
            and source_object_id
            and item.get("object_id") == source_object_id
        ):
            return True
    facts = card_facts(source_name)
    if facts is None or facts.is_instant_speed:
        return True
    return bool(card_roles(facts).keys() & _PLAN_ROLES)


def holds_in_a_row(record: tuple[int, int] | None, turn: int, seats: int) -> int:
    """How many own turns before this one the seat held mana back, one after the other.

    ``record`` is the seat's last hold: the length of the run and the turn number it ended on.
    A turn number at most one round after that is the seat's next own turn.
    """
    if record is None:
        return 0
    run, last = record
    if last == turn:
        return run - 1
    return run if 0 < turn - last <= seats else 0
