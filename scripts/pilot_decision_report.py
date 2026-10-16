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
patches the policy class, so games must not share a process) and with a private card
database per bridge JVM.

The figures are measurements of local games for pilot work, not qualification
evidence. Lower is better for every "bad_*" counter.
"""

from __future__ import annotations

import argparse
import json
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

from commander_lab.agents.card_knowledge import card_facts, card_roles  # noqa: E402
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


def _own_turn(state: dict[str, Any]) -> bool:
    return str(state.get("active_player_id", "")) == str(state.get("actor_id", ""))


def _seat(state: dict[str, Any]) -> int:
    return int(state.get("seat", -1)) + 1


def summarize(records: list[dict[str, Any]], players: int) -> dict[str, Any]:
    """Play-quality figures of one recorded game."""
    by_class: Counter[str] = Counter()
    forced = 0
    spells: Counter[int] = Counter()
    commander_turn: dict[int, int] = {}
    idle_main_with_spell = 0
    idle_main_with_land = 0
    own_turns: set[tuple[int, int]] = set()
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
        if _own_turn(state):
            own_turns.add((seat, turn))
        if decision_class == "priority":
            if len(options) == 1:
                forced += 1
                continue
            picked = chosen[0] if chosen else {}
            picked_type = str(picked.get("option_type", ""))
            meta = _meta(picked)
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
                    if found[0] == str(state.get("actor_id")):
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
    return {
        "turns": max_turn,
        "rounds": round(rounds, 2),
        "decisions": decisions,
        "decisions_per_round": round(decisions / rounds, 1),
        "forced_priority": forced,
        "by_class": dict(sorted(by_class.items())),
        "pilot_s": round(pilot_s, 2),
        "spells_cast": sum(spells.values()),
        "spells_per_player_round": round(sum(spells.values()) / players / rounds, 2),
        "commander_first_cast_turn": {str(k): v for k, v in sorted(commander_turn.items())},
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
    }


def _play(
    command: tuple[str, ...],
    pod: str,
    setup: tuple[Any, Any, Any],
    seed: int,
    private: bool = False,
) -> dict[str, Any]:
    scenario, decks, pilots = setup
    scenario = scenario.model_copy(update={"seed": seed})
    runner = XmageFullGameRunner(command, private_card_repository=private)
    records: list[dict[str, Any]] = []
    started = time.monotonic()
    row: dict[str, Any] = {"pod": pod, "seed": seed}
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
    print(json.dumps({k: row[k] for k in row if k != "by_class"}), flush=True)
    return row


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
        out["mean_rounds"] = round(sum(g["rounds"] for g in games) / len(games), 2)
        out["mean_wall_s"] = round(out["wall_s"] / len(games), 1)
        out["mean_decisions"] = round(out["decisions"] / len(games), 0)
        rounds = sum(g["rounds"] for g in games)
        players = 4
        out["spells_per_player_round"] = round(out["spells_cast"] / players / rounds, 2)
    return out


def run(args: argparse.Namespace) -> int:
    command = bench.bridge_command(args.jar, args.jvm_option)
    setups = {pod: bench._setup(paths) for pod, paths in bench._pods(args.coverage_pods)}
    jobs = [(pod, setup, seed) for pod, setup in setups.items() for seed in args.seeds]
    if args.workers <= 1:
        rows = [_play(command, pod, setup, seed) for pod, setup, seed in jobs]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [
                pool.submit(_play, command, pod, setup, seed, True) for pod, setup, seed in jobs
            ]
            rows = [future.result() for future in futures]
    report: dict[str, Any] = {"jar": str(args.jar), "games": rows}
    report["totals"] = totals(report)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["totals"], indent=1))
    return 0 if all(row["status"] == "ok" for row in rows) else 1


def compare(args: argparse.Namespace) -> int:
    a, b = (totals(json.loads(path.read_text(encoding="utf-8"))) for path in (args.a, args.b))
    for key in sorted(a.keys() | b.keys()):
        before, after = a.get(key, 0.0), b.get(key, 0.0)
        change = f"{100 * (after / before - 1):+.0f} %" if before else ""
        print(f"{key:40s} {before:>10} -> {after:<10} {change}")
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
    play.set_defaults(func=run)
    diff = sub.add_parser("compare")
    diff.add_argument("a", type=Path)
    diff.add_argument("b", type=Path)
    diff.set_defaults(func=compare)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
