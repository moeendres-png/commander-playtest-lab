"""The tool service's dirty-worktree gate, tested on its own repository.

Every other test runs with a clean-checkout stand-in (``tests/conftest.py``), so a
developer's uncommitted edit cannot fail unrelated tests. These tests keep the real
gate covered against a throwaway git repository, plus the stand-in itself.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from commander_lab.tools.service import CommanderToolService


@pytest.fixture
def dirty(real_worktree_checks: dict[str, Any]) -> Any:
    real = real_worktree_checks.get("tracked_worktree_dirty")
    if real is None:  # the session had not imported the service before this module
        real = CommanderToolService.tracked_worktree_dirty.fget
    return lambda root: bool(real(SimpleNamespace(root=root)))


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "lab@example.invalid")
    _git(tmp_path, "config", "user.name", "Lab")
    (tmp_path / "tracked.txt").write_text("one\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_a_clean_checkout_is_not_dirty(repository: Path, dirty: Any) -> None:
    assert dirty(repository) is False


def test_an_untracked_file_does_not_make_the_checkout_dirty(repository: Path, dirty: Any) -> None:
    (repository / "scratch.txt").write_text("x\n", encoding="utf-8")
    assert dirty(repository) is False


def test_a_modified_tracked_file_makes_the_checkout_dirty(repository: Path, dirty: Any) -> None:
    (repository / "tracked.txt").write_text("two\n", encoding="utf-8")
    assert dirty(repository) is True


def test_outside_a_repository_the_gate_reports_clean(tmp_path: Path, dirty: Any) -> None:
    assert dirty(tmp_path) is False


def test_the_session_sees_a_clean_checkout(repo_root: Path) -> None:
    # The stand-in is active: the service reports clean whatever git says.
    assert CommanderToolService(repo_root).tracked_worktree_dirty is False
