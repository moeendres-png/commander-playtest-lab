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
    # The project's curated profile wins where it exists (Sol Ring: strong ramp);
    # printed text fills the gaps (Balefire Liege has no curated profile).
    assert sol_ring is not None and card_roles(sol_ring) == {CardRole.RAMP: 2.2}
    liege = card_facts("Balefire Liege")
    assert liege is not None and CardRole.ENGINE in card_roles(liege)
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


def test_discard_cost_spell_is_not_cast_from_a_one_card_hand() -> None:
    # Big Score with nothing else to discard: the engine reversed the cast
    # after the mana was paid in a real game.
    big_score = _cast("score", "Big Score", red=1, generic=3)
    alone = _state(hand=["Big Score"])
    response = _policy().decide(_request("priority", [_PASS, big_score], alone))
    assert response["selected_option_ids"] == ["pass"]
    with_fodder = _state(hand=["Big Score", "Island"])
    response = _policy().decide(_request("priority", [_PASS, big_score], with_fodder))
    assert response["selected_option_ids"] == ["score"]


def test_lone_blocker_does_not_block_a_menace_attacker() -> None:
    state = _state(
        actor_board=[_card("dragon", "Dragon Token", 6, 6)],
        opponent_board=[_card("rograkh", "Rograkh, Son of Rohgahh", 3, 1, abilities=["Menace"])],
    )
    response = _policy().decide(
        _request("declare_blocker", [_block_option("dragon", "rograkh")], state, minimum=0)
    )
    assert response["selected_option_ids"] == []


def test_a_block_the_engine_keeps_rejecting_is_dropped() -> None:
    # The engine asks again when the declared block was illegal as a whole.
    policy = _policy()
    state = _state(
        actor_board=[_card("dragon", "Dragon Token", 6, 6)],
        opponent_board=[_card("orc", "Merciless Executioner", 3, 1)],
    )
    picks = [
        policy.decide(
            _request(
                "declare_blocker", [_block_option("dragon", "orc")], state, minimum=0, offset=n
            )
        )["selected_option_ids"]
        for n in range(1, 5)
    ]
    assert picks == [["block-dragon"], ["block-dragon"], [], []]


def test_attacks_focus_the_weakest_opponent_that_is_still_in_the_game() -> None:
    from commander_lab.engine.rules.full_game_pilot_views import focus_defender

    state = _state(actor_board=[_card("claim", "Claim Jumper", 3, 3)])
    opponents = state["players"][1:]
    opponents[0]["life"] = 30
    opponents[1]["life"] = 25
    opponents[2]["life"] = 0
    opponents[2]["has_lost"] = True
    assert focus_defender(state) == "opponent-2"
    options = [
        *_attack_options("claim", "Claim Jumper"),
        {
            "option_id": "attack-2",
            "label": "Claim Jumper attacks Seat 3",
            "option_type": "declare_attacker",
            "metadata": {"object_id": "claim", "name": "Claim Jumper", "defender_id": "opponent-2"},
        },
    ]
    response = _policy().decide(_request("declare_attacker", options, state))
    assert response["selected_option_ids"] == ["attack-2"]


def test_pilot_spends_its_mana_on_the_bigger_spell_in_its_main_phase() -> None:
    from commander_lab.engine.rules.full_game_pilot_views import _curve_bonus

    state = _state(
        actor_board=[_card(f"plains-{i}", "Island") for i in range(3)],
        hand=["Iron Myr", "Tor Wauki the Younger"],
    )
    myr = _cast("small", "Iron Myr", generic=2)
    tor = _cast("big", "Tor Wauki the Younger", generic=3, black=1, red=1)
    response = _policy().decide(_request("priority", [_PASS, myr, tor], state))
    assert response["selected_option_ids"] == ["big"]
    assert _curve_bonus(5.0, state) > _curve_bonus(2.0, state) > 0.0
    off_turn = {**state, "active_player_id": "opponent-1"}
    assert _curve_bonus(5.0, off_turn) == 0.0


def test_delve_payment_exiles_a_card_instead_of_looping() -> None:
    policy = _policy()
    state = _state(hand=["Dig Through Time"])
    delve = {
        "option_id": "delve-1",
        "label": "Dig Through Time — Exile a card from your graveyard: Delve",
        "option_type": "special_mana_action",
        "metadata": {},
    }
    cancel = {
        "option_id": "cancel",
        "label": "Cancel mana payment",
        "option_type": "cancel_mana_payment",
        "metadata": {},
    }
    paid = policy.decide(
        _request("mana_payment", [cancel, delve], state, context={"unpaid_mana": "{5}"})
    )
    assert paid["selected_option_ids"] == ["delve-1"]
    graveyard = [
        {"option_id": "g-1", "label": "Arcane Denial", "option_type": "choice"},
        {"option_id": "g-2", "label": "Silence", "option_type": "choice"},
    ]
    exiled = policy.decide(
        _request(
            "choose_object",
            graveyard,
            state,
            minimum=0,
            context={
                "outcome": "exile",
                "target_description": "up to one cards from your graveyard",
            },
            offset=2,
        )
    )
    assert exiled["selected_option_ids"] == ["g-2"]  # Silence costs 1, Arcane Denial 2


def test_mana_repeat_guard_sees_through_re_minted_option_ids() -> None:
    policy = _policy()
    state = _state(hand=["Dig Through Time"])
    cancel = {
        "option_id": "cancel",
        "label": "Cancel mana payment",
        "option_type": "cancel_mana_payment",
        "metadata": {},
    }
    picks = []
    for offset in range(1, 4):
        delve = {
            "option_id": f"delve-{offset}",
            "label": "Dig Through Time — Exile a card from your graveyard: Delve",
            "option_type": "special_mana_action",
            "metadata": {},
        }
        response = policy.decide(
            _request(
                "mana_payment",
                [cancel, delve],
                state,
                context={"unpaid_mana": "{5}"},
                offset=offset,
            )
        )
        picks.append(response["selected_option_ids"][0])
    assert picks[-1] == "cancel"


# Commander judgment (pilot intelligence workstream): who the archenemy is, what
# spot removal, wipes and counterspells are worth spending on.


def _opponent_state(
    boards: dict[int, list[dict[str, Any]]],
    *,
    actor_board: list[dict[str, Any]] | None = None,
    hand: list[str] | None = None,
    stack: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = _state(actor_board=actor_board, hand=hand, stack=stack)
    for index, player in enumerate(state["players"][1:], start=1):
        player["battlefield"] = list(boards.get(index, []))
    return state


def test_archenemy_is_the_player_with_the_clearly_strongest_board() -> None:
    from commander_lab.engine.rules.full_game_pilot_views import archenemy, table_threats

    even = _opponent_state({})
    assert archenemy(even) is None
    state = _opponent_state(
        {
            2: [
                _card("titan", "Grave Titan", 6, 6),
                _card("kaervek", "Kaervek the Merciless", 5, 4),
                _card("ring", "Sol Ring"),
            ]
        }
    )
    threats = table_threats(state)
    assert max(threats, key=threats.__getitem__) == "opponent-2"
    assert archenemy(state) == "opponent-2"
    view = _policy()._pilot_state(_policy()._pilots[1], state)
    assert view.archenemy_player_id == "opponent-2"
    assert max(view.opponents, key=lambda o: o.threat).player_id == "opponent-2"


def test_attacks_go_to_the_archenemy_over_an_empty_board() -> None:
    from commander_lab.engine.rules.full_game_pilot_views import focus_defender

    state = _opponent_state(
        {
            2: [
                _card("titan", "Grave Titan", 6, 6, tapped=True),
                _card("kaervek", "Kaervek the Merciless", 5, 4, tapped=True),
            ]
        }
    )
    assert focus_defender(state) == "opponent-2"
    # An attack that removes a player still beats hitting the leader.
    state["players"][0]["battlefield"].append(_card("jumper", "Claim Jumper", 3, 3))
    state["players"][1]["life"] = 3
    options = [
        *_attack_options("jumper", "Claim Jumper"),
        {
            "option_id": "attack-2",
            "label": "Claim Jumper attacks Seat 3",
            "option_type": "declare_attacker",
            "metadata": {
                "object_id": "jumper",
                "name": "Claim Jumper",
                "defender_id": "opponent-2",
            },
        },
    ]
    response = _policy().decide(_request("declare_attacker", options, state))
    assert response["selected_option_ids"] == ["attack-1"]
    state["players"][1]["life"] = 40
    response = _policy().decide(_request("declare_attacker", options, state))
    assert response["selected_option_ids"] == ["attack-2"]


def test_spot_removal_is_kept_for_a_real_threat() -> None:
    swords = _cast("swords", "Swords to Plowshares", white=1)
    token_only = _opponent_state(
        {1: [_card("token", "Soldier Token", 1, 1)]}, hand=["Swords to Plowshares"]
    )
    response = _policy().decide(_request("priority", [_PASS, swords], token_only))
    assert response["selected_option_ids"] == ["pass"]
    threat = _opponent_state(
        {1: [_card("titan", "Grave Titan", 6, 6)]}, hand=["Swords to Plowshares"]
    )
    response = _policy().decide(_request("priority", [_PASS, swords], threat))
    assert response["selected_option_ids"] == ["swords"]


def test_wipe_waits_until_the_table_is_ahead() -> None:
    from commander_lab.engine.rules.full_game_pilot_views import priority_view_fields

    deluge = _cast("deluge", "Toxic Deluge", black=1, generic=2)
    small = _opponent_state(
        {1: [_card("elf", "Llanowar Elves", 1, 1)]},
        actor_board=[_card("jumper", "Claim Jumper", 3, 3)],
    )
    assert priority_view_fields(deluge, small)[1] == "wipe_nothing_worth_wiping"
    behind = _opponent_state(
        {
            1: [_card("titan", "Grave Titan", 6, 6)],
            2: [_card("kaervek", "Kaervek the Merciless", 5, 4)],
        },
        actor_board=[_card("jumper", "Claim Jumper", 3, 3)],
    )
    assert priority_view_fields(deluge, behind)[1] is None
    ahead = _opponent_state(
        {1: [_card("jumper-2", "Claim Jumper", 3, 3), _card("elf", "Llanowar Elves", 1, 1)]},
        actor_board=[_card("titan", "Grave Titan", 6, 6)],
    )
    assert priority_view_fields(deluge, ahead)[1] == "wipe_hurts_own_board_most"


def test_counterspell_is_kept_for_a_spell_worth_countering() -> None:
    counter = _cast("counter", "Counterspell", blue=2)
    cheap = _state(hand=["Counterspell"], stack=[{"object_id": "s", "name": "Llanowar Elves"}])
    response = _policy().decide(_request("priority", [_PASS, counter], cheap))
    assert response["selected_option_ids"] == ["pass"]
    bomb = _state(hand=["Counterspell"], stack=[{"object_id": "s", "name": "Grave Titan"}])
    response = _policy().decide(_request("priority", [_PASS, counter], bomb))
    assert response["selected_option_ids"] == ["counter"]


def test_card_knowledge_covers_every_owner_coverage_deck() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    missing = sorted(
        str(card["oracle_name"])
        for path in sorted((root / "data/coverage_decks/collection").glob("*.json"))
        for card in json.loads(path.read_text(encoding="utf-8"))["cards"]
        if card_facts(str(card["oracle_name"])) is None
    )
    assert missing == []


def test_aura_and_edict_removal_are_recognised() -> None:
    for name in ("Arrest", "Dehydration", "Gatekeeper of Malakir", "Swords to Plowshares"):
        facts = card_facts(name)
        assert facts is not None and CardRole.REMOVAL in card_roles(facts), name


def test_a_blocker_stays_home_when_the_crack_back_is_dangerous() -> None:
    # Loyal Drake has no vigilance: attacking taps the only blocker.
    state = _opponent_state(
        {1: [_card("titan", "Grave Titan", 6, 6, tapped=True)]},
        actor_board=[_card("drake", "Loyal Drake", 2, 2)],
    )
    response = _policy().decide(
        _request("declare_attacker", _attack_options("drake", "Loyal Drake"), state)
    )
    assert response["selected_option_ids"] == ["attack-1"]
    state["players"][0]["life"] = 15
    response = _policy().decide(
        _request("declare_attacker", _attack_options("drake", "Loyal Drake"), state)
    )
    assert response["selected_option_ids"] == ["hold"]


def test_instant_removal_waits_for_an_opponents_end_step() -> None:
    from commander_lab.engine.rules.full_game_pilot_views import priority_view_fields

    swords = _cast("swords", "Swords to Plowshares", white=1)
    own_main = _opponent_state({1: [_card("titan", "Grave Titan", 6, 6)]})
    assert priority_view_fields(swords, own_main)[0]["metadata"]["instant_timing"] == -0.5
    their_end = _opponent_state({1: [_card("titan", "Grave Titan", 6, 6)]})
    their_end.update(active_player_id="opponent-1", phase="end", step="end_turn")
    assert priority_view_fields(swords, their_end)[0]["metadata"]["instant_timing"] == 0.6
    claim = _cast("claim", "Claim Jumper", white=1, generic=2)
    assert "instant_timing" not in priority_view_fields(claim, own_main)[0]["metadata"]


def test_engine_player_ids_resolve_to_the_seat_tokens_of_the_pilot_view() -> None:
    # Real games: the state names opponents "op-<seat>", while attack options
    # carry the engine's player id. The seat in the label joins them; before,
    # every real attack was scored as an unknown defender.
    from commander_lab.engine.rules.full_game_pilot_views import attack_score, resolve_player

    state = _opponent_state(
        {1: [_card("wall", "Orcish Siegemaster", 0, 5)], 2: [_card("titan", "Grave Titan", 6, 6)]},
        actor_board=[_card("myr", "Iron Myr", 1, 1)],
    )
    for index, player in enumerate(state["players"][1:], start=1):
        player["player_id"] = f"op-{index}"
    option = {
        "option_id": "attack-real",
        "label": "Iron Myr attacks Full Game Seat 3",
        "option_type": "declare_attacker",
        "metadata": {"object_id": "myr", "name": "Iron Myr", "defender_id": "9f1c-engine-uuid"},
    }
    found = resolve_player("9f1c-engine-uuid", option["label"], state)
    assert found is not None and found["player_id"] == "op-2"
    score, facts = attack_score(option, state)
    assert "combat_unknown" not in facts
    assert score < 0.0  # Grave Titan blocks and kills the Myr
