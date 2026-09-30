"""Security invariants for every GitHub Actions workflow and local action.

The repository is public, so anyone can open a PR or comment on an issue.
These checks keep the workflows safe against that audience:

- a comment-triggered job that can read a secret only runs for principals
  with write-level association (a comment's text is also its prompt);
- a ``pull_request_target`` workflow never checks out or builds candidate code;
- untrusted event text is never interpolated into a shell script;
- every third-party action is pinned to a full commit SHA;
- every workflow declares its token permissions explicitly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
ACTIONS = sorted((ROOT / ".github/actions").glob("*/action.yml"))
COMMENT_EVENTS = {"issue_comment", "pull_request_review_comment", "discussion_comment"}
TRUSTED_GATE = re.compile(
    r"contains\(fromJSON\('\[\"OWNER\", \"MEMBER\", \"COLLABORATOR\"\]'\), "
    r"github\.event\.comment\.author_association\)"
)
UNTRUSTED_TEXT = re.compile(
    r"\$\{\{\s*github\.(head_ref|event\.(comment|issue|review|discussion|head_commit"
    r"|pull_request\.(title|body|head\.ref|head\.label)))"
)
PINNED = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _events(workflow: dict) -> set[str]:
    on = workflow.get(True, workflow.get("on"))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    return set(on or {})


def _steps(document: dict) -> list[dict]:
    steps: list[dict] = []
    for job in (document.get("jobs") or {}).values():
        steps.extend(job.get("steps") or [])
    steps.extend((document.get("runs") or {}).get("steps") or [])
    return steps


def test_workflows_are_discovered() -> None:
    assert len(WORKFLOWS) >= 10
    assert (ROOT / ".github/workflows/opencode.yml") in WORKFLOWS


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_comment_triggered_jobs_with_secrets_require_a_trusted_author(path: Path) -> None:
    workflow = _load(path)
    if not _events(workflow) & COMMENT_EVENTS:
        return
    for name, job in workflow["jobs"].items():
        if "secrets." not in yaml.safe_dump(job):
            continue
        assert TRUSTED_GATE.search(str(job.get("if", ""))), (
            f"{path.name}:{name} reads a secret on a comment event without an author_association gate"
        )


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_pull_request_target_never_checks_out_candidate_code(path: Path) -> None:
    workflow = _load(path)
    if "pull_request_target" not in _events(workflow):
        return
    for step in _steps(workflow):
        if str(step.get("uses", "")).startswith("actions/checkout@"):
            ref = str((step.get("with") or {}).get("ref", ""))
            assert ref == "${{ github.event.pull_request.base.sha }}", (
                f"{path.name}: pull_request_target checkout must pin the base commit, got {ref!r}"
            )


@pytest.mark.parametrize("path", WORKFLOWS + ACTIONS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_untrusted_event_text_is_never_interpolated_into_a_shell(path: Path) -> None:
    for step in _steps(_load(path)):
        match = UNTRUSTED_TEXT.search(str(step.get("run", "")))
        assert match is None, (
            f"{path.name}:{step.get('name')} interpolates {match.group(0)} into a shell"
        )


@pytest.mark.parametrize("path", WORKFLOWS + ACTIONS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_third_party_actions_are_pinned_to_a_commit(path: Path) -> None:
    for step in _steps(_load(path)):
        uses = str(step.get("uses", ""))
        if uses and not uses.startswith("./"):
            assert PINNED.match(uses), f"{path.name}: {uses} is not pinned to a full commit SHA"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_workflow_declares_token_permissions(path: Path) -> None:
    workflow = _load(path)
    if "permissions" in workflow:
        return
    for name, job in workflow["jobs"].items():
        assert "permissions" in job, f"{path.name}:{name} runs with the default token permissions"
