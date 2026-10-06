"""Security invariants for every GitHub Actions workflow and local action.

The repository is public, so anyone can open a PR or comment on an issue.
These checks keep the workflows safe against that audience:

- a comment-triggered job that can read a secret only runs for principals
  with write-level association (a comment's text is also its prompt);
- a ``pull_request_target`` workflow never checks out or builds candidate code:
  it checks out the PR's historical base commit, or, only under a narrower
  proven contract, the current base-branch commit (``github.sha``);
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


HISTORICAL_BASE_REF = "${{ github.event.pull_request.base.sha }}"
CURRENT_BASE_REF = "${{ github.sha }}"
CANDIDATE_FETCH = 'git fetch --no-tags origin "refs/pull/$PR_NUMBER/head"'
CANDIDATE_BOUND = 'test "$(git rev-parse FETCH_HEAD)" = "$CANDIDATE_SHA"'
CANDIDATE_CHECKOUT = re.compile(
    r"git\s+(checkout|switch|worktree\s+add|reset|restore|read-tree|stash\s+apply)\b"
    r"|FETCH_HEAD\s*:|\$CANDIDATE_SHA\s*:|git\s+archive"
)


def _current_base_contract_violations(workflow: dict) -> list[str]:
    """Why ``github.sha`` would not be trusted base-branch code in this workflow.

    Under ``pull_request_target`` alone, ``github.sha`` is the last commit of
    the PR's base branch, so checking it out runs trusted code even when the
    PR's historical base predates that code. The same expression under any other
    trigger (``pull_request`` makes it the synthetic merge with candidate code)
    is not trusted, so the contract demands, all at once:

    - ``pull_request_target`` is the only trigger, restricted to ``main``;
    - every checkout keeps no credentials;
    - the candidate is reached only by fetching ``refs/pull/$PR_NUMBER/head``
      with ``FETCH_HEAD`` bound to the event's exact head SHA;
    - no step checks the candidate out, materializes it into the work tree or
      archives it.
    """
    violations: list[str] = []
    on = workflow.get(True, workflow.get("on"))
    if _events(workflow) != {"pull_request_target"}:
        violations.append(f"triggers {sorted(_events(workflow))} are not pull_request_target alone")
    target = (on or {}).get("pull_request_target") if isinstance(on, dict) else None
    if not isinstance(target, dict) or target.get("branches") != ["main"]:
        violations.append("pull_request_target is not restricted to branches: [main]")
    steps = _steps(workflow)
    for step in steps:
        if (
            str(step.get("uses", "")).startswith("actions/checkout@")
            and (step.get("with") or {}).get("persist-credentials") is not False
        ):
            violations.append("a checkout persists credentials")
    runs = [str(step.get("run", "")) for step in steps]
    fetching = [run for run in runs if "refs/pull/" in run]
    if not fetching or not all(
        CANDIDATE_FETCH in run and CANDIDATE_BOUND in run for run in fetching
    ):
        violations.append(
            "the candidate is not fetched only as refs/pull/<n>/head bound to its SHA"
        )
    for run in runs:
        match = CANDIDATE_CHECKOUT.search(run)
        if match is not None:
            violations.append(f"a step materializes Git content: {match.group(0)!r}")
    return violations


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_pull_request_target_never_checks_out_candidate_code(path: Path) -> None:
    workflow = _load(path)
    if "pull_request_target" not in _events(workflow):
        return
    for step in _steps(workflow):
        if str(step.get("uses", "")).startswith("actions/checkout@"):
            ref = str((step.get("with") or {}).get("ref", ""))
            if ref == HISTORICAL_BASE_REF:
                continue
            assert ref == CURRENT_BASE_REF, (
                f"{path.name}: pull_request_target checkout must pin the base commit, got {ref!r}"
            )
            violations = _current_base_contract_violations(workflow)
            assert not violations, (
                f"{path.name}: checking out {CURRENT_BASE_REF} needs the trusted current-base "
                f"contract: {violations}"
            )


def test_only_the_ci_definition_gate_uses_the_current_base_branch_commit() -> None:
    """The current-base checkout is an exception, held to one reviewed workflow;
    every other pull_request_target workflow keeps its historical base pin."""
    users = sorted(
        path.name
        for path in WORKFLOWS
        if "pull_request_target" in _events(_load(path))
        and any(
            str((step.get("with") or {}).get("ref", "")) == CURRENT_BASE_REF
            for step in _steps(_load(path))
            if str(step.get("uses", "")).startswith("actions/checkout@")
        )
    )
    assert users == ["ci-definition-integrity.yml"]


@pytest.mark.parametrize(
    "mutation, expected",
    [
        ("also_pull_request", "not pull_request_target alone"),
        ("any_branch", "restricted to branches"),
        ("persist_credentials", "persists credentials"),
        ("checkout_candidate", "materializes Git content"),
        ("unbound_fetch", "bound to its SHA"),
        ("worktree_candidate", "materializes Git content"),
    ],
)
def test_the_current_base_contract_rejects_every_weakening(mutation: str, expected: str) -> None:
    import copy

    workflow = copy.deepcopy(_load(ROOT / ".github/workflows/ci-definition-integrity.yml"))
    assert _current_base_contract_violations(workflow) == []
    on = workflow.get(True, workflow.get("on"))
    steps = _steps(workflow)
    inspect = next(step for step in steps if "refs/pull/" in str(step.get("run", "")))
    if mutation == "also_pull_request":
        on["pull_request"] = {"branches": ["main"]}
    elif mutation == "any_branch":
        on["pull_request_target"].pop("branches")
    elif mutation == "persist_credentials":
        next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@"))["with"][
            "persist-credentials"
        ] = True
    elif mutation == "checkout_candidate":
        inspect["run"] += "\ngit checkout FETCH_HEAD\n"
    elif mutation == "unbound_fetch":
        inspect["run"] = inspect["run"].replace(CANDIDATE_BOUND, "true")
    elif mutation == "worktree_candidate":
        inspect["run"] += '\ngit worktree add ../candidate "$CANDIDATE_SHA"\n'
    violations = _current_base_contract_violations(workflow)
    assert any(expected in item for item in violations), violations


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


def test_opencode_agent_refuses_untrusted_targets() -> None:
    """An agent run holding OPENCODE_API_KEY never targets untrusted content.

    The comment author's association is not enough: the agent reads the target
    issue/PR text and, on a PR, its head. Both jobs must also require a trusted
    target author and refuse fork pull requests before anything is checked out.
    """
    doc = yaml.safe_load((ROOT / ".github/workflows/opencode.yml").read_text(encoding="utf-8"))
    jobs = doc["jobs"]
    assert jobs, "opencode.yml has no jobs"
    for name, job in jobs.items():
        condition = job["if"]
        assert "github.event.comment.author_association" in condition, name
        assert (
            "github.event.issue.author_association || "
            "github.event.pull_request.author_association" in condition
        ), name
        first = job["steps"][0]
        assert first["name"] == "Refuse fork pull requests as agent targets", name
        assert '"$head_repo" != "$GITHUB_REPOSITORY"' in first["run"], name
        assert "exit 1" in first["run"], name


def test_pull_request_target_checkouts_never_persist_credentials() -> None:
    for path in WORKFLOWS:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        triggers = doc.get(True) or doc.get("on") or {}
        if "pull_request_target" not in (triggers if isinstance(triggers, dict) else [triggers]):
            continue
        for job in doc["jobs"].values():
            for step in job.get("steps", []):
                if str(step.get("uses", "")).startswith("actions/checkout@"):
                    assert (step.get("with") or {}).get("persist-credentials") is False, path.name
