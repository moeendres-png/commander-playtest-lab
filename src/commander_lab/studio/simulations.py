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
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin

from .decks import lab_snapshot
from .games import games_folder, read_game
from .launch import POD_PRESETS, engine_command, engine_state
from .store import DataClass, StudioStore, now_utc

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
    observed_cards: dict[str, dict[str, object]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
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
        }


def extract_game_log_telemetry(
    data_folder: str | Path,
    game_id: str,
    candidate_seat: int = 0,
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
    raw_winners = result.get("winner_seats")
    winner_seats: list[int] = (
        [_as_int(s) for s in raw_winners if isinstance(s, (int, float, str))]
        if isinstance(raw_winners, list)
        else []
    )
    candidate_won = candidate_seat in winner_seats
    decision_count = _as_int(result.get("decision_count") or data.get("total"), 0)

    # Scan frames for turn count and candidate cards in hand / cast
    max_turn = 0
    offered_cards: set[str] = set()
    cast_cards: dict[str, int] = {}
    first_cast_round: dict[str, int] = {}

    frames = data.get("frames")
    if isinstance(frames, list):
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            turn = frame.get("turn")
            if isinstance(turn, int) and turn > max_turn:
                max_turn = turn

            # If actor is candidate seat, extract hand cards
            seat = frame.get("seat")
            players = frame.get("players")
            if isinstance(players, list) and len(players) > candidate_seat:
                c_player = players[candidate_seat]
                if isinstance(c_player, dict):
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
        observed_cards=card_telemetry,
    )


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

        cards_summary.append(
            {
                "card_name": c_name,
                "games_completed": completed_count,
                "games_offered": offered_games,
                "games_cast_after_offer": cast_games,
                "games_rotted": rotted_games,
                "offered_castable": offered_games,
                "cast_count": total_casts,
                "mean_first_cast_round": mean_first_round,
            }
        )

    return {
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
        "cards": cards_summary,
    }


def save_batch_to_store(
    store: StudioStore,
    batch: BatchSimulation,
    summary: dict[str, object],
) -> str:
    """Save an aggregated batch simulation into simulation_run and simulation_card."""
    run_id = f"batch-{batch.batch_id}"
    engine_pin = canonical_xmage_engine_pin()

    # Create a reproducible content hash for source registration
    source_payload = json.dumps(
        {
            "run_id": run_id,
            "deck_id": batch.deck_id,
            "pod": batch.pod_name,
            "seeds": batch.seeds,
            "completed": summary.get("games_completed"),
        },
        sort_keys=True,
    )
    source_sha = hashlib.sha256(source_payload.encode("utf-8")).hexdigest()

    source_id = store.register_source(
        data_class=DataClass.SIMULATED_RESULT,
        title=f"Studio Batch Simulation {batch.batch_id} ({batch.pod_name})",
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
            "INSERT OR REPLACE INTO simulation_run(run_id, deck_id, pod, engine_pin, "
            "pilot_policy, seeds, games_planned, games_completed, games_failed, "
            "wins_fractional, win_rate, mean_rounds, hand_dwell_status, source_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                batch.deck_id,
                batch.pod_name,
                engine_pin,
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

    return run_id


class BatchSimulation:
    """Manages execution and status of a multi-game simulation series."""

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
    ) -> None:
        self.batch_id = batch_id
        self.data_folder = Path(data_folder)
        self.deck_id = deck_id
        self.revision_id = revision_id
        self.pod_name = pod_name
        self.opponent_paths = opponent_paths
        self.seeds = list(seeds)
        self.style = style
        self.game_executor = game_executor

        self.status = "pending"  # pending, running, completed, cancelled, failed
        self.current_index = 0
        self.current_game_id: str | None = None
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.error: str | None = None
        self.run_id: str | None = None

        self._cancel_requested = False
        self._current_process: subprocess.Popen[str] | None = None
        self._games: list[GameSummary] = []
        self._summary: dict[str, object] | None = None
        self._lock = threading.Lock()

    def cancel(self) -> None:
        """Gracefully request cancellation and terminate the active game process."""
        with self._lock:
            self._cancel_requested = True
            if self._current_process is not None:
                with contextlib.suppress(OSError):
                    self._current_process.terminate()

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                "batch_id": self.batch_id,
                "deck_id": self.deck_id,
                "revision_id": self.revision_id,
                "pod": self.pod_name,
                "status": self.status,
                "games_planned": len(self.seeds),
                "games_completed": sum(1 for g in self._games if g.status == "finished"),
                "games_failed": sum(1 for g in self._games if g.status != "finished"),
                "current_index": self.current_index,
                "current_game_id": self.current_game_id,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "error": self.error,
                "run_id": self.run_id,
                "summary": self._summary,
                "games": [g.to_dict() for g in self._games],
            }

    def run_worker(
        self,
        store_factory: Callable[[], StudioStore] | None = None,
        own_deck_path: Path | None = None,
    ) -> None:
        """Main execution loop running in a background thread."""
        self.started_at = now_utc()
        self.status = "running"

        try:
            for idx, seed in enumerate(self.seeds, start=1):
                if self.is_cancelled:
                    break

                self.current_index = idx
                game_id = f"batch-{self.batch_id}-s{seed}"
                self.current_game_id = game_id

                if self.game_executor is not None:
                    # Test or custom executor
                    exec_res = self.game_executor(
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
                    decisions_count = _as_int(exec_res.get("decision_count"), 0)
                    summary = GameSummary(
                        game_id=game_id,
                        seed=seed,
                        status=status,
                        winner_seats=winners,
                        decision_count=decisions_count,
                        rounds=_as_int(exec_res.get("rounds"), 10),
                        candidate_won=0 in winners,
                    )
                else:
                    # Isolated process execution
                    summary = self._run_game_process(game_id, seed, own_deck_path)

                with self._lock:
                    self._games.append(summary)

                if self.is_cancelled:
                    break

            # Finish batch
            with self._lock:
                if self._cancel_requested:
                    self.status = "cancelled"
                self.ended_at = now_utc()
                self._summary = aggregate_batch_results(self._games)

            # Persist into StudioStore if available
            if (
                not self._cancel_requested
                and store_factory is not None
                and _as_int(self._summary.get("games_completed"), 0) > 0
            ):
                store = store_factory()
                try:
                    self.run_id = save_batch_to_store(store, self, self._summary)
                finally:
                    store.close()

            with self._lock:
                if not self._cancel_requested:
                    self.status = "completed"

        except Exception as exc:
            with self._lock:
                self.status = "failed"
                self.error = str(exc)
                self.ended_at = now_utc()

    def _run_game_process(
        self,
        game_id: str,
        seed: int,
        own_deck_path: Path | None,
    ) -> GameSummary:
        """Launch commander_lab.studio play in an isolated child process."""
        if own_deck_path is None:
            return GameSummary(
                game_id=game_id,
                seed=seed,
                status="failed",
                failure_message="No own deck path provided",
            )

        cmd = [
            sys.executable,
            "-m",
            "commander_lab.studio",
            "--data",
            str(self.data_folder),
            "play",
            "--seed",
            str(seed),
            "--game-id",
            game_id,
            "--deck",
            str(own_deck_path),
        ]
        for opp in self.opponent_paths:
            cmd.extend(["--deck", str(opp)])
        if self.style is not None:
            cmd.extend(["--style", str(self.style)])

        folder = games_folder(self.data_folder)
        out_file = folder / f"{game_id}.out"
        try:
            with out_file.open("w", encoding="utf-8") as out:
                proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, text=True)
                with self._lock:
                    self._current_process = proc
                    if self._cancel_requested:
                        with contextlib.suppress(OSError):
                            proc.terminate()

                # Wait for child process to terminate
                proc.wait(timeout=300.0)

            with self._lock:
                self._current_process = None

            # Read back game log
            return extract_game_log_telemetry(self.data_folder, game_id, candidate_seat=0)

        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
            return GameSummary(
                game_id=game_id,
                seed=seed,
                status="failed",
                failure_class="TimeoutExpired",
                failure_message="Game execution timed out after 300s",
            )
        except Exception as exc:
            return GameSummary(
                game_id=game_id,
                seed=seed,
                status="failed",
                failure_class=type(exc).__name__,
                failure_message=str(exc),
            )


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
        seed_step: int = 1,
        style: float | None = None,
        game_executor: Callable[..., dict[str, object]] | None = None,
    ) -> BatchSimulation:
        """Prepare and start a new batch simulation in a background thread."""
        data_path = Path(data_folder).resolve()

        # Engine preflight check
        if game_executor is None and engine_command(data_path) is None:
            state = engine_state(data_path)
            raise RuntimeError(str(state.get("reason") or "Engine is not ready"))

        # Resolve opponent decks
        if opponent_ids:
            opp_list = opponent_ids
        elif pod in POD_PRESETS:
            opp_list = list(POD_PRESETS[pod])
        else:
            opp_list = list(POD_PRESETS["precon"])

        root = Path(__file__).resolve().parents[3]
        opp_paths: list[Path] = []
        for oid in opp_list:
            # Check precon / opponent files
            candidate = root / f"data/decks/precons/{oid}.json"
            if candidate.is_file():
                opp_paths.append(candidate)
                continue
            # Try searching precons
            found = False
            for p in (root / "data/decks/precons").glob("*.json"):
                if p.stem.endswith(oid) or oid in p.stem:
                    opp_paths.append(p)
                    found = True
                    break
            if not found:
                # Fallback to direct path or first precon
                fallback = root / "data/decks/precons/2026_lorehold_spirit.json"
                if fallback.is_file():
                    opp_paths.append(fallback)

        if not opp_paths:
            # Default to three available precons
            all_precons = sorted((root / "data/decks/precons").glob("*.json"))
            opp_paths = all_precons[:3] if len(all_precons) >= 3 else all_precons

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
        seeds = [base_seed + i * seed_step for i in range(games_count)]

        batch = BatchSimulation(
            batch_id=batch_id,
            data_folder=data_path,
            deck_id=deck_id,
            revision_id=revision_id,
            pod_name=pod,
            opponent_paths=opp_paths,
            seeds=seeds,
            style=style,
            game_executor=game_executor,
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
