from __future__ import annotations

import ast
from pathlib import Path

import pytest

from commander_lab.engine.rules.base import (
    DEFAULT_ENGINE_RUNTIME_DIRECTORY,
    ENGINE_RUNTIME_DIRECTORY_ENV,
    resolve_engine_working_directory,
    RulesEngineUnavailable,
)


ENGINE_LANE_CALLS = {"JsonLineBridgeClient", "ExternalRulesAdapter", "XmageFullGameRunner"}
ENGINE_LANE_FILES = (
    "src/commander_lab/engine/rules/bridge.py",
    "src/commander_lab/engine/rules/full_game.py",
)
ENGINE_LANE_SCRIPTS = (
    "scripts/run_external_b3_regression.py",
    "scripts/run_external_b4a_regression.py",
    "scripts/run_external_b4b_regression.py",
    "scripts/run_external_b4c_regression.py",
    "scripts/run_external_b4d_regression.py",
    "scripts/run_external_b4f_capability_closeout.py",
    "scripts/run_external_b4f_illegal_action_regression.py",
    "scripts/run_external_b4f_provider_pin_validation.py",
    "scripts/run_external_full_game_conformance.py",
    "scripts/run_real_4p_full_game_smoke.py",
    "scripts/run_real_deck_gate.py",
)


def _engine_lane_cwd_keywords(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in ENGINE_LANE_CALLS:
            continue
        for keyword in node.keywords:
            if keyword.arg == "cwd":
                found.append((node.lineno, ast.unparse(keyword.value)))
    return found


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
    from commander_lab.engine.rules.bridge import JsonLineBridgeClient

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENGINE_RUNTIME_DIRECTORY_ENV, raising=False)

    client = JsonLineBridgeClient(("synthetic-bridge",))

    assert client.cwd == str((tmp_path / DEFAULT_ENGINE_RUNTIME_DIRECTORY).resolve())


def test_full_game_client_uses_isolated_default_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.engine.rules.full_game import _RawFullGameClient

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENGINE_RUNTIME_DIRECTORY_ENV, raising=False)

    client = _RawFullGameClient(("synthetic-bridge", "full-game"))

    assert client.cwd == str((tmp_path / DEFAULT_ENGINE_RUNTIME_DIRECTORY).resolve())


def test_no_engine_lane_caller_pins_the_project_root(repo_root: Path) -> None:
    offenders: list[str] = []
    for relative in (*ENGINE_LANE_FILES, *ENGINE_LANE_SCRIPTS):
        path = repo_root / relative
        assert path.is_file(), f"engine-lane file disappeared: {relative}"
        for lineno, value in _engine_lane_cwd_keywords(path):
            if value in {"ROOT", "root", "self.root", "repo_root", "Path.cwd()"}:
                offenders.append(f"{relative}:{lineno} pins the project root as engine cwd")
    assert not offenders, "\n".join(offenders)
