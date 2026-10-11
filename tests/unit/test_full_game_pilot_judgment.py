"""Full-game pilot judgment from public card knowledge (#732).

Real-deck 4P games showed pilots that knew cards only by name: every spell
looked the same, zero-power creatures attacked, creatures chump-blocked at 40
life, the first mana colour (White) was always picked, counterspells were cast
at the pilot's own spells, and lands, board power and an online commander were
miscounted. These tests pin the pilot's choice among engine-offered options;
the engine stays the only rules authority.
"""

from __future__ import annotations

from typing import Any

from commander_lab.agents import GenericCommanderPilot
from commander_lab.agents.card_knowledge import card_facts, card_roles
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import CardRole, PilotConfig, PilotStrength


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC)
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Esior, Wardwing Familiar",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20261011)  # type: ignore[arg-type]


def _card(
    object_id: str, name: str, power: int = 0, toughness: int = 0, **extra: Any
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "name": name,
        "tapped": False,
        "power": power,
        "toughness": toughness,
        "damage": 0,
        **extra,
    }


def _state(
    *,
    actor_board: list[dict[str, Any]] | None = None,
    opponent_board: list[dict[str, Any]] | None = None,
    actor_life: int = 40,
    opponent_life: int = 40,
    hand: list[str] | None = None,
    stack: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lands = [_card(f"island-{index}", "Island") for index in range(3)]
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": actor_life,
        "hand_count": len(hand or []),
        "library_count": 90,
        "graveyard_count": 0,
        "battlefield": [*lands, *(actor_board or [])],
        "graveyard": [],
        "command": [],
        "hand": [{"object_id": f"hand-{i}", "name": name} for i, name in enumerate(hand or [])],
        "mana_pool": {},
    }
    opponents = [
        {
            "player_id": f"opponent-{seat}",
            "seat": seat,
            "life": opponent_life if seat == 1 else 40,
            "hand_count": 7,
            "library_count": 92,
            "graveyard_count": 0,
            "battlefield": list(opponent_board or []) if seat == 1 else [],
            "graveyard": [],
            "command": [],
        }
        for seat in range(1, 4)
    ]
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 6,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": "precombat_main",
        "players": [actor, *opponents],
        "stack": stack or [],
        "commander_status": [
            {
                "owner_id": "actor",
                "name": "Esior, Wardwing Familiar",
                "commander_damage_to_player": [],
                "casts_from_command": 1,
            }
        ],
    }


def _request(
    decision_class: str,
    options: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    minimum: int = 1,
    maximum: int = 1,
    prompt: str = "",
    context: dict[str, Any] | None = None,
    offset: int = 1,
) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-{decision_class}-{offset}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": state,
        "context": context or {},
        "minimum_selections": minimum,
        "maximum_selections": maximum,
        "legal_options": options,
        "prompt": prompt or decision_class,
    }


def _attack_options(attacker_id: str, name: str) -> list[dict[str, Any]]:
    return [
        {
            "option_id": "hold",
            "label": f"Do not attack with {name}",
            "option_type": "hold_attacker",
            "metadata": {"object_id": attacker_id, "name": name},
        },
        {
            "option_id": "attack-1",
            "label": f"{name} attacks Seat 2",
            "option_type": "declare_attacker",
            "metadata": {"object_id": attacker_id, "name": name, "defender_id": "opponent-1"},
        },
    ]


def _block_option(blocker_id: str, attacker_id: str) -> dict[str, Any]:
    return {
        "option_id": f"block-{blocker_id}",
        "label": f"{blocker_id} blocks {attacker_id}",
        "option_type": "declare_blocker",
        "metadata": {"blocker_id": blocker_id, "attacker_id": attacker_id},
    }


def test_card_knowledge_reads_printed_roles() -> None:
    sol_ring = card_facts("Sol Ring")
    counterspell = card_facts("Counterspell")
    assert sol_ring is not None and CardRole.MANA_SOURCE in card_roles(sol_ring)
    assert counterspell is not None and CardRole.COUNTER in card_roles(counterspell)
    command_tower = card_facts("Command Tower")
    assert command_tower is not None and command_tower.is_land
    assert card_facts("Not A Real Card Name") is None


def test_zero_power_creature_does_not_attack() -> None:
    state = _state(actor_board=[_card("millikin", "Millikin", 0, 1)])
    response = _policy().decide(
        _request("declare_attacker", _attack_options("millikin", "Millikin"), state)
    )
    assert response["selected_option_ids"] == ["hold"]


def test_attacker_holds_back_from_a_blocker_that_eats_it() -> None:
    state = _state(
        actor_board=[_card("drake", "Loyal Drake", 2, 2)],
        opponent_board=[_card("wall", "Orcish Siegemaster", 0, 5, abilities=["Reach"])],
    )
    # Orcish Siegemaster has 0 power, so it cannot kill the Drake: safe attack.
    response = _policy().decide(
        _request("declare_attacker", _attack_options("drake", "Loyal Drake"), state)
    )
    assert response["selected_option_ids"] == ["attack-1"]
    state = _state(
        actor_board=[_card("myr", "Iron Myr", 1, 1)],
        opponent_board=[_card("avatar", "Avatar of Woe", 6, 5)],
    )
    response = _policy().decide(
        _request("declare_attacker", _attack_options("myr", "Iron Myr"), state)
    )
    assert response["selected_option_ids"] == ["hold"]


def test_open_board_attack_is_taken() -> None:
    state = _state(actor_board=[_card("claim", "Claim Jumper", 3, 3)])
    response = _policy().decide(
        _request("declare_attacker", _attack_options("claim", "Claim Jumper"), state)
    )
    assert response["selected_option_ids"] == ["attack-1"]


def test_blocker_that_survives_and_kills_blocks() -> None:
    state = _state(
        actor_board=[_card("dragon", "Dragon Token", 6, 6)],
        opponent_board=[_card("orc", "Merciless Executioner", 3, 1)],
    )
    response = _policy().decide(
        _request("declare_blocker", [_block_option("dragon", "orc")], state, minimum=0)
    )
    assert response["selected_option_ids"] == ["block-dragon"]


def test_no_chump_block_at_healthy_life() -> None:
    state = _state(
        actor_board=[_card("myr", "Iron Myr", 1, 1)],
        opponent_board=[_card("avatar", "Avatar of Woe", 6, 5)],
    )
    response = _policy().decide(
        _request("declare_blocker", [_block_option("myr", "avatar")], state, minimum=0)
    )
    assert response["selected_option_ids"] == []


def test_chump_block_when_the_hit_would_be_lethal() -> None:
    state = _state(
        actor_board=[_card("myr", "Iron Myr", 1, 1)],
        opponent_board=[_card("avatar", "Avatar of Woe", 6, 5)],
        actor_life=6,
    )
    response = _policy().decide(
        _request("declare_blocker", [_block_option("myr", "avatar")], state, minimum=0)
    )
    assert response["selected_option_ids"] == ["block-myr"]


def test_engine_minimum_block_count_is_still_met() -> None:
    state = _state(
        actor_board=[_card("myr", "Iron Myr", 1, 1)],
        opponent_board=[_card("avatar", "Avatar of Woe", 6, 5)],
    )
    response = _policy().decide(
        _request("declare_blocker", [_block_option("myr", "avatar")], state, minimum=1)
    )
    assert response["selected_option_ids"] == ["block-myr"]


def _colors() -> list[dict[str, Any]]:
    return [
        {"option_id": f"color-{name}", "label": name, "option_type": "choice", "metadata": {}}
        for name in ("Blue", "Red", "White")
    ]


def test_mana_color_pick_serves_the_cost_being_paid() -> None:
    policy = _policy()
    # The hand alone would ask for Red; the cost being paid needs Blue.
    state = _state(hand=["Guttersnipe"])
    payment = {
        "option_id": "tap-signet",
        "label": "Arcane Signet — {T}: Add one mana",
        "option_type": "mana_ability",
        "metadata": {"source_name": "Arcane Signet"},
    }
    policy.decide(
        _request("mana_payment", [payment], state, context={"unpaid_mana": "{U}{U}"}, offset=1)
    )
    response = policy.decide(
        _request(
            "choice",
            _colors(),
            state,
            prompt="Pick a mana color",
            context={"outcome": "putmanainpool"},
            offset=2,
        )
    )
    assert response["selected_option_ids"] == ["color-Blue"]


def test_mana_color_pick_without_a_pending_cost_follows_the_hand() -> None:
    state = _state(hand=["Guttersnipe"])
    response = _policy().decide(
        _request(
            "choice",
            _colors(),
            state,
            prompt="Pick a mana color",
            context={"outcome": "putmanainpool"},
        )
    )
    assert response["selected_option_ids"] == ["color-Red"]


def _cast(option_id: str, name: str, **costs: int) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "label": f"{name} — Cast {name}",
        "option_type": "activated_ability",
        "metadata": {
            "source_name": name,
            "source_object_id": f"hand-{option_id}",
            "ability_type": "spell",
            **{f"mana_cost_{color}": value for color, value in costs.items()},
        },
    }


_PASS = {"option_id": "pass", "label": "Pass priority", "option_type": "pass_priority"}


def test_pilot_does_not_counter_its_own_spell() -> None:
    policy = _policy()
    state = _state(hand=["Claim Jumper", "Counterspell"])
    cast = _cast("claim", "Claim Jumper", white=1, generic=2)
    first = policy.decide(_request("priority", [_PASS, cast], state, offset=1))
    assert first["selected_option_ids"] == ["claim"]
    on_stack = _state(
        hand=["Counterspell"], stack=[{"object_id": "spell-1", "name": "Claim Jumper"}]
    )
    counter = _cast("counter", "Counterspell", blue=2)
    second = policy.decide(_request("priority", [_PASS, counter], on_stack, offset=2))
    assert second["selected_option_ids"] == ["pass"]


def test_pilot_does_not_aim_creature_removal_at_an_empty_board() -> None:
    state = _state(hand=["Infernal Grasp"])
    removal = _cast("grasp", "Infernal Grasp", black=1, generic=1)
    response = _policy().decide(_request("priority", [_PASS, removal], state))
    assert response["selected_option_ids"] == ["pass"]


def test_pilot_state_counts_lands_power_and_online_commander() -> None:
    policy = _policy()
    runtime = policy._pilots[1]
    state = _state(
        actor_board=[
            _card("tower", "Command Tower"),
            _card("signet", "Arcane Signet"),
            _card("esior", "Esior, Wardwing Familiar", 1, 3),
            _card("claim", "Claim Jumper", 3, 3),
        ],
        hand=["Counterspell", "Island"],
    )
    view = policy._pilot_state(runtime, state)
    assert view.lands == 4  # three Islands and Command Tower; the Signet is not a land
    assert view.board_power == 4.0
    assert view.commander_online
    commander = view.commanders[0]
    assert commander.casts == 1 and commander.next_cost == commander.base_cost + 2.0
    assert view.role_counts.get(CardRole.COUNTER) == 1


def test_a_cast_that_never_resolves_is_not_retried_forever() -> None:
    # Real games selected "Big Score — Cast Big Score" 838 times in one game:
    # the cast never reached the stack, so the window kept coming back.
    policy = _policy()
    state = _state(hand=["Claim Jumper"])
    cast = _cast("claim", "Claim Jumper", white=1, generic=2)
    picks = []
    for offset in range(1, 6):
        # The window changes each time (a land got tapped, mana floated), so
        # the identical-window guard never trips; only the per-turn cap does.
        varied = _state(hand=["Claim Jumper"])
        varied["players"][0]["mana_pool"] = {"white": offset}
        response = policy.decide(_request("priority", [_PASS, cast], varied, offset=offset))
        picks.append(response["selected_option_ids"])
    assert picks[:3] == [["claim"]] * 3
    assert picks[3:] == [["pass"]] * 2
    next_turn = {**state, "turn_number": state["turn_number"] + 1}
    again = policy.decide(_request("priority", [_PASS, cast], next_turn, offset=6))
    assert again["selected_option_ids"] == ["claim"]
