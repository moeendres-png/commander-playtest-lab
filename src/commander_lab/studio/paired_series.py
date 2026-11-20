"""Paired overnight comparison series controller and C-3 simulator-readiness audit.

Orchestrates background paired A-vs-B comparison series (same seeds, same seats,
same opponent pod, O'Brien-Fleming sequential looks) on top of ``paired_comparison``
and provides the C-3 simulator readiness audit across a deck and its free Tier-S/A
pool candidates (#1404 Option 6, C-3).

Hard invariants:
- XMage remains the sole rules authority; no rule decisions live here.
- Simulation results stay strictly ``SIMULATED_RESULT`` and never touch ``strength_view``
  weights or the tier list (``simulation`` weight stays 0).
- Fail-closed: missing XMage/pilot catalogs report ``UNKNOWN`` (never fabricated PASS).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from commander_lab.agents.card_knowledge import CardCatalogError, card_facts
from commander_lab.bridge_qualification import bridge_qualification
from commander_lab.engine.rules.full_game_comparison import (
    PLANNED_PAIR_SD,
    SlotAlignment,
    align_to_baseline_slots,
    difference_quantiles,
    pairs_needed,
)
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import RulesDeckInput

from . import builder, decks, paired_comparison, strength_view
from .card_outcomes import pilot_identity
from .decks import RevisionCard, lab_snapshot, list_rows, resolve_repo_baseline_cards
from .games import games_folder
from .launch import (
    MAX_SEATS,
    MIN_SEATS,
    SeriesEngine,
    cards_unknown_to_pilots,
    cards_unsupported_by_engine,
    checked_series_settings,
    engine_state,
    resolve_opponent_paths,
    series_engine,
    validate_released_seat_count,
)
from .launch import POD_PRESETS as POD_PRESETS  # re-exported for callers and tests
from .launch import (
    bridge_jar_sha256 as command_bridge_jar_sha256,
)
from .play import header_pilot_fingerprint
from .store import StudioStore, now_utc
from .strength import StrengthSettings

SCHEMA_PAIRED_JOB = "studio-paired-series-job-1"
SCHEMA_READINESS_AUDIT = "studio-sim-readiness-audit-1"

#: Per-worker throughput that #1513 multiplies by the workers: an UNMEASURED assumption, kept as
#: ``assumed_games_per_hour_unmeasured`` and never used for the duration shown. Measured is only
#: the batch series on the Owner PC (#1251): 541.2 games/hour for the WHOLE series with 6 workers
#: and 8 games per JVM, after the #1299 forced-pass option, i.e. about 90 per worker.
ESTIMATED_GAMES_PER_HOUR = 540.0
#: The one measured rate (#1251, whole batch series, 6 workers): the duration shown is the time
#: at this rate, a lower bound while no more than 6 workers run; paired series are unmeasured.
MEASURED_BATCH_GAMES_PER_HOUR = 541.2
MEASURED_BATCH_WORKERS = 6
THROUGHPUT_SOURCE = (
    "gemessen sind nur 541 Partien/h für eine ganze Batch-Serie mit 6 Workern und 8 Partien je "
    "JVM (#1251), also etwa 90 je Worker; für gepaarte Serien ist der Durchsatz ungemessen"
)
#: Assumed block correlation of the seat rotations of one seed, as in ``power_table`` (#1043).
PLANNING_BLOCK_CORRELATION = 0.25
PLANNING_REFERENCE_EFFECT_PP = 5.0
SERIES_PURPOSES = ("unspecified", "exploration", "confirmation", "control")
_SAFE_SERIES_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")


class SeriesCancelledError(RuntimeError):
    """Raised internally when an active paired series is cancelled by the user."""


def validate_series_id(series_id: str) -> str:
    cleaned = series_id.strip()
    if not _SAFE_SERIES_ID.fullmatch(cleaned):
        raise ValueError("invalid series_id")
    return cleaned


def _planned_detectable(pairs: int, seats_per_seed: int) -> float:
    """``(t95 + t80) * sd / sqrt(pairs)`` with t at (seeds - 1) df, as the evaluation uses."""
    seeds = max(1, math.ceil(pairs / seats_per_seed))
    t95, t80 = difference_quantiles(max(1, seeds - 1))
    return (t95 + t80) * PLANNED_PAIR_SD / math.sqrt(pairs)


def planned_detectable_difference_pp(budget_pairs: int, seats_per_seed: int) -> dict[str, object]:
    """What ``budget_pairs`` can detect before a game is played, with the assumptions named.

    The arithmetic of the evaluation (``cluster_difference_stats``: Student-t quantiles at
    seeds - 1 degrees of freedom, one cluster per seed) on the assumed pair sd 0.63, the
    engine lane's conservative planning value (exact for independent games at a 25 % win rate:
    ``sqrt(2 * 0.25 * 0.75) = 0.612``). The pairing correlation is unmeasured, so the sd is not
    lowered for it; the seat rotations of one seed count with the design effect
    ``1 + (m - 1) * 0.25`` at the upper end. A plan, not a measurement.
    """
    pairs = max(2, int(budget_pairs))
    seats = max(1, int(seats_per_seed))
    design_effect = 1.0 + (seats - 1) * PLANNING_BLOCK_CORRELATION
    seeds = max(1, math.ceil(pairs / seats))
    # one seed: no spread between seeds, the evaluation gives no interval either (unknown)
    low: float | None = _planned_detectable(pairs, seats) if seeds >= 2 else None
    effect = PLANNING_REFERENCE_EFFECT_PP / 100.0
    needed = pairs_needed(effect, PLANNED_PAIR_SD)  # normal quantiles: a lower bound
    while _planned_detectable(needed, seats) > effect:
        needed += 1
    return {
        "budget_pairs": pairs,
        "detectable_pp_low": None if low is None else round(low * 100.0, 1),
        "detectable_pp_high": (
            None if low is None else round(low * math.sqrt(design_effect) * 100.0, 1)
        ),
        "reference_effect_pp": PLANNING_REFERENCE_EFFECT_PP,
        "pairs_needed_low": needed,
        "pairs_needed_high": math.ceil(needed * design_effect),
        "assumptions": {
            "confidence": 0.95,
            "power": 0.80,
            "quantiles": "Student-t at seeds - 1 degrees of freedom (as cluster_difference_stats)",
            "degrees_of_freedom": max(1, seeds - 1),
            "pair_sd": PLANNED_PAIR_SD,
            "pair_sd_independent_exact": round(math.sqrt(2 * 0.25 * 0.75), 4),
            "pair_sd_basis": (
                "conservative planning value; independent games at 25 % win rate give 0.612; "
                "pairing correlation unmeasured"
            ),
            "seats_per_seed": seats,
            "design_effect": round(design_effect, 4),
            "block_correlation_assumed": PLANNING_BLOCK_CORRELATION,
            "sequential_looks": "not included (O'Brien-Fleming looks cost a little power)",
        },
    }


def estimate_series_duration(
    budget_pairs: int,
    *,
    pairs_planned_max: int | None = None,
    workers: int | None = None,
    games_per_jvm: int | None = None,
    seats_per_seed: int = 4,
) -> dict[str, object]:
    """Pre-run duration floor and plan for a paired A-vs-B comparison series.

    The duration is the time at the one measured rate (``MEASURED_BATCH_GAMES_PER_HOUR``, a
    whole 6-worker batch series): a lower bound, not a forecast, while no more than 6 workers
    run. ``estimated_seconds`` / ``estimated_minutes`` keep their names for older readers and
    carry the same floor. The #1513 per-worker figure stays visible as an unmeasured assumption.
    """
    used_workers = max(1, int(workers)) if workers is not None else 1
    assumed_rate = ESTIMATED_GAMES_PER_HOUR * used_workers
    pairs = max(0, int(pairs_planned_max if pairs_planned_max is not None else budget_pairs))
    max_games = pairs * 2
    seconds = round(max_games * (3600.0 / MEASURED_BATCH_GAMES_PER_HOUR))
    minutes = round(seconds / 60.0, 1)
    floor_holds = used_workers <= MEASURED_BATCH_WORKERS
    payload: dict[str, object] = {
        "budget_pairs": int(budget_pairs),
        "max_games": max_games,
        "measured_batch_games_per_hour": MEASURED_BATCH_GAMES_PER_HOUR,
        "minimum_seconds": seconds,
        "minimum_minutes": minutes,
        "minimum_is_lower_bound": floor_holds,
        "estimated_seconds": seconds,
        "estimated_minutes": minutes,
        "assumed_games_per_hour_unmeasured": int(assumed_rate),
        "workers": used_workers,
        "throughput_measured_for_paired_series": False,
        "throughput_source": THROUGHPUT_SOURCE,
        "basis": (
            f"mindestens ~{minutes} min bei der gemessenen Rate von "
            f"{MEASURED_BATCH_GAMES_PER_HOUR:.0f} Partien/h; {THROUGHPUT_SOURCE}, die Dauer ist "
            "vermutlich deutlich länger"
            + ("" if floor_holds else " (mit mehr als 6 Workern keine sichere Untergrenze)")
            + ". 2 Partien je Paar; früher Stopp je nach Look möglich."
        ),
        "planning": planned_detectable_difference_pp(max(2, pairs), seats_per_seed),
    }
    if games_per_jvm is not None:
        payload["games_per_jvm"] = int(games_per_jvm)
    return payload


#: One resolver for every surface (batch, series, experiment): unknown is an error.
_resolve_opponent_paths = resolve_opponent_paths


def is_revision_ref(ref: str) -> bool:
    """A Studio deck state (``<deck>@<hash>`` or ``repo:<stem>``), not a repository precon."""
    return "@" in ref or ref.startswith("repo:")


def _table_opponent_paths(
    store: StudioStore | None,
    deck_dir: Path,
    pod: str,
    opponent_ids: Sequence[str] | None,
    taken_deck_ids: set[str],
    table_seats: int | None = None,
) -> list[Path]:
    """The opponents' deck files: precons from the repository, Studio deck states (E15 Q6)
    as snapshot files in the series folder. With ``store`` the snapshots are written (start);
    without, they must already be there (resume). Unknown is an error, never a stand-in.
    ``table_seats`` (#1702) picks the preset of that size and is checked against the lock."""
    if opponent_ids is None or not any(is_revision_ref(str(o)) for o in opponent_ids):
        return resolve_opponent_paths(pod, opponent_ids, table_seats=table_seats)
    ids = [str(o).strip() for o in opponent_ids]
    if table_seats is not None:
        validate_released_seat_count(table_seats - 1)
        if len(ids) != table_seats - 1:
            raise ValueError(
                f"ein Tisch mit {table_seats} Sitzen braucht {table_seats - 1} Gegner, "
                f"angegeben sind {len(ids)}"
            )
    if len(set(ids)) != len(ids):
        raise ValueError("Gegner-Decks dürfen nicht doppelt vorkommen")
    precons = [o for o in ids if not is_revision_ref(o)]
    precon_paths = iter(resolve_opponent_paths(pod, precons) if precons else [])
    paths: list[Path] = []
    for index, oid in enumerate(ids):
        if not is_revision_ref(oid):
            paths.append(next(precon_paths))
            continue
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", oid)[:80]
        path = deck_dir / f"opponent-{index}-{safe}.json"
        if store is None:
            if not path.is_file():
                raise FileNotFoundError(f"Gegner-Snapshot {path.name} fehlt (nicht fortsetzbar)")
        else:
            snap = _snapshot_for_ref(store, oid)
            _preflight_snapshot_cards(f"Gegner-Deck {oid}", snap)
            if str(snap["deck_id"]) in taken_deck_ids:  # e.g. another state of the same deck
                snap["deck_id"] = f"{snap['deck_id']}--opp{index}"
            _write_json_atomic(path, snap)
        paths.append(path)
        taken_deck_ids.add(load_rules_deck_snapshot(path).deck_id)
    return paths


def _snapshot_for_ref(store: StudioStore, ref_id: str) -> dict[str, object]:
    """Convert a stored ``rev@...`` revision OR ``repo:<stem>`` baseline into a Rules snapshot."""
    if ref_id.startswith("repo:"):
        entries = resolve_repo_baseline_cards(store, ref_id)
        rows = list_rows(store, entries)
        commanders = [
            str(row["engine_name"] or row["oracle_name"])
            for row in rows
            if row["zone"] == "commander"
        ]
        stem = ref_id.split(":", 1)[1]
        digest = hashlib.sha256(
            json.dumps(
                [(str(r["engine_name"]), int(r["quantity"]), str(r["zone"])) for r in rows],
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return {
            "deck_id": f"repo-{stem}",
            "name": f"Referenz ({stem})",
            "studio_revision_id": ref_id,
            "studio_deck_hash": digest,
            "commander": {
                "commanders": commanders,
                "uses_partner": len(commanders) > 1,
                "commander_identity_override": None,
            },
            "cards": [
                {
                    "oracle_name": str(row["engine_name"] or row["oracle_name"]),
                    "quantity": int(str(row["quantity"])),
                    "zone": str(row["zone"]),
                }
                for row in rows
            ],
        }
    return lab_snapshot(store, ref_id)


def _preflight_snapshot_cards(label: str, snapshot: dict[str, object]) -> None:
    if not builder.sim_readiness_available():
        return
    unsupported = cards_unsupported_by_engine(snapshot)
    if unsupported:
        raise ValueError(
            f"{label}: XMage unterstützt diese Karten noch nicht: {', '.join(unsupported[:8])}"
        )
    unknown = cards_unknown_to_pilots(snapshot)
    if unknown:
        raise ValueError(
            f"{label}: Das Piloten-Kartenwissen kennt diese Karten noch nicht: {', '.join(unknown[:8])}"
        )


def _snapshot_file(folder: Path, prefix: str, ref_id: str, snapshot: Mapping[str, object]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", ref_id)[:80] or prefix
    path = folder / f"{prefix}-{safe}.json"
    path.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _align_variant_file(
    base_deck: RulesDeckInput,
    variant_deck: RulesDeckInput,
    variant_snap: Mapping[str, object],
    variant_path: Path,
) -> tuple[RulesDeckInput, SlotAlignment]:
    """Rewrite the variant's deck file with its cards in the baseline's library slots.

    Studio snapshots list cards by name, so a swap that crosses the alphabet moves every
    card in between to another slot and the two games of a pair share no library shuffle.
    The engine reads the deck file (``recorded_game_player`` passes paths), so the file
    itself gets the aligned main-zone order (``align_to_baseline_slots`` of the engine
    lane); every other entry stays as it was. The cards are exactly the variant's.
    """
    aligned, alignment = align_to_baseline_slots(base_deck, variant_deck)
    raw_cards = variant_snap.get("cards")
    entries = [e for e in raw_cards if isinstance(e, dict)] if isinstance(raw_cards, list) else []
    runs: list[dict[str, object]] = []
    for name in aligned.mainboard:
        last = runs[-1] if runs else None
        if last is not None and last["oracle_name"] == name:
            last["quantity"] = int(str(last["quantity"])) + 1
        else:
            runs.append({"oracle_name": name, "quantity": 1, "zone": "main"})
    others = [e for e in entries if e.get("zone") not in (None, "main")]
    _write_json_atomic(variant_path, {**variant_snap, "cards": [*others, *runs]})
    reloaded = load_rules_deck_snapshot(variant_path)
    if reloaded.mainboard != aligned.mainboard:
        raise ValueError("aligned variant deck file does not reload in the aligned order")
    return reloaded, alignment


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
    finally:
        with contextlib.suppress(OSError):
            if tmp.exists():
                tmp.unlink()


def pilot_change_message(
    preloaded: Mapping[tuple[str, int, int], paired_comparison.PlayedGame], current: str
) -> str | None:
    """Why an interrupted series cannot go on with the current pilot, or None (#1658).

    Games already played with another pilot (or before the fingerprint existed) would meet
    games of the current pilot in one comparison; that is never counted together."""
    others = [
        str(pilot_identity(exposure))
        for played in preloaded.values()
        if (exposure := played.get("exposure")) is not None and pilot_identity(exposure) != current
    ]
    if not others:
        return None
    return (
        f"nicht fortsetzbar: {len(others)} gespeicherte Partien dieser Serie stammen von einem "
        f"anderen Piloten ({', '.join(o[:20] for o in sorted(set(others)))}) als dem aktuellen "
        f"({current[:20]}); Partien verschiedener Piloten werden nie zusammengezählt. "
        "Bitte die Serie neu starten."
    )


class PairedSeriesJob:
    """In-memory + on-disk handle for one background paired A-vs-B comparison series."""

    def __init__(
        self,
        *,
        series_id: str,
        data_folder: Path,
        base_ref: str,
        variant_ref: str,
        base_deck: RulesDeckInput,
        variant_deck: RulesDeckInput,
        opponents: Sequence[RulesDeckInput],
        paths_by_deck_id: Mapping[str, Path],
        pod_name: str,
        seeds: list[int],
        tested_seats: list[int],
        budget_pairs: int,
        look_every_pairs: int,
        threshold_pp: float,
        significance_level: float = paired_comparison.DEFAULT_SIGNIFICANCE_LEVEL,
        play_override: paired_comparison.PairPlayer | None = None,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        engine: SeriesEngine | None = None,
        bridge_sha: str | None = None,
        qualification: Mapping[str, object] | None = None,
        slot_alignment: SlotAlignment | None = None,
        purpose: str = "unspecified",
        player_count: int | None = None,
        opponent_ids: Sequence[str] | None = None,
        raw_slot_alignment: dict[str, object] | None = None,
        created_at: str | None = None,
        preloaded_games: dict[tuple[str, int, int], paired_comparison.PlayedGame] | None = None,
        experiment: Mapping[str, object] | None = None,
    ) -> None:
        self.series_id = series_id
        #: The experiment this series plays (B2, #1658): id, plan SHA and table hash.
        self.experiment = dict(experiment) if experiment is not None else None
        self.data_folder = data_folder
        self.base_ref = base_ref
        self.variant_ref = variant_ref
        self.base_deck = base_deck
        self.variant_deck = variant_deck
        self.opponents = list(opponents)
        self.opponent_ids = list(opponent_ids) if opponent_ids is not None else None
        self.paths_by_deck_id = dict(paths_by_deck_id)
        self.pod_name = pod_name
        self.seeds = list(seeds)
        self.tested_seats = list(tested_seats)
        self.budget_pairs = budget_pairs
        self.look_every_pairs = look_every_pairs
        self.threshold_pp = threshold_pp
        self.significance_level = significance_level
        self.play_override = play_override
        self.workers, requested_batch = checked_series_settings(workers, games_per_jvm)
        self.engine = engine
        self.games_per_jvm = engine.games_per_jvm if engine is not None else requested_batch
        self.bridge_jar_sha256 = bridge_sha
        self.bridge_qualification = (
            dict(qualification) if qualification is not None else bridge_qualification()
        )
        self.estimate = estimate_series_duration(
            budget_pairs,
            workers=self.workers,
            games_per_jvm=self.games_per_jvm,
            seats_per_seed=len(tested_seats),
        )
        table_size = player_count if player_count is not None else 1 + len(self.opponents)
        #: Consecutive seeds on purpose: the engine starts the game at seat ``seed % players``
        #: (``full_game``), so a run of consecutive seeds balances the turn order.
        self.seed_plan: dict[str, object] = {
            "purpose": purpose,
            "first_seed": self.seeds[0] if self.seeds else None,
            "last_seed": self.seeds[-1] if self.seeds else None,
            "seeds_planned": len(self.seeds),
            "seed_rule": "consecutive",
            "player_count": table_size,
            "starting_seat_rule": "seed % player_count",
        }
        #: How the variant's library was lined up with the base's; ``None`` only for a
        #: series written before the alignment existed (its pairs share no shuffle).
        self.slot_alignment: dict[str, object] | None = (
            dict(raw_slot_alignment)
            if raw_slot_alignment is not None
            else (slot_alignment.model_dump() if slot_alignment is not None else None)
        )
        self.preloaded_games: dict[tuple[str, int, int], paired_comparison.PlayedGame] = (
            dict(preloaded_games) if preloaded_games else {}
        )

        self.status = "pending"
        self.pairs_attempted = len(
            {
                (seed, seat)
                for seed in self.seeds
                for seat in self.tested_seats
                if ("base", seed, seat) in self.preloaded_games
                and ("variant", seed, seat) in self.preloaded_games
            }
        )
        self.created_at = created_at or now_utc()
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.error: str | None = None
        self.result: paired_comparison.PairedComparison | None = None
        self._cancel_requested = False
        #: Games the engine has played to their end: the ones taken over from disk plus those
        #: announced during this run. A progress count that comes before the pair is complete.
        self._games_played: set[tuple[str, int, int]] = {
            key
            for key, played in self.preloaded_games.items()
            if played.get("failure_class") is None
        }
        self._lock = threading.Lock()
        self._persist_lock = threading.Lock()
        self._progress_lock = threading.Lock()

    def series_file(self) -> Path:
        return games_folder(self.data_folder) / f"{self.series_id}.paired.json"

    def progress_file(self) -> Path:
        return games_folder(self.data_folder) / "paired_decks" / self.series_id / "progress.jsonl"

    def lock_file(self) -> Path:
        return games_folder(self.data_folder) / "paired_decks" / self.series_id / "running.lock"

    def _write_lock(self) -> None:
        path = self.lock_file()
        _write_json_atomic(
            path,
            {
                "series_id": self.series_id,
                "pid": os.getpid(),
                "started_at": now_utc(),
                "heartbeat": time.time(),
            },
        )

    def _release_lock(self) -> None:
        with contextlib.suppress(OSError):
            self.lock_file().unlink(missing_ok=True)

    def _ensure_progress_newline(self) -> None:
        path = self.progress_file()
        if not path.is_file():
            return
        with self._progress_lock:
            size = path.stat().st_size
            if size > 0:
                with path.open("rb") as handle:
                    handle.seek(-1, os.SEEK_END)
                    last = handle.read(1)
                if last != b"\n":
                    with path.open("ab") as handle:
                        handle.write(b"\n")

    def _append_game_result(
        self, arm: str, seed: int, seat: int, played: paired_comparison.PlayedGame
    ) -> None:
        if played.get("failure_class") is not None:
            with self._lock:  # a game that ended as a failure is not a played game
                self._games_played.discard((arm, seed, seat))
        path = self.progress_file()
        line = json.dumps(
            {"arm": arm, "seed": seed, "seat": seat, "played": played},
            ensure_ascii=False,
        )
        with self._progress_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        self._write_lock()

    def mark_game_played(self, arm: str, seed: int, seat: int) -> None:
        """Count one game of this series as played by the engine (progress only)."""
        with self._lock:
            self._games_played.add((arm, seed, seat))
        self.persist()

    def cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True

    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def persist(self) -> None:
        with self._persist_lock:
            _write_json_atomic(self.series_file(), self.to_dict())

    def execution_metadata(self) -> dict[str, object]:
        engine = self.engine
        return {
            "workers": self.workers,
            "games_per_jvm": self.games_per_jvm,
            "serial_gc": engine.serial_gc if engine is not None else False,
            "appcds": engine.appcds if engine is not None else False,
        }

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            res = self.result
            bridge_shas = (
                list(res.get("bridge_jar_sha256s", []))
                if res
                else ([self.bridge_jar_sha256] if self.bridge_jar_sha256 else [])
            )
            qual_states = (
                list(res.get("bridge_qualification_states", []))
                if res
                else (
                    [str(self.bridge_qualification.get("status"))]
                    if self.bridge_qualification.get("status")
                    else []
                )
            )
            covered = bool(res.get("covered_by_sealed_epoch")) if res is not None else False
            return {
                "schema": SCHEMA_PAIRED_JOB,
                "series_id": self.series_id,
                "status": self.status,
                "base_ref": self.base_ref,
                "variant_ref": self.variant_ref,
                "base_deck_id": self.base_deck.deck_id,
                "variant_deck_id": self.variant_deck.deck_id,
                "pod": self.pod_name,
                "opponent_ids": list(self.opponent_ids) if self.opponent_ids is not None else None,
                "opponent_deck_ids": [deck.deck_id for deck in self.opponents],
                "budget_pairs": self.budget_pairs,
                "look_every_pairs": self.look_every_pairs,
                "tested_seats": list(self.tested_seats),
                "threshold_pp": self.threshold_pp,
                "significance_level": self.significance_level,
                "pairs_attempted": self.pairs_attempted,
                "games_played": len(self._games_played),
                "games_planned_max": 2 * self.budget_pairs,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "error": self.error,
                "estimate": self.estimate,
                "slot_alignment": self.slot_alignment,
                "seed_plan": self.seed_plan,
                "execution": self.execution_metadata(),
                "bridge_jar_sha256": bridge_shas[0]
                if len(bridge_shas) == 1
                else self.bridge_jar_sha256,
                "bridge_jar_sha256s": bridge_shas,
                "bridge_qualification_states": qual_states,
                "bridge_qualification": self.bridge_qualification,
                "covered_by_sealed_epoch": covered,
                "experiment": self.experiment,
                "result": res,
            }

    def run(self) -> None:
        self._write_lock()
        self._ensure_progress_newline()
        with self._lock:
            self.status = "running"
            self.started_at = now_utc()
            self.error = None
        self.persist()

        def _on_pair_done(count: int) -> None:
            with self._lock:
                self.pairs_attempted = max(self.pairs_attempted, count)
            self.persist()

        player = paired_comparison.parallel_window_player(
            self.data_folder,
            series_id=self.series_id,
            base_deck=self.base_deck,
            variant_deck=self.variant_deck,
            opponents=self.opponents,
            paths_by_deck_id=self.paths_by_deck_id,
            seeds=self.seeds,
            tested_seats=self.tested_seats,
            budget_pairs=self.budget_pairs,
            look_every_pairs=self.look_every_pairs,
            workers=self.workers,
            games_per_jvm=self.games_per_jvm,
            command=self.engine.command if self.engine is not None else None,
            play_single=self.play_override,
            is_cancelled=self.is_cancelled,
            on_pair_done=_on_pair_done,
            cancel_error_factory=lambda: SeriesCancelledError("Serie vom Benutzer abgebrochen"),
            preloaded=self.preloaded_games,
            on_game_result=self._append_game_result,
            on_game_played=self.mark_game_played,
        )

        try:
            result = paired_comparison.run_comparison_series(
                base_deck_id=self.base_deck.deck_id,
                variant_deck_id=self.variant_deck.deck_id,
                seeds=self.seeds,
                tested_seats=self.tested_seats,
                budget_pairs=self.budget_pairs,
                look_every_pairs=self.look_every_pairs,
                threshold_pp=self.threshold_pp,
                significance_level=self.significance_level,
                play=player,
                execution={
                    "series_id": self.series_id,
                    "command": "studio web paired-series",
                    "base_ref": self.base_ref,
                    "variant_ref": self.variant_ref,
                    "pod": self.pod_name,
                    "rotate_seats": len(self.tested_seats) > 1,
                    "look_every_pairs": self.look_every_pairs,
                    "budget_pairs": self.budget_pairs,
                    "games_dir": str(games_folder(self.data_folder)),
                    "slot_alignment": self.slot_alignment,
                    "seed_plan": self.seed_plan,
                    **self.execution_metadata(),
                },
            )
            pool_summary = player.pool_summary()
            if pool_summary is not None:
                result["execution"] = {**result["execution"], "pool": pool_summary}
            with self._lock:
                self.result = result
                self.pairs_attempted = int(result.get("pairs_played") or self.pairs_attempted)
                self.status = "completed"
                self.ended_at = now_utc()
        except SeriesCancelledError as exc:
            with self._lock:
                self.status = "cancelled"
                self.error = str(exc)
                self.ended_at = now_utc()
        except Exception as exc:
            with self._lock:
                self.status = "failed"
                self.error = str(exc)
                self.ended_at = now_utc()
        finally:
            player.close()  # the worker processes and their bridge JVMs end with the series
            self._release_lock()
            self.persist()


class PairedSeriesManager:
    """Thread-safe registry for background paired overnight comparison jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, PairedSeriesJob] = {}
        self._seq = 0
        self._lock = threading.Lock()

    def start_series(
        self,
        store: StudioStore,
        data_folder: str | Path,
        *,
        base_revision_id: str,
        variant_revision_id: str,
        pod: str = "precon",
        opponent_ids: Sequence[str] | None = None,
        budget_pairs: int = 20,
        look_every_pairs: int = 4,
        base_seed: int = 1000,
        rotate_seats: bool = True,
        threshold_pp: float = paired_comparison.DEFAULT_THRESHOLD_PP,
        significance_level: float = paired_comparison.DEFAULT_SIGNIFICANCE_LEVEL,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        play_override: paired_comparison.PairPlayer | None = None,
        purpose: str = "unspecified",
        allow_unreleased_seats: bool = False,
        experiment: Mapping[str, object] | None = None,
        table_seats: int | None = None,
    ) -> PairedSeriesJob:
        data_path = Path(data_folder).resolve()
        if purpose not in SERIES_PURPOSES:
            raise ValueError(f"purpose muss eines von {', '.join(SERIES_PURPOSES)} sein")
        if base_revision_id.strip() == variant_revision_id.strip():
            raise ValueError("Basis und Variante müssen zwei verschiedene Stände sein")
        if (
            not paired_comparison.MIN_BUDGET_PAIRS
            <= budget_pairs
            <= paired_comparison.MAX_BUDGET_PAIRS
        ):
            raise ValueError(
                f"budget_pairs muss zwischen {paired_comparison.MIN_BUDGET_PAIRS} und "
                f"{paired_comparison.MAX_BUDGET_PAIRS} liegen"
            )
        if look_every_pairs < 1:
            raise ValueError("look_every_pairs muss mindestens 1 sein")
        if table_seats is not None:
            # the table size of the series (#1702): the lock first, then exactly N - 1 opponents
            if not MIN_SEATS <= table_seats <= MAX_SEATS:
                raise ValueError(
                    f"ein Tisch hat {MIN_SEATS} bis {MAX_SEATS} Sitze, nicht {table_seats}"
                )
            validate_released_seat_count(
                table_seats - 1, allow_unreleased_seats=allow_unreleased_seats
            )
            if opponent_ids is not None and len(opponent_ids) != table_seats - 1:
                raise ValueError(
                    f"ein Tisch mit {table_seats} Sitzen braucht {table_seats - 1} Gegner, "
                    f"angegeben sind {len(opponent_ids)}"
                )
        if opponent_ids is not None:
            validate_released_seat_count(
                len(opponent_ids), allow_unreleased_seats=allow_unreleased_seats
            )
        used_workers, used_batch = checked_series_settings(workers, games_per_jvm)

        engine: SeriesEngine | None = None
        if play_override is None:
            engine = series_engine(data_path, used_batch)
            if engine is None:
                state = engine_state(data_path)
                raise RuntimeError(str(state.get("reason") or "Engine ist nicht bereitgestellt"))

        base_snap = _snapshot_for_ref(store, base_revision_id.strip())
        variant_snap = _snapshot_for_ref(store, variant_revision_id.strip())
        _preflight_snapshot_cards("Basis-Deck", base_snap)
        _preflight_snapshot_cards("Varianten-Deck", variant_snap)

        if opponent_ids is None or not any(is_revision_ref(str(o)) for o in opponent_ids):
            # precons only: checked before anything is written
            _resolve_opponent_paths(
                pod,
                opponent_ids,
                allow_unreleased_seats=allow_unreleased_seats,
                table_seats=table_seats,
            )

        with self._lock:
            self._seq += 1
            seq = self._seq
        digest = hashlib.sha256(
            f"{base_revision_id}|{variant_revision_id}|{base_seed}|{seq}".encode()
        ).hexdigest()[:8]
        series_id = f"paired-{int(time.time())}-{seq}-{digest}"
        deck_dir = games_folder(data_path) / "paired_decks" / series_id
        base_path = _snapshot_file(deck_dir, "base", base_revision_id, base_snap)
        variant_path = _snapshot_file(deck_dir, "variant", variant_revision_id, variant_snap)

        base_deck = load_rules_deck_snapshot(base_path)
        variant_deck = load_rules_deck_snapshot(variant_path)
        if base_deck.deck_id == variant_deck.deck_id:
            # Paired exposures match on RulesDeckInput.deck_id; distinguish base vs variant cleanly
            base_snap["deck_id"] = f"{base_deck.deck_id}--base"
            variant_snap["deck_id"] = f"{variant_deck.deck_id}--variant"
            base_path = _snapshot_file(deck_dir, "base", base_revision_id, base_snap)
            variant_path = _snapshot_file(deck_dir, "variant", variant_revision_id, variant_snap)
            base_deck = load_rules_deck_snapshot(base_path)
            variant_deck = load_rules_deck_snapshot(variant_path)
        variant_deck, alignment = _align_variant_file(
            base_deck, variant_deck, variant_snap, variant_path
        )
        opp_paths = _table_opponent_paths(
            store,
            deck_dir,
            pod,
            opponent_ids,
            {base_deck.deck_id, variant_deck.deck_id},
            table_seats,
        )
        opponents = [load_rules_deck_snapshot(p) for p in opp_paths]

        paths_by_deck_id: dict[str, Path] = {
            base_deck.deck_id: base_path,
            variant_deck.deck_id: variant_path,
        }
        for deck, path in zip(opponents, opp_paths, strict=True):
            paths_by_deck_id[deck.deck_id] = path

        table_size = 1 + len(opponents)
        tested_seats = list(range(table_size)) if rotate_seats else [0]
        needed_seeds = -(-budget_pairs // len(tested_seats))
        seeds = [int(base_seed) + i for i in range(needed_seeds)]

        jar_sha = (
            command_bridge_jar_sha256(data_path, engine.command) if engine is not None else None
        )
        job = PairedSeriesJob(
            series_id=series_id,
            data_folder=data_path,
            base_ref=base_revision_id,
            variant_ref=variant_revision_id,
            base_deck=base_deck,
            variant_deck=variant_deck,
            opponents=opponents,
            paths_by_deck_id=paths_by_deck_id,
            pod_name=pod,
            seeds=seeds,
            tested_seats=tested_seats,
            budget_pairs=budget_pairs,
            look_every_pairs=look_every_pairs,
            threshold_pp=threshold_pp,
            significance_level=significance_level,
            play_override=play_override,
            workers=used_workers,
            games_per_jvm=used_batch,
            engine=engine,
            bridge_sha=jar_sha,
            qualification=bridge_qualification(),
            slot_alignment=alignment,
            purpose=purpose,
            player_count=table_size,
            opponent_ids=opponent_ids,
            experiment=experiment,
        )
        job.persist()
        with self._lock:
            self._jobs[series_id] = job

        thread = threading.Thread(target=job.run, daemon=True)
        thread.start()
        return job

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if sys.platform == "win32":
            import ctypes

            win_dll = getattr(ctypes, "WinDLL", None)
            if win_dll is None:
                return False
            k32 = win_dll("kernel32", use_last_error=True)
            k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
            k32.GetExitCodeProcess.restype = ctypes.c_int
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            k32.CloseHandle.restype = ctypes.c_int
            process_query_limited_info = 0x1000
            still_active = 259
            handle = k32.OpenProcess(process_query_limited_info, 0, pid)
            if not handle:
                return ctypes.get_last_error() == 5
            try:
                exit_code = ctypes.c_uint32()
                ok = k32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                return bool(ok) and exit_code.value == still_active
            finally:
                k32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @classmethod
    def _is_lock_alive(cls, lock_path: Path) -> bool:
        if not lock_path.is_file():
            return False
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(data, dict):
            return False
        pid = data.get("pid")
        if type(pid) is not int or pid <= 0:
            return False
        return cls._is_pid_alive(pid)

    @classmethod
    def _is_disk_resumable(cls, raw: dict[str, object], target_folder: Path | None = None) -> bool:
        opp_deck_ids = raw.get("opponent_deck_ids")
        if (
            not isinstance(opp_deck_ids, list)
            or not opp_deck_ids
            or not all(isinstance(x, str) and x for x in opp_deck_ids)
        ):
            return False
        seed_plan = raw.get("seed_plan")
        if not isinstance(seed_plan, dict):
            return False
        if type(seed_plan.get("first_seed")) is not int:
            return False
        seeds_planned = seed_plan.get("seeds_planned")
        if type(seeds_planned) is not int or seeds_planned < 1:
            return False
        tested_seats = raw.get("tested_seats")
        if (
            not isinstance(tested_seats, list)
            or not tested_seats
            or not all(type(s) is int for s in tested_seats)
        ):
            return False
        budget_pairs = raw.get("budget_pairs")
        if type(budget_pairs) is not int or budget_pairs < 1:
            return False
        threshold_pp = raw.get("threshold_pp")
        if not isinstance(threshold_pp, (int, float)) or isinstance(threshold_pp, bool):
            return False
        err = raw.get("error")
        if isinstance(err, str) and (
            "mixed " in err or "abweichen" in err or "nicht fortsetzbar" in err
        ):
            return False
        if target_folder is not None and isinstance(raw.get("series_id"), str):
            sid = str(raw["series_id"])
            deck_dir = games_folder(target_folder) / "paired_decks" / sid
            if not list(deck_dir.glob("base-*.json")) or not list(deck_dir.glob("variant-*.json")):
                return False
        return True

    @classmethod
    def _normalize_disk_series(
        cls, raw: dict[str, object], target_folder: Path | None = None
    ) -> dict[str, object]:
        out = dict(raw)
        status = out.get("status")
        if status in {"running", "pending"}:
            sid = out.get("series_id")
            if (
                target_folder is not None
                and isinstance(sid, str)
                and cls._is_lock_alive(
                    games_folder(target_folder) / "paired_decks" / sid / "running.lock"
                )
            ):
                out["status"] = "running"
                out["resumable"] = False
            else:
                out["status"] = "interrupted"
                out["resumable"] = cls._is_disk_resumable(out, target_folder)
        elif status in {"cancelled", "failed"}:
            out["resumable"] = cls._is_disk_resumable(out, target_folder)
        else:
            out["resumable"] = False
        return out

    @staticmethod
    def _load_progress_jsonl(
        path: Path,
    ) -> dict[tuple[str, int, int], paired_comparison.PlayedGame]:
        loaded: dict[tuple[str, int, int], paired_comparison.PlayedGame] = {}
        if not path.is_file():
            return loaded
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if text and not text.endswith("\n") and lines:
            lines = lines[:-1]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            arm = rec.get("arm")
            seed = rec.get("seed")
            seat = rec.get("seat")
            played = rec.get("played")
            if (
                isinstance(arm, str)
                and type(seed) is int
                and type(seat) is int
                and isinstance(played, dict)
            ):
                loaded[(arm, seed, seat)] = played  # type: ignore[assignment]
        return loaded

    def resume_series(
        self,
        data_folder: str | Path,
        series_id: str,
        *,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        play_override: paired_comparison.PairPlayer | None = None,
    ) -> PairedSeriesJob:
        safe_id = validate_series_id(series_id)
        target_folder = Path(data_folder).resolve()
        with self._lock:
            existing = self._jobs.get(safe_id)
            if existing is not None and existing.status in {"pending", "running"}:
                raise RuntimeError(f"Serie {safe_id} läuft bereits (status={existing.status})")

            deck_dir = games_folder(target_folder) / "paired_decks" / safe_id
            if self._is_lock_alive(deck_dir / "running.lock"):
                raise RuntimeError(
                    f"Serie {safe_id} läuft bereits in einem aktiven Prozess (running.lock)"
                )

            disk = games_folder(target_folder) / f"{safe_id}.paired.json"
            if not disk.is_file():
                raise FileNotFoundError(f"Unbekannte Serie: {safe_id}")
            raw = json.loads(disk.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError(f"Ungültige Serien-Datei: {safe_id}")
            if raw.get("status") == "completed":
                raise RuntimeError(f"Serie {safe_id} ist bereits abgeschlossen")

            base_files = sorted(deck_dir.glob("base-*.json"))
            variant_files = sorted(deck_dir.glob("variant-*.json"))
            if not base_files or not variant_files:
                raise FileNotFoundError(f"Deck-Snapshots für Serie {safe_id} fehlen")
            base_path = base_files[0]
            variant_path = variant_files[0]
            base_deck = load_rules_deck_snapshot(base_path)
            variant_deck = load_rules_deck_snapshot(variant_path)

            pod_raw = raw.get("pod")
            if not isinstance(pod_raw, str) or not pod_raw:
                raise ValueError(f"pod fehlt in Serie {safe_id} (nicht fortsetzbar)")
            pod = pod_raw
            raw_opp_ids = raw.get("opponent_ids")
            if raw_opp_ids is not None and (
                not isinstance(raw_opp_ids, list)
                or not all(isinstance(x, str) and x for x in raw_opp_ids)
            ):
                raise ValueError(f"Ungültige opponent_ids in Serie {safe_id} (nicht fortsetzbar)")
            opp_ids = list(raw_opp_ids) if isinstance(raw_opp_ids, list) else None
            raw_opp_deck_ids = raw.get("opponent_deck_ids")
            # a preset series is resumed at its own table size (#1702), never at the default 4
            resume_seats = (
                1 + len(raw_opp_deck_ids)
                if opp_ids is None and isinstance(raw_opp_deck_ids, list) and raw_opp_deck_ids
                else None
            )
            opp_paths = _table_opponent_paths(
                None,
                deck_dir,
                pod,
                opp_ids,
                {base_deck.deck_id, variant_deck.deck_id},
                resume_seats,
            )
            opponents = [load_rules_deck_snapshot(path) for path in opp_paths]

            if (
                not isinstance(raw_opp_deck_ids, list)
                or not raw_opp_deck_ids
                or not all(isinstance(x, str) and x for x in raw_opp_deck_ids)
            ):
                raise ValueError(
                    f"opponent_deck_ids fehlt in Serie {safe_id} "
                    "(Alt-Serie ohne Gegner-Bindung, nicht fortsetzbar)"
                )
            if [d.deck_id for d in opponents] != [str(x) for x in raw_opp_deck_ids]:
                raise ValueError(
                    f"Gegner-Deck-IDs in Serie {safe_id} weichen ab (nicht fortsetzbar)"
                )

            seed_plan = raw.get("seed_plan")
            if not isinstance(seed_plan, dict):
                raise ValueError(f"seed_plan fehlt in Serie {safe_id} (nicht fortsetzbar)")
            first_seed = seed_plan.get("first_seed")
            seeds_planned = seed_plan.get("seeds_planned")
            if type(first_seed) is not int or type(seeds_planned) is not int or seeds_planned < 1:
                raise ValueError(f"Ungültiger seed_plan in Serie {safe_id} (nicht fortsetzbar)")
            plan_players = seed_plan.get("player_count")
            if type(plan_players) is int and plan_players != 1 + len(opponents):
                raise ValueError(
                    f"Sitzanzahl ({1 + len(opponents)}) weicht vom seed_plan "
                    f"({plan_players}) ab (nicht fortsetzbar)"
                )
            seeds = [first_seed + i for i in range(seeds_planned)]

            tested_seats_raw = raw.get("tested_seats")
            if (
                not isinstance(tested_seats_raw, list)
                or not tested_seats_raw
                or not all(type(s) is int for s in tested_seats_raw)
            ):
                raise ValueError(f"tested_seats fehlt in Serie {safe_id} (nicht fortsetzbar)")
            tested_seats = list(tested_seats_raw)

            budget_pairs = raw.get("budget_pairs")
            if type(budget_pairs) is not int or budget_pairs < 1:
                raise ValueError(f"budget_pairs fehlt in Serie {safe_id} (nicht fortsetzbar)")
            look_every_pairs = raw.get("look_every_pairs")
            if type(look_every_pairs) is not int or look_every_pairs < 1:
                raise ValueError(f"look_every_pairs fehlt in Serie {safe_id} (nicht fortsetzbar)")
            threshold_raw = raw.get("threshold_pp")
            if not isinstance(threshold_raw, (int, float)) or isinstance(threshold_raw, bool):
                raise ValueError(f"threshold_pp fehlt in Serie {safe_id} (nicht fortsetzbar)")
            threshold_pp = float(threshold_raw)
            sig_raw = raw.get("significance_level")
            if not isinstance(sig_raw, (int, float)) or isinstance(sig_raw, bool):
                raise ValueError(f"significance_level fehlt in Serie {safe_id} (nicht fortsetzbar)")
            significance_level = float(sig_raw)

            paths_by_deck_id: dict[str, Path] = {
                base_deck.deck_id: base_path,
                variant_deck.deck_id: variant_path,
            }
            for deck, path in zip(opponents, opp_paths, strict=True):
                paths_by_deck_id[deck.deck_id] = path

            raw_exec = raw.get("execution")
            exec_meta = raw_exec if isinstance(raw_exec, dict) else {}
            used_workers, used_batch = checked_series_settings(
                workers if workers is not None else exec_meta.get("workers"),
                games_per_jvm if games_per_jvm is not None else exec_meta.get("games_per_jvm"),
            )

            engine: SeriesEngine | None = None
            if play_override is None:
                engine = series_engine(target_folder, used_batch)
                if engine is None:
                    state = engine_state(target_folder)
                    raise RuntimeError(
                        str(state.get("reason") or "Engine ist nicht bereitgestellt")
                    )
            jar_sha = (
                command_bridge_jar_sha256(target_folder, engine.command)
                if engine is not None
                else (str(raw["bridge_jar_sha256"]) if raw.get("bridge_jar_sha256") else None)
            )
            recorded_sha = raw.get("bridge_jar_sha256")
            if (
                isinstance(recorded_sha, str)
                and recorded_sha
                and jar_sha is not None
                and recorded_sha != jar_sha
            ):
                raise ValueError(
                    f"Bridge-JAR-SHA weicht ab ({recorded_sha[:12]} != {jar_sha[:12]}, "
                    "nicht fortsetzbar)"
                )

            raw_alignment = (
                raw.get("slot_alignment") if isinstance(raw.get("slot_alignment"), dict) else None
            )
            preloaded = self._load_progress_jsonl(deck_dir / "progress.jsonl")
            if play_override is None:  # games the engine played, not stand-ins of a test
                stale = pilot_change_message(preloaded, f"fp:{header_pilot_fingerprint()}")
                if stale is not None:
                    raise ValueError(stale)

            job = PairedSeriesJob(
                series_id=safe_id,
                data_folder=target_folder,
                base_ref=str(raw.get("base_ref") or base_deck.deck_id),
                variant_ref=str(raw.get("variant_ref") or variant_deck.deck_id),
                base_deck=base_deck,
                variant_deck=variant_deck,
                opponents=opponents,
                paths_by_deck_id=paths_by_deck_id,
                pod_name=pod,
                seeds=seeds,
                tested_seats=tested_seats,
                budget_pairs=budget_pairs,
                look_every_pairs=look_every_pairs,
                threshold_pp=threshold_pp,
                significance_level=significance_level,
                play_override=play_override,
                workers=used_workers,
                games_per_jvm=used_batch,
                engine=engine,
                bridge_sha=jar_sha,
                qualification=bridge_qualification(),
                raw_slot_alignment=raw_alignment,
                purpose=str(seed_plan.get("purpose") or "unspecified"),
                player_count=1 + len(opponents),
                opponent_ids=opp_ids,
                created_at=str(raw.get("created_at")) if raw.get("created_at") else None,
                preloaded_games=preloaded,
                experiment=raw_exp if isinstance(raw_exp := raw.get("experiment"), dict) else None,
            )
            job.persist()
            job._write_lock()
            self._jobs[safe_id] = job

        thread = threading.Thread(target=job.run, daemon=True)
        try:
            thread.start()
        except Exception:
            job._release_lock()
            raise
        return job

    def get_series(self, data_folder: str | Path, series_id: str) -> dict[str, object] | None:
        safe_id = validate_series_id(series_id)
        target_folder = Path(data_folder).resolve()
        with self._lock:
            job = self._jobs.get(safe_id)
        if job is not None and job.data_folder == target_folder:
            return job.to_dict()
        disk = games_folder(target_folder) / f"{safe_id}.paired.json"
        if disk.is_file():
            try:
                raw = json.loads(disk.read_text(encoding="utf-8"))
            except ValueError:
                return None
            if isinstance(raw, dict):
                return self._normalize_disk_series(raw, target_folder)
        return None

    def get_job(self, series_id: str) -> PairedSeriesJob | None:
        """The running (or finished) job of this process, if it started here."""
        with self._lock:
            return self._jobs.get(validate_series_id(series_id))

    def cancel_series(self, series_id: str) -> bool:
        safe_id = validate_series_id(series_id)
        with self._lock:
            job = self._jobs.get(safe_id)
        if job is None:
            return False
        job.cancel()
        return True

    def list_series(self, data_folder: str | Path) -> list[dict[str, object]]:
        target_folder = Path(data_folder).resolve()
        folder = games_folder(target_folder)
        by_id: dict[str, dict[str, object]] = {}
        if folder.is_dir():
            for path in sorted(folder.glob("paired-*.paired.json"), reverse=True)[:30]:
                with contextlib.suppress(OSError, ValueError):
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict) and isinstance(raw.get("series_id"), str):
                        by_id[str(raw["series_id"])] = self._normalize_disk_series(
                            raw, target_folder
                        )
        with self._lock:
            for sid, job in self._jobs.items():
                if job.data_folder == target_folder:
                    by_id[sid] = job.to_dict()
        items = list(by_id.values())
        items.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        return items[:30]


paired_series_manager = PairedSeriesManager()


def simulator_readiness_audit(
    store: StudioStore,
    commander_names: Sequence[str],
    *,
    cards: Sequence[RevisionCard] | None = None,
    tiers: Sequence[str] = ("S", "A"),
    available_check: Callable[[], bool] | None = None,
    status_lookup: Callable[[str], str] | None = None,
    pilot_known: Callable[[str], bool] | None = None,
) -> dict[str, object]:
    """Audit XMage engine & pilot readiness for the deck and its free Tier-S/A pool candidates (C-3).

    Fails closed to ``status = "UNKNOWN"`` when card catalogs are unreadable (never reports
    fake readiness). Never mutates scores or tiers.
    """
    check_avail = available_check or builder.sim_readiness_available
    get_status = status_lookup or builder.sim_readiness_status
    has_pilot = pilot_known or (lambda n: card_facts(n) is not None)

    if not commander_names:
        raise ValueError("commander is required")

    def _unknown_result(reason: str) -> dict[str, object]:
        return {
            "schema": SCHEMA_READINESS_AUDIT,
            "commander": list(commander_names),
            "available": False,
            "status": "UNKNOWN",
            "reason": reason,
            "deck": {"total": 0, "ready": None, "issues": []},
            "free_top_candidates": {
                "tiers": list(tiers),
                "total": 0,
                "ready": None,
                "issues": [],
                "items": [],
            },
        }

    if not check_avail():
        return _unknown_result("XMage-/Piloten-Kartendaten sind nicht lesbar.")

    if pilot_known is None:
        try:
            card_facts("__readiness_probe__")
        except (CardCatalogError, OSError, ValueError):
            return _unknown_result("Piloten-Kartenwissen ist nicht lesbar.")

    # Resolve deck cards
    deck_rows: list[Mapping[str, object]] = []
    if cards is not None and len(cards) > 0:
        deck_rows = [dict(r) for r in decks.list_rows(store, cards)]
    else:
        for base in decks.baseline_decks_for_commander(commander_names):
            with contextlib.suppress(KeyError):
                baseline = resolve_repo_baseline_cards(store, str(base["revision_id"]))
                deck_rows = [dict(r) for r in decks.list_rows(store, baseline)]
                break

    deck_seen: dict[str, dict[str, object]] = {}
    deck_card_ids: set[str] = set()
    deck_card_names: set[str] = set()
    try:
        for row in deck_rows:
            cid = str(row.get("card_id") or "")
            if cid:
                deck_card_ids.add(cid)
            eng_name = str(row.get("engine_name") or "")
            ora_name = str(row.get("oracle_name") or "")
            if eng_name:
                deck_card_names.add(eng_name)
            if ora_name:
                deck_card_names.add(ora_name)
            name = eng_name or ora_name
            if not name or name in deck_seen:
                continue
            sim_st = get_status(name)
            pilot_ok = bool(has_pilot(name))
            ok = sim_st == "OK" and pilot_ok
            deck_seen[name] = {
                "card_id": row.get("card_id"),
                "name": name,
                "zone": row.get("zone", "main"),
                "sim_status": sim_st,
                "pilot_known": pilot_ok,
                "ready": ok,
            }
    except (CardCatalogError, OSError, ValueError):
        return _unknown_result(
            "XMage-/Piloten-Kartendaten konnten nicht vollständig gelesen werden."
        )

    deck_issues = [item for item in deck_seen.values() if not item["ready"]]
    deck_ready = len(deck_seen) - len(deck_issues)

    # Free Tier S/A pool candidates not currently in deck
    _identity, _cmd_ids = builder.commander_identity(store, commander_names)
    engine_name_by_id = {
        str(r["card_id"]): str(r["engine_name"] or r["oracle_name"] or "")
        for r in store.connection.execute("SELECT card_id, engine_name, oracle_name FROM card_fact")
    }
    role_rows = store.connection.execute(
        "SELECT card_id, roles FROM ("
        "SELECT c.card_id, GROUP_CONCAT(r.role, ',') AS roles "
        "FROM card c LEFT JOIN card_role r ON r.oracle_id = c.oracle_id "
        "GROUP BY c.card_id)"
    ).fetchall()
    roles_by_id: dict[str, list[str]] = {
        str(r["card_id"]): sorted(str(r["roles"]).split(",")) if r["roles"] else []
        for r in role_rows
    }
    inv_rows = {
        str(r["card_id"]): int(r["available_lower_bound"] or 0)
        for r in store.connection.execute("SELECT card_id, available_lower_bound FROM inventory")
    }

    tier_set = {str(t).upper() for t in tiers}
    strength_res = strength_view.compute(store, commander_names[0], StrengthSettings())
    candidate_items: list[dict[str, object]] = []
    try:
        for entry in strength_res.get("cards", []):
            tier = str(entry.get("tier") or "")
            if tier not in tier_set:
                continue
            cid = str(entry.get("card_id") or "")
            cname = str(entry.get("name") or "")
            lookup_name = engine_name_by_id.get(cid) or cname
            avail = inv_rows.get(cid, 0)
            if (
                avail <= 0
                or (cid and cid in deck_card_ids)
                or cname in deck_card_names
                or lookup_name in deck_card_names
            ):
                continue
            sim_st = get_status(lookup_name)
            pilot_ok = bool(has_pilot(lookup_name))
            ok = sim_st == "OK" and pilot_ok
            candidate_items.append(
                {
                    "card_id": cid,
                    "name": cname,
                    "tier": tier,
                    "index": entry.get("index"),
                    "roles": roles_by_id.get(cid, []),
                    "available": avail,
                    "sim_status": sim_st,
                    "pilot_known": pilot_ok,
                    "ready": ok,
                }
            )
    except (CardCatalogError, OSError, ValueError):
        return _unknown_result(
            "XMage-/Piloten-Kartendaten konnten nicht vollständig gelesen werden."
        )

    tier_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}

    def _cand_key(item: Mapping[str, object]) -> tuple[int, float, str]:
        idx = item.get("index")
        idx_val = float(idx) if isinstance(idx, (int, float)) else -1.0
        return (
            tier_order.get(str(item.get("tier") or ""), 9),
            -idx_val,
            str(item.get("name") or ""),
        )

    candidate_items.sort(key=_cand_key)
    cand_issues = [item for item in candidate_items if not item["ready"]]
    cand_ready = len(candidate_items) - len(cand_issues)

    overall_ok = len(deck_issues) == 0 and len(cand_issues) == 0
    return {
        "schema": SCHEMA_READINESS_AUDIT,
        "commander": list(commander_names),
        "available": True,
        "status": "OK" if overall_ok else "GAPS_FOUND",
        "deck": {
            "total": len(deck_seen),
            "ready": deck_ready,
            "issues": deck_issues,
        },
        "free_top_candidates": {
            "tiers": list(tiers),
            "total": len(candidate_items),
            "ready": cand_ready,
            "issues": cand_issues,
            "items": candidate_items,
        },
    }


__all__ = [
    "ESTIMATED_GAMES_PER_HOUR",
    "MEASURED_BATCH_GAMES_PER_HOUR",
    "SCHEMA_PAIRED_JOB",
    "SCHEMA_READINESS_AUDIT",
    "SERIES_PURPOSES",
    "THROUGHPUT_SOURCE",
    "PairedSeriesJob",
    "PairedSeriesManager",
    "estimate_series_duration",
    "paired_series_manager",
    "planned_detectable_difference_pp",
    "simulator_readiness_audit",
    "validate_series_id",
]
