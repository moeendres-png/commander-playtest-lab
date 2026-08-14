from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from commander_lab.models.common import FrozenModel


class DeckDesignPolicy(StrEnum):
    CURRENT_CONTROL = "current_control"
    OWNED_POOL_NEUTRAL = "owned_pool_neutral"
    META_LIGHT = "meta_light"
    META_MEDIUM = "meta_medium"
    META_HIGH = "meta_high"
    MAX_FEASIBLE_META_SHAPE = "max_feasible_meta_shape"
    LOW_LAND_HIGH_VELOCITY = "low_land_high_velocity"
    RESILIENT_COMMANDER_INDEPENDENT = "resilient_commander_independent"
    INTERACTION_HEAVY_LOCAL_META = "interaction_heavy_local_meta"


class WholeDeckFeatureVector(FrozenModel):
    lands: int = Field(ge=0, le=100)
    basics: int = Field(ge=0, le=100)
    nonbasics: int = Field(ge=0, le=100)
    average_nonland_mana_value: float = Field(ge=0.0)
    mv_zero_one: int = Field(ge=0)
    mv_two: int = Field(ge=0)
    ramp: int = Field(ge=0)
    draw: int = Field(ge=0)
    sustained_draw: int = Field(ge=0)
    selection: int = Field(ge=0)
    removal: int = Field(ge=0)
    stack_interaction: int = Field(ge=0)
    protection: int = Field(ge=0)
    wipes: int = Field(ge=0)
    graveyard_interaction: int = Field(ge=0)
    recursion: int = Field(ge=0)
    engines: int = Field(ge=0)
    compact_finish: int = Field(ge=0)
    role_compression_total: int = Field(ge=0)
    commander_independent_value: int = Field(ge=0)
    hard_threat_axes_covered: int = Field(ge=0)
    soft_threat_axes_covered: int = Field(ge=0)
    white_sources: int = Field(ge=0)
    blue_sources: int = Field(ge=0)
    red_sources: int = Field(ge=0)
    definitely_tapped_lands: int = Field(ge=0)
    conditionally_tapped_lands: int = Field(ge=0)


class WholeDeckVariant(FrozenModel):
    variant_id: str
    policy: DeckDesignPolicy
    seed: int = Field(ge=0)
    mainboard: tuple[str, ...]
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    knowledge_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    feature_vector: WholeDeckFeatureVector
    policy_utility: float
    meta_distance: float | None = None
    package_counts: dict[str, int] = Field(default_factory=dict)
    evidence_classes: tuple[str, ...] = (
        "derived_search_knowledge",
        "structural_model_input_candidate",
    )
    current_control_visible_during_construction: bool = False
    automatically_applied: bool = False

    @model_validator(mode="after")
    def validate_mainboard(self) -> WholeDeckVariant:
        if len(self.mainboard) != 98:
            raise ValueError("RogShai WholeDeckVariant mainboard must contain exactly 98 cards")
        nonbasics = [
            card
            for card in self.mainboard
            if card not in {"Plains", "Island", "Mountain"}
        ]
        if len(nonbasics) != len(set(nonbasics)):
            raise ValueError("nonbasic cards in a WholeDeckVariant must be singleton")
        return self
