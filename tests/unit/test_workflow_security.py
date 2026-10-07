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


# --- behavioral evaluation of the GitHub Actions `if` expressions -----------
#
# The trust properties below are semantic: the workflow's condition text is
# parsed and evaluated against concrete event contexts, so weakening a
# conjunction to a disjunction (or dropping the target gate) fails here even
# when the text still contains the expected substrings.

_EXPR_TOKEN = re.compile(
    r"\s*(?:(&&|\|\||==|!=|!|\(|\)|\[|\]|,)"
    r"|'((?:[^'\\]|\\.)*)'"
    r'|"((?:[^"\\]|\\.)*)"'
    r"|([A-Za-z_][A-Za-z0-9_.]*)"
    r"|(\d+))"
)


def _expr_tokens(text: str) -> list[tuple[str, object]]:
    tokens: list[tuple[str, object]] = []
    pos = 0
    while pos < len(text):
        match = _EXPR_TOKEN.match(text, pos)
        if match is None:
            if text[pos:].strip():
                raise ValueError(f"unparseable expression text at {pos}: {text[pos : pos + 20]!r}")
            break
        pos = match.end()
        op, single, double, identifier, number = match.groups()
        if op is not None:
            tokens.append(("op", op))
        elif single is not None or double is not None:
            tokens.append(("str", single if single is not None else double))
        elif identifier is not None:
            tokens.append(("id", identifier))
        else:
            tokens.append(("num", int(number)))
    return tokens


class _ExprParser:
    def __init__(self, tokens: list[tuple[str, object]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> tuple[str, object] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _take(self, kind: str, value: object = None) -> tuple[str, object]:
        token = self._peek()
        if token is None or token[0] != kind or (value is not None and token[1] != value):
            raise ValueError(f"expected {kind} {value!r}, got {token!r}")
        self.pos += 1
        return token

    def parse(self) -> object:
        node = self.parse_or()
        if self._peek() is not None:
            raise ValueError(f"trailing tokens: {self.tokens[self.pos :]!r}")
        return node

    def parse_or(self) -> object:
        node = self.parse_and()
        while self._peek() == ("op", "||"):
            self.pos += 1
            node = ("or", node, self.parse_and())
        return node

    def parse_and(self) -> object:
        node = self.parse_not()
        while self._peek() == ("op", "&&"):
            self.pos += 1
            node = ("and", node, self.parse_not())
        return node

    def parse_not(self) -> object:
        if self._peek() == ("op", "!"):
            self.pos += 1
            return ("not", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> object:
        node = self.parse_atom()
        while self._peek() in (("op", "=="), ("op", "!=")):
            operator = self._take("op")[1]
            node = (str(operator), node, self.parse_atom())
        return node

    def parse_atom(self) -> object:
        token = self._peek()
        if token is None:
            raise ValueError("unexpected end of expression")
        if token == ("op", "("):
            self.pos += 1
            node = self.parse_or()
            self._take("op", ")")
            return node
        if token == ("op", "["):
            self.pos += 1
            items: list[object] = []
            if self._peek() != ("op", "]"):
                items.append(self.parse_or())
                while self._peek() == ("op", ","):
                    self.pos += 1
                    items.append(self.parse_or())
            self._take("op", "]")
            return ("array", items)
        if token[0] == "str":
            self.pos += 1
            return ("lit", token[1])
        if token[0] == "num":
            self.pos += 1
            return ("lit", token[1])
        if token[0] == "id":
            self.pos += 1
            identifier = str(token[1])
            if self._peek() == ("op", "("):
                self.pos += 1
                args: list[object] = []
                if self._peek() != ("op", ")"):
                    args.append(self.parse_or())
                    while self._peek() == ("op", ","):
                        self.pos += 1
                        args.append(self.parse_or())
                self._take("op", ")")
                return ("call", identifier, args)
            return ("id", identifier)
        raise ValueError(f"unexpected token {token!r}")


def _expr_eval(node: object, context: dict) -> object:
    kind = node[0]  # type: ignore[index]
    if kind == "lit":
        return node[1]  # type: ignore[index]
    if kind == "array":
        return [_expr_eval(item, context) for item in node[1]]  # type: ignore[index]
    if kind == "id":
        identifier = str(node[1])  # type: ignore[index]
        if identifier in ("true", "false", "null"):
            return {"true": True, "false": False, "null": None}[identifier]
        current: object = context
        for part in identifier.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    if kind == "or":
        return _expr_eval(node[1], context) or _expr_eval(node[2], context)  # type: ignore[index]
    if kind == "and":
        return _expr_eval(node[1], context) and _expr_eval(node[2], context)  # type: ignore[index]
    if kind == "not":
        return not _expr_eval(node[1], context)  # type: ignore[index]
    if kind in ("==", "!="):
        left = _expr_eval(node[1], context)  # type: ignore[index]
        right = _expr_eval(node[2], context)  # type: ignore[index]
        return (left == right) if kind == "==" else (left != right)
    if kind == "call":
        name = str(node[1])  # type: ignore[index]
        args = [_expr_eval(arg, context) for arg in node[2]]  # type: ignore[index]
        if name == "contains":
            haystack, needle = args
            if isinstance(haystack, list):
                return any(item == needle for item in haystack)
            return str(needle) in str(haystack or "")
        if name == "startsWith":
            return str(args[0] or "").startswith(str(args[1]))
        if name == "endsWith":
            return str(args[0] or "").endswith(str(args[1]))
        if name == "fromJSON":
            import json

            return json.loads(str(args[0]))
        raise ValueError(f"unsupported expression function {name!r}")
    raise ValueError(f"unknown expression node {node!r}")


def condition_result(condition: str, context: dict) -> bool:
    return bool(_expr_eval(_ExprParser(_expr_tokens(condition)).parse(), context))


def _event_context(
    *,
    commenter: str,
    target: str,
    target_login: str,
    body: str,
    is_pr: bool = False,
) -> dict:
    issue: dict = {
        "author_association": target,
        "user": {"login": target_login},
        "pull_request": {} if is_pr else None,
        "number": 1,
    }
    event: dict = {
        "comment": {"author_association": commenter, "body": body},
        "issue": issue,
    }
    if is_pr:
        event["pull_request"] = {
            "author_association": target,
            "user": {"login": target_login},
            "number": 1,
        }
    return {"github": {"event": event}}


def test_expression_evaluator_tracks_boolean_semantics() -> None:
    """The evaluator is non-vacuous: it detects a conjunction->disjunction swap."""
    context = {"github": {"event": {"comment": {"author_association": "NONE"}}}}
    trusted = (
        'contains(fromJSON(\'["OWNER", "MEMBER", "COLLABORATOR"]\'), '
        "github.event.comment.author_association)"
    )
    assert condition_result(f"{trusted} && false", context) is False
    assert condition_result(f"{trusted} || false", context) is False  # NONE is not trusted
    weakened = f"{trusted} || true"
    assert condition_result(weakened, context) is True


def test_opencode_agent_refuses_untrusted_targets() -> None:
    """An agent run holding OPENCODE_API_KEY never targets untrusted content.

    Evaluated semantically per job: an untrusted commenter is refused, and a
    trusted commenter on an untrusted target (an issue/PR whose author has no
    write-level association, including a bot-authored thread) is refused. A
    fork PR is refused structurally before anything is checked out.
    """
    doc = yaml.safe_load((ROOT / ".github/workflows/opencode.yml").read_text(encoding="utf-8"))
    jobs = doc["jobs"]
    assert jobs, "opencode.yml has no jobs"
    for name, job in jobs.items():
        condition = str(job["if"])
        untrusted_commenter = _event_context(
            commenter="NONE", target="OWNER", target_login="maintainer", body="/oc work"
        )
        assert condition_result(condition, untrusted_commenter) is False, (
            f"{name}: an untrusted commenter can start the job"
        )
        untrusted_target = _event_context(
            commenter="OWNER", target="NONE", target_login="stranger", body="/oc work"
        )
        assert condition_result(condition, untrusted_target) is False, (
            f"{name}: an untrusted target can start the job"
        )
        first = job["steps"][0]
        assert first["name"] == "Refuse fork pull requests as agent targets", name
        assert first["if"] == "github.event.issue.pull_request || github.event.pull_request", name
        assert first["env"]["PR_NUMBER"] == (
            "${{ github.event.issue.number || github.event.pull_request.number }}"
        ), name
        assert "--jq '.head.repo.full_name'" in first["run"], name
        assert '"$head_repo" != "$GITHUB_REPOSITORY"' in first["run"], name
        assert "exit 1" in first["run"], name


def test_trusted_comments_start_each_opencode_lane() -> None:
    """Positive reachability: trusted comments select exactly the intended lane."""
    doc = yaml.safe_load((ROOT / ".github/workflows/opencode.yml").read_text(encoding="utf-8"))
    jobs = doc["jobs"]
    implementation = _event_context(
        commenter="OWNER", target="OWNER", target_login="maintainer", body="/oc continue"
    )
    bootstrap = _event_context(
        commenter="OWNER", target="OWNER", target_login="maintainer", body="/bunny audit this"
    )
    review_pr = _event_context(
        commenter="MEMBER",
        target="OWNER",
        target_login="maintainer",
        body="/bunny-review review exact SHA",
        is_pr=True,
    )
    assert condition_result(str(jobs["opencode"]["if"]), implementation) is True
    assert condition_result(str(jobs["opencode-bunny"]["if"]), bootstrap) is True
    assert condition_result(str(jobs["opencode-bunny-review"]["if"]), review_pr) is True


def test_bunny_bootstrap_lane_is_not_selected_by_the_direct_marker() -> None:
    """`/bunny-review` must never fall through to the writable /bunny lane."""
    doc = yaml.safe_load((ROOT / ".github/workflows/opencode.yml").read_text(encoding="utf-8"))
    direct_body = _event_context(
        commenter="OWNER",
        target="OWNER",
        target_login="maintainer",
        body="/bunny-review review this",
    )
    assert condition_result(str(doc["jobs"]["opencode-bunny"]["if"]), direct_body) is False
    assert condition_result(str(doc["jobs"]["opencode-bunny-review"]["if"]), direct_body) is True


def test_bunny_review_lane_stays_closed_for_untrusted_principals() -> None:
    """Both the commenter and the thread author must be write-level trusted."""
    doc = yaml.safe_load((ROOT / ".github/workflows/opencode.yml").read_text(encoding="utf-8"))
    condition = str(doc["jobs"]["opencode-bunny-review"]["if"])
    untrusted_commenter = _event_context(
        commenter="NONE",
        target="NONE",
        target_login="opencode-agent[bot]",
        body="/bunny-review review this",
        is_pr=True,
    )
    assert condition_result(condition, untrusted_commenter) is False
    untrusted_target = _event_context(
        commenter="OWNER",
        target="NONE",
        target_login="stranger",
        body="/bunny-review review this",
        is_pr=True,
    )
    assert condition_result(condition, untrusted_target) is False
    # A bot-authored thread is not exempt: the review lane matches the other
    # lanes' thread-author gate and refuses `opencode-agent[bot]` threads.
    bot_target = _event_context(
        commenter="OWNER",
        target="NONE",
        target_login="opencode-agent[bot]",
        body="/bunny-review review this",
        is_pr=True,
    )
    assert condition_result(condition, bot_target) is False
    wrong_mention = _event_context(
        commenter="OWNER",
        target="NONE",
        target_login="opencode-agent[bot]",
        body="/oc do implementation work",
        is_pr=True,
    )
    assert condition_result(condition, wrong_mention) is False


def test_pull_request_target_checkouts_never_persist_credentials() -> None:
    checked = 0
    for path in WORKFLOWS:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        triggers = doc.get(True) or doc.get("on") or {}
        if "pull_request_target" not in (triggers if isinstance(triggers, dict) else [triggers]):
            continue
        for job in doc["jobs"].values():
            for step in job.get("steps", []):
                if str(step.get("uses", "")).startswith("actions/checkout@"):
                    assert (step.get("with") or {}).get("persist-credentials") is False, path.name
                    checked += 1
    assert checked >= 1, "no pull_request_target checkout found: the check is vacuous"
