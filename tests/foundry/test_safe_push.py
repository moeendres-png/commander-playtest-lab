"""Adversarial tests for tools/foundry/safe_push.py.

All tests run against real local git repositories (a file:// bare repo as
"origin") and real subprocesses. Pushes that must not happen are verified
absent via ls-remote; the lock-ancestry path is exercised by running safe_push
as a genuine child of a lock-holding parent process.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "foundry" / "safe_push.py"
TOOLS_DIR = ROOT / "tools"

sys.path.insert(0, str(TOOLS_DIR))

from foundry import safe_push as safe_push_mod  # noqa: E402

SLUG = "test-host/fixture-repo"


def _git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False, env=env
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


def _git_env() -> dict:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "T",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": "/nonexistent-fake-home",
        }
    )
    return env


@pytest.fixture()
def rig(tmp_path: Path) -> dict:
    """Bare remote with main + a worktree repo on branch test/ws + valid state."""
    locks = tmp_path / "locks"
    locks.mkdir()
    env = _git_env()
    # Remote path embeds the trust slug so the remote-identity check exercises
    # its accept path on file:// URLs (mismatch path covered separately).
    remote = tmp_path / "test-host" / "fixture-repo" / "remote.git"
    remote.parent.mkdir(parents=True)
    _git(["init", "--bare", "-b", "main", str(remote)], tmp_path, env)
    seed = tmp_path / "seed"
    _git(["clone", str(remote), str(seed)], tmp_path, env)
    (seed / "f.txt").write_text("v1\n", encoding="utf-8")
    _git(["add", "."], seed, env)
    _git(["commit", "-m", "init"], seed, env)
    _git(["push", "origin", "HEAD:refs/heads/main"], seed, env)

    wt = tmp_path / "wt"
    _git(["clone", str(remote), str(wt)], tmp_path, env)
    _git(["checkout", "-b", "test/ws"], wt, env)
    (wt / "work.txt").write_text("work\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "work"], wt, env)
    base = _git(["rev-parse", "origin/main"], wt, env)
    head = _git(["rev-parse", "HEAD"], wt, env)
    assert base != head
    state = {
        "schema_version": "2.0",
        "repository": "test-host/fixture-repo",
        "worktree": str(wt),
        "branch": "test/ws",
        "audit_base_sha": base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": head,
        "validated_head": head,
        "objective": "x",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "TEST-WORKSTREAM",
        "status": "ACTIVE",
        "exact_next_action": "push",
    }
    state_path = wt / "STATE.yaml"
    state_text = yaml.safe_dump(state)
    state_path.write_text(state_text, encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "checkpoint state"], wt, env)
    checkpoint_head = _git(["rev-parse", "HEAD"], wt, env)
    rig_out = {
        "wt": wt,
        "remote": remote,
        "locks": locks,
        "state": state_path,
        "state_text": state_text,
        "env": env,
        "base": base,
        "head": head,
        "code_head": head,
        "checkpoint_head": checkpoint_head,
    }
    return rig_out


def _run_push(
    rig: dict, *extra: str, via_holder: bool = True, env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(TOOL),
        "--worktree",
        str(rig["wt"]),
        "--expected-branch",
        "test/ws",
        "--state",
        str(rig["state"]),
        "--expected-slug",
        SLUG,
        *extra,
    ]
    env = dict(rig["env"])
    env["FOUNDRY_LOCK_DIR"] = str(rig["locks"])
    env["PYTHONPATH"] = str(TOOLS_DIR)
    if env_extra:
        env.update(env_extra)
    if not via_holder:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    driver = (
        "import subprocess, sys; "
        "from foundry import writer_lock; "
        "lock = writer_lock.WriterLock(sys.argv[1], 'TEST-WORKSTREAM', 'test/ws', 'ses-t'); "
        "lock.acquire(); "
        "p = subprocess.run(sys.argv[2:], capture_output=True, text=True); "
        "sys.stdout.write(p.stdout); sys.stderr.write(p.stderr); "
        "lock.release(); "
        "sys.exit(p.returncode)"
    )
    return subprocess.run(
        [sys.executable, "-c", driver, str(rig["wt"]), *cmd],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def _remote_sha(rig: dict, ref: str) -> str | None:
    out = _git(["ls-remote", str(rig["remote"]), ref], rig["wt"], rig["env"])
    return out.split()[0] if out else None


def _rewrite_state(rig: dict, **overrides: object) -> None:
    data = yaml.safe_load(rig["state"].read_text(encoding="utf-8"))
    data.update(overrides)
    rig["state"].write_text(yaml.safe_dump(data), encoding="utf-8")


def test_push_main_refused(rig: dict) -> None:
    proc = _run_push(rig, "--expected-branch", "main")
    # main is refused at the branch gate even though the file remote is fine.
    assert proc.returncode == 2
    assert "PUSH_REJECT" in proc.stderr
    assert _remote_sha(rig, "refs/heads/main") is not None  # seed main untouched


def test_missing_lock_rejected(rig: dict) -> None:
    proc = _run_push(rig, via_holder=False)
    assert proc.returncode == 2
    assert "writer lock" in proc.stderr
    assert _remote_sha(rig, "refs/heads/test/ws") is None


def test_lock_held_by_non_ancestor_rejected(rig: dict) -> None:
    env = dict(rig["env"])
    env["FOUNDRY_LOCK_DIR"] = str(rig["locks"])
    env["PYTHONPATH"] = str(TOOLS_DIR)
    holder = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "tools" / "foundry" / "writer_lock.py"),
            "acquire",
            "--worktree",
            str(rig["wt"]),
            "--workstream",
            "TEST-WORKSTREAM",
            "--branch",
            "test/ws",
            "--hold",
        ],
        env=env,
        cwd=str(rig["wt"]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert holder.stdout is not None
    while "WRITER_OK" not in (holder.stdout.readline() or ""):
        pass
    try:
        proc = _run_push(rig, via_holder=False)  # sibling process, not a child
        assert proc.returncode == 2
        assert "not an ancestor" in proc.stderr
        assert _remote_sha(rig, "refs/heads/test/ws") is None
    finally:
        holder.terminate()
        holder.wait(timeout=10)


def test_branch_mismatch_rejected(rig: dict) -> None:
    _git(["checkout", "-b", "test/other"], rig["wt"], rig["env"])
    proc = _run_push(rig)
    assert proc.returncode == 2
    assert "branch mismatch" in proc.stderr


def test_detached_head_rejected(rig: dict) -> None:
    _git(["checkout", "--detach", "HEAD"], rig["wt"], rig["env"])
    proc = _run_push(rig)
    assert proc.returncode == 2
    assert "detached HEAD" in proc.stderr


def test_dirty_tree_rejected(rig: dict) -> None:
    (rig["wt"] / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
    proc = _run_push(rig)
    assert proc.returncode == 2
    assert "dirty worktree" in proc.stderr
    assert _remote_sha(rig, "refs/heads/test/ws") is None


def test_forged_state_branch_rejected(rig: dict) -> None:
    _rewrite_state(rig, branch="test/forged")
    proc = _run_push(rig)
    assert proc.returncode == 2
    assert "branch mismatch" in proc.stderr


def test_wrong_remote_slug_rejected(rig: dict) -> None:
    proc = _run_push(rig, "--expected-slug", "someone-else/other-repo")
    assert proc.returncode == 2
    assert "WRONG_REMOTE" in proc.stderr


def test_injection_branch_names_rejected(rig: dict) -> None:
    for evil in ("x --force", "HEAD:refs/heads/other", "-u", "a:b", "a..b", "a b"):
        rc = safe_push_mod._valid_branch_name(evil, str(rig["wt"]))
        assert rc is not None, evil


def test_non_fast_forward_rejected_and_remote_untouched(rig: dict) -> None:
    assert _run_push(rig).returncode == 0
    pushed = _remote_sha(rig, "refs/heads/test/ws")
    assert pushed == rig["checkpoint_head"]
    # Rival clone advances the remote branch outside our history.
    rival = rig["wt"].parent / "rival"
    _git(["clone", str(rig["remote"]), str(rival)], rig["wt"].parent, rig["env"])
    _git(["checkout", "test/ws"], rival, rig["env"])
    (rival / "rival.txt").write_text("rival\n", encoding="utf-8")
    _git(["add", "."], rival, rig["env"])
    _git(["commit", "-m", "rival"], rival, rig["env"])
    _git(["push", "origin", "HEAD:refs/heads/test/ws"], rival, rig["env"])
    rival_sha = _remote_sha(rig, "refs/heads/test/ws")
    assert rival_sha != pushed
    proc = _run_push(rig)
    assert proc.returncode == 2
    assert "non-fast-forward" in proc.stderr
    assert _remote_sha(rig, "refs/heads/test/ws") == rival_sha


def test_success_creation_then_up_to_date(rig: dict) -> None:
    assert _remote_sha(rig, "refs/heads/test/ws") is None
    first = _run_push(rig)
    assert first.returncode == 0, first.stderr
    assert "PUSHED" in first.stdout
    # Push writes live HEAD (the checkpoint commit); validated_head names the
    # tested code commit it descends from.
    assert _remote_sha(rig, "refs/heads/test/ws") == rig["checkpoint_head"]
    second = _run_push(rig)
    assert second.returncode == 0
    assert "UP_TO_DATE" in second.stdout


def test_dry_run_checks_without_writing(rig: dict) -> None:
    proc = _run_push(rig, "--dry-run")
    assert proc.returncode == 0
    assert "DRY_RUN_OK" in proc.stdout
    assert _remote_sha(rig, "refs/heads/test/ws") is None


def test_no_credential_or_secret_output(rig: dict) -> None:
    redacted = safe_push_mod._redact_url("https://user:s3cret@github.com/o/r.git")
    assert "s3cret" not in redacted and "user" not in redacted
    assert "github.com/o/r.git" in redacted
    proc = _run_push(rig, "--dry-run", env_extra={"FOUNDRY_SENTINEL_TOKEN": "sentinel-abc-123"})
    assert proc.returncode == 0
    assert "sentinel-abc-123" not in (proc.stdout + proc.stderr)


def test_null_validated_head_rejected(rig: dict) -> None:
    _rewrite_state(rig, validated_head=None)
    proc = _run_push(rig)
    assert proc.returncode == 2
    assert "validated_head is null" in proc.stderr


def test_rewritten_history_rejected(rig: dict) -> None:
    _git(["reset", "--hard", "HEAD~1"], rig["wt"], rig["env"])
    # Strand validated_head on the dropped checkpoint commit, then restore the
    # document: validated is no longer an ancestor of live HEAD. (Ancestry is
    # checked before the dirty-tree gate, so the untracked-but-restored state
    # file does not mask the verdict.)
    data = yaml.safe_load(rig["state_text"])
    data["validated_head"] = rig["checkpoint_head"]
    rig["state"].write_text(yaml.safe_dump(data), encoding="utf-8")
    proc = _run_push(rig)
    assert proc.returncode == 2
    assert "VALIDATED_REWRITTEN" in proc.stderr


if __name__ == "__main__":
    import pytest as _pytest

    raise SystemExit(_pytest.main([__file__, "-q"]))


# ---------------------------------------------------------------------------
# WS57: explicit remote-source-lineage creation (--expected-audit-base-ref).
# ---------------------------------------------------------------------------

LINEAGE_BRANCH = "target/ws"
LINEAGE_SOURCE = "source/lineage"
LINEAGE_UNRELATED = "unrelated/line"
LINEAGE_OWNER = "TEST-WS"


@pytest.fixture()
def lineage_rig(tmp_path: Path) -> dict:
    """Remote main at A plus a diverged source branch at B (WS54 shape).

    main advances past the fork point so B is NOT in main ancestry; the local
    target/ws branch descends from B with audit_base_sha=B and the target
    remote branch absent.
    """
    locks = tmp_path / "locks"
    locks.mkdir()
    env = _git_env()
    remote = tmp_path / "test-host" / "fixture-repo" / "remote.git"
    remote.parent.mkdir(parents=True)
    _git(["init", "--bare", "-b", "main", str(remote)], tmp_path, env)
    seed = tmp_path / "seed"
    _git(["clone", str(remote), str(seed)], tmp_path, env)
    (seed / "f.txt").write_text("v1\n", encoding="utf-8")
    _git(["add", "."], seed, env)
    _git(["commit", "-m", "init"], seed, env)
    _git(["push", "origin", "HEAD:refs/heads/main"], seed, env)
    _git(["checkout", "-b", LINEAGE_SOURCE], seed, env)
    (seed / "s.txt").write_text("lineage\n", encoding="utf-8")
    _git(["add", "."], seed, env)
    _git(["commit", "-m", "lineage B"], seed, env)
    _git(["push", "origin", f"HEAD:refs/heads/{LINEAGE_SOURCE}"], seed, env)
    audit_base = _git(["rev-parse", "HEAD"], seed, env)
    # Advance main elsewhere so the lineage is outside main ancestry.
    _git(["checkout", "main"], seed, env)
    (seed / "m.txt").write_text("main2\n", encoding="utf-8")
    _git(["add", "."], seed, env)
    _git(["commit", "-m", "main advance"], seed, env)
    _git(["push", "origin", "HEAD:refs/heads/main"], seed, env)
    # Unrelated branch at the main tip (never contains the audit base).
    _git(["checkout", "-b", LINEAGE_UNRELATED], seed, env)
    _git(["push", "origin", f"HEAD:refs/heads/{LINEAGE_UNRELATED}"], seed, env)

    wt = tmp_path / "wt"
    _git(["clone", str(remote), str(wt)], tmp_path, env)
    _git(["checkout", "-b", LINEAGE_BRANCH, f"origin/{LINEAGE_SOURCE}"], wt, env)
    (wt / "work.txt").write_text("work\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "work"], wt, env)
    head = _git(["rev-parse", "HEAD"], wt, env)
    state = {
        "schema_version": "2.0",
        "repository": "test-host/fixture-repo",
        "worktree": str(wt),
        "branch": LINEAGE_BRANCH,
        "audit_base_sha": audit_base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": head,
        "validated_head": head,
        "objective": "x",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": LINEAGE_OWNER,
        "status": "ACTIVE",
        "exact_next_action": "push",
    }
    state_path = wt / "STATE.yaml"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "checkpoint state"], wt, env)
    checkpoint_head = _git(["rev-parse", "HEAD"], wt, env)
    # Reproduce the WS54 shape: audit base outside main ancestry.
    diverged = subprocess.run(
        ["git", "merge-base", "--is-ancestor", audit_base, "origin/main"],
        cwd=wt,
        capture_output=True,
        check=False,
        env=env,
    )
    assert diverged.returncode != 0, "rig must place B outside main ancestry"
    return {
        "wt": wt,
        "seed": seed,
        "remote": remote,
        "locks": locks,
        "state": state_path,
        "env": env,
        "audit_base": audit_base,
        "checkpoint_head": checkpoint_head,
    }


def _run_lineage_push(
    rig: dict, *extra: str, via_holder: bool = True, env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(TOOL),
        "--worktree",
        str(rig["wt"]),
        "--expected-branch",
        LINEAGE_BRANCH,
        "--state",
        str(rig["state"]),
        "--expected-slug",
        SLUG,
        *extra,
    ]
    env = dict(rig["env"])
    env["FOUNDRY_LOCK_DIR"] = str(rig["locks"])
    env["PYTHONPATH"] = str(TOOLS_DIR)
    if env_extra:
        env.update(env_extra)
    if not via_holder:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    driver = (
        "import subprocess, sys; "
        "from foundry import writer_lock; "
        f"lock = writer_lock.WriterLock(sys.argv[1], {LINEAGE_OWNER!r}, "
        f"{LINEAGE_BRANCH!r}, 'ses-t'); "
        "lock.acquire(); "
        "p = subprocess.run(sys.argv[2:], capture_output=True, text=True); "
        "sys.stdout.write(p.stdout); sys.stderr.write(p.stderr); "
        "lock.release(); "
        "sys.exit(p.returncode)"
    )
    return subprocess.run(
        [sys.executable, "-c", driver, str(rig["wt"]), *cmd],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def test_lineage_creation_dry_run_with_source_ref(lineage_rig: dict) -> None:
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None
    proc = _run_lineage_push(lineage_rig, "--dry-run", "--expected-audit-base-ref", LINEAGE_SOURCE)
    assert proc.returncode == 0, proc.stderr
    assert "DRY_RUN_OK" in proc.stdout
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_creation_pushes_with_source_ref(lineage_rig: dict) -> None:
    proc = _run_lineage_push(lineage_rig, "--expected-audit-base-ref", LINEAGE_SOURCE)
    assert proc.returncode == 0, proc.stderr
    assert "PUSHED" in proc.stdout
    assert (
        _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") == lineage_rig["checkpoint_head"]
    )
    second = _run_lineage_push(lineage_rig, "--expected-audit-base-ref", LINEAGE_SOURCE)
    assert second.returncode == 0
    assert "UP_TO_DATE" in second.stdout


def test_lineage_creation_allows_advanced_source_tip(lineage_rig: dict) -> None:
    # The source branch advances past the audit base; creation stays permitted
    # while the audit base remains an ancestor of the source tip.
    seed = lineage_rig["seed"]
    env = lineage_rig["env"]
    _git(["checkout", LINEAGE_SOURCE], seed, env)
    (seed / "s2.txt").write_text("lineage-advance\n", encoding="utf-8")
    _git(["add", "."], seed, env)
    _git(["commit", "-m", "lineage advance"], seed, env)
    _git(["push", "origin", f"HEAD:refs/heads/{LINEAGE_SOURCE}"], seed, env)
    _git(["fetch", "origin", LINEAGE_SOURCE], lineage_rig["wt"], env)
    proc = _run_lineage_push(lineage_rig, "--dry-run", "--expected-audit-base-ref", LINEAGE_SOURCE)
    assert proc.returncode == 0, proc.stderr
    assert "DRY_RUN_OK" in proc.stdout
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_creation_rejected_without_source_ref(lineage_rig: dict) -> None:
    proc = _run_lineage_push(lineage_rig, "--dry-run")
    assert proc.returncode == 2
    assert "audit base is outside the remote history" in proc.stderr
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_absent_source_ref_rejected(lineage_rig: dict) -> None:
    proc = _run_lineage_push(
        lineage_rig, "--dry-run", "--expected-audit-base-ref", "source/missing"
    )
    assert proc.returncode == 2
    assert "absent on remote" in proc.stderr
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_unrelated_source_ref_rejected(lineage_rig: dict) -> None:
    for ref in (LINEAGE_UNRELATED, "main"):
        proc = _run_lineage_push(lineage_rig, "--dry-run", "--expected-audit-base-ref", ref)
        assert proc.returncode == 2, ref
        assert "does not contain the audit base" in proc.stderr, ref
        assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_malformed_source_refs_rejected(lineage_rig: dict) -> None:
    evil = [
        "x --force",
        "HEAD:refs/heads/other",
        "-u",
        "a:b",
        "a..b",
        "a b",
        "refs/heads/source/lineage",
        "HEAD",
        "source/*",
        "a@{1}",
        LINEAGE_BRANCH,  # must not equal the push target
        "0" * 40,  # SHA-like pseudo-ref
    ]
    for name in evil:
        reason = safe_push_mod._valid_source_ref_name(name, LINEAGE_BRANCH, str(lineage_rig["wt"]))
        assert reason is not None, name
    # End-to-end: a representative subset must reject before any remote write.
    for name in ("x --force", "a:b", "refs/heads/source/lineage", "0" * 40, LINEAGE_BRANCH):
        proc = _run_lineage_push(lineage_rig, "--dry-run", "--expected-audit-base-ref", name)
        assert proc.returncode == 2, name
        assert "PUSH_REJECT" in proc.stderr, name
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_source_ref_allows_protected_names_as_identity(
    lineage_rig: dict,
) -> None:
    # Protected-branch semantics govern push destinations, not source identity
    # evidence: "main" passes source-ref format validation (ancestry still
    # decides, and rejects it here because the lineage diverged from main).
    assert (
        safe_push_mod._valid_source_ref_name("main", LINEAGE_BRANCH, str(lineage_rig["wt"])) is None
    )
    assert safe_push_mod._valid_branch_name("main", str(lineage_rig["wt"])) is not None


def test_lineage_wrong_remote_rejected(lineage_rig: dict) -> None:
    proc = _run_lineage_push(
        lineage_rig,
        "--dry-run",
        "--expected-audit-base-ref",
        LINEAGE_SOURCE,
        "--expected-slug",
        "someone-else/other-repo",
    )
    assert proc.returncode == 2
    assert "WRONG_REMOTE" in proc.stderr
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_dirty_tree_rejected(lineage_rig: dict) -> None:
    (lineage_rig["wt"] / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
    proc = _run_lineage_push(lineage_rig, "--dry-run", "--expected-audit-base-ref", LINEAGE_SOURCE)
    assert proc.returncode == 2
    assert "dirty worktree" in proc.stderr
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_missing_lock_rejected(lineage_rig: dict) -> None:
    proc = _run_lineage_push(
        lineage_rig,
        "--dry-run",
        "--expected-audit-base-ref",
        LINEAGE_SOURCE,
        via_holder=False,
    )
    assert proc.returncode == 2
    assert "writer lock" in proc.stderr
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_sibling_lock_rejected(lineage_rig: dict) -> None:
    env = dict(lineage_rig["env"])
    env["FOUNDRY_LOCK_DIR"] = str(lineage_rig["locks"])
    env["PYTHONPATH"] = str(TOOLS_DIR)
    holder = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "tools" / "foundry" / "writer_lock.py"),
            "acquire",
            "--worktree",
            str(lineage_rig["wt"]),
            "--workstream",
            LINEAGE_OWNER,
            "--branch",
            LINEAGE_BRANCH,
            "--hold",
        ],
        env=env,
        cwd=str(lineage_rig["wt"]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert holder.stdout is not None
    while "WRITER_OK" not in (holder.stdout.readline() or ""):
        pass
    try:
        proc = _run_lineage_push(
            lineage_rig,
            "--dry-run",
            "--expected-audit-base-ref",
            LINEAGE_SOURCE,
            via_holder=False,
        )
        assert proc.returncode == 2
        assert "not an ancestor" in proc.stderr
        assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None
    finally:
        holder.terminate()
        holder.wait(timeout=10)


def test_lineage_null_validated_head_rejected(lineage_rig: dict) -> None:
    _rewrite_state(lineage_rig, validated_head=None)
    proc = _run_lineage_push(lineage_rig, "--dry-run", "--expected-audit-base-ref", LINEAGE_SOURCE)
    assert proc.returncode == 2
    assert "validated_head is null" in proc.stderr
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_audit_base_outside_head_rejected(lineage_rig: dict) -> None:
    main_tip = _remote_sha(lineage_rig, "refs/heads/main")
    assert main_tip is not None
    _rewrite_state(lineage_rig, audit_base_sha=main_tip)
    proc = _run_lineage_push(lineage_rig, "--dry-run", "--expected-audit-base-ref", LINEAGE_SOURCE)
    # A foreign audit base breaks validation credit (gate 7) before the
    # source-lock ancestry gate (gate 9) is reached; either way no write.
    assert proc.returncode == 2
    assert "VALIDATED_OUTSIDE_LOCK" in proc.stderr
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") is None


def test_lineage_non_fast_forward_rejected(lineage_rig: dict) -> None:
    first = _run_lineage_push(lineage_rig, "--expected-audit-base-ref", LINEAGE_SOURCE)
    assert first.returncode == 0, first.stderr
    pushed = _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}")
    assert pushed == lineage_rig["checkpoint_head"]
    rival = lineage_rig["wt"].parent / "rival"
    _git(
        ["clone", str(lineage_rig["remote"]), str(rival)],
        lineage_rig["wt"].parent,
        lineage_rig["env"],
    )
    _git(["checkout", LINEAGE_BRANCH], rival, lineage_rig["env"])
    (rival / "rival.txt").write_text("rival\n", encoding="utf-8")
    _git(["add", "."], rival, lineage_rig["env"])
    _git(["commit", "-m", "rival"], rival, lineage_rig["env"])
    _git(["push", "origin", f"HEAD:refs/heads/{LINEAGE_BRANCH}"], rival, lineage_rig["env"])
    rival_sha = _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}")
    assert rival_sha != pushed
    proc = _run_lineage_push(lineage_rig, "--expected-audit-base-ref", LINEAGE_SOURCE)
    assert proc.returncode == 2
    assert "non-fast-forward" in proc.stderr
    assert _remote_sha(lineage_rig, f"refs/heads/{LINEAGE_BRANCH}") == rival_sha
