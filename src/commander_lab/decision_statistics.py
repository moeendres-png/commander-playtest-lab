from __future__ import annotations

import math
import random
from statistics import fmean, stdev
from typing import Iterable


def _values(values: Iterable[float]) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if not result:
        raise ValueError("at least one observation is required")
    return result


def percentile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(_values(values))
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between zero and one")
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def paired_bootstrap_interval(
    differences: Iterable[float],
    *,
    confidence: float = 0.95,
    resamples: int = 2000,
    seed: int = 20260807,
) -> tuple[float, float]:
    values = _values(differences)
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    if resamples < 100:
        raise ValueError("at least 100 bootstrap resamples are required")
    rng = random.Random(seed)
    means = [
        fmean(values[rng.randrange(len(values))] for _ in values)
        for _ in range(resamples)
    ]
    alpha = (1 - confidence) / 2
    return percentile(means, alpha), percentile(means, 1 - alpha)


def paired_standardized_effect(differences: Iterable[float]) -> float:
    values = _values(differences)
    if len(values) < 2:
        return 0.0
    deviation = stdev(values)
    if deviation == 0:
        return 0.0 if fmean(values) == 0 else math.copysign(math.sqrt(len(values)), fmean(values))
    return fmean(values) / deviation


def bayesian_shrunk_mean(
    differences: Iterable[float],
    *,
    prior_mean: float = 0.0,
    prior_strength: float = 20.0,
) -> float:
    values = _values(differences)
    if prior_strength < 0:
        raise ValueError("prior_strength cannot be negative")
    return (sum(values) + prior_mean * prior_strength) / (len(values) + prior_strength)


def distributionally_robust_lower_bound(
    differences: Iterable[float], *, radius: float = 0.5
) -> float:
    values = _values(differences)
    if radius < 0:
        raise ValueError("radius cannot be negative")
    spread = stdev(values) if len(values) > 1 else 0.0
    return fmean(values) - radius * spread


def holm_adjust(p_values: Iterable[float]) -> tuple[float, ...]:
    values = tuple(float(value) for value in p_values)
    if any(not 0.0 <= value <= 1.0 for value in values):
        raise ValueError("p-values must be between zero and one")
    count = len(values)
    ordered = sorted(enumerate(values), key=lambda row: row[1])
    adjusted = [0.0] * count
    running = 0.0
    for rank, (index, value) in enumerate(ordered):
        candidate = min(1.0, (count - rank) * value)
        running = max(running, candidate)
        adjusted[index] = running
    return tuple(adjusted)


def quantile_summary(values: Iterable[float]) -> dict[str, float]:
    data = _values(values)
    return {
        "minimum": min(data),
        "q10": percentile(data, 0.10),
        "q25": percentile(data, 0.25),
        "median": percentile(data, 0.50),
        "q75": percentile(data, 0.75),
        "q90": percentile(data, 0.90),
        "maximum": max(data),
        "mean": fmean(data),
    }
