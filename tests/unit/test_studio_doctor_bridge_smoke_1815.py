"""Unit tests for #1815 follow-ups: Popen Cp1252 safety, UNC detection, doctor --bridge-smoke."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from commander_lab.engine.rules.base import ENGINE_RUNTIME_DIRECTORY_ENV
from commander_lab.engine.rules.bridge import JsonLineBridgeClient
from commander_lab.qualification.current_boundary.bridge_launcher import (
    LaunchPlan,
)
from commander_lab.qualification.current_boundary.bridge_launcher import (
    launch as launch_bridge,
)
from commander_lab.qualification.current_boundary.midgame_lane import MidgameLaneClient
from commander_lab.studio import __main__ as studio_cli
from commander_lab.studio import doctor, launch
from commander_lab.studio.game_pool import _ProcessWorker


def test_is_unc_or_network_path_recognizes_wsl_and_unc_shares() -> None:
    assert doctor.is_unc_or_network_path(r"\\wsl.localhost\Ubuntu\home\user\repo")
    assert doctor.is_unc_or_network_path(r"\\wsl$\Ubuntu\home\user\repo")
    assert doctor.is_unc_or_network_path("//wsl.localhost/Ubuntu/repo")
    assert doctor.is_unc_or_network_path(r"\\fileserver\share\dir")
    assert doctor.is_unc_or_network_path(r"\\?\UNC\fileserver\share\dir")
    assert doctor.is_unc_or_network_path("nio://wsl.localhost/Ubuntu/cards.h2.mv.db")
    assert not doctor.is_unc_or_network_path(r"\\?\C:\CommanderStudio\engine-runtime")
    assert not doctor.is_unc_or_network_path(r"C:\CommanderStudio\engine-runtime")
    assert not doctor.is_unc_or_network_path("/tmp/commander-studio")
    assert not doctor.is_unc_or_network_path("")


def test_doctor_engine_runtime_dir_fails_on_wsl_unc_path_and_non_writable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, r"\\wsl.localhost\Ubuntu\repo\.runtime\engine")
    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)
    monkeypatch.setattr(launch, "_java_executable", lambda: "/usr/bin/java")
    monkeypatch.setattr(launch, "_java_major", lambda _java: 17)
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)

    report = doctor.run_doctor(tmp_path, check_dependencies=False)
    assert report["ok"] is False
    checks = report["checks"]
    assert isinstance(checks, list)
    by_name = {c["name"]: c for c in checks}
    runtime_check = by_name["engine_runtime_dir"]
    assert runtime_check["status"] == "FAIL"
    assert "UNC-/WSL-Netzpfad" in str(runtime_check["detail"])
    assert "ENGINE_RUNTIME_DIRECTORY" in str(runtime_check["remediation"])

    # Local regular file colliding with runtime directory must FAIL instead of PASS
    blocker_file = tmp_path / "not_a_dir"
    blocker_file.write_text("x", encoding="utf-8")
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(blocker_file))
    file_check = doctor._check_engine_runtime_dir(tmp_path)
    assert file_check["status"] == "FAIL"
    assert "regulärer Datei" in str(file_check["detail"])

    # Separate UNC data_dir must point remediation at STUDIO_DATA_ENV / --data
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(tmp_path / "local_runtime"))
    data_unc_check = doctor._check_engine_runtime_dir(Path(r"\\wsl.localhost\Ubuntu\data"))
    assert data_unc_check["status"] == "FAIL"
    assert "COMMANDER_LAB_STUDIO_DATA" in str(data_unc_check["remediation"])


def test_doctor_bridge_smoke_reports_plaintext_cp1252_stderr_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_path / "fake_bridge_fail.py"
    script.write_text(
        "\n".join(
            [
                "import json, sys",
                "for raw in sys.stdin:",
                "    req = json.loads(raw)",
                "    rid = req.get('request_id')",
                "    mtype = req.get('message_type')",
                "    if mtype == 'start_engine':",
                "        resp = {'protocol_version': '2.0.0', 'request_id': rid, 'success': True, 'status': 'ok', 'payload': {'lane': 'full_game'}, 'errors': []}",
                "        sys.stdout.write(json.dumps(resp) + '\\n'); sys.stdout.flush()",
                "    elif mtype == 'import_deck':",
                "        sys.stderr.buffer.write('FileChannel.tryLock: Unzul\\u00e4ssige Funktion\\n'.encode('cp1252'))",
                "        sys.stderr.flush()",
                "        resp = {'protocol_version': '2.0.0', 'request_id': rid, 'success': False, 'status': 'error', 'payload': {}, 'errors': [{'code': 'deck_import_failed', 'message': 'XMAGE_CARD_REPOSITORY_INIT_FAILED', 'recoverable': False}]}",
                "        sys.stdout.write(json.dumps(resp) + '\\n'); sys.stdout.flush()",
                "    else:",
                "        resp = {'protocol_version': '2.0.0', 'request_id': rid, 'success': True, 'status': 'ok', 'payload': {'shutdown': 'graceful'}, 'errors': []}",
                "        sys.stdout.write(json.dumps(resp) + '\\n'); sys.stdout.flush()",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(tmp_path / "runtime"))
    monkeypatch.setenv(
        launch.ENGINE_COMMAND_ENV,
        launch.command_text((sys.executable, str(script), "full-game")),
    )
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)
    monkeypatch.setattr(
        doctor,
        "_check_engine_runtime_dir",
        lambda _dir: {
            "name": "engine_runtime_dir",
            "status": "PASS",
            "required": True,
            "detail": "ok",
            "remediation": None,
        },
    )

    code = studio_cli.main(["--data", str(tmp_path), "doctor", "--bridge-smoke"])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL] bridge_smoke:" in out
    assert "lokale Bridge-Diagnose (Klartext, nicht exportiert):" in out
    assert "FileChannel.tryLock: Unzul\\xe4ssige Funktion" in out


def test_doctor_bridge_smoke_passes_on_healthy_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_path / "fake_bridge_ok.py"
    script.write_text(
        "\n".join(
            [
                "import json, sys",
                "for raw in sys.stdin:",
                "    req = json.loads(raw)",
                "    rid = req.get('request_id')",
                "    mtype = req.get('message_type')",
                "    if mtype == 'start_engine':",
                "        payload = {'lane': 'full_game'}",
                "    elif mtype == 'import_deck':",
                "        payload = {'deck_handle': {'handle_id': 'smoke-handle-1'}}",
                "    elif mtype == 'shutdown_engine':",
                "        payload = {'shutdown': 'graceful'}",
                "    else:",
                "        payload = {}",
                "    resp = {'protocol_version': '2.0.0', 'request_id': rid, 'success': True, 'status': 'ok', 'payload': payload, 'errors': []}",
                "    sys.stdout.write(json.dumps(resp) + '\\n'); sys.stdout.flush()",
                "    if mtype == 'shutdown_engine': break",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(tmp_path / "runtime"))
    monkeypatch.setenv(
        launch.ENGINE_COMMAND_ENV,
        launch.command_text((sys.executable, str(script), "full-game")),
    )
    monkeypatch.setattr("commander_lab.studio.builder.sim_readiness_available", lambda: True)

    code = studio_cli.main(["--data", str(tmp_path), "doctor", "--bridge-smoke", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    by_name = {c["name"]: c for c in payload["checks"]}
    assert by_name["bridge_smoke"]["status"] == "PASS"
    assert "local_only_diagnostics" not in by_name["bridge_smoke"]


def test_json_line_bridge_client_survives_cp1252_stderr(tmp_path: Path) -> None:
    script = tmp_path / "cp1252_bridge.py"
    script.write_text(
        "\n".join(
            [
                "import json, sys",
                "sys.stderr.buffer.write('Unzul\\u00e4ssige Funktion \\u00e4\\u00f6\\u00fc\\n'.encode('cp1252'))",
                "sys.stderr.buffer.write(b'after cp1252\\n')",
                "sys.stderr.flush()",
                "for raw in sys.stdin:",
                "    req = json.loads(raw)",
                "    sys.stdout.write(json.dumps({'protocol_version': req.get('protocol_version', '1.0'), 'request_id': req.get('request_id'), 'ok': True}) + '\\n')",
                "    sys.stdout.flush()",
            ]
        ),
        encoding="utf-8",
    )
    client = JsonLineBridgeClient((sys.executable, str(script)), cwd=tmp_path, engine="xmage")
    try:
        client.start()
        assert client._stderr_thread is not None
        assert any("after cp1252" in line for line in _wait_stderr(client))
        assert client._stderr_thread.is_alive()
    finally:
        client.close()


def _wait_stderr(client: JsonLineBridgeClient) -> tuple[str, ...]:
    import time

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        tail = client.stderr_tail
        if any("after cp1252" in line for line in tail):
            return tail
        time.sleep(0.05)
    return client.stderr_tail


def test_bridge_launcher_midgame_and_process_worker_decode_cp1252_stderr(
    tmp_path: Path,
) -> None:
    import queue

    script = tmp_path / "cp1252_worker.py"
    script.write_text(
        "\n".join(
            [
                "import json, sys, time",
                "sys.stderr.buffer.write('Unzul\\u00e4ssige \\u00e4\\n'.encode('cp1252'))",
                "sys.stderr.buffer.write(b'ok-stderr\\n\\xe4')",
                "sys.stderr.flush()",
                "sys.stdout.write(json.dumps({'type': 'ready'}) + '\\n'); sys.stdout.flush()",
            ]
        ),
        encoding="utf-8",
    )
    plan = LaunchPlan(
        candidate="xmage",
        lane="protocol2",
        argv=(sys.executable, str(script)),
        cwd=tmp_path,
        env_overrides={},
        expected_engine_commit="0" * 40,
        build_identity={},
        workspace=str(tmp_path),
    )
    bp = launch_bridge(plan)
    try:
        assert isinstance(bp.popen.stderr, io.TextIOWrapper)
        assert bp.popen.stderr.errors == "backslashreplace"
        bp.popen.wait(timeout=5.0)
        bp.close()
        cap = bp.stderr_capture()
        assert "Unzul\\xe4ssige \\xe4" in cap.text
        assert "ok-stderr" in cap.text
        assert cap.text.endswith("\\xe4")
    finally:
        if bp.popen.poll() is None:
            bp.popen.kill()
            bp.popen.wait(timeout=2.0)

    mid = MidgameLaneClient(
        argv=(sys.executable, str(script)),
        cwd=tmp_path,
    )
    with mid:
        assert mid._process is not None
        assert isinstance(mid._process.stderr, io.TextIOWrapper)
        assert mid._process.stderr.errors == "backslashreplace"
        mid._process.wait(timeout=5.0)
    mid_cap = mid.stderr_capture()
    assert "Unzul\\xe4ssige \\xe4" in mid_cap.text
    assert "ok-stderr" in mid_cap.text

    events: queue.Queue[tuple[Any, dict[str, object] | None]] = queue.Queue()
    worker = _ProcessWorker("test-cp1252", [sys.executable, str(script)], {}, events)
    try:
        assert isinstance(worker.proc.stderr, io.TextIOWrapper)
        assert worker.proc.stderr.errors == "backslashreplace"
        worker.proc.wait(timeout=5.0)
        worker._err.join(timeout=2.0)
        assert any("Unzul\\xe4ssige \\xe4" in line for line in worker.stderr_tail)
        assert any("ok-stderr" in line for line in worker.stderr_tail)
    finally:
        if worker.proc.poll() is None:
            worker.proc.kill()
            worker.proc.wait(timeout=2.0)


def test_doctor_bridge_smoke_fails_on_missing_subcommand_or_ungraceful_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(tmp_path / "runtime"))
    custom = tmp_path / "wrapper.py"
    custom.write_text("print('hi')\n", encoding="utf-8")
    monkeypatch.setenv(
        launch.ENGINE_COMMAND_ENV, launch.command_text((sys.executable, str(custom)))
    )
    res_no_arg = doctor._check_bridge_smoke(tmp_path, [sys.executable, str(custom)], None)
    assert res_no_arg["status"] == "FAIL"
    assert res_no_arg["error_code"] == "ValueError"
    assert "full-game" in str(res_no_arg["remediation"])

    script = tmp_path / "bad_shutdown.py"
    script.write_text(
        "\n".join(
            [
                "import json, sys, time",
                "for raw in sys.stdin:",
                "    req = json.loads(raw)",
                "    rid = req.get('request_id')",
                "    mtype = req.get('message_type')",
                "    if mtype == 'shutdown_engine':",
                "        time.sleep(10)",
                "        break",
                "    payload = {'lane': 'full_game'} if mtype == 'start_engine' else {'deck_handle': {'handle_id': 'h1'}}",
                "    sys.stdout.write(json.dumps({'protocol_version': '2.0.0', 'request_id': rid, 'success': True, 'status': 'ok', 'payload': payload, 'errors': []}) + '\\n')",
                "    sys.stdout.flush()",
            ]
        ),
        encoding="utf-8",
    )
    orig_client = doctor.FullGameBridgeClient

    def _fast_client(command: tuple[str, ...], *, request_timeout_seconds: float = 30.0) -> Any:
        return orig_client(
            command,
            request_timeout_seconds=0.4,
            shutdown_grace_seconds=0.3,
        )

    monkeypatch.setattr(doctor, "FullGameBridgeClient", _fast_client)
    res_ungraceful = doctor._check_bridge_smoke(
        tmp_path, [sys.executable, str(script), "full-game"], None
    )
    assert res_ungraceful["status"] == "FAIL"
    assert res_ungraceful["error_code"] in {"BRIDGE_SMOKE_UNGRACEFUL_SHUTDOWN", "ENGINE_FAILURE"}

    # Process exits immediately after import_deck without graceful shutdown -> shutdown_disposition == already_exited
    script_early = tmp_path / "early_exit.py"
    script_early.write_text(
        "\n".join(
            [
                "import json, sys",
                "for raw in sys.stdin:",
                "    req = json.loads(raw)",
                "    rid = req.get('request_id')",
                "    mtype = req.get('message_type')",
                "    payload = {'lane': 'full_game'} if mtype == 'start_engine' else {'deck_handle': {'handle_id': 'h1'}}",
                "    sys.stdout.write(json.dumps({'protocol_version': '2.0.0', 'request_id': rid, 'success': True, 'status': 'ok', 'payload': payload, 'errors': []}) + '\\n')",
                "    sys.stdout.flush()",
                "    if mtype == 'import_deck':",
                "        break",
            ]
        ),
        encoding="utf-8",
    )
    res_early = doctor._check_bridge_smoke(
        tmp_path, [sys.executable, str(script_early), "full-game"], None
    )
    assert res_early["status"] == "FAIL"
    assert res_early["error_code"] in {"BRIDGE_SMOKE_UNGRACEFUL_SHUTDOWN", "ENGINE_FAILURE"}

    # Explicit shutdown_disposition check when close() itself does not raise
    class _StubUngracefulClient:
        stderr_tail = ("stub-stderr",)
        shutdown_disposition = "forced_kill"

        def __init__(self, *_a: Any, **_kw: Any) -> None:
            pass

        def __enter__(self) -> _StubUngracefulClient:
            return self

        def __exit__(self, *_a: Any) -> None:
            return None

        def request(
            self, message_type: str, _payload: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            if message_type == "start_engine":
                return {"lane": "full_game"}
            return {"deck_handle": {"handle_id": "h1"}}

    monkeypatch.setattr(doctor, "FullGameBridgeClient", _StubUngracefulClient)
    res_stub = doctor._check_bridge_smoke(
        tmp_path, [sys.executable, str(script_early), "full-game"], None
    )
    assert res_stub["status"] == "FAIL"
    assert res_stub["error_code"] == "ENGINE_FAILURE"
    assert any("forced_kill" in str(line) for line in res_stub["local_only_diagnostics"])
