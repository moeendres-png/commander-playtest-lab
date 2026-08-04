from __future__ import annotations

import pytest

from commander_lab.engine.structural import run_structural_batch
from commander_lab.models import StructuralAbortLimits, StructuralBatchConfig


@pytest.mark.integration
def test_batch_is_reproducible_across_worker_counts(structural_decks) -> None:
    common = dict(
        run_id="worker-repro",
        seed=20260804,
        iterations=8,
        deck_ids=("korvold/current", "rogshai/current", "synthetic/aggro"),
        limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=20),
    )
    serial = run_structural_batch(StructuralBatchConfig(**common, workers=1), structural_decks)
    parallel = run_structural_batch(StructuralBatchConfig(**common, workers=2), structural_decks)
    serial_key = [
        (item.seed, item.placements, item.winner_ids, item.turns, item.log_sha256, item.end_reason)
        for item in serial.match_results
    ]
    parallel_key = [
        (item.seed, item.placements, item.winner_ids, item.turns, item.log_sha256, item.end_reason)
        for item in parallel.match_results
    ]
    assert serial_key == parallel_key
    assert serial.aggregate == parallel.aggregate


@pytest.mark.integration
@pytest.mark.parametrize("pod_size", [1, 3, 4, 5])
def test_supported_validation_pod_sizes(pod_size, structural_decks) -> None:
    ordered = (
        "korvold/current",
        "rogshai/current",
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )
    result = run_structural_batch(
        StructuralBatchConfig(
            run_id=f"pod-{pod_size}",
            seed=101 + pod_size,
            iterations=2,
            deck_ids=ordered[:pod_size],
            workers=1,
            limits=StructuralAbortLimits(max_turns=35, max_events=30_000, max_no_progress_turns=20),
        ),
        structural_decks,
    )
    assert result.estimate_type == "structural_model_estimates"
    assert result.pod_size == pod_size
    assert result.completed_games + result.aborted_games == 2
