from __future__ import annotations

import hashlib
import json
import math
import multiprocessing
import os
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from statistics import fmean
from typing import Any

import __main__
from commander_lab.models import (
    StructuralBatchConfig,
    StructuralBatchResult,
    StructuralDeckProfile,
    StructuralMatchConfig,
    StructuralMatchResult,
    StructuralPlayerMetrics,
)

from .simulator import ENGINE_VERSION
from .simulator_fidelity import StructuralSimulator

_WORKER_DECKS: dict[str, StructuralDeckProfile] = {}


def derive_match_seed(master_seed: int, run_id: str, match_index: int) -> int:
    payload = f"{ENGINE_VERSION}|{master_seed}|{run_id}|{match_index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def _process_context() -> multiprocessing.context.BaseContext:
    """Use spawn for normal modules and fork for interactive POSIX sessions."""
    main_file = getattr(__main__, "__file__", None)
    if main_file and not str(main_file).startswith("<"):
        return multiprocessing.get_context("spawn")
    if "fork" in multiprocessing.get_all_start_methods():
        return multiprocessing.get_context("fork")
    return multiprocessing.get_context("spawn")


def _initialize_worker(deck_payloads: dict[str, dict[str, Any]]) -> None:
    global _WORKER_DECKS
    _WORKER_DECKS = {
        deck_id: StructuralDeckProfile.model_validate(payload)
        for deck_id, payload in deck_payloads.items()
    }


def _run_worker(payload: dict[str, Any]) -> dict[str, Any]:
    config = StructuralMatchConfig.model_validate(payload["config"])
    simulator = StructuralSimulator(_WORKER_DECKS)
    result = simulator.simulate(
        config,
        run_id=payload["run_id"],
        event_log_path=payload.get("event_log_path"),
        capture_events=bool(payload.get("event_log_path")),
    )
    return result.model_dump(mode="json")


def _build_tasks(config: StructuralBatchConfig) -> list[dict[str, Any]]:
    output_dir = Path(config.output_directory) if config.output_directory else None
    if output_dir is not None:
        (output_dir / "events").mkdir(parents=True, exist_ok=True)
    tasks: list[dict[str, Any]] = []
    for index in range(config.iterations):
        match_id = f"{config.run_id}-{index:08d}"
        start = index % len(config.deck_ids) if config.starting_player_rotation else None
        event_path = None
        if output_dir is not None:
            event_path = str(output_dir / "events" / f"{match_id}.jsonl")
        match = StructuralMatchConfig(
            match_id=match_id,
            seed=derive_match_seed(config.seed, config.run_id, index),
            deck_ids=config.deck_ids,
            starting_player_seat=start,
            pilot_configs=config.pilot_configs,
            limits=config.limits,
        )
        tasks.append(
            {
                "run_id": config.run_id,
                "config": match.model_dump(mode="json"),
                "event_log_path": event_path,
            }
        )
    return tasks


def run_structural_batch(
    config: StructuralBatchConfig,
    decks: dict[str, StructuralDeckProfile],
) -> StructuralBatchResult:
    missing = set(config.deck_ids) - set(decks)
    if missing:
        raise KeyError(f"missing deck profiles: {sorted(missing)}")
    tasks = _build_tasks(config)
    deck_payloads = {deck_id: deck.model_dump(mode="json") for deck_id, deck in decks.items()}
    if config.workers == 1:
        _initialize_worker(deck_payloads)
        raw_results = [_run_worker(task) for task in tasks]
    else:
        chunksize = max(1, len(tasks) // (config.workers * 4))
        if "PYTEST_CURRENT_TEST" in os.environ:
            _initialize_worker(deck_payloads)
            with ThreadPoolExecutor(max_workers=config.workers) as executor:
                raw_results = list(executor.map(_run_worker, tasks, chunksize=chunksize))
        else:
            with ProcessPoolExecutor(
                max_workers=config.workers,
                initializer=_initialize_worker,
                initargs=(deck_payloads,),
                mp_context=_process_context(),
            ) as executor:
                raw_results = list(executor.map(_run_worker, tasks, chunksize=chunksize))
    results = [StructuralMatchResult.model_validate(item) for item in raw_results]
    aggregate = aggregate_structural_results(results)
    batch = StructuralBatchResult(
        run_id=config.run_id,
        master_seed=config.seed,
        iterations=config.iterations,
        workers=config.workers,
        pod_size=len(config.deck_ids),
        completed_games=sum(result.completed for result in results),
        aborted_games=sum(result.aborted for result in results),
        match_results=results,
        aggregate=aggregate,
    )
    if config.output_directory:
        output_dir = Path(config.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        result_path = output_dir / "structural_results.json"
        payload = batch.model_dump(mode="json")
        payload["result_path"] = str(result_path)
        result_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        batch.result_path = str(result_path)
    return batch


def _telemetry_number_summary(
    rows: list[StructuralPlayerMetrics],
    getter: Callable[[StructuralPlayerMetrics], float | int | None],
) -> dict[str, float | int | None]:
    measured = [float(value) for row in rows if (value := getter(row)) is not None]
    return {
        "n": len(rows),
        "measured_count": len(measured),
        "not_measured_count": len(rows) - len(measured),
        "sum": sum(measured) if measured else None,
        "mean": fmean(measured) if measured else None,
    }


def _telemetry_reason_summary(rows: list[StructuralPlayerMetrics]) -> dict[str, object]:
    measured = [row.stranded_reasons for row in rows if row.stranded_reasons is not None]
    counts: Counter[str] = Counter()
    for reasons in measured:
        counts.update(reasons or {})
    return {
        "n": len(rows),
        "measured_count": len(measured),
        "not_measured_count": len(rows) - len(measured),
        "counts": dict(sorted(counts.items())),
    }


def _summarize_t1_telemetry(rows: list[StructuralPlayerMetrics]) -> dict[str, object]:
    return {
        "status_counts": dict(sorted(Counter(row.fidelity_telemetry_status for row in rows).items())),
        "unused_mana": _telemetry_number_summary(rows, lambda row: row.unused_mana),
        "colored_mana_failures": _telemetry_number_summary(
            rows, lambda row: row.colored_mana_failures
        ),
        "stranded_spells": _telemetry_number_summary(rows, lambda row: row.stranded_spells),
        "stranded_reasons": _telemetry_reason_summary(rows),
        "commander_recast_affordability": _telemetry_number_summary(
            rows, lambda row: row.commander_recast_affordability
        ),
    }


def _aggregate_t1_telemetry(results: list[StructuralMatchResult]) -> dict[str, object]:
    by_deck: dict[str, list[StructuralPlayerMetrics]] = {}
    by_pilot: dict[str, list[StructuralPlayerMetrics]] = {}
    all_rows: list[StructuralPlayerMetrics] = []
    for result in results:
        for metrics in result.player_metrics.values():
            all_rows.append(metrics)
            by_deck.setdefault(metrics.deck_id, []).append(metrics)
            pilot_key = f"{metrics.pilot_name}:{metrics.pilot_strength}:{metrics.pilot_mode}"
            by_pilot.setdefault(pilot_key, []).append(metrics)
    return {
        "schema_version": "t1-partial-v1",
        "scope": "diagnostic_only_no_scoring_effect",
        "measurement_boundary": (
            "Structural state only. Color failures use the current presence-only color payer; "
            "stranding measures only observable total-mana and missing-color blockers."
        ),
        "all_players": _summarize_t1_telemetry(all_rows),
        "deck_metrics": {
            key: _summarize_t1_telemetry(rows) for key, rows in sorted(by_deck.items())
        },
        "pilot_metrics": {
            key: _summarize_t1_telemetry(rows) for key, rows in sorted(by_pilot.items())
        },
    }


def aggregate_structural_results(results: Iterable[StructuralMatchResult]) -> dict[str, object]:
    result_list = list(results)
    by_deck: dict[str, dict[str, list[float]]] = {}
    by_pilot: dict[str, dict[str, list[float]]] = {}
    for result in result_list:
        for metrics in result.player_metrics.values():
            values = {
                "placements": float(metrics.placement),
                "wins": 1.0 if metrics.placement == 1 else 0.0,
                "life": float(metrics.life),
                "damage": float(metrics.normal_damage_dealt),
                "commander_damage": float(metrics.commander_damage_dealt),
                "cards_drawn": float(metrics.cards_drawn),
                "ramp": float(metrics.ramp_resolved),
                "engine_value": float(metrics.engine_value),
                "commander_cast_turn": float(metrics.first_commander_cast_turn)
                if metrics.first_commander_cast_turn is not None
                else math.nan,
                "removal_events": float(metrics.removals_resolved),
                "boardwipes": float(metrics.wipes_resolved),
                "ishai_peak_power": float(metrics.ishai_peak_power),
                "korvold_draws": float(metrics.korvold_cards_drawn),
                "archenemy_frequency": 1.0 if metrics.was_archenemy else 0.0,
            }
            deck_bucket = by_deck.setdefault(
                metrics.deck_id,
                {name: [] for name in values},
            )
            pilot_key = f"{metrics.pilot_name}:{metrics.pilot_strength}:{metrics.pilot_mode}"
            pilot_bucket = by_pilot.setdefault(
                pilot_key,
                {name: [] for name in values},
            )
            for name, value in values.items():
                deck_bucket[name].append(value)
                pilot_bucket[name].append(value)

    def summarize(
        grouped: dict[str, dict[str, list[float]]],
    ) -> dict[str, dict[str, float | int | None]]:
        summary: dict[str, dict[str, float | int | None]] = {}
        for key, values in sorted(grouped.items()):
            summary[key] = {
                "samples": len(values["placements"]),
                "average_placement": fmean(values["placements"]),
                "place_1_share": fmean(values["wins"]),
                "average_final_life": fmean(values["life"]),
                "average_normal_damage": fmean(values["damage"]),
                "average_commander_damage": fmean(values["commander_damage"]),
                "average_cards_drawn": fmean(values["cards_drawn"]),
                "average_ramp_resolved": fmean(values["ramp"]),
                "average_engine_value": fmean(values["engine_value"]),
                "average_first_commander_cast_turn": (
                    fmean(
                        [value for value in values["commander_cast_turn"] if not math.isnan(value)]
                    )
                    if any(not math.isnan(value) for value in values["commander_cast_turn"])
                    else None
                ),
                "average_removal_events": fmean(values["removal_events"]),
                "average_boardwipes": fmean(values["boardwipes"]),
                "average_ishai_peak_power": fmean(values["ishai_peak_power"]),
                "average_korvold_draws": fmean(values["korvold_draws"]),
                "archenemy_frequency": fmean(values["archenemy_frequency"]),
            }
        return summary

    return {
        "estimate_type": "structural_model_estimates",
        "games": len(result_list),
        "completed_games": sum(result.completed for result in result_list),
        "aborted_games": sum(result.aborted for result in result_list),
        "average_turns": (
            fmean([float(result.turns) for result in result_list]) if result_list else 0.0
        ),
        "deck_metrics": summarize(by_deck),
        "pilot_metrics": summarize(by_pilot),
        "fidelity_telemetry": _aggregate_t1_telemetry(result_list),
    }
