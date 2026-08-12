from __future__ import annotations

import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old[:100]!r}")
    write(path, content.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    content = read(path)
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: regex expected exactly one match, got {count}: {pattern[:100]!r}")
    write(path, updated)


CUT_FRONTIER = r'''
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from math import fsum
from typing import Any, Mapping

from commander_lab.models import CandidateProfile, StructuralDeckProfile
from commander_lab.optimization import profile_score

_CRITICAL_ROLES = frozenset(
    {"graveyard_hate", "removal", "counter", "protection", "wipe", "recursion", "rebuild"}
)


@dataclass(frozen=True, slots=True)
class CutHypothesis:
    oracle_name: str
    lanes: tuple[str, ...]
    roles: tuple[str, ...]
    unique_roles: tuple[str, ...]
    package_ids: tuple[str, ...]
    singleton_package_ids: tuple[str, ...]
    mana_value: float
    commander_synergy: float
    redundancy_units: int
    structural_challenge_priority: float
    rationale: tuple[str, ...]
    truth_boundary: str = "cut hypothesis for exploration, not empirical card weakness"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_cut_hypotheses(
    deck: StructuralDeckProfile,
    *,
    protected: set[str] | frozenset[str] = frozenset(),
    max_hypotheses: int = 32,
) -> list[CutHypothesis]:
    """Build a diverse structural cut challenge set without treating a scalar score as truth."""
    if max_hypotheses < 1:
        raise ValueError("max_hypotheses must be positive")
    role_counts: Counter[str] = Counter()
    package_counts: Counter[str] = Counter()
    for card in deck.cards:
        role_counts.update(role.value for role in card.roles)
        package_counts.update(card.package_ids)

    rows: list[CutHypothesis] = []
    for card in deck.cards:
        if card.oracle_name in deck.commander_names or card.is_land or card.oracle_name in protected:
            continue
        roles = tuple(sorted(role.value for role in card.roles))
        unique_roles = tuple(sorted(role for role in roles if role_counts[role] <= 1))
        packages = tuple(sorted(card.package_ids))
        singleton_packages = tuple(sorted(p for p in packages if package_counts[p] <= 1))
        redundancy_units = sum(max(0, role_counts[role] - 1) for role in roles)
        lanes = {"functional_replacement"}
        rationale: list[str] = ["eligible non-land, non-commander, non-protected slot"]
        if redundancy_units:
            lanes.add("role_redundancy")
            rationale.append(f"role redundancy units={redundancy_units}")
        if card.mana_value >= 4.0:
            lanes.add("curve_mana_pressure")
            rationale.append(f"mana value {card.mana_value:.1f} permits a curve-pressure challenge")
        if packages:
            lanes.add("package_axis_challenge")
            rationale.append(f"package memberships={','.join(packages)}")
        if card.commander_synergy >= 1.0:
            lanes.add("commander_dependence_challenge")
            rationale.append("high modeled commander synergy merits an independence challenge, not a weakness claim")
        unique_critical = sum(role in _CRITICAL_ROLES for role in unique_roles)
        priority = (
            -profile_score(card)
            + 0.16 * redundancy_units
            + 0.08 * max(0.0, card.mana_value - 3.0)
            - 1.6 * unique_critical
            - 0.85 * len(singleton_packages)
            - 0.35 * len(unique_roles)
        )
        if unique_roles:
            rationale.append(f"unique roles protected by penalty={','.join(unique_roles)}")
        if singleton_packages:
            rationale.append(
                "singleton package memberships protected by penalty=" + ",".join(singleton_packages)
            )
        rows.append(
            CutHypothesis(
                oracle_name=card.oracle_name,
                lanes=tuple(sorted(lanes)),
                roles=roles,
                unique_roles=unique_roles,
                package_ids=packages,
                singleton_package_ids=singleton_packages,
                mana_value=float(card.mana_value),
                commander_synergy=float(card.commander_synergy),
                redundancy_units=redundancy_units,
                structural_challenge_priority=priority,
                rationale=tuple(rationale),
            )
        )

    rows.sort(key=lambda row: (-row.structural_challenge_priority, row.oracle_name.casefold()))
    by_lane: dict[str, list[CutHypothesis]] = defaultdict(list)
    for row in rows:
        for lane in row.lanes:
            by_lane[lane].append(row)
    selected: list[CutHypothesis] = []
    seen: set[str] = set()
    lane_order = (
        "role_redundancy",
        "curve_mana_pressure",
        "package_axis_challenge",
        "commander_dependence_challenge",
        "functional_replacement",
    )
    depth = 0
    while len(selected) < max_hypotheses:
        added = False
        for lane in lane_order:
            group = by_lane.get(lane, [])
            if depth >= len(group):
                continue
            row = group[depth]
            if row.oracle_name in seen:
                continue
            selected.append(row)
            seen.add(row.oracle_name)
            added = True
            if len(selected) >= max_hypotheses:
                break
        if not added and all(depth >= len(by_lane.get(lane, [])) for lane in lane_order):
            break
        depth += 1
    for row in rows:
        if len(selected) >= max_hypotheses:
            break
        if row.oracle_name not in seen:
            selected.append(row)
            seen.add(row.oracle_name)
    return selected


def build_static_swap_rows(
    deck: StructuralDeckProfile,
    candidates: Mapping[str, CandidateProfile],
    *,
    protected: set[str] | frozenset[str] = frozenset(),
    max_cut_hypotheses: int = 32,
) -> list[dict[str, Any]]:
    """Generate a broad deterministic pair pool from candidate and diverse cut hypotheses."""
    cuts = build_cut_hypotheses(
        deck, protected=protected, max_hypotheses=max_cut_hypotheses
    )
    cut_cards = {card.oracle_name: card for card in deck.cards}
    rows: list[dict[str, Any]] = []
    for cut_hypothesis in cuts:
        cut = cut_cards[cut_hypothesis.oracle_name]
        for candidate_id, candidate in candidates.items():
            if candidate.allowed_deck_ids and deck.deck_id not in candidate.allowed_deck_ids:
                continue
            raw_delta = profile_score(candidate.card) - profile_score(cut)
            overlap = candidate.card.roles & cut.roles
            lost_roles = cut.roles - candidate.card.roles
            critical_loss = sum(role.value in _CRITICAL_ROLES for role in lost_roles)
            compatibility_adjustment = (
                1.5 * len(overlap)
                - 0.5 * len(lost_roles)
                - 3.0 * critical_loss
                - (0.75 if not overlap else 0.0)
            )
            candidate_packages = set(candidate.card.package_ids)
            unmatched_singleton_packages = tuple(
                package
                for package in cut_hypothesis.singleton_package_ids
                if package not in candidate_packages
            )
            unique_role_loss = tuple(
                role for role in cut_hypothesis.unique_roles if role not in {r.value for r in candidate.card.roles}
            )
            commander_synergy_loss = max(0.0, cut.commander_synergy - candidate.card.commander_synergy)
            axis_adjustment = (
                -1.25 * len(unmatched_singleton_packages)
                -1.0 * len(unique_role_loss)
                -0.25 * commander_synergy_loss
            )
            delta = raw_delta + compatibility_adjustment + axis_adjustment
            rows.append(
                {
                    "remove": cut.oracle_name,
                    "add": candidate.card.oracle_name,
                    "candidate_id": candidate_id,
                    "screening_delta": delta,
                    "raw_profile_delta": raw_delta,
                    "role_compatibility_adjustment": compatibility_adjustment,
                    "package_axis_adjustment": axis_adjustment,
                    "screening_uncertainty_penalty": 0.0,
                    "legacy_screening_uncertainty_penalty": (
                        2.5 if candidate_id.startswith("inventory/") else 0.0
                    ),
                    "semantic_quality": (
                        "keyword_inferred_structural_only"
                        if candidate.card.source_quality.value == "project_inferred"
                        else "curated_structural_profile"
                    ),
                    "role_gain": sorted(role.value for role in candidate.card.roles - cut.roles),
                    "role_loss": sorted(role.value for role in lost_roles),
                    "unique_role_loss": list(unique_role_loss),
                    "unmatched_singleton_packages": list(unmatched_singleton_packages),
                    "mana_value_delta": float(candidate.card.mana_value - cut.mana_value),
                    "commander_synergy_delta": float(candidate.card.commander_synergy - cut.commander_synergy),
                    "physical_status": candidate.physical_status,
                    "requires_paired_validation": True,
                    "cut_hypothesis": cut_hypothesis.as_dict(),
                }
            )
    rows.sort(
        key=lambda row: (
            float(row["screening_delta"]),
            float(row["cut_hypothesis"]["structural_challenge_priority"]),
            str(row["add"]).casefold(),
        ),
        reverse=True,
    )
    return rows


def select_diverse_swap_frontier(
    rows: list[dict[str, Any]], *, max_pairs: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select capacity-bounded pairs with cut coverage first, then deterministic score fill."""
    if max_pairs < 1:
        raise ValueError("max_pairs must be positive")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["remove"])].append(row)
    for group in grouped.values():
        group.sort(key=lambda row: float(row["screening_delta"]), reverse=True)
    cut_order = sorted(
        grouped,
        key=lambda cut: (
            -float(grouped[cut][0]["cut_hypothesis"]["structural_challenge_priority"]),
            -float(grouped[cut][0]["screening_delta"]),
            cut.casefold(),
        ),
    )
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str]] = set()
    # Coverage pass: one strongest compatible hypothesis per plausible cut.
    for cut in cut_order:
        if len(selected) >= max_pairs:
            break
        row = grouped[cut][0]
        key = (str(row["remove"]), str(row["candidate_id"]))
        selected.append(row)
        selected_keys.add(key)
    # Quality fill: remaining capacity goes to the strongest deterministic hypotheses globally.
    for row in rows:
        if len(selected) >= max_pairs:
            break
        key = (str(row["remove"]), str(row["candidate_id"]))
        if key in selected_keys:
            continue
        selected.append(row)
        selected_keys.add(key)

    counts = Counter(str(row["remove"]) for row in selected)
    total = len(selected)
    shares = [count / total for count in counts.values()] if total else []
    lanes: Counter[str] = Counter()
    for row in selected:
        lanes.update(str(lane) for lane in row["cut_hypothesis"].get("lanes", ()))
    metrics = {
        "unique_cut_count": len(counts),
        "top_cut_pair_share": max(shares, default=0.0),
        "cut_concentration_metric": fsum(share * share for share in shares),
        "cut_pair_distribution": dict(sorted(counts.items())),
        "cut_lane_distribution": dict(sorted(lanes.items())),
        "pair_count": total,
        "selection_policy": "plausible_cut_coverage_then_deterministic_score_fill",
        "truth_boundary": "frontier composition metric, not empirical card weakness",
    }
    return selected, metrics


__all__ = [
    "CutHypothesis",
    "build_cut_hypotheses",
    "build_static_swap_rows",
    "select_diverse_swap_frontier",
]
'''.lstrip()

DECISION_INFORMATION = r'''
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from commander_lab.storage.run_identity import sha256_run_value


class DecisionInformationStatus(StrEnum):
    STOP_WITH_PREFERENCE = "STOP_WITH_PREFERENCE"
    NO_MATERIAL_DECISION_DIFFERENCE = "NO_MATERIAL_DECISION_DIFFERENCE"
    MORE_SIMULATIONS_USEFUL = "MORE_SIMULATIONS_USEFUL"
    MODEL_NEEDS_DIFFERENT_METRIC = "MODEL_NEEDS_DIFFERENT_METRIC"
    TACTICAL_EVIDENCE_NEEDED = "TACTICAL_EVIDENCE_NEEDED"
    OPPONENT_UNCERTAINTY_DOMINATES = "OPPONENT_UNCERTAINTY_DOMINATES"
    PRECISION_CEILING_REACHED = "PRECISION_CEILING_REACHED"
    STOP = "STOP"


@dataclass(frozen=True)
class DecisionInformationState:
    schema_version: str
    status: DecisionInformationStatus
    pairwise_effect: float | None
    confidence_interval: tuple[float, float] | None
    decision_uncertainty: float | None
    indifference_threshold: float
    seed_spread: float | None
    scenario_spread: float | None
    failure_mode_differences: tuple[str, ...]
    missing_semantic_axes: tuple[str, ...]
    current_iterations: int | None
    precision_ceiling: int | None
    additional_precision_authorized: bool
    next_recommended_experiment: str
    stop_reason: str
    evidence_class: str = "structural_decision_information"
    truth_boundary: str = "decision-information diagnostic, not empirical winrate"

    @property
    def state_hash(self) -> str:
        return sha256_run_value(asdict(self))

    def as_dict(self) -> dict[str, Any]:
        return {"state_hash": self.state_hash, **asdict(self)}


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _interval(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    low = _number(value[0])
    high = _number(value[1])
    if low is None or high is None:
        return None
    return low, high


def build_decision_information_state(
    comparison: dict[str, Any],
    *,
    model_informativeness: dict[str, Any] | None = None,
    scenario_spread: float | None = None,
    failure_mode_differences: tuple[str, ...] = (),
    missing_semantic_axes: tuple[str, ...] = (),
    tactical_evidence_required: bool = False,
    precision_context: dict[str, Any] | None = None,
    indifference_threshold: float = 0.025,
) -> DecisionInformationState:
    """Diagnose which uncertainty source should control the next experiment."""
    if indifference_threshold < 0.0:
        raise ValueError("indifference_threshold must be non-negative")
    context = precision_context or comparison.get("precision_context") or {}
    if not isinstance(context, dict):
        context = {}
    current_iterations = _integer(context.get("current_iterations"))
    precision_ceiling = _integer(context.get("preregistered_precision_ceiling"))
    additional_precision_authorized = context.get("additional_precision_authorized") is True

    if comparison.get("status") != "completed":
        return DecisionInformationState(
            schema_version="1.1.0",
            status=DecisionInformationStatus.STOP,
            pairwise_effect=None,
            confidence_interval=None,
            decision_uncertainty=None,
            indifference_threshold=indifference_threshold,
            seed_spread=None,
            scenario_spread=scenario_spread,
            failure_mode_differences=failure_mode_differences,
            missing_semantic_axes=missing_semantic_axes,
            current_iterations=current_iterations,
            precision_ceiling=precision_ceiling,
            additional_precision_authorized=additional_precision_authorized,
            next_recommended_experiment="repair_constraints_or_choose_another_candidate",
            stop_reason="comparison did not pass the hard-constraint gate",
        )

    paired = comparison.get("paired", {})
    if not isinstance(paired, dict):
        paired = {}
    effect = _number(paired.get("placement_improvement"))
    interval = _interval(paired.get("confidence_interval"))
    mcse = _number(paired.get("monte_carlo_standard_error"))
    seed_spread = (interval[1] - interval[0]) / 2.0 if interval is not None else mcse
    uncertainty = seed_spread

    if tactical_evidence_required:
        status = DecisionInformationStatus.TACTICAL_EVIDENCE_NEEDED
        next_experiment = "run_bounded_tactical_evidence_fixture"
        reason = "the unresolved decision depends on legal-action/timing/rules execution"
    elif scenario_spread is not None and seed_spread is not None and scenario_spread > seed_spread:
        status = DecisionInformationStatus.OPPONENT_UNCERTAINTY_DOMINATES
        next_experiment = "test_finalists_across_declared_opponent_envelopes"
        reason = "between-scenario uncertainty exceeds within-scenario seed uncertainty"
    elif missing_semantic_axes:
        status = DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC
        next_experiment = "resolve_decision_material_semantic_axes"
        reason = "a decision-material semantic axis is missing from the current comparison"
    elif interval is not None and interval[0] > indifference_threshold:
        status = DecisionInformationStatus.STOP_WITH_PREFERENCE
        next_experiment = "stop_with_structural_preference"
        reason = "the paired interval is separated beyond the decision-indifference threshold"
    elif interval is not None and interval[1] < -indifference_threshold:
        status = DecisionInformationStatus.STOP
        next_experiment = "stop_or_return_to_candidate_screening"
        reason = "the paired interval is materially negative"
    elif (
        interval is not None
        and interval[0] >= -indifference_threshold
        and interval[1] <= indifference_threshold
    ):
        status = DecisionInformationStatus.NO_MATERIAL_DECISION_DIFFERENCE
        next_experiment = "stop_no_material_difference"
        reason = "the entire interval lies inside the decision-indifference region"
    elif (model_informativeness or {}).get("status") == "MODEL_INFORMATION_LIMIT":
        status = DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC
        next_experiment = "diagnose_model_information_before_more_seed_work"
        reason = "the structural cohort is saturated or non-separable; seeds alone are insufficient"
    elif (
        current_iterations is not None
        and precision_ceiling is not None
        and current_iterations >= precision_ceiling
        and not additional_precision_authorized
    ):
        status = DecisionInformationStatus.PRECISION_CEILING_REACHED
        next_experiment = "select_next_non_seed_evidence_or_remain_unresolved"
        reason = "the preregistered precision ceiling is reached and more seed work is not authorized"
    else:
        status = DecisionInformationStatus.MORE_SIMULATIONS_USEFUL
        next_experiment = "run_next_paired_micro_batch"
        reason = "current seed uncertainty can still plausibly change the material decision within budget"

    return DecisionInformationState(
        schema_version="1.1.0",
        status=status,
        pairwise_effect=effect,
        confidence_interval=interval,
        decision_uncertainty=uncertainty,
        indifference_threshold=indifference_threshold,
        seed_spread=seed_spread,
        scenario_spread=scenario_spread,
        failure_mode_differences=failure_mode_differences,
        missing_semantic_axes=missing_semantic_axes,
        current_iterations=current_iterations,
        precision_ceiling=precision_ceiling,
        additional_precision_authorized=additional_precision_authorized,
        next_recommended_experiment=next_experiment,
        stop_reason=reason,
    )


__all__ = [
    "DecisionInformationState",
    "DecisionInformationStatus",
    "build_decision_information_state",
]
'''.lstrip()

MODEL_INFO = r'''
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
'''.lstrip()

SEMANTIC_EVIDENCE = r'''
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Iterable

from commander_lab.models import CandidateProfile, DataQuality
from commander_lab.storage.run_identity import sha256_run_value


class SemanticEvidenceType(StrEnum):
    CANONICAL_PROJECT = "CANONICAL_PROJECT"
    PROJECT_DERIVED = "PROJECT_DERIVED"
    DETERMINISTIC_ORACLE = "DETERMINISTIC_ORACLE"
    EXTERNAL_STRUCTURED = "EXTERNAL_STRUCTURED"
    PROJECT_HEURISTIC = "PROJECT_HEURISTIC"
    LLM_INFERRED = "LLM_INFERRED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    UNKNOWN = "UNKNOWN"


class SemanticConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class DecisionMateriality(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class SemanticEvidenceRecord:
    card_id: str | None
    oracle_name: str
    feature: str
    value: Any
    confidence: SemanticConfidence
    evidence_type: SemanticEvidenceType
    source_id: str | None
    source_version: str | None
    extraction_method: str
    review_status: str
    decision_materiality: DecisionMateriality

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def evidence_hash(self) -> str:
        return sha256_run_value(self)


_DECISION_ROLES = frozenset(
    {
        "counter", "draw", "engine", "finisher", "land", "mana_source", "protection",
        "ramp", "rebuild", "removal", "selection", "wipe",
    }
)


def summarize_semantic_records(records: Iterable[SemanticEvidenceRecord]) -> dict[str, Any]:
    materialized = tuple(records)
    by_feature: dict[str, list[SemanticEvidenceRecord]] = {}
    for record in materialized:
        by_feature.setdefault(record.feature, []).append(record)
    conflicts: list[dict[str, Any]] = []
    for feature, rows in sorted(by_feature.items()):
        values = {sha256_run_value(row.value) for row in rows}
        material = any(row.decision_materiality == DecisionMateriality.HIGH for row in rows)
        if material and len(values) > 1:
            conflicts.append(
                {
                    "feature": feature,
                    "record_hashes": [row.evidence_hash for row in rows],
                    "source_ids": [row.source_id for row in rows],
                }
            )
    payload = {
        "records": [
            {"evidence_hash": record.evidence_hash, **record.as_dict()} for record in materialized
        ],
        "material_conflicts": conflicts,
        "material_conflict": bool(conflicts),
        "requires_semantic_adjudication": bool(conflicts),
        "automatic_promotion": False,
        "automatic_rejection": False,
        "llm_inferred_is_canonical": False,
        "truth_boundary": "semantic conflict routing, not empirical card power",
    }
    payload["semantic_record_set_hash"] = sha256_run_value(payload)
    return payload


def semantic_evidence_summary(
    *,
    oracle_name: str,
    profile: CandidateProfile | None,
    annotation_roles: tuple[str, ...] = (),
    annotation_packages: tuple[str, ...] = (),
    additional_records: tuple[SemanticEvidenceRecord, ...] = (),
) -> dict[str, Any]:
    roles = set(annotation_roles)
    packages = set(annotation_packages)
    source_types: set[str] = set()
    source_ids: set[str] = set()
    provenance_records: list[dict[str, Any]] = []

    if profile is not None:
        profile_roles = tuple(sorted(role.value for role in profile.card.roles))
        profile_packages = tuple(sorted(profile.card.package_ids))
        roles.update(profile_roles)
        packages.update(profile_packages)
        source_types.update(source.source_type for source in profile.card.sources)
        source_ids.update(source.source_path for source in profile.card.sources if source.source_path)
        provenance_records.append(
            {
                "layer": "structural_profile",
                "roles": profile_roles,
                "package_ids": profile_packages,
                "source_types": tuple(sorted(source_types)),
                "source_ids": tuple(sorted(source_ids)),
            }
        )
    if annotation_roles or annotation_packages:
        provenance_records.append(
            {
                "layer": "canonical_feature_annotation",
                "roles": tuple(sorted(annotation_roles)),
                "package_ids": tuple(sorted(annotation_packages)),
            }
        )

    if profile is None and not annotation_roles and not annotation_packages:
        evidence_type = SemanticEvidenceType.UNKNOWN
        confidence = SemanticConfidence.UNKNOWN
    elif profile is not None and profile.card.source_quality in {
        DataQuality.AUTHORITATIVE, DataQuality.PROJECT_VERIFIED,
    }:
        evidence_type = SemanticEvidenceType.CANONICAL_PROJECT
        confidence = SemanticConfidence.HIGH
    elif annotation_roles or annotation_packages:
        evidence_type = SemanticEvidenceType.PROJECT_DERIVED
        confidence = SemanticConfidence.MEDIUM
    elif profile is not None and profile.card.source_quality == DataQuality.PROJECT_INFERRED:
        evidence_type = SemanticEvidenceType.PROJECT_HEURISTIC
        confidence = SemanticConfidence.LOW
    else:
        evidence_type = SemanticEvidenceType.UNKNOWN
        confidence = SemanticConfidence.UNKNOWN

    if (roles & _DECISION_ROLES) or packages:
        materiality = DecisionMateriality.HIGH
    elif roles:
        materiality = DecisionMateriality.MEDIUM
    else:
        materiality = DecisionMateriality.LOW
    canonical_ready = evidence_type in {
        SemanticEvidenceType.CANONICAL_PROJECT, SemanticEvidenceType.PROJECT_DERIVED,
        SemanticEvidenceType.DETERMINISTIC_ORACLE, SemanticEvidenceType.EXTERNAL_STRUCTURED,
        SemanticEvidenceType.HUMAN_REVIEWED,
    }
    conflict_summary = summarize_semantic_records(additional_records)
    needs_targeted_adjudication = (
        (materiality == DecisionMateriality.HIGH and not canonical_ready)
        or conflict_summary["material_conflict"] is True
    )
    payload = {
        "oracle_name": oracle_name,
        "evidence_type": evidence_type.value,
        "confidence": confidence.value,
        "decision_materiality": materiality.value,
        "roles": tuple(sorted(roles)),
        "package_ids": tuple(sorted(packages)),
        "source_types": tuple(sorted(source_types)),
        "source_ids": tuple(sorted(source_ids)),
        "provenance_records": provenance_records,
        "canonical_project_fact": evidence_type == SemanticEvidenceType.CANONICAL_PROJECT,
        "llm_inferred": evidence_type == SemanticEvidenceType.LLM_INFERRED,
        "needs_targeted_adjudication": needs_targeted_adjudication,
        "semantic_conflict": conflict_summary,
        "truth_boundary": "semantic evidence and confidence, not empirical card power",
    }
    payload["semantic_evidence_hash"] = sha256_run_value(payload)
    return payload


__all__ = [
    "DecisionMateriality", "SemanticConfidence", "SemanticEvidenceRecord", "SemanticEvidenceType",
    "semantic_evidence_summary", "summarize_semantic_records",
]
'''.lstrip()

write("src/commander_lab/cut_frontier.py", CUT_FRONTIER)
write("src/commander_lab/decision_information.py", DECISION_INFORMATION)
write("src/commander_lab/model_informativeness.py", MODEL_INFO)
write("src/commander_lab/semantic_evidence.py", SEMANTIC_EVIDENCE)

# Extend paired observations so exact prefix reuse can reconstruct final statistics.
exp = read("src/commander_lab/optimization/experiments.py")
old_pair = '''            "baseline_placement": baseline_metrics.placement,\n            "variant_placement": variant_metrics.placement,\n            "comparison": comparison,'''
new_pair = '''            "baseline_placement": baseline_metrics.placement,\n            "variant_placement": variant_metrics.placement,\n            "baseline_win": baseline_row["win"],\n            "variant_win": variant_row["win"],\n            "baseline_damage": baseline_row["damage"],\n            "variant_damage": variant_row["damage"],\n            "baseline_cards_drawn": baseline_row["cards_drawn"],\n            "variant_cards_drawn": variant_row["cards_drawn"],\n            "comparison": comparison,'''
if exp.count(old_pair) != 1:
    raise RuntimeError("paired worker payload anchor mismatch")
exp = exp.replace(old_pair, new_pair, 1)
start = exp.index("def run_paired_structural_comparison(")
end_marker = "    return metrics, pairs\n"
end = exp.index(end_marker, start) + len(end_marker)
new_compare = r'''
def run_paired_structural_observations(
    *,
    baseline: StructuralDeckProfile,
    variant: StructuralDeckProfile,
    opponents: tuple[StructuralDeckProfile, ...],
    start_index: int,
    iterations: int,
    seed: int,
    pilot_config: PilotConfig,
    max_turns: int,
    pair_id: str,
    starting_player_seat: int | None = None,
    workers: int = 1,
) -> list[dict[str, object]]:
    if workers < 1:
        raise ValueError("workers must be positive")
    if iterations < 1:
        raise ValueError("iterations must be positive")
    if start_index < 0:
        raise ValueError("start_index must be non-negative")
    tasks: list[dict[str, Any]] = []
    for index in range(start_index, start_index + iterations):
        match_seed = derive_paired_seed(seed, pair_id, index)
        start = starting_player_seat if starting_player_seat is not None else index % (1 + len(opponents))
        tasks.append(
            {
                "index": index,
                "pair_id": pair_id,
                "seed": match_seed,
                "starting_player_seat": start,
                "pilot_config": pilot_config.model_dump(mode="json"),
                "max_turns": max_turns,
            }
        )
    initializer_args = (
        baseline.model_dump(mode="json"),
        variant.model_dump(mode="json"),
        [deck.model_dump(mode="json") for deck in opponents],
    )
    if workers == 1:
        _initialize_paired_worker(*initializer_args)
        raw_results = [_run_paired_worker(task) for task in tasks]
    else:
        chunksize = max(1, len(tasks) // (workers * 4))
        if "PYTEST_CURRENT_TEST" in os.environ:
            _initialize_paired_worker(*initializer_args)
            with ThreadPoolExecutor(max_workers=workers) as thread_executor:
                raw_results = list(thread_executor.map(_run_paired_worker, tasks, chunksize=chunksize))
        else:
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_initialize_paired_worker,
                initargs=initializer_args,
                mp_context=multiprocessing.get_context("spawn"),
            ) as process_executor:
                raw_results = list(process_executor.map(_run_paired_worker, tasks, chunksize=chunksize))
    return [dict(raw["pair"]) for raw in raw_results]


def aggregate_paired_observations(
    observations: list[dict[str, object]],
    *,
    seed: int,
    pair_id: str,
    pilot_config: PilotConfig,
    opponents: tuple[StructuralDeckProfile, ...],
    starting_player_seat: int | None = None,
    worker_count: int = 1,
) -> PairedMetrics:
    pairs = sorted(observations, key=lambda row: int(row["index"]))
    if not pairs:
        raise ValueError("paired observations must not be empty")
    expected = list(range(len(pairs)))
    actual = [int(row["index"]) for row in pairs]
    if actual != expected:
        raise ValueError("final paired observations must form the exact contiguous prefix 0..N-1")
    iterations = len(pairs)

    def avg(key: str) -> float:
        return fmean(float(row[key]) for row in pairs)

    differences = tuple(
        float(row["baseline_placement"]) - float(row["variant_placement"]) for row in pairs
    )
    interval = paired_bootstrap_interval(
        differences, seed=derive_paired_seed(seed, pair_id, iterations + 1)
    )
    base_place = avg("baseline_placement")
    var_place = avg("variant_placement")
    return PairedMetrics(
        games=iterations,
        baseline_average_placement=base_place,
        variant_average_placement=var_place,
        placement_improvement=base_place - var_place,
        baseline_place_1_share=avg("baseline_win"),
        variant_place_1_share=avg("variant_win"),
        place_1_share_delta=avg("variant_win") - avg("baseline_win"),
        baseline_average_damage=avg("baseline_damage"),
        variant_average_damage=avg("variant_damage"),
        damage_delta=avg("variant_damage") - avg("baseline_damage"),
        baseline_average_cards_drawn=avg("baseline_cards_drawn"),
        variant_average_cards_drawn=avg("variant_cards_drawn"),
        cards_drawn_delta=avg("variant_cards_drawn") - avg("baseline_cards_drawn"),
        paired_win_count=sum(row["comparison"] == "variant_win" for row in pairs),
        paired_loss_count=sum(row["comparison"] == "variant_loss" for row in pairs),
        paired_tie_count=sum(row["comparison"] == "tie" for row in pairs),
        requested_runs=iterations,
        started_runs=iterations,
        valid_runs=iterations,
        failed_runs=0,
        discarded_runs=0,
        actual_sample_size=iterations,
        seeds=tuple(int(row["seed"]) for row in pairs),
        worker_count=worker_count,
        validation_level="structural_only",
        paired_or_unpaired="paired",
        effect_size=paired_standardized_effect(differences),
        confidence_interval=interval,
        bootstrap_method="deterministic_paired_percentile_bootstrap_2000",
        holdout_definition="primary paired scenario; holdouts reported separately",
        worst_case_result=min(differences),
        scenario_weights="equal within this paired scenario",
        pilot_weights=f"single configured pilot: {pilot_config.strength.value}",
        multiple_testing_method="not_applicable_single_comparison; Holm required for ranked families",
        rounding_policy="unrounded internal values; presentation may round to six decimals",
        bayesian_shrunk_effect=bayesian_shrunk_mean(differences),
        distributionally_robust_lower_bound=distributionally_robust_lower_bound(differences),
        quantiles=quantile_summary(differences),
        paired_randomization_p_value=paired_randomization_p_value(
            differences, seed=derive_paired_seed(seed, pair_id, iterations + 2)
        ),
        monte_carlo_standard_error=monte_carlo_standard_error(differences),
        confidence_interval_interpretation=(
            "model-internal Monte Carlo uncertainty interval for the paired structural simulator; "
            "not an empirical Commander confidence interval"
        ),
        pairing_conditions={
            "common_random_numbers": True,
            "same_seeds": True,
            "same_seats": True,
            "same_pod_size": True,
            "same_opponent_assumptions": True,
            "same_pilot_configuration": True,
            "pod_size": 1 + len(opponents),
            "opponent_deck_ids": [deck.deck_id for deck in opponents],
            "pilot_strength": pilot_config.strength.value,
            "pilot_mode": pilot_config.mode.value,
            "seat_policy": "explicit_fixed" if starting_player_seat is not None else "deterministic_rotation",
            "starting_player_seat": starting_player_seat,
        },
    )


def run_paired_structural_comparison(
    *,
    baseline: StructuralDeckProfile,
    variant: StructuralDeckProfile,
    opponents: tuple[StructuralDeckProfile, ...],
    iterations: int,
    seed: int,
    pilot_config: PilotConfig,
    max_turns: int,
    pair_id: str,
    starting_player_seat: int | None = None,
    workers: int = 1,
) -> tuple[PairedMetrics, list[dict[str, object]]]:
    pairs = run_paired_structural_observations(
        baseline=baseline,
        variant=variant,
        opponents=opponents,
        start_index=0,
        iterations=iterations,
        seed=seed,
        pilot_config=pilot_config,
        max_turns=max_turns,
        pair_id=pair_id,
        starting_player_seat=starting_player_seat,
        workers=workers,
    )
    metrics = aggregate_paired_observations(
        pairs,
        seed=seed,
        pair_id=pair_id,
        pilot_config=pilot_config,
        opponents=opponents,
        starting_player_seat=starting_player_seat,
        worker_count=workers,
    )
    return metrics, pairs
'''.lstrip()
exp = exp[:start] + new_compare + exp[end:]
write("src/commander_lab/optimization/experiments.py", exp)

# Priority workflow: reuse exact cached prefixes and make cohort informativeness available to diagnose.
pw = read("src/commander_lab/priority_workflows.py")
pw = pw.replace("from statistics import", "from statistics import", 1) if "from statistics import" in pw else pw.replace(
    "from pathlib import Path\n", "from pathlib import Path\nfrom statistics import fmean\n", 1
)
pw = pw.replace(
    "    run_paired_structural_comparison,\n)",
    "    run_paired_structural_comparison,\n)\nfrom commander_lab.optimization.experiments import (\n    aggregate_paired_observations,\n    run_paired_structural_observations,\n)",
    1,
)
old_compute = '''        def compute() -> dict[str, Any]:\n            metrics, pairs = run_paired_structural_comparison(\n                baseline=baseline,\n                variant=built.variant,\n                opponents=opponents,\n                iterations=iterations,\n                seed=seed,\n                pilot_config=pilot_config,\n                max_turns=max_turns,\n                pair_id=pair_id,\n                workers=effective_workers,\n            )\n            return {"paired": metrics.as_dict(), "pairs": pairs}\n\n        cached = self.result_cache.get_or_compute(\n            cache_identity,\n            evidence_class="structural_model_estimates",\n            compute=compute,\n        )\n        paired = dict(cached.result["paired"])\n        pairs = list(cached.result["pairs"])'''
new_compute = '''        cached = self.result_cache.get(cache_identity)\n        reused_prefix_count = 0\n        incremental_simulated_count = 0\n        prefix_cache_key: str | None = None\n        if cached is None:\n            prefix_lookup = None\n            prefix_candidates = sorted(\n                {value for value in (512, 256, 128, 64, 32, 16, 8, iterations // 2) if 0 < value < iterations},\n                reverse=True,\n            )\n            for prefix_count in prefix_candidates:\n                prefix_identity = dict(cache_identity)\n                prefix_identity["simulation_config"] = {\n                    **dict(cache_identity["simulation_config"]),\n                    "iterations": prefix_count,\n                    "analysis_seed": derive_paired_seed(seed, pair_id, prefix_count + 1),\n                }\n                prefix_identity["exact_seed_set"] = list(paired_seeds[:prefix_count])\n                candidate_lookup = self.result_cache.get(prefix_identity)\n                if candidate_lookup is not None:\n                    prefix_lookup = candidate_lookup\n                    reused_prefix_count = prefix_count\n                    prefix_cache_key = candidate_lookup.cache_key\n                    break\n            if prefix_lookup is not None:\n                prefix_pairs = [dict(row) for row in prefix_lookup.result["pairs"]]\n                suffix_pairs = run_paired_structural_observations(\n                    baseline=baseline,\n                    variant=built.variant,\n                    opponents=opponents,\n                    start_index=reused_prefix_count,\n                    iterations=iterations - reused_prefix_count,\n                    seed=seed,\n                    pilot_config=pilot_config,\n                    max_turns=max_turns,\n                    pair_id=pair_id,\n                    workers=effective_workers,\n                )\n                incremental_simulated_count = len(suffix_pairs)\n                pairs = [*prefix_pairs, *suffix_pairs]\n                metrics = aggregate_paired_observations(\n                    pairs,\n                    seed=seed,\n                    pair_id=pair_id,\n                    pilot_config=pilot_config,\n                    opponents=opponents,\n                    worker_count=effective_workers,\n                )\n            else:\n                metrics, pairs = run_paired_structural_comparison(\n                    baseline=baseline,\n                    variant=built.variant,\n                    opponents=opponents,\n                    iterations=iterations,\n                    seed=seed,\n                    pilot_config=pilot_config,\n                    max_turns=max_turns,\n                    pair_id=pair_id,\n                    workers=effective_workers,\n                )\n                incremental_simulated_count = len(pairs)\n            cached = self.result_cache.put(\n                cache_identity,\n                {"paired": metrics.as_dict(), "pairs": pairs},\n                evidence_class="structural_model_estimates",\n            )\n        paired = dict(cached.result["paired"])\n        pairs = list(cached.result["pairs"])'''
if old_compute not in pw:
    raise RuntimeError("priority compare compute anchor mismatch")
pw = pw.replace(old_compute, new_compute, 1)
pw = pw.replace(
    '"policy": "validated_single_worker_until_issue_55_resolution",',
    '"policy": "validated_single_worker_policy_1_18",',
    1,
)
pw = pw.replace(
    '            "execution_workers": {',
    '            "incremental_execution": {\n                "target_pair_count": iterations,\n                "reused_prefix_count": reused_prefix_count,\n                "incremental_simulated_count": incremental_simulated_count,\n                "prefix_cache_key": prefix_cache_key,\n                "chunk_boundaries_are_execution_provenance_only": True,\n                "deck_quality_evidence": False,\n            },\n            "precision_context": {\n                "current_iterations": iterations,\n                "preregistered_precision_ceiling": 1024,\n                "additional_precision_authorized": False,\n            },\n            "execution_workers": {',
    1,
)
pattern = r'''    @staticmethod\n    def diagnose_next_experiment\(comparison: dict\[str, Any\]\) -> dict\[str, Any\]:.*?\n    @staticmethod\n    def model_informativeness'''
replacement = r'''    @staticmethod
    def diagnose_next_experiment(
        comparison: dict[str, Any],
        *,
        cohort_comparisons: tuple[dict[str, Any], ...] = (),
        opponent_evidence_quality: dict[str, int] | None = None,
        failure_mode_metrics: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        working = dict(comparison)
        if cohort_comparisons:
            paired_rows = tuple(
                dict(row.get("paired", {}))
                for row in cohort_comparisons
                if isinstance(row, dict) and isinstance(row.get("paired"), dict)
            )
            baseline_shares = [
                float(row["baseline_place_1_share"])
                for row in paired_rows
                if isinstance(row.get("baseline_place_1_share"), (int, float))
                and not isinstance(row.get("baseline_place_1_share"), bool)
            ]
            seat_wins: dict[int, list[float]] = {}
            for row in cohort_comparisons:
                observations = row.get("paired_observations", ()) if isinstance(row, dict) else ()
                if not isinstance(observations, (list, tuple)):
                    continue
                for obs in observations:
                    if not isinstance(obs, dict):
                        continue
                    seat = obs.get("starting_player_seat")
                    placement = obs.get("baseline_placement")
                    if isinstance(seat, int) and isinstance(placement, (int, float)):
                        seat_wins.setdefault(seat, []).append(float(placement == 1))
            seat_results = {
                str(seat): {"place_1_share": fmean(values)}
                for seat, values in seat_wins.items()
                if values
            }
            info = assess_model_informativeness(
                baseline_place_1_share=fmean(baseline_shares) if baseline_shares else None,
                seat_results=seat_results,
                variant_comparisons=paired_rows,
                opponent_evidence_quality=opponent_evidence_quality,
                failure_mode_metrics=failure_mode_metrics,
            ).as_dict()
            working["model_informativeness"] = info
        model_informativeness = working.get("model_informativeness")
        if not isinstance(model_informativeness, dict):
            model_informativeness = {}
        opponent_uncertainty = working.get("opponent_uncertainty")
        scenario_spread: float | None = None
        if isinstance(opponent_uncertainty, dict):
            raw_spread = opponent_uncertainty.get("scenario_spread")
            if isinstance(raw_spread, (int, float)) and not isinstance(raw_spread, bool):
                scenario_spread = float(raw_spread)
        raw_missing = working.get("missing_semantic_axes", ())
        missing_semantic_axes = (
            tuple(str(value) for value in raw_missing)
            if isinstance(raw_missing, (list, tuple))
            else ()
        )
        raw_failure = working.get("failure_mode_differences", ())
        failure_mode_differences = (
            tuple(str(value) for value in raw_failure)
            if isinstance(raw_failure, (list, tuple))
            else ()
        )
        state = build_decision_information_state(
            working,
            model_informativeness=model_informativeness,
            scenario_spread=scenario_spread,
            missing_semantic_axes=missing_semantic_axes,
            failure_mode_differences=failure_mode_differences,
            tactical_evidence_required=working.get("tactical_evidence_required") is True,
            precision_context=(working.get("precision_context") if isinstance(working.get("precision_context"), dict) else None),
        )
        return {
            "workflow": "diagnose_next_experiment",
            "next_experiment": state.next_recommended_experiment,
            "reason": state.stop_reason,
            "model_informativeness": model_informativeness,
            "decision_information_state": state.as_dict(),
        }

    @staticmethod
    def model_informativeness'''
pw, count = re.subn(pattern, replacement, pw, count=1, flags=re.S)
if count != 1:
    raise RuntimeError("diagnose method anchor mismatch")
write("src/commander_lab/priority_workflows.py", pw)

# Public diagnose schema can carry cohort context without expanding public tool count.
replace_once(
    "src/commander_lab/models/tooling.py",
    "class DeckDecisionDiagnoseInput(FrozenModel):\n    comparison: dict[str, Any]\n",
    "class DeckDecisionDiagnoseInput(FrozenModel):\n"
    "    comparison: dict[str, Any]\n"
    "    cohort_comparisons: tuple[dict[str, Any], ...] = ()\n"
    "    opponent_evidence_quality: dict[str, int] = Field(default_factory=dict)\n"
    "    failure_mode_metrics: tuple[str, ...] = ()\n",
)

# Service: import frontier helpers, replace legacy single-ranking methods, wire cohort diagnose.
service = read("src/commander_lab/tools/service.py")
service = service.replace(
    "from commander_lab.decision_statistics import holm_adjust\n",
    "from commander_lab.decision_statistics import holm_adjust\n"
    "from commander_lab.cut_frontier import build_static_swap_rows, select_diverse_swap_frontier\n",
    1,
)
recommend_method = r'''    def recommend_upgrades(self, request: RecommendUpgradesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._require_active_optimization_target(request.deck_id)
            deck = self._deck(request.deck_id)
            candidate_ids = set(request.candidate_ids) if request.candidate_ids else None
            candidates = {
                candidate_id: candidate
                for candidate_id, candidate in self.candidates.items()
                if candidate_ids is None or candidate_id in candidate_ids
            }
            rows = build_static_swap_rows(
                deck,
                candidates,
                protected=set(self.protected_cards.get(request.deck_id, [])),
                max_cut_hypotheses=max(16, min(32, request.max_recommendations)),
            )
            return {
                "method": "diverse_cut_hypothesis_and_role_package_profile_screening_only",
                "recommendations": rows[: request.max_recommendations],
                "warning": "Candidates are not confirmed until paired and robustness validation pass.",
            }

        return self._invoke("recommend_upgrades", request, work, deck_ids=(request.deck_id,))

'''
service, count = re.subn(
    r"    def recommend_upgrades\(self, request: RecommendUpgradesInput\) -> ToolResponse:.*?(?=    def _meta_kb)",
    recommend_method,
    service,
    count=1,
    flags=re.S,
)
if count != 1:
    raise RuntimeError("recommend_upgrades replacement failed")

generate_method = r'''    def generate_candidate_swaps(self, request: GenerateCandidateSwapsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._require_active_optimization_target(request.deck_id)
            from commander_lab.candidate_screening import RogShaiCandidateScreener

            deck = self._deck(request.deck_id)
            semantic_screen = RogShaiCandidateScreener(self.root, service=self).screen_pool(request.deck_id)
            raw_screen_rows = semantic_screen.get("rows", [])
            screen_rows: list[Any] = raw_screen_rows if isinstance(raw_screen_rows, list) else []
            by_id = {
                str(item["candidate_id"]): item
                for item in screen_rows
                if isinstance(item, dict) and item.get("candidate_id")
            }
            by_name = {
                str(item["oracle_name"]): item
                for item in screen_rows
                if isinstance(item, dict) and item.get("oracle_name")
            }
            requested_ids = set(request.candidate_ids) if request.candidate_ids else None
            candidate_map = {
                candidate_id: candidate
                for candidate_id, candidate in self.candidates.items()
                if requested_ids is None or candidate_id in requested_ids
            }
            raw_pairs = build_static_swap_rows(
                deck,
                candidate_map,
                protected=set(self.protected_cards.get(request.deck_id, [])),
                max_cut_hypotheses=32,
            )
            semantically_ready: list[dict[str, Any]] = []
            semantic_deferred: list[dict[str, Any]] = []
            for raw in raw_pairs:
                row = dict(raw)
                screen_row = by_id.get(str(row.get("candidate_id"))) or by_name.get(str(row.get("add")))
                evidence = (
                    dict(screen_row.get("semantic_evidence", {}))
                    if isinstance(screen_row, dict) and isinstance(screen_row.get("semantic_evidence"), dict)
                    else {}
                )
                bucket = str(screen_row.get("bucket")) if isinstance(screen_row, dict) else "missing"
                model_ready = bool(
                    isinstance(screen_row, dict)
                    and screen_row.get("model_dependent_recommendation_ready") is True
                )
                needs_adjudication = bool(evidence.get("needs_targeted_adjudication") is True or not model_ready)
                legacy_quality = str(row.get("semantic_quality", "unknown"))
                evidence_type = str(evidence.get("evidence_type", "UNKNOWN"))
                provenance_disagreement = (
                    legacy_quality == "keyword_inferred_structural_only"
                    and evidence_type not in {"PROJECT_HEURISTIC", "UNKNOWN"}
                )
                if screen_row is None:
                    frontier_status = "deferred_missing_current_semantic_screen"
                    needs_adjudication = True
                elif not model_ready:
                    frontier_status = "deferred_requires_profile"
                elif evidence.get("needs_targeted_adjudication") is True:
                    frontier_status = "deferred_requires_semantic_adjudication"
                elif bucket in {"defer_clear_static_dominance", "defer_low_confidence_default"}:
                    frontier_status = "deferred_static"
                else:
                    frontier_status = "preconstraint_ready"
                enriched = {
                    **row,
                    "legacy_semantic_quality": legacy_quality,
                    "semantic_authority": "semantic_evidence_summary",
                    "semantic_evidence": evidence,
                    "semantic_evidence_hash": str(evidence.get("semantic_evidence_hash", "")),
                    "semantic_screen_bucket": bucket,
                    "semantic_provenance_disagreement": provenance_disagreement,
                    "material_semantic_conflict": bool(evidence.get("needs_targeted_adjudication") is True),
                    "requires_semantic_adjudication": needs_adjudication,
                    "frontier_status": frontier_status,
                    "recommendation_status": "candidate_swap",
                    "validation_level": "structural_only",
                    "candidate_source": "verified local candidate registry",
                    "automatic_application": False,
                }
                if frontier_status == "preconstraint_ready":
                    semantically_ready.append(enriched)
                elif needs_adjudication:
                    semantic_deferred.append(enriched)
            # Select extra capacity so hard-constraint failures can be replaced without changing the policy.
            selected_pool, selection_metrics = select_diverse_swap_frontier(
                semantically_ready, max_pairs=min(len(semantically_ready), request.max_candidates * 2)
            )
            ready_rows: list[dict[str, Any]] = []
            constraint_deferred: list[dict[str, Any]] = []
            constraints = self._optimization_constraints(request.deck_id)
            for row in selected_pool:
                try:
                    built = build_search_candidate(
                        deck,
                        (VariantSwap(remove=str(row["remove"]), add_candidate_id=str(row["candidate_id"])),),
                        self.candidates,
                        constraints,
                        inventory=self.candidate_inventory,
                        verified_physical_names=self.verified_candidate_names,
                    )
                except (KeyError, ValueError) as exc:
                    constraint_deferred.append({**row, "frontier_status": "deferred_hard_constraint", "constraint_error": str(exc)})
                    continue
                if not built.constraint_report.valid:
                    constraint_deferred.append(
                        {**row, "frontier_status": "deferred_hard_constraint", "constraint_report": built.constraint_report.model_dump(mode="json")}
                    )
                    continue
                ready_rows.append(
                    {
                        **row,
                        "frontier_status": "simulation_ready",
                        "whole_deck_constraint_report": built.constraint_report.model_dump(mode="json"),
                        "variant_deck_hash": built.variant.deck_hash,
                    }
                )
                if len(ready_rows) >= request.max_candidates:
                    break
            _, final_metrics = select_diverse_swap_frontier(ready_rows, max_pairs=max(1, len(ready_rows))) if ready_rows else ([], {
                "unique_cut_count": 0, "top_cut_pair_share": 0.0, "cut_concentration_metric": 0.0,
                "cut_pair_distribution": {}, "cut_lane_distribution": {}, "pair_count": 0,
                "selection_policy": "no_ready_pairs", "truth_boundary": "frontier composition metric, not empirical card weakness",
            })
            bucket_counts = semantic_screen.get("bucket_counts", {})
            static_count = sum(
                int(bucket_counts.get(name, 0))
                for name in ("defer_clear_static_dominance", "defer_low_confidence_default")
            ) if isinstance(bucket_counts, dict) else 0
            return {
                "deck_id": request.deck_id,
                "deck_hash": deck.deck_hash,
                "method": "candidate_semantic_gate_x_diverse_cut_hypothesis_frontier",
                "candidates": ready_rows,
                "count": len(ready_rows),
                "pair_pool_count": len(raw_pairs),
                "preconstraint_pair_count": len(semantically_ready),
                "deferred_semantic_candidates": semantic_deferred,
                "semantic_deferred_count": len(semantic_deferred),
                "constraint_deferred_candidates": constraint_deferred,
                "constraint_deferred_count": len(constraint_deferred),
                "static_deprioritized_count": static_count,
                "candidate_recall": semantic_screen.get("candidate_recall"),
                "candidate_discoverable_count": semantic_screen.get("discoverable_candidate_count"),
                "frontier_composition": final_metrics,
                "selection_preview": selection_metrics,
                "semantic_frontier_gate": {
                    "authority": "semantic_evidence_summary",
                    "legacy_semantic_quality_is_authoritative": False,
                    "unmodeled_is_negative_evidence": False,
                    "noisy_early_simulation_elimination": False,
                },
                "cut_frontier_gate": {
                    "scalar_profile_score_is_sole_authority": False,
                    "package_axis_loss_considered": True,
                    "unique_role_loss_considered": True,
                    "commander_dependence_challenge_considered": True,
                    "whole_deck_constraints_checked_before_simulation": True,
                },
                "automatic_application": False,
            }

        return self._invoke("generate_candidate_swaps", request, work, deck_ids=(request.deck_id,))

'''
service, count = re.subn(
    r"    def generate_candidate_swaps\(self, request: GenerateCandidateSwapsInput\) -> ToolResponse:.*?(?=    def generate_candidate_packages)",
    generate_method,
    service,
    count=1,
    flags=re.S,
)
if count != 1:
    raise RuntimeError("generate_candidate_swaps replacement failed")
# Wire cohort fields into public diagnose.
service = service.replace(
    "facade.diagnose_next_experiment(request.comparison)",
    "facade.diagnose_next_experiment(\n"
    "                    request.comparison,\n"
    "                    cohort_comparisons=request.cohort_comparisons,\n"
    "                    opponent_evidence_quality=request.opponent_evidence_quality,\n"
    "                    failure_mode_metrics=request.failure_mode_metrics,\n"
    "                )",
    1,
)
write("src/commander_lab/tools/service.py", service)

# Version: additive public diagnose/status contract -> minor release.
replace_once("pyproject.toml", 'version = "1.17.1"', 'version = "1.18.0"')
replace_once("src/commander_lab/__init__.py", '__version__ = "1.17.1"', '__version__ = "1.18.0"')
for test_path in (ROOT / "tests").rglob("*.py"):
    text = test_path.read_text(encoding="utf-8")
    if '"1.17.1"' in text or "'1.17.1'" in text:
        text = text.replace('"1.17.1"', '"1.18.0"').replace("'1.17.1'", "'1.18.0'")
        test_path.write_text(text, encoding="utf-8")
changelog = read("CHANGELOG.md")
write(
    "CHANGELOG.md",
    "## 1.18.0 - 2026-08-12\n\n"
    "- Add diverse package/role-aware cut hypotheses to the RogShai decision frontier.\n"
    "- Make DecisionInformationState precision-ceiling aware and cohort-informativeness aware.\n"
    "- Reuse exact paired seed prefixes without changing structural simulation semantics.\n"
    "- Preserve material semantic conflicts and propagate semantic evidence hashes.\n\n"
    + changelog,
)

# Regression tests.
write(
    "tests/unit/test_decision_quality_1180.py",
    r'''
from __future__ import annotations

from commander_lab.decision_information import (
    DecisionInformationStatus,
    build_decision_information_state,
)
from commander_lab.model_informativeness import assess_model_informativeness
from commander_lab.models import DataQuality
from commander_lab.semantic_evidence import (
    DecisionMateriality,
    SemanticConfidence,
    SemanticEvidenceRecord,
    SemanticEvidenceType,
    semantic_evidence_summary,
)


def _comparison(low: float, high: float, effect: float = 0.0, *, iterations: int = 64):
    return {
        "status": "completed",
        "paired": {
            "placement_improvement": effect,
            "confidence_interval": [low, high],
            "monte_carlo_standard_error": abs(high - low) / 4,
        },
        "precision_context": {
            "current_iterations": iterations,
            "preregistered_precision_ceiling": 1024,
            "additional_precision_authorized": False,
        },
    }


def test_decision_information_routes_material_states_and_ceiling():
    assert build_decision_information_state(_comparison(0.03, 0.08, 0.05)).status == DecisionInformationStatus.STOP_WITH_PREFERENCE
    assert build_decision_information_state(_comparison(-0.08, -0.03, -0.05)).status == DecisionInformationStatus.STOP
    assert build_decision_information_state(_comparison(-0.01, 0.01)).status == DecisionInformationStatus.NO_MATERIAL_DECISION_DIFFERENCE
    assert build_decision_information_state(_comparison(-0.04, 0.05, iterations=512)).status == DecisionInformationStatus.MORE_SIMULATIONS_USEFUL
    assert build_decision_information_state(_comparison(-0.04, 0.05, iterations=1024)).status == DecisionInformationStatus.PRECISION_CEILING_REACHED


def test_model_information_limit_preempts_more_seed_work_when_cohort_is_broadly_nonseparable():
    rows = tuple({"confidence_interval": [-0.05, 0.05]} for _ in range(10))
    info = assess_model_informativeness(
        baseline_place_1_share=0.4,
        seat_results=None,
        variant_comparisons=rows,
        failure_mode_metrics=(),
    ).as_dict()
    assert info["status"] == "MODEL_INFORMATION_LIMIT"
    state = build_decision_information_state(
        _comparison(-0.05, 0.05, iterations=512), model_informativeness=info
    )
    assert state.status == DecisionInformationStatus.MODEL_NEEDS_DIFFERENT_METRIC


def test_opponent_and_tactical_routes_remain_distinct():
    comparison = _comparison(-0.04, 0.05, iterations=256)
    opponent = build_decision_information_state(comparison, scenario_spread=0.2)
    assert opponent.status == DecisionInformationStatus.OPPONENT_UNCERTAINTY_DOMINATES
    tactical = build_decision_information_state(comparison, tactical_evidence_required=True)
    assert tactical.status == DecisionInformationStatus.TACTICAL_EVIDENCE_NEEDED


def test_material_semantic_conflict_preserves_both_claims_and_defers():
    common = dict(
        card_id="card-x",
        oracle_name="Conflict Card",
        feature="decision_feature_x",
        confidence=SemanticConfidence.HIGH,
        source_version="1",
        extraction_method="fixture",
        review_status="unreviewed",
        decision_materiality=DecisionMateriality.HIGH,
    )
    left = SemanticEvidenceRecord(
        **common, value=True, evidence_type=SemanticEvidenceType.CANONICAL_PROJECT, source_id="source-a"
    )
    right = SemanticEvidenceRecord(
        **common, value=False, evidence_type=SemanticEvidenceType.PROJECT_DERIVED, source_id="source-b"
    )
    summary = semantic_evidence_summary(
        oracle_name="Conflict Card", profile=None, additional_records=(left, right)
    )
    conflict = summary["semantic_conflict"]
    assert conflict["material_conflict"] is True
    assert conflict["requires_semantic_adjudication"] is True
    assert conflict["automatic_promotion"] is False
    assert conflict["automatic_rejection"] is False
    assert len(conflict["records"]) == 2
    assert summary["needs_targeted_adjudication"] is True
    assert len(summary["semantic_evidence_hash"]) == 64
'''.lstrip(),
)

write(
    "tests/integration/test_priority_prefix_and_frontier_1180.py",
    r'''
from __future__ import annotations

from commander_lab.models.tooling import GenerateCandidateSwapsInput
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.tools import CommanderToolService


def test_frontier_reports_cut_composition_and_preserves_candidate_recall(repo_root):
    service = CommanderToolService(repo_root)
    response = service.generate_candidate_swaps(
        GenerateCandidateSwapsInput(deck_id="rogshai/current", max_candidates=50)
    )
    assert response.status.value == "completed"
    result = response.result
    assert result["candidate_recall"] == 1.0
    assert result["cut_frontier_gate"]["scalar_profile_score_is_sole_authority"] is False
    assert result["cut_frontier_gate"]["whole_deck_constraints_checked_before_simulation"] is True
    composition = result["frontier_composition"]
    assert composition["pair_count"] == result["count"]
    assert composition["unique_cut_count"] > 1
    assert 0.0 < composition["top_cut_pair_share"] <= 1.0
    assert all(row["semantic_evidence_hash"] for row in result["candidates"])


def test_prefix_reuse_is_exactly_equivalent_to_monolithic(repo_root, tmp_path):
    pair = {"deck_id": "rogshai/current", "remove": "Preordain", "add_candidate_id": "rogshai/opt-smoke"}
    staged = PriorityWorkflowFacade(repo_root, result_cache_path=tmp_path / "staged.sqlite3")
    first = staged.compare_validate(**pair, iterations=8, seed=2026081203, max_turns=20, workers=1)
    assert first["status"] == "completed"
    second = staged.compare_validate(**pair, iterations=16, seed=2026081203, max_turns=20, workers=1)
    assert second["incremental_execution"]["reused_prefix_count"] == 8
    assert second["incremental_execution"]["incremental_simulated_count"] == 8

    clean = PriorityWorkflowFacade(repo_root, result_cache_path=tmp_path / "clean.sqlite3")
    monolithic = clean.compare_validate(**pair, iterations=16, seed=2026081203, max_turns=20, workers=1)
    assert monolithic["incremental_execution"]["reused_prefix_count"] == 0
    assert second["paired"] == monolithic["paired"]
    assert second["paired_observations"] == monolithic["paired_observations"]
    assert second["cache_provenance"]["exact_seed_set_sha256"] == monolithic["cache_provenance"]["exact_seed_set_sha256"]
'''.lstrip(),
)

# Materializer cleanup and sanity assertions happen in the workflow after validation.
print("decision-quality materialization complete")
