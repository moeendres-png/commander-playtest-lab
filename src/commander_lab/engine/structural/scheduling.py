from __future__ import annotations

import os

from commander_lab.models import (
    StructuralBatchConfig,
    StructuralBatchResult,
    StructuralDeckProfile,
)

from .batch import run_structural_batch as _run_structural_batch_raw

_MIN_GAMES_PER_PROCESS_WORKER = 32


def effective_worker_count(config: StructuralBatchConfig, *, cpu_count: int | None = None) -> int:
    """Choose a process count only when the batch has enough measured work to amortize startup."""
    if config.workers == 1:
        return 1
    available_cpus = max(1, cpu_count if cpu_count is not None else (os.cpu_count() or 1))
    candidate = min(config.workers, available_cpus, config.iterations)
    if candidate <= 1:
        return 1
    if config.iterations < candidate * _MIN_GAMES_PER_PROCESS_WORKER:
        return 1
    return candidate


def run_structural_batch(
    config: StructuralBatchConfig,
    decks: dict[str, StructuralDeckProfile],
) -> StructuralBatchResult:
    """Run a structural batch with an evidence-based small-workload serial fallback."""
    effective_workers = effective_worker_count(config)
    if effective_workers == config.workers:
        return _run_structural_batch_raw(config, decks)

    scheduled = config.model_copy(update={"workers": effective_workers})
    result = _run_structural_batch_raw(scheduled, decks)
    return result.model_copy(update={"workers": config.workers})
