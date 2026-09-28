"""Tests for tools/foundry/bootstrap.py and tools/foundry/launcher.py.

Hermetic fixtures (fake canonical root + fake repos) plus real subprocesses,
real flock locks, and real file-remotes. The launch test execs a stub binary
through FOUNDRY_OPENCODE_BIN and proves lock-hold-across-exec by having the
child attempt a second acquire.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS = ROOT / "tools" / "foundry"

sys.path.insert(0, str(ROOT / "tools"))

from foundry import bootstrap as bootstrap_mod  # noqa: E402
from foundry import fs_sandbox as fs_sandbox_mod  # noqa: E402
from foundry import launcher as launcher_mod  # noqa: E402
from foundry import opencode_cli_version as version_mod  # noqa: E402
from foundry import permission_battery as permission_battery_mod  # noqa: E402

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
    # The omitted execution profile resolves to the primary executor.
    assert bundle["model"] == "opencode-go/space-bunny-free"
    assert bundle["permission"]["bash"]["git push*"] == "allow"
    assert bundle["permission"]["bash"]["git push origin main*"] == "deny"
    assert bundle["permission"]["bash"]["git push --force*"] == "deny"
    for sib_deny in launcher_mod._root_patterns(str(target["wt"].parent / "sib")):
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
        "assert bundle['model'] == 'opencode-go/space-bunny-free', 'model lock missing'\n"
        "assert bundle['permission']['bash']['git push*'] == 'allow', 'delegated push missing'\n"
        "assert bundle['permission']['bash']['git push origin main*'] == 'deny', 'main-push deny missing'\n"
        "assert bundle['permission']['bash']['git push --force*'] == 'deny', 'force-push deny missing'\n"
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
    """The injected config must carry no secret VALUES, and must still guard secrets.

    A whole-blob substring scan cannot express this: a permission pattern such as
    ``gh secret*`` or ``cat *credentials*`` is a rule *protecting* secrets and
    necessarily contains the marker word. The invariant is therefore split:

    * outside the permission block, no secret-shaped key or value may appear;
    * inside it, the rules that deny secret access must be present and closed;
    * no string value anywhere may look like a live credential.
    """
    plan = _plan(target, canon)
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])

    def strip(value: object) -> object:
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k != "permission"}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    non_permission = json.dumps(strip(bundle)).lower()
    for marker in ("apikey", "api_key", "token", "password", "credential"):
        assert marker not in non_permission, marker

    # The secret-protecting denies must still be closed, and secret files must
    # still be unreadable. This is the positive half of the same property.
    bash = bundle["permission"]["bash"]
    for pattern in (
        "env",
        "env *",
        "printenv*",
        "gh auth*",
        "gh secret*",
        "cat *id_rsa*",
        "cat *.pem",
        "cat *.key",
        "cat *credentials*",
        "cat *.netrc",
    ):
        assert bash.get(pattern) == "deny", pattern
    for tool in ("read", "glob", "grep", "list", "edit"):
        for pattern in ("*.env", "*.env.*", "**/*.env", "**/*.env.*"):
            assert bundle["permission"][tool].get(pattern) == "deny", f"{tool}:{pattern}"

    # No value anywhere may look like a live credential.
    def walk(node: object) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            lowered = node.lower()
            for prefix in ("ghp_", "gho_", "github_pat_", "sk-", "xoxb-", "akia"):
                assert not lowered.startswith(prefix), node
            assert "bearer " not in lowered, node

    walk(bundle)

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
    # The omitted execution profile resolves to the primary executor.
    assert bundle["model"] == "opencode-go/space-bunny-free"
    assert bundle["permission"]["bash"]["git push*"] == "allow"
    assert bundle["permission"]["bash"]["git push origin main*"] == "deny"
    assert bundle["permission"]["bash"]["git push --force*"] == "deny"


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
    "override,profile,provider,model,resolved_override,variant",
    [
        # No flag resolves to the primary executor; an omitted profile must never
        # fall through to the alternate.
        (None, None, "opencode-go", "opencode-go/space-bunny-free", "space-bunny", "max"),
        (None, "space-bunny", "opencode-go", "opencode-go/space-bunny-free", "space-bunny", "max"),
        (
            None,
            "muse",
            "opencode-go",
            "opencode-go/muse-spark-1.3-contributor",
            "muse",
            "xhigh",
        ),
        (
            "zen",
            None,
            "opencode",
            "opencode/muse-spark-1.3-contributor-free",
            "zen",
            "",
        ),
    ],
)
def test_ws190_execution_identity(
    target, canon, override, profile, provider, model, resolved_override, variant
):
    before = (canon / "opencode.json").read_bytes()
    plan = _plan(
        target,
        canon,
        execution_provider=override,
        **({"execution_profile": profile} if profile else {}),
    )
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
    # Telemetry must name the executor that actually runs: a "muse" label over a
    # Space Bunny run would be a silent fallback.
    assert context["execution"]["override"] == resolved_override
    assert context["execution"]["requested_effort"] == "high"
    if override == "zen":
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
        # Every reachable agent is pinned to the selected executor at exactly one
        # authorized native level, so no agent can silently run at another level.
        for agent in bundle["agent"].values():
            assert agent["model"] == model, agent
            assert agent["variant"] == variant, agent
        short = model.split("/", 1)[1]
        assert bundle["provider"][provider]["whitelist"] == [short]
        enabled = sorted(
            name
            for name, spec in bundle["provider"][provider]["models"][short]["variants"].items()
            if spec != {"disabled": True}
        )
        assert enabled == [variant]
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
        assert record["execution_override"] == (override or "space-bunny")
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


# --- explicit Space Bunny execution profile ---------------------------------


def test_space_bunny_profile_pins_go_model_and_native_max(target, canon):
    before = (canon / "opencode.json").read_bytes()
    plan = _plan(target, canon, execution_profile="space-bunny")
    assert plan["verdict"] == "LAUNCH_READY", plan
    execution = plan["execution"]
    assert execution == {
        "profile": "space-bunny",
        "override": "space-bunny",
        "provider": "opencode-go",
        "model": "opencode-go/space-bunny-free",
        "requested_effort": "high",
        "variant_resolution": "native_max",
        "native_variant": "max",
    }
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    assert bundle["model"] == "opencode-go/space-bunny-free"
    assert bundle["small_model"] == "opencode-go/space-bunny-free"
    assert bundle["enabled_providers"] == ["opencode-go"]
    assert bundle["provider"]["opencode-go"]["whitelist"] == ["space-bunny-free"]
    model = bundle["provider"]["opencode-go"]["models"]["space-bunny-free"]
    assert model["options"] == {"reasoningEffort": "max"}
    assert model["variants"] == {"max": {}}
    assert all(
        agent == {"model": "opencode-go/space-bunny-free", "variant": "max"}
        for agent in bundle["agent"].values()
    )
    assert plan["_env"]["FOUNDRY_EXECUTION_PROFILE"] == "space-bunny"
    assert plan["_env"]["FOUNDRY_NATIVE_VARIANT"] == "max"
    context = json.loads(Path(plan["context_path"]).read_text())
    assert context["execution"] == execution
    assert (canon / "opencode.json").read_bytes() == before


def test_space_bunny_profile_rejects_conflicting_zen_override(target, canon):
    plan = _plan(
        target,
        canon,
        execution_profile="space-bunny",
        execution_provider="zen",
    )
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "cannot select different executors" in plan["error"]


def test_space_bunny_profile_rejects_unknown_api_profile(target, canon):
    plan = _plan(target, canon, execution_profile="other")
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "unknown execution profile" in plan["error"]


def test_space_bunny_launch_uses_explicit_model_and_no_fallback(target, canon, monkeypatch):
    plan = _plan(target, canon, execution_profile="space-bunny")
    assert plan["verdict"] == "LAUNCH_READY", plan
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    real_run = subprocess.run
    calls = []

    def child(args, **kwargs):
        if args[0] == "git":
            return real_run(args, **kwargs)
        calls.append(args)
        return subprocess.CompletedProcess(args, 7)

    monkeypatch.setattr(launcher_mod.subprocess, "run", child)
    assert launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high") == 7
    assert len(calls) == 1
    assert calls[0][3:5] == ["--model", launcher_mod.SPACE_BUNNY_MODEL]
    records = [
        json.loads(s) for s in (Path(plan["run_dir"]) / "metrics.jsonl").read_text().splitlines()
    ]
    assert {record["model"] for record in records} == {launcher_mod.SPACE_BUNNY_MODEL}
    assert {record["execution_override"] for record in records} == {"space-bunny"}
    assert {record["execution_profile"] for record in records} == {"space-bunny"}
    assert {record["native_variant"] for record in records} == {"max"}
    assert {record["variant_resolution"] for record in records} == {"native_max"}


@pytest.mark.parametrize("effort", ["high", "xhigh"])
def test_space_bunny_project_effort_maps_to_native_max(target, canon, effort):
    plan = _plan(target, canon, execution_profile="space-bunny", effort=effort)
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["execution"]["requested_effort"] == effort
    assert plan["execution"]["native_variant"] == "max"
    assert plan["execution"]["variant_resolution"] == "native_max"
    assert plan["_env"]["FOUNDRY_EFFORT"] == effort
    assert plan["_env"]["FOUNDRY_NATIVE_VARIANT"] == "max"


def test_muse_xhigh_does_not_fabricate_top_level_native_variant(target, canon):
    plan = _plan(target, canon, execution_profile="muse", effort="xhigh")
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["execution"]["requested_effort"] == "xhigh"
    assert plan["execution"]["variant_resolution"] == "canonical_agent_variant"
    assert plan["execution"]["native_variant"] is None
    assert "FOUNDRY_NATIVE_VARIANT" not in plan["_env"]


def test_nested_muse_launch_clears_ambient_native_variant(target, canon, monkeypatch):
    monkeypatch.setenv("FOUNDRY_NATIVE_VARIANT", "max")
    plan = _plan(target, canon, execution_profile="muse", effort="xhigh")
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["execution"]["native_variant"] is None
    assert "FOUNDRY_NATIVE_VARIANT" not in plan["_env"]


def test_unsuppressed_nested_launch_clears_ambient_routing_suppression(target, canon, monkeypatch):
    monkeypatch.setenv("OPENCODE_DISABLE_PROJECT_CONFIG", "1")
    monkeypatch.setenv("FOUNDRY_ROUTING_SUPPRESSED", "1")
    plan = _plan(target, canon, execution_profile="space-bunny")
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert "OPENCODE_DISABLE_PROJECT_CONFIG" not in plan["_env"]
    assert "FOUNDRY_ROUTING_SUPPRESSED" not in plan["_env"]


def test_space_bunny_cli_consumes_explicit_profile(target, canon, monkeypatch):
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
            "--execution-profile",
            "space-bunny",
            "--run-dir",
            str(target["wt"].parent / "cli-space-bunny"),
        ]
    )
    assert rc == 0
    assert captured["execution_profile"] == "space-bunny"


# --- explicit cross-workstream access ---------------------------------------


def _workspace_surface(tmp_path: Path, *, ownership: str = "TEST-WS") -> tuple[Path, Path, dict]:
    root = tmp_path / "side-wt"
    root.mkdir()
    env = _env()
    _git(["init", "-b", "main"], root, env)
    _git(["config", "remote.origin.url", f"https://github.com/{CPL_SLUG}.git"], root, env)
    (root / "side.txt").write_text("side\n", encoding="utf-8")
    (root / ".gitignore").write_text(".foundry/\n", encoding="utf-8")
    _git(["add", "."], root, env)
    _git(["commit", "-m", "side"], root, env)
    _git(["checkout", "-b", "project/side"], root, env)
    head = _git(["rev-parse", "HEAD"], root, env)
    tree = _git(["rev-parse", "HEAD^{tree}"], root, env)
    state_path = root / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.parent.mkdir(parents=True)
    state = {
        "schema_version": "2.0",
        "repository": CPL_SLUG,
        "worktree": str(root),
        "branch": "project/side",
        "audit_base_sha": head,
        "audit_base_tree": tree,
        "state_written_against_head": head,
        "validated_head": head,
        "objective": "side objective",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": ownership,
        "status": "ACTIVE",
        "exact_next_action": "continue",
    }
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    spec = {
        "label": "side",
        "root": str(root),
        "repo_slug": CPL_SLUG,
        "commit": head,
        "tree": tree,
        "cleanliness": "allow-ignored-build-outputs",
        "access": "owned-write",
        "branch": "project/side",
        "state_path": str(state_path),
        "ownership": ownership,
    }
    return root, state_path, spec


def test_workspace_access_read_only_uses_disposable_snapshot(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, owned = _workspace_surface(tmp_path)
    spec = {
        key: value
        for key, value in owned.items()
        if key not in {"branch", "state_path", "ownership"}
    }
    spec["access"] = "read-only"
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    runtime = plan["workspace_access"][0]
    snapshot = Path(runtime["root"])
    assert snapshot != root
    assert snapshot.is_dir()
    assert "source_root" not in runtime
    assert _git(["rev-parse", "HEAD"], snapshot) == owned["commit"]

    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    ext = bundle["permission"]["external_directory"]
    edit = bundle["permission"]["edit"]
    for pattern in launcher_mod._root_patterns(str(root)):
        assert ext[pattern] == "deny"
        assert edit[pattern] == "deny"
    for pattern in launcher_mod._root_patterns(str(snapshot)):
        assert ext[pattern] == "allow"
        assert edit[pattern] == "deny"

    # Build/tool output may mutate the disposable snapshot, never authoritative source.
    (snapshot / "side.txt").write_text("snapshot-only\n", encoding="utf-8")
    assert (root / "side.txt").read_text(encoding="utf-8") == "side\n"
    injected = json.loads(plan["_env"]["FOUNDRY_WORKSPACE_ACCESS"])
    assert injected[0]["root"] == str(snapshot)
    assert "source_root" not in injected[0]


def test_legacy_reference_uses_disposable_snapshot(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, owned = _workspace_surface(tmp_path)
    ref = {
        "label": "side-ref",
        "root": str(root),
        "repo_slug": CPL_SLUG,
        "commit": owned["commit"],
        "tree": owned["tree"],
        "cleanliness": "allow-ignored-build-outputs",
        "intent": "read-only",
    }
    plan = _plan(target, canon, references=[json.dumps(ref)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    runtime = plan["references"][0]
    snapshot = Path(runtime["root"])
    assert snapshot != root
    assert _git(["rev-parse", "HEAD"], snapshot) == owned["commit"]
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    for pattern in launcher_mod._root_patterns(str(root)):
        assert bundle["permission"]["external_directory"][pattern] == "deny"
        assert bundle["permission"]["edit"][pattern] == "deny"
    for pattern in launcher_mod._root_patterns(str(snapshot)):
        assert bundle["permission"]["external_directory"][pattern] == "allow"
        assert bundle["permission"]["edit"][pattern] == "deny"


def test_workspace_access_read_only_rejects_lookalike_remote(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, owned = _workspace_surface(tmp_path)
    _git(
        [
            "config",
            "remote.origin.url",
            "https://github.com/moeendres-png/commander-playtest-lab-copy.git",
        ],
        root,
        target["env"],
    )
    spec = {
        key: value
        for key, value in owned.items()
        if key not in {"branch", "state_path", "ownership"}
    }
    spec["access"] = "read-only"
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_REFUSED"
    error = str(plan.get("error", ""))
    assert "remote identity" in error
    assert "exact requested slug" in error


def test_legacy_reference_rejects_lookalike_remote(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, owned = _workspace_surface(tmp_path)
    _git(
        [
            "config",
            "remote.origin.url",
            "https://github.com/moeendres-png/commander-playtest-lab-copy.git",
        ],
        root,
        target["env"],
    )
    ref = {
        "label": "side-ref",
        "root": str(root),
        "repo_slug": CPL_SLUG,
        "commit": owned["commit"],
        "tree": owned["tree"],
        "cleanliness": "allow-ignored-build-outputs",
        "intent": "read-only",
    }
    plan = _plan(target, canon, references=[json.dumps(ref)])
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "exact fetch identity" in str(plan.get("error", ""))


def test_workspace_access_owned_write_requires_matching_state_and_injects_write(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    for pattern in launcher_mod._root_patterns(str(root)):
        assert bundle["permission"]["external_directory"][pattern] == "allow"
        assert bundle["permission"]["edit"][pattern] == "allow"
    assert plan["worktree_states"][str(root)] == spec["state_path"]
    assert plan["workspace_access"][0]["ownership"] == "TEST-WS"


def test_owned_write_refuses_state_owned_by_other_workstream(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    _, _, spec = _workspace_surface(tmp_path, ownership="SIDE-WS")
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "current workstream" in str(plan.get("error", ""))


def test_workspace_path_rules_do_not_match_same_prefix_sibling(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    evil = Path(str(root) + "-evil")
    evil.mkdir()
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    # The declaration-specific rules are boundary anchored: neither exact-root nor
    # descendant pattern may match a same-prefix sibling. Generic /tmp policy is
    # intentionally irrelevant to this regression.
    probe = str(evil / "payload.txt")
    for pattern in launcher_mod._root_patterns(str(root)):
        assert not permission_battery_mod.matches(pattern, probe), pattern


def test_workspace_access_owned_write_refuses_wrong_ownership(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    _, _, spec = _workspace_surface(tmp_path)
    spec["ownership"] = "WRONG"
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "ownership" in str(plan.get("error", ""))


def test_multi_surface_launch_holds_every_writer_lock(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    real_run = subprocess.run
    calls = []

    def child(args, **kwargs):
        if args[0] == "git":
            return real_run(args, **kwargs)
        calls.append(args)
        for candidate, owner, branch in (
            (str(target["wt"]), "OTHER", "project/test"),
            (str(root), "OTHER", "project/side"),
        ):
            contender = launcher_mod.writer_lock_mod.WriterLock(candidate, owner, branch, "other")
            with pytest.raises(launcher_mod.writer_lock_mod.LockedError):
                contender.acquire()
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(launcher_mod.subprocess, "run", child)
    assert launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high") == 0
    assert len(calls) == 1


def test_multi_surface_launch_fails_before_child_when_secondary_lock_held(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    held = launcher_mod.writer_lock_mod.WriterLock(str(root), "FOREIGN", "project/side", "x")
    held.acquire()
    try:
        monkeypatch.setattr(
            launcher_mod.subprocess,
            "run",
            lambda *args, **kwargs: pytest.fail("child must not start when any owned lock is held"),
        )
        assert (
            launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high")
            == launcher_mod.writer_lock_mod.HELD_EXIT
        )
        primary = launcher_mod.writer_lock_mod.WriterLock(
            str(target["wt"]), "NEXT", "project/test", "next"
        )
        primary.acquire()
        primary.release()
    finally:
        held.release()


def test_owned_write_rejects_protected_main_branch(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, state_path, spec = _workspace_surface(tmp_path)
    _git(["checkout", "main"], root, target["env"])
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["branch"] = "main"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    spec["branch"] = "main"
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "protected" in str(plan.get("error", ""))


def test_owned_write_rejects_lookalike_remote_identity(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    _git(
        [
            "config",
            "remote.origin.url",
            "https://github.com/example/moeendres-png/commander-playtest-lab-copy.git",
        ],
        root,
        target["env"],
    )
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "remote identity" in str(plan.get("error", ""))


def test_duplicate_reference_label_fails_closed(target: dict, canon: Path, tmp_path: Path) -> None:
    root, _, owned = _workspace_surface(tmp_path)
    ref = {
        "label": "dup",
        "root": str(root),
        "repo_slug": CPL_SLUG,
        "commit": owned["commit"],
        "tree": owned["tree"],
        "cleanliness": "clean",
        "intent": "read-only",
    }
    plan = _plan(target, canon, references=[json.dumps(ref), json.dumps(ref)])
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "duplicate declared workspace label" in str(plan.get("error", ""))


def test_root_cannot_be_reference_and_owned_write(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    ref = {
        "label": "ref-side",
        "root": str(root),
        "repo_slug": CPL_SLUG,
        "commit": spec["commit"],
        "tree": spec["tree"],
        "cleanliness": "clean",
        "intent": "read-only",
    }
    plan = _plan(
        target,
        canon,
        references=[json.dumps(ref)],
        workspace_access=[json.dumps(spec)],
    )
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "cannot be both" in str(plan.get("error", ""))


def test_owned_write_reapplies_sensitive_edit_denies(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    rules = [
        {"permission": "edit", "pattern": pattern, "action": action}
        for pattern, action in bundle["permission"]["edit"].items()
    ]
    for probe in (str(root / ".env"), str(root / "secrets" / "prod.env")):
        verdict, matched = permission_battery_mod.evaluate_rule(rules, "edit", probe)
        assert verdict == "DENIED", (probe, matched)


def test_secondary_repository_siblings_are_denied(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    sibling = tmp_path / "side-linked-sibling"
    _git(["worktree", "add", str(sibling), "-b", "project/side-sibling"], root, target["env"])
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    for pattern in launcher_mod._root_patterns(str(sibling)):
        assert bundle["permission"]["external_directory"].get(pattern) == "deny"


def test_owned_write_is_reverified_after_lock_acquisition(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    marker_file = tmp_path / "child-started"
    stub = tmp_path / "opencode-revalidation-stub"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('1.18.30'); raise SystemExit(0)\n"
        f"pathlib.Path({str(marker_file)!r}).write_text('started')\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    plan = _plan(
        target,
        canon,
        workspace_access=[json.dumps(spec)],
        opencode_bin=str(stub),
    )
    assert plan["verdict"] == "LAUNCH_READY", plan
    (root / "after-init.txt").write_text("changed\n", encoding="utf-8")
    _git(["add", "."], root, target["env"])
    _git(["commit", "-m", "changed after init"], root, target["env"])
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    assert launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high") == 1
    assert not marker_file.exists()


def test_owned_write_rejects_foreign_same_cwd_opencode(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    occupant = subprocess.Popen(
        ["opencode", "-c", "import time; time.sleep(30)"],
        executable=sys.executable,
        cwd=str(root),
    )
    try:
        assert launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high") == 1
    finally:
        occupant.kill()
        occupant.wait()


def test_cross_workspace_requires_standalone_primary_checkout(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    linked = tmp_path / "linked-primary"
    _git(
        ["worktree", "add", str(linked), "-b", "project/linked-primary"],
        target["wt"],
        target["env"],
    )
    head = _git(["rev-parse", "HEAD"], linked, target["env"])
    state_path = linked / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.parent.mkdir(parents=True)
    state = yaml.safe_load(target["state"].read_text(encoding="utf-8"))
    state.update(
        {
            "worktree": str(linked),
            "branch": "project/linked-primary",
            "audit_base_sha": head,
            "state_written_against_head": head,
            "validated_head": head,
        }
    )
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    root, _, spec = _workspace_surface(tmp_path)
    plan = launcher_mod.init(
        profile="cpl",
        worktree=str(linked),
        workstream="TEST-WS",
        branch="project/linked-primary",
        audit_base_sha=head,
        effort="high",
        mode="writer",
        session="",
        state_path=str(state_path),
        canonical_root=str(canon),
        allow_same_cwd_pids=False,
        allow_suppressed_routing=False,
        install_pre_push_hook=False,
        run_dir=str(tmp_path / "cross-run"),
        workspace_access=[json.dumps(spec)],
    )
    assert root.is_dir()
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "standalone" in str(plan.get("error", ""))


def test_cross_workspace_state_must_be_inside_owned_surface(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, state_path, spec = _workspace_surface(tmp_path)
    outside = tmp_path / "outside-state.yaml"
    outside.write_text(state_path.read_text(encoding="utf-8"), encoding="utf-8")
    spec["state_path"] = str(outside)
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert root.is_dir()
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "ROOT/.foundry" in str(plan.get("error", ""))


def test_cross_workspace_run_dir_cannot_overlap_workspace(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, spec = _workspace_surface(tmp_path)
    plan = _plan(
        target,
        canon,
        workspace_access=[json.dumps(spec)],
        run_dir=str(root / "runtime"),
    )
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "run-dir" in str(plan.get("error", ""))


def test_cross_workspace_init_reserves_unique_runtime_snapshots(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    root, _, owned = _workspace_surface(tmp_path)
    ref = {
        "label": "unique",
        "root": str(root),
        "repo_slug": CPL_SLUG,
        "commit": owned["commit"],
        "tree": owned["tree"],
        "cleanliness": "allow-ignored-build-outputs",
        "intent": "read-only",
    }
    first = _plan(target, canon, references=[json.dumps(ref)])
    second = _plan(target, canon, references=[json.dumps(ref)])
    assert first["verdict"] == second["verdict"] == "LAUNCH_READY"
    assert first["run_dir"] != second["run_dir"]
    assert first["references"][0]["root"] != second["references"][0]["root"]
    assert Path(first["references"][0]["root"]).is_dir()
    assert Path(second["references"][0]["root"]).is_dir()


def test_cross_workspace_launch_is_wrapped_in_mount_sandbox(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, spec = _workspace_surface(tmp_path)
    plan = _plan(target, canon, workspace_access=[json.dumps(spec)])
    assert plan["verdict"] == "LAUNCH_READY", plan
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    captured: list[list[str]] = []
    real_run = subprocess.run

    def child(args, **kwargs):
        if args[0] == "git":
            return real_run(args, **kwargs)
        captured.append(list(args))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(launcher_mod.subprocess, "run", child)
    assert launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high") == 0
    assert len(captured) == 1
    argv = captured[0]
    assert argv[0] == sys.executable
    assert argv[1].endswith("tools/foundry/fs_sandbox.py")
    assert "--allow-write" in argv
    assert str(target["wt"]) in argv
    assert spec["root"] in argv
    assert "--" in argv


def test_bubblewrap_command_uses_read_only_root_and_explicit_writable_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(fs_sandbox_mod.shutil, "which", lambda name: "/usr/bin/bwrap")
    argv = fs_sandbox_mod.build_bwrap_argv(["child", "--flag"], [str(allowed)])
    assert argv[:7] == [
        "/usr/bin/bwrap",
        "--die-with-parent",
        "--new-session",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
    ]
    assert ["--bind", str(allowed), str(allowed)] == argv[-6:-3]
    assert argv[-3:] == ["--", "child", "--flag"]


@pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("bwrap") is None,
    reason="Bubblewrap runtime unavailable",
)
def test_bubblewrap_wrapper_blocks_content_and_metadata_outside_scope(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    blocked_file = blocked / "protected.txt"
    blocked_file.write_text("protected", encoding="utf-8")
    original_mode = blocked_file.stat().st_mode & 0o777
    wrapper = TOOLS / "fs_sandbox.py"
    code = (
        "import os; from pathlib import Path; "
        f"Path({str(allowed / 'ok.txt')!r}).write_text('ok'); "
        "content_blocked=False; metadata_blocked=False; "
        f"\ntry:\n Path({str(blocked / 'no.txt')!r}).write_text('no')\n"
        "except OSError:\n content_blocked=True\n"
        f"\ntry:\n os.chmod({str(blocked_file)!r}, 0)\n"
        "except OSError:\n metadata_blocked=True\n"
        "raise SystemExit(0 if content_blocked and metadata_blocked else 9)"
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(wrapper),
            "--allow-write",
            str(allowed),
            "--",
            sys.executable,
            "-c",
            code,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (allowed / "ok.txt").read_text(encoding="utf-8") == "ok"
    assert not (blocked / "no.txt").exists()
    assert (blocked_file.stat().st_mode & 0o777) == original_mode


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
