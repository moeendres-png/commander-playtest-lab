#!/usr/bin/env python3
"""Judge a mulligan policy by what the hands it keeps do in the first six turns.

``mulligan_keep_table.py`` shows how often the pilot keeps a hand. A keep rate cannot say whether
the keeps are good ones. This script plays the opening for seeded random hands of every deck it is
given: the pilot's own keep/mulligan chain and London bottoming, then six turns on the draw with
a greedy land drop and a greedy cast order. It reports what the policy was for:

* mana spent on turns 1-6 (the hand's use of its mana),
* land drops missed by turn 3,
* turns on which a spell was affordable by mana alone but blocked by colour,
* the commander cast by turn 6,
* the cards in hand after the chain (what the mulligans cost).

The model is a ruler, not a game: every land enters untapped, a ramp spell of mana value 3 or less
adds one mana of any colour from the next turn, and nothing is held back. It is the same for every
policy, so it compares policies; it does not predict a win rate. ``--policy always_keep`` and
``--policy lands_3_4`` are references that must score below a sensible policy (the wrong-reason
control of the ruler).

    python scripts/mulligan_policy_eval.py --decks data/decks/precons --hands 100
    python scripts/mulligan_policy_eval.py --decks data/decks/precons --policy always_keep

Exit code 0 on success.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from commander_lab.agents.card_knowledge import CardFacts, card_facts
from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.full_game_pilot_views import card_view_fields
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import (
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
)

HAND_SIZE = 7
MAX_MULLIGANS = 3  # the rules core forces a keep after 3 mulligans
TURNS = 6  # the horizon of the fit behind BasePilot.opening_hand_score
MISSED_DROP_TURNS = 3
ANY_COLOUR = frozenset("WUBRG")
_CHEAP_RAMP_VALUE = 3.0


@dataclass
class _Source:
    colours: frozenset[str]


@dataclass
class _Run:
    mana_spent: int = 0
    spells_cast: int = 0
    missed_land_drops: int = 0
    colour_blocked_turns: int = 0
    commander_cast: bool = False
    hand_after_chain: int = 0
    mulligans: int = 0
    unknown_cards: int = 0
    turn_spend: list[int] = field(default_factory=list)


def _views(names: list[str]) -> list[PilotActionView]:
    return [
        PilotActionView(
            action_id=f"hand-{index}",
            action_kind="card",
            card_name=name,
            floor_value=0.5,
            immediate_impact=0.3,
            **card_view_fields(name),
        )
        for index, name in enumerate(names)
    ]


def _land_colours(facts: CardFacts | None, name: str) -> frozenset[str]:
    return facts.colours_made if facts is not None else frozenset()


def _is_ramp(facts: CardFacts) -> bool:
    return (
        not facts.is_land
        and facts.mana_value <= _CHEAP_RAMP_VALUE
        and (
            "add {" in facts.oracle_text.casefold()
            or "search your library for a basic land" in facts.oracle_text.casefold()
            or "search your library for up to two basic land" in facts.oracle_text.casefold()
        )
        and "creature" not in facts.types
    )


def _affordable(pips: dict[str, int], generic: int, sources: list[_Source]) -> tuple[bool, bool]:
    """(castable, colour_blocked): castable with these sources; blocked if only colour stops it."""
    total = len(sources)
    needed = sum(pips.values()) + generic
    if needed > total:
        return False, False
    remaining = list(sources)
    for colour, count in sorted(pips.items(), key=lambda item: -item[1]):
        for _ in range(count):
            match = next(
                (s for s in sorted(remaining, key=lambda s: len(s.colours)) if colour in s.colours),
                None,
            )
            if match is None:
                return False, True
            remaining.remove(match)
    return True, False


def _cost(facts: CardFacts) -> tuple[dict[str, int], int]:
    pips = {colour: count for colour, count in facts.pips().items() if colour in ANY_COLOUR}
    coloured = sum(pips.values())
    generic = max(0, int(facts.mana_value) - coloured)
    return pips, generic


def _play_turns(hand: list[str], library: list[str], commander: str | None, run: _Run) -> None:
    lands: list[_Source] = []
    bonus = 0  # ramp mana of any colour from earlier turns
    pending_bonus = 0
    cards = list(hand)
    commander_facts = card_facts(commander) if commander else None
    commander_cast = False
    for turn in range(1, TURNS + 1):
        bonus += pending_bonus
        pending_bonus = 0
        if library:
            cards.append(library.pop())
        # land drop: prefer a land that adds a colour some uncast spell needs and no source has yet
        land_names = [name for name in cards if (f := card_facts(name)) is not None and f.is_land]
        basic_unknown = [name for name in cards if card_facts(name) is None]
        if not land_names and not basic_unknown:
            if turn <= MISSED_DROP_TURNS:
                run.missed_land_drops += 1
        else:
            have = set().union(*(s.colours for s in lands)) if lands else set()
            wanted = set()
            for name in cards:
                f = card_facts(name)
                if f is not None and not f.is_land:
                    wanted |= set(_cost(f)[0])
            if commander_facts is not None and not commander_cast:
                wanted |= set(_cost(commander_facts)[0])
            best_name = None
            best_gain = -1
            for name in land_names:
                f = card_facts(name)
                colours = _land_colours(f, name)
                gain = len((colours & wanted) - have) * 10 + len(colours & wanted)
                if gain > best_gain:
                    best_name, best_gain = name, gain
            if best_name is None:
                run.unknown_cards += 1
                best_name = basic_unknown[0]
                lands.append(_Source(frozenset()))
            else:
                lands.append(_Source(_land_colours(card_facts(best_name), best_name)))
            cards.remove(best_name)
        sources = list(lands) + [_Source(ANY_COLOUR) for _ in range(bonus)]
        spent = 0
        # ramp first (cheap first), then the rest by value, the commander among them
        spells = []
        for name in cards:
            f = card_facts(name)
            if f is None:
                run.unknown_cards += 1
            elif not f.is_land:
                spells.append((name, f))
        spells.sort(
            key=lambda item: (
                not _is_ramp(item[1]),
                -item[1].mana_value if not _is_ramp(item[1]) else item[1].mana_value,
                item[0],
            )
        )
        queue: list[tuple[str | None, CardFacts]] = [(n, f) for n, f in spells]
        if commander_facts is not None and not commander_cast:
            queue.insert(0 if turn >= 3 else len(queue), (None, commander_facts))
        for queued, facts in queue:
            if facts.mana_value <= 0:
                continue
            pips, generic = _cost(facts)
            ok, blocked = _affordable(pips, generic, sources)
            if ok:
                # pay: remove coloured sources first, then any
                need = sum(pips.values()) + generic
                spent += need
                run.spells_cast += 1
                for colour, count in pips.items():
                    for _ in range(count):
                        match = next(
                            (
                                s
                                for s in sorted(sources, key=lambda s: len(s.colours))
                                if colour in s.colours
                            ),
                            None,
                        )
                        if match is not None:
                            sources.remove(match)
                for _ in range(generic):
                    if sources:
                        sources.remove(sorted(sources, key=lambda s: len(s.colours))[0])
                if queued is None:
                    commander_cast = True
                    run.commander_cast = True
                else:
                    cards.remove(queued)
                    if _is_ramp(facts):
                        pending_bonus += 1
            elif blocked:
                run.colour_blocked_turns += 1
                break
        run.mana_spent += spent
        run.turn_spend.append(spent)


def _policy_keep(
    name: str, pilot: object, rng: random.Random
) -> Callable[[list[PilotActionView], int, tuple[str, ...]], bool]:
    if name == "always_keep":
        return lambda views, mulligans, commanders: True
    if name == "lands_3_4":
        return lambda views, mulligans, commanders: (
            mulligans >= 2 or 3 <= sum(bool(v.metadata.get("is_land")) for v in views) <= 4
        )

    def pilot_keep(
        views: list[PilotActionView], mulligans: int, commanders: tuple[str, ...]
    ) -> bool:
        keep, _ = pilot.should_keep_opening_hand(  # type: ignore[attr-defined]
            views, mulligans=mulligans, free_first=True, commander_names=commanders, rng=rng
        )
        return bool(keep)

    return pilot_keep


def _one_hand(
    deck_library: list[str],
    commander_names: tuple[str, ...],
    keep_fn: Callable[[list[PilotActionView], int, tuple[str, ...]], bool],
    pilot: object,
    rng: random.Random,
) -> _Run:
    run = _Run()
    mulligans = 0
    while True:
        shuffled = deck_library[:]
        rng.shuffle(shuffled)
        hand = shuffled[:HAND_SIZE]
        rest = shuffled[HAND_SIZE:]
        views = _views(hand)
        if mulligans >= MAX_MULLIGANS or keep_fn(views, mulligans, commander_names):
            break
        mulligans += 1
    bottom = max(0, mulligans - 1)  # the first mulligan is free
    if bottom:
        ids = pilot.choose_bottom_cards(  # type: ignore[attr-defined]
            views, bottom, commander_names=commander_names
        )
        gone = {int(action_id.split("-")[1]) for action_id in ids}
        rest = [hand[i] for i in sorted(gone)] + rest
        hand = [card for i, card in enumerate(hand) if i not in gone]
    run.mulligans = mulligans
    run.hand_after_chain = len(hand)
    library = list(reversed(rest))
    _play_turns(hand, library, commander_names[0] if commander_names else None, run)
    return run


def evaluate(
    decks: list[Path], hands: int, seed: int, policy: str, strength: PilotStrength
) -> dict[str, object]:
    pilot = build_pilot(
        PilotConfig(strength=strength, mode=PilotDecisionMode.DETERMINISTIC), strategy="generic"
    )
    runs: list[_Run] = []
    per_deck: dict[str, float] = {}
    for deck_path in decks:
        deck = load_rules_deck_snapshot(deck_path)
        library = list(deck.mainboard)
        rng = random.Random(f"{seed}:{deck_path.stem}")
        decide = random.Random(f"{seed}:{deck_path.stem}:d")
        keep_fn = _policy_keep(policy, pilot, decide)
        deck_runs = [
            _one_hand(library, deck.commander_names, keep_fn, pilot, rng) for _ in range(hands)
        ]
        per_deck[deck_path.stem] = statistics.fmean(r.mana_spent for r in deck_runs)
        runs.extend(deck_runs)

    def mean(values: list[float]) -> float:
        return statistics.fmean(values) if values else 0.0

    n = len(runs)
    return {
        "policy": policy,
        "strength": strength.value,
        "decks": len(decks),
        "hands_per_deck": hands,
        "seed": seed,
        "runs": n,
        "mana_spent": mean([r.mana_spent for r in runs]),
        "spells_cast": mean([r.spells_cast for r in runs]),
        "missed_land_drops": mean([r.missed_land_drops for r in runs]),
        "colour_blocked_turns": mean([r.colour_blocked_turns for r in runs]),
        "commander_cast": sum(r.commander_cast for r in runs) / n if n else 0.0,
        "mulligans_per_hand": mean([r.mulligans for r in runs]),
        "hand_after_chain": mean([r.hand_after_chain for r in runs]),
        "share_no_spell": sum(r.spells_cast == 0 for r in runs) / n if n else 0.0,
        "share_two_missed_drops": sum(r.missed_land_drops >= 2 for r in runs) / n if n else 0.0,
        "unknown_card_reads": sum(r.unknown_cards for r in runs),
        "worst_decks": sorted(per_deck.items(), key=lambda item: item[1])[:5],
    }


def format_report(report: dict[str, object]) -> str:
    lines = [
        f"policy={report['policy']} strength={report['strength']} decks={report['decks']} "
        f"hands/deck={report['hands_per_deck']} seed={report['seed']} runs={report['runs']}",
        f"mana spent T1-{TURNS}:           {report['mana_spent']:.3f}",
        f"spells cast T1-{TURNS}:          {report['spells_cast']:.3f}",
        f"missed land drops (T1-{MISSED_DROP_TURNS}):  {report['missed_land_drops']:.3f}",
        f"share with 2+ misses:      {report['share_two_missed_drops']:.3%}",
        f"colour-blocked turns:      {report['colour_blocked_turns']:.3f}",
        f"share with no spell:      {report['share_no_spell']:.3%}",
        f"commander cast by T{TURNS}:      {report['commander_cast']:.3%}",
        f"mulligans per hand:        {report['mulligans_per_hand']:.3f}",
        f"cards after the chain:     {report['hand_after_chain']:.3f}",
        f"unknown card reads:        {report['unknown_card_reads']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    global TURNS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decks", type=Path, required=True, help="a deck JSON or a folder of them")
    parser.add_argument("--hands", type=int, default=100, help="seeded hands per deck")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--policy", default="pilot", choices=("pilot", "always_keep", "lands_3_4"))
    parser.add_argument(
        "--strength",
        default=PilotStrength.AVERAGE.value,
        choices=[s.value for s in PilotStrength],
    )
    parser.add_argument(
        "--turns", type=int, default=TURNS, help="turns to play after the opening (default 6)"
    )
    parser.add_argument("--limit", type=int, default=0, help="only the first N decks (0 = all)")
    parser.add_argument("--json", type=Path, default=None, help="also write the report here")
    args = parser.parse_args(argv)
    TURNS = args.turns
    paths = sorted(args.decks.glob("*.json")) if args.decks.is_dir() else [args.decks]
    if args.limit:
        paths = paths[: args.limit]
    report = evaluate(paths, args.hands, args.seed, args.policy, PilotStrength(args.strength))
    print(format_report(report))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
