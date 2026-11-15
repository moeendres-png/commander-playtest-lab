from __future__ import annotations

from typing import Literal

from pydantic import Field, field_serializer, model_validator

from .common import Color, DataQuality, FrozenModel, SourceRef
from .roles import CardRole, StructuralMechanic

STRUCTURAL_ESTIMATE_TYPE: Literal["structural_model_estimates"] = "structural_model_estimates"


class ConditionalStrength(FrozenModel):
    condition: str
    multiplier: float = Field(default=1.0, ge=0.0, le=4.0)
    notes: str | None = None


class StructuralCardProfile(FrozenModel):
    oracle_name: str = Field(min_length=1)
    mana_value: float = Field(default=3.0, ge=0.0, le=20.0)
    roles: frozenset[CardRole]
    role_strengths: dict[CardRole, float] = Field(default_factory=dict)
    # Narrow Oracle-backed execution parameters.  These are populated only from verified current
    # facts and let the Structural resolver distinguish literal draw/scry shapes without pretending
    # to implement arbitrary card text.
    draw_count: int | None = Field(default=None, ge=1, le=20)
    scry_depth: int | None = Field(default=None, ge=1, le=20)
    timing_window: Literal["sorcery", "instant"] | None = None
    mechanic_tags: frozenset[StructuralMechanic] = frozenset()
    color_requirements: dict[Color, int] = Field(default_factory=dict)
    color_identity: frozenset[Color] = frozenset()
    produces_colors: frozenset[Color] = frozenset()
    is_land: bool = False
    is_permanent: bool = True
    is_creature: bool = False
    base_power: float = Field(default=0.0, ge=0.0, le=30.0)
    commander_synergy: float = Field(default=0.0, ge=0.0, le=2.0)
    floor_value: float = Field(default=0.5, ge=0.0, le=2.0)
    immediate_impact: float = Field(default=0.5, ge=0.0, le=1.5)
    turn_cycle_risk: float = Field(default=0.5, ge=0.0, le=1.0)
    multiplayer_scaling: float = Field(default=0.0, ge=-1.0, le=2.0)
    conditional_strength: tuple[ConditionalStrength, ...] = ()
    package_ids: frozenset[str] = frozenset()
    source_quality: DataQuality = DataQuality.PROJECT_INFERRED
    sources: tuple[SourceRef, ...] = ()
    notes: str | None = None

    @field_serializer("roles", "mechanic_tags", "color_identity", "produces_colors", "package_ids")
    def serialize_sets(self, values: frozenset[object]) -> list[object]:
        return sorted(values, key=lambda value: getattr(value, "value", str(value)))

    @field_serializer("role_strengths")
    def serialize_role_strengths(self, values: dict[CardRole, float]) -> dict[CardRole, float]:
        return dict(sorted(values.items(), key=lambda item: item[0].value))

    @model_validator(mode="after")
    def validate_role_strengths(self) -> StructuralCardProfile:
        missing = set(self.role_strengths) - set(self.roles)
        if missing:
            raise ValueError(f"role strengths reference absent roles: {sorted(missing)}")
        if self.is_land and CardRole.MANA_SOURCE not in self.roles:
            raise ValueError("land profiles must include mana_source")
        return self

    def strength(self, role: CardRole) -> float:
        if role not in self.roles:
            return 0.0
        return self.role_strengths.get(role, 1.0)


class StructuralDeckProfile(FrozenModel):
    deck_id: str
    deck_hash: str
    commander_names: tuple[str, ...]
    cards: tuple[StructuralCardProfile, ...]
    commander_base_costs: dict[str, float]
    commander_base_power: dict[str, float] = Field(default_factory=dict)
    commander_strategy: str = "generic"
    data_snapshot_hash: str

    @model_validator(mode="after")
    def validate_commander_profiles(self) -> StructuralDeckProfile:
        if not self.commander_names:
            raise ValueError("structural deck profile requires at least one commander")
        if len(self.commander_names) != len(set(self.commander_names)):
            raise ValueError("commander names must be unique")
        missing = set(self.commander_names) - set(self.commander_base_costs)
        if missing:
            raise ValueError(f"missing commander base costs: {sorted(missing)}")
        names = [card.oracle_name for card in self.cards]
        invalid_counts = {
            commander: names.count(commander)
            for commander in self.commander_names
            if names.count(commander) != 1
        }
        if invalid_counts:
            raise ValueError(
                f"each commander must have exactly one structural card profile: {invalid_counts}"
            )
        return self


def validate_commander_deck_profile(
    profile: StructuralDeckProfile, *, expected_card_count: int = 100
) -> StructuralDeckProfile:
    if expected_card_count < len(profile.commander_names):
        raise ValueError("expected card count cannot be smaller than commander count")
    if len(profile.cards) != expected_card_count:
        raise ValueError(
            f"structural Commander profile {profile.deck_id} contains {len(profile.cards)} cards; "
            f"expected {expected_card_count} including commanders"
        )
    commander_set = set(profile.commander_names)
    library_count = sum(card.oracle_name not in commander_set for card in profile.cards)
    expected_library_count = expected_card_count - len(profile.commander_names)
    if library_count != expected_library_count:
        raise ValueError(
            f"structural Commander profile {profile.deck_id} contains {library_count} library "
            f"profiles; expected {expected_library_count}"
        )
    return profile
