"""Tests for the Foundry deterministic helpers (tools/foundry/).

Covers: source-lock success, source mismatch failure, dirty-tree handling,
clustering identity preservation, no fabricated evidence, UNKNOWN
preservation, artifact hashing, state schema validation, and state round-trip
for continuation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools" / "foundry"

sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import cluster_failures, evidence, metrics, worktree_inventory
from foundry import source_lock as lock_mod
from foundry import state as state_mod


def _git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    _git(
        [
            "config",
            "remote.origin.url",
            "https://github.com/moeendres-png/commander-playtest-lab.git",
        ],
        tmp_path,
    )
    (tmp_path / "file.txt").write_text("hello\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)
    return tmp_path


def test_source_lock_success(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    reasons = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert reasons == []


def test_source_lock_branch_mismatch_fails(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    reasons = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="other-branch",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert any("branch mismatch" in r for r in reasons)


def test_source_lock_repo_mismatch_fails(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    reasons = lock_mod.verify(
        repo="someone-else/other-repo",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert any("repository mismatch" in r for r in reasons)


def test_source_lock_wrong_base_fails(repo: Path) -> None:
    reasons = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="main",
        audit_base_sha="0" * 40,
        workdir=str(repo),
    )
    assert any("audit base" in r for r in reasons)


def test_source_lock_dirty_tree_fails_closed(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    (repo / "file.txt").write_text("modified\n", encoding="utf-8")
    reasons = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert any("dirty worktree" in r for r in reasons)
    allowed = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
        allow_dirty=True,
    )
    assert allowed == []


def test_cluster_preserves_record_identity(tmp_path: Path) -> None:
    records = [
        {
            "id": "R1",
            "message": "boom at /a/b.py:12 commit abc1234",
            "evidence": "log1",
            "verdict": "FAIL",
        },
        {
            "id": "R2",
            "message": "boom at /x/y.py:99 commit def5678",
            "evidence": "log2",
            "verdict": "FAIL",
        },
        {"id": "R3", "message": "totally different harness timeout", "evidence": "log3"},
    ]
    clusters = cluster_failures.cluster(records)
    assert len(clusters) == 2
    big = next(c for c in clusters if c["count"] == 2)
    assert {m["id"] for m in big["members"]} == {"R1", "R2"}
    assert all(m["evidence"] in ("log1", "log2") for m in big["members"])


def test_evidence_report_never_fabricates() -> None:
    skeleton = evidence.handoff_skeleton("WS-X", {"sha": "abc"})
    assert skeleton["exact_next_action"] == "UNKNOWN"
    assert skeleton["tests_evidence"] == []
    skeleton2 = evidence.handoff_skeleton(
        "WS-X", {"sha": "abc"}, [{"name": "t", "verdict": "BOGUS"}]
    )
    assert skeleton2["tests_evidence"][0]["verdict"] == "UNKNOWN"


def test_artifact_index_hashes(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("deterministic\n", encoding="utf-8")
    manifest = evidence.artifact_index([str(tmp_path)], run="RUN1", source_sha="S" * 40)
    assert len(manifest["artifacts"]) == 1
    entry = manifest["artifacts"][0]
    assert entry["name"] == "out.txt"
    assert entry["size"] == target.stat().st_size
    assert entry["run"] == "RUN1"
    import hashlib

    assert entry["sha256"] == hashlib.sha256(b"deterministic\n").hexdigest()


def _valid_state() -> dict:
    sha = "a" * 40
    return {
        "schema_version": "1.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": "/tmp/wt",
        "branch": "project/x",
        "audit_base_sha": sha,
        "audit_base_tree": sha,
        "current_head": sha,
        "objective": "do the thing",
        "in_scope": ["a"],
        "out_of_scope": ["b"],
        "ownership": "tester",
        "status": "ACTIVE",
        "exact_next_action": "next",
    }


def test_state_schema_accepts_valid() -> None:
    assert state_mod.validate(_valid_state()) == []


def test_state_schema_rejects_bad_status_and_sha() -> None:
    bad = _valid_state()
    bad["status"] = "DONE"
    bad["current_head"] = "xyz"
    errors = state_mod.validate(bad)
    assert any("status" in e for e in errors)
    assert any("current_head" in e for e in errors)


def test_state_schema_rejects_missing_and_bad_class() -> None:
    bad = _valid_state()
    del bad["objective"]
    bad["failure_class"] = "MAYBE_ENGINE"
    errors = state_mod.validate(bad)
    assert any("objective" in e for e in errors)
    assert any("failure_class" in e for e in errors)


def test_state_round_trip_for_continuation(tmp_path: Path) -> None:
    path = tmp_path / "WORKSTREAM_STATE.yaml"
    path.write_text(yaml.safe_dump(_valid_state()), encoding="utf-8")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert state_mod.validate(data) == []
    assert data["exact_next_action"] == "next"


def test_metrics_record_appends_jsonl_without_invention(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    entry = metrics.record(str(metrics_path), task_id="T1", reasoning_effort="high", completed=True)
    assert "token_usage" not in entry
    assert "tool_calls" not in entry
    lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["task_id"] == "T1"


def test_repo_state_file_validates() -> None:
    state_path = REPO_ROOT / ".foundry" / "WORKSTREAM_STATE.yaml"
    data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    assert state_mod.validate(data) == []


def test_opencode_config_schema_conformance() -> None:
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert config["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert config["share"] == "disabled"
    variants = config["provider"]["opencode-go"]["models"]["muse-spark-1.3-contributor"]["variants"]
    for effort in ("none", "off", "minimal", "low", "medium"):
        assert variants[effort] == {"disabled": True}
    assert set(variants) == {"none", "off", "minimal", "low", "medium", "high", "xhigh"}
    assert "permissions" not in config
    assert isinstance(config["permission"], dict)


def test_inventory_marks_clean_true_and_strips_refs(repo: Path) -> None:
    entries = worktree_inventory.inventory(str(repo))
    assert len(entries) == 1
    entry = entries[0]
    assert entry["clean"] is True
    assert entry["branch"] == "main"
    assert entry["head"] == _git(["rev-parse", "HEAD"], repo)


def test_inventory_marks_dirty_false(repo: Path) -> None:
    (repo / "file.txt").write_text("dirty\n", encoding="utf-8")
    entries = worktree_inventory.inventory(str(repo))
    assert entries[0]["clean"] is False
