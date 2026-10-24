"""Blocks that keep the pilot alive: the damage of the whole declaration (#989 phase 3).

``block_score`` judges one blocker against one attacker. A chump block is worth it there only
when that single attacker is lethal or leaves five life, so a table where five attackers of 4 to
9 power face a pilot at 30 life gets no block at all, and the pilot is dead after combat. In 24
recorded real games 18 declarations left the pilot facing lethal damage; in 7 of them another
assignment of the same blockers would have survived.

The engine asks one blocker at a time, so the declaration is only known as it is asked: the
attackers each blocker may block, and what the earlier blockers of the same round took. This
module keeps that round and says, for a blocker asked while the damage still unblocked is lethal,
how much each of its options takes off the table.

Pure functions of the rules-visible request and state; nothing here decides legality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from commander_lab.agents.card_knowledge import card_facts, evasion

from .full_game_pilot_views import creature_power, creature_toughness_left, permanent_owner

# Commander damage that ends the game for the player that took it.
_COMMANDER_LETHAL = 21.0

# What one unit of damage taken off the table adds to a block's score, and the base that puts an
# urgent block above every judgment of the ordinary rule (whose best, a free kill, is 2.0 + 0.1
# per value point).
_URGENT_BASE = 1.0
_URGENT_PER_DAMAGE = 0.1
_COMMANDER_URGENCY = 5.0
# The ordinary score only breaks ties between blocks that take the same damage off the table.
_TIE_BREAK = 0.01


@dataclass
class BlockRound:
    """What is known of one block declaration while its blockers are asked one by one."""

    turn: object
    damage: dict[str, float] = field(default_factory=dict)
    trample: set[str] = field(default_factory=set)
    unblockable_alone: set[str] = field(default_factory=set)
    commander_lethal: set[str] = field(default_factory=set)
    # blocker id -> {attacker id: damage that block takes off the table}
    prevented: dict[str, dict[str, float]] = field(default_factory=dict)


def fresh_round(stored: BlockRound | None, turn: object) -> BlockRound:
    """The round of this turn: the stored one, or a new one when the turn moved on."""
    if stored is not None and stored.turn == turn:
        return stored
    return BlockRound(turn=turn)


def _items(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _life(state: Mapping[str, object], player_id: str) -> float | None:
    for player in _items(state.get("players")):
        if str(player.get("player_id")) == player_id:
            life = player.get("life")
            if isinstance(life, int | float) and not isinstance(life, bool):
                return float(life)
    return None


def _commander_damage_taken_from(
    state: Mapping[str, object], actor_id: str, name: str, owner_id: str
) -> float:
    """Damage the named commander of ``owner_id`` has dealt to the actor, 0 for anything else."""
    taken = 0.0
    for entry in _items(state.get("commander_status")):
        if str(entry.get("owner_id")) != owner_id or str(entry.get("name") or "") != name:
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


def note_attackers(
    round_: BlockRound,
    options: Sequence[Mapping[str, object]],
    state: Mapping[str, object],
) -> None:
    """Add the attackers these options name to the round, with the damage each deals."""
    actor_id = str(state.get("actor_id") or "")
    for option in options:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        attacker_id = str(meta.get("attacker_id") or "")
        found = permanent_owner(attacker_id, state)
        if not attacker_id or found is None:
            continue
        controller_id, attacker = found
        name = str(attacker.get("name") or "")
        keywords = evasion(card_facts(name), tuple(attacker.get("abilities") or ()))
        power = float(creature_power(attacker))
        damage = power * (2.0 if "double strike" in keywords else 1.0)
        round_.damage[attacker_id] = damage
        if "trample" in keywords:
            round_.trample.add(attacker_id)
        if "menace" in keywords:
            round_.unblockable_alone.add(attacker_id)
        if controller_id != actor_id:
            taken = _commander_damage_taken_from(state, actor_id, name, controller_id)
            if taken > 0.0 and taken + damage >= _COMMANDER_LETHAL:
                round_.commander_lethal.add(attacker_id)


def _remaining(round_: BlockRound, attacker_id: str, *, excluding: str) -> float:
    taken = sum(
        blocks.get(attacker_id, 0.0)
        for blocker_id, blocks in round_.prevented.items()
        if blocker_id != excluding
    )
    return max(0.0, round_.damage.get(attacker_id, 0.0) - taken)


def unblocked_damage(round_: BlockRound, *, excluding: str = "") -> float:
    """The damage still coming if no blocker but the earlier ones of the round blocks."""
    return sum(
        _remaining(round_, attacker_id, excluding=excluding) for attacker_id in round_.damage
    )


def is_pressing(round_: BlockRound, life: float, *, excluding: str = "") -> bool:
    """Whether the damage still unblocked kills the pilot (or a commander hit does)."""
    if unblocked_damage(round_, excluding=excluding) >= life:
        return True
    return any(
        _remaining(round_, attacker_id, excluding=excluding) > 0.0
        for attacker_id in round_.commander_lethal
    )


def urgent_scores(
    round_: BlockRound,
    blocker_id: str,
    options: Sequence[Mapping[str, object]],
    ordinary: Sequence[float],
    state: Mapping[str, object],
) -> list[float] | None:
    """Scores for this blocker's options when the declaration must take damage off the table.

    None while the damage still unblocked is survivable (the ordinary rule decides). Otherwise
    one score per option: the damage the block takes off the table (a trampler only loses the
    blocker's toughness), best first, with the ordinary score as the tie-break. An option on an
    attacker that is already blocked enough, or that cannot be blocked by one creature (menace),
    takes nothing off the table and is capped at the ordinary "do not block".
    """
    actor_id = str(state.get("actor_id") or "")
    life = _life(state, actor_id)
    if life is None or not is_pressing(round_, life, excluding=blocker_id):
        return None
    blocker = permanent_owner(blocker_id, state)
    toughness = float(creature_toughness_left(blocker[1])) if blocker is not None else 0.0
    scores: list[float] = []
    for option, base in zip(options, ordinary, strict=True):
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        attacker_id = str(meta.get("attacker_id") or "")
        remaining = _remaining(round_, attacker_id, excluding=blocker_id)
        if attacker_id in round_.unblockable_alone or remaining <= 0.0:
            scores.append(min(base, 0.0))
            continue
        taken = min(remaining, toughness) if attacker_id in round_.trample else remaining
        if taken <= 0.0:
            scores.append(min(base, 0.0))
            continue
        score = _URGENT_BASE + taken * _URGENT_PER_DAMAGE
        if attacker_id in round_.commander_lethal:
            score += _COMMANDER_URGENCY
        scores.append(score + _TIE_BREAK * max(-1.0, min(3.0, base)))
    return scores


def settled_scores(
    round_: BlockRound,
    blocker_id: str,
    options: Sequence[Mapping[str, object]],
    ordinary: Sequence[float],
    chump: Sequence[bool],
) -> list[float]:
    """The ordinary scores, except that a chump block does not go on an attacker already blocked.

    Each blocker is judged alone, so two creatures sent to chump the same lethal-looking attacker
    both die for one attacker's damage. A block that survives or kills is left alone (a second
    blocker that finishes the attacker is worth having).
    """
    scores: list[float] = []
    for option, base, is_chump in zip(options, ordinary, chump, strict=True):
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        attacker_id = str(meta.get("attacker_id") or "")
        settled = (
            is_chump
            and attacker_id in round_.damage
            and _remaining(round_, attacker_id, excluding=blocker_id) <= 0.0
        )
        scores.append(min(base, 0.0) if settled else base)
    return scores


def record_blocks(
    round_: BlockRound,
    blocker_id: str,
    picked: Sequence[Mapping[str, object]],
    state: Mapping[str, object],
) -> None:
    """Remember what this blocker's answer takes off the table, replacing an earlier answer."""
    blocker = permanent_owner(blocker_id, state)
    toughness = float(creature_toughness_left(blocker[1])) if blocker is not None else 0.0
    taken: dict[str, float] = {}
    for option in picked:
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        attacker_id = str(meta.get("attacker_id") or "")
        damage = round_.damage.get(attacker_id)
        if damage is None:
            continue
        taken[attacker_id] = min(damage, toughness) if attacker_id in round_.trample else damage
    round_.prevented[blocker_id] = taken
