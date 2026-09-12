"""WS75 Foundry/OpenCode tooling-hardening regression tests.

Covers the ten required remediations against hermetic fixtures (fake
canonical root + fake repos) plus real subprocesses, real flock locks,
and real file-remotes:

- HEADLESS_RUN_COMPAT (exact ``run --auto`` order) + TUI form preserved;
- TELEMETRY_OUT_OF_WORKTREE (run_dir location, parent auto-created,
  launcher leaves the Git tree clean);
- STATE_PATH_CONTEXT (exact state path + worktree/branch/workstream/
  run-dir/mode/effort exposed, no secrets);
- REFERENCE_ROOT contract (exact slug/HEAD/tree, mismatch fail closed,
  mutation detection, bootstrap + launcher wiring);
- TOOL_PERMISSION_BATTERY (git push / git -C / sibling denies,
  doom_loop deny, no broad /home/moeen/code write);
- OPENCODE_1_18_30_PIN (exact pin passes, drift/unparseable fail closed,
  bounded audit mode);
- SAFE_PUSH_REGRESSION (sole remote-write path under ancestor-held lock).
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
from foundry import metrics as metrics_mod  # noqa: E402
from foundry import opencode_cli_version as version_mod  # noqa: E402
from foundry import permission_battery as battery_mod  # noqa: E402
from foundry import reference_roots as reference_mod  # noqa: E402

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
    root = tmp_path / "canon"
    (root / ".opencode" / "agents").mkdir(parents=True)
    (root / ".opencode" / "skills").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    (root / ".opencode" / "agents" / "foundry-implementer.md").write_text(
        "---\nvariant: high\n---\n", encoding="utf-8"
    )
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
    rundir = tmp_path / "rundir"
    return {
        "wt": wt,
        "locks": locks,
        "env": env,
        "state": state_path,
        "base": base,
        "rundir": rundir,
    }


def _version_stub(tmp_path: Path, version: str = "1.18.30", exit_code: int = 0) -> Path:
    """Fake `opencode` binary: answers --version, records all other argv."""
    stub = tmp_path / "fake-opencode-bin"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        + (f"    print({version!r})\n" if version is not None else "    sys.exit(3)\n")
        + f"    sys.exit(0)\n"
        "record = os.environ.get('STUB_ARGV_FILE')\n"
        "if record:\n"
        "    open(record, 'a').write(' '.join(sys.argv) + chr(10))\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


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
        "run_dir": str(target["rundir"]),
        # WS75: pin the PATH binary explicitly so a stale FOUNDRY_OPENCODE_BIN
        # wrapper in the ambient environment cannot leak into hermetic tests.
        "opencode_bin": "opencode",
    }
    kwargs.update(over)
    return launcher_mod.init(**kwargs)


# --- 1. HEADLESS_RUN_COMPAT + TUI -------------------------------------------


def test_build_argv_headless_exact_order() -> None:
    argv = launcher_mod.build_argv("opencode", "headless", ["hello", "--model", "x"])
    assert argv == ["opencode", "run", "--auto", "hello", "--model", "x"]
    assert argv.index("run") == 1
    assert argv.index("--auto") == 2


def test_build_argv_tui_form_preserved() -> None:
    argv = launcher_mod.build_argv("opencode", "tui", ["hello"])
    assert argv == ["opencode", "--auto", "hello"]
    assert "run" not in argv


def test_build_argv_unknown_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="ui_mode"):
        launcher_mod.build_argv("opencode", "serve", [])


def test_headless_launch_execs_run_auto_first(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "argv.log"
    monkeypatch.setenv("STUB_ARGV_FILE", str(record))
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    stub = _version_stub(tmp_path, exit_code=7)
    plan = _plan(target, canon, ui_mode="headless", opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    rc = launcher_mod.launch(plan, ["do the thing"], str(target["wt"]), "TEST-WS", "high")
    assert rc == 7
    lines = record.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parts = lines[0].split(" ")
    assert parts[1] == "run"
    assert parts[2] == "--auto"
    assert parts[3:] == ["do", "the", "thing"]


def test_tui_launch_execs_without_run(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "argv-tui.log"
    monkeypatch.setenv("STUB_ARGV_FILE", str(record))
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    stub = _version_stub(tmp_path, exit_code=7)
    plan = _plan(target, canon, ui_mode="tui", opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    rc = launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high")
    assert rc == 7
    parts = record.read_text(encoding="utf-8").strip().split(" ")
    assert parts[1] == "--auto"
    assert "run" not in parts[1:]


# --- 2. TELEMETRY_OUT_OF_WORKTREE --------------------------------------------


def test_metrics_record_creates_missing_parent(tmp_path: Path) -> None:
    deep = tmp_path / "nope" / "nested" / "metrics.jsonl"
    entry = metrics_mod.record(str(deep), task_id="T", completed=True)
    assert entry["task_id"] == "T"
    assert deep.is_file()


def test_telemetry_under_run_dir_and_tree_stays_clean(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Checkpoint-commit the state file first, as the real flow does before
    # launch; the launcher itself must add nothing to the worktree.
    _git(["add", "."], target["wt"], target["env"])
    _git(["commit", "-m", "checkpoint"], target["wt"], target["env"])
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    stub = _version_stub(tmp_path, exit_code=0)
    plan = _plan(target, canon, ui_mode="headless", opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    rc = launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high")
    assert rc == 0
    metrics_file = Path(plan["run_dir"]) / "metrics.jsonl"
    assert metrics_file.is_file()
    records = [json.loads(line) for line in metrics_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["task_id"] == "TEST-WS"
    assert records[1]["completed"] is True
    # No telemetry inside the worktree, and the tree is clean.
    assert not (target["wt"] / ".foundry" / "metrics.jsonl").exists()
    porcelain = _git(["status", "--porcelain"], target["wt"], target["env"])
    assert porcelain == "", porcelain


# --- 3. STATE_PATH_CONTEXT ----------------------------------------------------


def test_state_path_context_exposed_without_secrets(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    stub = _version_stub(tmp_path)
    plan = _plan(target, canon, opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    env = plan["_env"]
    assert env["FOUNDRY_STATE_PATH"] == str(target["state"])
    assert env["FOUNDRY_WORKTREE"] == os.path.realpath(str(target["wt"]))
    assert env["FOUNDRY_BRANCH"] == "project/test"
    assert env["FOUNDRY_WORKSTREAM"] == "TEST-WS"
    assert env["FOUNDRY_RUN_DIR"] == str(target["rundir"])
    assert env["FOUNDRY_MODE"] == "writer"
    assert env["FOUNDRY_EFFORT"] == "high"
    context = json.loads(Path(plan["context_path"]).read_text(encoding="utf-8"))
    assert context["state_path"] == str(target["state"])
    assert context["run_dir"] == str(target["rundir"])
    blob = json.dumps(context).lower()
    for marker in ("apikey", "api_key", "token", "secret", "password", "credential"):
        assert marker not in blob, marker
    assert env["OPENCODE_CONFIG_CONTENT"] not in json.dumps(context)


def test_state_path_defaults_to_worktree_state(target: dict, canon: Path, tmp_path: Path) -> None:
    stub = _version_stub(tmp_path)
    plan = _plan(target, canon, state_path=None, opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["_env"]["FOUNDRY_STATE_PATH"].endswith(".foundry/WORKSTREAM_STATE.yaml")


def test_implementer_reads_exact_state_path() -> None:
    text = (ROOT / ".opencode" / "agents" / "foundry-implementer.md").read_text(encoding="utf-8")
    assert "FOUNDRY_STATE_PATH" in text
    assert "FOUNDRY_RUN_DIR" in text
    assert "FOUNDRY_REFERENCE_ROOTS" in text
    assert "never retry an identical denied command" in text.lower()
    assert (
        "never use `git -C`" in text or "never use ``git -C``" in text or "Never `git -C`" in text
    )


# --- 4. REFERENCE_ROOT contract ------------------------------------------------


@pytest.fixture()
def refrepo(tmp_path: Path) -> dict:
    repo = tmp_path / "forge-checkout"
    repo.mkdir()
    env = _env()
    _git(["init", "-b", "master"], repo, env)
    _git(["config", "remote.origin.url", "https://github.com/Card-Forge/forge.git"], repo, env)
    (repo / ".gitignore").write_text("*.out\n", encoding="utf-8")
    (repo / "engine.txt").write_text("engine\n", encoding="utf-8")
    _git(["add", "."], repo, env)
    _git(["commit", "-m", "forge pin"], repo, env)
    head = _git(["rev-parse", "HEAD"], repo, env)
    tree = _git(["rev-parse", "HEAD^{tree}"], repo, env)
    return {"root": repo, "env": env, "head": head, "tree": tree}


def _spec(refrepo: dict, **over: object) -> dict:
    spec = {
        "label": "forge",
        "root": str(refrepo["root"]),
        "repo_slug": "Card-Forge/forge",
        "commit": refrepo["head"],
        "tree": refrepo["tree"],
        "cleanliness": "clean",
        "intent": "read-only",
    }
    spec.update(over)
    return spec


def test_reference_verify_exact_pass(refrepo: dict) -> None:
    assert reference_mod.verify(_spec(refrepo)) == []


def test_reference_slug_mismatch_fails_closed(refrepo: dict) -> None:
    reasons = reference_mod.verify(_spec(refrepo, repo_slug="someone-else/forge"))
    assert any("slug" in r for r in reasons)


def test_reference_commit_mismatch_fails_closed(refrepo: dict) -> None:
    reasons = reference_mod.verify(_spec(refrepo, commit="0" * 40))
    assert any("HEAD" in r for r in reasons)


def test_reference_tree_mismatch_fails_closed(refrepo: dict) -> None:
    reasons = reference_mod.verify(_spec(refrepo, tree="f" * 40))
    assert any("tree" in r for r in reasons)


def test_reference_mutation_detected(refrepo: dict) -> None:
    (refrepo["root"] / "engine.txt").write_text("tampered\n", encoding="utf-8")
    reasons = reference_mod.verify(_spec(refrepo))
    assert any("dirty" in r for r in reasons)


def test_reference_strict_clean_rejects_ignored_residue(refrepo: dict) -> None:
    (refrepo["root"] / "build.out").write_text("output\n", encoding="utf-8")
    strict = reference_mod.verify(_spec(refrepo, cleanliness="clean"))
    assert any("ignored" in r for r in strict)
    allowed = reference_mod.verify(_spec(refrepo, cleanliness="allow-ignored-build-outputs"))
    assert allowed == []


def test_reference_malformed_spec_rejected(refrepo: dict) -> None:
    good = _spec(refrepo)
    bad_missing = dict(good)
    del bad_missing["tree"]
    with pytest.raises(reference_mod.ReferenceError):
        reference_mod.parse_spec(json.dumps(bad_missing))
    with pytest.raises(reference_mod.ReferenceError):
        reference_mod.parse_spec(json.dumps({**good, "root": "relative/path"}))
    with pytest.raises(reference_mod.ReferenceError):
        reference_mod.parse_spec(json.dumps({**good, "commit": "xyz"}))
    with pytest.raises(reference_mod.ReferenceError):
        reference_mod.parse_spec(json.dumps({**good, "intent": "read-write"}))
    with pytest.raises(reference_mod.ReferenceError):
        reference_mod.parse_spec("not json{")


def test_bootstrap_rejects_mismatched_reference(target: dict, canon: Path, refrepo: dict) -> None:
    bad = _spec(refrepo, commit="0" * 40)
    result = bootstrap_mod.bootstrap(
        str(target["wt"]),
        "TEST-WS",
        "project/test",
        target["base"],
        str(target["state"]),
        "cpl",
        str(ROOT / ".foundry" / "repo-profiles"),
        str(canon),
        references=[bad],
    )
    assert result["verdict"] == "BOOTSTRAP_FAIL"
    assert any("reference" in f for f in result["failures"])


def test_launcher_exposes_verified_references(
    target: dict, canon: Path, refrepo: dict, tmp_path: Path
) -> None:
    stub = _version_stub(tmp_path)
    plan = _plan(target, canon, references=[json.dumps(_spec(refrepo))], opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    exposed = json.loads(plan["_env"]["FOUNDRY_REFERENCE_ROOTS"])
    assert exposed[0]["label"] == "forge"
    assert exposed[0]["root"] == str(refrepo["root"])
    assert "reference" in plan["gate"]["notes"][-1].lower() or any(
        "reference" in n.lower() for n in plan["gate"]["notes"]
    )


def test_launcher_refuses_mismatched_reference(
    target: dict, canon: Path, refrepo: dict, tmp_path: Path
) -> None:
    stub = _version_stub(tmp_path)
    plan = _plan(
        target,
        canon,
        references=[json.dumps(_spec(refrepo, commit="0" * 40))],
        opencode_bin=str(stub),
    )
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert any(
        "reference" in str(plan.get("error", "")).lower() or "reference" in f
        for f in plan.get("gate", {}).get("failures", [])
    )


# --- 5/9. TOOL_PERMISSION_BATTERY + SAFE_PUSH regression ------------------------


def _config_bash_rules() -> list[dict]:
    perm = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))["permission"]
    return [
        {"permission": "bash", "pattern": pattern, "action": action}
        for pattern, action in perm["bash"].items()
    ]


def _config_ext_rules() -> list[dict]:
    perm = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))["permission"]
    return [
        {"permission": "external_directory", "pattern": pattern, "action": action}
        for pattern, action in perm["external_directory"].items()
    ]


def test_doom_loop_deny() -> None:
    config = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert config["permission"]["doom_loop"] == "deny"


def test_direct_git_push_denied() -> None:
    rules = _config_bash_rules()
    for cmd in ("git push origin test/ws", "git push --force origin test/ws", "git push"):
        verdict, matched = battery_mod.evaluate_rule(rules, "bash", cmd)
        assert verdict == "DENIED", (cmd, matched)


def test_git_C_remains_denied() -> None:
    rules = _config_bash_rules()
    for cmd in ("git -C /tmp/wt status", "git -C /tmp/wt push origin x"):
        verdict, matched = battery_mod.evaluate_rule(rules, "bash", cmd)
        assert verdict == "DENIED", (cmd, matched)


def test_no_broad_home_code_write_access() -> None:
    rules = _config_ext_rules()
    for probe in (
        "/home/moeen/code/ws75-foundry-opencode-tooling-hardening/tools/foundry/launcher.py",
        "/home/moeen/code/some-other-checkout/file.txt",
    ):
        verdict, matched = battery_mod.evaluate_rule(rules, "external_directory", probe)
        assert verdict != "ENFORCED_ALLOW", (probe, matched)


def test_sibling_worktree_denied_in_bundle(target: dict, canon: Path, tmp_path: Path) -> None:
    _git(
        ["worktree", "add", str(target["wt"].parent / "sib"), "-b", "project/sib"],
        target["wt"],
        target["env"],
    )
    stub = _version_stub(tmp_path)
    plan = _plan(target, canon, opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    sib_deny = f"{target['wt'].parent / 'sib'}*"
    assert bundle["permission"]["external_directory"].get(sib_deny) == "deny"


def test_safe_push_succeeds_under_ancestor_lock(tmp_path: Path) -> None:
    locks = tmp_path / "locks"
    locks.mkdir()
    env = _env()
    env["HOME"] = "/nonexistent-fake-home"
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
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "checkpoint"], wt, env)
    lock_env = dict(env)
    lock_env["FOUNDRY_LOCK_DIR"] = str(locks)
    lock_env["PYTHONPATH"] = str(ROOT / "tools")
    driver = (
        "import subprocess, sys; "
        "from foundry import writer_lock; "
        "lock = writer_lock.WriterLock(sys.argv[1], 'TEST-WORKSTREAM', 'test/ws', 'ses-t'); "
        "lock.acquire(); "
        f"p = subprocess.run([sys.executable, {str(TOOLS / 'safe_push.py')!r}, "
        "'--worktree', sys.argv[1], '--expected-branch', 'test/ws', "
        "'--state', sys.argv[2], '--expected-slug', 'test-host/fixture-repo'], "
        "capture_output=True, text=True); "
        "sys.stdout.write(p.stdout); sys.stderr.write(p.stderr); "
        "lock.release(); sys.exit(p.returncode)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver, str(wt), str(state_path)],
        capture_output=True,
        text=True,
        timeout=60,
        env=lock_env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "PUSHED" in proc.stdout


# --- 6. OPENCODE_1_18_30_PIN -----------------------------------------------------


def test_qualified_version_is_1_18_30() -> None:
    assert version_mod.QUALIFIED_OPENCODE_VERSION == "1.18.30"
    assert version_mod.ASSETS["linux-x64"]["verified"] is True
    assert version_mod.ASSETS["linux-arm64"]["verified"] is True


def test_installed_cli_reports_qualified_version() -> None:
    assert version_mod.installed_version("opencode") == "1.18.30"


def test_version_mismatch_fails_closed(target: dict, canon: Path, tmp_path: Path) -> None:
    stub = _version_stub(tmp_path, version="9.9.9")
    plan = _plan(target, canon, opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "version drift" in str(plan.get("error", ""))


def test_version_unparseable_fails_closed(target: dict, canon: Path, tmp_path: Path) -> None:
    stub = _version_stub(tmp_path, version=None, exit_code=0)
    plan = _plan(target, canon, opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "opencode version" in str(plan.get("error", ""))


def test_version_audit_mode_is_bounded_and_recorded(
    target: dict, canon: Path, tmp_path: Path
) -> None:
    stub = _version_stub(tmp_path, version="9.9.9")
    plan = _plan(target, canon, opencode_bin=str(stub), version_audit_mode=True)
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["version_audit_mode"] is True
    assert plan["opencode_version"]["installed"] == "9.9.9"
    assert any("audit mode" in n for n in plan["notes"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
