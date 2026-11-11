#!/usr/bin/env python3
"""S1 spike: what does look-ahead by restart cost, and does it change the pilot's choice?

Measurement only (issue #1168). Nothing here is evidence of deck strength and nothing here
changes the pilots, the runner or the bridge.

Idea: a game on the pinned engine is deterministic for one seed and one sequence of
answers. To look ahead from a decision, start a fresh game with the same seed, feed it the
recorded answers up to that decision, answer the decision with a candidate option, let the
rule pilots play on for a fixed horizon and score the board. This needs no engine change.
The price is a new bridge process per candidate and a replay of the whole prefix.

    python scripts/spike_s1_lookahead.py determinism --seed 7 --out out.json
    python scripts/spike_s1_lookahead.py search --seed 7 --samples 4 --out out.json

The bridge command comes from COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD. The score is a
plain board comparison (see ``board_score``); the search sees the rollout with the real
library order (an upper bound, reported as such).
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commander_lab.candidates.models import FutureXmageScenario  # noqa: E402
from commander_lab.engine.rules.full_game import (  # noqa: E402
    FullGamePilotBinding,
    XmageFullGameRunner,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength  # noqa: E402
from commander_lab.qualification.current_boundary.bridge_launcher import (  # noqa: E402
    canonical_xmage_engine_pin,
)
from commander_lab.semantic_replay.fingerprint import (  # noqa: E402
    build_object_index,
    option_fingerprint,
    seat_map_from_pilot_state,
)
from commander_lab.studio import play as studio_play  # noqa: E402

HORIZON_TURNS = 4  # one full round of a four-player table after the branch decision
CHECKPOINT_TURNS = (8, 16, 24)  # board score of seat 0 at the first decision of these turns
MAX_PREFIX = 3000  # no search later than this decision: the replay would outlast the 2-minute limit


class StopRollout(Exception):
    """Raised by the policy when the horizon is reached; carries nothing, state is on the policy."""


class Diverged(Exception):
    """The replayed game asked something other than the recording."""


_ID_KEYS = ("selected_option_ids", "ordering")
_GAME_KEYS = ("decision_id", "actor_id")  # belong to one game; set from the live decision


def option_prints(decision: dict[str, Any]) -> dict[str, str]:
    """Stable fingerprint per offered option (option ids change from game to game)."""
    state = decision["pilot_state"]
    mapping = seat_map_from_pilot_state(state)
    index = build_object_index(state, mapping)
    return {
        str(option["option_id"]): option_fingerprint(option, state, mapping, index)
        for option in decision.get("legal_options") or []
        if isinstance(option, dict) and option.get("option_id") is not None
    }


def portable(decision: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    """The answer with option ids replaced by fingerprints, so it can be replayed."""
    prints = option_prints(decision)
    out: dict[str, Any] = {
        k: v for k, v in answer.items() if k not in _ID_KEYS and k not in _GAME_KEYS
    }
    for key in _ID_KEYS:
        out[key] = [prints[str(oid)] for oid in answer.get(key) or []]
    return out


def concrete(decision: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any] | None:
    """The stored answer in this game's option ids, or ``None`` when an option is missing."""
    by_print: dict[str, list[str]] = {}
    for oid, fingerprint in option_prints(decision).items():
        by_print.setdefault(fingerprint, []).append(oid)
    out: dict[str, Any] = {k: copy.deepcopy(v) for k, v in stored.items() if k not in _ID_KEYS}
    for key in _GAME_KEYS:
        out[key] = decision[key]
    used: set[str] = set()
    for key in _ID_KEYS:
        ids: list[str] = []
        for fingerprint in stored.get(key) or []:
            free = [oid for oid in by_print.get(fingerprint, []) if oid not in used]
            if not free:
                return None
            used.add(free[0])
            ids.append(free[0])
        out[key] = ids
    return out


class SteeredPolicy:
    """The rule pilots' policy with an optional forced prefix and one forced branch answer.

    The inner policy is asked at every decision, so its own per-seat bookkeeping stays what
    it was in the recorded game; only the answer that goes to the engine is replaced.
    """

    def __init__(
        self,
        inner: Any,
        *,
        forced: Sequence[dict[str, Any]] = (),
        branch_index: int | None = None,
        branch_response: dict[str, Any] | None = None,
        horizon_turn: int | None = None,
        chooser: Any = None,
    ) -> None:
        self.chooser = chooser
        self.checkpoints: dict[int, float] = {}
        self.inner = inner
        self.forced = list(forced)
        self.branch_index = branch_index
        self.branch_response = branch_response
        self.horizon_turn = horizon_turn
        self.index = 0
        self.stopped = False
        self.diverged = False
        self.log: list[
            dict[str, Any]
        ] = []  # recorded decisions (class, seat, turn, options, answer)
        self.last_state: dict[str, Any] | None = None

    def decide(self, decision: dict[str, Any]) -> dict[str, Any]:
        state = decision.get("pilot_state")
        turn = state.get("turn_number") if isinstance(state, dict) else None
        if (
            self.horizon_turn is not None
            and self.index > (self.branch_index or 0)
            and isinstance(turn, int)
            and turn >= self.horizon_turn
        ):
            self.last_state = state
            self.stopped = True
            raise StopRollout
        answer = self.inner.decide(decision)
        if self.index < len(self.forced):
            replayed = concrete(decision, self.forced[self.index])
            if replayed is None and self.index != self.branch_index:
                self.diverged = True
                raise Diverged(f"decision {self.index}: recorded option not offered")
            if replayed is not None:
                answer = replayed
        if self.branch_index is not None and self.index == self.branch_index:
            if self.branch_response is None:
                raise ValueError("branch decision without a branch answer")
            answer = concrete(decision, self.branch_response) or answer
        if self.chooser is not None and self.index >= len(self.forced):
            answer = self.chooser(self, decision, answer)
        if isinstance(turn, int) and isinstance(state, dict):
            for checkpoint in CHECKPOINT_TURNS:
                if turn >= checkpoint and checkpoint not in self.checkpoints:
                    self.checkpoints[checkpoint] = round(board_score(state, 0), 2)
        self.log.append(
            {
                "i": self.index,
                "class": decision.get("decision_class"),
                "seat": decision.get("seat"),
                "turn": turn,
                "phase": state.get("step") if isinstance(state, dict) else None,
                "prints": option_prints(decision),
                "options": [
                    (str(o.get("option_id")), str(o.get("label")), str(o.get("option_type")))
                    for o in decision.get("legal_options") or []
                ],
                "answer": portable(decision, answer),
            }
        )
        self.last_state = state if isinstance(state, dict) else None
        self.index += 1
        return answer  # type: ignore[no-any-return]


class _SteeredRunner(XmageFullGameRunner):
    steered: SteeredPolicy | None = None

    def _validated_policy(self, scenario: Any, decks: Any, pilots: Any) -> Any:  # type: ignore[override]
        inner = super()._validated_policy(scenario, decks, pilots)
        if self.steered is None:
            raise RuntimeError("no steered policy bound")
        self.steered.inner = inner
        return self.steered


def build_setup(deck_paths: list[Path], *, seed: int, game_id: str) -> tuple[Any, Any, Any]:
    """Scenario, decks and rule-pilot bindings exactly as ``studio.play`` builds them."""
    decks = studio_play.load_decks(deck_paths)
    own = decks[0]
    if own.deck_hash is None:
        raise ValueError("the own deck has no deck hash")
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=len(decks),
        seat=1,
        scenario_id=f"studio-game-{game_id}",
        seed=seed,
        xmage_commit=canonical_xmage_engine_pin(),
        bridge_version=studio_play.BRIDGE_VERSION,
        pilot_identity=studio_play.PILOT_IDENTITY,
        pilot_version=studio_play.PILOT_VERSION,
        decision_policy_version=studio_play.POLICY_VERSION,
    )
    pilots = tuple(
        FullGamePilotBinding(
            seat=seat,
            deck_id=deck.deck_id,
            strategy="generic",
            commander_names=deck.commander_names,
            config=PilotConfig(
                pilot_name="auto",
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            pilot_identity=studio_play.PILOT_IDENTITY,
            pilot_version=studio_play.PILOT_VERSION,
            decision_policy_version=studio_play.POLICY_VERSION,
        )
        for seat, deck in enumerate(decks, start=1)
    )
    return scenario, decks, pilots


def play(
    deck_paths: list[Path], seed: int, steered: SteeredPolicy, *, private: bool = False
) -> tuple[dict[str, Any], float]:
    """One game (or rollout) on the engine. Returns (summary, wall seconds).

    ``private`` gives the bridge process its own card database copy, needed when several
    bridge processes run at once.
    """
    scenario, decks, pilots = build_setup(deck_paths, seed=seed, game_id=f"s1-{seed}")
    runner = _SteeredRunner(request_timeout_seconds=120.0, private_card_repository=private)
    runner.steered = steered
    started = time.monotonic()
    summary: dict[str, Any]
    try:
        result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
        summary = {
            "ended": "game_over",
            "winner_seats": [seat - 1 for seat in result.winner_seats],
            "decisions": result.decision_count,
        }
    except Exception as error:
        if steered.stopped:
            summary = {"ended": "horizon", "decisions": steered.index}
        elif steered.diverged:
            summary = {"ended": "diverged", "decisions": steered.index}
        else:
            summary = {"ended": "error", "error": type(error).__name__, "decisions": steered.index}
    return summary, time.monotonic() - started


def board_score(state: dict[str, Any], seat: int) -> float:
    """Own board minus the mean of the others, from the public rows of one frame.

    Counts what a player can see on the table: creature power and toughness, other
    permanents, lands, cards in hand, life. It is a plain proxy, not a rule and not a
    strength claim.
    """
    rows = {p["seat"]: p for p in state.get("players", []) if isinstance(p, dict)}

    def value(row: dict[str, Any]) -> float:
        body = 0.0
        permanents = 0.0
        for card in row.get("battlefield") or []:
            power, toughness = card.get("power") or 0, card.get("toughness") or 0
            if power or toughness:
                body += power + toughness
            else:
                permanents += 1
        life = row.get("life") or 0
        return 0.5 * body + 0.5 * permanents + 0.3 * (row.get("hand_count") or 0) + life / 10.0

    own = rows.get(seat)
    others = [row for s, row in rows.items() if s != seat and not row.get("has_lost")]
    if own is None:
        return 0.0
    if own.get("has_lost"):
        return -100.0
    if not others:
        return 100.0
    return value(own) - statistics.fmean(value(row) for row in others)


def _kind(label: str) -> str:
    if " — Cast " in label:
        return "cast"
    if " — Play " in label:
        return "land"
    return "pass" if label == "Pass priority" else "other"


def make_chooser(
    deck_paths: list[Path],
    seed: int,
    stats: dict[str, Any],
    *,
    max_searches: int,
    margin: float,
    workers: int,
    max_candidates: int = 4,
) -> Any:
    """A policy hook that searches seat 0's main-phase choices by restart look-ahead."""

    def chooser(
        policy: SteeredPolicy, decision: dict[str, Any], answer: dict[str, Any]
    ) -> dict[str, Any]:
        state = decision.get("pilot_state") or {}
        turn = state.get("turn_number") or 0
        if (
            decision.get("seat") != 0
            or decision.get("decision_class") != "priority"
            or not str(state.get("step")).endswith("main")
            or turn < 2
            or stats["searched"] >= max_searches
            or policy.index > MAX_PREFIX
        ):
            return answer
        prints = option_prints(decision)
        labels = {str(o["option_id"]): str(o.get("label")) for o in decision["legal_options"]}
        pilot_ids = list(answer.get("selected_option_ids") or [])
        seen: set[str] = set()
        candidates: list[str] = []  # option ids, one per distinct label
        for oid in pilot_ids + list(labels):
            if labels[oid] in seen or (_kind(labels[oid]) == "other" and oid not in pilot_ids):
                continue
            seen.add(labels[oid])
            candidates.append(oid)
        real = [oid for oid in candidates if _kind(labels[oid]) in {"cast", "land"}]
        if len(real) < 2:
            return answer
        candidates = candidates[:max_candidates]
        prefix = [entry["answer"] for entry in policy.log]
        base = portable(decision, answer)

        def rollout(oid: str) -> tuple[str, float | None, float]:
            response = copy.deepcopy(base)
            response["selected_option_ids"] = [prints[oid]]
            steered = SteeredPolicy(
                None,
                forced=[*prefix, response],
                branch_index=len(prefix),
                branch_response=response,
                horizon_turn=turn + HORIZON_TURNS,
            )
            summary, wall = play(deck_paths, seed, steered, private=True)
            if summary["ended"] == "horizon" and steered.last_state is not None:
                return oid, board_score(steered.last_state, 0), wall
            if summary["ended"] == "game_over":
                return oid, 100.0 if 0 in summary["winner_seats"] else -100.0, wall
            return oid, None, wall

        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(rollout, candidates))
        scores = {oid: score for oid, score, _w in results if score is not None}
        stats["searched"] += 1
        stats["rollouts"] += len(results)
        stats["rollout_wall_s"] += sum(w for _o, _s, w in results)
        stats["search_wall_s"] += time.monotonic() - started
        pilot_id = pilot_ids[0] if pilot_ids else None
        entry = {
            "decision": policy.index,
            "turn": turn,
            "pilot": labels.get(pilot_id or "", "?"),
            "scores": {labels[oid]: round(score, 2) for oid, score in scores.items()},
        }
        chosen = pilot_id
        if scores and pilot_id in scores:
            best = max(scores, key=lambda oid: scores[oid])
            if scores[best] - scores[pilot_id] >= margin:
                chosen = best
        entry["search"] = labels.get(chosen or "", "?")
        entry["overrode_pilot"] = chosen != pilot_id
        stats["points"].append(entry)
        if chosen != pilot_id:
            stats["overrides"] += 1
            changed = copy.deepcopy(answer)
            changed["selected_option_ids"] = [chosen]
            return changed
        return answer

    return chooser


def record_game(deck_paths: list[Path], seed: int) -> tuple[SteeredPolicy, dict[str, Any], float]:
    steered = SteeredPolicy(None)
    summary, wall = play(deck_paths, seed, steered)
    return steered, summary, wall


def cmd_determinism(args: argparse.Namespace) -> None:
    decks = [Path(p) for p in args.deck]
    first, first_summary, first_wall = record_game(decks, args.seed)
    forced = [entry["answer"] for entry in first.log]
    replay = SteeredPolicy(None, forced=forced)
    second_summary, second_wall = play(decks, args.seed, replay)
    same_log = [e["answer"] for e in first.log] == [e["answer"] for e in replay.log]
    report = {
        "seed": args.seed,
        "first": {**first_summary, "wall_s": round(first_wall, 1)},
        "replay": {**second_summary, "wall_s": round(second_wall, 1)},
        "same_answers_asked": same_log,
        "same_winners": first_summary.get("winner_seats") == second_summary.get("winner_seats"),
        "decisions": len(first.log),
    }
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


def candidate_points(log: list[dict[str, Any]], seat: int, count: int) -> list[int]:
    """Decisions of ``seat`` in a main phase with at least three real choices, spread over the game."""
    found = [
        entry["i"]
        for entry in log
        if entry["seat"] == seat
        and entry["class"] == "priority"
        and str(entry["phase"]).endswith("main")
        and len(entry["options"]) >= 4
        and (entry["turn"] or 0) >= 3
    ]
    if len(found) <= count:
        return found
    step = len(found) / count
    return [found[int(step * k)] for k in range(count)]


def cmd_search(args: argparse.Namespace) -> None:
    decks = [Path(p) for p in args.deck]
    base, base_summary, base_wall = record_game(decks, args.seed)
    forced = [entry["answer"] for entry in base.log]
    out: dict[str, Any] = {
        "seed": args.seed,
        "recorded_game": {
            **base_summary,
            "wall_s": round(base_wall, 1),
            "decisions": len(base.log),
        },
        "horizon_turns": HORIZON_TURNS,
        "branch_points": [],
        "note": "rollouts use the real library order; board_score is a plain proxy",
    }
    seat = 0
    for index in candidate_points(base.log, seat, args.samples):
        entry = base.log[index]
        options = entry["options"][: args.max_options]
        recorded = [
            oid
            for oid, fp in entry["prints"].items()
            if fp in (entry["answer"].get("selected_option_ids") or [])
        ]
        point: dict[str, Any] = {
            "decision": index,
            "turn": entry["turn"],
            "phase": entry["phase"],
            "pilot_choice": [label for oid, label, _t in entry["options"] if oid in recorded],
            "candidates": [],
        }
        for option_id, label, _kind in options:
            response = copy.deepcopy(entry["answer"])
            response["selected_option_ids"] = [entry["prints"][option_id]]
            steered = SteeredPolicy(
                None,
                forced=forced[: index + 1],
                branch_index=index,
                branch_response=response,
                horizon_turn=(entry["turn"] or 0) + HORIZON_TURNS,
            )
            summary, wall = play(decks, args.seed, steered)
            score = None
            if summary["ended"] == "horizon" and steered.last_state is not None:
                score = round(board_score(steered.last_state, seat), 2)
            elif summary["ended"] == "game_over":
                score = 100.0 if seat in summary.get("winner_seats", []) else -100.0
            point["candidates"].append(
                {
                    "label": label,
                    "chosen_by_pilot": option_id in recorded,
                    "ended": summary["ended"],
                    "score": score,
                    "wall_s": round(wall, 1),
                }
            )
            print(
                point["decision"], label[:60], summary["ended"], score, round(wall, 1), flush=True
            )
        scored = [c for c in point["candidates"] if c["score"] is not None]
        if scored:
            best = max(scored, key=lambda c: c["score"])
            point["search_choice"] = best["label"]
            point["search_differs"] = not best["chosen_by_pilot"]
        out["branch_points"].append(point)
        Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    walls = [c["wall_s"] for p in out["branch_points"] for c in p["candidates"]]
    out["rollouts"] = len(walls)
    out["rollout_wall_s_median"] = round(statistics.median(walls), 1) if walls else None
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


def _seeds(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        low, _, high = part.partition("-")
        out += list(range(int(low), int(high or low) + 1))
    return out


def cmd_game(args: argparse.Namespace) -> None:
    """Per seed: the rule pilots' game, then the same game with a searching seat 0."""
    decks = [Path(p) for p in args.deck]
    results: list[dict[str, Any]] = []
    for seed in _seeds(args.seeds):
        base, base_summary, base_wall = record_game(decks, seed)
        stats: dict[str, Any] = {
            "searched": 0,
            "rollouts": 0,
            "rollout_wall_s": 0.0,
            "search_wall_s": 0.0,
            "overrides": 0,
            "points": [],
        }
        searching = SteeredPolicy(
            None,
            chooser=make_chooser(
                decks,
                seed,
                stats,
                max_searches=args.max_searches,
                margin=args.margin,
                workers=args.workers,
            ),
        )
        summary, wall = play(decks, seed, searching)
        row = {
            "seed": seed,
            "rule": {
                **base_summary,
                "wall_s": round(base_wall, 1),
                "checkpoints": base.checkpoints,
            },
            "search": {**summary, "wall_s": round(wall, 1), "checkpoints": searching.checkpoints},
            "stats": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in stats.items()},
        }
        results.append(row)
        print(
            seed,
            "rule", base_summary.get("winner_seats"), "search", summary.get("ended"),
            summary.get("winner_seats"), "searched", stats["searched"], "overrides",
            stats["overrides"], "wall", round(wall), flush=True,
        )  # fmt: skip
        Path(args.out).write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("determinism", "search", "game"))
    parser.add_argument("--seeds", default="7")
    parser.add_argument("--max-searches", type=int, default=12)
    parser.add_argument("--margin", type=float, default=0.5)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--deck", action="append", default=None)
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--max-options", type=int, default=5)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    args.deck = args.deck or [
        "data/decks/deckbau/chulane_current.json",
        "data/decks/precons/2013_mind_seize.json",
        "data/decks/precons/2013_power_hungry.json",
        "data/decks/precons/2011_heavenly_inferno.json",
    ]
    {"determinism": cmd_determinism, "search": cmd_search, "game": cmd_game}[args.command](args)


if __name__ == "__main__":
    main()
