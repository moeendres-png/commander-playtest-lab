"""Concurrency invariants for the GitHub Actions workflows.

A concurrency group with ``cancel-in-progress`` cancels the older run in the
same group. Keyed on ``github.ref`` alone, every push to ``main`` shares one
group, so a merge landing while the previous merge's run is in progress
cancelled that run: 11 of the last 30 ``main`` runs of CI were cancelled
(2026-09-30), and those merged heads had no CI evidence of their own. Even
without ``cancel-in-progress`` GitHub keeps only one pending run per group, so
a third quick merge still drops the second one's.

Only runs of the same pull request may supersede each other. Every other run
must be in a group of its own, keyed on the commit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
NON_PR_EVENTS = {"push", "workflow_dispatch", "schedule", "workflow_run"}


def _events(workflow: dict) -> set[str]:
    on = workflow.get(True, workflow.get("on"))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    return set(on or {})


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_non_pull_request_runs_never_share_a_concurrency_group(path: Path) -> None:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    concurrency = workflow.get("concurrency")
    if concurrency is None or not (_events(workflow) & NON_PR_EVENTS):
        return
    group = concurrency["group"] if isinstance(concurrency, dict) else concurrency
    assert "github.sha" in group, (
        f"{path.name}: concurrency group {group!r} is shared by pushes/dispatches, so one merged "
        "head's run can cancel or displace another's; key non-PR runs on github.sha"
    )


@pytest.mark.parametrize(
    "name",
    [
        "ci.yml",
        "xmage-full-game-conformance.yml",
        "xmage-real-4p-smoke.yml",
        "external-engine-integration.yml",
        "production-qualification.yml",
    ],
)
def test_expensive_pull_request_runs_are_superseded_by_newer_pushes(name: str) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
    concurrency = workflow.get("concurrency") or {}
    assert concurrency.get("cancel-in-progress") is True, f"{name}: obsolete PR runs keep running"
    assert "github.head_ref" in concurrency.get("group", ""), (
        f"{name}: PR runs are not grouped by branch"
    )


def test_every_tree_integrity_run_is_superseded_by_the_same_pull_requests_next_run() -> None:
    """It runs on every push and every PR edit; 20 runs of one branch sat in the
    queue at once for superseded heads (2026-09-30), ahead of other PRs' runs."""
    path = ROOT / ".github/workflows/repository-tree-integrity.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert _events(workflow) == {"pull_request_target"}
    concurrency = workflow.get("concurrency") or {}
    assert concurrency.get("cancel-in-progress") is True
    assert "github.event.pull_request.number" in concurrency.get("group", "")
