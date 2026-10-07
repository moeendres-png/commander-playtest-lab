"""Wrong-reason controls for remote milestone-checkpoint verification.

Policy: a remote checkpoint is durable only when the live remote HEAD equals the
recorded checkpoint (or descends through a generated-state-only closeout).
Pushed WIP is never qualification PASS, and a remote mismatch blocks remote
resumability.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import remote_checkpoint as remote_mod  # noqa: E402
from foundry import state as state_mod  # noqa: E402


def _git(args: list[str], cwd: Path) -> str:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "T",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> dict:
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-b", "main"], root)
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "base"], root)
    base = _git(["rev-parse", "HEAD"], root)
    (root / "tools").mkdir()
    (root / "tools" / "impl.py").write_text("x = 1\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "impl"], root)
    impl = _git(["rev-parse", "HEAD"], root)
    (root / ".foundry").mkdir()
    (root / ".foundry" / "WORKSTREAM_STATE.yaml").write_text("schema_version: '2.0'\n")
    _git(["add", "."], root)
    _git(["commit", "-m", "checkpoint"], root)
    state_commit = _git(["rev-parse", "HEAD"], root)
    (root / ".foundry" / "reviews").mkdir()
    (root / ".foundry" / "reviews" / "r.json").write_text("{}\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "review receipt"], root)
    state_only_next = _git(["rev-parse", "HEAD"], root)
    (root / "tools" / "impl.py").write_text("x = 2\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "material change"], root)
    material_next = _git(["rev-parse", "HEAD"], root)
    return {
        "root": root,
        "base": base,
        "impl": impl,
        "state_commit": state_commit,
        "state_only_next": state_only_next,
        "material_next": material_next,
    }


def _tree(root: Path, commit: str) -> str:
    return _git(["rev-parse", f"{commit}^{{tree}}"], root)


def _doc(repo: dict, *, sha: str | None = None, tree: str | None = None, **over) -> dict:
    doc = {
        "schema_version": "2.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": str(repo["root"]),
        "branch": "project/test",
        "audit_base_sha": repo["base"],
        "audit_base_tree": _tree(repo["root"], repo["base"]),
        "state_written_against_head": repo["state_commit"],
        "validated_head": repo["impl"],
        "validated_tree": _tree(repo["root"], repo["impl"]),
        "objective": "remote checkpoint fixture",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "TEST-WS",
        "status": "ACTIVE",
        "materiality": "MATERIAL",
        "cross_executor_review": {"required": True, "verdict": "UNKNOWN", "reviewed_sha": None},
        "remote_checkpoint": {
            "remote": "origin",
            "branch": "project/test",
            "sha": sha or repo["state_commit"],
            "tree": tree or _tree(repo["root"], repo["state_commit"]),
        },
        "exact_next_action": "go",
    }
    doc.update(over)
    return doc


def _head(sha: str | None):
    def fn(remote: str, branch: str, workdir: str) -> str | None:
        return sha

    return fn


def test_exact_remote_head_equality_is_satisfied(repo: dict) -> None:
    doc = _doc(repo)
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(repo["state_commit"])
    )
    assert result.status == remote_mod.SATISFIED
    assert result.ok


def test_exact_remote_head_without_local_recorded_object_is_unverifiable(repo: dict) -> None:
    missing = "a" * 40
    doc = _doc(repo, sha=missing, tree="b" * 40)
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(missing)
    )
    assert result.status == remote_mod.UNVERIFIABLE
    assert not result.ok
    assert any("TREE identity cannot be verified" in reason for reason in result.reasons)


def test_recorded_tree_mismatch_is_refused(repo: dict) -> None:
    doc = _doc(repo, tree="f" * 40)
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(repo["state_commit"])
    )
    assert result.status == remote_mod.MISMATCH
    assert any("TREE_MISMATCH" in reason for reason in result.reasons)


def test_remote_mismatch_blocks_resumability(repo: dict) -> None:
    doc = _doc(repo, sha=repo["state_commit"], tree=_tree(repo["root"], repo["state_commit"]))
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(repo["material_next"])
    )
    assert result.status == remote_mod.MISMATCH
    assert remote_mod.resumability_status(doc, result) == "NO_REMOTE_RESUMABILITY"


def test_generated_state_only_closeout_descendant_is_satisfied(repo: dict) -> None:
    doc = _doc(repo)
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(repo["state_only_next"])
    )
    assert result.status == remote_mod.SATISFIED, result.reasons


def test_material_descendant_is_a_mismatch(repo: dict) -> None:
    doc = _doc(repo)
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(repo["material_next"])
    )
    assert result.status == remote_mod.MISMATCH


def test_absent_remote_branch_is_a_mismatch(repo: dict) -> None:
    doc = _doc(repo)
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(None)
    )
    assert result.status == remote_mod.MISMATCH


def test_moved_remote_without_local_recorded_object_is_unverifiable(repo: dict) -> None:
    doc = _doc(repo, sha="a" * 40, tree=_tree(repo["root"], repo["state_commit"]))
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(repo["material_next"])
    )
    assert result.status == remote_mod.UNVERIFIABLE


def test_missing_checkpoint_on_policy_state_is_missing(repo: dict) -> None:
    doc = _doc(repo)
    doc.pop("remote_checkpoint")
    result = remote_mod.verify_remote_checkpoint(doc, workdir=str(repo["root"]))
    assert result.status == remote_mod.MISSING
    assert not result.ok


def test_historical_state_without_policy_fields_is_exempt(repo: dict) -> None:
    doc = _doc(repo)
    doc.pop("remote_checkpoint")
    doc.pop("materiality")
    doc.pop("cross_executor_review")
    result = remote_mod.verify_remote_checkpoint(doc, workdir=str(repo["root"]))
    assert result.status == remote_mod.EXEMPT_HISTORICAL


def test_pushed_wip_never_becomes_qualification_pass(repo: dict) -> None:
    doc = _doc(repo, validated_head=None, validated_tree=None)
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(repo["state_commit"])
    )
    assert result.status == remote_mod.SATISFIED
    assert remote_mod.resumability_status(doc, result) == remote_mod.PUSHED_WIP


def test_validated_remote_resumable_status(repo: dict) -> None:
    doc = _doc(repo)
    result = remote_mod.verify_remote_checkpoint(
        doc, workdir=str(repo["root"]), remote_head_fn=_head(repo["state_commit"])
    )
    assert remote_mod.resumability_status(doc, result) == remote_mod.REMOTE_RESUMABLE


def test_state_cli_remote_mismatch_fails_closed_on_a_real_local_remote(tmp_path: Path) -> None:
    bare = tmp_path / "bare.git"
    _git(["init", "--bare", "-b", "main", str(bare)], tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "base"], repo)
    base = _git(["rev-parse", "HEAD"], repo)
    _git(["remote", "add", "origin", str(bare)], repo)
    _git(["push", "origin", "main"], repo)
    _git(["checkout", "-b", "project/test"], repo)
    (repo / "tools").mkdir()
    (repo / "tools" / "impl.py").write_text("x = 1\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "impl"], repo)
    impl = _git(["rev-parse", "HEAD"], repo)
    _git(["push", "origin", "project/test"], repo)
    remote_sha = _git(["rev-parse", "HEAD"], repo)
    _git(["checkout", "--detach", base], repo)

    def doc_for(sha: str) -> dict:
        return {
            "schema_version": "2.0",
            "repository": "moeendres-png/commander-playtest-lab",
            "worktree": str(repo),
            "branch": "project/test",
            "audit_base_sha": base,
            "audit_base_tree": _git(["rev-parse", f"{base}^{{tree}}"], repo),
            "state_written_against_head": base,
            "validated_head": impl,
            "validated_tree": _git(["rev-parse", f"{impl}^{{tree}}"], repo),
            "objective": "cli remote fixture",
            "in_scope": [],
            "out_of_scope": [],
            "ownership": "TEST-WS",
            "status": "ACTIVE",
            "materiality": "MATERIAL",
            "cross_executor_review": {"required": True, "verdict": "UNKNOWN"},
            "remote_checkpoint": {
                "remote": "origin",
                "branch": "project/test",
                "sha": sha,
                "tree": _git(["rev-parse", f"{sha}^{{tree}}"], repo)
                if sha == remote_sha
                else "0" * 40,
            },
            "exact_next_action": "go",
        }

    state_path = repo / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump(doc_for(remote_sha)), encoding="utf-8")
    assert (
        state_mod.main(
            [
                "--state",
                str(state_path),
                "--workdir",
                str(repo),
                "--check-remote-checkpoint",
                "--fail-on-remote-checkpoint",
            ]
        )
        == 0
    )
    state_path.write_text(yaml.safe_dump(doc_for(base)), encoding="utf-8")
    assert (
        state_mod.main(
            [
                "--state",
                str(state_path),
                "--workdir",
                str(repo),
                "--check-remote-checkpoint",
                "--fail-on-remote-checkpoint",
            ]
        )
        == 1
    )
