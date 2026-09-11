"""WS-46 provider translation for immutable WS-44 v1.0.4 records.

This module deliberately reuses the source-audited WS42/WS39 bootstrap only for
card/deck/native object construction.  It rebinds the immutable v1.0.4 request
and adds only provider entry metadata needed to construct pending Rules-Core
entry objects.  It never decides Magic legality or player choices.
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

from successor_contract_v104 import requested_state_digest, requested_state_projection  # noqa: E402


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
            f"WS46_ZONE_MOVE_COMMANDER_OBJECT_MAPPING_NOT_UNIQUE:{record.get('fixture_id')}:{commander_id}:matches={len(matches)}"
        )
    obj = matches[0]
    if obj.get("zone") != event.get("from"):
        raise ValueError(
            f"WS46_ZONE_MOVE_SOURCE_ZONE_MISMATCH:{record.get('fixture_id')}:{obj.get('zone')}:{event.get('from')}"
        )
    return {
        "commander_id": str(commander_id),
        "semantic_id": str(obj["semantic_id"]),
        "owner": str(obj["owner"]),
        "from": str(event["from"]),
        "to": str(event["to"]),
        "commander_choice_timing": str(event["commander_choice_timing"]),
    }


def deck_and_scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decks, scenario = base.deck_and_scenario(record)
    scenario["scenario_id"] = f"WS46-{record['fixture_id']}"
    scenario["ws46_contract_version"] = "commander-lab.semantic-fixture-materialization/1.0.4"

    # Rebind to the immutable WS44 request.  This field is configuration only;
    # WS46 construction proof is lower-level native/provider readback and the
    # independent normalizer explicitly rejects whole-request echo as evidence.
    scenario["successor_requested_state"] = requested_state_projection(record)
    scenario["successor_requested_state_digest"] = requested_state_digest(record)
    if scenario["successor_requested_state_digest"] != record["requested_state_digest"]:
        raise ValueError(f"WS46_V104_REQUESTED_STATE_DIGEST_MISMATCH:{record['fixture_id']}")

    entry = _zone_move_entry(record)
    if entry is not None:
        scenario["ws46_zone_move_entry"] = entry

    # Preserve the exact v1.0.4 dynamic state inputs already emitted by the
    # WS42 translator.  These are setup requests, not construction proof.
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
