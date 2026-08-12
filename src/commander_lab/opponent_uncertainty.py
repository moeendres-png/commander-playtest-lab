from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from statistics import fmean
from typing import Any, Iterable

from commander_lab.storage.run_identity import sha256_run_value


class OpponentScenarioEvidence(StrEnum):
    OBSERVED = "OBSERVED"
    PLAUSIBLE_ENVELOPE = "PLAUSIBLE_ENVELOPE"
    STRESS = "STRESS"


@dataclass(frozen=True)
class OpponentScenarioEnvelope:
    scenario_id: str
    opponent_entity_id: str
    evidence_class: OpponentScenarioEvidence
    assumptions: tuple[tuple[str, str], ...] = ()
    source_ids: tuple[str, ...] = ()
    canonical_observation: bool = False

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.opponent_entity_id:
            raise ValueError("scenario_id and opponent_entity_id are required")
        if self.evidence_class == OpponentScenarioEvidence.OBSERVED:
            if not self.canonical_observation:
                raise ValueError("OBSERVED scenario must be marked canonical_observation=true")
            if self.assumptions:
                raise ValueError("OBSERVED scenario cannot contain synthetic assumptions")
        elif self.canonical_observation:
            raise ValueError("synthetic scenario must never be marked canonical observation")

    @property
    def scenario_hash(self) -> str:
        return sha256_run_value(asdict(self))

    def as_dict(self) -> dict[str, Any]:
        return {"scenario_hash": self.scenario_hash, **asdict(self)}


@dataclass(frozen=True)
class OpponentUncertaintySummary:
    nominal_result: float | None
    worst_plausible_result: float | None
    scenario_regret: float | None
    lower_tail_result: float | None
    rank_stability_across_scenarios: float | None
    scenario_spread: float | None
    scenario_count: int
    evidence_classes: tuple[str, ...]
    evidence_class: str = "synthetic_assumption_sensitivity"
    truth_boundary: str = "scenario envelopes are sensitivity assumptions, not local observations"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_scenario_results(
    rows: Iterable[tuple[OpponentScenarioEnvelope, float]],
    *,
    nominal_scenario_id: str | None = None,
) -> OpponentUncertaintySummary:
    materialized = tuple(rows)
    values = [float(value) for _scenario, value in materialized]
    nominal: float | None = None
    if nominal_scenario_id is not None:
        for scenario, value in materialized:
            if scenario.scenario_id == nominal_scenario_id:
                nominal = float(value)
                break
        if nominal is None:
            raise ValueError(f"nominal scenario not found: {nominal_scenario_id}")
    observed = [
        float(value)
        for scenario, value in materialized
        if scenario.evidence_class == OpponentScenarioEvidence.OBSERVED
    ]
    if nominal is None and observed:
        nominal = fmean(observed)
    plausible = [
        float(value)
        for scenario, value in materialized
        if scenario.evidence_class
        in {OpponentScenarioEvidence.OBSERVED, OpponentScenarioEvidence.PLAUSIBLE_ENVELOPE}
    ]
    worst = min(plausible) if plausible else None
    regret = (nominal - worst) if nominal is not None and worst is not None else None
    lower_tail = min(values) if values else None
    spread = max(values) - min(values) if values else None
    if not values:
        stability = None
    else:
        signs = [value >= 0.0 for value in values]
        stability = max(sum(signs), len(signs) - sum(signs)) / len(signs)
    return OpponentUncertaintySummary(
        nominal_result=nominal,
        worst_plausible_result=worst,
        scenario_regret=regret,
        lower_tail_result=lower_tail,
        rank_stability_across_scenarios=stability,
        scenario_spread=spread,
        scenario_count=len(values),
        evidence_classes=tuple(sorted({scenario.evidence_class.value for scenario, _ in materialized})),
    )


__all__ = [
    "OpponentScenarioEnvelope",
    "OpponentScenarioEvidence",
    "OpponentUncertaintySummary",
    "summarize_scenario_results",
]
