from __future__ import annotations

from commander_lab.models import StructuralBatchConfig


def _config(*, iterations: int, workers: int) -> StructuralBatchConfig:
    return StructuralBatchConfig(
        run_id="audit-e-scheduler",
        seed=20260808,
        iterations=iterations,
        deck_ids=("a", "b", "c"),
        workers=workers,
    )
