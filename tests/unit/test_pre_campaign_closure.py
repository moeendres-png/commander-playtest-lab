from __future__ import annotations

from commander_lab.models import (
    CardRole,
    DataQuality,
    StructuralCardProfile,
    StructuralDeckProfile,
)


def _synthetic_finisher_deck(
    deck_id: str, *, multiplayer_scaling: float, strength: float
) -> StructuralDeckProfile:
    quality = DataQuality.SYNTHETIC_ASSUMPTION
    commander = StructuralCardProfile(
        oracle_name=f"{deck_id}-commander",
        mana_value=0.0,
        roles=frozenset({CardRole.ENABLER}),
        role_strengths={CardRole.ENABLER: 1.0},
        color_identity=frozenset(),
        produces_colors=frozenset(),
        is_land=False,
        is_permanent=True,
        commander_synergy=0.0,
        floor_value=0.5,
        immediate_impact=0.5,
        turn_cycle_risk=0.5,
        multiplayer_scaling=0.0,
        source_quality=quality,
    )
    cards = [commander]
    for index in range(99):
        cards.append(
            StructuralCardProfile(
                oracle_name=f"{deck_id}-finisher-{index:02d}",
                mana_value=0.0,
                roles=frozenset({CardRole.FINISHER}),
                role_strengths={CardRole.FINISHER: strength},
                color_identity=frozenset(),
                produces_colors=frozenset(),
                is_land=False,
                is_permanent=False,
                commander_synergy=0.0,
                floor_value=1.0,
                immediate_impact=1.0,
                turn_cycle_risk=0.0,
                multiplayer_scaling=multiplayer_scaling,
                source_quality=quality,
            )
        )
    return StructuralDeckProfile(
        deck_id=deck_id,
        deck_hash=(deck_id.encode().hex() + "0" * 64)[:64],
        commander_names=(commander.oracle_name,),
        cards=tuple(cards),
        commander_base_costs={commander.oracle_name: 0.0},
        commander_base_power={commander.oracle_name: 0.0},
        commander_strategy="generic",
        data_snapshot_hash="synthetic-pre-campaign-closure",
    )
