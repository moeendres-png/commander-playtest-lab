"""Candidate 0 (baseline): mirrors current Structural executor semantics.

ProcessPoolExecutor.map with spawn context, no per-task timeout, no retry,
no resume, no manifest, no quarantine, no failure accounting: the first
worker exception aborts the whole batch (executor.map re-raises).
"""

from __future__ import annotations

import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor

from workload import synthetic_game


def _run_task(task: dict) -> dict:
    return synthetic_game(task["job_id"], task["seed"], attempt=0, scenario=task["scenario"])


def run_baseline(plan: list[dict], *, workers: int = 4) -> dict:
    started = time.perf_counter()
    first_result_at: float | None = None
    results: list[dict] = []
    error: str | None = None
    try:
        with ProcessPoolExecutor(
            max_workers=workers, mp_context=multiprocessing.get_context("spawn")
        ) as ex:
            for out in ex.map(_run_task, plan):
                if first_result_at is None:
                    first_result_at = time.perf_counter() - started
                results.append(out)
    except Exception as exc:  # noqa: BLE001 - baseline failure accounting is the point
        error = f"{type(exc).__name__}: {exc}"
    wall = time.perf_counter() - started
    return {
        "executor": "baseline-process-pool",
        "completed": len(results),
        "error": error,
        "aborted_batch": error is not None,
        "results": results,
        "wall_seconds": wall,
        "startup_overhead_seconds": first_result_at,
    }
