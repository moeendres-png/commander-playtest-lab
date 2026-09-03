"""WS-39 provider translation for immutable WS-32 v1.0.2 records.

Only provider-facing construction metadata is produced. Magic legality and
commander-tax calculation remain exclusively in XMage.
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FC = HERE.parents[0] / "finalist-convergence-xmage"
WS34 = HERE.parents[0] / "ws34-xmage-successor"
sys.path[:0] = [str(FC), str(WS34)]

import canonical_v101 as legacy  # noqa: E402
from successor_contract import requested_state_digest, requested_state_projection  # noqa: E402

SCHEMA = "xmage-qualification-scenario/1.1.0"
ZONE_KEYS = {"hand", "library", "graveyard", "exile", "battlefield"}
COMMANDER_DECK_SIZE = 100
QUALIFICATION_FILLER = "Wastes"


def _seat(player_id: str) -> int:
    return legacy.seat(player_id)


def _commander_entries(record: dict[str, Any]) -> list[dict[str, Any]]:
    state = record.get("commander_state") or {}
    entries = state.get("commanders") or []
    if not isinstance(entries, list):
        raise ValueError("COMMANDER_STATE_COMMANDERS_NOT_LIST")
    by_object = {obj.get("semantic_id"): obj for obj in record.get("semantic_objects") or []}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("COMMANDER_STATE_ENTRY_NOT_OBJECT")
        commander_id = str(entry.get("commander_id") or "")
        if not commander_id or commander_id in seen:
            raise ValueError(f"COMMANDER_STATE_ID_INVALID:{commander_id}")
        seen.add(commander_id)
        object_id = entry.get("object_id")
        obj = by_object.get(object_id) if object_id else None
        owner = entry.get("owner") or (obj or {}).get("owner")
        card_name = (
            entry.get("card_identity")
            or entry.get("card_name")
            or (obj or {}).get("card_identity")
        )
        count = entry.get("prior_command_zone_cast_count", 0)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"COMMANDER_HISTORY_COUNT_INVALID:{commander_id}:{count}")
        if not isinstance(owner, str) or not isinstance(card_name, str) or not card_name:
            raise ValueError(f"COMMANDER_STATE_MAPPING_INCOMPLETE:{commander_id}")
        result.append(
            {
                "seat": _seat(owner),
                "commander_id": commander_id,
                "card_name": card_name,
                "prior_command_zone_cast_count": count,
            }
        )
    return result


def _legal_import_mainboard(commander_names: list[str], player_id: str) -> list[str]:
    """Build a legal inert import bootstrap, independent of frozen semantic objects."""
    required_mainboard = COMMANDER_DECK_SIZE - len(commander_names)
    if required_mainboard < 0:
        raise ValueError(
            "QUALIFICATION_DECK_COMMANDER_OVERFLOW:"
            f"{player_id}:commanders={len(commander_names)}"
        )
    # The imported deck only bootstraps a native Commander game. Frozen semantic
    # objects are materialized separately as real XMage cards by the qualification
    # state loader (CardRepository + Game.loadCards) and validated there. Wastes is
    # a colorless Basic Land, so this bootstrap does not constrain commander color
    # identity and does not add semantic state to the frozen scenario.
    return [QUALIFICATION_FILLER] * required_mainboard


def deck_and_scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the native-load scenario without weakening any WS-32 state."""
    player_count = len(record["players"])
    objects = sorted(record["semantic_objects"], key=lambda item: item["semantic_id"])
    commanders = _commander_entries(record)
    commanders_by_seat: dict[int, list[str]] = {}
    for entry in commanders:
        commanders_by_seat.setdefault(entry["seat"], []).append(entry["card_name"])

    decks: list[dict[str, Any]] = []
    players: list[dict[str, Any]] = []
    for number in range(1, player_count + 1):
        player_id = f"P{number}"
        owned = [item for item in objects if item["owner"] == player_id]
        commander_names = sorted(commanders_by_seat.get(number, []))
        if not commander_names:
            commander_names = sorted(
                item["card_identity"] for item in owned if item["zone"] == "command"
            )
        if not commander_names:
            raise ValueError(f"COMMANDER_IDENTITY_MISSING:{player_id}")
        mainboard = _legal_import_mainboard(commander_names, player_id)
        deck = {
            "deck_id": f"ws39-{record['fixture_id'].lower()}-p{number}",
            "mainboard": mainboard,
            "commander_names": commander_names,
            "sideboard": [],
        }
        deck["deck_hash"] = legacy.canonical_sha(deck)
        decks.append(deck)
        zones = {key: [] for key in ZONE_KEYS}
        for item in owned:
            zone = item["zone"]
            if zone == "command":
                continue
            if zone not in zones:
                raise ValueError(f"UNSUPPORTED_WS39_NATIVE_ZONE:{zone}")
            zones[zone].append(
                {
                    "semantic_id": item["semantic_id"],
                    "card_name": item["card_identity"],
                    "tapped": bool(item.get("tapped", False)),
                    "controller_seat": _seat(item["controller"]),
                    "face": "main",
                }
            )
        life = next(p["life"] for p in record["players"] if p["player_id"] == player_id)
        players.append(
            {
                "seat": number,
                "life": life,
                "commander_names": commander_names,
                "zones": zones,
            }
        )

    temporal = record["temporal_state"]
    scenario = {
        "schema_version": SCHEMA,
        "scenario_id": f"WS39-{record['fixture_id']}",
        "execution_entry_mode": record["execution_entry_mode"],
        "seed": int(record["materialization_digest"][:16], 16) & 0x7FFF_FFFF_FFFF_FFFF,
        "starting_player_seat": 1,
        "temporal_state": {
            "turn_number": temporal["turn_number"],
            "active_player": temporal["active_player"],
            "priority_player": temporal["priority_player"],
            "phase": temporal["phase"],
            "step": temporal["step"],
        },
        "players": players,
        "commander_history": commanders,
        "successor_requested_state": requested_state_projection(record),
        "successor_requested_state_digest": requested_state_digest(record),
    }
    if scenario["successor_requested_state_digest"] != record["requested_state_digest"]:
        raise ValueError("WS32_REQUESTED_STATE_DIGEST_MISMATCH")
    return decks, scenario


def with_v101_seed(record: dict[str, Any]) -> dict[str, Any]:
    copied = deepcopy(record)
    copied.setdefault("rules_randomness", {})["rules_seed"] = (
        int(record["materialization_digest"][:16], 16) & 0x7FFF_FFFF_FFFF_FFFF
    )
    return copied
