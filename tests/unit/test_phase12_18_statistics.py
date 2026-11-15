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
