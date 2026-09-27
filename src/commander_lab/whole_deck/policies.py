from __future__ import annotations

from commander_lab.models import FormatBand

from .models import DeckDesignPolicy, PolicyId, TargetCorridor


def _corridor(
    low: float,
    high: float,
    *,
    weight: float = 1.0,
    hard_low: float | None = None,
    hard_high: float | None = None,
) -> TargetCorridor:
    return TargetCorridor(
        preferred_minimum=low,
        preferred_maximum=high,
        weight=weight,
        hard_minimum=hard_low,
        hard_maximum=hard_high,
    )


_POLICY_REGISTRY: dict[PolicyId, DeckDesignPolicy] = {
    PolicyId.CURRENT_CONTROL: DeckDesignPolicy(
        policy_id=PolicyId.CURRENT_CONTROL,
        target_corridors={
            "land_count": _corridor(36, 38, hard_low=36, hard_high=38),
            "average_nonland_mv": _corridor(1.8, 2.5, hard_high=2.5),
        },
        contextual_weights={"floor_value": 1.0, "commander_synergy": 1.0},
        notes="Control policy for backward-compatible current-deck shape comparisons.",
    ),
    PolicyId.OWNED_POOL_NEUTRAL: DeckDesignPolicy(
        policy_id=PolicyId.OWNED_POOL_NEUTRAL,
        target_corridors={"land_count": _corridor(33, 39)},
        contextual_weights={
            "role_strength": 1.0,
            "floor_value": 1.0,
            "immediate_impact": 1.0,
            "multiplayer_scaling": 1.0,
            "commander_synergy": 0.7,
            "commander_independence": 0.8,
        },
        functional_meta_weight=0.0,
        notes="No meta-nearness quality bonus; construction starts from the owned pool.",
    ),
    PolicyId.META_LIGHT: DeckDesignPolicy(
        policy_id=PolicyId.META_LIGHT,
        target_corridors={"land_count": _corridor(33, 38)},
        contextual_weights={"role_strength": 1.0, "floor_value": 1.0},
        meta_band_weights={
            FormatBand.NORMAL_FOUR_PLAYER: 1.0,
            FormatBand.HIGH_POWER: 0.75,
            FormatBand.CEDH_TOURNAMENT: 0.35,
        },
        functional_meta_weight=0.20,
    ),
    PolicyId.META_MEDIUM: DeckDesignPolicy(
        policy_id=PolicyId.META_MEDIUM,
        target_corridors={"land_count": _corridor(32, 37)},
        contextual_weights={"role_strength": 1.0, "floor_value": 1.0, "role_compression": 0.5},
        meta_band_weights={
            FormatBand.NORMAL_FOUR_PLAYER: 0.8,
            FormatBand.HIGH_POWER: 1.0,
            FormatBand.CEDH_TOURNAMENT: 0.65,
        },
        functional_meta_weight=0.45,
    ),
    PolicyId.META_HIGH: DeckDesignPolicy(
        policy_id=PolicyId.META_HIGH,
        target_corridors={"land_count": _corridor(30, 36)},
        contextual_weights={
            "role_strength": 1.0,
            "floor_value": 1.0,
            "immediate_impact": 1.0,
            "role_compression": 0.8,
        },
        meta_band_weights={
            FormatBand.NORMAL_FOUR_PLAYER: 0.45,
            FormatBand.HIGH_POWER: 1.0,
            FormatBand.CEDH_TOURNAMENT: 1.0,
        },
        functional_meta_weight=0.80,
    ),
    PolicyId.MAX_FEASIBLE_META_SHAPE: DeckDesignPolicy(
        policy_id=PolicyId.MAX_FEASIBLE_META_SHAPE,
        target_corridors={"land_count": _corridor(28, 35)},
        contextual_weights={
            "role_strength": 1.0,
            "immediate_impact": 1.0,
            "role_compression": 1.0,
            "mana_efficiency": 1.0,
        },
        meta_band_weights={
            FormatBand.HIGH_POWER: 1.0,
            FormatBand.CEDH_TOURNAMENT: 1.0,
        },
        functional_meta_weight=1.0,
        notes="Approach functional high-power/cEDH shape only where the owned pool can support it.",
    ),
    PolicyId.LOW_LAND_HIGH_VELOCITY: DeckDesignPolicy(
        policy_id=PolicyId.LOW_LAND_HIGH_VELOCITY,
        target_corridors={
            "land_count": _corridor(33, 35, hard_low=30, hard_high=35),
            "average_nonland_mv": _corridor(1.6, 2.3),
        },
        contextual_weights={
            "mana_efficiency": 1.2,
            "selection": 1.1,
            "ramp": 1.0,
            "immediate_impact": 1.0,
        },
        functional_meta_weight=0.0,
    ),
    PolicyId.RESILIENT_COMMANDER_INDEPENDENT: DeckDesignPolicy(
        policy_id=PolicyId.RESILIENT_COMMANDER_INDEPENDENT,
        target_corridors={"land_count": _corridor(34, 38)},
        contextual_weights={
            "floor_value": 1.2,
            "commander_independence": 1.5,
            "rebuild": 1.2,
            "protection": 0.8,
            "commander_synergy": 0.35,
        },
        functional_meta_weight=0.0,
    ),
    PolicyId.INTERACTION_HEAVY_LOCAL_META: DeckDesignPolicy(
        policy_id=PolicyId.INTERACTION_HEAVY_LOCAL_META,
        target_corridors={
            "land_count": _corridor(34, 38),
            "role.counter": _corridor(7, 13, weight=1.2),
            "role.removal": _corridor(9, 16, weight=1.2),
            "role.protection": _corridor(8, 15, weight=1.0),
        },
        contextual_weights={
            "counter": 1.4,
            "removal": 1.3,
            "protection": 1.1,
            "immediate_impact": 1.0,
        },
        meta_band_weights={FormatBand.LOCAL_META: 1.0},
        functional_meta_weight=0.65,
    ),
}


def policy_registry() -> dict[PolicyId, DeckDesignPolicy]:
    return dict(_POLICY_REGISTRY)


def get_policy(policy_id: PolicyId | str) -> DeckDesignPolicy:
    return _POLICY_REGISTRY[PolicyId(policy_id)]
