from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_required_phase85_files_exist(repo_root: Path) -> None:
    required = [
        "scripts/bootstrap_engine_linux.sh",
        "scripts/bootstrap_engine_macos.sh",
        "scripts/bootstrap_engine_windows.ps1",
        "scripts/start_engine.sh",
        "scripts/stop_engine.sh",
        "scripts/verify_engine.sh",
        "scripts/collect_engine_logs.sh",
        "docker/xmage/Dockerfile",
        "docker/forge/Dockerfile",
        "docker-compose.engine.yml",
        ".devcontainer/devcontainer.json",
        "schemas/engine_adapter_protocol.schema.json",
    ]
    for rel in required:
        assert (repo_root / rel).exists(), rel


def _gnu_bash() -> str | None:
    executable = shutil.which("bash")
    if executable is None:
        return None
    completed = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or "GNU bash" not in completed.stdout:
        return None
    return executable


def test_shell_scripts_parse(repo_root: Path) -> None:
    bash = _gnu_bash()
    if bash is None:
        pytest.skip("GNU Bash is unavailable on this runner")

    for rel in (
        "scripts/bootstrap_engine_linux.sh",
        "scripts/bootstrap_engine_macos.sh",
        "scripts/bootstrap_maven.sh",
        "scripts/start_engine.sh",
        "scripts/stop_engine.sh",
        "scripts/verify_engine.sh",
        "scripts/collect_engine_logs.sh",
        "scripts/engine_container_entrypoint.sh",
    ):
        completed = subprocess.run(
            [bash, "-n", str(repo_root / rel)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr


def test_engine_config_is_pinned(repo_root: Path) -> None:
    config = json.loads((repo_root / "config/rules_engines.json").read_text())
    assert len(config["primary_engine"]["commit"]) == 40
    assert len(config["secondary_engine"]["commit"]) == 40
    assert config["current_runtime"]["external_engine_validation_pending"] is True
