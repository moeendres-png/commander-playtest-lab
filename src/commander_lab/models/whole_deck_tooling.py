from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import FrozenModel


class WholeDeckDecisionPrepareInput(FrozenModel):
    deck_id: str = "rogshai/current"
    design_mode: Literal["swap", "whole_deck"] = "swap"
    candidate_limit: int = Field(default=25, ge=1, le=250)
    whole_deck_policies: tuple[str, ...] = (
        "OWNED_POOL_NEUTRAL",
        "META_LIGHT",
        "LOW_LAND_HIGH_VELOCITY",
        "RESILIENT_COMMANDER_INDEPENDENT",
        "INTERACTION_HEAVY_LOCAL_META",
    )
    design_seed: int = Field(default=2026081401, ge=0)
    whole_deck_diversified_starts: int = Field(default=2, ge=0, le=8)
    whole_deck_steps_per_start: int = Field(default=8, ge=1, le=100)
    whole_deck_finalists_per_policy: int = Field(default=2, ge=1, le=8)
    whole_deck_max_variants: int = Field(default=10, ge=1, le=64)
    whole_deck_output_name: str = "whole_deck_design.json"


class WholeDeckDecisionRunInput(FrozenModel):
    deck_id: str = "rogshai/current"
    comparison_mode: Literal["swap", "whole_deck"] = "swap"
    remove: str | None = None
    add_candidate_id: str | None = None
    prepared_design_path: str | None = None
    whole_deck_variant_id: str | None = None
    iterations: int = Field(default=64, ge=1, le=10_000)
    seed: int = Field(default=2026082103, ge=0)
    max_turns: int = Field(default=35, ge=1, le=500)
    workers: int = Field(default=1, ge=1, le=64)
    max_simulation_seconds: float | None = Field(default=None, gt=0.0, le=600.0)

    @model_validator(mode="after")
    def validate_comparison_mode(self) -> WholeDeckDecisionRunInput:
        if self.comparison_mode == "swap":
            if not self.remove or not self.add_candidate_id:
                raise ValueError("swap comparison requires remove and add_candidate_id")
            if self.prepared_design_path or self.whole_deck_variant_id:
                raise ValueError("swap mode must not provide Whole-Deck artifact fields")
        else:
            if not self.prepared_design_path or not self.whole_deck_variant_id:
                raise ValueError(
                    "whole_deck comparison requires prepared_design_path and whole_deck_variant_id"
                )
            if self.remove or self.add_candidate_id:
                raise ValueError("whole_deck mode must not provide swap fields")
        return self
