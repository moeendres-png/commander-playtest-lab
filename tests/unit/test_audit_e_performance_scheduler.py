from __future__ import annotations

import pytest

from commander_lab.engine.structural.scheduling import effective_worker_count, run_structural_batch
from commander_lab.models import StructuralBatchConfig


def _config(*, iterations: int, workers: int) -> StructuralBatchConfig:
    return StructuralBatchConfig(
        run_id="audit-e-scheduler",
        seed=20260808,
        iterations=iterations,
        deck_ids=("a", "b", "c"),
        workers=workers,
    )


def test_small_batches_avoid_measured_process_startup_overhead() -> None:
    assert effective_worker_count(_config(iterations=32, workers=2), cpu_count=2) == 1
    assert effective_worker_count(_config(iterations=32, workers=4), cpu_count=2) == 1


def test_single_worker_path_is_never_changed() -> None:
    assert effective_worker_count(_config(iterations=1, workers=1), cpu_count=64) == 1
    assert effective_worker_count(_config(iterations=10_000, workers=1), cpu_count=64) == 1


def test_parallelism_is_capped_by_available_cpus_and_requires_enough_work() -> None:
    assert effective_worker_count(_config(iterations=128, workers=4), cpu_count=2) == 2
    assert effective_worker_count(_config(iterations=63, workers=2), cpu_count=2) == 1
    assert effective_worker_count(_config(iterations=64, workers=2), cpu_count=2) == 2


def test_scheduler_propagates_failures_without_hiding_them(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(iterations=32, workers=2)

    def fail(_config: StructuralBatchConfig, _decks: object) -> object:
        assert _config.workers == 1
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(
        "commander_lab.engine.structural.scheduling._run_structural_batch_raw",
        fail,
    )
    with pytest.raises(RuntimeError, match="synthetic failure"):
        run_structural_batch(config, {})
