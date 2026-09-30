"""B5: a credited Forge execution must bind an explicit, validated workspace.

The runner defaulted ``FORGE_WORKSPACE`` to one machine-local historical checkout
(``/home/moeen/code/ws-forge-full107-cdq-20260926``) whose Rules-Core modules match
the recorded candidate but whose ``forge-protocol2-bridge`` tree differs from the
intended bridge/evidence head. A run on that default would credit a suite executed
by a bridge the evidence identity does not name. These tests pin the fail-closed
contract: explicit selection, checkout identity, Rules-Core equivalence, and
separate bridge/evidence binding.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import receipts as receipt_mod

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"
AMBIENT_DEFAULT = "/home/moeen/code/ws-forge-full107-cdq-20260926"


def _git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)
    return _git(["rev-parse", "HEAD"], repo)


def _write_forge_module(repo: Path, module: str, payload: str) -> None:
    path = repo / module / "src" / "main" / "java" / "Main.java"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def make_forge_repo(tmp_path: Path) -> dict[str, str]:
    """A minimal Forge-shaped repository with divergent commit histories.

    c0  baseline: every Rules-Core module and the bridge module at one identity
    c1  bridge-only change on top of c0
    c2  neutral change on top of c0 (no engine or bridge source touched)
    c3  Rules-Core change on top of c0
    """
    repo = tmp_path / "forge"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "config", "user.email", "b5@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "B5 Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    for module in receipt_mod.FORGE_RULES_CORE_MODULE_ROOTS:
        _write_forge_module(repo, module, f"// {module} v1\n")
    _write_forge_module(repo, "forge-protocol2-bridge", "// bridge v1\n")
    base = _commit(repo, "baseline")

    subprocess.run(["git", "checkout", "-q", "-b", "bridge-change"], cwd=repo, check=True)
    _write_forge_module(repo, "forge-protocol2-bridge", "// bridge v2\n")
    bridge = _commit(repo, "bridge change")

    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "neutral-change"], cwd=repo, check=True)
    (repo / "README.md").write_text("docs only\n", encoding="utf-8")
    neutral = _commit(repo, "docs change")

    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "rules-change"], cwd=repo, check=True)
    _write_forge_module(repo, "forge-game", "// forge-game v2 Rules Core change\n")
    rules = _commit(repo, "rules change")

    subprocess.run(["git", "checkout", "-q", base], cwd=repo, check=True)
    return {
        "repo": str(repo),
        "base": base,
        "bridge": bridge,
        "neutral": neutral,
        "rules": rules,
        "base_tree": _git(["rev-parse", f"{base}^{{tree}}"], repo),
    }


def _checkout(repo: Path, ref: str) -> None:
    subprocess.run(["git", "checkout", "-q", ref], cwd=repo, check=True)


def runner_module(monkeypatch: pytest.MonkeyPatch, *, forge_workspace: str | None = None):
    if forge_workspace is None:
        monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    else:
        monkeypatch.setenv("FORGE_WORKSPACE", forge_workspace)
    spec = importlib.util.spec_from_file_location("current_boundary_runner_b5", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def forge_error(module: object) -> type[BaseException]:
    return getattr(module, "ForgeWorkspaceError", RuntimeError)


def _resolve(module: object, repo: Path, **overrides: object) -> dict:
    expected = {
        "expected_rules_core_commit": overrides.pop("expected_rules_core_commit", None),
        "expected_bridge_commit": overrides.pop("expected_bridge_commit", None),
        "expected_bridge_tree": overrides.pop("expected_bridge_tree", None),
    }
    return module.bind_forge_workspace(repo, **expected)


def test_runner_source_has_no_ambient_workspace_default() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert AMBIENT_DEFAULT not in source, (
        "the runner still carries a machine-local Forge workspace default; a credited "
        "execution must bind an explicitly supplied checkout"
    )
    assert "FORGE_WORKSPACE" in source, "the explicit environment input must stay documented"


def test_forge_workspace_is_required_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    module = runner_module(monkeypatch)
    with pytest.raises(forge_error(module)):
        module.resolve_forge_workspace()


def test_forge_workspace_must_be_its_own_git_worktree_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch)
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(forge_error(module)):
        module.resolve_forge_workspace(plain)
    subdir = tmp_path / "outer"
    fake = make_forge_repo(subdir)
    nested = Path(fake["repo"]) / "forge-game"
    with pytest.raises(forge_error(module)):
        module.resolve_forge_workspace(nested)


def test_bridge_divergence_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = runner_module(monkeypatch)
    fake = make_forge_repo(tmp_path)
    repo = Path(fake["repo"])
    _checkout(repo, fake["bridge"])
    with pytest.raises(forge_error(module), match="BRIDGE_IDENTITY"):
        module.bind_forge_workspace(
            repo,
            expected_rules_core_commit=fake["base"],
            expected_bridge_commit=fake["base"],
            expected_bridge_tree=fake["base_tree"],
        )


def test_rules_core_divergence_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch)
    fake = make_forge_repo(tmp_path)
    repo = Path(fake["repo"])
    _checkout(repo, fake["rules"])
    with pytest.raises(forge_error(module)):
        module.bind_forge_workspace(
            repo,
            expected_rules_core_commit=fake["base"],
            expected_bridge_commit=fake["base"],
            expected_bridge_tree=fake["base_tree"],
        )


def test_neutral_descendant_is_accepted_with_full_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch)
    fake = make_forge_repo(tmp_path)
    repo = Path(fake["repo"])
    _checkout(repo, fake["neutral"])
    proof = module.bind_forge_workspace(
        repo,
        expected_rules_core_commit=fake["base"],
        expected_bridge_commit=fake["base"],
        expected_bridge_tree=fake["base_tree"],
    )
    assert proof["workspace"] == str(repo.resolve())
    assert proof["actual_commit"] == fake["neutral"]
    assert len(proof["actual_tree"]) == 40
    assert proof["rules_core_identity_proof"]["engine_equivalent"] is True
    assert proof["bridge_identity_proof"]["identical"] is True
    assert (
        proof["bridge_identity_proof"]["actual_bridge_module_tree"]
        == (proof["bridge_identity_proof"]["expected_bridge_module_tree"])
    )


def test_exact_bridge_head_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = runner_module(monkeypatch)
    fake = make_forge_repo(tmp_path)
    repo = Path(fake["repo"])
    _checkout(repo, fake["base"])
    proof = module.bind_forge_workspace(
        repo,
        expected_rules_core_commit=fake["base"],
        expected_bridge_commit=fake["base"],
        expected_bridge_tree=fake["base_tree"],
    )
    assert proof["rules_core_identity_proof"]["justification"] == "EXACT_COMMIT"
    assert proof["bridge_identity_proof"]["justification"] == "EXACT_BRIDGE_COMMIT"


def test_recorded_bridge_tree_must_match_the_recorded_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch)
    fake = make_forge_repo(tmp_path)
    repo = Path(fake["repo"])
    _checkout(repo, fake["base"])
    with pytest.raises(forge_error(module), match="BRIDGE_IDENTITY"):
        module.bind_forge_workspace(
            repo,
            expected_rules_core_commit=fake["base"],
            expected_bridge_commit=fake["base"],
            expected_bridge_tree="f" * 40,
        )


def test_dirty_workspace_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Committed identity trees cannot describe uncommitted executing bytes."""
    module = runner_module(monkeypatch)
    fake = make_forge_repo(tmp_path)
    repo = Path(fake["repo"])
    _checkout(repo, fake["base"])
    _write_forge_module(repo, "forge-game", "// uncommitted Rules-Core edit\n")
    with pytest.raises(forge_error(module), match="uncommitted changes"):
        module.bind_forge_workspace(
            repo,
            expected_rules_core_commit=fake["base"],
            expected_bridge_commit=fake["base"],
            expected_bridge_tree=fake["base_tree"],
        )


def test_run_native_suite_refuses_forge_without_a_workspace_and_runs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = runner_module(monkeypatch)

    def _explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("no native-suite process may start without a validated workspace")

    monkeypatch.setattr(module.subprocess, "run", _explode)
    identity = receipt_mod.RunnerIdentity(
        repository="test",
        commit="0" * 40,
        tree="0" * 40,
        branch="test",
        dirty=False,
        dirty_paths=(),
        input_digests={"test": "0" * 64},
    )
    with pytest.raises(forge_error(module)):
        module.run_native_suite("forge", "direct", runner=identity)


def test_a_credited_run_cannot_substitute_forge_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner's entry point binds config/rules_engines.json and nothing else."""
    import inspect

    module = runner_module(monkeypatch)
    parameters = inspect.signature(module.resolve_forge_workspace).parameters
    assert list(parameters) == ["workspace"]
    authority = module.canonical_forge_authority()
    seen: dict[str, object] = {}

    def _record(workspace: object, **expected: object) -> dict:
        seen.update(expected)
        return {}

    monkeypatch.setattr(module, "bind_forge_workspace", _record)
    module.resolve_forge_workspace(tmp_path)
    assert seen == {
        "expected_rules_core_commit": authority["rules_core_commit"],
        "expected_bridge_commit": authority["bridge_commit"],
        "expected_bridge_tree": authority["bridge_tree"],
    }


def test_binding_requires_every_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = runner_module(monkeypatch)
    with pytest.raises(forge_error(module), match="no expected Forge"):
        module.bind_forge_workspace(
            tmp_path,
            expected_rules_core_commit="a" * 40,
            expected_bridge_commit="",
            expected_bridge_tree="b" * 40,
        )
