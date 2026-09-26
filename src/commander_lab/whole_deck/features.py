from __future__ import annotations

from typing import Literal

from commander_lab.models import CardRole, DataQuality, StructuralCardProfile
from commander_lab.optimization.experiments import profile_score
from commander_lab.storage import sha256_value

from .models import (
    CardFeatureConfidence,
    CardFeatureVector,
    ContextualCardUtility,
    DeckDesignPolicy,
)


def card_feature_vector(card: StructuralCardProfile) -> CardFeatureVector:
    payload = {
        "oracle_name": card.oracle_name,
        "mana_value": card.mana_value,
        "roles": tuple(sorted(role.value for role in card.roles)),
        "role_strengths": dict(
            sorted((role.value, value) for role, value in card.role_strengths.items())
        ),
        "mechanic_tags": tuple(sorted(tag.value for tag in card.mechanic_tags)),
        "color_requirements": dict(
            sorted((color.value, value) for color, value in card.color_requirements.items())
        ),
        "color_identity": tuple(sorted(color.value for color in card.color_identity)),
        "produces_colors": tuple(sorted(color.value for color in card.produces_colors)),
        "is_land": card.is_land,
        "is_permanent": card.is_permanent,
        "is_creature": card.is_creature,
        "commander_synergy": card.commander_synergy,
        "floor_value": card.floor_value,
        "immediate_impact": card.immediate_impact,
        "turn_cycle_risk": card.turn_cycle_risk,
        "multiplayer_scaling": card.multiplayer_scaling,
        "package_ids": tuple(sorted(card.package_ids)),
    }
    return CardFeatureVector.model_validate({**payload, "feature_hash": sha256_value(payload)})


def card_feature_confidence(card: StructuralCardProfile) -> CardFeatureConfidence:
    if card.source_quality in {DataQuality.AUTHORITATIVE, DataQuality.PROJECT_VERIFIED}:
        confidence = 0.95 if card.sources else 0.9
        label: Literal[
            "authoritative_or_verified_structural_profile",
            "project_inferred_structural_profile",
            "synthetic_or_unknown_structural_profile",
        ] = "authoritative_or_verified_structural_profile"
    elif card.source_quality == DataQuality.PROJECT_INFERRED:
        confidence = 0.65 if card.sources else 0.55
        label = "project_inferred_structural_profile"
    else:
        confidence = 0.25 if card.sources else 0.1
        label = "synthetic_or_unknown_structural_profile"
    return CardFeatureConfidence(
        oracle_name=card.oracle_name,
        source_quality=card.source_quality,
        source_count=len(card.sources),
        confidence=confidence,
        evidence_label=label,
    )


def _role_component(card: StructuralCardProfile, role: CardRole) -> float:
    return card.strength(role)


def contextual_card_utility(
    card: StructuralCardProfile,
    policy: DeckDesignPolicy,
) -> ContextualCardUtility:
    mechanics = {tag.value for tag in card.mechanic_tags}
    components = {
        "profile_prior": profile_score(card),
        "role_strength": sum(card.strength(role) for role in card.roles),
        "floor_value": card.floor_value,
        "immediate_impact": card.immediate_impact,
        "multiplayer_scaling": card.multiplayer_scaling,
        "commander_synergy": card.commander_synergy,
        "commander_independence": 1.0 if "commander_independent" in mechanics else 0.0,
        "rebuild": 1.0 if "rebuild" in mechanics else 0.0,
        "role_compression": max(0.0, float(len(card.roles) - 1)),
        "mana_efficiency": max(0.0, 4.0 - card.mana_value) / 4.0,
        "selection": _role_component(card, CardRole.SELECTION),
        "ramp": _role_component(card, CardRole.RAMP),
        "counter": _role_component(card, CardRole.COUNTER),
        "removal": _role_component(card, CardRole.REMOVAL),
        "protection": _role_component(card, CardRole.PROTECTION),
    }
    weighted_terms = [
        components.get(name, 0.0) * weight for name, weight in policy.contextual_weights.items()
    ]
    utility = sum(weighted_terms)
    confidence = card_feature_confidence(card).confidence
    return ContextualCardUtility(
        oracle_name=card.oracle_name,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        components=components,
        search_utility=utility,
        confidence=confidence,
    )
