from __future__ import annotations

from commander_lab.models import CardRole, DataQuality, StructuralCardProfile
from commander_lab.whole_deck.search import SearchCard


def profile(name: str, *, mv: float = 2.0, roles=frozenset(), is_land: bool = False, produces=frozenset(), package_ids=frozenset()):
    actual_roles = roles
    if is_land:
        source_role = next(role for role in CardRole if role.value.endswith("source"))
        actual_roles = frozenset(set(actual_roles) | {source_role})
    return StructuralCardProfile(
        oracle_name=name,
        mana_value=mv,
        roles=actual_roles,
        role_strengths={role: 1.0 for role in actual_roles},
        color_identity=frozenset(produces),
        produces_colors=produces,
        is_land=is_land,
        is_permanent=True,
        commander_synergy=0.0,
        floor_value=0.5,
        immediate_impact=0.5,
        turn_cycle_risk=0.5,
        multiplayer_scaling=0.0,
        package_ids=package_ids,
        source_quality=DataQuality.PROJECT_VERIFIED,
    )


def card(name: str, *, profile: StructuralCardProfile, quantity: int = 1, basic: bool = False, utility: float | None = None) -> SearchCard:
    return SearchCard(
        oracle_name=name,
        profile=profile,
        available_quantity=quantity,
        is_basic=basic,
        semantic_evidence="fixture_verified",
        semantic_known=True,
        color_identity=frozenset(color.value for color in profile.color_identity),
        search_utility_override=utility,
    )
