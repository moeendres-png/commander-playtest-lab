"""The external engine process must never run in the Git worktree.

XMage hardcodes its H2 card repository at ``jdbc:h2:file:./db/cards.h2``
(``DatabaseUtils.prepareH2Connection``), i.e. relative to the *process* working
directory. A first real game therefore materializes a multi-hundred-megabyte
database in whatever directory the engine was spawned from. Spawning it from the
repository root drops that state into the tracked worktree.

Two failure modes are guarded here:

1. a caller pinning the project root as the engine working directory, which
   bypasses the shared runtime-state default entirely; and
2. the default itself regressing back to inheriting the caller's directory.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from commander_lab.engine.rules.base import (
    DEFAULT_ENGINE_RUNTIME_DIRECTORY,
    ENGINE_RUNTIME_DIRECTORY_ENV,
    RulesEngineUnavailable,
    resolve_engine_working_directory,
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
    """Return every ``cwd=`` keyword value passed to an engine-lane constructor."""
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
            if keyword.arg != "cwd":
                continue
            value = ast.unparse(keyword.value)
            found.append((node.lineno, value))
    return found


def test_no_engine_lane_caller_pins_the_project_root(repo_root: Path) -> None:
    """No engine-lane caller may set the engine working directory to the repo root."""
    offenders: list[str] = []
    for relative in (*ENGINE_LANE_FILES, *ENGINE_LANE_SCRIPTS):
        path = repo_root / relative
        assert path.is_file(), f"engine-lane file disappeared: {relative}"
        for lineno, value in _engine_lane_cwd_keywords(path):
            if value in {"ROOT", "root", "self.root", "repo_root", "Path.cwd()"}:
                offenders.append(f"{relative}:{lineno} pins the project root as the engine cwd")
    assert not offenders, "\n".join(offenders)


def test_unset_cwd_resolves_to_the_shared_runtime_state_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENGINE_RUNTIME_DIRECTORY_ENV, raising=False)
    resolved = resolve_engine_working_directory(None)
    assert resolved is not None
    assert Path(resolved) == tmp_path / DEFAULT_ENGINE_RUNTIME_DIRECTORY
    # The directory must exist before it is handed to subprocess, otherwise the
    # spawn fails with an opaque FileNotFoundError instead of a rules error.
    assert Path(resolved).is_dir()


def test_runtime_directory_is_configurable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "elsewhere" / "engine-state"
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(target))
    resolved = resolve_engine_working_directory(None)
    assert resolved is not None
    assert Path(resolved) == target
    assert target.is_dir()


def test_explicit_cwd_is_honoured_and_not_overridden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit working directory keeps caller authority and is never rewritten."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(tmp_path / "from-env"))
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    assert resolve_engine_working_directory(explicit) == str(explicit)
    assert resolve_engine_working_directory(str(explicit)) == str(explicit)


def test_unusable_runtime_directory_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An uncreatable runtime directory must fail closed, never fall back to the worktree."""
    monkeypatch.chdir(tmp_path)
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv(ENGINE_RUNTIME_DIRECTORY_ENV, str(blocker / "engine"))
    with pytest.raises(RulesEngineUnavailable):
        resolve_engine_working_directory(None)
