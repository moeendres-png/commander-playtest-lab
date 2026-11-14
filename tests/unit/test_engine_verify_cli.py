from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import typer
from typer.testing import CliRunner

from commander_lab.cli.main import app as console_app
from commander_lab.engine import verify_cli
from commander_lab.engine.process_manager import EngineProcessManager
from commander_lab.models.engine_runtime import EngineProcessStatus, EngineRuntimeConfig

runner = CliRunner()
single = typer.Typer()
single.command()(verify_cli.engine_verify)


def _unreachable_config(root: Path) -> EngineRuntimeConfig:
    return EngineRuntimeConfig(
        provider="xmage",
        start_command=(sys.executable, "-c", "print('must not run')"),
        port=17171,
        log_directory=".runtime/engine",
    )


def test_unreachable_engine_exits_one_and_prints_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        verify_cli, "load_engine_runtime_config", lambda: _unreachable_config(tmp_path)
    )
    monkeypatch.setattr(EngineProcessManager, "port_available", lambda self: False)

    result = runner.invoke(single, ["--root", str(tmp_path)])

    assert result.exit_code == 1
    assert '"status": "unhealthy"' in result.output
    assert EngineProcessStatus.UNHEALTHY.value == "unhealthy"
    assert "already in use" in result.output


def test_healthy_engine_exits_zero(monkeypatch, tmp_path: Path) -> None:
    class _Healthy(EngineProcessManager):
        def start(self):  # type: ignore[no-untyped-def]
            return self._replace(status=EngineProcessStatus.HEALTHY, details=())

    monkeypatch.setattr(verify_cli, "EngineProcessManager", _Healthy)
    monkeypatch.setattr(
        verify_cli, "load_engine_runtime_config", lambda: _unreachable_config(tmp_path)
    )

    result = runner.invoke(single, ["--root", str(tmp_path)])

    assert result.exit_code == 0
    assert '"status": "healthy"' in result.output


def test_root_must_be_an_existing_directory(tmp_path: Path) -> None:
    result = runner.invoke(single, ["--root", str(tmp_path / "missing")])
    assert result.exit_code == 2


def test_console_app_exposes_engine_verify_with_the_same_exit_code(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        verify_cli, "load_engine_runtime_config", lambda: _unreachable_config(tmp_path)
    )
    monkeypatch.setattr(EngineProcessManager, "port_available", lambda self: False)

    result = runner.invoke(console_app, ["engine-verify", "--root", str(tmp_path)])

    assert result.exit_code == 1


def test_module_entry_point_parses_arguments() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "commander_lab.engine.verify_cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    plain_stdout = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", completed.stdout)
    assert "--root" in plain_stdout
