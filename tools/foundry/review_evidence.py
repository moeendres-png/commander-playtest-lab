"""Trusted external evidence for a cross-executor Space Bunny review record.

A review record is authored by the implementation executor, so a PASS verdict
inside it proves nothing by itself. This module binds a PASS record to
independently verifiable GitHub evidence produced by the single trusted
read-only OpenCode workflow lane: a trusted issue comment selected the
``/bunny-review`` lane, the workflow run and its expected job succeeded, the
workflow file at the run's exact ``head_sha`` pins Space Bunny MAX and the
structurally read-only ``foundry-reviewer`` agent, and the OpenCode bot's
result comment carries the machine-parseable marker and the exact reviewed
identifiers/verdict.

The receipt is bound to the run, not merely embedded in its text:

- the result comment's ``created_at`` must fall inside that run's
  ``run_started_at..updated_at`` window;
- the run must have been triggered by the evidence's trigger comment: the
  trigger comment precedes the run start and is the newest issue comment on the
  thread created before it (no other issue comment could have started the run);
- the result comment's last ``/actions/runs/{id}`` link must be the cited run,
  so a quoted or foreign run link elsewhere in the body is never credited.

The pinned CLI ignores ``AGENT`` (#654), so the workflow pin is admitted only
when the job selects the reviewer through ``OPENCODE_CONFIG_CONTENT`` and runs
the trusted ``review_runtime_identity.py`` preflight and post-run audit, and the
committed config merged with the reviewer's rules leaves no write-capable
permission allowed.

Only ``DIRECT_REVIEW_LANE`` (``opencode-bunny-review`` / ``foundry-reviewer``)
is admitted. The former writable ``opencode-bunny``/``bunny-verifier``
attestation carrier is removed: a review that can write is not review evidence.

The verifier performs read-only GitHub REST reads through a dependency-injected
transport. Production defaults to ``urllib`` against ``api.github.com``; a
``GH_TOKEN``/``GITHUB_TOKEN`` in the environment may raise the rate limit, but
its absence never turns a failed, unparseable or missing lookup into PASS.
Every network/API/parse failure is ``UNVERIFIABLE`` or ``UNSATISFIED``, never
``SATISFIED``. Secret values are never printed or stored.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

try:
    from . import review_runtime_identity as runtime_identity
except ImportError:  # loaded as a top-level module from tools/foundry
    import review_runtime_identity as runtime_identity  # type: ignore[no-redef,import-not-found]

SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"
UNVERIFIABLE = "UNVERIFIABLE"

EVIDENCE_SCHEMA_VERSION = "1.0"

# Only the structurally read-only direct lane is admitted. There is no carrier
# for a review produced by a writable top-level agent.
CARRIER_DIRECT = "DIRECT_REVIEW_LANE"
CARRIERS = (CARRIER_DIRECT,)

MARKER_DIRECT = "BUNNY_DIRECT_READ_ONLY_REVIEW"
CARRIER_MARKERS = {CARRIER_DIRECT: MARKER_DIRECT}

DIRECT_JOB_NAME = "opencode-bunny-review"
CARRIER_JOB_NAMES = {CARRIER_DIRECT: DIRECT_JOB_NAME}
# Top-level agent pinned by the trusted workflow lane.
CARRIER_TOP_LEVEL_AGENTS = {CARRIER_DIRECT: ("foundry-reviewer",)}
# Agent attested by the result comment: the fresh-context read-only reviewer.
CARRIER_REVIEW_AGENTS = {CARRIER_DIRECT: "foundry-reviewer"}
# Lanes that must NOT be the successful lane for the carrier to count.
INCOMPATIBLE_LANE_JOBS = ("opencode", "opencode-bunny")
READ_ONLY_AGENT_FILES = {"foundry-reviewer": ".opencode/agents/foundry-reviewer.md"}
PROJECT_CONFIG_PATH = "opencode.json"
# Run log the watchdog copies for the runtime audit (review_runtime_identity.py).
RUNTIME_LOG = '"$RUNNER_TEMP/opencode-review.log"'
RUNTIME_CHECKER = "tools/foundry/review_runtime_identity.py"

TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
OPENCODE_BOT_LOGINS = frozenset({"opencode-agent[bot]", "opencode-agent"})
TRUSTED_WORKFLOW_PATH = ".github/workflows/opencode.yml"
TRUSTED_MODEL_ID = "opencode-go/space-bunny"
NATIVE_VARIANT = "max"
PASS_VERDICT = "PASS"

REQUIRED_EVIDENCE_FIELDS = (
    "schema_version",
    "carrier",
    "repository",
    "trigger_issue_number",
    "trigger_comment_id",
    "result_comment_id",
    "workflow_run_id",
    "workflow_job_id",
    "workflow_job_name",
    "workflow_head_sha",
    "workflow_path",
    "marker",
)
INTEGER_EVIDENCE_FIELDS = (
    "trigger_issue_number",
    "trigger_comment_id",
    "result_comment_id",
    "workflow_run_id",
    "workflow_job_id",
)
RESULT_FIELD_KEYS = (
    "REVIEWER_MODEL",
    "REVIEWER_VARIANT",
    "REVIEW_AGENT",
    "REVIEWED_SHA",
    "REVIEWED_TREE",
    "REVIEW_VERDICT",
    "READ_ONLY",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?/[A-Za-z0-9._-]+$")
_ISSUE_URL_RE = re.compile(r"/repos/[^/]+/[^/]+/issues/(\d+)$")


class EvidenceTransportError(RuntimeError):
    """Transport-level failure; always fail closed, never PASS."""


class EvidenceTransport(Protocol):
    """Minimal dependency-injected HTTP transport for tests."""

    def request(
        self, method: str, url: str, headers: Mapping[str, str], timeout: float
    ) -> tuple[int, bytes]:  # pragma: no cover - protocol
        ...


class UrllibTransport:
    """Production read-only transport; no credentials are ever logged."""

    def request(
        self, method: str, url: str, headers: Mapping[str, str], timeout: float
    ) -> tuple[int, bytes]:
        request = urllib.request.Request(url, method=method, headers=dict(headers))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return int(getattr(response, "status", 200)), response.read()
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read()
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise EvidenceTransportError(type(exc).__name__) from exc


@dataclass(frozen=True)
class GitHubEvidenceClient:
    """Read-only GitHub REST client with an injected transport."""

    transport: EvidenceTransport
    base_url: str = "https://api.github.com"
    token: str | None = None
    timeout: float = 20.0

    def _headers(self, accept: str) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "commander-foundry-review-evidence",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get(self, path: str, accept: str) -> tuple[int, str]:
        url = f"{self.base_url}{path}"
        status, body = self.transport.request("GET", url, self._headers(accept), self.timeout)
        return status, body.decode("utf-8", "replace")

    def get_json(self, path: str) -> tuple[int, Any]:
        status, text = self._get(path, "application/vnd.github+json")
        if status != 200:
            return status, None
        try:
            import json

            return status, json.loads(text)
        except ValueError as exc:
            raise EvidenceTransportError("unparseable JSON") from exc

    def get_raw(self, path: str) -> tuple[int, str]:
        return self._get(path, "application/vnd.github.raw+json")


def default_client(
    *,
    transport: EvidenceTransport | None = None,
    token: str | None = None,
) -> GitHubEvidenceClient:
    """Build the production client; a token only raises the rate limit."""
    if token is None:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or None
    return GitHubEvidenceClient(transport=transport or UrllibTransport(), token=token)


@dataclass(frozen=True)
class ReviewEvidenceResult:
    status: str
    reasons: tuple[str, ...]
    checks: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == SATISFIED

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "ok": self.ok,
            "reasons": list(self.reasons),
            "checks": list(self.checks),
        }


class _EvidenceFailure(Exception):
    def __init__(self, code: str, detail: str, *, unverifiable: bool = False) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.unverifiable = unverifiable


def validate_evidence_shape(value: Any) -> list[str]:
    """Structural validation only: no network I/O, every deviation fails closed."""
    if not isinstance(value, dict):
        return ["review_evidence must be a mapping"]
    errors: list[str] = []
    unknown = sorted(set(value) - set(REQUIRED_EVIDENCE_FIELDS))
    if unknown:
        errors.append(f"review_evidence has unknown fields: {unknown}")
    for field in REQUIRED_EVIDENCE_FIELDS:
        if field not in value:
            errors.append(f"review_evidence missing required field {field!r}")
    if value.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(f"review_evidence.schema_version must be {EVIDENCE_SCHEMA_VERSION!r}")
    carrier = value.get("carrier")
    if carrier not in CARRIERS:
        errors.append(f"review_evidence.carrier must be one of {list(CARRIERS)}")
    repository = value.get("repository")
    if not isinstance(repository, str) or not _REPO_RE.match(repository):
        errors.append("review_evidence.repository must be an owner/name slug")
    for field in INTEGER_EVIDENCE_FIELDS:
        item = value.get(field)
        if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
            errors.append(f"review_evidence.{field} must be a positive integer")
    head_sha = value.get("workflow_head_sha")
    if not isinstance(head_sha, str) or not _SHA_RE.match(head_sha):
        errors.append("review_evidence.workflow_head_sha must be a 40-hex commit")
    if value.get("workflow_path") != TRUSTED_WORKFLOW_PATH:
        errors.append(f"review_evidence.workflow_path must be {TRUSTED_WORKFLOW_PATH!r}")
    if (
        carrier in CARRIER_JOB_NAMES
        and value.get("workflow_job_name") != CARRIER_JOB_NAMES[carrier]
    ):
        errors.append(
            f"review_evidence.workflow_job_name must be {CARRIER_JOB_NAMES[carrier]!r} "
            f"for carrier {carrier!r}"
        )
    if carrier in CARRIER_MARKERS and value.get("marker") != CARRIER_MARKERS[carrier]:
        errors.append(
            f"review_evidence.marker must be {CARRIER_MARKERS[carrier]!r} for carrier {carrier!r}"
        )
    return errors


def _field(body: str, key: str) -> str | None:
    match = re.search(rf"(?mi)^[\s>\-*]*{re.escape(key)}\s*[:=]\s*(.+?)\s*$", body)
    if match is None:
        return None
    return match.group(1).strip().strip("`*\"'[]()")


def _has_marker(body: str, marker: str) -> bool:
    return re.search(rf"(?m)^\s*{re.escape(marker)}\s*$", body) is not None


def _selects(body: str, mention: str) -> bool:
    # Mirrors the workflow `contains(body, ' /x') || startsWith(body, '/x')` gate.
    return body.startswith(mention) or f" {mention}" in body


def _issue_number_from_url(url: Any) -> int | None:
    match = _ISSUE_URL_RE.search(str(url or ""))
    return int(match.group(1)) if match else None


def _parse_utc(value: Any) -> datetime | None:
    """Parse a GitHub ISO-8601 timestamp; anything unparseable stays None."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class _Verifier:
    def __init__(
        self,
        record: Mapping[str, Any],
        evidence: dict,
        client: GitHubEvidenceClient,
        *,
        expected_repository: str | None,
    ) -> None:
        self.record = record
        self.evidence = evidence
        self.client = client
        self.checks: list[str] = []
        self.repository = str(evidence["repository"])
        self.carrier = str(evidence["carrier"])
        self.expected_repository = expected_repository
        self.trigger_comment: dict[str, Any] | None = None
        self.run_started: datetime | None = None
        self.run_updated: datetime | None = None
        self._run_link_re = re.compile(
            re.escape(f"https://github.com/{self.repository}/actions/runs/") + r"(\d+)"
        )

    def verify_repository(self) -> None:
        if self.expected_repository and self.expected_repository != self.repository:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_REPOSITORY_MISMATCH",
                f"evidence repository {self.repository!r} != expected {self.expected_repository!r}",
            )
        self.checks.append(f"repository:{self.repository}")

    # -- helpers ---------------------------------------------------------

    def _get_json(self, path: str, code: str) -> Any:
        try:
            status, payload = self.client.get_json(path)
        except EvidenceTransportError as exc:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_UNVERIFIABLE", f"{code} API read failed ({exc})", unverifiable=True
            ) from exc
        if status != 200 or not isinstance(payload, (dict, list)):
            raise _EvidenceFailure(code, f"GitHub API returned status {status}")
        return payload

    def _get_raw(self, path: str, code: str) -> str:
        try:
            status, text = self.client.get_raw(path)
        except EvidenceTransportError as exc:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_UNVERIFIABLE", f"{code} API read failed ({exc})", unverifiable=True
            ) from exc
        if status != 200 or not text.strip():
            raise _EvidenceFailure(code, f"GitHub API returned status {status}")
        return text

    # -- verification steps ---------------------------------------------

    def verify_trigger_comment(self) -> None:
        comment_id = int(self.evidence["trigger_comment_id"])
        issue_number = int(self.evidence["trigger_issue_number"])
        comment = self._get_json(
            f"/repos/{self.repository}/issues/comments/{comment_id}",
            "REVIEW_EVIDENCE_TRIGGER_COMMENT_MISSING",
        )
        if not isinstance(comment, dict):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_TRIGGER_COMMENT_MISSING", "trigger comment is not an object"
            )
        if _issue_number_from_url(comment.get("issue_url")) != issue_number:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_TRIGGER_ISSUE_MISMATCH",
                f"trigger comment {comment_id} is not on issue/PR {issue_number}",
            )
        if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_TRIGGER_COMMENTER_UNTRUSTED",
                f"trigger comment association {comment.get('author_association')!r}",
            )
        body = str(comment.get("body") or "")
        if not _selects(body, "/bunny-review"):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_TRIGGER_CARRIER_MISMATCH",
                "trigger comment does not select the /bunny-review carrier",
            )
        self.trigger_comment = comment
        self.checks.append(
            f"trigger_comment:{comment_id}:trusted:{comment.get('author_association')}"
        )

    def verify_result_comment(self) -> None:
        comment_id = int(self.evidence["result_comment_id"])
        issue_number = int(self.evidence["trigger_issue_number"])
        run_id = int(self.evidence["workflow_run_id"])
        marker = str(self.evidence["marker"])
        comment = self._get_json(
            f"/repos/{self.repository}/issues/comments/{comment_id}",
            "REVIEW_EVIDENCE_RESULT_COMMENT_MISSING",
        )
        if not isinstance(comment, dict):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RESULT_COMMENT_MISSING", "result comment is not an object"
            )
        if _issue_number_from_url(comment.get("issue_url")) != issue_number:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RESULT_ISSUE_MISMATCH",
                f"result comment {comment_id} is not on issue/PR {issue_number}",
            )
        login = str((comment.get("user") or {}).get("login") or "")
        if login not in OPENCODE_BOT_LOGINS:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RESULT_AUTHOR_UNTRUSTED",
                f"result comment author {login!r} is not the OpenCode bot",
            )
        created_at = _parse_utc(comment.get("created_at"))
        if (
            created_at is None
            or self.run_started is None
            or self.run_updated is None
            or created_at < self.run_started
            or created_at > self.run_updated
        ):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RESULT_TIME_WINDOW",
                f"result comment {comment_id} created_at {comment.get('created_at')!r} is "
                f"outside run {run_id} window {self.run_started}..{self.run_updated}",
            )
        body = str(comment.get("body") or "")
        run_links = self._run_link_re.findall(body)
        if not run_links or int(run_links[-1]) != run_id:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RESULT_RUN_LINK_MISMATCH",
                f"result comment {comment_id} must end with its own run link "
                f"https://github.com/{self.repository}/actions/runs/{run_id}; "
                f"last run link was {run_links[-1] if run_links else None!r}",
            )
        if not _has_marker(body, marker):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RESULT_MARKER_MISSING",
                f"result comment lacks marker {marker}",
            )
        fields: dict[str, str] = {}
        for key in RESULT_FIELD_KEYS:
            value = _field(body, key)
            if value is None:
                raise _EvidenceFailure(
                    "REVIEW_EVIDENCE_RESULT_FIELD_MISSING",
                    f"result comment lacks machine-readable {key}",
                )
            fields[key] = value
        expected_agent = CARRIER_REVIEW_AGENTS[self.carrier]
        record_agent = str(self.record.get("review_agent") or "")
        expected = {
            "REVIEWER_MODEL": str(self.record.get("resolved_model_id") or ""),
            "REVIEWER_VARIANT": str(self.record.get("native_variant") or ""),
            "REVIEW_AGENT": expected_agent,
            "REVIEWED_SHA": str(self.record.get("reviewed_sha") or ""),
            "REVIEWED_TREE": str(self.record.get("reviewed_tree") or ""),
            "REVIEW_VERDICT": str(self.record.get("verdict") or ""),
        }
        for key, want in expected.items():
            got = fields[key]
            if got != want:
                raise _EvidenceFailure(
                    "REVIEW_EVIDENCE_RESULT_FIELD_MISMATCH",
                    f"result {key}={got!r} != review {want!r}",
                )
        if fields["READ_ONLY"].strip().lower() not in ("true", "yes"):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RESULT_NOT_READ_ONLY",
                f"result READ_ONLY={fields['READ_ONLY']!r}",
            )
        if record_agent and record_agent != expected_agent:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_AGENT_MISMATCH",
                f"record review_agent {record_agent!r} != carrier agent {expected_agent!r}",
            )
        self.checks.append(
            f"result_comment:{comment_id}:bot:{login}:marker:{marker}:verdict:{fields['REVIEW_VERDICT']}"
        )

    def verify_workflow_run(self) -> dict:
        run_id = int(self.evidence["workflow_run_id"])
        run = self._get_json(
            f"/repos/{self.repository}/actions/runs/{run_id}",
            "REVIEW_EVIDENCE_RUN_MISSING",
        )
        if not isinstance(run, dict):
            raise _EvidenceFailure("REVIEW_EVIDENCE_RUN_MISSING", "workflow run is not an object")
        if int(run.get("id") or 0) != run_id:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_MISMATCH", f"run id {run.get('id')!r} != {run_id}"
            )
        repository = run.get("repository") or {}
        if str(repository.get("full_name") or "") != self.repository:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_REPOSITORY_MISMATCH",
                f"run repository {repository.get('full_name')!r}",
            )
        if run.get("event") != "issue_comment":
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_EVENT_MISMATCH", f"run event {run.get('event')!r}"
            )
        if run.get("path") != TRUSTED_WORKFLOW_PATH:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_WORKFLOW_MISMATCH", f"run path {run.get('path')!r}"
            )
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_NOT_SUCCESS",
                f"run status={run.get('status')!r} conclusion={run.get('conclusion')!r}",
            )
        if run.get("head_sha") != self.evidence["workflow_head_sha"]:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_HEAD_MISMATCH",
                f"run head_sha {run.get('head_sha')!r} != {self.evidence['workflow_head_sha']!r}",
            )
        started = _parse_utc(run.get("run_started_at"))
        updated = _parse_utc(run.get("updated_at"))
        if started is None or updated is None or updated < started:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_TIME_MISSING",
                f"run {run_id} has no usable run_started_at..updated_at window "
                f"({run.get('run_started_at')!r}..{run.get('updated_at')!r})",
            )
        self.run_started = started
        self.run_updated = updated
        self.checks.append(f"workflow_run:{run_id}:success:head:{run.get('head_sha')}")
        return run

    def verify_run_trigger_binding(self) -> None:
        """Bind the run to the trigger comment, not merely to a shared thread.

        A run cannot start before its trigger comment, and the trigger comment
        must be the newest issue comment created before the run started: any
        other issue comment in between could have been the actual trigger.
        Comments created during the run (including the result comment) do not
        affect this check.
        """
        run_id = int(self.evidence["workflow_run_id"])
        trigger_id = int(self.evidence["trigger_comment_id"])
        issue_number = int(self.evidence["trigger_issue_number"])
        if self.trigger_comment is None or self.run_started is None:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_TRIGGER_MISMATCH",
                f"trigger comment {trigger_id} was not fetched before run {run_id} binding",
            )
        trigger_at = _parse_utc(self.trigger_comment.get("created_at"))
        if trigger_at is None:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_TRIGGER_TIME_MISSING",
                f"trigger comment {trigger_id} has no parseable created_at",
            )
        if trigger_at > self.run_started:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_TRIGGER_ORDER",
                f"trigger comment {trigger_id} created {trigger_at.isoformat()} after "
                f"run {run_id} started {self.run_started.isoformat()}",
            )
        payload = self._get_json(
            f"/repos/{self.repository}/issues/{issue_number}/comments"
            "?per_page=100&sort=created&direction=desc",
            "REVIEW_EVIDENCE_ISSUE_COMMENTS_MISSING",
        )
        if not isinstance(payload, list) or not payload:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_ISSUE_COMMENTS_MISSING",
                f"cannot read issue {issue_number} comments to bind run {run_id}",
            )
        candidates: list[tuple[datetime, int]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            created = _parse_utc(item.get("created_at"))
            comment_id = item.get("id")
            if (
                created is not None
                and isinstance(comment_id, int)
                and not isinstance(comment_id, bool)
                and comment_id > 0
                and created <= self.run_started
            ):
                candidates.append((created, comment_id))
        if not candidates:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_TRIGGER_MISMATCH",
                f"no issue comment before run {run_id} start is visible on issue {issue_number}",
            )
        latest_at, latest_id = max(candidates)
        if latest_id != trigger_id:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_RUN_TRIGGER_MISMATCH",
                f"run {run_id} started after comment {latest_id} "
                f"({latest_at.isoformat()}), not trigger comment {trigger_id}",
            )
        self.checks.append(f"run_trigger:{run_id}:trigger_comment:{trigger_id}:bound")

    def verify_jobs(self) -> None:
        run_id = int(self.evidence["workflow_run_id"])
        job_id = int(self.evidence["workflow_job_id"])
        job_name = str(self.evidence["workflow_job_name"])
        payload = self._get_json(
            f"/repos/{self.repository}/actions/runs/{run_id}/jobs?per_page=100",
            "REVIEW_EVIDENCE_JOBS_MISSING",
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise _EvidenceFailure("REVIEW_EVIDENCE_JOBS_MISSING", "jobs payload is malformed")
        jobs: dict[str, dict] = {}
        for item in payload["jobs"]:
            if isinstance(item, dict) and item.get("name"):
                jobs[str(item["name"])] = item
        expected = jobs.get(job_name)
        if expected is None:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_JOB_MISSING", f"run {run_id} has no job {job_name!r}"
            )
        if int(expected.get("id") or 0) != job_id:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_JOB_ID_MISMATCH",
                f"job {job_name!r} id {expected.get('id')!r} != {job_id}",
            )
        if expected.get("status") != "completed" or expected.get("conclusion") != "success":
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_JOB_NOT_SUCCESS",
                f"job {job_name!r} status={expected.get('status')!r} "
                f"conclusion={expected.get('conclusion')!r}",
            )
        for lane in INCOMPATIBLE_LANE_JOBS:
            lane_job = jobs.get(lane)
            if lane_job is not None and lane_job.get("conclusion") == "success":
                raise _EvidenceFailure(
                    "REVIEW_EVIDENCE_IMPLEMENTATION_LANE_RAN",
                    f"lane {lane!r} succeeded; an implementation lane is not review evidence",
                )
        self.checks.append("jobs:opencode-bunny-review:success:implementation_lanes:absent")

    def verify_workflow_pin(self) -> None:
        head_sha = str(self.evidence["workflow_head_sha"])
        job_name = str(self.evidence["workflow_job_name"])
        raw = self._get_raw(
            f"/repos/{self.repository}/contents/{TRUSTED_WORKFLOW_PATH}?ref={head_sha}",
            "REVIEW_EVIDENCE_WORKFLOW_MISSING",
        )
        import yaml

        try:
            workflow = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_UNPARSEABLE", f"workflow YAML invalid ({exc})"
            ) from exc
        if not isinstance(workflow, dict) or not isinstance(workflow.get("jobs"), dict):
            raise _EvidenceFailure("REVIEW_EVIDENCE_WORKFLOW_UNPARSEABLE", "workflow has no jobs")
        job = workflow["jobs"].get(job_name)
        if not isinstance(job, dict):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_JOB_MISSING",
                f"workflow at {head_sha[:12]} has no job {job_name!r}",
            )
        condition = str(job.get("if") or "")
        if (
            "github.event.comment.author_association" not in condition
            or '["OWNER", "MEMBER", "COLLABORATOR"]' not in condition
            or "github.event.issue.author_association" not in condition
        ):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_TRUST_GATE_MISSING",
                f"job {job_name!r} has no commenter/thread trust gate",
            )
        for bot_login in OPENCODE_BOT_LOGINS:
            if bot_login in condition:
                raise _EvidenceFailure(
                    "REVIEW_EVIDENCE_WORKFLOW_BOT_THREAD_EXCEPTION",
                    f"job {job_name!r} exempts the bot-authored thread {bot_login!r} "
                    "from the target trust gate",
                )
        env_steps = [
            step
            for step in job.get("steps") or []
            if isinstance(step, dict)
            and isinstance(step.get("env"), dict)
            and "MODEL" in step["env"]
        ]
        if len(env_steps) != 1:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_PIN_MISSING",
                f"job {job_name!r} does not pin exactly one OpenCode run env",
            )
        env = env_steps[0]["env"]
        model = str(env.get("MODEL") or "")
        variant = str(env.get("VARIANT") or "")
        agent = str(env.get("AGENT") or "")
        if model != TRUSTED_MODEL_ID:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_MODEL_MISMATCH",
                f"workflow pins MODEL={model!r} (expected Space Bunny canonical)",
            )
        if variant != NATIVE_VARIANT:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_VARIANT_MISMATCH",
                f"workflow pins VARIANT={variant!r} (expected native max)",
            )
        allowed_agents = CARRIER_TOP_LEVEL_AGENTS[self.carrier]
        if agent not in allowed_agents:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_AGENT_MISMATCH",
                f"workflow pins AGENT={agent!r} (expected one of {allowed_agents})",
            )
        self._verify_agent_selection(workflow, job, env_steps[0])
        self.checks.append(
            f"workflow_pin:{head_sha}:{job_name}:{model}:{variant}:{agent}:trust_gate"
        )

    def _verify_agent_selection(
        self, workflow: dict[str, Any], job: dict[str, Any], run_step: dict[str, Any]
    ) -> None:
        """The reviewer must be selected and checked at runtime, not just declared."""
        job_name = str(self.evidence["workflow_job_name"])
        raw_env = job.get("env")
        job_env: dict[str, Any] = raw_env if isinstance(raw_env, dict) else {}
        problems = runtime_identity.override_problems(job_env.get("OPENCODE_CONFIG_CONTENT"))
        if problems:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_AGENT_SELECTION_MISSING",
                f"job {job_name!r}: {problems[0]}",
            )
        steps = [step for step in job.get("steps") or [] if isinstance(step, dict)]
        scopes: list[tuple[str, Any]] = [("workflow", workflow.get("env")), ("job", job_env)]
        scopes += [(f"step {step.get('name')!r}", step.get("env")) for step in steps]
        for scope, env in scopes:
            if not isinstance(env, dict):
                continue
            names = [name for name in runtime_identity.FORBIDDEN_CONFIG_ENV if name in env]
            if scope.startswith("step") and "OPENCODE_CONFIG_CONTENT" in env:
                names.append("OPENCODE_CONFIG_CONTENT")
            if names:
                raise _EvidenceFailure(
                    "REVIEW_EVIDENCE_WORKFLOW_CONFIG_OVERRIDE",
                    f"{scope} sets {', '.join(names)}",
                )
        if any("GITHUB_ENV" in str(step.get("run") or "") for step in steps):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_CONFIG_OVERRIDE",
                f"job {job_name!r} writes GITHUB_ENV, which can change the agent config",
            )
        if job.get("continue-on-error") or any(step.get("continue-on-error") for step in steps):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_RUNTIME_CHECK_MISSING",
                f"job {job_name!r} lets a failed step pass (continue-on-error)",
            )
        run_index = steps.index(run_step)

        def runs(step: dict[str, Any], *needles: str) -> bool:
            script = str(step.get("run") or "")
            return "if" not in step and all(needle in script for needle in needles)

        copied = f'"${{GITHUB_SHA}}:{RUNTIME_CHECKER}"'
        preflight = any(runs(step, copied, "preflight") for step in steps[:run_index])
        logged = runs(run_step, f"--log {RUNTIME_LOG}")
        audited = any(
            runs(step, f"audit {RUNTIME_LOG}", "preflight") for step in steps[run_index + 1 :]
        )
        if not (preflight and logged and audited):
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_WORKFLOW_RUNTIME_CHECK_MISSING",
                f"job {job_name!r} lacks the trusted reviewer runtime preflight/log/audit "
                f"(preflight={preflight}, log={logged}, audit={audited})",
            )
        self.checks.append(
            f"agent_selection:{job_name}:OPENCODE_CONFIG_CONTENT=default_agent:"
            f"{runtime_identity.REVIEW_AGENT}:preflight+audit"
        )

    def verify_read_only_agent(self) -> None:
        head_sha = str(self.evidence["workflow_head_sha"])
        agent = CARRIER_REVIEW_AGENTS[self.carrier]
        path = READ_ONLY_AGENT_FILES[agent]
        raw = self._get_raw(
            f"/repos/{self.repository}/contents/{path}?ref={head_sha}",
            "REVIEW_EVIDENCE_AGENT_FILE_MISSING",
        )
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_AGENT_FILE_INVALID", f"{path} has no YAML frontmatter"
            )
        import yaml

        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as exc:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_AGENT_FILE_INVALID", f"{path} frontmatter invalid ({exc})"
            ) from exc
        if not isinstance(frontmatter, dict):
            raise _EvidenceFailure("REVIEW_EVIDENCE_AGENT_FILE_INVALID", f"{path} frontmatter")
        permission = frontmatter.get("permission") or {}
        bash = permission.get("bash") or {}
        problems: list[str] = []
        if str(frontmatter.get("model") or "") != TRUSTED_MODEL_ID:
            problems.append(f"model={frontmatter.get('model')!r}")
        if str(frontmatter.get("variant") or "") != NATIVE_VARIANT:
            problems.append(f"variant={frontmatter.get('variant')!r}")
        if permission.get("edit") != "deny":
            problems.append("edit not denied")
        if bash.get("*") != "deny":
            problems.append("bash not default-denied")
        if permission.get("task") != "deny":
            problems.append("task not denied")
        if problems:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_AGENT_NOT_READ_ONLY",
                f"{path} at {head_sha[:12]}: {', '.join(problems)}",
            )
        # The CLI appends the agent's rules to the project's; the last match wins.
        raw_config = self._get_raw(
            f"/repos/{self.repository}/contents/{PROJECT_CONFIG_PATH}?ref={head_sha}",
            "REVIEW_EVIDENCE_PROJECT_CONFIG_MISSING",
        )
        try:
            project_config = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_PROJECT_CONFIG_MISSING",
                f"{PROJECT_CONFIG_PATH} at {head_sha[:12]} is not JSON ({exc.msg})",
            ) from exc
        surface = runtime_identity.static_problems(project_config, frontmatter)
        if surface:
            raise _EvidenceFailure(
                "REVIEW_EVIDENCE_AGENT_NOT_READ_ONLY",
                f"effective reviewer permissions at {head_sha[:12]}: {', '.join(surface[:4])}",
            )
        self.checks.append(
            f"read_only_agent:{path}@{head_sha}:{TRUSTED_MODEL_ID}:{NATIVE_VARIANT}:"
            f"edit=deny,bash=deny,task=deny:effective:{len(runtime_identity.WRITE_PROBES)}_write_probes_refused"
        )

    def run(self) -> ReviewEvidenceResult:
        self.verify_repository()
        self.verify_trigger_comment()
        self.verify_workflow_run()
        self.verify_run_trigger_binding()
        self.verify_result_comment()
        self.verify_jobs()
        self.verify_workflow_pin()
        self.verify_read_only_agent()
        return ReviewEvidenceResult(
            status=SATISFIED,
            reasons=(
                "REVIEW_EVIDENCE_SATISFIED: trusted OpenCode review evidence verified "
                f"({self.carrier})",
            ),
            checks=tuple(self.checks),
        )


def verify_review_evidence(
    record: Mapping[str, Any],
    *,
    expected_repository: str | None = None,
    client: GitHubEvidenceClient | None = None,
    transport: EvidenceTransport | None = None,
    token: str | None = None,
) -> ReviewEvidenceResult:
    """Verify a review record's external evidence; fail closed on anything unknown."""
    if not isinstance(record, Mapping):
        return ReviewEvidenceResult(
            UNVERIFIABLE, ("REVIEW_EVIDENCE_UNVERIFIABLE: record is not a mapping",)
        )
    if str(record.get("verdict") or "") != PASS_VERDICT:
        return ReviewEvidenceResult(
            UNSATISFIED,
            ("REVIEW_EVIDENCE_RECORD_NOT_PASS: only a PASS record has verifiable evidence",),
        )
    evidence = record.get("review_evidence")
    shape_errors = validate_evidence_shape(evidence)
    if shape_errors:
        return ReviewEvidenceResult(
            UNSATISFIED, tuple(f"REVIEW_EVIDENCE_SCHEMA: {error}" for error in shape_errors[:4])
        )
    if not isinstance(evidence, dict):  # pragma: no cover - shape check covers this
        return ReviewEvidenceResult(
            UNVERIFIABLE, ("REVIEW_EVIDENCE_UNVERIFIABLE: evidence is not a mapping",)
        )
    verifier = _Verifier(
        record,
        evidence,
        client or default_client(transport=transport, token=token),
        expected_repository=expected_repository,
    )
    try:
        return verifier.run()
    except _EvidenceFailure as failure:
        status = UNVERIFIABLE if failure.unverifiable else UNSATISFIED
        return ReviewEvidenceResult(
            status,
            (f"{failure.code}: {failure.detail}",),
            checks=tuple(verifier.checks),
        )
    except Exception as exc:
        return ReviewEvidenceResult(
            UNVERIFIABLE,
            (f"REVIEW_EVIDENCE_UNVERIFIABLE: unexpected {type(exc).__name__}",),
            checks=tuple(verifier.checks),
        )
