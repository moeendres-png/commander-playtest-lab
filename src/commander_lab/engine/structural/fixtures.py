from __future__ import annotations

from commander_lab.models import (
    CardRole,
    Color,
    DataQuality,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.storage import sha256_value


def _card(
    name: str,
    mana_value: float,
    roles: set[CardRole],
    *,
    strength: float = 1.0,
    power: float = 0.0,
    permanent: bool = True,
    creature: bool = False,
    multiplayer: float = 0.0,
    colors: frozenset[Color] = frozenset(),
) -> StructuralCardProfile:
    return StructuralCardProfile(
        oracle_name=name,
        mana_value=mana_value,
        roles=frozenset(roles),
        role_strengths={role: strength for role in roles},
        color_requirements={color: 1 for color in colors} if mana_value else {},
        produces_colors=colors if CardRole.MANA_SOURCE in roles else frozenset(),
        is_land=CardRole.MANA_SOURCE in roles and mana_value == 0,
        is_permanent=permanent,
        is_creature=creature,
        base_power=power,
        commander_synergy=0.3,
        floor_value=0.7,
        immediate_impact=0.7,
        turn_cycle_risk=0.4,
        multiplayer_scaling=multiplayer,
        source_quality=DataQuality.SYNTHETIC_ASSUMPTION,
        notes="Synthetic engine-validation fixture; not an opponent profile.",
    )


def build_synthetic_deck_profile(archetype: str, *, data_snapshot_hash: str) -> StructuralDeckProfile:
    archetype = archetype.casefold()
    if archetype not in {"aggro", "control", "engine"}:
        raise ValueError(f"unknown synthetic archetype: {archetype}")
    prefix = f"synthetic/{archetype}"
    commander_name = f"Synthetic {archetype.title()} Commander"
    cards: list[StructuralCardProfile] = [
        _card(commander_name, 4, {CardRole.ENGINE, CardRole.PAYOFF}, strength=1.2, power=4, creature=True)
    ]
    land_count = 37 if archetype != "control" else 38
    colors = frozenset({Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN})
    for index in range(land_count):
        cards.append(_card(f"{prefix} land {index:02d}", 0, {CardRole.MANA_SOURCE}, colors=colors))

    def add_many(label: str, count: int, mv: float, roles: set[CardRole], **kwargs: object) -> None:
        for index in range(count):
            cards.append(_card(f"{prefix} {label} {index:02d}", mv, roles, **kwargs))

    add_many("ramp", 10, 2, {CardRole.RAMP}, permanent=True)
    if archetype == "aggro":
        add_many("draw", 7, 2, {CardRole.DRAW, CardRole.SELECTION}, permanent=False)
        add_many("removal", 8, 2, {CardRole.REMOVAL}, permanent=False)
        add_many("wipe", 2, 4, {CardRole.WIPE}, permanent=False)
        add_many("threat", 22, 3, {CardRole.ENABLER, CardRole.COMBAT_PAYOFF}, power=3, creature=True)
        add_many("token", 7, 3, {CardRole.TOKEN_SOURCE, CardRole.PAYOFF}, power=2, creature=True)
        add_many("finisher", 6, 5, {CardRole.FINISHER, CardRole.COMBAT_PAYOFF}, strength=1.3, power=5, creature=True, multiplayer=0.4)
    elif archetype == "control":
        add_many("draw", 10, 3, {CardRole.DRAW, CardRole.SELECTION}, permanent=False)
        add_many("counter", 10, 2, {CardRole.COUNTER}, permanent=False)
        add_many("removal", 10, 2, {CardRole.REMOVAL}, permanent=False)
        add_many("wipe", 5, 5, {CardRole.WIPE}, strength=1.3, permanent=False, multiplayer=0.4)
        add_many("protection", 4, 1, {CardRole.PROTECTION}, permanent=False)
        add_many("engine", 7, 4, {CardRole.ENGINE, CardRole.DRAW}, strength=1.2)
        add_many("finisher", 5, 6, {CardRole.FINISHER}, strength=1.4, power=5, creature=True, multiplayer=0.8)
    else:
        add_many("draw", 9, 3, {CardRole.DRAW, CardRole.SELECTION}, permanent=False)
        add_many("removal", 8, 2, {CardRole.REMOVAL}, permanent=False)
        add_many("wipe", 3, 5, {CardRole.WIPE}, permanent=False)
        add_many("engine", 11, 3, {CardRole.ENGINE, CardRole.ENABLER}, strength=1.2)
        add_many("token", 8, 3, {CardRole.TOKEN_SOURCE, CardRole.ENABLER}, power=2, creature=True)
        add_many("payoff", 8, 4, {CardRole.PAYOFF, CardRole.FINISHER}, strength=1.25, power=3, creature=True, multiplayer=0.7)
        add_many("recursion", 5, 4, {CardRole.RECURSION, CardRole.ENGINE}, strength=1.1)
    while len(cards) < 100:
        cards.append(_card(f"{prefix} filler {len(cards):02d}", 3, {CardRole.ENABLER}, power=2, creature=True))
    cards = cards[:100]
    deck_hash = sha256_value([card.oracle_name for card in cards])
    return StructuralDeckProfile(
        deck_id=prefix,
        deck_hash=deck_hash,
        commander_names=(commander_name,),
        cards=tuple(cards),
        commander_base_costs={commander_name: 4.0},
        commander_base_power={commander_name: 4.0},
        commander_strategy=archetype,
        data_snapshot_hash=data_snapshot_hash,
    )
