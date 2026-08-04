from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import Color, FrozenModel
from .pilots import PilotStrength
from .roles import CardRole
from .tooling import SimulationInput, VariantSwap


class OptimizationObjective(StrEnum):
    FOUR_PLAYER_PERFORMANCE = "four_player_performance"
    WORST_QUARTILE = "worst_quartile"
    COMMANDER_INDEPENDENCE = "commander_independence"
    REBUILD = "rebuild"
    CLOSING_POWER = "closing_power"
    MATCHUP_ROBUSTNESS = "matchup_robustness"
    PHYSICAL_ALLOCATION = "physical_allocation"


class OptimizationConstraints(FrozenModel):
    exact_card_count: int = Field(default=100, ge=1, le=500)
    singleton: bool = True
    allowed_colors: frozenset[Color] = frozenset()
    role_minima: dict[CardRole, int] = Field(default_factory=dict)
    minimum_lands: int = Field(default=0, ge=0, le=100)
    maximum_lands: int = Field(default=100, ge=0, le=100)
    minimum_colored_sources: dict[Color, int] = Field(default_factory=dict)
    maximum_average_nonland_mana_value: float = Field(default=99.0, ge=0.0, le=20.0)
    maximum_high_mana_value_cards: int = Field(default=100, ge=0, le=100)
    high_mana_value_threshold: float = Field(default=5.0, ge=0.0, le=20.0)
    require_verified_inventory: bool = True
    simultaneous_deck_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_ranges(self) -> "OptimizationConstraints":
        if self.minimum_lands > self.maximum_lands:
            raise ValueError("minimum_lands cannot exceed maximum_lands")
        return self


class ConstraintIssue(FrozenModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    context: dict[str, Any] = Field(default_factory=dict)


class ConstraintReport(FrozenModel):
    valid: bool
    issues: tuple[ConstraintIssue, ...] = ()
    metrics: dict[str, Any] = Field(default_factory=dict)


class ObjectiveVector(FrozenModel):
    four_player_performance: float
    worst_quartile: float
    commander_independence: float
    rebuild: float
    closing_power: float
    matchup_robustness: float
    physical_allocation: float

    def as_maximize_dict(self) -> dict[str, float]:
        return self.model_dump(mode="json")


class OptimizationVariant(FrozenModel):
    variant_id: str
    deck_id: str
    deck_hash: str
    swaps: tuple[VariantSwap, ...]
    structural_rationale: tuple[str, ...]
    affected_matchups: tuple[str, ...]
    constraint_report: ConstraintReport
    objectives: ObjectiveVector | None = None
    screening_score: float | None = None
    search_method: str
    parent_variant_id: str | None = None
    automatically_applied: Literal[False] = False


class CandidatePackage(FrozenModel):
    package_id: str
    swaps: tuple[VariantSwap, ...]
    rationale: str | None = None

    @model_validator(mode="after")
    def nonempty_package(self) -> "CandidatePackage":
        if not self.swaps:
            raise ValueError("package must contain at least one swap")
        if len({swap.remove for swap in self.swaps}) != len(self.swaps):
            raise ValueError("package cannot remove the same card twice")
        if len({swap.add_candidate_id for swap in self.swaps}) != len(self.swaps):
            raise ValueError("package cannot add the same candidate twice")
        return self


class LocalSearchInput(SimulationInput):
    deck_id: str
    candidate_ids: tuple[str, ...] = ()
    max_steps: int = Field(default=3, ge=1, le=12)
    cuts_per_step: int = Field(default=8, ge=1, le=30)
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro", "synthetic/control", "synthetic/engine"
    )
    constraints: OptimizationConstraints | None = None


class BeamSearchInput(SimulationInput):
    deck_id: str
    candidate_ids: tuple[str, ...] = ()
    beam_width: int = Field(default=4, ge=1, le=32)
    depth: int = Field(default=2, ge=1, le=5)
    max_cuts_per_node: int = Field(default=6, ge=1, le=20)
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro", "synthetic/control", "synthetic/engine"
    )
    constraints: OptimizationConstraints | None = None


class PackageSearchInput(SimulationInput):
    deck_id: str
    packages: tuple[CandidatePackage, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    max_package_size: int = Field(default=2, ge=2, le=5)
    max_packages: int = Field(default=12, ge=1, le=100)
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro", "synthetic/control", "synthetic/engine"
    )
    constraints: OptimizationConstraints | None = None


class ParetoFrontInput(SimulationInput):
    deck_id: str
    variants: tuple[tuple[VariantSwap, ...], ...]
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro", "synthetic/control", "synthetic/engine"
    )
    holdout_pods: tuple[tuple[str, ...], ...] = (
        ("synthetic/control", "synthetic/control", "synthetic/engine"),
        ("synthetic/aggro", "synthetic/aggro", "synthetic/control"),
    )
    constraints: OptimizationConstraints | None = None


class ShapleyInput(SimulationInput):
    deck_id: str
    card_names: tuple[str, ...]
    permutations: int = Field(default=128, ge=8, le=4096)
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro", "synthetic/control", "synthetic/engine"
    )

    @model_validator(mode="after")
    def validate_cards(self) -> "ShapleyInput":
        if not 2 <= len(self.card_names) <= 12:
            raise ValueError("Shapley approximation requires 2 to 12 cards")
        if len(set(self.card_names)) != len(self.card_names):
            raise ValueError("card_names must be unique")
        return self


class OptimizationValidationInput(SimulationInput):
    deck_id: str
    swaps: tuple[VariantSwap, ...]
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro", "synthetic/control", "synthetic/engine"
    )
    holdout_pods: tuple[tuple[str, ...], ...] = (
        ("synthetic/control", "synthetic/control", "synthetic/engine"),
        ("synthetic/aggro", "synthetic/aggro", "synthetic/control"),
    )
    sensitivity_seeds: tuple[int, ...] = (20260804, 20260805, 20260806)
    sensitivity_strengths: tuple[PilotStrength, ...] = (
        PilotStrength.AVERAGE,
        PilotStrength.STRONG,
        PilotStrength.NEAR_OPTIMAL_HEURISTIC,
    )
    minimum_place_delta: float = Field(default=0.01, ge=-3.0, le=3.0)
    constraints: OptimizationConstraints | None = None
