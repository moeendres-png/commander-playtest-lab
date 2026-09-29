from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify_repository_tree.py"
spec = importlib.util.spec_from_file_location("repository_tree_guard", SCRIPT)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            *args,
        ],
        text=True,
    ).strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    for name in guard.REQUIRED_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("raise RuntimeError('candidate code must never execute')\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "fixture")
    return tmp_path


def test_complete_tree_is_read_without_executing_candidate(repository: Path) -> None:
    head = git(repository, "rev-parse", "HEAD")
    assert guard.inspect_tree(repository, head)["valid"]
    assert git(repository, "status", "--porcelain") == ""


@pytest.mark.parametrize("missing", guard.REQUIRED_FILES)
def test_lost_operating_entrypoint_fails(repository: Path, missing: str) -> None:
    git(repository, "rm", "--", missing)
    git(repository, "commit", "-qm", "missing entrypoint")
    result = guard.inspect_tree(repository, git(repository, "rev-parse", "HEAD"))
    assert not result["valid"]
    assert result["errors"] == [f"required regular file missing or replaced: {missing}"]


def test_symlink_blob_is_not_a_required_regular_file(repository: Path) -> None:
    blob = git(repository, "rev-parse", "HEAD:AGENTS.md")
    git(repository, "update-index", "--cacheinfo", f"120000,{blob},AGENTS.md")
    git(repository, "commit", "-qm", "symlink entry")
    assert not guard.inspect_tree(repository, git(repository, "rev-parse", "HEAD"))["valid"]


def test_directory_cannot_replace_required_file(repository: Path) -> None:
    (repository / "AGENTS.md").unlink()
    (repository / "AGENTS.md").mkdir()
    (repository / "AGENTS.md" / "entry").write_text("not a regular root entry")
    git(repository, "add", "-A")
    git(repository, "commit", "-qm", "directory entry")
    assert not guard.inspect_tree(repository, git(repository, "rev-parse", "HEAD"))["valid"]


@pytest.mark.parametrize("ref", ["HEAD", "--help", "0" * 40])
def test_invalid_or_unavailable_commit_fails(repository: Path, ref: str) -> None:
    with pytest.raises(ValueError):
        guard.inspect_tree(repository, ref)


def test_tree_object_is_not_accepted_as_a_commit(repository: Path) -> None:
    with pytest.raises(ValueError):
        guard.inspect_tree(repository, git(repository, "rev-parse", "HEAD^{tree}"))


def test_annotated_tag_is_not_accepted_as_a_commit(repository: Path) -> None:
    git(repository, "tag", "-am", "fixture tag", "candidate")
    with pytest.raises(ValueError):
        guard.inspect_tree(repository, git(repository, "rev-parse", "candidate"))


def test_target_workflow_only_executes_trusted_base() -> None:
    path = SCRIPT.parent.parent / ".github/workflows/repository-tree-integrity.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["repository-tree-integrity"]["steps"]
    checkout = [step for step in steps if "actions/checkout@" in step.get("uses", "")]
    assert len(checkout) == 1
    assert checkout[0]["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert not any("cache" in step.get("with", {}) for step in steps)
    for step in steps:
        assert "${{ github.event.pull_request.head" not in step.get("run", "")
    assert steps[-1]["env"]["CANDIDATE_SHA"] == "${{ github.event.pull_request.head.sha }}"
