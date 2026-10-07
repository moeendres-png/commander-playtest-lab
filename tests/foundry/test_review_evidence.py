"""Wrong-reason controls for trusted cross-executor review evidence.

A PASS review record is authored by the implementation executor, so the record
itself can never satisfy the gate. These tests inject fake GitHub REST
responses through the dependency-injected transport and prove that fabricated
or inconsistent external evidence fails closed, while a coherent trusted
direct-lane evidence graph satisfies the gate.

The receipt is bound to its run: the result comment must fall inside the run's
``run_started_at..updated_at`` window, the run must have been triggered by the
evidence's trigger comment, and the comment's own footer run link must be the
last run link. The writable bootstrap carrier is removed entirely.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import review_evidence as evidence_mod  # noqa: E402
from foundry import review_gate as review_mod  # noqa: E402

REPO = "moeendres-png/commander-playtest-lab"
AUDIT_BASE = "5a062a5bd1836e08514c78085f97071e8f533970"
IMPL = "ab02ba3359e3433b2dcf69ba48af39a1ee7df8a4"
IMPL_TREE = "aba282afa63ab67f5c9bb1bd70a1ce5c973e5ffc"
WORKFLOW_HEAD = "d0c54fcfaf182a2e2c3f28cdf91382d1ef927aea"
ISSUE = 578
TRIGGER_DIRECT = 222222
RESULT_DIRECT = 444444
RUN_DIRECT = 666666
JOB_DIRECT = 888888
WORKFLOW_PATH = ".github/workflows/opencode.yml"

TRIGGER_AT = "2026-10-06T20:00:00Z"
RUN_STARTED = "2026-10-06T20:00:05Z"
RESULT_AT = "2026-10-06T20:10:00Z"
RUN_UPDATED = "2026-10-06T20:10:05Z"


class FakeGitHub:
    """Injected read-only transport serving canned GitHub REST responses."""

    def __init__(self) -> None:
        self.responses: dict[str, tuple[int, str]] = {}
        self.requests: list[str] = []

    def add_json(self, path: str, payload: object, status: int = 200) -> None:
        self.responses[path] = (status, json.dumps(payload))

    def add_raw(self, path: str, text: str, status: int = 200) -> None:
        self.responses[path] = (status, text)

    def request(self, method: str, url: str, headers: dict, timeout: float) -> tuple[int, bytes]:
        assert method == "GET"
        path = url.removeprefix("https://api.github.com")
        self.requests.append(path)
        if path in self.responses:
            status, body = self.responses[path]
            return status, body.encode("utf-8")
        return 404, b'{"message":"Not Found"}'


class ExplodingTransport:
    def request(self, method: str, url: str, headers: dict, timeout: float) -> tuple[int, bytes]:
        raise evidence_mod.EvidenceTransportError("connection refused")


def _workflow_yaml(
    *,
    model: str = "opencode-go/space-bunny",
    variant: str = "max",
    agent: str | None = None,
    trust_gate: bool = True,
) -> str:
    if trust_gate:
        condition = (
            'contains(fromJSON(\'["OWNER", "MEMBER", "COLLABORATOR"]\'), '
            "github.event.comment.author_association) && ("
            'contains(fromJSON(\'["OWNER", "MEMBER", "COLLABORATOR"]\'), '
            "github.event.issue.author_association || "
            "github.event.pull_request.author_association)"
        )
    else:
        condition = "true"
    job = {
        "if": condition,
        "steps": [
            {
                "name": "Run opencode",
                "env": {
                    "MODEL": model,
                    "VARIANT": variant,
                    "AGENT": "foundry-reviewer" if agent is None else agent,
                },
            }
        ],
    }
    return yaml.safe_dump(
        {
            "on": {"issue_comment": {"types": ["created"]}},
            "jobs": {
                "opencode": {"if": "false", "steps": []},
                "opencode-bunny-review": job,
            },
        }
    )


def _agent_markdown(*, read_only: bool = True) -> str:
    if read_only:
        permission = {"edit": "deny", "bash": {"*": "deny"}, "task": "deny"}
    else:
        permission = {"edit": "allow", "bash": {"*": "allow"}, "task": "allow"}
    frontmatter = {
        "model": "opencode-go/space-bunny",
        "variant": "max",
        "permission": permission,
    }
    return "---\n" + yaml.safe_dump(frontmatter) + "---\n\nReview read-only.\n"


def _result_body(
    *,
    run_id: int = RUN_DIRECT,
    footer_run_id: int | None = None,
    **overrides: str,
) -> str:
    fields = {
        "REVIEWER_MODEL": "opencode-go/space-bunny",
        "REVIEWER_VARIANT": "max",
        "REVIEW_AGENT": "foundry-reviewer",
        "REVIEWED_SHA": IMPL,
        "REVIEWED_TREE": IMPL_TREE,
        "REVIEW_VERDICT": "PASS",
        "READ_ONLY": "true",
    }
    fields.update(overrides)
    footer = run_id if footer_run_id is None else footer_run_id
    lines = [
        evidence_mod.MARKER_DIRECT,
        "",
        "Read-only fresh-context Space Bunny review of the exact SHA/TREE.",
        "",
        *(f"{key}: {value}" for key, value in fields.items()),
        "",
        f"[github run](https://github.com/{REPO}/actions/runs/{footer})",
    ]
    return "\n".join(lines)


def _run_payload(run_id: int, **overrides: object) -> dict:
    payload = {
        "id": run_id,
        "repository": {"full_name": REPO},
        "event": "issue_comment",
        "path": WORKFLOW_PATH,
        "status": "completed",
        "conclusion": "success",
        "head_sha": WORKFLOW_HEAD,
        "run_started_at": RUN_STARTED,
        "updated_at": RUN_UPDATED,
    }
    payload.update(overrides)
    return payload


def _graph(
    *,
    trigger_association: str = "OWNER",
    trigger_body: str | None = None,
    trigger_created_at: str = TRIGGER_AT,
    result_login: str = "opencode-agent[bot]",
    result_body: str | None = None,
    result_created_at: str = RESULT_AT,
    run_conclusion: str = "success",
    run_started_at: str | None = RUN_STARTED,
    run_updated_at: str | None = RUN_UPDATED,
    job_conclusion: str = "success",
    implementation_lane: str = "skipped",
    workflow_yaml: str | None = None,
    agent_markdown: str | None = None,
    extra_comments: list[dict] | None = None,
) -> FakeGitHub:
    trigger = trigger_body if trigger_body is not None else "/bunny-review review this"
    body = result_body if result_body is not None else _result_body()
    run_overrides: dict[str, object] = {}
    if run_started_at is not None:
        run_overrides["run_started_at"] = run_started_at
    if run_updated_at is not None:
        run_overrides["updated_at"] = run_updated_at
    fake = FakeGitHub()
    issue_url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}"
    fake.add_json(
        f"/repos/{REPO}/issues/comments/{TRIGGER_DIRECT}",
        {
            "id": TRIGGER_DIRECT,
            "issue_url": issue_url,
            "author_association": trigger_association,
            "body": trigger,
            "created_at": trigger_created_at,
        },
    )
    fake.add_json(
        f"/repos/{REPO}/issues/comments/{RESULT_DIRECT}",
        {
            "id": RESULT_DIRECT,
            "issue_url": issue_url,
            "user": {"login": result_login, "type": "Bot"},
            "body": body,
            "created_at": result_created_at,
        },
    )
    fake.add_json(
        f"/repos/{REPO}/actions/runs/{RUN_DIRECT}",
        _run_payload(RUN_DIRECT, conclusion=run_conclusion, **run_overrides),
    )
    jobs = [
        {
            "id": JOB_DIRECT,
            "name": "opencode-bunny-review",
            "status": "completed",
            "conclusion": job_conclusion,
        },
        {
            "id": 2,
            "name": "opencode",
            "status": "completed",
            "conclusion": implementation_lane,
        },
        {
            "id": 3,
            "name": "opencode-bunny",
            "status": "completed",
            "conclusion": implementation_lane,
        },
    ]
    fake.add_json(f"/repos/{REPO}/actions/runs/{RUN_DIRECT}/jobs?per_page=100", {"jobs": jobs})
    comments = [
        {
            "id": TRIGGER_DIRECT,
            "created_at": trigger_created_at,
            "user": {"login": "maintainer"},
            "body": trigger,
        },
        {
            "id": RESULT_DIRECT,
            "created_at": result_created_at,
            "user": {"login": "opencode-agent[bot]"},
            "body": body,
        },
        *(extra_comments or []),
    ]
    fake.add_json(
        f"/repos/{REPO}/issues/{ISSUE}/comments?per_page=100&sort=created&direction=desc",
        comments,
    )
    fake.add_raw(
        f"/repos/{REPO}/contents/{WORKFLOW_PATH}?ref={WORKFLOW_HEAD}",
        workflow_yaml if workflow_yaml is not None else _workflow_yaml(),
    )
    fake.add_raw(
        f"/repos/{REPO}/contents/.opencode/agents/foundry-reviewer.md?ref={WORKFLOW_HEAD}",
        agent_markdown if agent_markdown is not None else _agent_markdown(),
    )
    return fake


def _serve_run(fake: FakeGitHub, run_id: int, job_id: int, *, job_name: str) -> None:
    """Serve a coherent second run so only run-link binding can reject it."""
    fake.add_json(f"/repos/{REPO}/actions/runs/{run_id}", _run_payload(run_id))
    fake.add_json(
        f"/repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100",
        {
            "jobs": [
                {"id": job_id, "name": job_name, "status": "completed", "conclusion": "success"},
                {"id": 21, "name": "opencode", "status": "completed", "conclusion": "skipped"},
                {
                    "id": 22,
                    "name": "opencode-bunny",
                    "status": "completed",
                    "conclusion": "skipped",
                },
            ]
        },
    )


def _record(**overrides: object) -> dict:
    record = {
        "schema_version": "1.0",
        "record_type": "cross_executor_review",
        "required": True,
        "materiality": "MATERIAL",
        "logical_profile": "space-bunny",
        "resolved_provider": "opencode-go",
        "resolved_model_id": "opencode-go/space-bunny",
        "model_alias_class": "CANONICAL",
        "native_variant": "max",
        "review_mode": "READ_ONLY_FRESH_CONTEXT",
        "review_agent": "foundry-reviewer",
        "reviewed_sha": IMPL,
        "reviewed_tree": IMPL_TREE,
        "verdict": "PASS",
        "findings": {"P1": [], "P2": [], "P3": []},
        "implementation_executor": "deepseek",
        "review_executor": "space-bunny",
        "review_evidence": {
            "schema_version": "1.0",
            "carrier": evidence_mod.CARRIER_DIRECT,
            "repository": REPO,
            "trigger_issue_number": ISSUE,
            "trigger_comment_id": TRIGGER_DIRECT,
            "result_comment_id": RESULT_DIRECT,
            "workflow_run_id": RUN_DIRECT,
            "workflow_job_id": JOB_DIRECT,
            "workflow_job_name": "opencode-bunny-review",
            "workflow_head_sha": WORKFLOW_HEAD,
            "workflow_path": WORKFLOW_PATH,
            "marker": evidence_mod.MARKER_DIRECT,
        },
    }
    record.update(overrides)
    return record


def _state_doc(**overrides: object) -> dict:
    doc = {
        "schema_version": "2.0",
        "repository": REPO,
        "branch": "opencode/issue578-20261006204641",
        "audit_base_sha": AUDIT_BASE,
        "validated_head": IMPL,
        "validated_tree": IMPL_TREE,
        "materiality": "MATERIAL",
        "cross_executor_review": {
            "required": True,
            "logical_profile": "space-bunny",
            "implementation_executor": "deepseek",
            "review_executor": "space-bunny",
            "reviewed_sha": IMPL,
            "reviewed_tree": IMPL_TREE,
            "verdict": "PASS",
            "review_record_path": None,
        },
    }
    doc.update(overrides)
    return doc


def _verify(record: dict, fake: FakeGitHub | None = None):
    return evidence_mod.verify_review_evidence(
        record,
        expected_repository=REPO,
        transport=fake or _graph(),
    )


# --- structural / required --------------------------------------------------


def test_missing_review_evidence_is_structurally_invalid() -> None:
    record = _record()
    record.pop("review_evidence")
    errors = review_mod.validate_review_record(record)
    assert any("review_evidence" in error for error in errors)


def test_review_evidence_unknown_fields_fail_closed() -> None:
    record = _record()
    record["review_evidence"]["sneaky"] = True
    errors = review_mod.validate_review_record(record)
    assert any("unknown fields" in error for error in errors)


def test_self_asserted_record_without_evidence_never_satisfies_gate() -> None:
    record = _record()
    record.pop("review_evidence")
    result = review_mod.evaluate_review_gate(
        _state_doc(), review_record=record, evidence_transport=FakeGitHub()
    )
    assert result.status == "UNSATISFIED"
    assert any("REVIEW_RECORD_INVALID" in reason for reason in result.reasons)


def test_fabricated_record_with_unverifiable_evidence_never_satisfies_gate() -> None:
    """A record with correct-looking Bunny fields but fake IDs fails closed."""
    result = review_mod.evaluate_review_gate(
        _state_doc(), review_record=_record(), evidence_transport=FakeGitHub()
    )
    assert result.status != "SATISFIED"
    assert any("REVIEW_EVIDENCE" in reason for reason in result.reasons)


# --- the writable bootstrap carrier is removed -------------------------------


def test_bootstrap_writable_carrier_is_removed() -> None:
    """P1-b control: no carrier may rest on a writable top-level review."""
    assert evidence_mod.CARRIERS == (evidence_mod.CARRIER_DIRECT,)
    assert not hasattr(evidence_mod, "CARRIER_BOOTSTRAP")
    assert not hasattr(evidence_mod, "MARKER_BOOTSTRAP")

    record = _record()
    record["review_evidence"]["carrier"] = "BOOTSTRAP_ISSUE_COMMENT"
    errors = review_mod.validate_review_record(record)
    assert any("carrier" in error for error in errors)

    verifier_doc = (REPO_ROOT / ".opencode" / "agents" / "bunny-verifier.md").read_text(
        encoding="utf-8"
    )
    assert "BUNNY_AUDITOR_SUBAGENT_REVIEW" not in verifier_doc
    assert "REVIEW_VERDICT:" not in verifier_doc

    auditor_doc = (REPO_ROOT / ".opencode" / "agents" / "bunny-auditor.md").read_text(
        encoding="utf-8"
    )
    assert "BUNNY_AUDITOR_SUBAGENT_REVIEW" not in auditor_doc


# --- trusted direct lane satisfies ------------------------------------------


def test_consistent_direct_lane_evidence_is_satisfied() -> None:
    result = _verify(_record())
    assert result.ok, result.reasons
    assert any("foundry-reviewer" in check for check in result.checks)
    assert any("run_trigger" in check for check in result.checks)


def test_gate_satisfied_only_with_verified_evidence_transport() -> None:
    result = review_mod.evaluate_review_gate(
        _state_doc(), review_record=_record(), evidence_transport=_graph()
    )
    assert result.status == "SATISFIED", result.reasons


# --- run binding -------------------------------------------------------------


def test_result_comment_linking_foreign_run_is_unsatisfied() -> None:
    """P1-a wrong-reason control: a bot comment linking a foreign run fails."""
    fake = _graph(result_body=_result_body(footer_run_id=999999))
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_RUN_LINK_MISMATCH" in result.reasons[0]


def test_evidence_citing_foreign_run_is_unsatisfied() -> None:
    """A fully valid foreign run is not credited when the footer is another run."""
    foreign_run = 999999
    foreign_job = 999998
    fake = _graph()
    _serve_run(fake, foreign_run, foreign_job, job_name="opencode-bunny-review")
    record = _record()
    record["review_evidence"]["workflow_run_id"] = foreign_run
    record["review_evidence"]["workflow_job_id"] = foreign_job
    result = _verify(record, fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_RUN_LINK_MISMATCH" in result.reasons[0]


def test_result_comment_outside_run_window_is_unsatisfied() -> None:
    """The receipt comment must have been produced by the cited run."""
    fake = _graph(result_created_at="2026-10-06T19:00:00Z")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_TIME_WINDOW" in result.reasons[0]

    fake = _graph(result_created_at="2026-10-06T21:00:00Z")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_TIME_WINDOW" in result.reasons[0]


def test_run_without_time_window_is_unsatisfiable() -> None:
    fake = _graph(run_started_at="")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RUN_TIME_MISSING" in result.reasons[0]

    fake = _graph(run_updated_at="")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RUN_TIME_MISSING" in result.reasons[0]


def test_run_must_be_triggered_by_the_trigger_comment() -> None:
    """Another issue comment between trigger and run start breaks the binding."""
    fake = _graph(
        extra_comments=[
            {
                "id": TRIGGER_DIRECT + 1,
                "created_at": "2026-10-06T20:00:03Z",
                "user": {"login": "other"},
                "body": "/bunny-review from another comment",
            }
        ]
    )
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RUN_TRIGGER_MISMATCH" in result.reasons[0]


def test_run_cannot_precede_its_trigger_comment() -> None:
    fake = _graph(trigger_created_at="2026-10-06T20:01:00Z")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RUN_TRIGGER_ORDER" in result.reasons[0]


def test_missing_issue_comments_list_is_unverifiable() -> None:
    fake = _graph()
    fake.responses.pop(
        f"/repos/{REPO}/issues/{ISSUE}/comments?per_page=100&sort=created&direction=desc"
    )
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_ISSUE_COMMENTS_MISSING" in result.reasons[0]


# --- fabricated / inconsistent external evidence ----------------------------


def test_nonexistent_run_comment_or_job_fails() -> None:
    fake = _graph()
    fake.responses.pop(f"/repos/{REPO}/actions/runs/{RUN_DIRECT}")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RUN_MISSING" in result.reasons[0]

    fake = _graph()
    fake.responses.pop(f"/repos/{REPO}/issues/comments/{TRIGGER_DIRECT}")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_TRIGGER_COMMENT_MISSING" in result.reasons[0]

    fake = _graph()
    fake.add_json(
        f"/repos/{REPO}/actions/runs/{RUN_DIRECT}/jobs?per_page=100",
        {"jobs": [{"id": 1, "name": "opencode", "conclusion": "skipped"}]},
    )
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_JOB_MISSING" in result.reasons[0]


def test_deepseek_workflow_evidence_fails() -> None:
    """The workflow at the run head must pin Space Bunny, not DeepSeek."""
    fake = _graph(workflow_yaml=_workflow_yaml(model="opencode-go/deepseek-v4.1-flash"))
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_WORKFLOW_MODEL_MISMATCH" in result.reasons[0]


def test_bunny_job_failed_or_skipped_fails() -> None:
    for conclusion in ("failure", "skipped"):
        fake = _graph(job_conclusion=conclusion)
        result = _verify(_record(), fake)
        assert not result.ok, conclusion
        assert "REVIEW_EVIDENCE_JOB_NOT_SUCCESS" in result.reasons[0]


def test_direct_lane_rejects_successful_implementation_lane() -> None:
    fake = _graph(implementation_lane="success")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_IMPLEMENTATION_LANE_RAN" in result.reasons[0]


def test_untrusted_trigger_comment_fails() -> None:
    fake = _graph(trigger_association="NONE")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_TRIGGER_COMMENTER_UNTRUSTED" in result.reasons[0]


def test_trigger_comment_for_wrong_carrier_fails() -> None:
    fake = _graph(trigger_body="/bunny audit this")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_TRIGGER_CARRIER_MISMATCH" in result.reasons[0]


def test_result_comment_from_wrong_author_fails() -> None:
    fake = _graph(result_login="random-user")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_AUTHOR_UNTRUSTED" in result.reasons[0]


def test_result_run_link_mismatch_fails() -> None:
    body = _result_body(footer_run_id=999999)
    fake = _graph(result_body=body)
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_RUN_LINK_MISMATCH" in result.reasons[0]


def test_result_marker_missing_fails() -> None:
    body = _result_body().replace(evidence_mod.MARKER_DIRECT, "SOME_OTHER_MARKER")
    fake = _graph(result_body=body)
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_MARKER_MISSING" in result.reasons[0]


def test_result_reviewed_sha_or_tree_mismatch_fails() -> None:
    for key, value in (("REVIEWED_SHA", "f" * 40), ("REVIEWED_TREE", "e" * 40)):
        fake = _graph(result_body=_result_body(**{key: value}))
        result = _verify(_record(), fake)
        assert not result.ok, key
        assert "REVIEW_EVIDENCE_RESULT_FIELD_MISMATCH" in result.reasons[0]


def test_result_verdict_mismatch_fails() -> None:
    fake = _graph(result_body=_result_body(REVIEW_VERDICT="UNKNOWN"))
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_FIELD_MISMATCH" in result.reasons[0]


def test_result_read_only_false_fails() -> None:
    fake = _graph(result_body=_result_body(READ_ONLY="false"))
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_NOT_READ_ONLY" in result.reasons[0]


def test_workflow_variant_or_agent_mismatch_fails() -> None:
    fake = _graph(workflow_yaml=_workflow_yaml(variant="high"))
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_WORKFLOW_VARIANT_MISMATCH" in result.reasons[0]

    fake = _graph(workflow_yaml=_workflow_yaml(agent="bunny-verifier"))
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_WORKFLOW_AGENT_MISMATCH" in result.reasons[0]


def test_workflow_without_trust_gate_fails() -> None:
    fake = _graph(workflow_yaml=_workflow_yaml(trust_gate=False))
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_WORKFLOW_TRUST_GATE_MISSING" in result.reasons[0]


def test_workflow_with_bot_author_exception_fails() -> None:
    """The read-only lane must match the other lanes' thread-author gate."""
    condition = (
        'contains(fromJSON(\'["OWNER", "MEMBER", "COLLABORATOR"]\'), '
        "github.event.comment.author_association) && ("
        'contains(fromJSON(\'["OWNER", "MEMBER", "COLLABORATOR"]\'), '
        "github.event.issue.author_association) || "
        "github.event.issue.user.login == 'opencode-agent[bot]')"
    )
    workflow = yaml.safe_load(_workflow_yaml())
    workflow["jobs"]["opencode-bunny-review"]["if"] = condition
    fake = _graph(workflow_yaml=yaml.safe_dump(workflow))
    result = _verify(_record(), fake)
    # The verifier itself rejects a workflow that exempts bot-authored threads
    # from the target trust gate.
    assert not result.ok
    assert "REVIEW_EVIDENCE_WORKFLOW_BOT_THREAD_EXCEPTION" in result.reasons[0]


def test_unparseable_workflow_or_missing_result_field_fails() -> None:
    fake = _graph(workflow_yaml="jobs: [unclosed")
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_WORKFLOW_UNPARSEABLE" in result.reasons[0]

    body = _result_body().replace("REVIEWED_TREE:", "TREE_MISSING:")
    fake = _graph(result_body=body)
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_RESULT_FIELD_MISSING" in result.reasons[0]


def test_reviewer_agent_file_not_read_only_fails() -> None:
    fake = _graph(agent_markdown=_agent_markdown(read_only=False))
    result = _verify(_record(), fake)
    assert not result.ok
    assert "REVIEW_EVIDENCE_AGENT_NOT_READ_ONLY" in result.reasons[0]


def test_writable_verifier_agent_name_is_rejected() -> None:
    record = _record()
    record["review_agent"] = "bunny-verifier"
    errors = review_mod.validate_review_record(record)
    assert any("structurally read-only reviewer" in error for error in errors)

    record = _record()
    record["review_agent"] = "bunny-auditor"
    errors = review_mod.validate_review_record(record)
    assert any("structurally read-only reviewer" in error for error in errors)

    record = _record()
    record["review_agent"] = "foundry-reviewer"
    fake = _graph()
    result = _verify(record, fake)
    assert result.ok, result.reasons


def test_repository_mismatch_fails() -> None:
    record = _record()
    record["review_evidence"]["repository"] = "attacker/other-repo"
    result = evidence_mod.verify_review_evidence(
        record, expected_repository=REPO, transport=_graph()
    )
    assert not result.ok
    assert "REVIEW_EVIDENCE_REPOSITORY_MISMATCH" in result.reasons[0]


def test_non_pass_record_has_no_verifiable_evidence() -> None:
    record = _record(verdict="FAIL")
    result = _verify(record, _graph())
    assert not result.ok
    assert "REVIEW_EVIDENCE_RECORD_NOT_PASS" in result.reasons[0]


def test_network_failure_is_unverifiable_never_satisfied() -> None:
    result = evidence_mod.verify_review_evidence(
        _record(), expected_repository=REPO, transport=ExplodingTransport()
    )
    assert result.status == evidence_mod.UNVERIFIABLE
    assert not result.ok


def test_gate_rejects_record_pointing_at_deepseek_run_evidence() -> None:
    """Even a structurally valid record cannot satisfy a DeepSeek run."""
    fake = _graph(workflow_yaml=_workflow_yaml(model="opencode-go/deepseek-v4.1-flash"))
    result = review_mod.evaluate_review_gate(
        _state_doc(), review_record=_record(), evidence_transport=fake
    )
    assert result.status != "SATISFIED"
    assert any("WORKFLOW_MODEL_MISMATCH" in reason for reason in result.reasons)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record["review_evidence"].update({"trigger_comment_id": 999999999}),
        lambda record: record["review_evidence"].update({"result_comment_id": 999999999}),
        lambda record: record["review_evidence"].update({"workflow_run_id": 999999999}),
        lambda record: record["review_evidence"].update({"workflow_job_id": 999999999}),
    ],
    ids=["trigger", "result", "run", "job"],
)
def test_fake_external_identifier_fails_closed(mutate) -> None:
    record = _record()
    mutate(record)
    result = _verify(record, _graph())
    assert not result.ok
