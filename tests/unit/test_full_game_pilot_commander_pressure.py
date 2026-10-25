"""The second clock in an attack: commander damage the actor's commanders already dealt (#989 P0-1).

The pilot's win-progress term has always read ``commander_damage_pressure`` on a combat target;
the structural simulator sets it, the full-game path never did, so a defender with 14 commander
damage on it looked like any other. These tests pin the input and its effect on the target.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_attack_ties import _attack_request, _policy


def _with_commander_damage(request: dict[str, Any], dealt: dict[str, float]) -> dict[str, Any]:
    request["pilot_state"]["commander_status"] = [
        {
            "name": "Esior, Wardwing Familiar",
            "owner_id": "actor",
            "casts_from_command": 1,
            "commander_damage_to_player": [
                {"player_id": player_id, "total": total} for player_id, total in dealt.items()
            ],
        }
    ]
    return request


def test_a_defender_the_commander_already_hit_carries_the_pressure() -> None:
    request = _with_commander_damage(_attack_request(), {"opponent-3": 14})
    policy = _policy(1)
    by_defender = {
        option["metadata"]["defender_id"]: policy._combat_action(option, request["pilot_state"])
        for option in request["legal_options"]
        if option["option_type"] == "declare_attacker"
    }
    assert by_defender["opponent-3"].metadata["commander_damage_pressure"] == 14.0
    assert "commander_damage_pressure" not in by_defender["opponent-1"].metadata
    assert "commander_damage_pressure" not in by_defender["opponent-2"].metadata


def test_commander_damage_over_the_limit_is_capped_at_21() -> None:
    request = _with_commander_damage(_attack_request(), {"opponent-1": 30})
    option = next(o for o in request["legal_options"] if o["option_type"] == "declare_attacker")
    action = _policy(1)._combat_action(option, request["pilot_state"])
    assert action.metadata["commander_damage_pressure"] == 21.0


def test_the_pressure_decides_among_defenders_the_pilot_scored_alike() -> None:
    request = _with_commander_damage(_attack_request(), {"opponent-3": 14})
    picks = {_policy(seed).decide(request)["selected_option_ids"][0] for seed in range(8)}
    assert picks == {"attack-3"}


def test_a_commander_of_another_player_is_no_pressure() -> None:
    request = _attack_request()
    request["pilot_state"]["commander_status"] = [
        {
            "name": "Someone Else",
            "owner_id": "opponent-1",
            "casts_from_command": 1,
            "commander_damage_to_player": [{"player_id": "opponent-3", "total": 14}],
        }
    ]
    option = next(o for o in request["legal_options"] if o["option_type"] == "declare_attacker")
    for candidate in request["legal_options"]:
        if candidate["option_type"] == "declare_attacker":
            action = _policy(1)._combat_action(candidate, request["pilot_state"])
            assert "commander_damage_pressure" not in action.metadata
    assert option["option_type"] == "declare_attacker"
