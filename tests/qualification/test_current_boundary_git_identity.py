"""B4: every Git fact used for evidence credit must fail closed.

The runner's ``git()`` helper ran with ``check=False`` and returned ``stdout.strip()``
unconditionally, so a failed Git call (missing repository, unborn HEAD, redirecting
environment) produced an empty or *other-repository* identity that flowed into
evidence documents as if it were measured. These tests pin the fail-closed contract:

* a Git fact that cannot be established raises instead of returning "";
* an inherited ``GIT_DIR``/``GIT_WORK_TREE`` cannot redirect the read;
* HEAD/tree facts are validated as full SHAs;
* the runner does not fabricate a suite engine tree at import time from an ambient
  path that may not be a repository.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"


def live_git(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def init_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "config", "user.email", "b4@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "B4 Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "file.txt").write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=path, check=True)
    return live_git("rev-parse", "HEAD", cwd=path)


def runner_module(monkeypatch: pytest.MonkeyPatch, *, forge_workspace: Path | None = None):
    """Load the runner script as a module under an explicit Forge workspace."""
    if forge_workspace is None:
        monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    else:
        monkeypatch.setenv("FORGE_WORKSPACE", str(forge_workspace))
    spec = importlib.util.spec_from_file_location("current_boundary_runner_b4", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def runner_error(module: object) -> type[BaseException]:
    """The runner's own fail-closed Git error, or the strictest fallback."""
    return getattr(module, "RunnerGitError", RuntimeError)


def test_git_fact_fails_closed_outside_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    with pytest.raises(runner_error(module)):
        module.git("rev-parse", "HEAD", cwd=tmp_path)


def test_git_fact_fails_closed_on_an_unborn_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    empty = tmp_path / "empty"
    subprocess.run(["git", "init", "-q", str(empty)], check=True)
    with pytest.raises(runner_error(module)):
        module.git_sha("rev-parse", "HEAD", cwd=empty)


def test_git_toplevel_refuses_a_non_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    with pytest.raises(runner_error(module)):
        module.git_toplevel(tmp_path)


def test_inherited_git_environment_cannot_redirect_the_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    decoy = tmp_path / "decoy"
    decoy_commit = init_repo(decoy)
    expected = live_git("rev-parse", "HEAD", cwd=REPO)
    assert decoy_commit != expected
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    assert module.git("rev-parse", "HEAD", cwd=REPO) == expected


def test_head_facts_are_validated_full_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    commit = module.git_sha("rev-parse", "HEAD", cwd=REPO)
    assert len(commit) == 40 and commit == live_git("rev-parse", "HEAD", cwd=REPO)
    tree = module.git_sha("rev-parse", "HEAD^{tree}", cwd=REPO)
    assert len(tree) == 40 and tree == live_git("rev-parse", "HEAD^{tree}", cwd=REPO)


def test_runner_git_toplevel_matches_the_repository_root(monkeypatch: pytest.MonkeyPatch) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    assert module.git_toplevel(REPO) == REPO.resolve()


def test_import_records_no_fabricated_suite_tree_from_an_ambient_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing non-repository path must not yield a silent empty engine_tree.

    Module import resolved each suite root's tree with the same check=False helper,
    so a directory that exists but is not a Git checkout produced the string ``""``
    recorded as an engine tree. Resolution is deferred to execution, which validates
    the root, so import records nothing it did not measure.
    """
    module = runner_module(monkeypatch, forge_workspace=tmp_path)
    forge = module.NATIVE_SUITE_BINDING["forge"]
    assert "engine_tree" not in forge, (
        "the import-time tree resolution recorded an unmeasured engine tree: "
        f"{forge.get('engine_tree')!r}. Resolve suite roots at execution time."
    )
