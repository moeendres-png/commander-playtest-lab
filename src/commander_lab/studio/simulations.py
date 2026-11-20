"""Batch simulation runner and analysis for Commander Studio (Meilenstein 5).

Runs series of games in isolated processes with deterministic seeds,
aggregates win rates with explicit denominators and Wilson confidence intervals,
records card telemetry, and persists results into StudioStore (simulation_run and simulation_card).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from commander_lab.bridge_qualification import (
    BRIDGE_AHEAD,
    BRIDGE_ALIGNED,
    BRIDGE_UNKNOWN,
    bridge_qualification,
)
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin

from . import cache
from .decks import lab_snapshot
from .games import games_folder, read_game
from .launch import (
    ENGINE_COMMAND_ENV,
    POD_PRESETS,
    SeriesEngine,
    checked_series_settings,
    command_text,
    engine_state,
    resolve_opponent_paths,
    series_engine,
)
from .launch import (
    bridge_jar_sha256 as command_bridge_jar_sha256,
)
from .store import DataClass, StudioStore, now_utc

# What ``save_batch_to_store`` writes (``cache.write``): the series tables, its source row and
# the commander binding of that source.
_SERIES_WRITES = frozenset({cache.Group.SIMULATION, cache.Group.IMPORT})

PILOT_POLICY = "GenericCommanderPilot 1.0.0"


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, (float, str)):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def wilson_score_interval(wins: float, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion.

    Guarantees no false certainty or fabricated claims: for 0 or small denominators,
    the interval explicitly reflects the large uncertainty.
    """
    if total <= 0:
        return (0.0, 0.0)
    p = max(0.0, min(1.0, wins / total))
    z = 2.576 if confidence >= 0.99 else 1.95996
    denom = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denom
    variance_term = (p * (1.0 - p)) / total + (z * z) / (4.0 * total * total)
    spread = (z * math.sqrt(max(0.0, variance_term))) / denom
    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    return (round(lower, 4), round(upper, 4))


def _norm_card_name(name: str) -> str:
    return name.split(" // ", 1)[0].split(" (", 1)[0].strip().casefold()


def _resolve_seat_plan(
    header: Mapping[str, object],
    candidate_seat: int,
    override: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    if isinstance(override, Mapping):
        return override
    raw_seats = header.get("seats")
    if not isinstance(raw_seats, list):
        return None
    for entry in raw_seats:
        if isinstance(entry, Mapping) and entry.get("seat") == candidate_seat:
            plan = entry.get("deck_plan")
            return plan if isinstance(plan, Mapping) else None
    if 0 <= candidate_seat < len(raw_seats):
        entry = raw_seats[candidate_seat]
        if isinstance(entry, Mapping):
            plan = entry.get("deck_plan")
            return plan if isinstance(plan, Mapping) else None
    return None


def _plan_name_bucket(plan: Mapping[str, object], key: str) -> set[str]:
    raw = plan.get(key)
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return set()
    return {_norm_card_name(item) for item in raw if isinstance(item, str) and item.strip()}


def _player_for_seat(players: object, candidate_seat: int) -> Mapping[str, object] | None:
    if not isinstance(players, list) or candidate_seat < 0:
        return None
    for entry in players:
        if isinstance(entry, Mapping) and entry.get("seat") == candidate_seat:
            return entry
    if candidate_seat < len(players):
        entry = players[candidate_seat]
        if isinstance(entry, Mapping):
            return entry
    return None


def _compute_plan_telemetry(
    plan: Mapping[str, object],
    frames: Sequence[Mapping[str, object]],
    candidate_seat: int,
    offered_cards: set[str],
    cast_cards: Mapping[str, int],
) -> dict[str, object]:
    combos_raw = plan.get("combos")
    combos_parsed: list[tuple[str, frozenset[str]]] = []
    combo_cards_from_lines: set[str] = set()
    if isinstance(combos_raw, (list, tuple)):
        for idx, item in enumerate(combos_raw):
            if not isinstance(item, Mapping):
                continue
            raw_cards = item.get("cards")
            if not isinstance(raw_cards, (list, tuple)):
                continue
            folded = frozenset(
                _norm_card_name(c) for c in raw_cards if isinstance(c, str) and c.strip()
            )
            if len(folded) < 2:
                continue
            cid = str(item.get("combo_id") or f"combo-{idx}")
            combos_parsed.append((cid, folded))
            combo_cards_from_lines.update(folded)

    role_sets: dict[str, set[str]] = {
        "combo_card": _plan_name_bucket(plan, "combo_cards") | combo_cards_from_lines,
        "key_card": _plan_name_bucket(plan, "key_cards"),
        "engine": _plan_name_bucket(plan, "engines"),
        "answer": _plan_name_bucket(plan, "answers"),
    }
    if not combos_parsed and not any(role_sets.values()):
        return {}

    combos_assembled: set[str] = set()
    combos_deployed: set[str] = set()
    min_assembled_round: int | None = None
    min_deployed_round: int | None = None
    command_seen: set[str] = set()

    for frame in frames:
        c_player = _player_for_seat(frame.get("players"), candidate_seat)
        if c_player is None:
            continue
        turn = frame.get("turn")
        turn_int = turn if isinstance(turn, int) else None
        command_zone: set[str] = set()
        cmd = c_player.get("command")
        if isinstance(cmd, list):
            for cname in cmd:
                if isinstance(cname, str) and cname and cname != "(verdeckt)":
                    norm_cmd = _norm_card_name(cname)
                    command_zone.add(norm_cmd)
                    command_seen.add(norm_cmd)
        if not combos_parsed:
            continue
        deployed_zone: set[str] = set()
        bf = c_player.get("battlefield")
        if isinstance(bf, list):
            for perm in bf:
                if isinstance(perm, Mapping):
                    pname = perm.get("name")
                    if isinstance(pname, str) and pname and pname != "(verdeckt)":
                        deployed_zone.add(_norm_card_name(pname))
        hand_zone: set[str] = set()
        hand = c_player.get("hand")
        if isinstance(hand, list):
            for hname in hand:
                if isinstance(hname, str) and hname and hname != "(verdeckt)":
                    hand_zone.add(_norm_card_name(hname))
        assembled_zone = deployed_zone | hand_zone | command_zone
        for cid, cset in combos_parsed:
            if cset <= assembled_zone:
                combos_assembled.add(cid)
                if turn_int is not None and (
                    min_assembled_round is None or turn_int < min_assembled_round
                ):
                    min_assembled_round = turn_int
            if cset <= deployed_zone:
                combos_deployed.add(cid)
                if turn_int is not None and (
                    min_deployed_round is None or turn_int < min_deployed_round
                ):
                    min_deployed_round = turn_int

    offered_norm = {_norm_card_name(c) for c in offered_cards} | command_seen
    cast_norm = {_norm_card_name(c) for c in cast_cards}
    roles_stats: dict[str, dict[str, int]] = {}
    for role_key, card_set in role_sets.items():
        cast_hits = card_set & cast_norm
        offered_hits = card_set & (offered_norm | cast_hits)
        roles_stats[role_key] = {
            "in_plan": len(card_set),
            "offered": len(offered_hits),
            "cast": len(cast_hits),
        }

    return {
        "has_plan": True,
        "provenance": str(plan.get("provenance") or "abgeleitet, nicht gemessen"),
        "combo_lines_in_plan": len(combos_parsed),
        "combos_assembled": sorted(combos_assembled),
        "combos_deployed": sorted(combos_deployed),
        "combo_assembled": bool(combos_assembled),
        "combo_deployed": bool(combos_deployed),
        "first_combo_assembled_round": min_assembled_round,
        "first_combo_deployed_round": min_deployed_round,
        "roles": roles_stats,
    }


@dataclass
class GameSummary:
    game_id: str
    seed: int
    status: str  # "finished" | "failed"
    winner_seats: list[int] = field(default_factory=list)
    decision_count: int = 0
    rounds: int = 0
    candidate_won: bool = False
    failure_class: str | None = None
    failure_message: str | None = None
    log_path: str | None = None
    bridge_jar_sha256: str | None = None
    bridge_qualification_state: str | None = None
    covered_by_sealed_epoch: bool = False
    observed_cards: dict[str, dict[str, object]] = field(default_factory=dict)
    plan_telemetry: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "game_id": self.game_id,
            "seed": self.seed,
            "status": self.status,
            "winner_seats": self.winner_seats,
            "decision_count": self.decision_count,
            "rounds": self.rounds,
            "candidate_won": self.candidate_won,
            "failure_class": self.failure_class,
            "failure_message": self.failure_message,
            "log_path": self.log_path,
            "bridge_jar_sha256": self.bridge_jar_sha256,
            "bridge_qualification_state": self.bridge_qualification_state,
            "covered_by_sealed_epoch": self.covered_by_sealed_epoch,
        }
        if self.plan_telemetry:
            payload["plan_telemetry"] = self.plan_telemetry
        return payload


def extract_game_log_telemetry(
    data_folder: str | Path,
    game_id: str,
    candidate_seat: int = 0,
    *,
    deck_plan: Mapping[str, object] | None = None,
) -> GameSummary:
    """Read a recorded game log and extract candidate-seat telemetry and outcome."""
    try:
        data = read_game(data_folder, game_id, start=0, count=1000)
    except (KeyError, ValueError, OSError) as exc:
        return GameSummary(
            game_id=game_id,
            seed=0,
            status="failed",
            failure_class="ReadGameError",
            failure_message=str(exc),
        )

    hdr_raw = data.get("header")
    hdr = hdr_raw if isinstance(hdr_raw, dict) else {}
    seed = _as_int(hdr.get("seed"), 0)
    result_raw = data.get("result")
    result = result_raw if isinstance(result_raw, dict) else {}
    status = str(result.get("status") or ("running" if data.get("running") else "failed"))
    raw_sha = hdr.get("bridge_jar_sha256") or result.get("bridge_jar_sha256")
    bridge_jar_sha256 = str(raw_sha) if isinstance(raw_sha, str) and raw_sha else None
    raw_qual = hdr.get("bridge_qualification_state") or result.get("bridge_qualification_state")
    bridge_qualification_state = str(raw_qual) if isinstance(raw_qual, str) and raw_qual else None
    covered_by_sealed_epoch = (
        bool(hdr.get("covered_by_sealed_epoch"))
        and bridge_qualification_state == BRIDGE_ALIGNED
        and bridge_jar_sha256 is not None
    )
    raw_winners = result.get("winner_seats")
    winner_seats: list[int] = (
        [_as_int(s) for s in raw_winners if isinstance(s, (int, float, str))]
        if isinstance(raw_winners, list)
        else []
    )
    candidate_won = candidate_seat in winner_seats
    decision_count = _as_int(result.get("decision_count") or data.get("total"), 0)

    # Collect all frames (paginating if the log exceeds 1000 frames)
    raw_frames = data.get("frames")
    frames: list[dict[str, object]] = (
        [f for f in raw_frames if isinstance(f, dict)] if isinstance(raw_frames, list) else []
    )
    total_frames = _as_int(data.get("total"), len(frames))
    offset = len(frames)
    while offset < total_frames:
        try:
            more = read_game(data_folder, game_id, start=offset, count=1000)
        except (KeyError, ValueError, OSError):
            break
        more_frames = more.get("frames")
        if not isinstance(more_frames, list) or not more_frames:
            break
        batch_frames = [f for f in more_frames if isinstance(f, dict)]
        if not batch_frames:
            break
        frames.extend(batch_frames)
        offset += len(more_frames)

    # Scan frames for turn count and candidate cards in hand / cast
    max_turn = 0
    offered_cards: set[str] = set()
    cast_cards: dict[str, int] = {}
    first_cast_round: dict[str, int] = {}

    for frame in frames:
        turn = frame.get("turn")
        if isinstance(turn, int) and turn > max_turn:
            max_turn = turn

        # If actor is candidate seat, extract hand cards
        seat = frame.get("seat")
        c_player = _player_for_seat(frame.get("players"), candidate_seat)
        if c_player is not None:
            hand = c_player.get("hand")
            if isinstance(hand, list):
                for c in hand:
                    if isinstance(c, str) and c and c != "(verdeckt)":
                        offered_cards.add(c)

        # Check if candidate seat made a cast decision
        if seat == candidate_seat:
            dc = frame.get("decision_class")
            chosen = frame.get("chosen")
            source = frame.get("source")
            if dc in {"play_land", "cast_spell"} and isinstance(chosen, list):
                for item in chosen:
                    if isinstance(item, str) and item:
                        card_name = item.split(" (")[0].strip()
                        cast_cards[card_name] = cast_cards.get(card_name, 0) + 1
                        if card_name not in first_cast_round and isinstance(turn, int):
                            first_cast_round[card_name] = turn
            elif isinstance(source, str) and source and dc in {"cast_spell", "play_land"}:
                cast_cards[source] = cast_cards.get(source, 0) + 1
                if source not in first_cast_round and isinstance(turn, int):
                    first_cast_round[source] = turn

    card_telemetry: dict[str, dict[str, object]] = {}
    for card in offered_cards | set(cast_cards.keys()):
        was_cast = card in cast_cards
        card_telemetry[card] = {
            "offered": card in offered_cards,
            "cast": was_cast,
            "cast_count": cast_cards.get(card, 0),
            "first_cast_round": first_cast_round.get(card),
        }

    resolved_plan = _resolve_seat_plan(hdr, candidate_seat, deck_plan)
    plan_telemetry = (
        _compute_plan_telemetry(resolved_plan, frames, candidate_seat, offered_cards, cast_cards)
        if resolved_plan is not None
        else {}
    )

    return GameSummary(
        game_id=game_id,
        seed=seed,
        status=status,
        winner_seats=winner_seats,
        decision_count=decision_count,
        rounds=max_turn,
        candidate_won=candidate_won,
        failure_class=str(result["failure_class"]) if "failure_class" in result else None,
        failure_message=str(result["failure_message"]) if "failure_message" in result else None,
        log_path=str(games_folder(data_folder) / f"{game_id}.jsonl.gz"),
        bridge_jar_sha256=bridge_jar_sha256,
        bridge_qualification_state=bridge_qualification_state,
        covered_by_sealed_epoch=covered_by_sealed_epoch,
        observed_cards=card_telemetry,
        plan_telemetry=plan_telemetry,
    )


def _aggregate_plan_summary(
    successful: Sequence[GameSummary],
) -> dict[str, object] | None:
    planned = [g for g in successful if g.plan_telemetry.get("has_plan")]
    if not planned:
        return None
    planned_n = len(planned)
    assembled_n = sum(1 for g in planned if g.plan_telemetry.get("combo_assembled"))
    deployed_n = sum(1 for g in planned if g.plan_telemetry.get("combo_deployed"))
    role_summary: dict[str, dict[str, object]] = {}
    for role in ("combo_card", "key_card", "engine", "answer"):
        offered_sum = 0
        cast_sum = 0
        for g in planned:
            roles_map = g.plan_telemetry.get("roles")
            if isinstance(roles_map, Mapping):
                entry = roles_map.get(role)
                if isinstance(entry, Mapping):
                    offered_sum += _as_int(entry.get("offered"), 0)
                    cast_sum += _as_int(entry.get("cast"), 0)
        role_summary[role] = {
            "offered_total": offered_sum,
            "cast_total": cast_sum,
            "cast_after_offer_rate": round(cast_sum / offered_sum, 4) if offered_sum > 0 else None,
        }
    return {
        "data_class": DataClass.SIMULATED_RESULT.value,
        "games_with_plan": planned_n,
        "games_completed": len(successful),
        "combo_assembled_games": assembled_n,
        "combo_deployed_games": deployed_n,
        "combo_assembly_rate": round(assembled_n / planned_n, 4),
        "combo_deployment_rate": round(deployed_n / planned_n, 4),
        "roles": role_summary,
    }


def censored_round_quartiles(reached_rounds: Sequence[int], games: int) -> dict[str, int | None]:
    """Quartiles of a first-event round over all ``games``; ``None`` where it was not reached.

    A game in which the event never happened stays in the denominator as "later than the
    game lasted": the nearest-rank quantile ``ceil(q * games)`` over the reached rounds in
    order is ``None`` once that rank lies among the games that never reached it. So the
    median is ``None`` when fewer than half of the games reached the event, instead of a
    mean over only the games that did (which reads early whatever the card does).
    """
    ordered = sorted(reached_rounds)
    quartiles: dict[str, int | None] = {}
    for label, share in (("q1", 0.25), ("median", 0.5), ("q3", 0.75)):
        rank = math.ceil(share * games)
        quartiles[label] = ordered[rank - 1] if games > 0 and 1 <= rank <= len(ordered) else None
    return quartiles


def aggregate_batch_results(
    games: Sequence[GameSummary],
    deck_card_names: Sequence[str] | None = None,
) -> dict[str, object]:
    """Aggregate multiple game outcomes into an objective simulation summary."""
    successful = [g for g in games if g.status == "finished"]
    failed = [g for g in games if g.status != "finished"]

    wins = sum(
        (1.0 / len(g.winner_seats)) if g.winner_seats and 0 in g.winner_seats else 0.0
        for g in successful
    )
    completed_count = len(successful)
    win_rate = round(wins / completed_count, 4) if completed_count > 0 else None
    ci_lower, ci_upper = (
        wilson_score_interval(wins, completed_count) if completed_count > 0 else (0.0, 0.0)
    )

    mean_rounds = (
        round(sum(g.rounds for g in successful) / completed_count, 2)
        if completed_count > 0
        else None
    )

    bridge_shas = sorted({g.bridge_jar_sha256 for g in successful if g.bridge_jar_sha256})
    qual_states = sorted(
        {g.bridge_qualification_state for g in successful if g.bridge_qualification_state}
    )
    covered_by_sealed_epoch = bool(successful) and all(
        g.covered_by_sealed_epoch
        and g.bridge_qualification_state == BRIDGE_ALIGNED
        and g.bridge_jar_sha256 is not None
        for g in successful
    )

    # Per-card aggregation
    card_names = set(deck_card_names or ())
    for g in successful:
        card_names.update(g.observed_cards.keys())

    cards_summary: list[dict[str, object]] = []
    for c_name in sorted(card_names):
        offered_games = sum(
            1 for g in successful if g.observed_cards.get(c_name, {}).get("offered")
        )
        cast_games = sum(1 for g in successful if g.observed_cards.get(c_name, {}).get("cast"))
        total_casts = sum(
            _as_int(g.observed_cards.get(c_name, {}).get("cast_count"), 0) for g in successful
        )
        first_rounds = [
            _as_int(r)
            for g in successful
            if (r := g.observed_cards.get(c_name, {}).get("first_cast_round")) is not None
        ]
        mean_first_round = round(sum(first_rounds) / len(first_rounds), 2) if first_rounds else None
        rotted_games = max(0, offered_games - cast_games)
        reached_games = len(first_rounds)

        cards_summary.append(
            {
                "card_name": c_name,
                "games_completed": completed_count,
                "games_offered": offered_games,
                "games_cast_after_offer": cast_games,
                "games_rotted": rotted_games,
                "offered_castable": offered_games,
                "cast_count": total_casts,
                # mean over the games in which the card was cast only (n below)
                "mean_first_cast_round": mean_first_round,
                "first_cast_round_basis": (
                    "mean over games_reached of games_completed only; quartiles nearest-rank "
                    "over all games_completed, a game that never cast it ranks as later than "
                    "the game lasted (None = not reached)"
                ),
                "first_cast_round_games_reached": reached_games,
                "first_cast_round_games_not_reached": completed_count - reached_games,
                "first_cast_round_quartiles": censored_round_quartiles(
                    first_rounds, completed_count
                ),
            }
        )

    result_payload: dict[str, object] = {
        "games_planned": len(games),
        "games_completed": completed_count,
        "games_failed": len(failed),
        "wins_fractional": round(wins, 2),
        "win_rate": win_rate,
        "win_rate_percent": round(win_rate * 100.0, 1) if win_rate is not None else None,
        "confidence_interval_95": {
            "lower": ci_lower,
            "upper": ci_upper,
            "lower_percent": round(ci_lower * 100.0, 1),
            "upper_percent": round(ci_upper * 100.0, 1),
        },
        "mean_rounds": mean_rounds,
        "bridge_jar_sha256": bridge_shas[0] if len(bridge_shas) == 1 else None,
        "bridge_jar_sha256s": bridge_shas,
        "bridge_qualification_states": qual_states,
        "covered_by_sealed_epoch": covered_by_sealed_epoch,
        "cards": cards_summary,
    }
    plan_summary = _aggregate_plan_summary(successful)
    if plan_summary is not None:
        result_payload["plan_summary"] = plan_summary
    return result_payload


def save_batch_to_store(
    store: StudioStore,
    batch: BatchSimulation,
    summary: dict[str, object],
) -> str:
    """Save an aggregated batch simulation into simulation_run and simulation_card."""
    run_id = f"batch-{batch.batch_id}"
    engine_pin = canonical_xmage_engine_pin()

    shas_raw = summary.get("bridge_jar_sha256s")
    summary_shas = (
        [str(s) for s in shas_raw if isinstance(s, str) and s] if isinstance(shas_raw, list) else []
    )
    if len(summary_shas) > 1:
        bridge_jar_sha256: str | None = None
    elif len(summary_shas) == 1:
        bridge_jar_sha256 = summary_shas[0]
    else:
        raw_sha = summary.get("bridge_jar_sha256")
        bridge_jar_sha256 = (
            str(raw_sha)
            if isinstance(raw_sha, str) and raw_sha
            else getattr(batch, "bridge_jar_sha256", None)
        )

    states_raw = summary.get("bridge_qualification_states")
    summary_states = (
        {str(s) for s in states_raw if isinstance(s, str) and s}
        if isinstance(states_raw, list)
        else set()
    )
    batch_qual = getattr(batch, "bridge_qualification", {})
    batch_qual_status = (
        str(batch_qual.get("status"))
        if isinstance(batch_qual, Mapping) and batch_qual.get("status")
        else None
    )
    covered = bool(summary.get("covered_by_sealed_epoch")) and bool(bridge_jar_sha256)
    if covered and (not summary_states or summary_states == {BRIDGE_ALIGNED}):
        qual_state = BRIDGE_ALIGNED
    elif BRIDGE_AHEAD in summary_states or batch_qual_status == BRIDGE_AHEAD:
        qual_state = BRIDGE_AHEAD
    else:
        qual_state = BRIDGE_UNKNOWN

    # Create a reproducible content hash for source registration
    source_payload = json.dumps(
        {
            "run_id": run_id,
            "deck_id": batch.deck_id,
            "pod": batch.pod_name,
            "seeds": batch.seeds,
            "completed": summary.get("games_completed"),
            "execution": batch.execution(),
            "bridge_jar_sha256": bridge_jar_sha256,
            "bridge_qualification_state": qual_state,
        },
        sort_keys=True,
    )
    source_sha = hashlib.sha256(source_payload.encode("utf-8")).hexdigest()

    engine_flags = batch.engine.jvm_flags if batch.engine is not None else ()
    source_id = store.register_source(
        data_class=DataClass.SIMULATED_RESULT,
        title=(
            f"Studio Batch Simulation {batch.batch_id} ({batch.pod_name}); "
            f"workers={batch.workers} games_per_jvm={batch.games_per_jvm} "
            f"jvm_flags={' '.join(engine_flags)}"
        ),
        sha256=source_sha,
    )

    card_rows: list[tuple[object, ...]] = []
    cards_list = summary.get("cards")
    if isinstance(cards_list, list):
        for c in cards_list:
            if not isinstance(c, dict):
                continue
            card_name = str(c.get("card_name") or "")
            if not card_name:
                continue
            # Look up card_id in store if available
            row = store.connection.execute(
                "SELECT card_id FROM card WHERE oracle_name = ? LIMIT 1",
                (card_name,),
            ).fetchone()
            card_id = row[0] if row else None
            card_rows.append(
                (
                    run_id,
                    card_id,
                    card_name,
                    int(c.get("games_completed") or 0),
                    int(c.get("games_offered") or 0),
                    int(c.get("games_cast_after_offer") or 0),
                    int(c.get("games_rotted") or 0),
                    int(c.get("offered_castable") or 0),
                    int(c.get("cast_count") or 0),
                    c.get("mean_first_cast_round"),
                )
            )

    with store.connection as db:
        db.execute("DELETE FROM simulation_card WHERE run_id = ?", (run_id,))
        db.execute(
            "INSERT OR REPLACE INTO simulation_run(run_id, deck_id, revision_id, deck_hash, "
            "pod, engine_pin, bridge_jar_sha256, bridge_qualification_state, "
            "pilot_policy, seeds, games_planned, games_completed, games_failed, "
            "wins_fractional, win_rate, mean_rounds, hand_dwell_status, source_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                batch.deck_id,
                batch.revision_id or None,
                getattr(batch, "deck_hash", None),
                batch.pod_name,
                engine_pin,
                bridge_jar_sha256,
                qual_state,
                PILOT_POLICY,
                json.dumps(batch.seeds),
                _as_int(summary.get("games_planned"), len(batch.seeds)),
                _as_int(summary.get("games_completed"), 0),
                _as_int(summary.get("games_failed"), 0),
                _as_float(summary.get("wins_fractional"), 0.0),
                summary.get("win_rate"),
                summary.get("mean_rounds"),
                "NOT_MEASURED",
                source_id,
            ),
        )
        db.executemany(
            "INSERT INTO simulation_card(run_id, card_id, card_name, games_completed, "
            "games_offered, games_cast_after_offer, games_rotted, offered_castable, "
            "cast_count, mean_first_cast_round) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            card_rows,
        )
        # A series belongs to the commander of the deck revision it played; it is shown
        # only under that commander and never added to another commander's figures.
        db.execute(
            "DELETE FROM commander_binding WHERE kind = 'simulation_run' AND key = ?", (run_id,)
        )
        db.execute(
            "INSERT OR IGNORE INTO commander_binding(kind, key, commander_name, basis) "
            "SELECT 'simulation_run', ?, f.oracle_name, 'DECK_REVISION_COMMANDER' "
            "FROM deck_revision_card rc JOIN card_fact f ON f.card_id = rc.card_id "
            "WHERE rc.revision_id = ? AND rc.zone = 'commander'",
            (run_id, batch.revision_id),
        )

    return run_id


#: How a chunk of games is played: the seeds in, one summary per game out as each finishes.
ChunkRunner = Callable[[Sequence[int]], Iterator[GameSummary]]

CHUNK_SECONDS_PER_GAME = 300.0


def plan_chunks(seeds: Sequence[int], workers: int, games_per_jvm: int) -> list[list[int]]:
    """Split ``seeds`` into chunks, one engine process each, in seed order.

    No chunk is larger than ``games_per_jvm``. There are at least ``workers`` chunks (as far as
    there are games), so that every worker has work; the sizes differ by at most one.
    """
    total = len(seeds)
    if total == 0:
        return []
    count = max(-(-total // games_per_jvm), min(workers, total))
    base, extra = divmod(total, count)
    chunks: list[list[int]] = []
    start = 0
    for index in range(count):
        size = base + (1 if index < extra else 0)
        chunks.append(list(seeds[start : start + size]))
        start += size
    return chunks


class BatchSimulation:
    """Manages execution and status of a multi-game simulation series.

    The games of a series are split into chunks (``plan_chunks``). A chunk is played by one
    ``play-batch`` process, whose bridge JVM plays the chunk's games one after the other
    (``games_per_jvm``); ``workers`` chunks run at once. Every game has its own log, its own
    seed, its own row and its own status. Evidence and qualification lanes do not use this path.
    """

    def __init__(
        self,
        batch_id: str,
        data_folder: str | Path,
        deck_id: str,
        revision_id: str,
        pod_name: str,
        opponent_paths: list[Path],
        seeds: list[int],
        *,
        style: float | None = None,
        game_executor: Callable[..., dict[str, object]] | None = None,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        engine: SeriesEngine | None = None,
        chunk_runner: ChunkRunner | None = None,
        initial_games: Sequence[GameSummary] | None = None,
        bridge_jar_sha256: str | None = None,
        qualification: Mapping[str, object] | None = None,
        opponent_ids: Sequence[str] | None = None,
    ) -> None:
        self.batch_id = batch_id
        #: The opponents as asked for (None: the pod preset), so a resume plays the same table
        self.opponent_ids = list(opponent_ids) if opponent_ids is not None else None
        self.data_folder = Path(data_folder)
        self.deck_id = deck_id
        self.revision_id = revision_id
        self.pod_name = pod_name
        self.opponent_paths = opponent_paths
        self.seeds = list(seeds)
        self.style = style
        self.game_executor = game_executor
        self.chunk_runner = chunk_runner
        self.engine = engine
        self.workers, requested = checked_series_settings(workers, games_per_jvm)
        # a launcher that cannot play several games per process (not java) says so here
        self.games_per_jvm = engine.games_per_jvm if engine is not None else requested
        self.bridge_jar_sha256: str | None = (
            bridge_jar_sha256
            if bridge_jar_sha256 is not None
            else (
                command_bridge_jar_sha256(self.data_folder, engine.command)
                if engine is not None
                else None
            )
        )
        self.bridge_qualification: dict[str, object] = (
            dict(qualification) if qualification is not None else bridge_qualification()
        )
        # The deck state the series plays (#1657): the seat's ``deck_hash`` of the game log
        # header, set from the own deck snapshot in ``run_worker``; None reads "Stand unbekannt".
        self.deck_hash: str | None = None

        # Track completed vs remaining seeds for resumable execution
        self._games: list[GameSummary] = list(initial_games or [])
        completed_seeds = {g.seed for g in self._games if g.status == "finished"}
        remaining_seeds = [s for s in self.seeds if s not in completed_seeds]
        self.chunks = plan_chunks(remaining_seeds, self.workers, self.games_per_jvm)

        self.status = "pending" if remaining_seeds else "completed"
        self.current_index = len(self._games)
        self.current_game_id: str | None = None
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.error: str | None = None
        self.run_id: str | None = None

        self._cancel_requested = False
        #: Log ids of games the engine has played to their end (a progress signal that comes
        #: before the result: the log is closed after the engine process ends).
        self._played: set[str] = set()
        self._processes: set[subprocess.Popen[str]] = set()
        self._summary: dict[str, object] | None = (
            aggregate_batch_results(self._games) if not remaining_seeds else None
        )
        self._lock = threading.Lock()

    def game_id_of(self, seed: int) -> str:
        return f"batch-{self.batch_id}-s{seed}"

    def execution(self) -> dict[str, object]:
        """The execution identity of the series: how its games were run, not what they were."""
        engine = self.engine
        return {
            "workers": self.workers,
            "games_per_jvm": self.games_per_jvm,
            "chunks": [list(chunk) for chunk in self.chunks],
            "jvm_flags": list(engine.jvm_flags) if engine is not None else [],
            "serial_gc": engine.serial_gc if engine is not None else False,
            "appcds": engine.appcds if engine is not None else False,
            "engine_command": list(engine.command) if engine is not None else [],
            "bridge_jar_sha256": self.bridge_jar_sha256,
            "bridge_qualification_state": self.bridge_qualification.get("status"),
        }

    def cancel(self) -> None:
        """Gracefully request cancellation and terminate the active engine processes."""
        with self._lock:
            self._cancel_requested = True
            for process in self._processes:
                with contextlib.suppress(OSError):
                    process.terminate()

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def mark_played(self, game_id: str) -> None:
        """Count a game of this series as played by the engine; any other id is ignored."""
        if game_id not in {self.game_id_of(seed) for seed in self.seeds}:
            return
        with self._lock:
            self._played.add(game_id)

    def _games_played(self) -> int:
        """Games the engine played and that did not end as a failed row; caller holds the lock.

        A game announced as played can still end as a failed row (cancelled while its log was
        open, a failure after the drive): it is not counted as played, so played plus failed
        counts every game once.
        """
        finished = {g.game_id for g in self._games if g.status == "finished"}
        failed_only = {g.game_id for g in self._games if g.status != "finished"} - finished
        return len((self._played | finished) - failed_only)

    def _games_in_seed_order(self) -> list[GameSummary]:
        order = {self.game_id_of(seed): index for index, seed in enumerate(self.seeds)}
        return sorted(self._games, key=lambda game: order.get(game.game_id, len(order)))

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            games = self._games_in_seed_order()
            if isinstance(self._summary, dict) and "covered_by_sealed_epoch" in self._summary:
                covered = bool(self._summary["covered_by_sealed_epoch"])
            else:
                covered = (
                    bool(self.bridge_qualification.get("covered_by_sealed_epoch", False))
                    and self.bridge_qualification.get("status") == BRIDGE_ALIGNED
                    and bool(self.bridge_jar_sha256)
                )
            return {
                "batch_id": self.batch_id,
                "seeds": list(self.seeds),
                "deck_id": self.deck_id,
                "revision_id": self.revision_id,
                "pod": self.pod_name,
                "opponent_ids": self.opponent_ids,
                "status": self.status,
                "games_planned": len(self.seeds),
                "games_completed": sum(1 for g in games if g.status == "finished"),
                "games_failed": sum(1 for g in games if g.status != "finished"),
                "games_played": self._games_played(),
                "current_index": self.current_index,
                "current_game_id": self.current_game_id,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "error": self.error,
                "run_id": self.run_id,
                "bridge_jar_sha256": self.bridge_jar_sha256,
                "bridge_qualification": dict(self.bridge_qualification),
                "covered_by_sealed_epoch": covered,
                "execution": self.execution(),
                "summary": self._summary,
                "games": [g.to_dict() for g in games],
            }

    @classmethod
    def from_saved_series(
        cls,
        data_folder: str | Path,
        batch_id: str,
        *,
        opponent_paths: list[Path] | None = None,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        engine: SeriesEngine | None = None,
        chunk_runner: ChunkRunner | None = None,
        game_executor: Callable[..., dict[str, object]] | None = None,
        bridge_jar_sha256: str | None = None,
        qualification: Mapping[str, object] | None = None,
    ) -> BatchSimulation:
        """Construct a BatchSimulation from a saved series record for resumption.

        Raises KeyError when no record exists for ``batch_id`` and ValueError
        when the stored record is not valid JSON. Without explicit ``opponent_paths`` the
        opponents are the ``opponent_ids`` the record stores (since #1658). A record without
        them was written before the fix of the opponent lookup (whose games ran against a
        stand-in table) and is refused: one series never mixes two tables.
        """
        data_path = Path(data_folder)
        folder = games_folder(data_path)
        series_file = folder / f"{batch_id}.series.json"
        if not series_file.is_file():
            raise KeyError(f"no series record found for batch_id {batch_id!r}")
        try:
            raw = json.loads(series_file.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(f"corrupt series record for batch_id {batch_id!r}: {error}") from error

        planned_seeds: list[int]
        if "seeds" in raw and isinstance(raw["seeds"], list):
            planned_seeds = [int(s) for s in raw["seeds"]]
        else:
            exec_chunks = raw.get("execution", {}).get("chunks")
            if isinstance(exec_chunks, list):
                planned_seeds = [
                    int(s) for chunk in exec_chunks if isinstance(chunk, list) for s in chunk
                ]
            else:
                planned_seeds = [int(g["seed"]) for g in raw.get("games", []) if "seed" in g]

        # Scan for already completed games on disk
        completed_games: list[GameSummary] = []
        for seed in planned_seeds:
            gid = f"batch-{batch_id}-s{seed}"
            if any(folder.glob(f"{gid}.jsonl*")):
                try:
                    summary = extract_game_log_telemetry(data_path, gid, candidate_seat=0)
                    if summary.status == "finished":
                        completed_games.append(summary)
                except Exception:
                    pass

        # Resolve opponents if needed: the stored ids, else the stored pod preset; an unknown
        # one is an error, never a stand-in deck (B2, #1658)
        raw_ids = raw.get("opponent_ids")
        stored_ids = [str(oid) for oid in raw_ids] if isinstance(raw_ids, list) else None
        opp_paths = list(opponent_paths or [])
        if not opp_paths:
            if stored_ids is None:
                raise ValueError(
                    f"Serie {batch_id} nennt ihre Gegner nicht (vor #1658 gestartet, ihre Partien "
                    "liefen gegen einen Ersatz-Tisch); nicht fortsetzbar, bitte neu starten"
                )
            opp_paths = resolve_opponent_paths(str(raw.get("pod") or "precon"), stored_ids)

        deck_id = str(raw.get("deck_id") or "chulane")
        revision_id = str(raw.get("revision_id") or "current")
        pod_name = str(raw.get("pod") or "precon")
        exec_info = raw.get("execution", {})
        saved_workers = exec_info.get("workers")
        saved_batch = exec_info.get("games_per_jvm")
        saved_sha = exec_info.get("bridge_jar_sha256") or raw.get("bridge_jar_sha256")
        resolved_sha = (
            bridge_jar_sha256
            if bridge_jar_sha256 is not None
            else (str(saved_sha) if isinstance(saved_sha, str) and saved_sha else None)
        )
        saved_qual = raw.get("bridge_qualification")
        resolved_qual: Mapping[str, object] | None = (
            qualification
            if qualification is not None
            else (saved_qual if isinstance(saved_qual, dict) else None)
        )

        return cls(
            batch_id=batch_id,
            data_folder=data_path,
            deck_id=deck_id,
            revision_id=revision_id,
            pod_name=pod_name,
            opponent_paths=opp_paths,
            opponent_ids=stored_ids,
            seeds=planned_seeds,
            game_executor=game_executor,
            workers=workers if workers is not None else saved_workers,
            games_per_jvm=games_per_jvm if games_per_jvm is not None else saved_batch,
            engine=engine,
            chunk_runner=chunk_runner,
            initial_games=completed_games,
            bridge_jar_sha256=resolved_sha,
            qualification=resolved_qual,
        )

    def run_worker(
        self,
        store_factory: Callable[[], StudioStore] | None = None,
        own_deck_path: Path | None = None,
    ) -> None:
        """Main execution loop running in a background thread."""
        if own_deck_path is not None:
            from .play import snapshot_deck_hash

            self.deck_hash = snapshot_deck_hash(own_deck_path)
        self.started_at = self.started_at or now_utc()
        self.status = "running"

        try:
            if self.chunks:
                with ThreadPoolExecutor(
                    max_workers=min(self.workers, len(self.chunks)),
                    thread_name_prefix=f"series-{self.batch_id}",
                ) as pool:
                    futures = [
                        pool.submit(self._run_chunk, chunk, own_deck_path) for chunk in self.chunks
                    ]
                    for future in futures:
                        future.result()

            # Finish batch
            with self._lock:
                if self._cancel_requested:
                    self.status = "cancelled"
                self.ended_at = now_utc()
                self._games = self._games_in_seed_order()
                self._summary = aggregate_batch_results(self._games)

            # Persist into StudioStore if available
            if (
                not self._cancel_requested
                and store_factory is not None
                and _as_int(self._summary.get("games_completed"), 0) > 0
            ):
                store = store_factory()
                try:
                    # the series rows and their source row: a known write of this process
                    with cache.write(store, _SERIES_WRITES):
                        self.run_id = save_batch_to_store(store, self, self._summary)
                finally:
                    store.close()

            with self._lock:
                if not self._cancel_requested:
                    self.status = "completed"
            self._write_record()

        except Exception as exc:
            with self._lock:
                self.status = "failed"
                self.error = str(exc)
                self.ended_at = now_utc()

    def _write_record(self) -> None:
        """The series record next to the game logs: results and the execution that made them."""
        folder = games_folder(self.data_folder)
        with contextlib.suppress(OSError):
            (folder / f"{self.batch_id}.series.json").write_text(
                json.dumps(self.to_dict(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    def _run_chunk(self, seeds: Sequence[int], own_deck_path: Path | None) -> None:
        """Play one chunk and record a row per game; a failure here is a failed row, never a crash."""
        if self.is_cancelled:
            return
        runner = self.chunk_runner or self._chunk_runner(own_deck_path)
        reported: set[int] = set()
        by_game = {self.game_id_of(seed): seed for seed in seeds}
        with self._lock:
            self.current_game_id = self.game_id_of(seeds[0])
        try:
            for summary in runner(seeds):
                reported.add(by_game.get(summary.game_id, summary.seed))
                self._add_game(summary)
        except Exception as exc:
            for seed in seeds:
                if seed not in reported:
                    reported.add(seed)
                    self._add_game(self._failed(seed, type(exc).__name__, str(exc)))
        for seed in seeds:
            if seed in reported:
                continue
            if self.is_cancelled and not self._log_exists(self.game_id_of(seed)):
                continue  # never started
            reason = "cancelled" if self.is_cancelled else "the chunk ended without this game"
            self._add_game(
                self._failed(seed, "Cancelled" if self.is_cancelled else "NotPlayed", reason)
            )

    def _add_game(self, summary: GameSummary) -> None:
        with self._lock:
            self._games.append(summary)
            self.current_index = len(self._games)
            self.current_game_id = summary.game_id

    def _failed(self, seed: int, failure_class: str, message: str) -> GameSummary:
        return GameSummary(
            game_id=self.game_id_of(seed),
            seed=seed,
            status="failed",
            failure_class=failure_class,
            failure_message=message,
        )

    def _log_exists(self, game_id: str) -> bool:
        return any(games_folder(self.data_folder).glob(f"{game_id}.jsonl*"))

    def _chunk_runner(self, own_deck_path: Path | None) -> ChunkRunner:
        if self.game_executor is not None:
            return lambda seeds: self._executor_chunk(seeds, own_deck_path)
        return lambda seeds: self._process_chunk(seeds, own_deck_path)

    def _executor_chunk(
        self, seeds: Sequence[int], own_deck_path: Path | None
    ) -> Iterator[GameSummary]:
        """Test or custom executor: the games of the chunk one after the other."""
        executor = self.game_executor
        if executor is None:
            return
        for seed in seeds:
            if self.is_cancelled:
                return
            game_id = self.game_id_of(seed)
            exec_res = executor(
                data_folder=self.data_folder,
                deck_paths=[own_deck_path, *self.opponent_paths]
                if own_deck_path
                else list(self.opponent_paths),
                seed=seed,
                game_id=game_id,
                style=self.style,
            )
            status = str(exec_res.get("status") or "finished")
            raw_winners = exec_res.get("winner_seats")
            winners: list[int] = (
                [_as_int(w) for w in raw_winners if isinstance(w, (int, float, str))]
                if isinstance(raw_winners, list)
                else []
            )
            raw_sha = exec_res.get("bridge_jar_sha256")
            game_sha = (
                str(raw_sha) if isinstance(raw_sha, str) and raw_sha else self.bridge_jar_sha256
            )
            raw_qual = exec_res.get("bridge_qualification_state")
            game_qual = (
                str(raw_qual)
                if isinstance(raw_qual, str) and raw_qual
                else str(self.bridge_qualification.get("status") or BRIDGE_UNKNOWN)
            )
            if game_sha is None and game_qual == BRIDGE_ALIGNED:
                game_qual = BRIDGE_UNKNOWN
            if "covered_by_sealed_epoch" in exec_res:
                game_covered = (
                    bool(exec_res.get("covered_by_sealed_epoch"))
                    and game_qual == BRIDGE_ALIGNED
                    and game_sha is not None
                )
            else:
                game_covered = (
                    bool(self.bridge_qualification.get("covered_by_sealed_epoch", False))
                    and game_qual == BRIDGE_ALIGNED
                    and game_sha is not None
                )
            yield GameSummary(
                game_id=game_id,
                seed=seed,
                status=status,
                winner_seats=winners,
                decision_count=_as_int(exec_res.get("decision_count"), 0),
                rounds=_as_int(exec_res.get("rounds"), 10),
                candidate_won=0 in winners,
                bridge_jar_sha256=game_sha,
                bridge_qualification_state=game_qual,
                covered_by_sealed_epoch=game_covered,
            )

    def _process_chunk(
        self, seeds: Sequence[int], own_deck_path: Path | None
    ) -> Iterator[GameSummary]:
        """Launch ``commander_lab.studio play-batch`` for the chunk in a child process.

        The child plays the games in one bridge JVM and prints one line per finished game; the
        summary of a game is read back from its log, as for a game played alone.
        """
        if own_deck_path is None:
            for seed in seeds:
                yield self._failed(seed, "NoDeck", "No own deck path provided")
            return

        cmd = [
            sys.executable,
            "-m",
            "commander_lab.studio",
            "--data",
            str(self.data_folder),
            "play-batch",
            "--deck",
            str(own_deck_path),
        ]
        for opp in self.opponent_paths:
            cmd.extend(["--deck", str(opp)])
        for seed in seeds:
            cmd.extend(["--game", f"{seed}:{self.game_id_of(seed)}"])
        if self.style is not None:
            cmd.extend(["--style", str(self.style)])
        if self.workers > 1:
            # parallel bridge JVMs would collide on the shared card database (#739)
            cmd.append("--private-card-repository")
        env = dict(os.environ)
        if self.engine is not None:
            env[ENGINE_COMMAND_ENV] = command_text(self.engine.command)

        out_file = games_folder(self.data_folder) / f"{self.batch_id}-chunk-s{seeds[0]}.out"
        expected = {self.game_id_of(seed): seed for seed in seeds}
        done: set[str] = set()
        timed_out = threading.Event()
        with out_file.open("w", encoding="utf-8") as err:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=err,
                stdin=subprocess.DEVNULL,
                text=True,
                env=env,
            )
            with self._lock:
                self._processes.add(proc)
                if self._cancel_requested:
                    with contextlib.suppress(OSError):
                        proc.terminate()

            def _expire() -> None:
                timed_out.set()
                with contextlib.suppress(OSError):
                    proc.kill()

            watchdog = threading.Timer(CHUNK_SECONDS_PER_GAME * len(seeds), _expire)
            watchdog.daemon = True
            watchdog.start()
            try:
                if proc.stdout is not None:
                    for line in proc.stdout:
                        played_id = _played_game(line)
                        if played_id is not None:
                            if played_id in expected:
                                self.mark_played(played_id)
                            continue
                        game_id = _reported_game(line)
                        if game_id in expected and game_id not in done:
                            done.add(game_id)
                            yield extract_game_log_telemetry(
                                self.data_folder, game_id, candidate_seat=0
                            )
                code = proc.wait()
            finally:
                watchdog.cancel()
                if proc.poll() is None:
                    with contextlib.suppress(OSError):
                        proc.kill()
                    proc.wait()
                with self._lock:
                    self._processes.discard(proc)
        for game_id, seed in expected.items():
            if game_id in done:
                continue
            if timed_out.is_set():
                limit = int(CHUNK_SECONDS_PER_GAME * len(seeds))
                yield self._failed(seed, "TimeoutExpired", f"Chunk timed out after {limit}s")
            elif self.is_cancelled:
                if self._log_exists(game_id):
                    yield self._failed(seed, "Cancelled", "The series was cancelled")
            elif self._log_exists(game_id):
                # the engine process ended before this game's log was closed
                summary = extract_game_log_telemetry(self.data_folder, game_id, candidate_seat=0)
                if summary.status == "finished":
                    yield summary
                else:
                    yield self._failed(
                        seed,
                        "ChunkProcessExited",
                        f"The engine process ended with exit code {code} during this game",
                    )
            else:
                yield self._failed(
                    seed, "ChunkProcessExited", f"The chunk process ended with exit code {code}"
                )


def _reported_game(line: str) -> str | None:
    """The game id of a ``play-batch`` result line; other output lines are ignored.

    A progress line (``_played_game``) names its game under another key and is not a result.
    """
    try:
        raw = json.loads(line)
    except ValueError:
        return None
    if isinstance(raw, dict) and isinstance(raw.get("game_id"), str):
        return str(raw["game_id"])
    return None


def _played_game(line: str) -> str | None:
    """The game id of a ``play-batch`` progress line (the engine played the game to its end)."""
    try:
        raw = json.loads(line)
    except ValueError:
        return None
    if (
        isinstance(raw, dict)
        and raw.get("event") == "played"
        and isinstance(raw.get("played_game_id"), str)
    ):
        return str(raw["played_game_id"])
    return None


class SimulationBatchManager:
    """Session-level registry and controller for batch simulation jobs."""

    def __init__(self) -> None:
        self._batches: dict[str, BatchSimulation] = {}
        self._lock = threading.Lock()

    def start_batch(
        self,
        store: StudioStore,
        data_folder: str | Path,
        *,
        revision_id: str,
        pod: str = "precon",
        opponent_ids: list[str] | None = None,
        games_count: int = 10,
        base_seed: int = 1000,
        style: float | None = None,
        game_executor: Callable[..., dict[str, object]] | None = None,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        chunk_runner: ChunkRunner | None = None,
        allow_unreleased_seats: bool = False,
    ) -> BatchSimulation:
        """Prepare and start a new batch simulation in a background thread.

        ``workers`` (1..16, default ``min(4, cpu count - 1)``) chunks of games run at once; one
        engine process plays up to ``games_per_jvm`` (1..24, default 16) games of its chunk.
        """
        data_path = Path(data_folder).resolve()
        used_workers, used_games_per_jvm = checked_series_settings(workers, games_per_jvm)

        # Unknown pod or deck id is an error before anything starts (B2, #1658): no other deck
        # takes the seat, so the series plays exactly the table that was asked for.
        opp_paths = resolve_opponent_paths(
            pod, opponent_ids, allow_unreleased_seats=allow_unreleased_seats
        )

        # Engine preflight check
        engine: SeriesEngine | None = None
        if game_executor is None and chunk_runner is None:
            engine = series_engine(data_path, used_games_per_jvm)
            if engine is None:
                state = engine_state(data_path)
                raise RuntimeError(str(state.get("reason") or "Engine is not ready"))

        # Snapshot the candidate deck
        snapshot = lab_snapshot(store, revision_id)
        deck_id = str(snapshot.get("deck_id") or "chulane")
        deck_folder = games_folder(data_path) / "decks"
        deck_folder.mkdir(parents=True, exist_ok=True)
        safe_rev = revision_id.replace("@", "-").replace("/", "-")
        own_deck_path = deck_folder / f"{safe_rev}.json"
        own_deck_path.write_text(
            json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        batch_id = f"batch-{int(time.time())}-{re.sub(r'[^a-z0-9]+', '-', deck_id.lower())[:16]}"
        seeds = [base_seed + i for i in range(games_count)]
        qual = bridge_qualification()
        jar_sha = (
            command_bridge_jar_sha256(data_path, engine.command) if engine is not None else None
        )

        batch = BatchSimulation(
            batch_id=batch_id,
            data_folder=data_path,
            deck_id=deck_id,
            revision_id=revision_id,
            pod_name=pod,
            opponent_paths=opp_paths,
            opponent_ids=opponent_ids if opponent_ids is not None else list(POD_PRESETS[pod]),
            seeds=seeds,
            style=style,
            game_executor=game_executor,
            workers=used_workers,
            games_per_jvm=used_games_per_jvm,
            engine=engine,
            chunk_runner=chunk_runner,
            bridge_jar_sha256=jar_sha,
            qualification=qual,
        )

        with self._lock:
            self._batches[batch_id] = batch

        # Store factory for persistence at end of run
        def _open_store() -> StudioStore:
            if store.path is not None:
                return StudioStore.open(store.path.parent)
            return StudioStore.open(data_path)

        thread = threading.Thread(
            target=batch.run_worker,
            kwargs={"store_factory": _open_store, "own_deck_path": own_deck_path},
            daemon=True,
        )
        thread.start()
        return batch

    def get_batch(self, batch_id: str) -> BatchSimulation | None:
        with self._lock:
            return self._batches.get(batch_id)

    def resume_batch(
        self,
        store: StudioStore,
        data_folder: str | Path,
        batch_id: str,
        *,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        chunk_runner: ChunkRunner | None = None,
        game_executor: Callable[..., dict[str, object]] | None = None,
    ) -> BatchSimulation:
        """Resume an incomplete or interrupted batch simulation."""
        data_path = Path(data_folder).resolve()
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is not None and existing.status in ("pending", "running"):
                raise RuntimeError(f"Batch {batch_id} is already active (status={existing.status})")

        used_workers, used_games_per_jvm = checked_series_settings(workers, games_per_jvm)
        engine: SeriesEngine | None = None
        if game_executor is None and chunk_runner is None:
            engine = series_engine(data_path, used_games_per_jvm)
        qual = bridge_qualification()
        jar_sha = (
            command_bridge_jar_sha256(data_path, engine.command) if engine is not None else None
        )

        if existing is not None:
            completed_seeds = {g.seed for g in existing._games if g.status == "finished"}
            remaining_seeds = [s for s in existing.seeds if s not in completed_seeds]
            existing.chunks = plan_chunks(remaining_seeds, used_workers, used_games_per_jvm)
            existing.workers = used_workers
            existing.games_per_jvm = used_games_per_jvm
            existing.engine = engine
            existing.bridge_qualification = dict(qual)
            if jar_sha is not None:
                existing.bridge_jar_sha256 = jar_sha
            existing._cancel_requested = False
            batch = existing
        else:
            batch = BatchSimulation.from_saved_series(
                data_path,
                batch_id,
                workers=used_workers,
                games_per_jvm=used_games_per_jvm,
                engine=engine,
                chunk_runner=chunk_runner,
                game_executor=game_executor,
                bridge_jar_sha256=jar_sha,
                qualification=qual,
            )

        with self._lock:
            self._batches[batch_id] = batch

        if not batch.chunks:
            batch.status = "completed"
            return batch

        # Locate or snapshot candidate deck
        safe_rev = batch.revision_id.replace("@", "-").replace("/", "-")
        deck_folder = games_folder(data_path) / "decks"
        own_deck_path = deck_folder / f"{safe_rev}.json"
        if not own_deck_path.is_file():
            snapshot = lab_snapshot(store, batch.revision_id)
            deck_folder.mkdir(parents=True, exist_ok=True)
            own_deck_path.write_text(
                json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
            )

        def _open_store() -> StudioStore:
            if store.path is not None:
                return StudioStore.open(store.path.parent)
            return StudioStore.open(data_path)

        thread = threading.Thread(
            target=batch.run_worker,
            kwargs={"store_factory": _open_store, "own_deck_path": own_deck_path},
            daemon=True,
        )
        thread.start()
        return batch

    def cancel_batch(self, batch_id: str) -> bool:
        batch = self.get_batch(batch_id)
        if batch is None:
            return False
        batch.cancel()
        return True

    def list_batches(self) -> list[dict[str, object]]:
        with self._lock:
            return [b.to_dict() for b in reversed(list(self._batches.values()))]


# Global manager singleton for web runtime
simulation_manager = SimulationBatchManager()
