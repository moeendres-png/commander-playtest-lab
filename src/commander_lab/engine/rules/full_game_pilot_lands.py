"""Which land to play and which land to fetch (#989 phase 6).

The pilot scored every land the same, so the land it played was the one that sorted last by
name, and a "search for a basic land" took the same colours in the same order: Swamp, Plains,
Mountain, Island, Forest. Recorded real pod games, 24 seeds: 645 priority choices tied on score
and were broken that way, most of them between two lands, and 203 library searches for a land
named Swamp 79 times, Plains 64 and Mountain 8 times, Island and Forest never, whatever the hand
needed. A black-white bias in a simulator that compares decks is a bias in the comparison.

A player picks the land that lets a spell be cast this turn, plays a land that enters tapped when
no untapped land would cast anything extra, and otherwise fixes a colour the hand needs and the
board cannot make. This module ranks the lands that way from the actor's own hand, board and
commander colours. It only orders lands of one offer; whether to play a land at all stays with
the pilot.

Pure functions of Rules-visible content: nothing here decides legality and nothing orders by an
engine identifier.
"""

from __future__ import annotations

import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from commander_lab.agents.card_knowledge import CardFacts, card_facts

_COLORS = "WUBRG"
_BASIC_COLOR = {"plains": "W", "island": "U", "swamp": "B", "mountain": "R", "forest": "G"}
_MAX_DEMAND_CARDS = 12

_ENTERS_TAPPED = re.compile(r"enters(?: the battlefield)? tapped")
_UNLESS_CONTROL = re.compile(r"unless you control (?:an? |the )?([^.\n]+)")
_UNLESS_COUNT = re.compile(r"unless you control (\w+) or (more|fewer) (basic |other )?lands")
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_REVEAL_FROM_HAND = re.compile(r"reveal an? ([^.\n]+?) card from your hand")
_PAY_LIFE = re.compile(r"you may pay (\d+) life")
_FETCH = re.compile(r"sacrifice[^.\n]*: search your library for")
_CONDITIONAL_MANA = re.compile(r"activate only|spend this mana only|only if you control")
_FETCH_COLORS = re.compile(r"\b(plains|island|swamp|mountain|forest)\b")


def _entries(value: object) -> list[Mapping[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _actor(state: Mapping[str, object]) -> Mapping[str, object] | None:
    actor_id = str(state.get("actor_id", ""))
    for player in _entries(state.get("players")):
        if player.get("is_actor") is True or str(player.get("player_id", "")) == actor_id:
            return player
    return None


def commander_identity(state: Mapping[str, object]) -> frozenset[str]:
    """The colours the actor's commanders allow; empty when the table does not say."""
    actor_id = str(state.get("actor_id", ""))
    colors: set[str] = set()
    for entry in _entries(state.get("commander_status")):
        if str(entry.get("owner_id", "")) == actor_id:
            facts = card_facts(str(entry.get("name", "")))
            if facts is not None:
                colors |= {color for color in facts.color_identity if color in _COLORS}
    return frozenset(colors)


def _produced(facts: CardFacts, identity: frozenset[str]) -> frozenset[str]:
    """Coloured mana a card makes, limited to what the actor's commander can use."""
    made = frozenset(color for color in facts.produced_mana if color in _COLORS)
    if not identity:
        return made
    return made & identity


def _is_fetch(facts: CardFacts) -> bool:
    return facts.is_land and _FETCH.search(facts.oracle_text.casefold()) is not None


def _fetchable(facts: CardFacts, identity: frozenset[str]) -> frozenset[str]:
    """The colours a fetch land can bring: the basic types named, else any the commander allows."""
    text = facts.oracle_text.casefold()
    named = frozenset(_BASIC_COLOR[word] for word in _FETCH_COLORS.findall(text))
    pool = named or frozenset(_COLORS)
    return pool & identity if identity else pool


@dataclass(frozen=True, slots=True)
class _Source:
    colors: frozenset[str]
    weight: float
    untapped: bool
    mana: int


def _source(item: Mapping[str, object], identity: frozenset[str]) -> _Source | None:
    facts = card_facts(str(item.get("name") or ""))
    if facts is None or facts.is_creature or _is_fetch(facts):
        return None
    if not facts.produced_mana:
        return None
    weight = 1.0 if facts.is_land else 0.75
    if _CONDITIONAL_MANA.search(facts.oracle_text.casefold()):
        weight *= 0.4
    colors = _produced(facts, identity)
    mana = 2 if "{c}{c}" in facts.oracle_text.casefold() else 1
    return _Source(colors, weight, item.get("tapped") is not True, mana)


def board_sources(state: Mapping[str, object], identity: frozenset[str]) -> list[_Source]:
    actor = _actor(state)
    if actor is None:
        return []
    found = (_source(item, identity) for item in _entries(actor.get("battlefield")))
    return [source for source in found if source is not None]


def lands_on_board(actor: Mapping[str, object] | None) -> int:
    if actor is None:
        return 0
    found = (card_facts(str(item.get("name") or "")) for item in _entries(actor.get("battlefield")))
    return sum(1 for facts in found if facts is not None and facts.is_land)


def _pool_mana(actor: Mapping[str, object]) -> int:
    pool = actor.get("mana_pool")
    if not isinstance(pool, dict):
        return 0
    return sum(value for value in pool.values() if isinstance(value, int) and value > 0)


@dataclass(frozen=True, slots=True)
class _Plan:
    mana_value: int
    pips: Mapping[str, int]
    weight: float


def _plan_cards(
    state: Mapping[str, object], identity: frozenset[str], lands_on_board: int
) -> list[_Plan]:
    """What the actor wants to cast: nonland cards in hand and commanders in the command zone."""
    actor = _actor(state)
    if actor is None:
        return []
    names = [str(item.get("name") or "") for item in _entries(actor.get("hand"))]
    commanders = [str(item.get("name") or "") for item in _entries(actor.get("command"))]
    plan: list[_Plan] = []
    for name, in_command_zone in [(n, False) for n in names] + [(n, True) for n in commanders]:
        facts = card_facts(name)
        if facts is None or facts.is_land:
            continue
        mana_value = int(facts.mana_value)
        if mana_value <= 0:
            continue
        distance = mana_value - lands_on_board
        weight = 1.0 if distance <= 2 else 0.5 if distance <= 5 else 0.25
        pips = {color: count for color, count in facts.pips().items() if color in _COLORS}
        plan.append(_Plan(mana_value, pips, 1.0 if in_command_zone else weight))
    plan.sort(key=lambda card: (card.mana_value, sorted(card.pips.items())))
    return plan[:_MAX_DEMAND_CARDS]


def _demand(plan: Sequence[_Plan]) -> dict[str, float]:
    demand: dict[str, float] = {}
    for card in plan:
        for color, count in card.pips.items():
            demand[color] = demand.get(color, 0.0) + count * card.weight
    return demand


def _colour_totals(sources: Sequence[_Source]) -> dict[str, float]:
    """Sources per colour, a rock or a conditional source counting for less than a land."""
    totals: dict[str, float] = {}
    for source in sources:
        for color in source.colors:
            totals[color] = totals.get(color, 0.0) + source.weight
    return totals


def _source_gain(color: str, demand: Mapping[str, float], have: Mapping[str, float]) -> float:
    """How much one more source of a colour is worth: a needed colour with none, then a second."""
    wanted = demand.get(color, 0.0)
    if wanted <= 0.0:
        return 0.0
    owned = have.get(color, 0.0)
    if owned < 0.5:
        return 1.0
    if owned < 1.5 and wanted >= 2.0:
        return 0.4
    return 0.0


def _castable(card: _Plan, mana: int, have: Mapping[str, float]) -> bool:
    """Enough mana, and for each coloured symbol as many sources of that colour (0.7 and up)."""
    return card.mana_value <= mana and all(
        have.get(color, 0.0) >= min(count, 2) - 0.3 for color, count in card.pips.items()
    )


def _best_spend(plan: Sequence[_Plan], mana: int, have: Mapping[str, float]) -> int:
    """The most mana one or two castable cards use up this turn."""
    ready = [card for card in plan if _castable(card, mana, have)]
    best = max((card.mana_value for card in ready), default=0)
    for first in range(len(ready)):
        for second in range(first + 1, len(ready)):
            total = ready[first].mana_value + ready[second].mana_value
            if total <= mana:
                best = max(best, total)
    return best


def _land_subtypes(facts: CardFacts) -> frozenset[str]:
    return frozenset(word.casefold() for word in facts.subtypes)


def _hand_lands(actor: Mapping[str, object]) -> list[CardFacts]:
    found = (card_facts(str(item.get("name") or "")) for item in _entries(actor.get("hand")))
    return [facts for facts in found if facts is not None and facts.is_land]


def _types_named(text: str) -> frozenset[str]:
    return frozenset(word for word in re.split(r"[^a-z]+", text.casefold()) if word)


def enters_tapped(facts: CardFacts, state: Mapping[str, object]) -> bool:
    """Whether the land enters tapped now, read from its text and the actor's board and hand."""
    text = facts.oracle_text.casefold()
    if _ENTERS_TAPPED.search(text) is None:
        return False
    actor = _actor(state)
    if actor is None:
        return True
    battlefield = [
        card_facts(str(item.get("name") or "")) for item in _entries(actor.get("battlefield"))
    ]
    own_lands = [item for item in battlefield if item is not None and item.is_land]
    other_lands = len(own_lands)
    sentence = next(
        (line for line in re.split(r"[.\n]", text) if "tapped" in line and "enters" in line),
        "",
    )
    counted = _UNLESS_COUNT.search(text)
    if counted is not None and counted.group(1) in _NUMBER_WORDS:
        limit = _NUMBER_WORDS[counted.group(1)]
        basics = sum(1 for item in own_lands if "basic" in item.type_line.casefold())
        have_count = basics if counted.group(3) == "basic " else other_lands
        return have_count < limit if counted.group(2) == "more" else have_count > limit
    if "two or more opponents" in text:
        return False
    unless = _UNLESS_CONTROL.search(text)
    if unless is not None:
        wanted = _types_named(unless.group(1)) - {"or", "an", "a", "the", "and"}
        have = frozenset().union(*(_land_subtypes(item) for item in own_lands))
        names = frozenset(word for item in own_lands for word in _types_named(item.name))
        return not (wanted & (have | names))
    reveal = _REVEAL_FROM_HAND.search(text)
    if reveal is not None and "if you don't" in text:
        wanted = _types_named(reveal.group(1)) - {"or", "an", "a"}
        others = [item for item in _hand_lands(actor) if item.name != facts.name]
        return not any(wanted & _land_subtypes(item) for item in others)
    pay = _PAY_LIFE.search(text)
    if pay is not None and "if you don't" in text:
        life = actor.get("life")
        return not (isinstance(life, int | float) and life > int(pay.group(1)) + 8)
    return "tapped" in sentence


def _delivers_mana_now(facts: CardFacts, tapped: bool) -> bool:
    return not tapped and bool(facts.produced_mana) and not _is_fetch(facts)


def _colors_after(
    facts: CardFacts,
    have: Mapping[str, float],
    identity: frozenset[str],
    *,
    weight: float = 1.0,
) -> dict[str, float]:
    colors = _fetchable(facts, identity) if _is_fetch(facts) else _produced(facts, identity)
    if _CONDITIONAL_MANA.search(facts.oracle_text.casefold()):
        weight *= 0.4
    merged = dict(have)
    for color in colors:
        merged[color] = merged.get(color, 0.0) + weight
    return merged


@dataclass(frozen=True, slots=True)
class _Verdict:
    name: str
    enabled: int
    tapped_when_idle: bool
    gain: float
    keeps_utility: int
    scarcity: float
    basic: bool


def _rank_key(verdict: _Verdict, idle: bool) -> tuple[float, ...]:
    return (
        float(verdict.enabled),
        1.0 if idle and verdict.tapped_when_idle else 0.0,
        round(verdict.gain, 3),
        -float(verdict.keeps_utility),
        round(verdict.scarcity, 3),
        1.0 if verdict.basic else 0.0,
    )


def land_verdicts(
    names: Sequence[str], state: Mapping[str, object]
) -> list[tuple[str, tuple[float, ...]]]:
    """Each distinct land of a hand with the key a player would rank it by (higher is better)."""
    identity = commander_identity(state)
    actor = _actor(state)
    sources = board_sources(state, identity)
    have = _colour_totals(sources)
    plan = _plan_cards(state, identity, lands_on_board(actor))
    demand = _demand(plan)
    mana_now = sum(source.mana for source in sources if source.untapped)
    mana_now += _pool_mana(actor) if actor is not None else 0
    base_spend = _best_spend(plan, mana_now, have)
    verdicts: list[_Verdict] = []
    for name in dict.fromkeys(names):
        facts = card_facts(name)
        if facts is None:
            verdicts.append(_Verdict(name, 0, False, 0.0, 1, 0.0, False))
            continue
        text = facts.oracle_text.casefold()
        tapped = enters_tapped(facts, state)
        enabled = 0
        if _delivers_mana_now(facts, tapped):
            enabled = _best_spend(plan, mana_now + 1, _colors_after(facts, have, identity))
            enabled -= base_spend
        fetch = _is_fetch(facts)
        colors = _fetchable(facts, identity) if fetch else _produced(facts, identity)
        painful = int(("pay" in text and "life" in text) or "sacrifice two lands" in text)
        situational = int(
            not facts.produced_mana
            or "exile target player's graveyard" in text
            or "destroy target nonbasic land" in text
        )
        verdicts.append(
            _Verdict(
                name=name,
                enabled=max(0, enabled),
                tapped_when_idle=tapped or fetch,
                gain=min(1.6, sum(_source_gain(color, demand, have) for color in colors)),
                keeps_utility=max(painful, situational),
                scarcity=max((1.0 / (1.0 + have.get(color, 0.0)) for color in colors), default=0.0),
                basic="basic" in facts.type_line.casefold(),
            )
        )
    idle = all(verdict.enabled == 0 for verdict in verdicts)
    return [(verdict.name, _rank_key(verdict, idle)) for verdict in verdicts]


def choose_land_to_play(
    names: Sequence[str], state: Mapping[str, object], rng: random.Random
) -> str | None:
    """The land a player would play from this hand; lands that rank alike are told apart by rng."""
    verdicts = land_verdicts(names, state)
    if not verdicts:
        return None
    best = max(key for _name, key in verdicts)
    return rng.choice(sorted(name for name, key in verdicts if key == best))


def choose_lands_to_fetch(
    names: Sequence[str], state: Mapping[str, object], rng: random.Random, *, count: int = 1
) -> list[str]:
    """The lands to take from the library, best first; each pick counts for the next one.

    The land comes in tapped, so only the colours it adds and what it keeps from the deck matter:
    a needed colour the board cannot make, then the colour with the fewest sources among the ones
    the commander allows, then plainly the basic over a land with a drawback.
    """
    identity = commander_identity(state)
    actor = _actor(state)
    have = _colour_totals(board_sources(state, identity))
    demand = _demand(_plan_cards(state, identity, lands_on_board(actor)))
    remaining = list(names)
    chosen: list[str] = []
    while remaining and len(chosen) < max(1, count):
        scored: dict[str, tuple[float, ...]] = {}
        for name in dict.fromkeys(remaining):
            facts = card_facts(name)
            if facts is None:
                scored[name] = (0.0, 0.0, 0.0)
                continue
            colors = _fetchable(facts, identity) if _is_fetch(facts) else _produced(facts, identity)
            scarcity = max((1.0 / (1.0 + have.get(color, 0.0)) for color in colors), default=0.0)
            scored[name] = (
                round(sum(_source_gain(color, demand, have) for color in colors), 3),
                round(scarcity, 3),
                0.0 if "basic" in facts.type_line.casefold() else -1.0,
            )
        best = max(scored.values())
        pick = rng.choice(sorted(name for name, key in scored.items() if key == best))
        chosen.append(pick)
        remaining.remove(pick)
        picked = card_facts(pick)
        if picked is not None:
            have = _colors_after(picked, have, identity)
    return chosen + remaining
