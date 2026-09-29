"""F-31/F-32/F-33 observation fields are replay-bound without public leakage."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from commander_lab.semantic_replay.fingerprint import (
    STATE_DIGEST_VERSION,
    build_object_index,
    canonical_actor_view,
    principal_observation_digest,
    public_state_digest,
    seat_map_from_pilot_state,
)


def _state() -> dict[str, Any]:
    return {
        "actor_id": "p1",
        "active_player_id": "p1",
        "priority_player_id": "p1",
        "phase": "precombat_main",
        "step": "precombat_main",
        "turn_number": 3,
        "players": [
            {
                "player_id": "p1", "seat": 0, "life": 40, "poison_counters": 0,
                "hand_count": 1, "library_count": 88, "graveyard_count": 0,
                "has_lost": False, "has_won": False, "is_actor": True,
                "private_state_visible": True,
                "battlefield": [{"object_id": "morph-permanent", "controller_id": "p1",
                    "name": "", "face_down": True, "private_identity": "Exalted Angel",
                    "power": "2", "toughness": "2", "tapped": False, "damage": 0,
                    "ability_count": 0, "abilities": [], "counters": []}],
                "graveyard": [], "command": [], "exile_count": 1,
                "exile": [{"object_id": "public-exile", "name": "Grizzly Bears"}],
                "library_top_revealed": {"object_id": "top-card", "name": "Forest"},
                "granted_library": [], "hand": [{"object_id": "hand-card", "name": "Island"}],
                "mana_pool": {"blue": 1}, "land_plays_remaining": 1,
            },
            {
                "player_id": "p2", "seat": 1, "life": 40, "poison_counters": 0,
                "hand_count": 0, "library_count": 89, "graveyard_count": 0,
                "has_lost": False, "has_won": False, "is_actor": False,
                "private_state_visible": False, "battlefield": [], "graveyard": [],
                "command": [], "exile_count": 1,
                "exile": [{"object_id": "private-exile", "name": "Counterspell", "face_down": True}],
                "library_top_revealed": None, "granted_library": [],
            },
        ],
        "stack": [{"object_id": "face-down-spell", "name": "Exalted Angel", "face_down": True}],
        "looked_at": [
            {"turn": 2, "title": "Top card", "cards": [{"name": "Brainstorm", "owner_seat": 0}]},
            {"turn": 3, "title": "Gonti look", "cards": [{"name": "Counterspell", "owner_seat": 1}]},
        ],
        "revealed": [{"turn": 3, "title": "Telepathy", "revealed_by_seat": 1,
            "cards": [{"name": "Lightning Bolt", "owner_seat": 1}]}],
        "commander_status": [],
    }


def test_digest_version_marks_expanded_observation_semantics() -> None:
    assert STATE_DIGEST_VERSION == "semantic-state-digest-1.1.0"


def test_principal_view_binds_new_visible_fields() -> None:
    canonical = canonical_actor_view(_state())
    assert canonical["players"][0]["exile"] == [{"name": "Grizzly Bears"}]
    assert canonical["players"][1]["exile"] == [{"name": "Counterspell", "face_down": True}]
    assert canonical["players"][0]["library_top_revealed"] == {"name": "Forest"}
    assert canonical["looked_at"][1]["cards"] == [{"name": "Counterspell", "owner_seat": 1}]
    assert canonical["revealed"][0]["revealed_by_seat"] == 1
    assert canonical["stack"] == [{"name": "Exalted Angel", "face_down": True}]
    assert canonical["players"][0]["battlefield"][0]["face_down"] is True
    assert canonical["players"][0]["battlefield"][0]["private_identity"] == "Exalted Angel"


def test_private_exile_look_and_face_down_names_never_enter_public_digest() -> None:
    first = _state()
    second = deepcopy(first)
    second["players"][1]["exile"][0]["name"] = "Doom Blade"
    second["looked_at"][1]["cards"][0]["name"] = "Demonic Tutor"
    second["stack"][0]["name"] = "Krosan Cloudscraper"
    second["players"][0]["battlefield"][0]["private_identity"] = "Willbender"
    assert principal_observation_digest(first) != principal_observation_digest(second)
    assert public_state_digest(first) == public_state_digest(second)


def test_public_exile_top_and_reveal_change_public_and_principal_digests() -> None:
    baseline = _state()
    variants = []
    changed = deepcopy(baseline)
    changed["players"][0]["exile"][0]["name"] = "Serra Angel"
    variants.append(changed)
    changed = deepcopy(baseline)
    changed["players"][0]["library_top_revealed"]["name"] = "Plains"
    variants.append(changed)
    changed = deepcopy(baseline)
    changed["revealed"][0]["cards"][0]["name"] = "Shock"
    variants.append(changed)
    for variant in variants:
        assert principal_observation_digest(baseline) != principal_observation_digest(variant)
        assert public_state_digest(baseline) != public_state_digest(variant)


def test_look_timeline_order_is_semantic_but_private() -> None:
    first = _state()
    second = deepcopy(first)
    second["looked_at"] = list(reversed(second["looked_at"]))
    assert principal_observation_digest(first) != principal_observation_digest(second)
    assert public_state_digest(first) == public_state_digest(second)


def test_face_down_status_itself_is_public_on_stack() -> None:
    first = _state()
    second = deepcopy(first)
    second["stack"][0]["face_down"] = False
    assert public_state_digest(first) != public_state_digest(second)


def test_object_index_carries_exile_and_public_face_down_characteristics() -> None:
    state = _state()
    index = build_object_index(state, seat_map_from_pilot_state(state))
    assert index["private-exile"]["zone"] == "exile"
    assert index["private-exile"]["face_down"] is True
    assert index["face-down-spell"]["face_down"] is True
    assert index["morph-permanent"]["face_down"] is True
