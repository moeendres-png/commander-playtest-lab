"""Every source a path-filtered workflow executes is covered by that workflow's gates.

A qualification workflow gated by ``pull_request.paths`` or the ``change-scope``
action only runs when a listed path changes. Before this guard, the meta
qualification workflow executed the semantic-replay comparator but did not
list ``src/commander_lab/semantic_replay/**``, and most gated workflows missed
dozens of the modules they import. ``scripts/audit_workflow_impact.py`` derives
each job's executed files from its entry points and the repository's own
imports; this test fails when any of them is outside a gate that applies to
the job. Fix a failure with ``python scripts/audit_workflow_impact.py --fix``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _audit() -> Any:
    spec = importlib.util.spec_from_file_location(
        "audit_workflow_impact", ROOT / "scripts" / "audit_workflow_impact.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _audit()
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_every_executed_source_is_covered_by_the_gates_of_its_job(workflow: Path) -> None:
    if workflow.name in AUDIT.NOT_REWRITTEN:
        pytest.skip(f"{workflow.name}: {AUDIT.NOT_REWRITTEN[workflow.name]}")
    result = AUDIT.audit(workflow)
    if result is None:
        return
    uncovered = {
        job: detail["uncovered"] for job, detail in result["jobs"].items() if detail["uncovered"]
    }
    assert uncovered == {}, (
        f"{workflow.name} executes sources its gates do not cover; "
        "run scripts/audit_workflow_impact.py --fix"
    )


def test_every_exemption_names_a_real_workflow() -> None:
    for name in AUDIT.NOT_REWRITTEN:
        assert (ROOT / ".github" / "workflows" / name).is_file(), name


def test_the_meta_qualification_gate_covers_the_semantic_replay_comparator() -> None:
    result = AUDIT.audit(ROOT / ".github/workflows/meta-qualification.yml")
    executed = {path for detail in result["jobs"].values() for path in detail["executed_files"]}
    assert any(path.startswith("src/commander_lab/semantic_replay/") for path in executed)
    assert AUDIT.covered(
        "src/commander_lab/semantic_replay/comparator.py",
        AUDIT.trigger_gates(
            __import__("yaml").safe_load(
                (ROOT / ".github/workflows/meta-qualification.yml").read_text()
            )
        ),
    )


@pytest.mark.parametrize(
    ("path", "globs", "expected"),
    [
        ("src/commander_lab/engine/rules/full_game.py", ["src/commander_lab/engine/**"], True),
        ("src/commander_lab/engine/rules/full_game.py", ["src/commander_lab/engine/*"], False),
        ("src/commander_lab/engine/x.py", ["src/commander_lab/engine/*"], True),
        ("tests/conftest.py", ["tests/**/conftest.py"], True),
        ("a/b.py", ["a/**", "!a/b.py"], False),
        ("a/c.py", ["a/**", "!a/b.py"], True),
    ],
)
def test_glob_semantics_match_github_and_git_pathspecs(
    path: str, globs: list[str], expected: bool
) -> None:
    assert AUDIT.covered(path, globs) is expected


def test_a_whole_subpackage_is_covered_at_once() -> None:
    assert (
        AUDIT.cover_glob("src/commander_lab/engine/rules/full_game.py")
        == "src/commander_lab/engine/**"
    )
    assert (
        AUDIT.cover_glob("src/commander_lab/advancement.py") == "src/commander_lab/advancement.py"
    )
    assert AUDIT.cover_glob("tests/conftest.py") == "tests/conftest.py"


def test_full_game_push_requalifies_semantic_replay_changes() -> None:
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load(
        (root / ".github/workflows/xmage-full-game-conformance.yml").read_text()
    )
    triggers = document.get("on") or document.get(True)
    assert "src/commander_lab/semantic_replay/**" in triggers["push"]["paths"]
