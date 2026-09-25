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
from foundry import opencode_cli_version as version_mod  # noqa: E402

CPL_SLUG = "moeendres-png/commander-playtest-lab"


@pytest.fixture(autouse=True)
def _hermetic_opencode_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WS75R: route ambient binary resolution at a hermetic stub.

    Every launcher init in this module resolves its OpenCode binary through
    this stub unless a test passes explicit ``opencode_bin=`` (which still
    wins), so no test depends on ambient PATH containing a real ``opencode``
    executable. The stub reports exactly the canonical qualified version.
    Function-scoped (own tmp dir per test).
    """
    stub = tmp_path / "qualified-opencode-stub"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        f"    print({version_mod.QUALIFIED_OPENCODE_VERSION!r})\n"
        "    sys.exit(0)\n"
        "print('STUB: unexpected exec', sys.argv[1:])\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    monkeypatch.setenv("FOUNDRY_OPENCODE_BIN", str(stub))


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
            "--state",
            str(target["state"]),
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
        # WS75R: no ambient binary default; the autouse hermetic stub serves
        # FOUNDRY_OPENCODE_BIN (explicit opencode_bin= overrides still win).
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
    # Slug-anchored remote path: WS241 exact push-target identity requires a
    # full owner/repo slug (bare fragments no longer match).
    remote = target["wt"].parent / "test-host" / "hook-remote.git"
    remote.parent.mkdir(parents=True, exist_ok=True)
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
        "'--expected-slug', 'test-host/hook-remote', "
        "'--allow-local-path-target'], capture_output=True, text=True); "
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
        # WS75: answer the launcher version gate like the qualified CLI.
        "if sys.argv[1:] == ['--version']:\n"
        "    print('1.18.30')\n"
        "    sys.exit(0)\n"
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
    plan = _plan(target, canon, effort="xhigh", opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    env = plan["_env"]
    env["FOUNDARY_TOOLS"] = str(ROOT / "tools")
    env["FOUNDARY_WT"] = str(target["wt"])
    env["FOUNDRY_LOCK_DIR"] = str(target["locks"])
    os.environ["FOUNDRY_LOCK_DIR"] = str(target["locks"])
    try:
        rc = launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "xhigh")
    finally:
        del os.environ["FOUNDRY_LOCK_DIR"]
    assert rc == 7
    # WS75: runtime telemetry lives under run_dir, outside the Git worktree.
    metrics_file = Path(plan["run_dir"]) / "metrics.jsonl"
    assert metrics_file.is_file()
    assert not (target["wt"] / ".foundry" / "metrics.jsonl").exists()
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


def test_injection_bundle_carries_no_secret_shaped_keys(target: dict, canon: Path) -> None:
    plan = _plan(target, canon)
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    blob = json.dumps(bundle).lower()
    for marker in ("apikey", "api_key", "token", "secret", "password", "credential"):
        assert marker not in blob, marker
    printable = {k: v for k, v in plan.items() if k != "_env"}
    assert "_env" not in printable
    # Key names are transparent; values (the bundle) must not leak into logs.
    assert plan["_env"]["OPENCODE_CONFIG_CONTENT"] not in json.dumps(printable)


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
    explicit_state = str(wt / ".foundry" / "WORKSTREAM_STATE.yaml")
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
            "--state",
            explicit_state,
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
        state_path=explicit_state,
        canonical_root=str(canon),
        allow_same_cwd_pids=False,
        allow_suppressed_routing=False,
        install_pre_push_hook=False,
        run_dir=str(tmp_path / "rundir"),
        # WS75R: autouse hermetic stub serves the binary (no ambient opencode).
    )
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    assert bundle["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert bundle["permission"]["bash"]["git push*"] == "deny"


# --- explicit-state authority (ROOT_STATE_SEMANTICS) -------------------------


def _cli_base(target: dict) -> list[str]:
    return [
        "--worktree",
        str(target["wt"]),
        "--workstream",
        "TEST-WS",
        "--branch",
        "project/test",
        "--audit-base-sha",
        target["base"],
    ]


def test_bootstrap_cli_refuses_without_state(target: dict) -> None:
    with pytest.raises(SystemExit) as exc:
        bootstrap_mod.main(
            [
                *_cli_base(target),
                "--profile",
                "cpl",
                "--profiles-dir",
                str(ROOT / ".foundry" / "repo-profiles"),
            ]
        )
    assert exc.value.code == 2  # argparse: required --state missing


def test_launcher_cli_refuses_without_state(target: dict, canon: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        launcher_mod.main(
            ["init", *_cli_base(target), "--profile", "cpl", "--canonical-root", str(canon)]
        )
    assert exc.value.code == 2  # argparse: required --state missing


def test_bootstrap_api_refuses_none_state_path(target: dict, canon: Path) -> None:
    result = bootstrap_mod.bootstrap(
        str(target["wt"]),
        "TEST-WS",
        "project/test",
        target["base"],
        None,
        "cpl",
        str(ROOT / ".foundry" / "repo-profiles"),
        str(canon),
    )
    assert result["verdict"] == "BOOTSTRAP_FAIL"
    assert any("explicit --state" in f for f in result["failures"])


def test_launcher_init_refuses_none_state_path(target: dict, canon: Path) -> None:
    plan = _plan(target, canon, state_path=None)
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "explicit --state" in str(plan.get("error", ""))


def test_explicit_state_path_reaches_env_and_context_exact(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    """FOUNDRY_STATE_PATH/context carry the exact explicit path (never guessed)."""
    custom = tmp_path / "custom" / "STATE.yaml"
    custom.parent.mkdir(parents=True)
    custom.write_text(target["state"].read_text(encoding="utf-8"), encoding="utf-8")
    plan = _plan(target, canon, state_path=str(custom))
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["_env"]["FOUNDRY_STATE_PATH"] == str(custom)
    assert plan["state_path"] == str(custom)
    context = json.loads(Path(plan["context_path"]).read_text(encoding="utf-8"))
    assert context["state_path"] == str(custom)


def test_init_state_writes_only_at_explicit_path(target: dict, tmp_path: Path) -> None:
    target["state"].unlink()
    custom = tmp_path / "dedicated" / "WS-TEST.yaml"
    rc = bootstrap_mod.main(
        [
            *_cli_base(target),
            "--state",
            str(custom),
            "--profile",
            "cpl",
            "--profiles-dir",
            str(ROOT / ".foundry" / "repo-profiles"),
            "--init-state",
        ]
    )
    assert rc == 0
    data = yaml.safe_load(custom.read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0"
    assert data["validated_head"] is None
    assert data["ownership"] == "TEST-WS"
    # No implicit worktree-root state file is created as a side effect.
    assert not (target["wt"] / ".foundry" / "WORKSTREAM_STATE.yaml").exists()


# --- explicit ownership authority (P2 follow-up) -------------------------------


def _rewrite_state_ownership(target: dict, ownership: str) -> None:
    data = yaml.safe_load(target["state"].read_text(encoding="utf-8"))
    data["ownership"] = ownership
    target["state"].write_text(yaml.safe_dump(data), encoding="utf-8")


def test_bootstrap_rejects_conflicting_state_ownership(target: dict, canon: Path) -> None:
    """An explicit state owned by another workstream fails closed."""
    _rewrite_state_ownership(target, "OTHER-WS")
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
    assert any("ownership" in f for f in result["failures"])


def test_bootstrap_accepts_matching_explicit_ownership(target: dict, canon: Path) -> None:
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


def test_launcher_declares_own_pair_in_gate_and_context(target: dict, canon: Path) -> None:
    """The launcher auto-declares its own worktree/state pair (no discovery)."""
    plan = _plan(target, canon)
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["state_path"] == str(target["state"])
    assert plan["worktree_states"] == {os.path.realpath(str(target["wt"])): str(target["state"])}
    context = json.loads(Path(plan["context_path"]).read_text(encoding="utf-8"))
    assert context["worktree_states"] == {os.path.realpath(str(target["wt"])): str(target["state"])}
    assert plan["gate"]["state_path"] == str(target["state"])


def test_launcher_refuses_malformed_worktree_state(target: dict, canon: Path) -> None:
    plan = _plan(target, canon, worktree_states=["no-equals-here"])
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "worktree-state" in str(plan.get("error", ""))


def test_launcher_refuses_conflicting_own_pair(target: dict, canon: Path, tmp_path: Path) -> None:
    other = tmp_path / "OTHER.yaml"
    other.write_text(target["state"].read_text(encoding="utf-8"), encoding="utf-8")
    plan = _plan(
        target,
        canon,
        worktree_states=[f"{target['wt']}={other}"],
    )
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "conflicts with --state" in str(plan.get("error", ""))


def test_launcher_sibling_pair_flows_to_inventory(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    """An operator-declared sibling pair reaches the bootstrap gate entries."""
    sib = tmp_path / "sibstate" / "SIB.yaml"
    sib.parent.mkdir(parents=True)
    data = yaml.safe_load(target["state"].read_text(encoding="utf-8"))
    data["worktree"] = str(tmp_path / "sib-wt")
    data["ownership"] = "SIB-WS"
    sib.write_text(yaml.safe_dump(data), encoding="utf-8")
    plan = _plan(
        target,
        canon,
        worktree_states=[f"{tmp_path / 'sib-wt'}={sib}"],
    )
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["worktree_states"][str(tmp_path / "sib-wt")] == str(sib)


def test_bootstrap_cli_accepts_worktree_state_map(target: dict) -> None:
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
            "--state",
            str(target["state"]),
            "--profile",
            "cpl",
            "--profiles-dir",
            str(ROOT / ".foundry" / "repo-profiles"),
            "--worktree-state",
            f"{target['wt']}={target['state']}",
        ]
    )
    assert rc == 0


def test_bootstrap_cli_rejects_malformed_worktree_state(target: dict) -> None:
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
            "--state",
            str(target["state"]),
            "--profile",
            "cpl",
            "--profiles-dir",
            str(ROOT / ".foundry" / "repo-profiles"),
            "--worktree-state",
            "malformed",
        ]
    )
    assert rc == 1


@pytest.mark.parametrize(
    "override,provider,model",
    [
        (None, "opencode-go", "opencode-go/muse-spark-1.3-contributor"),
        ("zen", "opencode", "opencode/muse-spark-1.3-contributor-free"),
    ],
)
def test_ws190_execution_identity(target, canon, override, provider, model):
    before = (canon / "opencode.json").read_bytes()
    plan = _plan(target, canon, execution_provider=override)
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    assert bundle["model"] == model
    assert bundle["enabled_providers"] == [provider]
    assert bundle["share"] == "disabled"
    original = json.loads(before)
    assert bundle["permission"] == original["permission"]
    assert bundle["experimental"]["policies"][-1] == {
        "action": "provider.use",
        "effect": "allow",
        "resource": provider,
    }
    context = json.loads(Path(plan["context_path"]).read_text())
    assert context["execution"]["provider"] == provider
    assert context["execution"]["model"] == model
    assert context["execution"]["override"] == (override or "canonical")
    assert context["execution"]["requested_effort"] == "high"
    if override:
        assert bundle["disabled_providers"] == ["opencode-go"]
        assert bundle["small_model"] == model
        variants = bundle["provider"][provider]["models"][model.split("/")[1]]["variants"]
        assert all(v == {"disabled": True} for v in variants.values())
        assert "reasoningEffort" not in json.dumps(bundle["provider"][provider])
        for agent in bundle["agent"].values():
            assert agent["model"] == model
            assert agent["variant"] == ""
    else:
        assert "opencode" not in bundle["provider"]
    assert (canon / "opencode.json").read_bytes() == before


@pytest.mark.parametrize("override", ["auto", "openai", "", "opencode"])
def test_ws190_unknown_override_refused(target, canon, override):
    plan = _plan(target, canon, execution_provider=override)
    assert plan["verdict"] == "LAUNCH_REFUSED"


@pytest.mark.parametrize("effort", ["medium", "low", "minimal", "none", "off"])
def test_ws190_zen_below_high_refused(target, canon, effort):
    assert (
        _plan(target, canon, execution_provider="zen", effort=effort)["verdict"] == "LAUNCH_REFUSED"
    )


@pytest.mark.parametrize("result", [0, 7, 130, -2, "interrupt", "spawn-error"])
@pytest.mark.parametrize("override", [None, "zen"])
def test_ws190_child_lifecycle(target, canon, monkeypatch, result, override):
    plan = _plan(target, canon, **({"execution_provider": override} if override else {}))
    assert plan["verdict"] == "LAUNCH_READY", plan
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    real_run = subprocess.run
    calls = []

    def child(args, **kwargs):
        if args[0] == "git":
            return real_run(args, **kwargs)
        calls.append(args)
        contender = launcher_mod.writer_lock_mod.WriterLock(str(target["wt"]), "OTHER", "b", "s")
        with pytest.raises(launcher_mod.writer_lock_mod.LockedError):
            contender.acquire()
        if result == "interrupt":
            raise KeyboardInterrupt
        if result == "spawn-error":
            raise FileNotFoundError("stub missing")
        return subprocess.CompletedProcess(args, result)

    monkeypatch.setattr(launcher_mod.subprocess, "run", child)
    expected = 130 if result in ("interrupt", -2) else 127 if result == "spawn-error" else result
    assert launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high") == expected
    assert len(calls) == 1  # no fallback/retry, including provider failure
    if override:
        assert calls[0][3:5] == ["--model", launcher_mod.ZEN_MODEL]
    records = [
        json.loads(s) for s in (Path(plan["run_dir"]) / "metrics.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2
    for record in records:
        assert record["model"] == plan["execution"]["model"]
        assert record["execution_provider"] == plan["execution"]["provider"]
        assert record["execution_override"] == (override or "canonical")
    assert records[-1]["exit_status"] == expected
    assert records[-1]["completed"] is (result == 0)
    assert records[-1]["interrupted"] is (result in ("interrupt", -2, 130))
    contender = launcher_mod.writer_lock_mod.WriterLock(str(target["wt"]), "NEXT", "b", "s")
    contender.acquire()
    contender.release()


@pytest.mark.parametrize(
    "extra", [["--model", "other/x"], ["-mother/x"], ["--variant=low"], ["--continue"], ["-c"]]
)
def test_ws190_child_cannot_override_policy(target, canon, extra, monkeypatch):
    plan = _plan(target, canon, execution_provider="zen")
    monkeypatch.setattr(
        launcher_mod.subprocess, "run", lambda *a, **k: pytest.fail("must not execute")
    )
    assert launcher_mod.launch(plan, extra, str(target["wt"]), "TEST-WS", "high") == 1


def test_ws190_ambient_permission_override_removed(target, canon, monkeypatch):
    monkeypatch.setenv("OPENCODE_PERMISSION", '{"bash":"allow"}')
    plan = _plan(target, canon, execution_provider="zen")
    assert "OPENCODE_PERMISSION" not in plan["_env"]


def test_ws190_end_telemetry_failure_still_releases(target, canon, monkeypatch):
    plan = _plan(target, canon)
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    real_record = launcher_mod.metrics_mod.record

    def record(*args, **kwargs):
        if "ended_utc" in kwargs:
            raise ValueError("telemetry defect")
        return real_record(*args, **kwargs)

    monkeypatch.setattr(launcher_mod.metrics_mod, "record", record)
    with pytest.raises(ValueError, match="telemetry defect"):
        launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high")
    lock = launcher_mod.writer_lock_mod.WriterLock(str(target["wt"]), "NEXT", "b", "s")
    lock.acquire()
    lock.release()


def test_ws190_cli_consumes_explicit_override(target, canon, monkeypatch, capsys):
    captured = {}

    def fake_init(**kwargs):
        captured.update(kwargs)
        return {"verdict": "LAUNCH_READY"}

    monkeypatch.setattr(launcher_mod, "init", fake_init)
    rc = launcher_mod.main(
        [
            "init",
            *_cli_base(target),
            "--state",
            str(target["state"]),
            "--profile",
            "cpl",
            "--canonical-root",
            str(canon),
            "--execution-provider",
            "zen",
            "--run-dir",
            str(target["wt"].parent / "cli-run"),
        ]
    )
    assert rc == 0
    assert captured["execution_provider"] == "zen"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
