"""Tests for tools/foundry/bootstrap.py and tools/foundry/launcher.py.

Hermetic fixtures (fake canonical root + fake repos) plus real subprocesses,
real flock locks, and real file-remotes. The launch test execs a stub binary
through FOUNDRY_OPENCODE_BIN and proves lock-hold-across-exec by having the
child attempt a second acquire.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS = ROOT / "tools" / "foundry"

sys.path.insert(0, str(ROOT / "tools"))

from foundry import bootstrap as bootstrap_mod  # noqa: E402
from foundry import launcher as launcher_mod  # noqa: E402

CPL_SLUG = "moeendres-png/commander-playtest-lab"


def _git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False, env=env
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


def _env() -> dict:
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
    return env


@pytest.fixture()
def canon(tmp_path: Path) -> Path:
    """Minimal canonical root carrying the real model/provider/effort lock."""
    root = tmp_path / "canon"
    (root / ".opencode" / "agents").mkdir(parents=True)
    (root / ".opencode" / "skills").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    (root / ".opencode" / "agents" / "foundry-implementer.md").write_text(
        "---\nvariant: high\n---\n", encoding="utf-8"
    )
    (root / ".opencode" / "skills" / "demo").mkdir()
    (root / ".opencode" / "skills" / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    real = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    (root / "opencode.json").write_text(
        json.dumps(
            {
                "model": real["model"],
                "share": real["share"],
                "enabled_providers": real["enabled_providers"],
                "provider": real["provider"],
                "permission": real["permission"],
            }
        ),
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def target(tmp_path: Path) -> dict:
    """CPL-claimed worktree repo on branch project/test with a valid 2.0 state."""
    locks = tmp_path / "locks"
    locks.mkdir()
    wt = tmp_path / "wt"
    wt.mkdir()
    env = _env()
    _git(["init", "-b", "main"], wt, env)
    _git(["config", "remote.origin.url", f"https://github.com/{CPL_SLUG}.git"], wt, env)
    (wt / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    (wt / "code.txt").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "init"], wt, env)
    base = _git(["rev-parse", "HEAD"], wt, env)
    _git(["checkout", "-b", "project/test"], wt, env)
    state = {
        "schema_version": "2.0",
        "repository": CPL_SLUG,
        "worktree": str(wt),
        "branch": "project/test",
        "audit_base_sha": base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": base,
        "validated_head": base,
        "objective": "test objective",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "TEST-WS",
        "status": "ACTIVE",
        "exact_next_action": "go",
    }
    state_path = wt / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    return {"wt": wt, "locks": locks, "env": env, "state": state_path, "base": base}


def _lock_env(target: dict) -> dict:
    env = dict(target["env"])
    env["FOUNDRY_LOCK_DIR"] = str(target["locks"])
    env["PYTHONPATH"] = str(ROOT / "tools")
    return env


# --- bootstrap gate ---------------------------------------------------------


def test_bootstrap_pass(target: dict, canon: Path) -> None:
    result = bootstrap_mod.bootstrap(
        str(target["wt"]),
        "TEST-WS",
        "project/test",
        target["base"],
        str(target["state"]),
        "cpl",
        str(ROOT / ".foundry" / "repo-profiles"),
        str(canon),
    )
    assert result["verdict"] == "BOOTSTRAP_PASS", result


def test_bootstrap_state_branch_mismatch(target: dict, canon: Path) -> None:
    result = bootstrap_mod.bootstrap(
        str(target["wt"]),
        "TEST-WS",
        "project/other",
        target["base"],
        str(target["state"]),
        "cpl",
        str(ROOT / ".foundry" / "repo-profiles"),
        str(canon),
    )
    assert result["verdict"] == "BOOTSTRAP_FAIL"
    assert any("branch" in f for f in result["failures"])


def test_bootstrap_init_state_creates_minimal(target: dict) -> None:
    target["state"].unlink()
    rc = bootstrap_mod.main(
        [
            "--worktree",
            str(target["wt"]),
            "--workstream",
            "TEST-WS",
            "--branch",
            "project/test",
            "--audit-base-sha",
            target["base"],
            "--profile",
            "cpl",
            "--profiles-dir",
            str(ROOT / ".foundry" / "repo-profiles"),
            "--init-state",
        ]
    )
    assert rc == 0
    data = yaml.safe_load(target["state"].read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0"
    assert data["validated_head"] is None


def test_bootstrap_same_cwd_opencode_fails_closed(target: dict, canon: Path) -> None:
    occupant = subprocess.Popen(
        ["opencode", "-c", "import time; time.sleep(30)"],
        executable=sys.executable,
        cwd=str(target["wt"]),
    )
    try:
        result = bootstrap_mod.bootstrap(
            str(target["wt"]),
            "TEST-WS",
            "project/test",
            target["base"],
            str(target["state"]),
            "cpl",
            str(ROOT / ".foundry" / "repo-profiles"),
            str(canon),
        )
        assert result["verdict"] == "BOOTSTRAP_FAIL"
        assert any("same-CWD" in f for f in result["failures"])
        allowed = bootstrap_mod.bootstrap(
            str(target["wt"]),
            "TEST-WS",
            "project/test",
            target["base"],
            str(target["state"]),
            "cpl",
            str(ROOT / ".foundry" / "repo-profiles"),
            str(canon),
            allow_same_cwd_pids=True,
        )
        assert allowed["verdict"] == "BOOTSTRAP_PASS", allowed
    finally:
        occupant.kill()
        occupant.wait()


def test_bootstrap_held_lock_fails(
    target: dict, canon: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    env = _lock_env(target)
    holder = subprocess.Popen(
        [
            sys.executable,
            str(TOOLS / "writer_lock.py"),
            "acquire",
            "--worktree",
            str(target["wt"]),
            "--workstream",
            "OTHER-WS",
            "--branch",
            "project/test",
            "--hold",
        ],
        env=env,
        cwd=str(target["wt"]),
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    while "WRITER_OK" not in (holder.stdout.readline() or ""):
        pass
    try:
        result = bootstrap_mod.bootstrap(
            str(target["wt"]),
            "TEST-WS",
            "project/test",
            target["base"],
            str(target["state"]),
            "cpl",
            str(ROOT / ".foundry" / "repo-profiles"),
            str(canon),
        )
        assert result["verdict"] == "BOOTSTRAP_FAIL"
        assert any("already held" in f for f in result["failures"])
    finally:
        holder.terminate()
        holder.wait(timeout=10)


# --- launcher init ----------------------------------------------------------


def _plan(target: dict, canon: Path, **over: object) -> dict:
    kwargs: dict = {
        "profile": "cpl",
        "worktree": str(target["wt"]),
        "workstream": "TEST-WS",
        "branch": "project/test",
        "audit_base_sha": target["base"],
        "effort": "high",
        "mode": "writer",
        "session": "ses-t",
        "state_path": str(target["state"]),
        "canonical_root": str(canon),
        "allow_same_cwd_pids": False,
        "allow_suppressed_routing": False,
        "install_pre_push_hook": False,
        "run_dir": str(target["wt"].parent / "rundir"),
    }
    kwargs.update(over)
    return launcher_mod.init(**kwargs)


def test_init_cpl_ready_with_dynamic_denies(target: dict, canon: Path) -> None:
    # A sibling worktree of the same repo must land in the injected denies.
    _git(
        ["worktree", "add", str(target["wt"].parent / "sib"), "-b", "project/sib"],
        target["wt"],
        target["env"],
    )
    plan = _plan(target, canon)
    assert plan["verdict"] == "LAUNCH_READY", plan
    env = plan["_env"]
    bundle = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    assert bundle["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert bundle["permission"]["bash"]["git push*"] == "deny"
    sib_deny = f"{target['wt'].parent / 'sib'}*"
    assert bundle["permission"]["external_directory"].get(sib_deny) == "deny"
    assert env["FOUNDRY_EFFORT"] == "high"
    assert env["FOUNDRY_SESSION"] == "ses-t"
    assert len(env["FOUNDRY_CANONICAL_POLICY_HASH"]) == 64
    assert (Path(env["OPENCODE_CONFIG_DIR"]) / "agents" / "foundry-implementer.md").is_file()


def test_effort_below_high_refused(target: dict, canon: Path) -> None:
    plan = _plan(target, canon, effort="medium")
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "medium" in str(plan.get("error", ""))


def test_canonical_model_drift_refused(target: dict, canon: Path, tmp_path: Path) -> None:
    tampered = tmp_path / "tampered"
    import shutil

    shutil.copytree(canon, tampered)
    config = json.loads((tampered / "opencode.json").read_text(encoding="utf-8"))
    config["model"] = "evil/other-model"
    (tampered / "opencode.json").write_text(json.dumps(config), encoding="utf-8")
    plan = _plan(target, canon, canonical_root=str(tampered))
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "model drift" in str(plan.get("error", ""))


def test_suppressed_routing_gates_engine_stale_target(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    # Retarget the fixture at the mage slug so the mage profile identity gate
    # holds and only the routing finding is under test.
    _git(
        ["config", "remote.origin.url", "https://github.com/moeendres-png/mage.git"],
        target["wt"],
        target["env"],
    )
    (target["wt"] / "AGENTS.md").write_text("WS33_COMPLETE gates apply\n", encoding="utf-8")
    refused = _plan(target, canon, profile="mage")
    assert refused["verdict"] == "LAUNCH_REFUSED"
    assert refused["gate"]["drift"]["verdict"] == "DRIFT_FAIL"
    plan = _plan(target, canon, profile="mage", allow_suppressed_routing=True)
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["_env"].get("OPENCODE_DISABLE_PROJECT_CONFIG") == "1"
    assert plan["_env"].get("FOUNDRY_ROUTING_SUPPRESSED") == "1"


# --- hook + safe push integration -------------------------------------------


def test_hook_blocks_raw_push_but_allows_safe_push(target: dict, canon: Path) -> None:
    env = _lock_env(target)
    remote = target["wt"].parent / "hook-remote.git"
    _git(["init", "--bare", "-b", "main", str(remote)], target["wt"].parent, target["env"])
    _git(["remote", "add", "origin2", str(remote)], target["wt"], target["env"])
    _git(["push", "origin2", "main:refs/heads/main"], target["wt"], target["env"])
    hook_path = launcher_mod.install_hook(str(target["wt"]), "project/test")
    assert Path(hook_path).exists()
    # Raw push to the guarded branch dies in the hook.
    raw = subprocess.run(
        ["git", "push", "origin2", "HEAD:refs/heads/project/test"],
        cwd=str(target["wt"]),
        capture_output=True,
        text=True,
        env=target["env"],
        timeout=60,
    )
    assert raw.returncode != 0
    assert "HOOK_REJECT" in raw.stderr
    # safe_push (marker set internally, lock held by parent) succeeds.
    data = yaml.safe_load(target["state"].read_text(encoding="utf-8"))
    data["validated_head"] = _git(["rev-parse", "HEAD"], target["wt"], target["env"])
    data["state_written_against_head"] = data["validated_head"]
    target["state"].write_text(yaml.safe_dump(data), encoding="utf-8")
    _git(["add", "."], target["wt"], target["env"])
    _git(["commit", "-m", "checkpoint"], target["wt"], target["env"])
    driver = (
        "import subprocess, sys; "
        "from foundry import writer_lock; "
        "lock = writer_lock.WriterLock(sys.argv[1], 'TEST-WS', 'project/test', 's'); "
        "lock.acquire(); "
        f"p = subprocess.run([sys.executable, {str(TOOLS / 'safe_push.py')!r}, "
        "'--worktree', sys.argv[1], '--expected-branch', 'project/test', "
        "'--state', sys.argv[2], '--remote', 'origin2', "
        "'--expected-slug', 'hook-remote'], capture_output=True, text=True); "
        "sys.stdout.write(p.stdout); sys.stderr.write(p.stderr); "
        "lock.release(); sys.exit(p.returncode)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver, str(target["wt"]), str(target["state"])],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "PUSHED" in proc.stdout


def test_hook_refuses_to_clobber_foreign_hook(target: dict) -> None:
    hooks = Path(
        subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(target["wt"]),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    if not hooks.is_absolute():
        hooks = target["wt"] / hooks
    hook_file = hooks / "hooks" / "pre-push"
    hook_file.parent.mkdir(parents=True, exist_ok=True)
    hook_file.write_text("#!/bin/sh\n# foreign hook\nexit 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="foreign hook"):
        launcher_mod.install_hook(str(target["wt"]), "project/test")


# --- launch exec ------------------------------------------------------------


def test_launch_holds_lock_passes_env_and_records_telemetry(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    stub = tmp_path / "fake-opencode"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "sys.path.insert(0, os.environ['FOUNDARY_TOOLS'])\n"
        "from foundry import writer_lock\n"
        "bundle = json.loads(os.environ['OPENCODE_CONFIG_CONTENT'])\n"
        "assert bundle['model'] == 'opencode-go/muse-spark-1.3-contributor', 'model lock missing'\n"
        "assert bundle['permission']['bash']['git push*'] == 'deny', 'deny lock missing'\n"
        "assert os.environ.get('FOUNDRY_EFFORT') == 'xhigh', 'effort missing'\n"
        "assert os.path.isdir(os.environ['OPENCODE_CONFIG_DIR']), 'config dir missing'\n"
        "lock = writer_lock.WriterLock(os.environ['FOUNDARY_WT'], 'INTRUDER', 'project/test', '')\n"
        "try:\n"
        "    lock.acquire()\n"
        "except writer_lock.LockedError:\n"
        "    print('STUB: second writer correctly refused')\n"
        "else:\n"
        "    print('STUB: LOCK NOT HELD - launcher defect'); sys.exit(9)\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    plan = _plan(target, canon, effort="xhigh")
    assert plan["verdict"] == "LAUNCH_READY", plan
    env = plan["_env"]
    env["FOUNDRY_OPENCODE_BIN"] = str(stub)
    env["FOUNDARY_TOOLS"] = str(ROOT / "tools")
    env["FOUNDARY_WT"] = str(target["wt"])
    env["FOUNDRY_LOCK_DIR"] = str(target["locks"])
    os.environ["FOUNDRY_LOCK_DIR"] = str(target["locks"])
    try:
        rc = launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "xhigh")
    finally:
        del os.environ["FOUNDRY_LOCK_DIR"]
    assert rc == 7
    metrics_file = target["wt"] / ".foundry" / "metrics.jsonl"
    assert metrics_file.is_file()
    records = [json.loads(line) for line in metrics_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["task_id"] == "TEST-WS"
    assert records[0]["reasoning_effort"] == "xhigh"
    assert "token_usage" not in records[0] and "tool_calls" not in records[0]
    assert records[1]["completed"] is False
    assert isinstance(records[1]["elapsed_seconds"], (int, float))


def test_launch_refused_plan_returns_one(target: dict, canon: Path) -> None:
    plan = _plan(target, canon, effort="low")
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "low") == 1


_SLUG_BY_PROFILE = {
    "cpl": "moeendres-png/commander-playtest-lab",
    "mage": "moeendres-png/mage",
    "forge": "moeendres-png/forge",
}


@pytest.mark.parametrize("profile", ["cpl", "mage", "forge"])
def test_init_ready_for_all_three_profiles(
    tmp_path: Path, canon: Path, profile: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§28: same canonical policy resolves for CPL/Mage/Forge contexts."""
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(tmp_path / "locks"))
    wt = tmp_path / f"{profile}-wt"
    wt.mkdir()
    env = _env()
    _git(["init", "-b", "main"], wt, env)
    _git(
        ["config", "remote.origin.url", f"https://github.com/{_SLUG_BY_PROFILE[profile]}.git"],
        wt,
        env,
    )
    (wt / "code.txt").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "init"], wt, env)
    base = _git(["rev-parse", "HEAD"], wt, env)
    rc = bootstrap_mod.main(
        [
            "--worktree",
            str(wt),
            "--workstream",
            f"TEST-{profile.upper()}",
            "--branch",
            "main",
            "--audit-base-sha",
            base,
            "--profile",
            profile,
            "--profiles-dir",
            str(ROOT / ".foundry" / "repo-profiles"),
            "--init-state",
        ]
    )
    assert rc == 0
    plan = launcher_mod.init(
        profile=profile,
        worktree=str(wt),
        workstream=f"TEST-{profile.upper()}",
        branch="main",
        audit_base_sha=base,
        effort="high",
        mode="writer",
        session="",
        state_path=None,
        canonical_root=str(canon),
        allow_same_cwd_pids=False,
        allow_suppressed_routing=False,
        install_pre_push_hook=False,
        run_dir=str(tmp_path / "rundir"),
    )
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    assert bundle["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert bundle["permission"]["bash"]["git push*"] == "deny"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
