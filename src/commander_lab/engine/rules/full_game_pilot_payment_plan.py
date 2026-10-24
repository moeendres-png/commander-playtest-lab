"""Mana payments that stay completable: a colour-aware look at the payment still ahead (#989 phase 5).

The pilot pays one engine prompt at a time. Its source order knows colours (scarcest first), but
the check that feeds pooled mana into a costed ability (a filter land, a signet) only counts
mana, not colours. A Mountain tapped for {R} and spent on the {1} of a {1}{W} cost leaves the
Rugged Prairie unable to pay its own {R/W}, and the payment is cancelled: in 24 recorded real
games 136 of 3,599 payments ended in "Cancel mana payment".

This module answers one question about an offer: after which of the offered options can the
rest of the cost still be paid? It reads only what the engine shows (the unpaid cost, the pool
and the text of each mana ability) and makes no legality claim; the engine still accepts or
refuses whatever is chosen. Anything it cannot read (a cost it does not know, an ability that
taps another creature, a count that depends on counters) makes it answer None, and the caller
keeps its existing choice. Where it cannot be sure it is optimistic, so a dead end it reports is
a dead end.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_TYPES = "wubrgc"
_SYMBOL = re.compile(r"\{([^}]*)\}")
_POOL_TYPES = {
    "white": "w",
    "blue": "u",
    "black": "b",
    "red": "r",
    "green": "g",
    "colorless": "c",
}
_COUNT_WORDS = {"one": 1, "two": 2, "three": 3}
_NODE_CAP = 20000

_FIXED_MANA = re.compile(r"add ((?:\{[wubrgc]\})+)", re.IGNORECASE)
_ANY_COLOR = re.compile(r"add (one|two|three) mana of any (?:one )?colou?r", re.IGNORECASE)
_COMBINATION = re.compile(
    r"add (one|two|three) mana in any combination of (?P<kinds>(?:\{[wubrgc]\}[, ]*(?:and/or )?)+)",
    re.IGNORECASE,
)
_SACRIFICE_COST = re.compile(r"sacrifice this \w+", re.IGNORECASE)
_LIFE_COST = re.compile(r"pay \d+ life", re.IGNORECASE)

Pip = frozenset[str]
# generic mana still owed, the coloured and hybrid pips still owed, mana in the pool by type
# (indexed like _TYPES), and the sources already used
_State = tuple[int, tuple[Pip, ...], tuple[int, ...], frozenset[str]]


@dataclass(frozen=True)
class Ability:
    """One offered mana ability: what activating it costs and what it adds to the pool."""

    source: str
    generic: int
    pips: tuple[Pip, ...]
    slots: tuple[Pip, ...]


class _Capped(Exception):
    """The search outgrew its budget; the offer cannot be judged."""


def _cost_symbol(symbol: str) -> tuple[int, Pip | None] | None:
    """(generic mana, pip) a cost symbol stands for; (0, None) for a free one; None if unknown."""
    text = symbol.casefold()
    if text.isdigit():
        return int(text), None
    parts = text.split("/")
    if "p" in parts:
        return 0, None
    if all(len(part) == 1 and part in _TYPES for part in parts):
        return 0, frozenset(parts)
    return None


def colour_letter(label: str) -> str | None:
    """The mana letter ("wubrgc") a colour name or symbol stands for: "Red", "{R}" or "R"."""
    text = label.strip().strip("{}").casefold()
    if text in _TYPES and len(text) == 1:
        return text
    return _POOL_TYPES.get(text)


def parse_unpaid(unpaid_mana: str) -> tuple[int, tuple[Pip, ...]] | None:
    """The generic amount and pips of an unpaid cost, or None for X, snow, energy and the like."""
    generic = 0
    pips: list[Pip] = []
    for symbol in _SYMBOL.findall(unpaid_mana):
        read = _cost_symbol(symbol)
        if read is None:
            return None
        generic += read[0]
        if read[1] is not None:
            pips.append(read[1])
    return generic, tuple(sorted(pips, key=sorted))


def _slots_of(effect: str) -> tuple[Pip, ...] | None:
    sentence = re.split(r"\.\s|\.$", effect, maxsplit=1)[0].strip()
    fixed = _FIXED_MANA.fullmatch(sentence)
    if fixed is not None:
        return tuple(frozenset(symbol.casefold()) for symbol in _SYMBOL.findall(fixed.group(1)))
    anycolor = _ANY_COLOR.match(sentence)
    if anycolor is not None:
        return (frozenset("wubrg"),) * _COUNT_WORDS[anycolor.group(1).casefold()]
    combination = _COMBINATION.match(sentence)
    if combination is not None:
        kinds = frozenset(symbol.casefold() for symbol in _SYMBOL.findall(combination["kinds"]))
        return (kinds,) * _COUNT_WORDS[combination.group(1).casefold()]
    return None


def parse_ability(option: Mapping[str, object]) -> Ability | None:
    """Read a mana ability from the engine's own text; None when any part is not understood."""
    label = str(option.get("label") or "")
    text = label.partition(" — ")[2] or label
    cost_text, colon, effect = text.partition(": ")
    if not colon:
        return None
    generic = 0
    pips: list[Pip] = []
    consumes_source = False
    for token in (part.strip() for part in cost_text.split(", ")):
        if token.casefold() == "{t}" or _SACRIFICE_COST.fullmatch(token):
            consumes_source = True
        elif _LIFE_COST.fullmatch(token):
            continue
        elif token.startswith("{") and token.endswith("}") and _SYMBOL.fullmatch(token):
            read = _cost_symbol(token[1:-1])
            if read is None:
                return None
            generic += read[0]
            if read[1] is not None:
                pips.append(read[1])
        else:
            return None
    slots = _slots_of(effect)
    if not consumes_source or slots is None:
        return None
    metadata = option.get("metadata")
    meta = metadata if isinstance(metadata, dict) else {}
    # Without the engine's source id every offer counts as its own source: that errs towards
    # more mana, never towards a false dead end.
    source = str(meta.get("source_object_id") or option.get("option_id") or label)
    return Ability(source, generic, tuple(pips), slots)


def _remove_one(pips: tuple[Pip, ...], pip: Pip) -> tuple[Pip, ...]:
    items = list(pips)
    items.remove(pip)
    return tuple(items)


def _spend(generic: int, pips: tuple[Pip, ...], kind: str) -> tuple[int, tuple[Pip, ...]] | None:
    """What one mana of ``kind`` pays: a pip it fits (the least flexible), else generic."""
    fits = [pip for pip in set(pips) if kind in pip]
    if fits:
        best = min(fits, key=lambda pip: (len(pip), sorted(pip)))
        return generic, _remove_one(pips, best)
    if generic > 0:
        return generic - 1, pips
    return None


def _take(pool: tuple[int, ...], kind: str) -> tuple[int, ...]:
    index = _TYPES.index(kind)
    return (*pool[:index], pool[index] - 1, *pool[index + 1 :])


def _give(pool: tuple[int, ...], kinds: Sequence[str]) -> tuple[int, ...]:
    counts = list(pool)
    for kind in kinds:
        counts[_TYPES.index(kind)] += 1
    return tuple(counts)


def _pay_cost(
    ability: Ability, pool: tuple[int, ...], wanted: frozenset[str]
) -> list[tuple[int, ...]]:
    """Pools left after paying an ability's cost from the pool (several when a pip has a choice)."""
    pools = [pool]
    for pip in ability.pips:
        pools = [
            _take(current, kind)
            for current in pools
            for kind in sorted(pip)
            if current[_TYPES.index(kind)] > 0
        ]
        if not pools:
            return []
    result: list[tuple[int, ...]] = []
    for current in pools:
        left = current
        for _ in range(ability.generic):
            owned = [kind for kind in _TYPES if left[_TYPES.index(kind)] > 0]
            if not owned:
                break
            # generic mana is paid with whatever the rest of the cost needs least
            kind = min(owned, key=lambda item: (item in wanted, -left[_TYPES.index(item)], item))
            left = _take(left, kind)
        else:
            result.append(left)
    return result


def _produced(ability: Ability, useful: frozenset[str]) -> list[tuple[str, ...]]:
    """What an ability can add, one tuple per distinct outcome that could matter."""
    outcomes: set[tuple[str, ...]] = {()}
    for slot in ability.slots:
        kinds = sorted(slot & useful) or [min(slot)]
        outcomes = {tuple(sorted((*done, kind))) for done in outcomes for kind in kinds}
    return sorted(outcomes)


def _activate(state: _State, ability: Ability, useful: frozenset[str]) -> list[_State]:
    generic, pips, pool, used = state
    if ability.source in used:
        return []
    wanted = frozenset().union(*pips) if pips else frozenset()
    states: list[_State] = []
    for paid in _pay_cost(ability, pool, wanted):
        for produced in _produced(ability, useful):
            states.append((generic, pips, _give(paid, produced), used | {ability.source}))
    return states


def _completes(start: _State, abilities: Sequence[Ability], useful: frozenset[str]) -> bool:
    seen: dict[_State, bool] = {}
    nodes = 0

    def key(state: _State) -> _State:
        generic, pips, pool, used = state
        return generic, tuple(sorted(pips, key=sorted)), pool, used

    def solve(state: _State) -> bool:
        nonlocal nodes
        generic, pips, pool, used = state
        if generic == 0 and not pips:
            return True
        cached = seen.get(key(state))
        if cached is not None:
            return cached
        nodes += 1
        if nodes > _NODE_CAP:
            raise _Capped
        owed = generic + len(pips)
        supply = sum(pool) + sum(len(a.slots) for a in abilities if a.source not in used)
        outcome = False
        if supply >= owed:
            for kind in _TYPES:
                if pool[_TYPES.index(kind)] > 0:
                    paid = _spend(generic, pips, kind)
                    if paid is not None and solve((paid[0], paid[1], _take(pool, kind), used)):
                        outcome = True
                        break
            if not outcome:
                for ability in abilities:
                    if any(solve(after) for after in _activate(state, ability, useful)):
                        outcome = True
                        break
        seen[key(state)] = outcome
        return outcome

    return solve(start)


@dataclass(frozen=True)
class _Offer:
    """A payment offer as the model reads it."""

    owed: tuple[int, tuple[Pip, ...]]
    pool: tuple[int, ...]
    pool_options: tuple[tuple[str, str], ...]
    abilities: dict[str, Ability]
    unfunded: frozenset[str]


def _read_offer(options: Sequence[Mapping[str, object]], unpaid_mana: str) -> _Offer | None:
    owed = parse_unpaid(unpaid_mana)
    if owed is None:
        return None
    pool = [0] * len(_TYPES)
    abilities: dict[str, Ability] = {}
    unfunded: set[str] = set()
    pool_options: list[tuple[str, str]] = []
    for option in options:
        option_type = str(option.get("option_type") or "")
        option_id = str(option.get("option_id") or "")
        if option_type == "cancel_mana_payment":
            continue
        metadata = option.get("metadata")
        meta = metadata if isinstance(metadata, dict) else {}
        if option_type == "mana_pool":
            kind = _POOL_TYPES.get(str(meta.get("mana_type") or "").casefold())
            amount = meta.get("mana_available")
            if kind is None:
                return None
            pool[_TYPES.index(kind)] += amount if isinstance(amount, int) and amount > 0 else 1
            pool_options.append((option_id, kind))
        elif option_type == "mana_ability":
            ability = parse_ability(option)
            if ability is None:
                return None
            abilities[option_id] = ability
            # The flag counts a hybrid pip as both of its colours ({R/W} "needs" R and W), so a
            # pool holding one of them reads as short; the pool is read here instead.
            if meta.get("pool_covers_mana_cost") is False and all(
                len(pip) == 1 for pip in ability.pips
            ):
                unfunded.add(option_id)
        else:
            return None
    return _Offer(owed, tuple(pool), tuple(pool_options), abilities, frozenset(unfunded))


def _useful(offer: _Offer) -> frozenset[str]:
    useful = frozenset("c").union(*offer.owed[1]) if offer.owed[1] else frozenset("c")
    for ability in offer.abilities.values():
        for pip in ability.pips:
            useful |= pip
    return useful


def completing_options(
    options: Sequence[Mapping[str, object]], unpaid_mana: str
) -> frozenset[str] | None:
    """Ids of the offered options after which the rest of the cost can still be paid.

    None when the offer cannot be judged (an unreadable cost or ability, a special payment such
    as delve or convoke, an unknown pool type, or a search that grew too large). An empty set
    means no option leads to a full payment; the cancel option is never part of the answer.
    """
    offer = _read_offer(options, unpaid_mana)
    if offer is None:
        return None
    useful = _useful(offer)
    everything = list(offer.abilities.values())
    start: _State = (offer.owed[0], offer.owed[1], offer.pool, frozenset())
    completing: set[str] = set()
    try:
        for option_id, kind in offer.pool_options:
            paid = _spend(start[0], start[1], kind)
            if paid is not None and _completes(
                (paid[0], paid[1], _take(start[2], kind), start[3]), everything, useful
            ):
                completing.add(option_id)
        for option_id, ability in offer.abilities.items():
            # the engine's own verdict on the pool as it is now; later prompts see a fuller pool
            if option_id in offer.unfunded:
                continue
            if any(
                _completes(after, everything, useful) for after in _activate(start, ability, useful)
            ):
                completing.add(option_id)
    except _Capped:
        return None
    return frozenset(completing)


def completing_outcomes(
    options: Sequence[Mapping[str, object]],
    unpaid_mana: str,
    activated_id: str,
    outcomes: Sequence[tuple[str, ...]],
) -> frozenset[tuple[str, ...]] | None:
    """Which colour outcomes of an activated ability keep the payment completable.

    An ability that adds mana of a colour the player picks (any colour, any combination) asks
    for it in a prompt of its own, after the activation. Each outcome is the sorted letters of
    the mana it would add ("wubrgc"). None when the offer or the activated ability cannot be
    judged; otherwise the outcomes after which the rest of the cost can still be paid.
    """
    offer = _read_offer(options, unpaid_mana)
    ability = None if offer is None else offer.abilities.get(activated_id)
    if offer is None or ability is None:
        return None
    useful = _useful(offer).union(*(frozenset(outcome) for outcome in outcomes))
    everything = list(offer.abilities.values())
    wanted = frozenset().union(*offer.owed[1]) if offer.owed[1] else frozenset()
    completing: set[tuple[str, ...]] = set()
    try:
        for paid in _pay_cost(ability, offer.pool, wanted):
            after = (
                offer.owed[0],
                offer.owed[1],
                paid,
                frozenset({ability.source}),
            )
            for outcome in outcomes:
                state = (after[0], after[1], _give(after[2], outcome), after[3])
                if _completes(state, everything, useful):
                    completing.add(outcome)
    except _Capped:
        return None
    return frozenset(completing)
