from __future__ import annotations

from pathlib import Path

from commander_lab.engine.process_manager import EngineProcessManager, load_engine_runtime_config


def test_engine_runtime_defaults_to_ignored_runtime_directory(tmp_path: Path) -> None:
    config = load_engine_runtime_config({})

    assert config.log_directory == ".runtime/engine"

    manager = EngineProcessManager(config, root=tmp_path)
    state = manager.diagnose()

    assert state.status.value == "not_configured"
    assert manager.state_path == tmp_path / ".runtime" / "engine" / "xmage.process-state.json"
    assert manager.state_path.exists()
    assert not (tmp_path / "artifacts" / "engine_setup" / "logs").exists()


def test_explicit_engine_log_directory_override_is_preserved(tmp_path: Path) -> None:
    config = load_engine_runtime_config({"ENGINE_LOG_DIRECTORY": "custom-runtime"})
    manager = EngineProcessManager(config, root=tmp_path)

    manager.diagnose()

    assert manager.state_path == tmp_path / "custom-runtime" / "xmage.process-state.json"
    assert manager.state_path.exists()
