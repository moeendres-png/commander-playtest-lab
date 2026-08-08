from __future__ import annotations

import random

from commander_lab.agents import GenericCommanderPilot, KorvoldPilot, RogShaiPilot
from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotCommanderView,
    PilotConfig,
    PilotDecisionMode,
    PilotOpponentView,
    PilotStateView,
    PilotStrength,
)


def _state(
    *,
    strategy: str = "generic",
    mana: float = 4.0,
    turn: int = 5,
    battlefield: tuple[str, ...] = (),
    hand_names: tuple[str, ...] = (),
    role_counts: dict[CardRole, int] | None = None,
    commanders: tuple[PilotCommanderView, ...] = (),
    opponents: tuple[PilotOpponentView, ...] | None = None,
    resources: float = 0.0,
    tokens: float = 0.0,
) -> PilotStateView:
    if opponents is None:
        opponents = (
            PilotOpponentView(
                player_id="p2",
                life=30,
                threat=7,
                board_power=5,
                engine_value=2,
                graveyard_size=4,
                hand_size=5,
            ),
            PilotOpponentView(
                player_id="p3",
                life=24,
                threat=5,
                board_power=4,
                engine_value=1,
                graveyard_size=2,
                hand_size=4,
            ),
        )
    return PilotStateView(
        player_id="p1",
        deck_id=f"test/{strategy}",
        strategy=strategy,
        turn=turn,
        pod_size=1 + len(opponents),
        life=34,
        hand_size=max(3, len(hand_names)),
        mana_available=mana,
        lands=4,
        ramp_mana=1,
        resources=resources,
        tokens=tokens,
        board_power=4,
        engine_value=1,
        graveyard_size=5,
        battlefield_names=battlefield,
        hand_names=hand_names,
        role_counts=role_counts or {},
        commanders=commanders,
        opponents=opponents,
    )


def _action(
    action_id: str,
    name: str,
    *,
    cost: float,
    roles: set[CardRole] | None = None,
    strengths: dict[CardRole, float] | None = None,
    remaining: float = 0.0,
    power: float = 0.0,
    kind: str = "card",
    immediate: float = 0.7,
    floor: float = 0.7,
    commander_synergy: float = 0.0,
    multiplayer: float = 0.0,
    metadata: dict[str, float | int | str | bool] | None = None,
) -> PilotActionView:
    role_set = frozenset(roles or set())
    return PilotActionView(
        action_id=action_id,
        action_kind=kind,  # type: ignore[arg-type]
        card_name=name,
        mana_cost=cost,
        roles=role_set,
        role_strengths=strengths or {role: 1.0 for role in role_set},
        remaining_mana=remaining,
        base_power=power,
        immediate_impact=immediate,
        floor_value=floor,
        commander_synergy=commander_synergy,
        multiplayer_scaling=multiplayer,
        metadata=metadata or {},
    )


def test_deterministic_pilot_ignores_rng_for_same_state() -> None:
    pilot = GenericCommanderPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    state = _state()
    actions = (
        _action("draw", "Draw spell", cost=2, roles={CardRole.DRAW}, remaining=2),
        _action("engine", "Engine", cost=3, roles={CardRole.ENGINE}, remaining=1),
    )
    first = pilot.choose_action(state, actions, random.Random(1))
    second = pilot.choose_action(state, actions, random.Random(999))
    assert first.selected_action_id == second.selected_action_id
    assert first.selected_utility == second.selected_utility


def test_stochastic_pilot_is_seeded_but_not_constant_across_seeds() -> None:
    pilot = GenericCommanderPilot(
        PilotConfig(
            strength=PilotStrength.AVERAGE,
            mode=PilotDecisionMode.STOCHASTIC,
            temperature=1.5,
            mistake_rate=0.0,
        )
    )
    state = _state()
    actions = (
        _action("a", "Option A", cost=2, roles={CardRole.DRAW}, remaining=2),
        _action("b", "Option B", cost=2, roles={CardRole.SELECTION}, remaining=2),
    )
    first = pilot.choose_action(state, actions, random.Random(42))
    replay = pilot.choose_action(state, actions, random.Random(42))
    choices = {
        pilot.choose_action(state, actions, random.Random(seed)).selected_action_id
        for seed in range(30)
    }
    assert first.selected_action_id == replay.selected_action_id
    assert len(choices) == 2


def test_near_optimal_rogshai_preserves_interaction_mana() -> None:
    state = _state(
        strategy="rogshai",
        mana=2,
        role_counts={CardRole.COUNTER: 1},
        hand_names=("Counterspell", "Visible Engine"),
    )
    engine = _action(
        "engine",
        "Visible Engine",
        cost=2,
        roles={CardRole.ENGINE},
        remaining=0,
        immediate=0.25,
        floor=0.55,
    )
    pass_action = _action(
        "pass",
        "Pass priority window",
        cost=0,
        remaining=2,
        kind="pass",
        immediate=0.1,
        floor=0.2,
    )
    near = RogShaiPilot(
        PilotConfig(
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    weak = RogShaiPilot(
        PilotConfig(strength=PilotStrength.WEAK, mode=PilotDecisionMode.DETERMINISTIC)
    )
    assert (
        near.choose_action(state, (engine, pass_action), random.Random(1)).selected_action_id
        == "pass"
    )
    assert (
        weak.choose_action(state, (engine, pass_action), random.Random(1)).selected_action_id
        == "engine"
    )


def test_korvold_pilot_values_sacrifice_outlet_with_material_and_commander() -> None:
    state = _state(
        strategy="korvold",
        resources=3,
        tokens=4,
        role_counts={CardRole.TOKEN_SOURCE: 2, CardRole.LAND_SYNERGY: 2},
        commanders=(
            PilotCommanderView(
                name="Korvold, Fae-Cursed King",
                base_cost=5,
                next_cost=5,
                casts=1,
                on_battlefield=True,
                power=8,
            ),
        ),
    )
    outlet = _action(
        "outlet",
        "Goblin Bombardment",
        cost=2,
        roles={CardRole.SACRIFICE_OUTLET, CardRole.PAYOFF},
        remaining=2,
    )
    generic_draw = _action(
        "draw",
        "Generic Draw",
        cost=2,
        roles={CardRole.DRAW},
        remaining=2,
    )
    pilot = KorvoldPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    decision = pilot.choose_action(state, (outlet, generic_draw), random.Random(1))
    assert decision.selected_action_id == "outlet"


def test_korvold_pilot_delays_commander_without_immediate_value() -> None:
    state = _state(
        strategy="korvold",
        mana=5,
        resources=0,
        tokens=0,
        role_counts={},
        commanders=(
            PilotCommanderView(
                name="Korvold, Fae-Cursed King",
                base_cost=5,
                next_cost=5,
                casts=0,
                on_battlefield=False,
                power=4,
            ),
        ),
    )
    commander = _action(
        "korvold",
        "Korvold, Fae-Cursed King",
        cost=5,
        roles={CardRole.ENGINE, CardRole.DRAW, CardRole.PAYOFF},
        remaining=0,
        power=4,
        kind="commander",
        commander_synergy=1,
    )
    engine = _action(
        "token-engine",
        "Token Engine",
        cost=3,
        roles={CardRole.TOKEN_SOURCE, CardRole.ENGINE},
        remaining=2,
    )
    pilot = KorvoldPilot(
        PilotConfig(
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    assert (
        pilot.choose_action(state, (commander, engine), random.Random(1)).selected_action_id
        == "token-engine"
    )


def test_rogshai_pilot_casts_rograkh_as_early_resource() -> None:
    state = _state(
        strategy="rogshai",
        mana=1,
        turn=1,
        hand_names=("Springleaf Drum",),
        commanders=(
            PilotCommanderView(
                name="Rograkh, Son of Rohgahh",
                base_cost=0,
                next_cost=0,
                casts=0,
                on_battlefield=False,
                power=0,
            ),
            PilotCommanderView(
                name="Ishai, Ojutai Dragonspeaker",
                base_cost=4,
                next_cost=4,
                casts=0,
                on_battlefield=False,
                power=1,
            ),
        ),
    )
    rograkh = _action(
        "rograkh",
        "Rograkh, Son of Rohgahh",
        cost=0,
        roles={CardRole.ENABLER},
        remaining=1,
        kind="commander",
    )
    selection = _action(
        "selection",
        "Consider",
        cost=1,
        roles={CardRole.SELECTION},
        remaining=0,
    )
    pilot = RogShaiPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    assert (
        pilot.choose_action(state, (rograkh, selection), random.Random(1)).selected_action_id
        == "rograkh"
    )


def test_rogshai_pilot_prioritizes_jeska_with_large_ishai() -> None:
    state = _state(
        strategy="rogshai",
        mana=5,
        battlefield=("Ishai, Ojutai Dragonspeaker",),
        commanders=(
            PilotCommanderView(
                name="Ishai, Ojutai Dragonspeaker",
                base_cost=4,
                next_cost=4,
                casts=1,
                on_battlefield=True,
                power=11,
            ),
            PilotCommanderView(
                name="Rograkh, Son of Rohgahh",
                base_cost=0,
                next_cost=2,
                casts=1,
                on_battlefield=False,
                power=0,
            ),
        ),
    )
    jeska = _action(
        "jeska",
        "Jeska, Thrice Reborn",
        cost=3,
        roles={CardRole.COMBAT_PAYOFF, CardRole.FINISHER},
        remaining=2,
        multiplayer=0.5,
    )
    draw = _action("draw", "Draw spell", cost=2, roles={CardRole.DRAW}, remaining=3)
    pilot = RogShaiPilot(
        PilotConfig(
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    assert pilot.choose_action(state, (jeska, draw), random.Random(1)).selected_action_id == "jeska"


def test_rogshai_combat_target_uses_per_opponent_commander_damage() -> None:
    opponents = (
        PilotOpponentView(
            player_id="p2",
            life=28,
            threat=4,
            board_power=2,
            engine_value=1,
            graveyard_size=2,
            hand_size=4,
            commander_damage_from_actor={"Ishai, Ojutai Dragonspeaker": 18},
        ),
        PilotOpponentView(
            player_id="p3",
            life=9,
            threat=6,
            board_power=3,
            engine_value=2,
            graveyard_size=3,
            hand_size=5,
        ),
    )
    state = _state(strategy="rogshai", opponents=opponents)
    p2 = _action(
        "p2",
        "Attack p2",
        cost=0,
        kind="combat_target",
        power=8,
        metadata={"target_life": 28.0, "commander_damage_pressure": 18.0},
    )
    p3 = _action(
        "p3",
        "Attack p3",
        cost=0,
        kind="combat_target",
        power=8,
        metadata={"target_life": 9.0, "commander_damage_pressure": 0.0},
    )
    pilot = RogShaiPilot(
        PilotConfig(
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    assert pilot.choose_combat_target(state, (p2, p3), random.Random(1)).selected_action_id == "p2"


def test_korvold_pilot_values_land_rebuild_from_large_graveyard() -> None:
    state = _state(
        strategy="korvold",
        mana=5,
        resources=1,
        tokens=1,
        role_counts={CardRole.LAND_SYNERGY: 3},
    ).model_copy(update={"graveyard_size": 12})
    reclamation = _action(
        "reclamation",
        "Splendid Reclamation",
        cost=4,
        roles={CardRole.RECURSION, CardRole.LAND_SYNERGY, CardRole.PAYOFF},
        remaining=1,
    )
    draw = _action("draw", "Generic Draw", cost=2, roles={CardRole.DRAW}, remaining=3)
    pilot = KorvoldPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    assert (
        pilot.choose_action(state, (reclamation, draw), random.Random(1)).selected_action_id
        == "reclamation"
    )


def test_korvold_pilot_values_table_damage_in_five_player_pod() -> None:
    opponents = tuple(
        PilotOpponentView(
            player_id=f"p{index}",
            life=30,
            threat=5,
            board_power=3,
            engine_value=1,
            graveyard_size=2,
            hand_size=4,
        )
        for index in range(2, 6)
    )
    state = _state(
        strategy="korvold",
        opponents=opponents,
        resources=3,
        tokens=4,
        role_counts={CardRole.TOKEN_SOURCE: 2, CardRole.SACRIFICE_OUTLET: 1},
    )
    bats = _action(
        "bats",
        "Mirkwood Bats",
        cost=4,
        roles={CardRole.PAYOFF, CardRole.FINISHER},
        remaining=0,
        multiplayer=1.2,
    )
    engine = _action("engine", "Generic Engine", cost=3, roles={CardRole.ENGINE}, remaining=1)
    pilot = KorvoldPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    assert pilot.choose_action(state, (bats, engine), random.Random(1)).selected_action_id == "bats"


def test_rogshai_pilot_uses_combat_draw_when_ishai_is_protected() -> None:
    commanders = (
        PilotCommanderView(
            name="Ishai, Ojutai Dragonspeaker",
            base_cost=4,
            next_cost=4,
            casts=1,
            on_battlefield=True,
            power=8,
        ),
        PilotCommanderView(
            name="Rograkh, Son of Rohgahh",
            base_cost=0,
            next_cost=2,
            casts=1,
            on_battlefield=False,
            power=0,
        ),
    )
    state = _state(
        strategy="rogshai",
        mana=3,
        role_counts={CardRole.PROTECTION: 1},
        commanders=commanders,
        hand_names=("Loran's Escape", "Combat Research"),
    )
    aura = _action(
        "aura",
        "Combat Research",
        cost=1,
        roles={CardRole.DRAW, CardRole.COMBAT_PAYOFF},
        remaining=2,
        commander_synergy=1,
    )
    engine = _action("engine", "Generic Engine", cost=3, roles={CardRole.ENGINE}, remaining=0)
    pilot = RogShaiPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    assert pilot.choose_action(state, (aura, engine), random.Random(1)).selected_action_id == "aura"


def test_rogshai_pilot_uses_kykar_axis_when_ishai_is_offline() -> None:
    commanders = (
        PilotCommanderView(
            name="Ishai, Ojutai Dragonspeaker",
            base_cost=4,
            next_cost=6,
            casts=1,
            on_battlefield=False,
            power=1,
        ),
        PilotCommanderView(
            name="Rograkh, Son of Rohgahh",
            base_cost=0,
            next_cost=2,
            casts=1,
            on_battlefield=False,
            power=0,
        ),
    )
    state = _state(
        strategy="rogshai",
        mana=4,
        commanders=commanders,
        role_counts={CardRole.COUNTER: 1},
        hand_names=("Kykar, Wind's Fury", "Combat Research"),
    )
    kykar = _action(
        "kykar",
        "Kykar, Wind's Fury",
        cost=4,
        roles={CardRole.ENGINE, CardRole.TOKEN_SOURCE, CardRole.PAYOFF},
        remaining=0,
        power=3,
    )
    aura = _action(
        "aura",
        "Combat Research",
        cost=1,
        roles={CardRole.DRAW, CardRole.COMBAT_PAYOFF},
        remaining=3,
        commander_synergy=1,
    )
    pilot = RogShaiPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    assert pilot.choose_action(state, (kykar, aura), random.Random(1)).selected_action_id == "kykar"


def test_rogshai_protects_large_ishai_from_high_value_removal() -> None:
    commanders = (
        PilotCommanderView(
            name="Ishai, Ojutai Dragonspeaker",
            base_cost=4,
            next_cost=6,
            casts=1,
            on_battlefield=True,
            power=12,
        ),
        PilotCommanderView(
            name="Rograkh, Son of Rohgahh",
            base_cost=0,
            next_cost=2,
            casts=1,
            on_battlefield=False,
            power=0,
        ),
    )
    state = _state(strategy="rogshai", mana=2, commanders=commanders)
    protection = _action(
        "protect",
        "Loran's Escape",
        cost=1,
        roles={CardRole.PROTECTION},
        remaining=1,
        kind="protection",
    ).model_copy(update={"threat_score": 8.0})
    pilot = RogShaiPilot(
        PilotConfig(
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    take, breakdown = pilot.should_take_reaction(state, protection, random.Random(1), threshold=0.5)
    assert take
    assert breakdown.survival > 0
    assert breakdown.commander_value > 0


def test_korvold_opening_hand_score_rewards_sacrifice_and_land_package() -> None:
    pilot = KorvoldPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    lands = tuple(
        _action(
            f"land-{index}",
            f"Land {index}",
            cost=0,
            roles={CardRole.MANA_SOURCE},
            metadata={"is_land": True, "is_creature": False},
        )
        for index in range(3)
    )
    synergy = (
        *lands,
        _action("ramp", "Nature's Lore", cost=2, roles={CardRole.RAMP}),
        _action("token", "Ophiomancer", cost=3, roles={CardRole.TOKEN_SOURCE}),
        _action(
            "outlet",
            "Goblin Bombardment",
            cost=2,
            roles={CardRole.SACRIFICE_OUTLET},
        ),
        _action("land-engine", "Ramunap Excavator", cost=3, roles={CardRole.LAND_SYNERGY}),
    )
    disconnected = lands + tuple(
        _action(f"filler-{index}", f"Filler {index}", cost=4, roles={CardRole.ENABLER})
        for index in range(4)
    )
    assert pilot.opening_hand_score(synergy) > pilot.opening_hand_score(disconnected)


def test_rogshai_bottoms_slow_combat_aura_before_cheap_interaction() -> None:
    pilot = RogShaiPilot(
        PilotConfig(
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    cards = (
        _action(
            "aura",
            "Staggering Insight",
            cost=2,
            roles={CardRole.DRAW, CardRole.COMBAT_PAYOFF},
        ),
        _action("counter", "Counterspell", cost=2, roles={CardRole.COUNTER}),
        _action("protect", "Loran's Escape", cost=1, roles={CardRole.PROTECTION}),
    )
    assert pilot.choose_bottom_cards(
        cards,
        1,
        commander_names=(
            "Ishai, Ojutai Dragonspeaker",
            "Rograkh, Son of Rohgahh",
        ),
    ) == ("aura",)


def test_pilot_removal_target_prefers_largest_threat_reduction() -> None:
    pilot = GenericCommanderPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    state = _state()
    low = _action(
        "low",
        "Remove p2",
        cost=0,
        roles={CardRole.REMOVAL},
        kind="removal_target",
    ).model_copy(update={"target_threat": 3.0, "threat_score": 2.0})
    high = _action(
        "high",
        "Remove p3",
        cost=0,
        roles={CardRole.REMOVAL},
        kind="removal_target",
    ).model_copy(update={"target_threat": 10.0, "threat_score": 8.0})
    assert pilot.choose_target(state, (low, high), random.Random(1)).selected_action_id == "high"


def test_pilot_graveyard_target_prefers_larger_recursion_resource() -> None:
    pilot = GenericCommanderPilot(
        PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    )
    state = _state()
    small = _action(
        "small",
        "Exile p2 graveyard",
        cost=0,
        roles={CardRole.GRAVEYARD_HATE},
        kind="graveyard_target",
    ).model_copy(update={"threat_score": 3.0})
    large = _action(
        "large",
        "Exile p3 graveyard",
        cost=0,
        roles={CardRole.GRAVEYARD_HATE},
        kind="graveyard_target",
    ).model_copy(update={"threat_score": 12.0})
    assert (
        pilot.choose_target(state, (small, large), random.Random(1)).selected_action_id == "large"
    )
