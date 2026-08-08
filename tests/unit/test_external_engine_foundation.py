from __future__ import annotations

import sys
from pathlib import Path

from commander_lab.engine.process_manager import EngineProcessManager
from commander_lab.engine.rules.protocol import (
    REQUIRED_EXTERNAL_MESSAGE_TYPES,
    build_protocol_schema,
)
from commander_lab.engine.runtime_evidence import (
    build_runtime_attestation,
    rotate_runtime_log,
)
from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    EngineMessageType,
    EngineProcessStatus,
    EngineRuntimeConfig,
)


def test_protocol_schema_tracks_runtime_protocol_version() -> None:
    schema = build_protocol_schema()

    assert schema["$id"].endswith(f"engine-adapter-protocol-{ENGINE_PROTOCOL_VERSION}.json")
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


def test_log_rotation_keeps_bounded_backups(tmp_path: Path) -> None:
    log = tmp_path / "xmage.log"
    log.write_text("first", encoding="utf-8")
    rotate_runtime_log(log, max_bytes=1, backup_count=2)
    assert not log.exists()
    assert (tmp_path / "xmage.log.1").read_text(encoding="utf-8") == "first"

    log.write_text("second", encoding="utf-8")
    rotate_runtime_log(log, max_bytes=1, backup_count=2)
    assert (tmp_path / "xmage.log.1").read_text(encoding="utf-8") == "second"
    assert (tmp_path / "xmage.log.2").read_text(encoding="utf-8") == "first"


def test_runtime_attestation_never_grants_semantic_validation() -> None:
    attestation = build_runtime_attestation(
        provider="xmage",
        engine_version="test-version",
        protocol_version=ENGINE_PROTOCOL_VERSION,
        pid=123,
        runtime_kind="external_rules_engine",
        start_executable=sys.executable,
    )

    assert attestation["provider"] == "xmage"
    assert attestation["start_executable_sha256"] is not None
    assert attestation["semantic_validation_granted"] is False


def test_busy_engine_port_fails_before_process_spawn(monkeypatch, tmp_path: Path) -> None:
    config = EngineRuntimeConfig(
        provider="xmage",
        start_command=(sys.executable, "-c", "print('must not run')"),
        port=17171,
        log_directory=".runtime/engine",
    )
    manager = EngineProcessManager(config, root=tmp_path)
    monkeypatch.setattr(manager, "port_available", lambda: False)

    state = manager.start()

    assert state.status == EngineProcessStatus.UNHEALTHY
    assert state.pid is None
    assert "already in use" in state.details[0]
