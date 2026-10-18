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


def totals(report: dict[str, Any]) -> dict[str, float]:
    games = [g for g in report["games"] if g["status"] == "ok"]
    out: dict[str, float] = {
        "games_ok": len(games),
        "games_failed": len(report["games"]) - len(games),
    }
    for key in _TOTALS:
        out[key] = round(sum(float(g.get(key, 0)) for g in games), 2)
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
            for key in _TOTALS:
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
# 2000 resamples, stdlib only). A metric is CHANGED only when the interval
# excludes 0, so seed noise and a real shift do not look the same.
# ---------------------------------------------------------------------------

_BOOTSTRAP_SEED = 20261016
_BOOTSTRAP_RESAMPLES = 2000
_MIN_PAIRED_SEEDS_PER_POD = 10

_COMPARE_METRICS = (*_TOTALS, "spells_per_player_round")


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


def compare_reports(report_a: dict[str, Any], report_b: dict[str, Any]) -> dict[str, Any]:
    """Compare two pilot reports on their paired (pod, seed) games.

    Per metric: mean per-game delta with a 95% paired bootstrap interval; the
    metric is marked CHANGED only when the interval excludes 0. Pods with fewer
    than 10 paired seeds get a noise warning.
    """
    paired, unpaired = pair_games(report_a, report_b)
    metrics: dict[str, dict[str, Any]] = {}
    for key in _COMPARE_METRICS:
        deltas = [
            float(game_b.get(key, 0)) - float(game_a.get(key, 0)) for _, game_a, game_b in paired
        ]
        if not deltas:
            continue
        before = sum(float(game_a.get(key, 0)) for _, game_a, _ in paired) / len(paired)
        after = sum(float(game_b.get(key, 0)) for _, _, game_b in paired) / len(paired)
        mean_delta = sum(deltas) / len(deltas)
        ci_lo, ci_hi = bootstrap_mean_ci(deltas)
        metrics[key] = {
            "paired_games": len(deltas),
            "before_mean": before,
            "after_mean": after,
            "mean_delta": mean_delta,
            "ci95": [ci_lo, ci_hi],
            "changed": bool(ci_lo > 0 or ci_hi < 0),
        }
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
    versions = sorted((_per_card_versions(report_a) | _per_card_versions(report_b)), key=repr)
    if len(versions) > 1:
        warnings.append(
            "per-card figures not compared across different per_card_version "
            f"values: {', '.join(map(repr, versions))}"
        )
    return {
        "paired_games": len(paired),
        "paired_seeds_per_pod": seeds_per_pod,
        "metrics": metrics,
        "unpaired_games": unpaired,
        "warnings": warnings,
    }


def format_comparison(result: dict[str, Any]) -> list[str]:
    """Human-readable lines for a ``compare_reports`` result."""
    lines = [f"paired games: {result['paired_games']}"]
    for key in _COMPARE_METRICS:
        metric = result["metrics"].get(key)
        if metric is None:
            lines.append(f"{key:40s} no paired games")
            continue
        lo, hi = metric["ci95"]
        flag = "CHANGED" if metric["changed"] else "same"
        lines.append(
            f"{key:40s} {metric['before_mean']:>10.2f} -> {metric['after_mean']:<10.2f} "
            f"delta {metric['mean_delta']:+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]  {flag}"
        )
    for game in result["unpaired_games"]:
        lines.append(
            f"unpaired: report={game['report']} pod={game['pod']} "
            f"seed={game['seed']} reason={game['reason']}"
        )
    lines.extend(result["warnings"])
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
        }
        for key, metric in result["metrics"].items()
    }
    return {
        "report_a": str(path_a),
        "report_b": str(path_b),
        "paired_games": result["paired_games"],
        "paired_seeds_per_pod": result["paired_seeds_per_pod"],
        "metrics": metrics,
        "unpaired_games": result["unpaired_games"],
        "warnings": result["warnings"],
    }


def compare(args: argparse.Namespace) -> int:
    report_a = json.loads(args.a.read_text(encoding="utf-8"))
    report_b = json.loads(args.b.read_text(encoding="utf-8"))
    result = compare_reports(report_a, report_b)
    for line in format_comparison(result):
        print(line)
    if args.json is not None:
        args.json.write_text(
            json.dumps(comparison_payload(result, args.a, args.b), indent=1) + "\n",
            encoding="utf-8",
        )
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
    diff.set_defaults(func=compare)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
