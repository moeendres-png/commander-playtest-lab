from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.engine.rules.base import (
    DEFAULT_ENGINE_RUNTIME_DIRECTORY,
    ENGINE_RUNTIME_DIRECTORY_ENV,
    RulesEngineUnavailable,
    resolve_engine_working_directory,
)
from commander_lab.engine.rules.bridge import JsonLineBridgeClient
from commander_lab.engine.rules.full_game import _RawFullGameClient


def test_default_engine_cwd_is_isolated_from_caller_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENGINE_RUNTIME_DIRECTORY_ENV, raising=False)

    resolved = resolve_engine_working_directory(None)

    expected = (tmp_path / DEFAULT_ENGINE_RUNTIME_DIRECTORY).resolve()
    assert resolved == str(expected)
    assert expected.is_dir()
    assert expected != tmp_path.resolve()


def test_engine_runtime_directory_override_is_honored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "engine-state"
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(target))

    resolved = resolve_engine_working_directory(None)

    assert resolved == str(target.resolve())
    assert target.is_dir()


def test_explicit_engine_cwd_remains_authoritative(tmp_path: Path) -> None:
    explicit = tmp_path / "intentional"
    assert resolve_engine_working_directory(explicit) == str(explicit)


def test_uncreatable_runtime_directory_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENGINE_RUNTIME_DIRECTORY_ENV, raising=False)

    def fail_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        raise OSError("synthetic mkdir failure")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(RulesEngineUnavailable, match="unable to create"):
        resolve_engine_working_directory(None)


def test_jsonl_client_uses_isolated_default_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENGINE_RUNTIME_DIRECTORY_ENV, raising=False)

    client = JsonLineBridgeClient(("synthetic-bridge",))

    assert client.cwd == str((tmp_path / DEFAULT_ENGINE_RUNTIME_DIRECTORY).resolve())


def test_full_game_client_uses_isolated_default_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENGINE_RUNTIME_DIRECTORY_ENV, raising=False)

    client = _RawFullGameClient(("synthetic-bridge", "full-game"))

    assert client.cwd == str((tmp_path / DEFAULT_ENGINE_RUNTIME_DIRECTORY).resolve())
