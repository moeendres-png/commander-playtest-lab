from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import fmean, pvariance
from typing import Any, Literal

from commander_lab.storage import sha256_value

ModelInformationStatus = Literal["INFORMATIVE", "MODEL_INFORMATION_LIMIT"]


@dataclass(frozen=True)
class ModelInformativenessReport:
    schema_version: str
    status: ModelInformationStatus
    recommended_action: str
    outcome_concentration: float | None
    ceiling_indication: bool
    placement_variance: float | None
    seat_dispersion: float | None
    lower_tail_available: bool
    failure_mode_diversity: int
    variant_count: int
    separable_variant_count: int
    overlapping_variant_count: int
    separable_ratio: float | None
    overlap_ratio: float | None
    opponent_evidence_quality: dict[str, int]
    synthetic_opponent_share: float | None
    metric_coverage: tuple[str, ...]
    triggered_indicators: tuple[str, ...]
    next_diagnostics: tuple[str, ...]
    evidence_class: str = "structural_model_diagnostic"
    truth_boundary: str = "model informativeness, not empirical deck power or winrate"

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def report_hash(self) -> str:
        return sha256_value(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {"report_hash": self.report_hash, **self.payload()}


def _float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _seat_shares(rows: object) -> tuple[float, ...]:
    if not isinstance(rows, dict):
        return ()
    values: list[float] = []
    for key in sorted(rows, key=str):
        row = rows[key]
        if isinstance(row, dict):
            value = _float(row.get("place_1_share"))
            if value is not None:
                values.append(value)
    return tuple(values)


def _interval(row: dict[str, Any]) -> tuple[float, float] | None:
    value = row.get("confidence_interval")
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    low = _float(value[0])
    high = _float(value[1])
    return (low, high) if low is not None and high is not None else None


def assess_model_informativeness(
    *,
    baseline_place_1_share: float | None,
    seat_results: dict[str, Any] | None,
    variant_comparisons: tuple[dict[str, Any], ...] = (),
    opponent_evidence_quality: dict[str, int] | None = None,
    failure_mode_metrics: tuple[str, ...] = (),
) -> ModelInformativenessReport:
    """Assess cohort separability using conjunctive structural indicators."""
    shares = _seat_shares(seat_results or {})
    concentration = _float(baseline_place_1_share)
    placement_variance = pvariance(shares) if len(shares) > 1 else None
    seat_dispersion = max(shares) - min(shares) if shares else None
    intervals = tuple(
        interval for row in variant_comparisons if (interval := _interval(row)) is not None
    )
    separable = sum(1 for low, high in intervals if low > 0.0 or high < 0.0)
    overlapping = sum(1 for low, high in intervals if low <= 0.0 <= high)
    separable_ratio = separable / len(intervals) if intervals else None
    overlap_ratio = overlapping / len(intervals) if intervals else None
    lower_tail_available = any(
        isinstance(row.get("lower_tail"), dict) for row in variant_comparisons
    )
    evidence = dict(sorted((opponent_evidence_quality or {}).items()))
    total_evidence = sum(max(0, value) for value in evidence.values())
    synthetic = sum(
        max(0, value)
        for key, value in evidence.items()
        if "synthetic" in key.casefold() or "inferred" in key.casefold()
    )
    synthetic_share = synthetic / total_evidence if total_evidence else None

    indicators: list[str] = []
    ceiling = concentration is not None and concentration >= 0.90
    if ceiling:
        indicators.append("outcome_concentration_near_ceiling")
    if shares and fmean(shares) >= 0.88 and (seat_dispersion or 0.0) <= 0.15:
        indicators.append("seat_rotation_remains_concentrated")
    if intervals and separable == 0:
        indicators.append("variant_intervals_not_separable")
    if (
        len(intervals) >= 8
        and overlap_ratio is not None
        and overlap_ratio >= 0.75
        and separable_ratio is not None
        and separable_ratio <= 0.10
    ):
        indicators.append("broad_cohort_mostly_nonseparable")
    if variant_comparisons and not failure_mode_metrics:
        indicators.append("decision_uses_no_explicit_failure_mode_metric")
    if synthetic_share is not None and synthetic_share >= 0.50:
        indicators.append("opponent_evidence_is_majority_synthetic_or_inferred")

    concentration_limit = ceiling and "seat_rotation_remains_concentrated" in indicators
    separability_limit = bool(intervals) and separable == 0
    evidence_limit = "opponent_evidence_is_majority_synthetic_or_inferred" in indicators
    broad_nonseparable = "broad_cohort_mostly_nonseparable" in indicators
    limited = (
        (concentration_limit and separability_limit)
        or (concentration_limit and evidence_limit)
        or (broad_nonseparable and not failure_mode_metrics)
    )
    status: ModelInformationStatus = "MODEL_INFORMATION_LIMIT" if limited else "INFORMATIVE"
    action = "DIAGNOSE_BEFORE_MORE_SEED_WORK" if limited else "COMPARISON_PERMITTED"
    diagnostics = (
        (
            "use existing continuous failure-mode metrics before adding seeds",
            "improve opponent profile or scenario evidence when scenario uncertainty is material",
            "test a narrower preregistered deckbuilding hypothesis if the cohort remains non-separable",
        )
        if limited
        else ("continue with preregistered paired comparisons and advancement gates",)
    )
    coverage = tuple(
        name
        for name, present in (
            ("outcome_concentration", concentration is not None),
            ("seat_dispersion", bool(shares)),
            ("placement_variance", placement_variance is not None),
            ("lower_tail", lower_tail_available),
            ("variant_interval_separability", bool(intervals)),
            ("failure_modes", bool(failure_mode_metrics)),
            ("opponent_evidence", bool(evidence)),
        )
        if present
    )
    return ModelInformativenessReport(
        schema_version="1.1.0",
        status=status,
        recommended_action=action,
        outcome_concentration=concentration,
        ceiling_indication=ceiling,
        placement_variance=placement_variance,
        seat_dispersion=seat_dispersion,
        lower_tail_available=lower_tail_available,
        failure_mode_diversity=len(set(failure_mode_metrics)),
        variant_count=len(variant_comparisons),
        separable_variant_count=separable,
        overlapping_variant_count=overlapping,
        separable_ratio=separable_ratio,
        overlap_ratio=overlap_ratio,
        opponent_evidence_quality=evidence,
        synthetic_opponent_share=synthetic_share,
        metric_coverage=coverage,
        triggered_indicators=tuple(indicators),
        next_diagnostics=diagnostics,
    )


__all__ = ["ModelInformativenessReport", "assess_model_informativeness"]
