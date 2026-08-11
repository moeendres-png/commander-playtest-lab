from __future__ import annotations

from commander_lab.agents import RogShaiPilot
from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotCommanderView,
    PilotConfig,
    PilotDecisionMode,
    PilotOpponentView,
    PilotStateView,
    PilotStrength,
    StructuralMechanic,
)


def _pilot() -> RogShaiPilot:
    return RogShaiPilot(
        PilotConfig(
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )


def _opponents() -> tuple[PilotOpponentView, ...]:
    return tuple(
        PilotOpponentView(
            player_id=f"p{index}",
            life=30,
            threat=8 if index == 3 else 6,
            board_power=4,
            engine_value=2,
            graveyard_size=3,
            hand_size=5,
        )
        for index in range(2, 5)
    )


def _commanders(*, ishai_online: bool, ishai_power: float = 8.0) -> tuple[PilotCommanderView, ...]:
    return (
        PilotCommanderView(
            name="Ishai, Ojutai Dragonspeaker",
            base_cost=4,
            next_cost=6 if not ishai_online else 4,
            casts=1 if ishai_online else 0,
            on_battlefield=ishai_online,
            power=ishai_power,
        ),
        PilotCommanderView(
            name="Rograkh, Son of Rohgahh",
            base_cost=0,
            next_cost=0,
            casts=0,
            on_battlefield=False,
            power=0,
        ),
    )


def _state(
    *,
    ishai_online: bool,
    ishai_power: float = 8.0,
    turn: int = 5,
    role_counts: dict[CardRole, int] | None = None,
    battlefield_names: tuple[str, ...] = (),
    hand_names: tuple[str, ...] = (),
    denial: float = 0.0,
    wipe: float = 0.0,
    archenemy: str | None = None,
) -> PilotStateView:
    return PilotStateView(
        player_id="p1",
        deck_id="rogshai/current",
        strategy="rogshai",
        turn=turn,
        pod_size=4,
        seat_position=1,
        life=34,
        hand_size=max(4, len(hand_names)),
        mana_available=6,
        lands=4,
        ramp_mana=1,
        resources=0,
        tokens=0,
        board_power=4,
        engine_value=1,
        graveyard_size=4,
        battlefield_names=battlefield_names,
        hand_names=hand_names,
        role_counts=role_counts or {},
        commanders=_commanders(ishai_online=ishai_online, ishai_power=ishai_power),
        opponents=_opponents(),
        commander_denial_risk=denial,
        boardwipe_risk=wipe,
        hidden_information_uncertainty=0.6,
        opponent_intent_uncertainty=0.6,
        unknown_opponent_fraction=0.3,
        opponents_to_act_before_next_turn=3,
        archenemy_player_id=archenemy,
    )


def _action(
    action_id: str,
    card_name: str,
    *,
    kind: str = "card",
    remaining_mana: float = 1.0,
    roles: frozenset[CardRole] = frozenset(),
    mechanic_tags: frozenset[StructuralMechanic] = frozenset(),
    target_player_id: str | None = None,
    metadata: dict[str, float | int | str | bool] | None = None,
) -> PilotActionView:
    return PilotActionView(
        action_id=action_id,
        action_kind=kind,  # type: ignore[arg-type]
        card_name=card_name,
        mana_cost=0 if card_name.startswith("Rograkh") else 2,
        roles=roles,
        role_strengths={role: 1.0 for role in roles},
        mechanic_tags=mechanic_tags,
        floor_value=0.8,
        immediate_impact=0.8,
        remaining_mana=remaining_mana,
        target_player_id=target_player_id,
        metadata=metadata or {},
    )


def test_ishai_cast_timing_respects_protection_counter_denial_wipe_and_exposure() -> None:
    pilot = _pilot()
    state = _state(
        ishai_online=False,
        role_counts={CardRole.PROTECTION: 1, CardRole.COUNTER: 1},
        denial=0.9,
        wipe=0.8,
    )
    protected = _action(
        "protected-ishai",
        "Ishai, Ojutai Dragonspeaker",
        kind="commander",
        remaining_mana=2,
        metadata={"increases_board_exposure": 0.4},
    )
    exposed = _action(
        "exposed-ishai",
        "Ishai, Ojutai Dragonspeaker",
        kind="commander",
        remaining_mana=0,
        metadata={"increases_board_exposure": 1.0},
    )
    assert pilot.specialist_bonus(state, protected, {}) > pilot.specialist_bonus(state, exposed, {})


def test_commander_damage_double_strike_jeska_and_kediss_finish_axes_are_positive() -> None:
    pilot = _pilot()
    state = _state(ishai_online=True, ishai_power=11)
    generic = _action("generic", "Generic Value")
    double_strike = _action("double", "Duelist's Heritage")
    kediss = _action(
        "kediss",
        "Kediss, Emberclaw Familiar",
        mechanic_tags=frozenset({StructuralMechanic.TABLE_DAMAGE}),
    )
    jeska = _action(
        "jeska",
        "Jeska, Thrice Reborn",
        metadata={"expected_lethal_opponents": 1, "protected_finish_window": True},
    )
    generic_bonus = pilot.specialist_bonus(state, generic, {})
    assert pilot.specialist_bonus(state, double_strike, {}) > generic_bonus
    assert pilot.specialist_bonus(state, kediss, {}) > generic_bonus
    assert pilot.specialist_bonus(state, jeska, {}) > generic_bonus


def test_rograkh_resource_combat_draw_and_independent_spellslinger_rebuild_axes() -> None:
    pilot = _pilot()
    early = _state(
        ishai_online=False,
        turn=1,
        hand_names=("Springleaf Drum",),
        denial=0.7,
        wipe=0.7,
    )
    rograkh = _action("rograkh", "Rograkh, Son of Rohgahh", kind="commander")
    assert pilot.specialist_bonus(early, rograkh, {}) > 0

    online = _state(
        ishai_online=True,
        ishai_power=8,
        role_counts={CardRole.PROTECTION: 1},
    )
    combat_draw = _action(
        "draw",
        "Combat Research",
        roles=frozenset({CardRole.DRAW, CardRole.COMBAT_PAYOFF}),
        remaining_mana=2,
    )
    assert pilot.specialist_bonus(online, combat_draw, {}) > 0

    kykar = _action(
        "kykar",
        "Kykar, Wind's Fury",
        roles=frozenset({CardRole.ENGINE}),
        mechanic_tags=frozenset({StructuralMechanic.COMMANDER_INDEPENDENT}),
    )
    assert pilot.specialist_bonus(early, kykar, {}) > 0


def test_archenemy_pressure_and_commander_damage_change_combat_target_priority() -> None:
    pilot = _pilot()
    state = _state(ishai_online=True, ishai_power=9, archenemy="p3")
    normal = _action(
        "normal",
        "Attack p2",
        kind="combat_target",
        target_player_id="p2",
        metadata={"commander_damage_pressure": 8.0, "target_life": 30.0},
    )
    archenemy = _action(
        "archenemy",
        "Attack p3",
        kind="combat_target",
        target_player_id="p3",
        metadata={"commander_damage_pressure": 8.0, "target_life": 30.0},
    )
    assert pilot.specialist_bonus(state, archenemy, {}) > pilot.specialist_bonus(state, normal, {})
