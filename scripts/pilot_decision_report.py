"""Measure how the full-game pilots play: speed and decision quality of real XMage games.

Plays real pods like ``benchmark_xmage_full_games.py`` and records every pilot decision
(request and answer) in memory, then reduces each game to play-quality figures a
Commander player would look at:

* length: turns, rounds (turns per player), decisions, decisions per round, wall time,
  the Python pilot's own share of the time;
* tempo: spells cast per player and round, own main phases left with a castable spell
  or an unplayed land, first commander cast;
* interaction: removal aimed at the actor's own permanents, wipes cast while the actor's
  own board is the biggest, counters aimed at the actor's own spells;
* combat: attacks declared, attacks into a blocker that kills the attacker and
  survives, chump blocks that were not needed.

    python scripts/pilot_decision_report.py run --jar bridge.jar --out before.json --seeds 1-4
    python scripts/pilot_decision_report.py compare before.json after.json

``--workers N`` plays N games at once, each in its own Python process (the recording
patches the policy class, so games must not share a process). Every game runs with a
private card database slot per bridge JVM, also with one worker: report processes started
side by side must not open one H2 file together (it fails about one start in ten with
XMAGE_CARD_REPOSITORY_INIT_FAILED, H2 "Lock file recently modified", #878).

The figures are measurements of local games for pilot work, not qualification
evidence. Lower is better for every "bad_*" counter.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark_xmage_full_games as bench  # noqa: E402

from commander_lab.agents.card_knowledge import (  # noqa: E402
    canonical_card_name,
    card_facts,
    card_roles,
)
from commander_lab.engine.rules import full_game_pilot_views as views  # noqa: E402
from commander_lab.engine.rules.full_game import XmageFullGameRunner  # noqa: E402
from commander_lab.engine.rules.full_game_pilot import (  # noqa: E402
    ExternalPilotDecisionPolicy,
)
from commander_lab.models import CardRole  # noqa: E402


@contextmanager
def recording(sink: list[dict[str, Any]]) -> Iterator[None]:
    """Record every policy decision (request, answer, pilot seconds) into ``sink``."""
    original: Callable[..., dict[str, Any]] = ExternalPilotDecisionPolicy.decide

    def decide(self: ExternalPilotDecisionPolicy, request: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        answer = original(self, request)
        sink.append(
            {"request": request, "answer": answer, "pilot_s": time.perf_counter() - started}
        )
        return answer

    ExternalPilotDecisionPolicy.decide = decide  # type: ignore[method-assign]
    try:
        yield
    finally:
        ExternalPilotDecisionPolicy.decide = original  # type: ignore[method-assign]


def _options(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [o for o in request.get("legal_options") or [] if isinstance(o, dict)]


def _chosen(record: dict[str, Any]) -> list[dict[str, Any]]:
    ids = set(record["answer"].get("selected_option_ids") or [])
    return [o for o in _options(record["request"]) if o.get("option_id") in ids]


def _meta(option: dict[str, Any]) -> dict[str, Any]:
    meta = option.get("metadata")
    return meta if isinstance(meta, dict) else {}


def _is_main(state: dict[str, Any]) -> bool:
    return "main" in str(state.get("phase", "")).casefold()


def _postcombat(state: dict[str, Any]) -> bool:
    text = f"{state.get('phase', '')} {state.get('step', '')}".casefold()
    return "postcombat" in text or "post_combat" in text or "main2" in text


def _opponent_target_offered(options: list[dict], state: dict, views) -> bool:
    """True when the prompt also offered a permanent the actor does not own.

    Effects whose legal targets are only the actor's own permanents (Guardian of
    Faith's phasing, XMage labels it "detriment") leave no better choice, so
    picking an own permanent there is not a pilot mistake.
    """
    actor = str(state.get("actor_id"))
    for option in options:
        found = views.permanent_owner(
            str(_meta(option).get("object_id") or option.get("option_id")), state
        )
        if found is not None and found[0] != actor:
            return True
    return False


def _own_turn(state: dict[str, Any]) -> bool:
    return str(state.get("active_player_id", "")) == str(state.get("actor_id", ""))


def _is_instant_speed(name: str) -> bool:
    """True when the card catalog knows the name as instant-speed.

    Unknown names (facts is None) fall back to sorcery-speed, the old rule.
    """
    facts = card_facts(name)
    return facts is not None and facts.is_instant_speed


def _stack_top_is_own_cast(state: dict[str, Any], own_names: set[str]) -> bool:
    """Whether the stack's top spell is one this seat cast earlier.

    Index 0 is the stack top (confirmed in real recordings). Abilities are
    skipped: the first spell object from index 0 decides. A stack item counts
    as a spell when its name resolves to card facts; ability names (e.g.
    "Equip {0}") do not. Name-based approximation, the same idea as the
    pilot's ``_remember_own_cast`` in ``full_game_pilot/state.py``: stack
    objects carry no controller, so a top spell whose name matches a spell
    the actor cast earlier in the game is treated as the actor's own. It can
    misfire when both seats cast the same-named card in one game, which the
    report accepts as a documented approximation.
    """
    stack = state.get("stack")
    if not isinstance(stack, list) or not stack:
        return False
    for item in stack:
        if not isinstance(item, dict):
            continue
        name = canonical_card_name(str(item.get("name") or ""))
        if not name:
            continue
        if card_facts(name) is None:
            continue  # ability or unknown name, not a spell
        return name.casefold() in own_names
    return False


def _seat(state: dict[str, Any]) -> int:
    return int(state.get("seat", -1)) + 1


# Counters repeated per seat in ``summarize(...)["by_seat"]``.
_SEAT_KEYS = (
    "decisions",
    "forced_priority",
    "pilot_s",
    "by_class",
    "spells_cast",
    "spell_offers",
    "spell_offers_without_pilot_knowledge",
    "own_turns",
    "bad_idle_main_with_castable_spell",
    "bad_idle_main_with_unplayed_land",
    "removal_targets",
    "bad_removal_on_own_permanent",
    "wipes_cast",
    "bad_wipes_while_ahead",
    "counters_cast",
    "attacks",
    "bad_attacks_into_killer",
    "blocks",
    "bad_needless_chump_blocks",
    "max_activations_one_turn",
    "commander_first_cast_turn",
    "commander_first_cast_round",
    "commander_first_cast_round_by_name",
)


def _round_of(turn: int, players: int) -> int:
    """1-based round of a game turn counter, assuming every player takes one turn per round.

    Only the fallback: once a player has left the game the counter advances by fewer than
    ``players`` per round, so :func:`summarize` counts the seat's own turns instead.
    """
    return (max(turn, 1) - 1) // max(1, players) + 1


def summarize(
    records: list[dict[str, Any]], players: int, *, by_seat: bool = True
) -> dict[str, Any]:
    """Play-quality figures of one recorded game.

    The counters at the top level add up all seats of the pod. ``by_seat`` repeats the
    ``_SEAT_KEYS`` counters for each seat on its own, so a figure about one deck is not
    mixed with the opponents' play.
    """
    by_class: Counter[str] = Counter()
    forced = 0
    spells: Counter[int] = Counter()
    commander_turn: dict[int, int] = {}
    commander_round: dict[int, int] = {}
    commander_round_by_name: dict[int, dict[str, int]] = defaultdict(dict)
    spell_offers = 0
    spell_offers_unknown = 0
    idle_main_with_spell = 0
    idle_main_with_land = 0
    own_turns: set[tuple[int, int]] = set()
    own_turn_count: Counter[int] = Counter()
    removal_on_own = 0
    removal_total = 0
    wipes_cast = 0
    bad_wipes = 0
    counters_cast = 0
    attacks = 0
    bad_attacks = 0
    blocks = 0
    needless_chumps = 0
    max_turn = 0
    pilot_s = 0.0
    abilities_per_turn: dict[tuple[int, int], int] = defaultdict(int)
    # Per (seat, card name): how often a cast was offered in a countable
    # priority window vs. actually chosen. Only the actor's own seat is
    # recorded; hidden information stays actor-scoped.
    # Own-cast memory: casefolded names of spells the actor chose to cast
    # earlier in this game, per seat. Built from the actor's own chosen cast
    # options like the pilot's _remember_own_cast; see
    # _stack_top_is_own_cast for the name-based approximation and why.
    offered_castable: dict[tuple[int, str], int] = Counter()
    cast_count: dict[tuple[int, str], int] = Counter()
    cast_in_offer_window: dict[tuple[int, str], int] = Counter()
    cast_on_opponent_turn: dict[tuple[int, str], int] = Counter()
    instant_speed: dict[tuple[int, str], bool] = {}
    first_cast_round: dict[tuple[int, str], int] = {}
    own_cast_names: dict[int, set[str]] = {}
    for record in records:
        request = record["request"]
        state = request.get("pilot_state") or {}
        decision_class = str(request.get("decision_class", ""))
        options = _options(request)
        chosen = _chosen(record)
        by_class[decision_class] += 1
        pilot_s += float(record["pilot_s"])
        turn = int(state.get("turn_number", 0) or 0)
        max_turn = max(max_turn, turn)
        seat = _seat(state)
        if _own_turn(state) and (seat, turn) not in own_turns:
            own_turns.add((seat, turn))
            own_turn_count[seat] += 1
        # The seat's own turn number: exact after eliminations and extra turns, which turn
        # counter arithmetic is not. Before the seat's first own turn, the arithmetic stands in.
        own_round = own_turn_count[seat] or _round_of(turn, players)
        if decision_class == "priority":
            if len(options) == 1:
                forced += 1
                continue
            picked = chosen[0] if chosen else {}
            picked_type = str(picked.get("option_type", ""))
            meta = _meta(picked)
            # Spell options the pilot saw, and how many of them are for a card it has no
            # knowledge of (it then plays the card as a spell without cost or role). The
            # lookup is the pilot's own: the option's source name.
            for option in options:
                if _meta(option).get("ability_type") != "spell":
                    continue
                spell_offers += 1
                if (
                    card_facts(str(_meta(option).get("source_name") or option.get("label") or ""))
                    is None
                ):
                    spell_offers_unknown += 1
            # Per-card cast tracking. A cast counts in every priority window
            # of the actor (any turn, any phase). An offer counts for
            # sorcery-speed cards only in own main-phase windows (the old
            # rule); for instant-speed cards it counts in any window where
            # the stack is empty or its top object is not a spell this seat
            # cast earlier. Withholding a counterspell while one's own spell
            # sits on top of the stack is correct play, not a missed cast.
            # Names are the physical card's: XMage offers each half of a split
            # card and the combined card as separate spells, which count once.
            offered_names = {
                canonical_card_name(str(_meta(o).get("source_name") or ""))
                for o in options
                if _meta(o).get("ability_type") == "spell"
                and str(_meta(o).get("source_name") or "")
            }
            counted_now: set[str] = set()
            for name in offered_names:
                is_instant = _is_instant_speed(name)
                instant_speed[(seat, name)] = is_instant
                if is_instant:
                    if not _stack_top_is_own_cast(state, own_cast_names.get(seat, set())):
                        offered_castable[(seat, name)] += 1
                        counted_now.add(name)
                elif _own_turn(state) and _is_main(state):
                    offered_castable[(seat, name)] += 1
                    counted_now.add(name)
            if meta.get("ability_type") == "spell":
                name = canonical_card_name(str(meta.get("source_name") or ""))
                if name:
                    cast_count[(seat, name)] += 1
                    if name in counted_now:
                        cast_in_offer_window[(seat, name)] += 1
                    instant_speed[(seat, name)] = _is_instant_speed(name)
                    if not _own_turn(state):
                        cast_on_opponent_turn[(seat, name)] += 1
                    first_cast_round.setdefault((seat, name), own_round)
                    own_cast_names.setdefault(seat, set()).add(name.strip().casefold())
            if meta.get("ability_type") == "spell":
                spells[seat] += 1
                name = str(meta.get("source_name") or "")
                command_ids = {
                    str(item.get("object_id"))
                    for player in views.players(state)
                    if str(player.get("player_id")) == str(state.get("actor_id"))
                    for item in views._items(player.get("command"))
                }
                if str(meta.get("source_object_id")) in command_ids:
                    commander_turn.setdefault(seat, turn)
                    commander_round.setdefault(seat, own_round)
                    commander_round_by_name[seat].setdefault(name, own_round)
                facts = card_facts(name)
                roles = card_roles(facts) if facts is not None else {}
                if CardRole.WIPE in roles:
                    wipes_cast += 1
                    mine = next(
                        (
                            views.board_summary(p)["creature_power"]
                            for p in views.players(state)
                            if str(p.get("player_id")) == str(state.get("actor_id"))
                        ),
                        0.0,
                    )
                    theirs = max(
                        (
                            views.board_summary(p)["creature_power"]
                            for p in views.players(state)
                            if str(p.get("player_id")) != str(state.get("actor_id"))
                        ),
                        default=0.0,
                    )
                    if mine >= theirs and mine > 0:
                        bad_wipes += 1
                if CardRole.COUNTER in roles:
                    counters_cast += 1
            elif picked_type == "activated_ability":
                abilities_per_turn[(seat, turn)] += 1
            if (
                picked_type == "pass_priority"
                and _own_turn(state)
                and _postcombat(state)
                and not state.get("stack")
            ):
                if any(_meta(o).get("ability_type") == "spell" for o in options):
                    idle_main_with_spell += 1
                if any(
                    o.get("option_type") == "play_land"
                    or _meta(o).get("ability_type") == "play_land"
                    for o in options
                ):
                    idle_main_with_land += 1
        elif decision_class in {"target", "choose_object", "target_amount"}:
            outcome = str((request.get("context") or {}).get("outcome", "")).casefold()
            if outcome in {"detriment", "detriment_to_controller"}:
                for option in chosen:
                    found = views.permanent_owner(
                        str(_meta(option).get("object_id") or option.get("option_id")), state
                    )
                    if found is None:
                        continue
                    removal_total += 1
                    if found[0] == str(state.get("actor_id")) and _opponent_target_offered(
                        options, state, views
                    ):
                        removal_on_own += 1
        elif decision_class == "declare_attacker":
            for option in chosen:
                if option.get("option_type") != "declare_attacker":
                    continue
                attacks += 1
                score, _facts = views.attack_score(option, state)
                if score <= -0.5:
                    bad_attacks += 1
        elif decision_class == "declare_blocker":
            for option in chosen:
                blocks += 1
                _score, facts = views.block_score(option, state)
                if not facts.get("block_survives") and not facts.get("block_kills"):
                    actor = next(
                        (
                            p
                            for p in views.players(state)
                            if str(p.get("player_id")) == str(state.get("actor_id"))
                        ),
                        {},
                    )
                    life = float(actor.get("life", 40) or 40)
                    found = views.permanent_owner(
                        str(_meta(option).get("attacker_id") or ""), state
                    )
                    power = views.creature_power(found[1]) if found else 0
                    if life - power > 5:
                        needless_chumps += 1
    rounds = max(1.0, max_turn / max(1, players))
    decisions = sum(by_class.values())
    # Per-card figures keyed by (seat, card name); first_cast_round is None
    # when the card was offered but never cast. A card can be cast without a
    # counted offer (an instant cast while its top-of-stack guard holds), so
    # the union of offered and cast names is listed. cast_in_offer_window is
    # the part of ``cast`` that happened in a window counted in
    # offered_castable, so cast_in_offer_window / offered_castable never
    # exceeds 1. per_card_version 2 added instant-speed windows; version 3
    # counts a split card once under its combined name and gives
    # first_cast_round as the 1-based round of the seat's own turn. Readers
    # must not mix versions (see compare_reports).
    per_card = [
        {
            "seat": seat,
            "card": name,
            "offered_castable": offered_castable.get((seat, name), 0),
            "cast": cast_count.get((seat, name), 0),
            "cast_in_offer_window": cast_in_offer_window.get((seat, name), 0),
            "cast_on_opponent_turn": cast_on_opponent_turn.get((seat, name), 0),
            "instant_speed": instant_speed.get((seat, name), False),
            "first_cast_round": first_cast_round.get((seat, name)),
        }
        for (seat, name) in sorted(set(offered_castable) | set(cast_count))
    ]
    result: dict[str, Any] = {
        "turns": max_turn,
        "rounds": round(rounds, 2),
        # Game length in own turns: the largest number of own turns any seat
        # had. After eliminations this exceeds rounds (which divides total
        # turns by player count). 0 when no decision record exists.
        "rounds_own_turns": max(own_turn_count.values(), default=0),
        "decisions": decisions,
        "decisions_per_round": round(decisions / rounds, 1),
        "forced_priority": forced,
        "by_class": dict(sorted(by_class.items())),
        "pilot_s": round(pilot_s, 2),
        "spells_cast": sum(spells.values()),
        "spell_offers": spell_offers,
        "spell_offers_without_pilot_knowledge": spell_offers_unknown,
        "spells_per_player_round": round(sum(spells.values()) / players / rounds, 2),
        # The game turn counter at the first commander cast. It counts every player's
        # turns, so it depends on the seat; commander_first_cast_round is the round.
        "commander_first_cast_turn": {str(k): v for k, v in sorted(commander_turn.items())},
        "commander_first_cast_round": {str(k): v for k, v in sorted(commander_round.items())},
        # Partner commanders are separate cards (one may cost {0}), so the first cast of
        # either hides the other; this keeps each commander's round.
        "commander_first_cast_round_by_name": {
            str(k): dict(sorted(v.items())) for k, v in sorted(commander_round_by_name.items())
        },
        "own_turns": len(own_turns),
        "bad_idle_main_with_castable_spell": idle_main_with_spell,
        "bad_idle_main_with_unplayed_land": idle_main_with_land,
        "removal_targets": removal_total,
        "bad_removal_on_own_permanent": removal_on_own,
        "wipes_cast": wipes_cast,
        "bad_wipes_while_ahead": bad_wipes,
        "counters_cast": counters_cast,
        "attacks": attacks,
        "bad_attacks_into_killer": bad_attacks,
        "blocks": blocks,
        "bad_needless_chump_blocks": needless_chumps,
        "max_activations_one_turn": max(abilities_per_turn.values(), default=0),
        "per_card": per_card,
        "per_card_version": 3,
    }
    if by_seat:
        result["by_seat"] = {
            str(seat): {
                key: value
                for key, value in summarize(
                    [r for r in records if _seat(r["request"].get("pilot_state") or {}) == seat],
                    players,
                    by_seat=False,
                ).items()
                if key in _SEAT_KEYS
            }
            for seat in sorted({_seat(r["request"].get("pilot_state") or {}) for r in records})
        }
    return result


def _play(
    command: tuple[str, ...], pod: str, setup: tuple[Any, Any, Any], seed: int
) -> dict[str, Any]:
    scenario, decks, pilots = setup
    scenario = scenario.model_copy(update={"seed": seed})
    runner = XmageFullGameRunner(command, private_card_repository=True)
    records: list[dict[str, Any]] = []
    started = time.monotonic()
    row: dict[str, Any] = {"pod": pod, "seed": seed, "players": len(decks)}
    try:
        with recording(records):
            result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
        row |= {
            "status": "ok",
            "semantic": result.semantic_transcript_sha256,
            "winners": list(result.winner_seats),
        }
    except Exception as exc:  # a failed game is a result row, not a crash
        row |= {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:400]}
    row["wall_s"] = round(time.monotonic() - started, 2)
    row |= summarize(records, len(decks))
    print(json.dumps({k: row[k] for k in row if k not in {"by_class", "by_seat"}}), flush=True)
    return row


def _play_batch(
    command: tuple[str, ...],
    jobs: list[tuple[str, tuple[Any, Any, Any], int]],
) -> list[dict[str, Any]]:
    """Play several games in one bridge JVM process (Owner decision 2026-10-15).

    Measurement only; the bridge must be started with
    -Dcommanderlab.fullGame.gamesPerJvm=N for N >= len(jobs).

    A batched row carries the semantic hash, the winners and a wall time, not the
    per-decision summary of :func:`_play`: the recording hook cannot tell the
    games of one process apart without guessing, so ``decisions_recorded`` is
    False and :func:`totals` keeps those games out of the decision figures. Use
    the default of one game per JVM for decision, pilot-time and card figures.
    """
    game_inputs = []
    job_metas = []
    for pod, setup, seed in jobs:
        scenario, decks, pilots = setup
        game_inputs.append((scenario.model_copy(update={"seed": seed}), decks, pilots))
        job_metas.append((pod, seed, len(decks)))

    runner = XmageFullGameRunner(command, private_card_repository=True)
    started = time.monotonic()
    outcomes = runner.run_batch(game_inputs)
    # One JVM plays the whole chunk, so a game has no wall time of its own: every
    # row carries its share of the chunk, and the shares add up to the chunk total.
    share = round((time.monotonic() - started) / max(1, len(outcomes)), 2)

    rows: list[dict[str, Any]] = []
    for (pod, seed, n_players), outcome in zip(job_metas, outcomes, strict=True):
        row: dict[str, Any] = {"pod": pod, "seed": seed, "players": n_players}
        if isinstance(outcome, Exception):
            row |= {"status": "failed", "error": f"{type(outcome).__name__}: {outcome}"[:400]}
        else:
            row |= {
                "status": "ok",
                "semantic": outcome.semantic_transcript_sha256,
                "winners": list(outcome.winner_seats),
            }
        row |= {"wall_s": share, "decisions_recorded": False}
        print(json.dumps(row), flush=True)
        rows.append(row)
    return rows


_TOTALS = (
    "turns",
    "decisions",
    "forced_priority",
    "wall_s",
    "pilot_s",
    "spells_cast",
    "own_turns",
    "bad_idle_main_with_castable_spell",
    "bad_idle_main_with_unplayed_land",
    "removal_targets",
    "bad_removal_on_own_permanent",
    "wipes_cast",
    "bad_wipes_while_ahead",
    "counters_cast",
    "attacks",
    "bad_attacks_into_killer",
    "blocks",
    "bad_needless_chump_blocks",
)


# Counted for every report but never compared as a metric: how much of what the pilot was
# offered it had no knowledge of says what a verdict is about, not whether a pilot is better.
_CONTEXT_TOTALS = ("spell_offers", "spell_offers_without_pilot_knowledge")

# Counted with the pilot's own scoring function on the state it decided on (``attack_score``,
# ``block_score``). A pilot that follows its score cannot produce one, so a 0 here is not a
# measurement. The rows keep the keys; ``compare`` leaves them out.
_NOT_MEASURED = {
    "bad_attacks_into_killer": "counted with the pilot's own attack score",
    "bad_needless_chump_blocks": "counted with the pilot's own block score",
}

# Above this share of spell options without pilot knowledge, a report is flagged: any value is
# a convention, 1.6 % is what the real pod shows, half of the precon card slots lack knowledge.
_UNKNOWN_SHARE_WARN = 0.05


def totals(report: dict[str, Any]) -> dict[str, float]:
    games = [g for g in report["games"] if g["status"] == "ok"]
    out: dict[str, float] = {
        "games_ok": len(games),
        "games_failed": len(report["games"]) - len(games),
    }
    for key in _TOTALS:
        out[key] = round(sum(float(g.get(key, 0)) for g in games), 2)
    if any("spell_offers" in g for g in games):
        for key in _CONTEXT_TOTALS:
            out[key] = round(sum(float(g.get(key, 0)) for g in games), 2)
        if out["spell_offers"]:
            out["share_spell_offers_without_pilot_knowledge"] = round(
                out["spell_offers_without_pilot_knowledge"] / out["spell_offers"], 4
            )
    if games:
        # Batched games (--games-per-jvm > 1) carry no decision record; they count
        # for the wall time but not for the per-decision figures.
        recorded = [g for g in games if "rounds" in g]
        out["mean_wall_s"] = round(out["wall_s"] / len(games), 1)
        if len(recorded) < len(games):
            out["games_without_decision_record"] = len(games) - len(recorded)
        if recorded:
            out["mean_rounds"] = round(sum(g["rounds"] for g in recorded) / len(recorded), 2)
            # Games with rounds_own_turns (new) vs old reports without it.
            # Same rule as mean_rounds: leave out games without the field.
            with_own_turns = [g for g in recorded if "rounds_own_turns" in g]
            if with_own_turns:
                out["mean_rounds_own_turns"] = round(
                    sum(g["rounds_own_turns"] for g in with_own_turns) / len(with_own_turns), 2
                )
            out["mean_decisions"] = round(out["decisions"] / len(recorded), 0)
            # Per-game player count; reports written before ``players`` was stored
            # fall back to the old 4-player assumption.
            player_rounds = sum(float(g.get("players", 4)) * g["rounds"] for g in recorded)
            out["spells_per_player_round"] = (
                round(out["spells_cast"] / player_rounds, 2) if player_rounds else 0.0
            )
    return out


def totals_by_seat(report: dict[str, Any]) -> dict[str, dict[str, float]]:
    """The ``_TOTALS`` counters of each seat, summed over the ok games with ``by_seat``.

    ``totals`` adds up all seats of a pod; a deck's own figures need the seat.
    """
    out: dict[str, dict[str, float]] = {}
    for game in report["games"]:
        if game.get("status") != "ok":
            continue
        for seat, counters in (game.get("by_seat") or {}).items():
            row = out.setdefault(seat, {"games_ok": 0.0})
            row["games_ok"] += 1
            for key in (*_TOTALS, *_CONTEXT_TOTALS):
                if key in counters:
                    row[key] = round(row.get(key, 0.0) + float(counters[key]), 2)
    return out


def run(args: argparse.Namespace) -> int:
    # Validate games_per_jvm (measurement only; evidence lane stays at 1)
    if args.games_per_jvm < 1:
        raise ValueError("--games-per-jvm must be positive")
    jvm_options = list(args.jvm_option)
    if args.games_per_jvm > 1:
        jvm_options.append(f"-Dcommanderlab.fullGame.gamesPerJvm={args.games_per_jvm}")
    command = bench.bridge_command(args.jar, jvm_options)
    setups = {pod: bench._setup(paths) for pod, paths in bench._pods(args.coverage_pods)}
    jobs = [(pod, setup, seed) for pod, setup in setups.items() for seed in args.seeds]
    run_started = time.monotonic()
    rows: list[dict[str, Any]]
    if args.games_per_jvm == 1:
        # Single game per JVM (default, also used by evidence lane)
        if args.workers <= 1:
            rows = [_play(command, pod, setup, seed) for pod, setup, seed in jobs]
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                futures = [
                    pool.submit(_play, command, pod, setup, seed) for pod, setup, seed in jobs
                ]
                rows = [future.result() for future in futures]
    else:
        # Batched: multiple games per JVM (measurement only)
        size = args.games_per_jvm
        chunks = [jobs[i : i + size] for i in range(0, len(jobs), size)]
        if args.workers <= 1:
            rows = [row for chunk in chunks for row in _play_batch(command, chunk)]
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                batch_futures = [pool.submit(_play_batch, command, chunk) for chunk in chunks]
                rows = [row for future in batch_futures for row in future.result()]
    elapsed_s = round(time.monotonic() - run_started, 1)
    report: dict[str, Any] = {
        "jar": str(args.jar),
        "games_per_jvm": args.games_per_jvm,
        "workers": args.workers,
        "elapsed_s": elapsed_s,
        "games": rows,
    }
    report["not_measured"] = dict(_NOT_MEASURED)
    report["totals"] = totals(report)
    report["totals_by_seat"] = totals_by_seat(report)
    report["cards"] = aggregate_cards(report)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["totals"], indent=1))
    for line in format_rotting(report["cards"]):
        print(line)
    return 0 if all(row["status"] == "ok" for row in rows) else 1


# ---------------------------------------------------------------------------
# cards: per-card cast rate and cards that rot in hand.
#
# ``summarize`` records per (seat, card) how often a cast was offered in a
# countable priority window vs. actually chosen: sorcery-speed cards count in
# own main-phase windows, instant-speed cards in any window whose stack is
# empty or whose top object is not a spell the actor cast earlier.
# Here the per-game figures are aggregated by card name across seats and
# games; the "rotting" list ranks cards that were offered castable in >= 3
# windows of a game but never cast in it. Records without the version-2
# fields (``instant_speed``, ``cast_on_opponent_turn``, ``per_card_version``)
# still aggregate: they predate the instant-speed windows and default to
# sorcery-speed counting.
# ---------------------------------------------------------------------------

_ROTTING_MIN_WINDOWS = 3


def aggregate_cards(report: dict[str, Any]) -> dict[str, Any]:
    """Aggregate per-card cast figures over the ok games of a report.

    ``cards`` and ``rotting`` merge all seats by card name, which is right for one deck
    played in every seat and wrong for a pod of different decks; ``by_seat`` repeats the
    aggregation for each seat on its own.
    """
    result = _aggregate_cards(report, None)
    seats = sorted(
        {
            int(entry["seat"])
            for game in report["games"]
            if game["status"] == "ok"
            for entry in game.get("per_card", [])
            if entry.get("seat") is not None
        }
    )
    result["by_seat"] = {str(seat): _aggregate_cards(report, seat) for seat in seats}
    return result


def _aggregate_cards(report: dict[str, Any], seat: int | None) -> dict[str, Any]:
    games = [g for g in report["games"] if g["status"] == "ok"]
    offered: dict[str, int] = Counter()
    cast: dict[str, int] = Counter()
    cast_in_window: dict[str, int] = Counter()
    cast_on_opponent_turn: dict[str, int] = Counter()
    instant_speed: dict[str, bool] = {}
    seen_in: dict[str, set[int]] = defaultdict(set)
    games_offered: dict[str, int] = Counter()
    games_cast_after_offer: dict[str, int] = Counter()
    first_rounds: dict[str, list[float]] = defaultdict(list)
    rotted_in: dict[str, int] = Counter()
    for game_idx, game in enumerate(games):
        per_game_offered: dict[str, int] = Counter()
        per_game_cast: dict[str, int] = Counter()
        per_game_cast_in_window: dict[str, int] = Counter()
        for entry in game.get("per_card", []):
            if seat is not None and entry.get("seat") != seat:
                continue
            name = str(entry.get("card") or "")
            if not name:
                continue
            n_offered = int(entry.get("offered_castable", 0) or 0)
            n_cast = int(entry.get("cast", 0) or 0)
            # Records before per_card_version 3 do not split out the casts inside a
            # counted window; their cast count stands in for it.
            n_in_window = int(entry.get("cast_in_offer_window", n_cast) or 0)
            offered[name] += n_offered
            cast[name] += n_cast
            cast_in_window[name] += n_in_window
            cast_on_opponent_turn[name] += int(entry.get("cast_on_opponent_turn", 0) or 0)
            if entry.get("instant_speed"):
                instant_speed[name] = True
            per_game_offered[name] += n_offered
            per_game_cast[name] += n_cast
            per_game_cast_in_window[name] += n_in_window
            if n_offered or n_cast:
                seen_in[name].add(game_idx)
            first = entry.get("first_cast_round")
            if first is not None:
                first_rounds[name].append(float(first))
        for name, n_offered in per_game_offered.items():
            if n_offered:
                games_offered[name] += 1
                if per_game_cast_in_window.get(name, 0):
                    games_cast_after_offer[name] += 1
            if n_offered >= _ROTTING_MIN_WINDOWS and per_game_cast.get(name, 0) == 0:
                rotted_in[name] += 1
    cards = [
        {
            "card": name,
            "games_seen": len(seen_in[name]),
            "offered_castable": offered[name],
            "cast": cast[name],
            "cast_in_offer_window": cast_in_window[name],
            "cast_on_opponent_turn": cast_on_opponent_turn[name],
            "instant_speed": instant_speed.get(name, False),
            # Casts in a counted window per counted window, at most 1.
            "cast_rate": (
                round(min(cast_in_window[name], offered[name]) / offered[name], 3)
                if offered[name]
                else 0.0
            ),
            # Share of the games with at least one counted offer in which the card
            # was cast in such a window. A window rate counts a card held for ten
            # windows ten times; this counts the game once.
            "games_offered": games_offered[name],
            "games_cast_after_offer": games_cast_after_offer[name],
            "cast_share": (
                round(games_cast_after_offer[name] / games_offered[name], 3)
                if games_offered[name]
                else None
            ),
            "mean_first_cast_round": (
                round(sum(first_rounds[name]) / len(first_rounds[name]), 2)
                if first_rounds[name]
                else None
            ),
        }
        for name in sorted(offered)
    ]
    rotting_entries: list[dict[str, Any]] = [
        {"card": name, "games_rotted": count} for name, count in rotted_in.items()
    ]
    rotting = sorted(
        rotting_entries,
        key=lambda item: (-int(item["games_rotted"]), str(item["card"])),
    )
    return {"cards": cards, "rotting": rotting}


def format_rotting(cards: dict[str, Any], limit: int = 10) -> list[str]:
    """Human-readable lines for the most-rotting cards."""
    lines = ["most rotting cards (offered castable, never cast):"]
    for entry in cards.get("rotting", [])[:limit]:
        lines.append(f"  {entry['card']}: rotted in {entry['games_rotted']} game(s)")
    if len(lines) == 1:
        lines.append("  (none)")
    return lines


# ---------------------------------------------------------------------------
# compare: paired seed-noise analysis.
#
# Games are paired by (pod, seed) across the two reports; per metric the mean
# per-game delta is reported with a 95% paired bootstrap interval (fixed seed,
# 2000 resamples, stdlib only). ``changed`` is true when the interval excludes 0.
#
# About twenty metrics are compared at once, so some interval excludes 0 by chance
# in most comparisons of two identical pilots (``calibrate`` measures how often).
# Each metric therefore also gets a sign-flip permutation p-value, and the p-values
# of the metrics that move at all are Holm-adjusted: ``significant`` is the verdict
# that holds up against the number of looks. A change that is judged on one metric
# names it up front (``--primary``); that metric is tested alone, the rest are
# exploratory.
# ---------------------------------------------------------------------------

_BOOTSTRAP_SEED = 20261016
_BOOTSTRAP_RESAMPLES = 2000
_FLIP_SEED = 20261022
_FLIPS = 4000
_ALPHA = 0.05
# (z(1 - alpha/2) + z(power)) for alpha = 5 % two-sided and 80 % power.
_POWER_FACTOR = 2.8
_MIN_PAIRED_SEEDS_PER_POD = 10

_COMPARE_METRICS = tuple(
    key for key in (*_TOTALS, "spells_per_player_round") if key not in _NOT_MEASURED
)


def _game_key(game: dict[str, Any]) -> tuple[Any, Any]:
    return (game.get("pod"), game.get("seed"))


def pair_games(
    report_a: dict[str, Any], report_b: dict[str, Any]
) -> tuple[list[tuple[tuple[Any, Any], dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
    """Pair the ok games of two reports by (pod, seed).

    Returns the paired games and the unpaired/failed games with their reasons;
    nothing is silently dropped.
    """

    def index(
        report: dict[str, Any],
    ) -> tuple[dict[tuple[Any, Any], dict[str, Any]], list[tuple[tuple[Any, Any], str]]]:
        ok: dict[tuple[Any, Any], dict[str, Any]] = {}
        problems: list[tuple[tuple[Any, Any], str]] = []
        for game in report.get("games", []):
            key = _game_key(game)
            if game.get("status") != "ok":
                problems.append((key, f"status={game.get('status')}"))
            elif key in ok:
                problems.append((key, "duplicate (pod, seed)"))
            else:
                ok[key] = game
        return ok, problems

    a_ok, a_problems = index(report_a)
    b_ok, b_problems = index(report_b)
    a_bad_keys = {key for key, _ in a_problems}
    b_bad_keys = {key for key, _ in b_problems}
    paired = sorted(
        ((key, a_ok[key], b_ok[key]) for key in a_ok.keys() & b_ok.keys()),
        key=lambda item: repr(item[0]),
    )
    unpaired = [
        {"report": side, "pod": key[0], "seed": key[1], "reason": reason}
        for side, problems in (("a", a_problems), ("b", b_problems))
        for key, reason in problems
    ]
    for key in sorted(a_ok.keys() - b_ok.keys() - b_bad_keys, key=repr):
        unpaired.append({"report": "a", "pod": key[0], "seed": key[1], "reason": "no match in b"})
    for key in sorted(b_ok.keys() - a_ok.keys() - a_bad_keys, key=repr):
        unpaired.append({"report": "b", "pod": key[0], "seed": key[1], "reason": "no match in a"})
    unpaired.sort(key=lambda game: repr((game["report"], game["pod"], game["seed"])))
    return paired, unpaired


def _per_card_versions(report: dict[str, Any]) -> set[Any]:
    """per_card_version of the ok games of a report (1 when not recorded)."""
    return {
        game.get("per_card_version", 1)
        for game in report.get("games", [])
        if game.get("status") == "ok"
    }


def bootstrap_mean_ci(
    deltas: list[float],
    *,
    seed: int = _BOOTSTRAP_SEED,
    resamples: int = _BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    """95% percentile bootstrap confidence interval for the mean (stdlib only).

    Resamples the paired per-game deltas with replacement under a fixed seed, so
    the same two reports always yield the same interval.
    """
    rng = random.Random(seed)
    n = len(deltas)
    means = sorted(sum(deltas[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def sign_flip_p_value(deltas: list[float], *, seed: int = _FLIP_SEED, flips: int = _FLIPS) -> float:
    """Two-sided sign-flip permutation p-value that the mean paired delta is zero.

    Under "the change moves nothing" each pair's delta is as likely positive as negative, so
    flipping signs gives the distribution of the mean. Valid for any number of pairs (the
    bootstrap interval is optimistic with a dozen). Exact when all ``2**n`` flips fit in
    ``flips``; otherwise ``flips`` seeded random flips, never below ``1 / (flips + 1)``.
    """
    if not any(deltas):
        return 1.0
    n = len(deltas)
    observed = abs(sum(deltas))
    # Tolerance: sums of the same floats in another order differ in the last digits.
    threshold = observed - 1e-9 * max(1.0, observed)
    if 2**n <= flips:
        extreme = sum(
            abs(sum(d if (bits >> i) & 1 else -d for i, d in enumerate(deltas))) >= threshold
            for bits in range(2**n)
        )
        return extreme / 2**n
    rng = random.Random(seed)
    extreme = 0
    for _ in range(flips):
        bits = rng.getrandbits(n)
        total = sum(d if (bits >> i) & 1 else -d for i, d in enumerate(deltas))
        if abs(total) >= threshold:
            extreme += 1
    return (extreme + 1) / (flips + 1)


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values (family-wise error control), same keys."""
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (key, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * p))
        adjusted[key] = running
    return adjusted


def minimum_detectable_change(deltas: list[float]) -> float:
    """Smallest mean paired change this many pairs detect with 80 % power at 5 % (two-sided).

    ``2.8 * sd / sqrt(n)`` from the spread of the observed paired deltas: a planning figure
    for how large a change must be to show, not a statement about the change.
    """
    n = len(deltas)
    if n < 2:
        return float("inf")
    mean = sum(deltas) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in deltas) / (n - 1))
    return _POWER_FACTOR * sd / math.sqrt(n)


def knowledge_share(games: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Spell options the pilot saw in ``games`` and how many were for a card it knows nothing about.

    None when no game carries the counters (a report written before they existed).
    """
    counted = [g for g in games if "spell_offers" in g]
    if not counted:
        return None
    offers = sum(int(g["spell_offers"]) for g in counted)
    unknown = sum(int(g.get("spell_offers_without_pilot_knowledge", 0)) for g in counted)
    return {
        "spell_offers": offers,
        "without_pilot_knowledge": unknown,
        "share": (unknown / offers) if offers else None,
        "games": len(counted),
    }


def compare_reports(
    report_a: dict[str, Any],
    report_b: dict[str, Any],
    *,
    primary: str | None = None,
    resamples: int = _BOOTSTRAP_RESAMPLES,
    flips: int = _FLIPS,
) -> dict[str, Any]:
    """Compare two pilot reports on their paired (pod, seed) games.

    Per metric: mean per-game delta with a 95% paired bootstrap interval (``changed`` when it
    excludes 0), a sign-flip p-value, the smallest change these pairs detect (``mde80``) and
    ``significant``: the p-value Holm-adjusted over the metrics that move, or, for ``primary``,
    the p-value alone (named before the games, so one look). Pods with fewer than 10 paired
    seeds get a noise warning.
    """
    paired, unpaired = pair_games(report_a, report_b)
    metrics: dict[str, dict[str, Any]] = {}
    deltas_of: dict[str, list[float]] = {}
    for key in _COMPARE_METRICS:
        deltas = [
            float(game_b.get(key, 0)) - float(game_a.get(key, 0)) for _, game_a, game_b in paired
        ]
        if not deltas:
            continue
        before = sum(float(game_a.get(key, 0)) for _, game_a, _ in paired) / len(paired)
        after = sum(float(game_b.get(key, 0)) for _, _, game_b in paired) / len(paired)
        mean_delta = sum(deltas) / len(deltas)
        ci_lo, ci_hi = bootstrap_mean_ci(deltas, resamples=resamples)
        deltas_of[key] = deltas
        metrics[key] = {
            "paired_games": len(deltas),
            "before_mean": before,
            "after_mean": after,
            "mean_delta": mean_delta,
            "ci95": [ci_lo, ci_hi],
            "changed": bool(ci_lo > 0 or ci_hi < 0),
            "p": sign_flip_p_value(deltas, flips=flips),
            "mde80": minimum_detectable_change(deltas),
        }
    if primary is not None and primary not in metrics:
        raise ValueError(f"primary metric {primary!r} is not among the compared metrics")
    # The family: every metric that moves in at least one pair, except the primary one.
    family = {
        key: metric["p"]
        for key, metric in metrics.items()
        if key != primary and any(deltas_of[key])
    }
    adjusted = holm_adjust(family)
    for key, metric in metrics.items():
        if key == primary:
            metric["role"] = "primary"
            metric["p_adjusted"] = metric["p"]
        else:
            metric["role"] = "exploratory"
            metric["p_adjusted"] = adjusted.get(key, 1.0)
        metric["significant"] = bool(metric["p_adjusted"] < _ALPHA)
    seeds_per_pod: dict[str, int] = {}
    for (pod, _seed), _, _ in paired:
        seeds_per_pod[str(pod)] = seeds_per_pod.get(str(pod), 0) + 1
    warnings = [
        f"WARNING: pod {pod} has only {count} paired seeds "
        f"(fewer than {_MIN_PAIRED_SEEDS_PER_POD}); treat differences as noise"
        for pod, count in sorted(seeds_per_pod.items())
        if count < _MIN_PAIRED_SEEDS_PER_POD
    ]
    # Per-card figures are never compared across different per_card_version
    # values: version 2 changed which windows count as offers/casts for
    # instant-speed cards, so the figures mean different things.
    knowledge = {
        "before": knowledge_share([game_a for _, game_a, _ in paired]),
        "after": knowledge_share([game_b for _, _, game_b in paired]),
    }
    for arm, figures in knowledge.items():
        share = figures["share"] if figures else None
        if share is not None and share >= _UNKNOWN_SHARE_WARN:
            warnings.append(
                f"WARNING: {share:.1%} of the spell options the pilot saw ({arm}) are for cards "
                "it has no knowledge of; it plays them as spells without cost or role, so "
                "figures about those cards measure that"
            )
    versions = sorted((_per_card_versions(report_a) | _per_card_versions(report_b)), key=repr)
    if len(versions) > 1:
        warnings.append(
            "per-card figures not compared across different per_card_version "
            f"values: {', '.join(map(repr, versions))}"
        )
    return {
        "paired_games": len(paired),
        "paired_seeds_per_pod": seeds_per_pod,
        "primary": primary,
        "family_size": len(family),
        "metrics": metrics,
        "pilot_knowledge": knowledge,
        "unpaired_games": unpaired,
        "warnings": warnings,
    }


def _knowledge_line(result: dict[str, Any]) -> str | None:
    """One line: the share of spell options without pilot knowledge in each arm."""
    knowledge = result.get("pilot_knowledge") or {}
    parts = []
    for arm in ("before", "after"):
        figures = knowledge.get(arm)
        if not figures or figures["share"] is None:
            continue
        parts.append(
            f"{arm} {figures['share']:.1%} ({figures['without_pilot_knowledge']} of "
            f"{figures['spell_offers']})"
        )
    if not parts:
        return None
    return "spell options for cards without pilot knowledge: " + ", ".join(parts)


def _not_compared_line() -> str:
    return (
        "not compared: "
        + ", ".join(sorted(_NOT_MEASURED))
        + " (counted with the pilot's own score, so a pilot that follows it never shows one)"
    )


def _verdict(metric: dict[str, Any]) -> str:
    if metric["significant"]:
        return "CHANGED"
    return "ci only" if metric["changed"] else "same"


def format_comparison(result: dict[str, Any]) -> list[str]:
    """Human-readable lines for a ``compare_reports`` result."""
    lines = [f"paired games: {result['paired_games']}"]
    primary = result.get("primary")
    if primary and primary in result["metrics"]:
        metric = result["metrics"][primary]
        lines.append(
            f"PRIMARY {primary}: {_verdict(metric)} (delta {metric['mean_delta']:+.2f}, "
            f"p={metric['p']:.4f}, detectable change {metric['mde80']:.2f})"
        )
    for key in _COMPARE_METRICS:
        metric = result["metrics"].get(key)
        if metric is None:
            lines.append(f"{key:40s} no paired games")
            continue
        lo, hi = metric["ci95"]
        role = "*" if metric["role"] == "primary" else " "
        lines.append(
            f"{role}{key:39s} {metric['before_mean']:>10.2f} -> {metric['after_mean']:<10.2f} "
            f"delta {metric['mean_delta']:+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]  "
            f"p={metric['p']:.4f} adj={metric['p_adjusted']:.4f} "
            f"min {metric['mde80']:.2f}  {_verdict(metric)}"
        )
    ci_only = sorted(
        k for k, m in result["metrics"].items() if m["changed"] and not m["significant"]
    )
    lines.append(
        f"CHANGED = adjusted p < {_ALPHA} (Holm over {result['family_size']} moving metrics"
        f"{'; the primary metric alone' if primary else ''}); 'ci only' = the interval excludes 0 "
        f"but the adjusted p does not: {len(ci_only)} of {len(result['metrics'])} metrics"
    )
    if not primary:
        lines.append("no primary metric named: every metric above is exploratory (--primary)")
    knowledge_line = _knowledge_line(result)
    if knowledge_line:
        lines.append(knowledge_line)
    lines.append(_not_compared_line())
    for game in result["unpaired_games"]:
        lines.append(
            f"unpaired: report={game['report']} pod={game['pod']} "
            f"seed={game['seed']} reason={game['reason']}"
        )
    lines.extend(result["warnings"])
    return lines


def format_markdown(result: dict[str, Any], path_a: Path, path_b: Path) -> list[str]:
    """A block for a pull request: the primary metric, then what else moved, then the limits."""
    lines = [
        f"Pilot comparison `{path_a.name}` -> `{path_b.name}`: {result['paired_games']} paired "
        f"games in {len(result['paired_seeds_per_pod'])} pod(s)."
    ]
    primary = result.get("primary")
    shown = [k for k in _COMPARE_METRICS if k in result["metrics"]]
    moved = [k for k in shown if k == primary or result["metrics"][k]["changed"]]
    lines += [
        "",
        "| metric | before | after | delta | 95% CI | p | adjusted p | detectable | verdict |",
        "|---|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for key in moved:
        m = result["metrics"][key]
        name = f"**{key}** (primary)" if key == primary else key
        lines.append(
            f"| {name} | {m['before_mean']:.2f} | {m['after_mean']:.2f} | {m['mean_delta']:+.2f} "
            f"| [{m['ci95'][0]:+.2f}, {m['ci95'][1]:+.2f}] | {m['p']:.4f} "
            f"| {m['p_adjusted']:.4f} | {m['mde80']:.2f} | {_verdict(m)} |"
        )
    if not moved:
        lines.append("| (no metric moved) | | | | | | | | |")
    lines.append("")
    lines.append(
        f"{len(shown)} metrics compared; adjusted p is Holm over {result['family_size']} moving "
        f"metrics{
            ' (the primary metric is tested alone)'
            if primary
            else ' and nothing was named as primary, so every row is exploratory'
        }. 'detectable' is the smallest "
        "mean change these pairs detect with 80 % power."
    )
    knowledge_line = _knowledge_line(result)
    if knowledge_line:
        lines.append(f"- {knowledge_line}")
    lines.append(f"- {_not_compared_line()}")
    lines.extend(f"- {w}" for w in result["warnings"])
    return lines


def comparison_payload(result: dict[str, Any], path_a: Path, path_b: Path) -> dict[str, Any]:
    """JSON-serializable comparison payload for ``--json`` (consumed by later reports)."""
    metrics = {
        key: {
            "paired_games": metric["paired_games"],
            "before_mean": round(metric["before_mean"], 4),
            "after_mean": round(metric["after_mean"], 4),
            "mean_delta": round(metric["mean_delta"], 4),
            "ci95": [round(metric["ci95"][0], 4), round(metric["ci95"][1], 4)],
            "changed": metric["changed"],
            "p": round(metric["p"], 6),
            "p_adjusted": round(metric["p_adjusted"], 6),
            "significant": metric["significant"],
            "role": metric["role"],
            "mde80": round(metric["mde80"], 4) if math.isfinite(metric["mde80"]) else None,
        }
        for key, metric in result["metrics"].items()
    }
    return {
        "report_a": str(path_a),
        "report_b": str(path_b),
        "paired_games": result["paired_games"],
        "paired_seeds_per_pod": result["paired_seeds_per_pod"],
        "primary": result.get("primary"),
        "family_size": result["family_size"],
        "metrics": metrics,
        "pilot_knowledge": result.get("pilot_knowledge"),
        "not_compared": dict(_NOT_MEASURED),
        "unpaired_games": result["unpaired_games"],
        "warnings": result["warnings"],
    }


def compare(args: argparse.Namespace) -> int:
    report_a = json.loads(args.a.read_text(encoding="utf-8"))
    report_b = json.loads(args.b.read_text(encoding="utf-8"))
    result = compare_reports(report_a, report_b, primary=getattr(args, "primary", None))
    for line in format_comparison(result):
        print(line)
    if getattr(args, "markdown", False):
        print()
        for line in format_markdown(result, args.a, args.b):
            print(line)
    if args.json is not None:
        args.json.write_text(
            json.dumps(comparison_payload(result, args.a, args.b), indent=1) + "\n",
            encoding="utf-8",
        )
    return 0


_CALIBRATION_SEED = 20261023


def calibrate_report(
    report: dict[str, Any],
    *,
    rounds: int = 200,
    resamples: int = 400,
    flips: int = 1000,
    seed: int = _CALIBRATION_SEED,
) -> dict[str, Any]:
    """How often does comparing two pilots that differ in nothing flag a change?

    The ok games of one report are shuffled and split into two arms of equal size whose games
    are then paired in order. The pairs are unrelated (a pilot change that diverges the games
    couples them only weakly, so this is the conservative null), so every flag is false.
    Reports the share of rounds in which any metric is flagged by the interval alone and
    after Holm, and the share per metric.
    """
    games = [g for g in report.get("games", []) if g.get("status") == "ok"]
    half = len(games) // 2
    if half < 3:
        raise ValueError(f"need at least 6 ok games to split into two arms, got {len(games)}")
    rng = random.Random(seed)
    any_ci = any_holm = 0
    per_metric: Counter[str] = Counter()
    for _ in range(rounds):
        order = games[:]
        rng.shuffle(order)
        arm_a = [{**order[i], "pod": "null", "seed": i} for i in range(half)]
        arm_b = [{**order[half + i], "pod": "null", "seed": i} for i in range(half)]
        result = compare_reports(
            {"games": arm_a}, {"games": arm_b}, resamples=resamples, flips=flips
        )
        flagged = [k for k, m in result["metrics"].items() if m["changed"]]
        any_ci += bool(flagged)
        any_holm += any(m["significant"] for m in result["metrics"].values())
        per_metric.update(flagged)
    return {
        "games": len(games),
        "pairs": half,
        "rounds": rounds,
        "any_metric_flagged_by_interval": any_ci / rounds,
        "any_metric_significant_after_holm": any_holm / rounds,
        "per_metric_flagged_by_interval": {
            k: per_metric[k] / rounds for k in sorted(per_metric, key=lambda k: -per_metric[k])
        },
    }


def calibrate(args: argparse.Namespace) -> int:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    result = calibrate_report(report, rounds=args.rounds)
    print(
        f"{result['games']} ok games -> {result['pairs']} unrelated pairs, {result['rounds']} rounds, "
        "no change between the arms"
    )
    print(
        f"any metric flagged by its interval alone: {result['any_metric_flagged_by_interval']:.1%}"
    )
    print(
        "any metric significant after Holm:        "
        f"{result['any_metric_significant_after_holm']:.1%}"
    )
    worst = list(result["per_metric_flagged_by_interval"].items())[:5]
    print("most often flagged by interval: " + ", ".join(f"{k} {v:.0%}" for k, v in worst))
    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    play = sub.add_parser("run")
    play.add_argument("--jar", type=Path, required=True)
    play.add_argument("--out", type=Path, required=True)
    play.add_argument("--seeds", type=bench._seeds, default=bench._seeds("1-4"))
    play.add_argument("--coverage-pods", action="store_true")
    play.add_argument("--jvm-option", action="append", default=[])
    play.add_argument("--workers", type=int, default=1)
    play.add_argument(
        "--games-per-jvm",
        type=int,
        default=1,
        help="play up to N games in one bridge JVM (default: 1, measurement only). "
        "Requires the bridge to support -Dcommanderlab.fullGame.gamesPerJvm=N.",
    )
    play.set_defaults(func=run)
    diff = sub.add_parser("compare")
    diff.add_argument("a", type=Path)
    diff.add_argument("b", type=Path)
    diff.add_argument("--json", type=Path, default=None, help="write the comparison as JSON")
    diff.add_argument(
        "--primary",
        choices=_COMPARE_METRICS,
        default=None,
        help="the one metric the change is judged on, named before the games were played",
    )
    diff.add_argument("--markdown", action="store_true", help="also print a block for a PR")
    diff.set_defaults(func=compare)
    cal = sub.add_parser(
        "calibrate",
        help="false-positive rate of compare on a report (two arms that differ in nothing)",
    )
    cal.add_argument("report", type=Path)
    cal.add_argument("--rounds", type=int, default=200)
    cal.add_argument("--json", type=Path, default=None)
    cal.set_defaults(func=calibrate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
