"""Tests for state schema 2.0 identity semantics.

Covers: removal of ambiguous current_head, migration without fabricated
validation credit, validated_head ancestry (inside lock / outside lock /
rewritten history), and the honest-null case. Ancestry tests run against real
temporary git repositories.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import state as state_mod  # noqa: E402


def _git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def history(tmp_path: Path) -> Path:
    """Three-commit linear history: base -> validated -> checkpoint."""
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "base"], tmp_path)
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "validated"], tmp_path)
    (tmp_path / "c.txt").write_text("c\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "checkpoint"], tmp_path)
    return tmp_path


def _shas(repo: Path) -> tuple[str, str, str]:
    base = _git(["rev-parse", "HEAD~2"], repo)
    validated = _git(["rev-parse", "HEAD~1"], repo)
    live = _git(["rev-parse", "HEAD"], repo)
    return base, validated, live


def _doc(base: str, live: str, validated: str | None) -> dict:
    return {
        "schema_version": "2.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": "/tmp/wt",
        "branch": "project/x",
        "audit_base_sha": base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": live,
        "validated_head": validated,
        "objective": "x",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "tester",
        "status": "ACTIVE",
        "exact_next_action": "next",
    }


def test_v2_rejects_ambiguous_current_head() -> None:
    doc = _doc("a" * 40, "b" * 40, None)
    doc["current_head"] = "c" * 40
    errors = state_mod.validate(doc)
    assert any("removed in schema 2.0" in e for e in errors)


def test_unknown_version_points_at_migration() -> None:
    doc = _doc("a" * 40, "b" * 40, None)
    doc["schema_version"] = "3.0"
    errors = state_mod.validate(doc)
    assert any("unsupported schema_version" in e for e in errors)
    assert any("migrate" in e for e in errors)


def test_migrate_claims_no_validation_credit() -> None:
    legacy = dict(_doc("a" * 40, "a" * 40, None))
    legacy["schema_version"] = "1.0"
    legacy["current_head"] = legacy.pop("state_written_against_head")
    del legacy["validated_head"]
    out = state_mod.migrate(legacy)
    assert out["validated_head"] is None
    assert state_mod.validate(out) == []


def test_migrate_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="cannot migrate"):
        state_mod.migrate({"schema_version": "9.9"})


def test_ancestry_ok_when_validated_inside_lock(history: Path, tmp_path: Path) -> None:
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    path.write_text(yaml.safe_dump(_doc(base, live, validated)), encoding="utf-8")
    assert state_mod.check_validated_ancestry(str(path), str(history)) == []


def test_ancestry_fails_when_validated_outside_lock(history: Path, tmp_path: Path) -> None:
    _, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    path.write_text(yaml.safe_dump(_doc("f" * 40, live, validated)), encoding="utf-8")
    notes = state_mod.check_validated_ancestry(str(path), str(history))
    assert any("VALIDATED_OUTSIDE_LOCK" in n for n in notes)


def test_ancestry_fails_when_history_rewritten(history: Path, tmp_path: Path) -> None:
    base, validated, _ = _shas(history)
    # Rewrite: drop the validated commit; live no longer descends from it.
    _git(["reset", "--hard", "HEAD~2"], history)
    live = _git(["rev-parse", "HEAD"], history)
    assert live == base
    path = tmp_path / "S.yaml"
    path.write_text(yaml.safe_dump(_doc(base, live, validated)), encoding="utf-8")
    notes = state_mod.check_validated_ancestry(str(path), str(history))
    assert any("VALIDATED_REWRITTEN" in n for n in notes)


def test_null_validated_head_is_honest_note_not_error(history: Path, tmp_path: Path) -> None:
    base, _, live = _shas(history)
    path = tmp_path / "S.yaml"
    doc = _doc(base, live, None)
    assert state_mod.validate(doc) == []
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    notes = state_mod.check_validated_ancestry(str(path), str(history))
    assert notes == ["VALIDATED_NONE: no commit validated beyond the audit base (honest null)"]


def test_migrate_cli_writes_v2(tmp_path: Path) -> None:
    legacy = {
        "schema_version": "1.0",
        "repository": "r",
        "worktree": "w",
        "branch": "b",
        "audit_base_sha": "a" * 40,
        "audit_base_tree": "b" * 40,
        "current_head": "c" * 40,
        "objective": "o",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "t",
        "status": "ACTIVE",
        "exact_next_action": "n",
    }
    path = tmp_path / "S.yaml"
    path.write_text(yaml.safe_dump(legacy), encoding="utf-8")
    rc = state_mod.main(["--state", str(path), "--migrate", "--in-place"])
    assert rc == 0
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0"
    assert data["state_written_against_head"] == "c" * 40
    assert data["validated_head"] is None
    assert state_mod.validate(data) == []


def _repo_with_state(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "code"], repo)
    code_head = _git(["rev-parse", "HEAD"], repo)
    return repo, code_head


def test_state_only_checkpoint_commit_is_clean_not_mismatch(tmp_path: Path) -> None:
    repo, code_head = _repo_with_state(tmp_path)
    state_path = repo / "S.yaml"
    state_path.write_text(yaml.safe_dump(_doc(code_head, code_head, code_head)), encoding="utf-8")
    # Checkpoint commit touches ONLY the state file: the write->commit cycle
    # must terminate instead of demanding another state update.
    _git(["add", "S.yaml"], repo)
    _git(["commit", "-m", "checkpoint state"], repo)
    assert state_mod.check_head_mismatch(str(state_path), str(repo)) == []


def test_checkpoint_commit_with_code_changes_still_mismatches(tmp_path: Path) -> None:
    repo, code_head = _repo_with_state(tmp_path)
    state_path = repo / "S.yaml"
    state_path.write_text(yaml.safe_dump(_doc(code_head, code_head, code_head)), encoding="utf-8")
    (repo / "code.py").write_text("x = 2\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "sneaky code change"], repo)
    warnings = state_mod.check_head_mismatch(str(state_path), str(repo))
    assert any("HEAD_MISMATCH" in w for w in warnings)
