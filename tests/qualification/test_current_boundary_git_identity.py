"""B4: every Git fact used for evidence credit must fail closed.

The runner's ``git()`` helper ran with ``check=False`` and returned ``stdout.strip()``
unconditionally, so a failed Git call (missing repository, unborn HEAD, redirecting
environment) produced an empty or *other-repository* identity that flowed into
evidence documents as if it were measured. These tests pin the fail-closed contract:

* a Git fact that cannot be established raises instead of returning "";
* an inherited ``GIT_DIR``/``GIT_WORK_TREE`` cannot redirect the read;
* HEAD/tree facts are validated as full SHAs;
* the runner does not fabricate a suite engine tree at import time from an ambient
  path that may not be a repository.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"


def live_git(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def init_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "config", "user.email", "b4@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "B4 Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "file.txt").write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=path, check=True)
    return live_git("rev-parse", "HEAD", cwd=path)


def runner_module(monkeypatch: pytest.MonkeyPatch, *, forge_workspace: Path | None = None):
    """Load the runner script as a module under an explicit Forge workspace."""
    if forge_workspace is None:
        monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    else:
        monkeypatch.setenv("FORGE_WORKSPACE", str(forge_workspace))
    spec = importlib.util.spec_from_file_location("current_boundary_runner_b4", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def runner_error(module: object) -> type[BaseException]:
    """The runner's own fail-closed Git error, or the strictest fallback."""
    return getattr(module, "RunnerGitError", RuntimeError)


def test_git_fact_fails_closed_outside_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    with pytest.raises(runner_error(module)):
        module.git("rev-parse", "HEAD", cwd=tmp_path)


def test_git_fact_fails_closed_on_an_unborn_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    empty = tmp_path / "empty"
    subprocess.run(["git", "init", "-q", str(empty)], check=True)
    with pytest.raises(runner_error(module)):
        module.git_sha("rev-parse", "HEAD", cwd=empty)


def test_git_toplevel_refuses_a_non_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    with pytest.raises(runner_error(module)):
        module.git_toplevel(tmp_path)


def test_inherited_git_environment_cannot_redirect_the_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    decoy = tmp_path / "decoy"
    decoy_commit = init_repo(decoy)
    expected = live_git("rev-parse", "HEAD", cwd=REPO)
    assert decoy_commit != expected
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    assert module.git("rev-parse", "HEAD", cwd=REPO) == expected


def test_head_facts_are_validated_full_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    commit = module.git_sha("rev-parse", "HEAD", cwd=REPO)
    assert len(commit) == 40 and commit == live_git("rev-parse", "HEAD", cwd=REPO)
    tree = module.git_sha("rev-parse", "HEAD^{tree}", cwd=REPO)
    assert len(tree) == 40 and tree == live_git("rev-parse", "HEAD^{tree}", cwd=REPO)


def test_runner_git_toplevel_matches_the_repository_root(monkeypatch: pytest.MonkeyPatch) -> None:
    module = runner_module(monkeypatch, forge_workspace=REPO)
    assert module.git_toplevel(REPO) == REPO.resolve()


def test_import_records_only_an_explicit_unconfigured_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing non-repository path must not yield an empty engine_tree.

    Module import tolerated a missing checkout by recording ``""`` as an engine
    tree. The canonical behaviour is the explicit ``UNCONFIGURED`` marker, and a
    run never uses that marker: resolve_suite_root re-proves the checkout and
    fails closed.
    """
    module = runner_module(monkeypatch, forge_workspace=tmp_path)
    forge = module.NATIVE_SUITE_BINDING["forge"]
    assert forge["engine_tree"] == "UNCONFIGURED"
    with pytest.raises(module.ForgeWorkspaceError):
        module.resolve_suite_root("forge")


def test_runner_digest_covers_the_native_suite_test_sources() -> None:
    """A receipt proves what its test bytes assert; those bytes must be bound.

    The runner digest is what stales a receipt when the code that produced it
    changed. The native suite test classes are execution-semantic inputs: they
    define the observation a receipt records, so a change to them must change the
    digest instead of being inherited silently.
    """
    from commander_lab.qualification.current_boundary import receipts as R

    assert "engine-bridge/src/test/java/org/commanderlab/xmage/*.java" in R._EXECUTED_INPUT_GLOBS
    identity = R.capture_runner_identity(REPO)
    covered = [name for name in identity.input_digests if "/src/test/java/" in name]
    assert covered, "no native-suite test source is covered by the runner digest"


def test_git_redirection_list_covers_config_and_index_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One canonical strip list, shared by every evidence Git read.

    A redirected index can hide a dirty worktree from the provenance gate, and
    injected config/namespace/replace/shallow state can change what a Git fact
    means. The list is owned by receipts and consumed by the runner and the epoch
    resolver so the three cannot drift.
    """
    from commander_lab.qualification.current_boundary import receipts as R

    required = {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
        "GIT_SHALLOW_FILE",
        "GIT_REPLACE_REFS",
        "GIT_CEILING_DIRECTORIES",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
    }
    assert required <= set(R._GIT_REDIRECTION_ENV)
    assert not required & set(R.clean_git_environment())
    # Injected config entries are name-prefixed rather than fixed names.
    # monkeypatch restores any pre-existing value: deleting a GIT_CONFIG_KEY_0
    # the environment already set (while GIT_CONFIG_COUNT stays) breaks every
    # later git call in the process.
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "status.showUntrackedFiles")
    assert "GIT_CONFIG_KEY_0" not in R.clean_git_environment()
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "no")
    assert "GIT_CONFIG_VALUE_0" not in R.clean_git_environment()
    # The runner consumes the same strict reader (which strips the environment),
    # and the epoch resolver calls the sanitizer directly; neither keeps a
    # second strip list that could drift.
    runner_source = RUNNER.read_text(encoding="utf-8")
    assert "receipt_mod.git_fact(" in runner_source
    assert "_GIT_REDIRECTION_ENV =" not in runner_source
    epoch_sources = (
        REPO / "src" / "commander_lab" / "qualification" / "current_boundary" / "evidence_epoch.py"
    ).read_text(encoding="utf-8")
    assert "clean_git_environment()" in epoch_sources


def test_capture_runner_identity_is_not_redirected_by_inherited_git_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The AUTHORITATIVE identity path must read this checkout, not a decoy.

    ``capture_runner_identity`` is what binds every receipt, and
    ``engine_tree_equivalence`` is what proves a Forge Rules Core is the same
    engine. Both ran Git with the inherited environment, so an exported
    GIT_DIR/GIT_WORK_TREE could bind a receipt to another repository's commit
    while the evidence named this one.
    """
    from commander_lab.qualification.current_boundary import receipts as R

    decoy = tmp_path / "decoy"
    decoy_commit = init_repo(decoy)
    live_commit = live_git("rev-parse", "HEAD", cwd=REPO)
    live_tree = live_git("rev-parse", "HEAD^{tree}", cwd=REPO)
    assert decoy_commit != live_commit
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    identity = R.capture_runner_identity(REPO)
    assert identity.commit == live_commit
    assert identity.tree == live_tree


def test_engine_tree_equivalence_ignores_inherited_git_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.qualification.current_boundary import receipts as R

    decoy = tmp_path / "decoy"
    init_repo(decoy)
    head = live_git("rev-parse", "HEAD", cwd=REPO)
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    proof = R.engine_tree_equivalence(
        REPO, recorded_commit=head, actual_commit=head, module_roots=("engine-bridge",)
    )
    assert proof["engine_equivalent"] is True, proof
