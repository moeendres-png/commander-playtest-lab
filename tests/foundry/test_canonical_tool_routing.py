"""WS196 canonical cross-repo tool routing regression tests.

Defect under test: a cross-repository Forge/XMage workstream can be launched
correctly through Foundry yet cannot deterministically locate canonical
control-plane tooling such as ``tools/foundry/safe_push.py``. The child
session (CWD inside the engine checkout) receives no machine-readable
canonical tool identity, so model-driven discovery hits external-directory
boundaries or wrongly assumes ``tools/foundry/*`` exists in the engine repo.

Required systemic result (all hermetic: fake canonical CPL root plus fake
CPL/Forge/XMage worktree repos, real git subprocesses):

- CPL-native, Forge and XMage launches expose the exact canonical
  ``FOUNDRY_CANONICAL_ROOT`` / ``FOUNDRY_SAFE_PUSH`` identity in both the
  child environment and ``launch-context.json`` (no globbing, no sibling
  discovery required).
- A canonical root without ``tools/foundry/safe_push.py`` fails closed
  (LAUNCH_REFUSED) before any model-driven discovery.
- Permissions stay narrow: no broad ``external_directory`` allow is added,
  ``git push*`` stays deny, sibling denies still hold.
- ``safe_push.py`` gates, TUI/headless parity, the canonical Go default and
  the explicit Zen override are preserved.
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

sys.path.insert(0, str(ROOT / "tools"))

from foundry import launcher as launcher_mod  # noqa: E402
from foundry import opencode_cli_version as version_mod  # noqa: E402
from foundry import permission_battery as battery_mod  # noqa: E402
from foundry import safe_push as safe_push_mod  # noqa: E402

CPL_SLUG = "moeendres-png/commander-playtest-lab"
FORGE_SLUG = "moeendres-png/forge"
MAGE_SLUG = "moeendres-png/mage"

SLUG_BY_PROFILE = {"cpl": CPL_SLUG, "forge": FORGE_SLUG, "mage": MAGE_SLUG}


@pytest.fixture(autouse=True)
def _hermetic_opencode_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Route binary resolution at a hermetic stub reporting the qualified version."""
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
    """Canonical CPL root carrying policy files AND control-plane tooling."""
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
    tools_dir = root / "tools" / "foundry"
    tools_dir.mkdir(parents=True)
    (tools_dir / "safe_push.py").write_text(
        "#!/usr/bin/env python3\n# canonical safe-push stub for routing tests\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def canon_naked(tmp_path: Path, canon: Path) -> Path:
    """Canonical-appearing root whose control-plane tooling is absent."""
    import shutil

    naked = tmp_path / "canon-naked"
    shutil.copytree(canon, naked, ignore=shutil.ignore_patterns("tools"))
    return naked


def _make_worktree(
    tmp_path: Path, name: str, slug: str, branch: str, workstream: str
) -> dict:
    wt = tmp_path / name
    wt.mkdir()
    env = _env()
    _git(["init", "-b", "main"], wt, env)
    _git(["config", "remote.origin.url", f"https://github.com/{slug}.git"], wt, env)
    (wt / "code.txt").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "init"], wt, env)
    base = _git(["rev-parse", "HEAD"], wt, env)
    _git(["checkout", "-b", branch], wt, env)
    state = {
        "schema_version": "2.0",
        "repository": slug,
        "worktree": str(wt),
        "branch": branch,
        "audit_base_sha": base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": base,
        "validated_head": base,
        "objective": "test objective",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": workstream,
        "status": "ACTIVE",
        "exact_next_action": "go",
    }
    state_path = wt / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    return {"wt": wt, "env": env, "state": state_path, "base": base}


@pytest.fixture()
def cpl_target(tmp_path: Path) -> dict:
    return _make_worktree(tmp_path, "cpl-wt", CPL_SLUG, "project/test", "TEST-WS")


@pytest.fixture()
def forge_target(tmp_path: Path) -> dict:
    return _make_worktree(tmp_path, "forge-wt", FORGE_SLUG, "engine/work", "TEST-FORGE")


@pytest.fixture()
def mage_target(tmp_path: Path) -> dict:
    return _make_worktree(tmp_path, "mage-wt", MAGE_SLUG, "engine/work", "TEST-MAGE")


def _plan(
    target: dict, canon: Path, profile: str, workstream: str, **over: object
) -> dict:
    kwargs: dict = {
        "profile": profile,
        "worktree": str(target["wt"]),
        "workstream": workstream,
        "branch": "engine/work" if profile in ("forge", "mage") else "project/test",
        "audit_base_sha": target["base"],
        "effort": "high",
        "mode": "writer",
        "session": "ses-t",
        "state_path": str(target["state"]),
        "canonical_root": str(canon),
        "allow_same_cwd_pids": False,
        "allow_suppressed_routing": False,
        "install_pre_push_hook": False,
        "run_dir": str(target["wt"].parent / f"rundir-{profile}"),
    }
    kwargs.update(over)
    return launcher_mod.init(**kwargs)


def _assert_canonical_identity(plan: dict, canon: Path, target: dict) -> None:
    """Deterministic identity: exact paths in env AND context, file exists."""
    assert plan["verdict"] == "LAUNCH_READY", plan
    env = plan["_env"]
    want_root = os.path.realpath(str(canon))
    want_push = os.path.join(want_root, "tools", "foundry", "safe_push.py")
    assert env["FOUNDRY_CANONICAL_ROOT"] == want_root
    assert env["FOUNDRY_SAFE_PUSH"] == want_push
    assert os.path.isfile(want_push), "canonical tool identity must name a real file"
    assert plan["canonical_root"] == want_root
    assert plan["canonical_safe_push"] == want_push
    context = json.loads(Path(plan["context_path"]).read_text(encoding="utf-8"))
    assert context["canonical_root"] == want_root
    assert context["canonical_safe_push"] == want_push
    assert "FOUNDRY_CANONICAL_ROOT" in plan["env_keys"]
    assert "FOUNDRY_SAFE_PUSH" in plan["env_keys"]


# --- CPL / Forge / XMage resolution -------------------------------------------


def test_cpl_native_resolves_canonical_safe_push(cpl_target: dict, canon: Path) -> None:
    plan = _plan(cpl_target, canon, "cpl", "TEST-WS")
    _assert_canonical_identity(plan, canon, cpl_target)


def test_forge_cross_repo_resolves_canonical_safe_push(
    forge_target: dict, canon: Path
) -> None:
    """Engine CWD, CPL canonical root: safe_push resolves without discovery."""
    assert os.path.realpath(str(forge_target["wt"])) != os.path.realpath(str(canon))
    plan = _plan(forge_target, canon, "forge", "TEST-FORGE")
    _assert_canonical_identity(plan, canon, forge_target)
    assert plan["_env"]["FOUNDRY_WORKTREE"] != plan["_env"]["FOUNDRY_CANONICAL_ROOT"]


def test_xmage_cross_repo_resolves_canonical_safe_push(
    mage_target: dict, canon: Path
) -> None:
    assert os.path.realpath(str(mage_target["wt"])) != os.path.realpath(str(canon))
    plan = _plan(mage_target, canon, "mage", "TEST-MAGE")
    _assert_canonical_identity(plan, canon, mage_target)
    assert plan["_env"]["FOUNDRY_WORKTREE"] != plan["_env"]["FOUNDRY_CANONICAL_ROOT"]


def test_no_filesystem_discovery_required(
    cpl_target: dict, forge_target: dict, mage_target: dict, canon: Path
) -> None:
    """The identity is exact and self-sufficient: absolute, existent, joined
    from the canonical root by construction (never globbed or searched)."""
    for target, profile, workstream in (
        (cpl_target, "cpl", "TEST-WS"),
        (forge_target, "forge", "TEST-FORGE"),
        (mage_target, "mage", "TEST-MAGE"),
    ):
        plan = _plan(target, canon, profile, workstream)
        assert plan["verdict"] == "LAUNCH_READY", plan
        env = plan["_env"]
        assert os.path.isabs(env["FOUNDRY_SAFE_PUSH"])
        assert env["FOUNDRY_SAFE_PUSH"] == os.path.join(
            env["FOUNDRY_CANONICAL_ROOT"], "tools", "foundry", "safe_push.py"
        )
        assert os.path.isfile(env["FOUNDRY_SAFE_PUSH"])


# --- resolver unit --------------------------------------------------------------


def test_resolve_canonical_tools_unit(canon: Path, tmp_path: Path) -> None:
    resolved = launcher_mod.resolve_canonical_tools(str(canon))
    assert resolved["canonical_root"] == os.path.realpath(str(canon))
    assert resolved["safe_push"] == os.path.join(
        resolved["canonical_root"], "tools", "foundry", "safe_push.py"
    )
    with pytest.raises(ValueError, match="safe_push"):
        launcher_mod.resolve_canonical_tools(str(tmp_path / "absent-root"))
    with pytest.raises(ValueError, match="canonical root"):
        launcher_mod.resolve_canonical_tools("")
    not_a_file = tmp_path / "not-a-file"
    not_a_file.mkdir()
    with pytest.raises(ValueError, match="safe_push"):
        launcher_mod.resolve_canonical_tools(str(not_a_file))


# --- missing tool fails closed ----------------------------------------------------


@pytest.mark.parametrize("profile", ["cpl", "forge", "mage"])
def test_missing_canonical_tool_fails_closed(
    profile: str,
    cpl_target: dict,
    forge_target: dict,
    mage_target: dict,
    canon_naked: Path,
) -> None:
    """Absent control-plane tooling refuses launch before model discovery."""
    target = {"cpl": cpl_target, "forge": forge_target, "mage": mage_target}[profile]
    workstream = {"cpl": "TEST-WS", "forge": "TEST-FORGE", "mage": "TEST-MAGE"}[profile]
    plan = _plan(target, canon_naked, profile, workstream)
    assert plan["verdict"] == "LAUNCH_REFUSED"
    assert "safe_push" in str(plan.get("error", "")).lower()
    assert "_env" not in plan, "refused plans must not publish an environment"


# --- narrow permissions -------------------------------------------------------------


def _ext_rules(bundle: dict) -> list[dict]:
    return [
        {"permission": "external_directory", "pattern": pattern, "action": action}
        for pattern, action in bundle["permission"]["external_directory"].items()
    ]


def test_narrow_permission_no_broad_allow(forge_target: dict, canon: Path) -> None:
    """Only the pre-existing narrow allows survive; git push stays deny."""
    _git(
        ["worktree", "add", str(forge_target["wt"].parent / "sib"), "-b", "engine/sib"],
        forge_target["wt"],
        forge_target["env"],
    )
    plan = _plan(forge_target, canon, "forge", "TEST-FORGE")
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    assert bundle["permission"]["bash"]["git push*"] == "deny"
    static_ext = json.loads((canon / "opencode.json").read_text(encoding="utf-8"))[
        "permission"
    ]["external_directory"]
    static_allows = {k for k, v in static_ext.items() if v == "allow"}
    bundle_allows = {
        k for k, v in bundle["permission"]["external_directory"].items() if v == "allow"
    }
    assert bundle_allows == static_allows, "no broad external allow may be injected"
    assert "/tmp/*" in bundle_allows
    sib_deny = f"{forge_target['wt'].parent / 'sib'}*"
    assert bundle["permission"]["external_directory"].get(sib_deny) == "deny"
    rules = _ext_rules(bundle)
    # Production-shaped probe: a canonical checkout outside /tmp must NOT be
    # allow-listed (the hermetic FOUNDRY_SAFE_PUSH itself lives under /tmp,
    # where the pre-existing narrow /tmp/* allow legitimately applies).
    verdict, _ = battery_mod.evaluate_rule(
        rules,
        "external_directory",
        "/home/moeen/code/cpl-checkout/tools/foundry/safe_push.py",
    )
    assert verdict != "ENFORCED_ALLOW", "canonical tools stay narrow (no allow entry)"
    verdict, _ = battery_mod.evaluate_rule(rules, "external_directory", sib_deny[:-1])
    assert verdict == "DENIED"
    verdict, _ = battery_mod.evaluate_rule(rules, "external_directory", "/tmp/scratch")
    assert verdict == "ENFORCED_ALLOW"


def test_direct_git_push_stays_denied_in_cross_repo_bundle(
    mage_target: dict, canon: Path
) -> None:
    plan = _plan(mage_target, canon, "mage", "TEST-MAGE")
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    assert bundle["permission"]["bash"]["git push*"] == "deny"


# --- safe_push gates preserved ----------------------------------------------------------


def test_safe_push_gates_preserved(tmp_path: Path) -> None:
    """Gate functions intact: protected refs refused; narrow API unchanged."""
    assert {"main", "master", "HEAD"} <= safe_push_mod.PROTECTED_BRANCHES
    assert safe_push_mod._valid_branch_name("main", str(tmp_path)) is not None
    assert safe_push_mod._valid_branch_name("evil --force", str(tmp_path)) is not None
    assert (ROOT / "tools" / "foundry" / "safe_push.py").is_file()


# --- TUI / headless parity ------------------------------------------------------------------


def test_tui_headless_parity(forge_target: dict, canon: Path) -> None:
    headless = _plan(forge_target, canon, "forge", "TEST-FORGE", ui_mode="headless")
    tui = _plan(
        forge_target,
        canon,
        "forge",
        "TEST-FORGE",
        ui_mode="tui",
        run_dir=str(forge_target["wt"].parent / "rundir-forge-tui"),
    )
    assert headless["verdict"] == "LAUNCH_READY", headless
    assert tui["verdict"] == "LAUNCH_READY", tui
    for key in ("FOUNDRY_CANONICAL_ROOT", "FOUNDRY_SAFE_PUSH", "FOUNDRY_STATE_PATH"):
        assert headless["_env"][key] == tui["_env"][key]
    assert headless["ui_mode"] == "headless"
    assert tui["ui_mode"] == "tui"
    assert launcher_mod.build_argv("opencode", "headless", ["x"])[1] == "run"
    assert "run" not in launcher_mod.build_argv("opencode", "tui", ["x"])


# --- provider posture preserved -----------------------------------------------------------------


def test_canonical_go_default_and_zen_override_preserved(
    forge_target: dict, canon: Path
) -> None:
    plan = _plan(forge_target, canon, "forge", "TEST-FORGE")
    assert plan["verdict"] == "LAUNCH_READY", plan
    bundle = json.loads(plan["_env"]["OPENCODE_CONFIG_CONTENT"])
    assert bundle["model"] == launcher_mod.CANONICAL_MODEL
    assert bundle["enabled_providers"] == ["opencode-go"]
    zen = _plan(forge_target, canon, "forge", "TEST-FORGE", execution_provider="zen")
    assert zen["verdict"] == "LAUNCH_READY", zen
    zen_bundle = json.loads(zen["_env"]["OPENCODE_CONFIG_CONTENT"])
    assert zen_bundle["model"] == launcher_mod.ZEN_MODEL
    assert zen_bundle["enabled_providers"] == ["opencode"]
    assert zen["_env"]["FOUNDRY_SAFE_PUSH"] == plan["_env"]["FOUNDRY_SAFE_PUSH"]
    assert zen["execution"]["override"] == "zen"
    assert plan["execution"]["override"] == "canonical"


# --- agent instruction ------------------------------------------------------------------------------


def test_implementer_documents_canonical_routing() -> None:
    text = (ROOT / ".opencode" / "agents" / "foundry-implementer.md").read_text(
        encoding="utf-8"
    )
    assert "FOUNDRY_CANONICAL_ROOT" in text
    assert "FOUNDRY_SAFE_PUSH" in text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
