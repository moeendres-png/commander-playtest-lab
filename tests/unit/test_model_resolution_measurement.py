from __future__ import annotations

import pytest

from commander_lab.model_resolution_measurement import (
    ModelResolutionMeasurementProtocol,
    summarize_resolution_measurements,
)


def _observations() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    placements = (1.0, 2.0, 3.0, 4.0, 2.0, 3.0, 1.0, 4.0)
    for index, placement in enumerate(placements):
        rows.append(
            {
                "baseline_placement": placement,
                "baseline_place_1": float(placement == 1.0),
                "own_seat": (index % 4) + 1,
                "opponent_deck_ids": [
                    f"opponent/{index % 3}",
                    f"opponent/{(index + 1) % 3}",
                    f"opponent/{(index + 2) % 3}",
                ],
            }
        )
    return tuple(rows)


def test_protocol_requires_multiple_independent_seed_blocks() -> None:
    with pytest.raises(ValueError, match="at least three"):
        ModelResolutionMeasurementProtocol(independent_seed_blocks=2)


def test_seed_block_range_sets_sampling_resolution() -> None:
    report = summarize_resolution_measurements(
        block_means=(2.20, 2.25, 2.18, 2.24),
        observations=_observations(),
        pilot_means={"strong": 2.30, "average": 2.45},
        calibrated_sesoi=0.05,
    )
    assert report["status"] == "MEASURED"
    assert report["effective_resolution"] == pytest.approx(0.07)
    sampling = report["sampling_resolution"]
    assert isinstance(sampling, dict)
    assert sampling["epistemic_class"] == "PRECISION_ONLY_SAME_MODEL"


def test_robustness_spreads_are_not_folded_into_effective_resolution() -> None:
    report = summarize_resolution_measurements(
        block_means=(2.20, 2.21, 2.19, 2.20),
        observations=_observations(),
        pilot_means={"strong": 1.50, "average": 3.50},
        calibrated_sesoi=0.05,
    )
    assert report["effective_resolution"] == pytest.approx(0.05)
    robustness = report["robustness_axis_spreads"]
    assert isinstance(robustness, dict)
    assert robustness["pilot_policy"] == pytest.approx(2.0)


def test_compression_is_diagnostic_not_an_invented_numeric_penalty() -> None:
    observations = tuple(
        {
            "baseline_placement": 1.0,
            "baseline_place_1": 1.0,
            "own_seat": (index % 4) + 1,
            "opponent_deck_ids": ["a", "b", "c"],
        }
        for index in range(20)
    )
    report = summarize_resolution_measurements(
        block_means=(1.0, 1.0, 1.0),
        observations=observations,
        pilot_means={"strong": 1.0, "average": 1.0},
        calibrated_sesoi=0.05,
    )
    compression = report["outcome_compression"]
    assert isinstance(compression, dict)
    assert compression["status"] == "MODEL_INFORMATION_LIMIT"
    assert compression["folded_into_effective_resolution"] is False
    unsupported = report["unsupported_same_metric_axes"]
    assert isinstance(unsupported, dict)
    assert "no arbitrary" in str(unsupported["tie_quantization"])


def test_seed_range_larger_than_sesoi_is_conservatively_retained() -> None:
    report = summarize_resolution_measurements(
        block_means=(2.0, 2.20, 2.10),
        observations=_observations(),
        pilot_means={"strong": 2.0, "average": 2.0},
        calibrated_sesoi=0.05,
    )
    assert report["effective_resolution"] == pytest.approx(0.20)
