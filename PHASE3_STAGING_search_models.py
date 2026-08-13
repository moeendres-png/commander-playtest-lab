from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from commander_lab.models import FrozenModel

from .models import PolicyId


class WholeDeckNeighborhood(StrEnum):
    ROLE_PACKAGE = "role_package"
    ENGINE_PACKAGE = "engine_package"
    FINISH_PACKAGE = "finish_package"
    INTERACTION_PACKAGE = "interaction_package"
    CURVE_BAND = "curve_band"
    MANA_PACKAGE = "mana_package"
    LAND_NONLAND_BALANCE = "land_nonland_balance"
    BASIC_NONBASIC_MIX = "basic_nonbasic_mix"


class ManaBasePolicy(FrozenModel):
    preferred_land_minimum: int = Field(ge=0, le=98)
    preferred_land_maximum: int = Field(ge=0, le=98)
    hard_land_minimum: int = Field(ge=0, le=98)
    hard_land_maximum: int = Field(ge=0, le=98)
    preferred_basic_minimum: int = Field(default=0, ge=0, le=98)
    preferred_basic_maximum: int = Field(default=98, ge=0, le=98)
    minimum_white_sources: int = Field(default=1, ge=0, le=98)
    minimum_blue_sources: int = Field(default=1, ge=0, le=98)
    minimum_red_sources: int = Field(default=1, ge=0, le=98)
    preferred_t1_untapped_sources: int = Field(default=12, ge=0, le=98)
    preferred_flexible_sources: int = Field(default=8, ge=0, le=98)
    preferred_maximum_tapped_lands: int = Field(default=10, ge=0, le=98)
    utility_land_budget: int = Field(default=8, ge=0, le=98)

    @model_validator(mode="after")
    def valid_mana_ranges(self) -> ManaBasePolicy:
        if self.preferred_land_minimum > self.preferred_land_maximum:
            raise ValueError("preferred land minimum exceeds maximum")
        if self.hard_land_minimum > self.hard_land_maximum:
            raise ValueError("hard land minimum exceeds maximum")
        if self.preferred_basic_minimum > self.preferred_basic_maximum:
            raise ValueError("preferred basic minimum exceeds maximum")
        return self


class WholeDeckMutation(FrozenModel):
    neighborhood: WholeDeckNeighborhood
    removed: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    changed_slots: int = Field(default=0, ge=0, le=98)
    accepted: bool = False
    accepted_worse: bool = False
    objective_delta: float | None = None


class WholeDeckHardGate(FrozenModel):
    valid: bool
    issues: tuple[str, ...] = ()
    card_count: int
    land_count: int
    basic_count: int
    physical_inventory_checked: bool = True
    commander_configuration_checked: bool = True
    color_identity_checked: bool = True


class WholeDeckVariant(FrozenModel):
    variant_id: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    mainboard: tuple[str, ...]
    policy_id: PolicyId
    policy_version: str
    seed: int = Field(ge=0)
    parent_variant_id: str | None = None
    mutation: WholeDeckMutation | None = None
    feature_vector: dict[str, object] = Field(default_factory=dict)
    mana: dict[str, object] = Field(default_factory=dict)
    objective_prior: float
    meta_distance: dict[str, float | None] = Field(default_factory=dict)
    hard_gate: WholeDeckHardGate
    provenance: dict[str, object] = Field(default_factory=dict)


class WholeDeckSearchConfig(FrozenModel):
    seed: int = Field(default=20260813, ge=0)
    diversified_starts: int = Field(default=3, ge=0, le=32)
    max_steps_per_start: int = Field(default=24, ge=1, le=500)
    minimum_neighborhood_changes: int = Field(default=6, ge=2, le=30)
    maximum_neighborhood_changes: int = Field(default=16, ge=6, le=40)
    archive_limit: int = Field(default=2000, ge=32, le=100_000)
    finalist_limit: int = Field(default=4, ge=1, le=32)
    initial_temperature: float = Field(default=0.20, gt=0.0, le=10.0)
    final_temperature: float = Field(default=0.01, gt=0.0, le=10.0)
    include_current_control_arm: bool = True

    @model_validator(mode="after")
    def valid_search_config(self) -> WholeDeckSearchConfig:
        if self.minimum_neighborhood_changes > self.maximum_neighborhood_changes:
            raise ValueError("minimum neighborhood changes exceeds maximum")
        if self.final_temperature > self.initial_temperature:
            raise ValueError("final temperature exceeds initial temperature")
        return self


class WholeDeckSearchResult(FrozenModel):
    campaign_id: str
    policy_id: PolicyId
    policy_version: str
    seed: int
    data_snapshot_hash: str
    candidate_count: int
    start_variant_ids: tuple[str, ...]
    explored_variant_ids: tuple[str, ...]
    finalist_variant_ids: tuple[str, ...]
    variants: tuple[WholeDeckVariant, ...]
    control_variant_id: str | None = None
    control_used_as_search_prior: bool = False
    automatically_applied: Literal[False] = False
