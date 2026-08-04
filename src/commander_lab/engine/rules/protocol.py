from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import EngineProtocolRequest, EngineProtocolResponse


def build_protocol_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://commander-playtest-lab.local/schemas/engine-adapter-protocol-1.0.0.json",
        "title": "Commander Lab Engine Adapter Protocol",
        "oneOf": [
            EngineProtocolRequest.model_json_schema(),
            EngineProtocolResponse.model_json_schema(),
        ],
    }


def write_protocol_schema(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_protocol_schema(), indent=2, sort_keys=True), encoding="utf-8")
    return target


__all__ = ["build_protocol_schema", "write_protocol_schema"]
