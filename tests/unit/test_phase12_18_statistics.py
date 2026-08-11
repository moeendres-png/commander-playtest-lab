from __future__ import annotations

from pathlib import Path

from commander_lab.decision_statistics import (
    bayesian_shrunk_mean,
    distributionally_robust_lower_bound,
    holm_adjust,
    paired_bootstrap_interval,
    paired_standardized_effect,
    quantile_summary,
)
from commander_lab.models import PairedVariantInput, VariantSwap
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_deterministic_paired_statistics_and_multiple_testing() -> None:
    values = (1.0, 0.0, -1.0, 1.0, 0.0)
    first = paired_bootstrap_interval(values, seed=7, resamples=500)
    second = paired_bootstrap_interval(values, seed=7, resamples=500)
    assert first == second
    assert first[0] <= sum(values) / len(values) <= first[1]
    assert paired_standardized_effect(values) > 0
    assert abs(bayesian_shrunk_mean(values)) < abs(sum(values) / len(values))
    assert distributionally_robust_lower_bound(values) <= sum(values) / len(values)
    adjusted = holm_adjust((0.01, 0.04, 0.20))
    assert adjusted == (0.03, 0.08, 0.2)
    summary = quantile_summary(values)
    assert summary["minimum"] == -1.0
    assert summary["maximum"] == 1.0


def test_every_paired_comparison_exposes_required_protocol_fields() -> None:
    service = CommanderToolService(ROOT)
    response = service.compare_variants_paired(
        PairedVariantInput(
            deck_id="rogshai/current",
            swaps=(VariantSwap(remove="Consider", add_candidate_id="rogshai/opt-smoke"),),
            iterations=3,
            workers=1,
            seed=123,
        )
    )
    assert response.status.value == "completed"
    metrics = response.result["comparison"]
    required = {
        "requested_runs",
        "started_runs",
        "valid_runs",
        "failed_runs",
        "discarded_runs",
        "actual_sample_size",
        "seeds",
        "worker_count",
        "validation_level",
        "paired_or_unpaired",
        "effect_size",
        "confidence_interval",
        "bootstrap_method",
        "holdout_definition",
        "worst_case_result",
        "scenario_weights",
        "pilot_weights",
        "multiple_testing_method",
        "rounding_policy",
    }
    assert required <= set(metrics)
    assert metrics["requested_runs"] == metrics["actual_sample_size"] == 3
    assert metrics["validation_level"] == "structural_only"
    assert metrics["paired_or_unpaired"] == "paired"
