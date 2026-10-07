"""Wrong-reason controls for fail-safe materiality classification."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import materiality as mat  # noqa: E402


def _git(args: list[str], cwd: Path) -> str:
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
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_ordinary_docs_default_to_material() -> None:
    """Wrong-reason control: docs/** is fail-safe MATERIAL by default."""
    for path in (
        "docs/PROJECT_MISSION.md",
        "docs/note.md",
        "docs/notes.txt",
        "docs/data.json",
        "docs/random/new.md",
        "docs/CLOSEOUT_POLICY.md",
        "docs/evidence-closeout.md",
    ):
        assert mat.classify_path(path) == mat.MATERIAL, path


def test_narrow_documentation_closeout_reports_are_non_material() -> None:
    """The only docs exemption: explicitly named historical closeout reports."""
    for path in (
        "docs/J_P3_CLOSEOUT.md",
        "docs/B4F_XMAGE_FIDELITY_CLOSEOUT.md",
        "docs/workstream_deep_research_closure_20260923/PHASE1_CLOSEOUT.md",
        "docs/decision_quality/SIMULATION_FIDELITY_124_CLOSEOUT_CURRENT.md",
    ):
        assert mat.classify_path(path) == mat.NON_MATERIAL, path


def test_non_policy_root_markdown_stays_non_material() -> None:
    for path in ("README.md", "CHANGELOG.md"):
        assert mat.classify_path(path) == mat.NON_MATERIAL, path


def test_policy_markdown_is_always_material() -> None:
    for path in (
        "AGENTS.md",
        "CLAUDE.md",
        "POLICY.md",
        "docs/CURRENT_EXECUTION_AUTHORITY.md",
        "docs/PROJECT_MISSION.md",
        "docs/QUALIFICATION.md",
        "docs/EVIDENCE_POLICY.md",
        "docs/foundry-execution/ROUTING_AND_EFFORT.md",
        "docs/foundry-execution/WORKSTREAM_CONTRACT_TEMPLATE.md",
        "docs/foundry-execution/UNKNOWN_FUTURE_NOTE.md",
        "docs/CARD_KNOWLEDGE_POLICY_CURRENT.md",
        "docs/OPERATIONAL_SIMULATION_POLICY.md",
        "docs/REPOSITORY_TRIAGE_INDEX.md",
        "docs/closeouts/SECURITY_CLOSEOUT.md",
    ):
        assert mat.classify_path(path) == mat.MATERIAL, path


def test_closeout_name_outside_docs_is_not_an_exemption() -> None:
    for path in ("notes/CLOSEOUT.md", "reports/J_P3_CLOSEOUT.md"):
        assert mat.classify_path(path) == mat.MATERIAL, path


def test_generated_state_paths_are_non_material_but_unknown_foundry_yaml_and_policy_are_not() -> (
    None
):
    state = ".foundry/WORKSTREAM_STATE.yaml"
    assert mat.classify_path(state, state_paths=(state,)) == mat.GENERATED_STATE
    # Wrong-reason control: a YAML suffix alone must never grant an exemption.
    assert mat.classify_path(".foundry/oc-policy-20261006.yaml") == mat.MATERIAL
    assert mat.classify_path(".foundry/reviews/ws.json") == mat.GENERATED_STATE
    # Policy/registry/schema/evidence receipts under .foundry are MATERIAL:
    # review cannot be evaded by dressing a policy change as state.
    assert mat.classify_path(".foundry/executor-profiles.json") == mat.MATERIAL
    assert mat.classify_path(".foundry/WORKSTREAM_STATE.schema.json") == mat.MATERIAL
    assert mat.classify_path(".foundry/space-bunny-rebind-runtime-activation-20261006.json") == (
        mat.MATERIAL
    )


def test_explicit_state_path_is_generated_state_even_outside_foundry() -> None:
    assert (
        mat.classify_path("work/state.yaml", state_paths=("work/state.yaml",))
        == mat.GENERATED_STATE
    )


def test_implementation_tooling_schema_ci_and_test_paths_are_material() -> None:
    for path in (
        "tools/foundry/launcher.py",
        "src/commander_lab/engine/rules/bridge.py",
        "tests/foundry/test_review_gate.py",
        "scripts/verify_repository_tree.py",
        ".github/workflows/opencode.yml",
        "opencode.json",
        "schemas/foundry/state.json",
        ".opencode/agents/foundry-reviewer.md",
    ):
        assert mat.classify_path(path) == mat.MATERIAL, path


def test_unknown_paths_default_to_material() -> None:
    for path in ("mystery.bin", "newdir/whatever.xyz", ".foundry/unknown.json", ""):
        assert mat.classify_path(path) == mat.MATERIAL, path


def test_classify_paths_material_if_any_path_is_material() -> None:
    report = mat.classify_paths(
        ["docs/J_P3_CLOSEOUT.md", ".foundry/WORKSTREAM_STATE.yaml", "tools/foundry/launcher.py"],
        state_paths=(".foundry/WORKSTREAM_STATE.yaml",),
    )
    assert report.computed == mat.MATERIAL
    assert report.material_paths == ("tools/foundry/launcher.py",)
    assert report.non_material_paths == ("docs/J_P3_CLOSEOUT.md",)
    assert report.generated_state_paths == (".foundry/WORKSTREAM_STATE.yaml",)

    # Wrong-reason control: an ordinary docs change is material, never a docs
    # exemption.
    report = mat.classify_paths(["docs/note.md", "README.md"])
    assert report.computed == mat.MATERIAL
    assert report.material_paths == ("docs/note.md",)
    assert report.non_material_paths == ("README.md",)


def test_classify_paths_generated_state_only_is_non_material() -> None:
    report = mat.classify_paths(
        [".foundry/WORKSTREAM_STATE.yaml", ".foundry/reviews/r.json"],
        state_paths=(".foundry/WORKSTREAM_STATE.yaml",),
    )
    assert report.computed == mat.NON_MATERIAL
    assert report.material_paths == ()

    # Without the explicit state path the same YAML is fail-safe MATERIAL.
    report = mat.classify_paths([".foundry/WORKSTREAM_STATE.yaml"])
    assert report.computed == mat.MATERIAL


@pytest.fixture()
def repo(tmp_path: Path) -> dict:
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-b", "main"], root)
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("a\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "base"], root)
    base = _git(["rev-parse", "HEAD"], root)
    (root / "tools").mkdir()
    (root / "tools" / "impl.py").write_text("x = 1\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "impl"], root)
    material = _git(["rev-parse", "HEAD"], root)
    (root / ".foundry").mkdir()
    (root / ".foundry" / "WORKSTREAM_STATE.yaml").write_text("schema_version: '2.0'\n")
    _git(["add", "."], root)
    _git(["commit", "-m", "state"], root)
    generated = _git(["rev-parse", "HEAD"], root)
    (root / "docs" / "b_CLOSEOUT.md").write_text("b\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "docs closeout"], root)
    docs = _git(["rev-parse", "HEAD"], root)
    return {"root": root, "base": base, "material": material, "generated": generated, "docs": docs}


def test_commit_range_material_and_generated_state_classification(repo: dict) -> None:
    report = mat.classify_commit_range(str(repo["root"]), repo["base"], repo["material"])
    assert report.computed == mat.MATERIAL
    assert report.material_paths == ("tools/impl.py",)

    report = mat.classify_commit_range(
        str(repo["root"]),
        repo["material"],
        repo["generated"],
        state_paths=(".foundry/WORKSTREAM_STATE.yaml",),
    )
    assert report.computed == mat.NON_MATERIAL
    assert report.generated_state_paths == (".foundry/WORKSTREAM_STATE.yaml",)

    report = mat.classify_commit_range(str(repo["root"]), repo["generated"], repo["docs"])
    assert report.computed == mat.NON_MATERIAL
    assert report.non_material_paths == ("docs/b_CLOSEOUT.md",)


def test_commit_range_empty_delta_is_non_material(repo: dict) -> None:
    report = mat.classify_commit_range(str(repo["root"]), repo["base"], repo["base"])
    assert report.computed == mat.NON_MATERIAL


def test_commit_range_unavailable_objects_are_unknown_and_fail_safe(repo: dict) -> None:
    report = mat.classify_commit_range(str(repo["root"]), "f" * 40, repo["material"])
    assert report.computed == mat.UNKNOWN
    assert report.effective_computed == mat.MATERIAL
    assert report.is_material


def test_non_material_underclaim_is_a_failure(repo: dict) -> None:
    report = mat.classify_commit_range(str(repo["root"]), repo["base"], repo["material"])
    problems = mat.declared_materiality_problems(mat.NON_MATERIAL, report)
    assert problems and "MATERIALITY_UNDERCLAIM" in problems[0]

    report = mat.classify_commit_range(
        str(repo["root"]),
        repo["material"],
        repo["generated"],
        state_paths=(".foundry/WORKSTREAM_STATE.yaml",),
    )
    assert mat.declared_materiality_problems(mat.NON_MATERIAL, report) == []
    assert mat.declared_materiality_problems(mat.MATERIAL, report) == []


def test_invalid_declared_materiality_fails_closed(repo: dict) -> None:
    report = mat.classify_commit_range(str(repo["root"]), repo["base"], repo["material"])
    problems = mat.declared_materiality_problems("MAYBE", report)
    assert problems and "MATERIALITY_INVALID" in problems[0]
