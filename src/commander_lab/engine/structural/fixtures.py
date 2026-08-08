from __future__ import annotations

from pathlib import Path

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


def build_synthetic_deck_profile(
    archetype: str, *, data_snapshot_hash: str
) -> StructuralDeckProfile:
    archetype = archetype.casefold()
    if archetype not in {"aggro", "control", "engine"}:
        raise ValueError(f"unknown synthetic archetype: {archetype}")
    prefix = f"synthetic/{archetype}"
    commander_name = f"Synthetic {archetype.title()} Commander"
    cards: list[StructuralCardProfile] = [
        _card(
            commander_name,
            4,
            {CardRole.ENGINE, CardRole.PAYOFF},
            strength=1.2,
            power=4,
            creature=True,
        )
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
        add_many(
            "threat", 22, 3, {CardRole.ENABLER, CardRole.COMBAT_PAYOFF}, power=3, creature=True
        )
        add_many("token", 7, 3, {CardRole.TOKEN_SOURCE, CardRole.PAYOFF}, power=2, creature=True)
        add_many(
            "finisher",
            6,
            5,
            {CardRole.FINISHER, CardRole.COMBAT_PAYOFF},
            strength=1.3,
            power=5,
            creature=True,
            multiplayer=0.4,
        )
    elif archetype == "control":
        add_many("draw", 10, 3, {CardRole.DRAW, CardRole.SELECTION}, permanent=False)
        add_many("counter", 10, 2, {CardRole.COUNTER}, permanent=False)
        add_many("removal", 10, 2, {CardRole.REMOVAL}, permanent=False)
        add_many("wipe", 5, 5, {CardRole.WIPE}, strength=1.3, permanent=False, multiplayer=0.4)
        add_many("protection", 4, 1, {CardRole.PROTECTION}, permanent=False)
        add_many("engine", 7, 4, {CardRole.ENGINE, CardRole.DRAW}, strength=1.2)
        add_many(
            "finisher",
            5,
            6,
            {CardRole.FINISHER},
            strength=1.4,
            power=5,
            creature=True,
            multiplayer=0.8,
        )
    else:
        add_many("draw", 9, 3, {CardRole.DRAW, CardRole.SELECTION}, permanent=False)
        add_many("removal", 8, 2, {CardRole.REMOVAL}, permanent=False)
        add_many("wipe", 3, 5, {CardRole.WIPE}, permanent=False)
        add_many("engine", 11, 3, {CardRole.ENGINE, CardRole.ENABLER}, strength=1.2)
        add_many("token", 8, 3, {CardRole.TOKEN_SOURCE, CardRole.ENABLER}, power=2, creature=True)
        add_many(
            "payoff",
            8,
            4,
            {CardRole.PAYOFF, CardRole.FINISHER},
            strength=1.25,
            power=3,
            creature=True,
            multiplayer=0.7,
        )
        add_many("recursion", 5, 4, {CardRole.RECURSION, CardRole.ENGINE}, strength=1.1)
    while len(cards) < 100:
        cards.append(
            _card(
                f"{prefix} filler {len(cards):02d}", 3, {CardRole.ENABLER}, power=2, creature=True
            )
        )
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


def build_current_opponent_profiles(
    config_path: str | Path,
    *,
    data_snapshot_hash: str,
) -> dict[str, StructuralDeckProfile]:
    """Build current opponent role profiles from a versioned local configuration.

    These are structural estimates, not card-by-card rules-engine deck implementations.
    """
    import json
    from pathlib import Path

    payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
    profiles: dict[str, StructuralDeckProfile] = {}
    all_colors = frozenset({Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN})
    for spec in payload["profiles"]:
        deck_id = str(spec["deck_id"])
        commander_name = str(spec["commander"])
        quality = DataQuality(str(spec.get("data_quality", "project_inferred")))
        source_status = str(spec.get("source_status", "role_profile_only"))
        snapshot_dir = spec.get("snapshot_dir")
        if spec.get("verified_full_list") and snapshot_dir:
            snapshot_root = Path(config_path).resolve().parents[2] / str(snapshot_dir)
            deck_payload = json.loads((snapshot_root / "deck.json").read_text(encoding="utf-8"))
            roles_payload = json.loads((snapshot_root / "roles.json").read_text(encoding="utf-8"))
            role_by_name = {row["oracle_name"]: row for row in roles_payload["roles"]}
            exact_cards: list[StructuralCardProfile] = []
            for entry in deck_payload["cards"]:
                role_row = role_by_name[entry["oracle_name"]]
                roles = frozenset(CardRole(value) for value in role_row["roles"])
                colors = frozenset(
                    Color(value)
                    for value in str(entry.get("color_identity", ""))
                    if value in {"W", "U", "B", "R", "G"}
                )
                produces = frozenset()
                if role_row.get("is_land"):
                    if entry["oracle_name"] == "Swamp":
                        produces = frozenset({Color.BLACK})
                    elif entry["oracle_name"] == "Mountain":
                        produces = frozenset({Color.RED})
                    else:
                        produces = frozenset({Color.BLACK, Color.RED})
                requirements: dict[Color, int] = {}
                mana_cost = str(entry.get("mana_cost", ""))
                for color in (Color.BLACK, Color.RED):
                    count = mana_cost.count("{" + color.value + "}")
                    if count:
                        requirements[color] = count
                quantity = int(entry.get("quantity", 1))
                for _ in range(quantity):
                    exact_cards.append(
                        StructuralCardProfile(
                            oracle_name=str(entry["oracle_name"]),
                            mana_value=float(entry.get("mana_value", 0.0)),
                            roles=roles,
                            role_strengths={role: 1.0 for role in roles},
                            color_requirements=requirements,
                            color_identity=colors,
                            produces_colors=produces,
                            is_land=bool(role_row.get("is_land")),
                            is_permanent=not any(
                                token in str(entry.get("card_type", ""))
                                for token in ("Instant", "Sorcery")
                            ),
                            is_creature=bool(role_row.get("is_creature")),
                            base_power=4.0
                            if entry["oracle_name"] == commander_name
                            else (3.0 if role_row.get("is_creature") else 0.0),
                            commander_synergy=1.0
                            if entry["oracle_name"] == commander_name
                            else (
                                0.55
                                if roles & {CardRole.ENGINE, CardRole.PAYOFF, CardRole.FINISHER}
                                else 0.2
                            ),
                            floor_value=0.78,
                            immediate_impact=0.85
                            if roles & {CardRole.REMOVAL, CardRole.WIPE, CardRole.GRAVEYARD_HATE}
                            else 0.6,
                            turn_cycle_risk=0.35
                            if roles & {CardRole.REMOVAL, CardRole.PROTECTION}
                            else 0.5,
                            multiplayer_scaling=0.55
                            if roles & {CardRole.WIPE, CardRole.PAYOFF, CardRole.FINISHER}
                            else 0.1,
                            source_quality=quality,
                            notes=f"Exact verified opponent snapshot card for {deck_id}; source_status={source_status}.",
                        )
                    )
            if len(exact_cards) != 100:
                raise ValueError(
                    f"verified opponent snapshot {deck_id} contains {len(exact_cards)} cards, expected 100"
                )
            profiles[deck_id] = StructuralDeckProfile(
                deck_id=deck_id,
                deck_hash=str(deck_payload["deck_hash"]),
                commander_names=(commander_name,),
                cards=tuple(exact_cards),
                commander_base_costs={commander_name: float(spec.get("commander_cost", 5.0))},
                commander_base_power={commander_name: float(spec.get("commander_power", 5.0))},
                commander_strategy=str(spec.get("strategy", "generic")),
                data_snapshot_hash=data_snapshot_hash,
            )
            continue
        cards: list[StructuralCardProfile] = [
            StructuralCardProfile(
                oracle_name=commander_name,
                mana_value=float(spec.get("commander_cost", 5.0)),
                roles=frozenset({CardRole.ENGINE, CardRole.PAYOFF, CardRole.COMBAT_PAYOFF}),
                role_strengths={
                    CardRole.ENGINE: 1.15,
                    CardRole.PAYOFF: 1.1,
                    CardRole.COMBAT_PAYOFF: 0.8,
                },
                is_permanent=True,
                is_creature=True,
                base_power=float(spec.get("commander_power", 5.0)),
                commander_synergy=1.0,
                floor_value=0.75,
                immediate_impact=0.65,
                turn_cycle_risk=0.45,
                multiplayer_scaling=0.35,
                source_quality=quality,
                notes=f"Current opponent commander role profile; source_status={source_status}.",
            )
        ]
        land_count = int(spec.get("land_count", 38))
        for index in range(land_count):
            cards.append(
                StructuralCardProfile(
                    oracle_name=f"{deck_id} mana source {index:02d}",
                    mana_value=0.0,
                    roles=frozenset({CardRole.MANA_SOURCE}),
                    role_strengths={CardRole.MANA_SOURCE: 1.0},
                    produces_colors=all_colors,
                    is_land=True,
                    floor_value=1.0,
                    immediate_impact=1.0,
                    turn_cycle_risk=0.0,
                    source_quality=quality,
                    notes=f"Abstract mana source for {deck_id}.",
                )
            )
        role_counts = {CardRole(key): int(value) for key, value in spec.get("roles", {}).items()}
        role_mv = {
            CardRole.RAMP: 2.0,
            CardRole.DRAW: 3.0,
            CardRole.SELECTION: 2.0,
            CardRole.REMOVAL: 2.5,
            CardRole.COUNTER: 2.0,
            CardRole.PROTECTION: 1.5,
            CardRole.WIPE: 5.0,
            CardRole.RECURSION: 4.0,
            CardRole.GRAVEYARD_HATE: 2.5,
            CardRole.ENGINE: 3.5,
            CardRole.ENABLER: 3.0,
            CardRole.PAYOFF: 4.0,
            CardRole.FINISHER: 6.0,
            CardRole.COMBAT_PAYOFF: 3.5,
            CardRole.TOKEN_SOURCE: 3.5,
            CardRole.SACRIFICE_OUTLET: 2.5,
            CardRole.LAND_SYNERGY: 3.0,
        }
        slot_count = 100 - len(cards)
        slot_roles: list[set[CardRole]] = [set() for _ in range(slot_count)]
        for role_index, (role, count) in enumerate(role_counts.items()):
            capped = min(count, slot_count)
            for offset in range(capped):
                slot = (role_index * 11 + offset * 7) % slot_count
                slot_roles[slot].add(role)
        for index, roles in enumerate(slot_roles):
            if not roles:
                roles = {CardRole.ENABLER}
            creature = bool(
                roles
                & {
                    CardRole.ENGINE,
                    CardRole.ENABLER,
                    CardRole.PAYOFF,
                    CardRole.FINISHER,
                    CardRole.COMBAT_PAYOFF,
                    CardRole.TOKEN_SOURCE,
                }
            )
            mana_value = sum(role_mv.get(role, 3.0) for role in roles) / len(roles)
            cards.append(
                StructuralCardProfile(
                    oracle_name=f"{deck_id} role card {index:03d}",
                    mana_value=mana_value,
                    roles=frozenset(roles),
                    role_strengths={role: 1.0 for role in roles},
                    is_permanent=not bool(
                        roles
                        & {CardRole.REMOVAL, CardRole.COUNTER, CardRole.WIPE, CardRole.SELECTION}
                    ),
                    is_creature=creature,
                    base_power=3.0 if creature else 0.0,
                    commander_synergy=0.45
                    if roles & {CardRole.ENGINE, CardRole.ENABLER, CardRole.PAYOFF}
                    else 0.15,
                    floor_value=0.72,
                    immediate_impact=0.8
                    if roles
                    & {CardRole.REMOVAL, CardRole.COUNTER, CardRole.WIPE, CardRole.PROTECTION}
                    else 0.55,
                    turn_cycle_risk=0.25
                    if roles & {CardRole.REMOVAL, CardRole.COUNTER, CardRole.PROTECTION}
                    else 0.5,
                    multiplayer_scaling=0.45
                    if roles
                    & {CardRole.WIPE, CardRole.PAYOFF, CardRole.FINISHER, CardRole.TOKEN_SOURCE}
                    else 0.1,
                    source_quality=quality,
                    notes=f"Structural role-density card for {deck_id}; source_status={source_status}.",
                )
            )
        while len(cards) < 100:
            cards.append(
                StructuralCardProfile(
                    oracle_name=f"{deck_id} neutral filler {len(cards):03d}",
                    mana_value=3.0,
                    roles=frozenset({CardRole.ENABLER}),
                    role_strengths={CardRole.ENABLER: 0.7},
                    is_permanent=True,
                    is_creature=True,
                    base_power=2.5,
                    floor_value=0.55,
                    immediate_impact=0.4,
                    turn_cycle_risk=0.55,
                    multiplayer_scaling=0.05,
                    source_quality=quality,
                    notes=f"Neutral structural filler for {deck_id}.",
                )
            )
        cards = cards[:100]
        profiles[deck_id] = StructuralDeckProfile(
            deck_id=deck_id,
            deck_hash=sha256_value({"spec": spec, "cards": [card.oracle_name for card in cards]}),
            commander_names=(commander_name,),
            cards=tuple(cards),
            commander_base_costs={commander_name: float(spec.get("commander_cost", 5.0))},
            commander_base_power={commander_name: float(spec.get("commander_power", 5.0))},
            commander_strategy=str(spec.get("strategy", "generic")),
            data_snapshot_hash=data_snapshot_hash,
        )
    return profiles
