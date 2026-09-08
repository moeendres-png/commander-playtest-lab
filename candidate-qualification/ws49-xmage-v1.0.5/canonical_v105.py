"""WS-49 provider translation for immutable WS-47 v1.0.5 records.

Reuses only the source-audited WS42/WS39 native bootstrap surfaces.  All
v1.0.5 requested state remains immutable; provider translation may only create
native setup metadata and never Magic legality or discretionary choices.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS42 = HERE.parents[0] / "ws42-xmage-v1.0.3"
sys.path.insert(0, str(WS42))

import canonical_v103 as base  # noqa: E402

from successor_contract_v105 import (  # noqa: E402
    CONTRACT_VERSION,
    requested_state_digest,
    requested_state_projection,
)


def _zone_move_entry(record: dict[str, Any]) -> dict[str, Any] | None:
    event = record.get("zone_move_event")
    if not event:
        return None
    commander_id = event.get("commander_id")
    matches = [
        obj for obj in (record.get("semantic_objects") or [])
        if obj.get("commander_id") == commander_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"WS49_ZONE_MOVE_COMMANDER_OBJECT_MAPPING_NOT_UNIQUE:{record.get('fixture_id')}:{commander_id}:matches={len(matches)}"
        )
    obj = matches[0]
    if obj.get("zone") != event.get("from"):
        raise ValueError(
            f"WS49_ZONE_MOVE_SOURCE_ZONE_MISMATCH:{record.get('fixture_id')}:{obj.get('zone')}:{event.get('from')}"
        )
    return {
        "commander_id": str(commander_id),
        "semantic_id": str(obj["semantic_id"]),
        "owner": str(obj["owner"]),
        "from": str(event["from"]),
        "to": str(event["to"]),
        "commander_choice_timing": str(event["commander_choice_timing"]),
    }


def _natural_deck_templates(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    state = record.get("deck_state") or {}
    raw = state.get("deck_template")
    if not isinstance(raw, list):
        raise ValueError(f"WS49_NATURAL_DECK_TEMPLATE_NOT_LIST:{record.get('fixture_id')}")
    result: dict[str, dict[str, Any]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"WS49_NATURAL_DECK_TEMPLATE_ENTRY_NOT_OBJECT:{record.get('fixture_id')}")
        player = entry.get("player") or entry.get("player_id")
        if not isinstance(player, str) or not player.startswith("P"):
            raise ValueError(f"WS49_NATURAL_DECK_TEMPLATE_PLAYER_INVALID:{record.get('fixture_id')}:{player!r}")
        if player in result:
            raise ValueError(f"WS49_NATURAL_DECK_TEMPLATE_DUPLICATE:{record.get('fixture_id')}:{player}")
        result[player] = entry
    expected = {p["player_id"] for p in record["players"]}
    if set(result) != expected:
        raise ValueError(
            f"WS49_NATURAL_DECK_TEMPLATE_PLAYERS_MISMATCH:{record.get('fixture_id')}:expected={sorted(expected)}:actual={sorted(result)}"
        )
    return result


def _template_library(entry: dict[str, Any], fixture_id: str, player: str) -> tuple[str, int]:
    library = entry.get("library_template")
    if not isinstance(library, dict):
        raise ValueError(f"WS49_NATURAL_LIBRARY_TEMPLATE_MISSING:{fixture_id}:{player}")
    name = library.get("card_identity")
    count = library.get("count")
    if not isinstance(name, str) or not name or not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError(f"WS49_NATURAL_LIBRARY_TEMPLATE_INVALID:{fixture_id}:{player}:{library!r}")
    return name, count


def _template_commander(entry: dict[str, Any], fixture_id: str, player: str) -> str:
    commander = entry.get("commander")
    if isinstance(commander, dict):
        name = commander.get("card_identity") or commander.get("card_name")
    else:
        name = entry.get("commander_card_identity")
    if not isinstance(name, str) or not name:
        raise ValueError(f"WS49_NATURAL_COMMANDER_TEMPLATE_INVALID:{fixture_id}:{player}:{entry!r}")
    return name


def _apply_natural_start(
    record: dict[str, Any],
    decks: list[dict[str, Any]],
    scenario: dict[str, Any],
) -> None:
    fixture_id = str(record["fixture_id"])
    templates = _natural_deck_templates(record)
    players_by_seat = {int(p["seat"]): p for p in scenario["players"]}
    if len(decks) != len(players_by_seat):
        raise ValueError(f"WS49_NATURAL_DECK_PLAYER_COUNT_MISMATCH:{fixture_id}")

    for seat, deck in enumerate(decks, 1):
        player = f"P{seat}"
        entry = templates[player]
        library_name, library_count = _template_library(entry, fixture_id, player)
        commander_name = _template_commander(entry, fixture_id, player)
        opening = entry.get("opening_hand_size")
        if opening != 7:
            raise ValueError(f"WS49_NATURAL_OPENING_HAND_SIZE_UNSUPPORTED:{fixture_id}:{player}:{opening!r}")
        if entry.get("shuffle_required") is not True:
            raise ValueError(f"WS49_NATURAL_SHUFFLE_REQUIRED_NOT_TRUE:{fixture_id}:{player}")

        # Exact native deck input.  No provider filler is permitted for
        # NATURAL_GAME_START: XMage itself must shuffle/draw this deck.
        deck["mainboard"] = [library_name] * library_count
        deck["commander_names"] = [commander_name]
        deck["deck_id"] = f"ws49-{fixture_id.lower()}-p{seat}-natural"
        # inherited importer recomputes/validates the hash only as opaque deck
        # provenance; use its canonical helper through the bootstrap module.
        deck["deck_hash"] = base.base.legacy.canonical_sha({
            "deck_id": deck["deck_id"],
            "mainboard": deck["mainboard"],
            "commander_names": deck["commander_names"],
            "sideboard": deck.get("sideboard", []),
        })

        spec = players_by_seat[seat]
        spec["commander_names"] = [commander_name]
        spec["natural_library_card_name"] = library_name
        spec["natural_library_card_count"] = library_count
        zones = spec.get("zones")
        if not isinstance(zones, dict):
            raise ValueError(f"WS49_NATURAL_ZONES_MISSING:{fixture_id}:{player}")
        for key in ("hand", "library", "graveyard", "exile", "battlefield"):
            zones[key] = []


def deck_and_scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decks, scenario = base.deck_and_scenario(record)
    scenario["scenario_id"] = f"WS49-{record['fixture_id']}"
    scenario["ws46_contract_version"] = CONTRACT_VERSION

    if record.get("execution_entry_mode") == "NATURAL_GAME_START":
        _apply_natural_start(record, decks, scenario)

    scenario["successor_requested_state"] = requested_state_projection(record)
    scenario["successor_requested_state_digest"] = requested_state_digest(record)
    if scenario["successor_requested_state_digest"] != record["requested_state_digest"]:
        raise ValueError(f"WS49_V105_REQUESTED_STATE_DIGEST_MISMATCH:{record['fixture_id']}")

    entry = _zone_move_entry(record)
    if entry is not None:
        scenario["ws46_zone_move_entry"] = entry

    for key in (
        "ws42_combat_state",
        "ws42_extra_turn_creation",
        "ws42_elimination_trigger",
        "ws42_knowledge_state",
        "ws42_zone_move_event",
        "ws42_revealed_state",
        "ws42_commander_damage_matrix",
    ):
        if key in scenario:
            scenario[key] = copy.deepcopy(scenario[key])
    return decks, scenario
