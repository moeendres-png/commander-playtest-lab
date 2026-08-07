from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from commander_lab.engine.process_manager import EngineProcessManager
from commander_lab.engine.rules import JsonLineBridgeClient, replay_into_internal_model
from commander_lab.engine.rules.replay import ReplayValidationError
from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    EngineMessageType,
    EngineProcessStatus,
    EngineProtocolRequest,
    EngineReplay,
    EngineRuntimeConfig,
    RuntimeValidationLevel,
)


def test_every_required_message_type_has_a_valid_request_model() -> None:
    for kind in EngineMessageType:
        request = EngineProtocolRequest(
            request_id=f"req-{kind.value}", engine="xmage", message_type=kind
        )
        assert request.protocol_version == ENGINE_PROTOCOL_VERSION
        assert request.wire_dict()["method"] == kind.value


def test_unknown_message_is_deterministically_rejected(repo_root: Path) -> None:
    client = JsonLineBridgeClient(
        (sys.executable, str(repo_root / "scripts/tactical_rules_bridge.py")), cwd=repo_root
    )
    try:
        with pytest.raises(Exception, match="unknown bridge message type"):
            client.request("definitely_unknown")
    finally:
        client.close()


def test_process_manager_healthy_requires_external_handshake(
    repo_root: Path, tmp_path: Path
) -> None:
    config = EngineRuntimeConfig(
        provider="xmage",
        start_command=(
            sys.executable,
            str(repo_root / "tests/fixtures/fake_external_engine_bridge.py"),
        ),
        healthcheck_timeout_seconds=2,
        request_timeout_seconds=2,
        log_directory=str(tmp_path / "engine-process"),
    )
    manager = EngineProcessManager(config, root=repo_root)
    state = manager.start()
    try:
        assert state.status == EngineProcessStatus.HEALTHY
        assert state.capabilities is not None
        assert state.capabilities.runtime_kind == "external_rules_engine"
    finally:
        assert manager.stop().status == EngineProcessStatus.STOPPED


def test_tactical_bridge_cannot_be_healthy_external_xmage(
    repo_root: Path, tmp_path: Path
) -> None:
    config = EngineRuntimeConfig(
        provider="xmage",
        start_command=(sys.executable, str(repo_root / "scripts/tactical_rules_bridge.py")),
        healthcheck_timeout_seconds=2,
        request_timeout_seconds=2,
        log_directory=str(tmp_path / "tactical-process"),
    )
    manager = EngineProcessManager(config, root=repo_root)
    state = manager.start()
    try:
        assert state.status != EngineProcessStatus.HEALTHY
    finally:
        manager.stop()


def test_replay_rejects_silent_unknown_event_without_snapshot() -> None:
    state = {
        "game_id": "g",
        "seed": 1,
        "status": "in_progress",
        "turn_number": 0,
        "active_player_id": "p",
        "priority_player_id": "p",
        "phase": "beginning",
        "players": [{"player_id": "p", "seat": 0, "zones": {}}],
        "event_sequence": 0,
    }
    import hashlib

    events = ({"sequence": 0, "event_type": "unknown"},)
    digest = hashlib.sha256(
        json.dumps(events, sort_keys=True, default=list).encode()
    ).hexdigest()
    replay = EngineReplay(
        engine="tactical",
        engine_version="test",
        validation_level=RuntimeValidationLevel.TACTICAL_ORACLE,
        game_id="g",
        initial_state=state,
        events=events,
        final_state=state,
        event_log_sha256=digest,
    )
    with pytest.raises(ReplayValidationError, match="no internal_state_after"):
        replay_into_internal_model(replay)


def test_tactical_bridge_returns_a_valid_envelope_for_every_message(repo_root: Path) -> None:
    import subprocess

    from commander_lab.models import EngineProtocolResponse

    process = subprocess.Popen(
        [sys.executable, str(repo_root / "scripts/tactical_rules_bridge.py")],
        cwd=repo_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None and process.stdout is not None
    kinds = [
        kind
        for kind in EngineMessageType
        if kind not in {EngineMessageType.SHUTDOWN_GAME, EngineMessageType.SHUTDOWN_ENGINE}
    ]
    kinds.append(EngineMessageType.SHUTDOWN_ENGINE)
    try:
        for kind in kinds:
            request = EngineProtocolRequest(
                request_id=f"wire-{kind.value}",
                engine="tactical",
                game_id=(
                    "missing-game"
                    if kind
                    not in {
                        EngineMessageType.ENGINE_HELLO,
                        EngineMessageType.ENGINE_CAPABILITIES,
                        EngineMessageType.LOAD_DECK,
                        EngineMessageType.CREATE_GAME,
                    }
                    else None
                ),
                message_type=kind,
                payload={},
            )
            process.stdin.write(json.dumps(request.wire_dict()) + "\n")
            process.stdin.flush()
            line = process.stdout.readline()
            assert line, {"message_type": kind.value}
            response = EngineProtocolResponse.from_wire(json.loads(line))
            assert response.request_id == request.request_id
            assert response.protocol_version == ENGINE_PROTOCOL_VERSION
        process.stdin.close()
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()


def test_bridge_client_close_reaps_threads_and_streams(repo_root: Path) -> None:
    client = JsonLineBridgeClient(
        (sys.executable, str(repo_root / "scripts/tactical_rules_bridge.py")), cwd=repo_root
    )
    client.request(EngineMessageType.ENGINE_HELLO)
    process = client._process
    stdout_thread = client._stdout_thread
    stderr_thread = client._stderr_thread
    assert process is not None and stdout_thread is not None and stderr_thread is not None
    client.close()
    assert process.poll() is not None
    assert process.stdin is not None and process.stdin.closed
    assert process.stdout is not None and process.stdout.closed
    assert process.stderr is not None and process.stderr.closed
    assert not stdout_thread.is_alive() and not stderr_thread.is_alive()
    assert client._process is None
    assert client._stdout_thread is None
    assert client._stderr_thread is None


def test_timeout_is_reported_without_false_success(repo_root: Path, tmp_path: Path) -> None:
    script = tmp_path / "hang.py"
    script.write_text("import time; time.sleep(5)", encoding="utf-8")
    client = JsonLineBridgeClient(
        (sys.executable, str(script)), cwd=repo_root, request_timeout_seconds=0.1
    )
    try:
        with pytest.raises(Exception, match=r"timeout|closed"):
            client.request(EngineMessageType.ENGINE_HELLO)
    finally:
        client.close()
