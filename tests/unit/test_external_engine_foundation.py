from __future__ import annotations

from commander_lab.engine.rules.protocol import (
    REQUIRED_EXTERNAL_MESSAGE_TYPES,
    build_protocol_schema,
)
from commander_lab.models import ENGINE_PROTOCOL_VERSION, EngineMessageType


def test_protocol_schema_tracks_runtime_protocol_version() -> None:
    schema = build_protocol_schema()

    assert schema["$id"].endswith(
        f"engine-adapter-protocol-{ENGINE_PROTOCOL_VERSION}.json"
    )
    assert schema["x-commander-lab-protocol-version"] == ENGINE_PROTOCOL_VERSION


def test_required_external_compatibility_surface_is_complete() -> None:
    required = {item.value for item in REQUIRED_EXTERNAL_MESSAGE_TYPES}

    assert required == {
        "engine_hello",
        "engine_capabilities",
        "load_deck",
        "create_game",
        "set_seed",
        "start_game",
        "get_game_state",
        "get_legal_actions",
        "submit_action",
        "advance_priority",
        "advance_phase",
        "get_event_log",
        "export_replay",
        "shutdown_game",
    }
    assert set(REQUIRED_EXTERNAL_MESSAGE_TYPES).issubset(set(EngineMessageType))
