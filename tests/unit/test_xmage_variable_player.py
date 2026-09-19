from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from commander_lab.agents import GenericCommanderPilot
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGameConformanceError,
    FullGamePilotBinding,
    FullGameProtocolError,
    XmageFullGameRunner,
    _RuntimePilot,
)
from commander_lab.engine.rules.full_game_batch import FullGameBatchCase
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput

XMAGE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"


def _binding(seat: int, deck_id: str) -> FullGamePilotBinding:
    config = PilotConfig(
        pilot_name="auto",
        strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
        mode=PilotDecisionMode.DETERMINISTIC,
    )
    return FullGamePilotBinding(
        seat=seat,
        deck_id=deck_id,
        strategy="generic",
        commander_names=("Isamaru, Hound of Konda",),
        config=config,
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _deck(seat: int) -> RulesDeckInput:
    return RulesDeckInput(
        deck_id=f"fixture-{seat}",
        name=f"Full-game fixture {seat}",
        commander_names=("Isamaru, Hound of Konda",),
        mainboard=tuple("Plains" for _ in range(99)),
        deck_hash=(f"{seat:x}" * 64)[:64],
    )


def _scenario(player_count: int, seat: int = 1) -> FutureXmageScenario:
    decks = [_deck(index) for index in range(1, player_count + 1)]
    assert decks[seat - 1].deck_hash is not None
    return FutureXmageScenario(
        candidate_id=decks[seat - 1].deck_id,
        deck_hash=decks[seat - 1].deck_hash,  # type: ignore[arg-type]
        opponent_deck_ids=tuple(
            deck.deck_id for index, deck in enumerate(decks, start=1) if index != seat
        ),
        player_count=player_count,  # type: ignore[arg-type]
        seat=seat,
        scenario_id="technical-variable-player",
        seed=17,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _policy(player_count: int, seed: int = 7) -> ExternalPilotDecisionPolicy:
    runtimes = tuple(
        _RuntimePilot(
            binding=_binding(seat, f"fixture-{seat}"),
            pilot=GenericCommanderPilot(_binding(seat, f"fixture-{seat}").config),
        )
        for seat in range(1, player_count + 1)
    )
    return ExternalPilotDecisionPolicy(runtimes, seed)


def _actor_state(player_count: int) -> dict[str, Any]:
    players: list[dict[str, Any]] = [
        {
            "player_id": "actor",
            "seat": 0,
            "life": 40,
            "hand_count": 7,
            "library_count": 92,
            "graveyard_count": 0,
            "battlefield": [],
            "graveyard": [],
            "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
            "hand": [{"object_id": f"card-{index}", "name": "Plains"} for index in range(7)],
            "mana_pool": {"white": 0, "blue": 0, "black": 0, "red": 0, "green": 0,
                          "colorless": 0},
        }
    ]
    for seat in range(1, player_count):
        players.append(
            {
                "player_id": f"opponent-{seat}",
                "seat": seat,
                "life": 40,
                "hand_count": 7,
                "library_count": 92,
                "graveyard_count": 0,
                "battlefield": [],
                "graveyard": [],
                "command": [],
            }
        )
    return {
        "game_id": "opaque-engine-game",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 1,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": None,
        "players": players,
        "stack": [],
    }


def _priority_pass_request(player_count: int) -> dict[str, Any]:
    return {
        "decision_id": "engine-a",
        "decision_offset": 3,
        "actor_id": "actor",
        "decision_class": "priority",
        "pilot_state": _actor_state(player_count),
        "context": {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": [
            {"option_id": "pass", "label": "Pass", "option_type": "pass_priority"},
        ],
    }


def _handshake_lane(min_players: int = 2, max_players: int = 5) -> dict[str, Any]:
    return {
        "full_game_lane": {
            "lane": "xmage_full_game_external_pilots",
            "decision_protocol_version": "xmage-external-decision-protocol-1.0.0",
            "min_players": min_players,
            "max_players": max_players,
            "evidence_class": "technical_conformance_only",
            "generic_capability_promotion": False,
            "one_game_per_process": True,
            "bit_exact_replay_validated": False,
        },
        "capabilities": {
            "commander_supported": True,
            "partner_supported": True,
            "multiplayer_supported": True,
            "headless_supported": True,
            "seed_supported": True,
            "deck_import_supported": True,
            "target_selection_supported": True,
            "mode_selection_supported": True,
            "trigger_order_supported": True,
            "mulligan_supported": True,
        },
    }


@pytest.mark.parametrize("player_count", [2, 3, 4, 5])
def test_policy_accepts_every_supported_count(player_count: int) -> None:
    policy = _policy(player_count)
    response = policy.decide(_priority_pass_request(player_count))
    assert response["selected_option_ids"] == ["pass"]
    assert policy._player_count == player_count


def test_policy_rejects_single_and_six_pilots() -> None:
    with pytest.raises(ValueError):
        _policy(1)
    with pytest.raises(ValueError):
        _policy(6)


def test_policy_rejects_seat_coverage_gap() -> None:
    config = _binding(1, "fixture-1").config
    runtimes = tuple(
        _RuntimePilot(
            binding=_binding(seat, f"fixture-{seat}"),
            pilot=GenericCommanderPilot(config),
        )
        for seat in (1, 2, 4)
    )
    with pytest.raises(ValueError):
        ExternalPilotDecisionPolicy(runtimes, 7)


def test_pilot_state_scales_with_player_count() -> None:
    for player_count in (2, 3, 4, 5):
        policy = _policy(player_count)
        runtime = policy._pilots[1]
        view = policy._pilot_state(runtime, _actor_state(player_count))
        assert view.pod_size == player_count
        assert view.seat_position == 1
        assert len(view.opponents) == player_count - 1
        assert view.opponents_to_act_before_next_turn == player_count - 1


def test_binding_seat_five_accepted_six_rejected() -> None:
    _binding(5, "fixture-5")
    with pytest.raises(ValidationError):
        _binding(6, "fixture-6")


def _mana_request(
    player_count: int, unpaid: str, pool_types: tuple[str, ...], with_ability: bool = True
) -> dict[str, Any]:
    options: list[dict[str, Any]] = []
    for index, mana_type in enumerate(pool_types):
        options.append(
            {
                "option_id": f"pool-{index}",
                "label": f"Spend {mana_type} mana from pool",
                "option_type": "mana_pool",
                "metadata": {"mana_type": mana_type},
            }
        )
    if with_ability:
        options.append(
            {
                "option_id": "ability-0",
                "label": "Plains — {T}: Add {W}.",
                "option_type": "mana_ability",
                "metadata": {},
            }
        )
    options.append(
        {
            "option_id": "cancel",
            "label": "Cancel mana payment",
            "option_type": "cancel_mana_payment",
            "metadata": {},
        }
    )
    return {
        "decision_id": "engine-mana",
        "decision_offset": 11,
        "actor_id": "actor",
        "decision_class": "mana_payment",
        "pilot_state": _actor_state(player_count),
        "context": {"unpaid_mana": unpaid},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": options,
    }


def test_mana_pool_shortcut_pays_generic_costs() -> None:
    policy = _policy(4)
    response = policy.decide(_mana_request(4, "{3}", ("blue",)))
    assert response["selected_option_ids"] == ["pool-0"]


def test_mana_pool_shortcut_pays_exact_colored_requirement() -> None:
    policy = _policy(4)
    response = policy.decide(_mana_request(4, "{1}{W}", ("blue", "white")))
    assert response["selected_option_ids"] == ["pool-1"]


def test_mana_pool_shortcut_never_spends_wrong_color_into_colored_cost() -> None:
    # WS215 liveness guard: spending blue toward {W} loops the native payment
    # request forever. The policy must tap a source or cancel instead.
    policy = _policy(4)
    response = policy.decide(_mana_request(4, "{W}", ("blue",)))
    assert response["selected_option_ids"] != ["pool-0"]
    assert response["selected_option_ids"] in (["ability-0"], ["cancel"])


def test_mana_decision_without_productive_option_fails_closed() -> None:
    policy = _policy(4)
    request = _mana_request(4, "{W}", ("blue",), with_ability=False)
    request["legal_options"] = [
        option for option in request["legal_options"] if option["option_type"] == "mana_pool"
    ]
    with pytest.raises(FullGameProtocolError, match="no productive option"):
        policy.decide(request)


@pytest.mark.parametrize("player_count", [2, 3, 4, 5])
def test_validate_inputs_accepts_exact_coverage(player_count: int) -> None:
    scenario = _scenario(player_count)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    XmageFullGameRunner._validate_inputs(scenario, decks, pilots)


def test_validate_inputs_rejects_mismatched_deck_count() -> None:
    scenario = _scenario(3)
    decks = tuple(_deck(seat) for seat in range(1, 3))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 4))
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._validate_inputs(scenario, decks, pilots)


def test_validate_inputs_rejects_duplicate_deck_identities() -> None:
    scenario = _scenario(2)
    decks = (_deck(1), _deck(1))
    pilots = (_binding(1, "fixture-1"), _binding(2, "fixture-1"))
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._validate_inputs(scenario, decks, pilots)


def test_validate_inputs_rejects_seat_gap() -> None:
    scenario = _scenario(3)
    decks = tuple(_deck(seat) for seat in range(1, 4))
    pilots = (_binding(1, "fixture-1"), _binding(2, "fixture-2"), _binding(4, "fixture-3"))
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._validate_inputs(scenario, decks, pilots)


def test_validate_inputs_rejects_opponent_id_mismatch() -> None:
    scenario = _scenario(2, seat=1).model_copy(
        update={"opponent_deck_ids": ("wrong-opponent",)}
    )
    decks = tuple(_deck(seat) for seat in range(1, 3))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 3))
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._validate_inputs(scenario, decks, pilots)


def test_handshake_accepts_two_to_five_lane() -> None:
    for player_count in (2, 3, 4, 5):
        scenario = _scenario(player_count)
        provider = {"engine": "xmage", "engine_commit": XMAGE_COMMIT}
        XmageFullGameRunner._validate_handshake(scenario, provider, _handshake_lane())


def test_handshake_rejects_legacy_four_only_lane() -> None:
    scenario = _scenario(4)
    provider = {"engine": "xmage", "engine_commit": XMAGE_COMMIT}
    lane = _handshake_lane()
    lane["full_game_lane"] = {
        "lane": "xmage_full_game_external_pilots",
        "decision_protocol_version": "xmage-external-decision-protocol-1.0.0",
        "operational_pod_size": 4,
        "evidence_class": "technical_conformance_only",
        "generic_capability_promotion": False,
        "one_game_per_process": True,
        "bit_exact_replay_validated": False,
    }
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._validate_handshake(scenario, provider, lane)


def test_handshake_rejects_scenario_outside_lane_range() -> None:
    scenario = _scenario(5)
    provider = {"engine": "xmage", "engine_commit": XMAGE_COMMIT}
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._validate_handshake(scenario, provider, _handshake_lane(2, 4))


@pytest.mark.parametrize("player_count", [2, 3, 4, 5])
def test_build_result_requires_one_outcome_per_seat(player_count: int) -> None:
    scenario = _scenario(player_count)
    provider = {"engine_version": "1.4.61", "engine_commit": XMAGE_COMMIT}
    result = {
        "evidence_class": "technical_conformance_only",
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
        "official_campaign_eligible": False,
        "rules_authority": "xmage",
        "decision_policy_authority": "commander_lab_external_pilot",
        "bit_exact_replay_validated": False,
        "seed": scenario.seed,
        "terminal": True,
        "decision_count": 12,
        "outcomes": [
            {"seat": index, "won": index == 0, "lost": index != 0, "left": False,
             "life": 40 if index == 0 else 0}
            for index in range(player_count)
        ],
        "transcript": [],
    }
    built = XmageFullGameRunner._build_result(scenario, provider, result)
    assert built.winner_seats == (1,)
    assert built.terminal is True
    short = dict(result)
    short["outcomes"] = short["outcomes"][:-1]
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._build_result(scenario, provider, short)


@pytest.mark.parametrize("player_count", [2, 3, 4, 5])
def test_batch_case_accepts_exact_coverage(player_count: int) -> None:
    scenario = _scenario(player_count)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    FullGameBatchCase(
        case_id=f"ws215-{player_count}p",
        scenario=scenario,
        decks=decks,
        pilots=pilots,
    )


def test_batch_case_rejects_mismatched_cardinality() -> None:
    scenario = _scenario(3)
    decks = tuple(_deck(seat) for seat in range(1, 3))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 3))
    with pytest.raises(ValidationError):
        FullGameBatchCase(
            case_id="ws215-bad",
            scenario=scenario,
            decks=decks,
            pilots=pilots,
        )
