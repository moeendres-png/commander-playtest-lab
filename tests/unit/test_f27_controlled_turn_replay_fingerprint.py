"""F-27 controlled-turn replay observation binding."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from commander_lab.semantic_replay.fingerprint import (
    canonical_actor_view,
    principal_observation_digest,
    public_state_digest,
)


def _state(*, authorized: bool, hand_name: str, face_identity: str) -> dict[str, Any]:
    return {
        "actor_id": "actor",
        "active_player_id": "controlled",
        "priority_player_id": "controlled",
        "phase": "precombat_main",
        "step": "precombat_main",
        "turn_number": 2,
        "players": [
            {
                "player_id": "actor",
                "seat": 0,
                "life": 40,
                "poison_counters": 0,
                "hand_count": 1,
                "library_count": 90,
                "graveyard_count": 0,
                "has_lost": False,
                "has_won": False,
                "is_actor": True,
                "private_state_visible": True,
                "battlefield": [],
                "graveyard": [],
                "command": [],
                "exile_count": 0,
                "granted_library": [],
                "hand": [{"object_id": "actor-card", "name": "Island"}],
                "mana_pool": {"blue": 1},
                "land_plays_remaining": 1,
            },
            {
                "player_id": "controlled",
                "seat": 1,
                "life": 37,
                "poison_counters": 0,
                "hand_count": 1,
                "library_count": 90,
                "graveyard_count": 0,
                "has_lost": False,
                "has_won": False,
                "is_actor": False,
                "private_state_visible": authorized,
                "battlefield": [
                    {
                        "object_id": "face-down",
                        "controller_id": "controlled",
                        "name": "Face Down Creature",
                        "private_identity": face_identity,
                        "power": "2",
                        "toughness": "2",
                        "tapped": False,
                        "damage": 0,
                        "ability_count": 0,
                        "abilities": [],
                        "counters": [],
                    }
                ],
                "graveyard": [],
                "command": [],
                "exile_count": 0,
                "granted_library": [{"object_id": "top", "name": "Brainstorm"}],
                "hand": [{"object_id": "controlled-card", "name": hand_name}],
                "mana_pool": {"red": 1},
                "land_plays_remaining": 0,
            },
        ],
        "stack": [],
        "commander_status": [],
    }


def test_authorized_controlled_private_row_is_bound_into_observation_digest() -> None:
    first = _state(authorized=True, hand_name="Lightning Bolt", face_identity="Grizzly Bears")
    second = deepcopy(first)
    second["players"][1]["hand"][0]["name"] = "Shock"
    second["players"][1]["battlefield"][0]["private_identity"] = "Runeclaw Bear"

    canonical = canonical_actor_view(first)
    controlled = canonical["players"][1]
    assert controlled["hand"] == [{"name": "Lightning Bolt"}]
    assert controlled["mana_pool"] == {"red": 1}
    assert controlled["land_plays_remaining"] == 0
    assert controlled["granted_library"] == [{"name": "Brainstorm"}]
    assert controlled["battlefield"][0]["private_identity"] == "Grizzly Bears"
    assert principal_observation_digest(first) != principal_observation_digest(second)
    assert public_state_digest(first) == public_state_digest(second)


def test_unmarked_smuggled_private_row_stays_out_of_observation_digest() -> None:
    first = _state(authorized=False, hand_name="Lightning Bolt", face_identity="Grizzly Bears")
    second = deepcopy(first)
    second["players"][1]["hand"][0]["name"] = "Shock"
    second["players"][1]["battlefield"][0]["private_identity"] = "Runeclaw Bear"
    second["players"][1]["mana_pool"] = {"red": 99}
    second["players"][1]["granted_library"][0]["name"] = "Ancestral Recall"

    canonical = canonical_actor_view(first)
    controlled = canonical["players"][1]
    assert "hand" not in controlled
    assert "mana_pool" not in controlled
    assert "land_plays_remaining" not in controlled
    assert "granted_library" not in controlled
    assert "private_identity" not in controlled["battlefield"][0]
    assert principal_observation_digest(first) == principal_observation_digest(second)
