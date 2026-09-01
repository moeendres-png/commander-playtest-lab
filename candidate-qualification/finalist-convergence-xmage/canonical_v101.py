"""Provider-neutral v1.0.1 record extraction and state projection helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


COMMANDER = "Rograkh, Son of Rohgahh"
ZONE_KEYS = {"hand", "library", "graveyard", "exile", "battlefield"}


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def seat(player_id: str) -> int:
    if not player_id.startswith("P") or not player_id[1:].isdigit():
        raise ValueError(f"invalid canonical player id: {player_id}")
    return int(player_id[1:])


def deck_and_scenario(record: dict[str, Any], schema: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    player_count = len(record["players"])
    objects = sorted(record["semantic_objects"], key=lambda item: item["semantic_id"])
    decks: list[dict[str, Any]] = []
    players: list[dict[str, Any]] = []
    for number in range(1, player_count + 1):
        player_id = f"P{number}"
        owned = [item for item in objects if item["owner"] == player_id]
        mainboard = [item["card_identity"] for item in owned if item["zone"] != "command"]
        commander_names = [item["card_identity"] for item in owned if item["zone"] == "command"]
        if commander_names != [COMMANDER]:
            raise ValueError(f"canonical commander identity mismatch for {player_id}: {commander_names}")
        deck = {
            "deck_id": f"fc-{record['fixture_id'].lower()}-p{number}",
            "mainboard": mainboard,
            "commander_names": commander_names,
            "sideboard": [],
        }
        deck["deck_hash"] = canonical_sha(deck)
        decks.append(deck)
        zones = {key: [] for key in ZONE_KEYS}
        for item in owned:
            zone = item["zone"]
            if zone == "command":
                continue
            if zone not in zones:
                raise ValueError(f"unsupported Primitive-A zone: {zone}")
            zones[zone].append(
                {
                    "semantic_id": item["semantic_id"],
                    "card_name": item["card_identity"],
                    "tapped": bool(item.get("tapped", False)),
                    "controller_seat": seat(item["controller"]),
                    "face": "main",
                }
            )
        life = next(
            player["life"] for player in record["players"] if player["player_id"] == player_id
        )
        players.append(
            {
                "seat": number,
                "life": life,
                "commander_names": commander_names,
                "zones": zones,
            }
        )
    temporal = record["temporal_state"]
    return decks, {
        "schema_version": schema,
        "scenario_id": f"FINALIST-{record['fixture_id']}",
        "execution_entry_mode": "NATIVE_STATE_LOAD",
        "seed": record["rules_randomness"]["rules_seed"],
        "starting_player_seat": 1,
        "temporal_state": {
            "turn_number": temporal["turn_number"],
            "active_player": temporal["active_player"],
            "priority_player": temporal["priority_player"],
            "phase": temporal["phase"],
            "step": temporal["step"],
        },
        "players": players,
    }


def requested_projection(record: dict[str, Any]) -> dict[str, Any]:
    objects = []
    commanders: dict[str, list[str]] = {}
    for item in sorted(record["semantic_objects"], key=lambda value: value["semantic_id"]):
        if item["zone"] == "command":
            commanders.setdefault(item["owner"], []).append(item["card_identity"])
            continue
        objects.append(
            {
                "semantic_id": item["semantic_id"],
                "card_identity": item["card_identity"],
                "owner": item["owner"],
                "controller": item["controller"],
                "zone": item["zone"],
                "tapped": bool(item.get("tapped", False)),
            }
        )
    return {
        "players": [
            {
                "player_id": item["player_id"],
                "life": item["life"],
                "commanders": sorted(commanders.get(item["player_id"], [])),
            }
            for item in record["players"]
        ],
        "objects": objects,
        "temporal_state": {
            "turn_number": record["temporal_state"]["turn_number"],
            "active_player": record["temporal_state"]["active_player"],
            "priority_player": record["temporal_state"]["priority_player"],
            "phase": record["temporal_state"]["phase"],
            "step": record["temporal_state"]["step"],
        },
    }


def native_projection(
    observation: dict[str, Any], semantic_state: dict[str, Any], status: dict[str, Any]
) -> dict[str, Any]:
    players = []
    for item in observation["players"]:
        command = item.get("command") or []
        players.append(
            {
                "player_id": item["player_id"],
                "life": item["life"],
                "commanders": sorted(card["name"] for card in command if card.get("name")),
            }
        )
    objects = []
    for item in semantic_state["scenario_objects"]:
        owner = f"P{item['owner_seat']}"
        objects.append(
            {
                "semantic_id": item["semantic_id"],
                "card_identity": item["card_name"],
                "owner": owner,
                "controller": f"P{item.get('controller_seat', item['owner_seat'])}",
                "zone": "exile" if item["zone"] == "exiled" else item["zone"],
                "tapped": bool(item.get("tapped", False)),
            }
        )
    objects.sort(key=lambda value: value["semantic_id"])
    step = status["step"]
    if step == "precombat_main":
        step = "main"
    return {
        "players": players,
        "objects": objects,
        "temporal_state": {
            "turn_number": status["turn"],
            "active_player": f"P{status['active_player_seat']}",
            "priority_player": f"P{status['priority_player_seat']}",
            "phase": status["phase"],
            "step": step,
        },
    }


def unique_option(decision: dict[str, Any], predicate, semantic: str) -> dict[str, Any]:
    legal_options = decision.get("legal_options") or []
    matches = [option for option in legal_options if predicate(option)]
    if len(matches) != 1:
        diagnostic = [
            {
                "option_type": option.get("option_type"),
                "label": option.get("label"),
                "metadata": option.get("metadata"),
            }
            for option in legal_options
        ]
        raise RuntimeError(
            "SEMANTIC_OPTION_MATCH_NOT_UNIQUE:"
            f"{semantic}:matches={len(matches)}:offered="
            + json.dumps(diagnostic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
    return matches[0]
