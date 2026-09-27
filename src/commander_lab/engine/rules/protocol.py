from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    EngineMessageType,
    EngineProtocolRequest,
    EngineProtocolResponse,
)

# Phase-8.5 compatibility surface required by the external provider contract.
# Protocol 2 extends this surface but must continue to accept these names while
# XMage/Forge provider bridges are migrated.
REQUIRED_EXTERNAL_MESSAGE_TYPES = (
    EngineMessageType.ENGINE_HELLO,
    EngineMessageType.ENGINE_CAPABILITIES,
    EngineMessageType.LOAD_DECK,
    EngineMessageType.CREATE_GAME,
    EngineMessageType.SET_SEED,
    EngineMessageType.START_GAME,
    EngineMessageType.GET_GAME_STATE,
    EngineMessageType.GET_LEGAL_ACTIONS,
    EngineMessageType.SUBMIT_ACTION,
    EngineMessageType.ADVANCE_PRIORITY,
    EngineMessageType.ADVANCE_PHASE,
    EngineMessageType.GET_EVENT_LOG,
    EngineMessageType.EXPORT_REPLAY,
    EngineMessageType.SHUTDOWN_GAME,
)


def build_protocol_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://commander-playtest-lab.local/schemas/"
            f"engine-adapter-protocol-{ENGINE_PROTOCOL_VERSION}.json"
        ),
        "title": "Commander Lab Engine Adapter Protocol",
        "x-commander-lab-protocol-version": ENGINE_PROTOCOL_VERSION,
        "x-required-external-message-types": [
            item.value for item in REQUIRED_EXTERNAL_MESSAGE_TYPES
        ],
        "oneOf": [
            EngineProtocolRequest.model_json_schema(),
            EngineProtocolResponse.model_json_schema(),
        ],
    }


def write_protocol_schema(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = build_protocol_schema()
    if target.exists():
        try:
            if json.loads(target.read_text(encoding="utf-8")) == schema:
                return target
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    newline = "\r\n" if target.exists() and b"\r\n" in target.read_bytes() else "\n"
    target.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline=newline,
    )
    return target


__all__ = [
    "REQUIRED_EXTERNAL_MESSAGE_TYPES",
    "build_protocol_schema",
    "write_protocol_schema",
]
