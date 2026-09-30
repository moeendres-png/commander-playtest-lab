"""Deterministic execution receipts for current-boundary qualification evidence.

Every credit this qualification system grants must trace to an observed execution.
A receipt is the only acceptable proof. Source text, fixture-name prefixes, class
names and hand-written literals are not evidence and must never be able to produce
one.

Three receipt families live here:

``RunnerIdentity``
    Binds the *executing* qualification code: Lab commit and tree, the exact
    digests of every executed runner/adapter/protocol input, and the dirty state
    of each. A dirty or unbound runner fails closed before any runtime evidence is
    issued, because an artifact that names a clean commit while the executing
    bytes differ is a false provenance claim.

``NativeSuiteReceipt``
    One executed native suite: exact command, candidate repository, commit, tree,
    build/runtime identity, start/end timestamps, return code, test/pass/fail
    counts, environment identity, schema version and a content digest.

``PositiveFixtureReceipt``
    One positive behaviour observation binding a fixture id to an exact test
    identity, an exact candidate head, the obligation actually exercised, the
    observed semantic assertion, and the runtime receipt it came from.

Every loader in this module is fail-closed by construction. A missing, malformed,
stale or non-positive receipt yields no credit rather than a default.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

RUNNER_IDENTITY_SCHEMA = "commander-lab.runner-identity/1.0.0"
NATIVE_SUITE_RECEIPT_SCHEMA = "commander-lab.native-suite-receipt/1.0.0"
POSITIVE_FIXTURE_RECEIPT_SCHEMA = "commander-lab.positive-fixture-receipt/1.0.0"
SEED_BINDING_SCHEMA = "commander-lab.seed-binding/1.0.0"

#: Inputs the runner digest must cover. A change to any of these changes what the
#: evidence means, so the receipt must change with it. The Lab XMage adapter is
#: included: a bridge-source change with an unchanged engine candidate is still
#: an adapter drift, and a receipt produced by the old bridge must not survive
#: it. The probe is included for the same reason on the PB-03 route.
_EXECUTED_INPUT_GLOBS = (
    "scripts/run_current_boundary_qualification.py",
    "scripts/assemble_current_boundary_evidence.py",
    "scripts/run_midgame_capability_probe.py",
    "src/commander_lab/qualification/current_boundary/*.py",
    "src/commander_lab/engine/rules/*.py",
    "schemas/engine_adapter_protocol.schema.json",
    "config/rules_engines.json",
    "engine-bridge/pom.xml",
    "engine-bridge/src/main/java/org/commanderlab/xmage/*.java",
)

_NO_CREDIT = "NO_CREDIT"


class ReceiptError(RuntimeError):
    """A receipt is missing, malformed, stale, or not positive. Never credit-worthy."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def document_digest(document: dict[str, Any]) -> str:
    """Canonical content digest for an evidence document.

    Any pipeline that persists a receipt-like document computes its self-digest
    with this one function, so a document's integrity binding cannot drift
    between producers.
    """
    return _digest(dict(document))


def _git(root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise ReceiptError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.rstrip("\n")


def _git_porcelain(root: Path) -> list[str]:
    """Porcelain status lines with NO leading-whitespace stripping.

    ``git status --porcelain`` encodes each line as a two-character status column
    plus a space, so an unstaged modification begins with a space. Stripping the
    whole output removed that space from the FIRST line, which shifted every
    subsequent column slice and turned
    ``qualification/final-current-boundary-20260927/X.json`` into
    ``ualification/...``. The run-output exclusion then failed to match and a
    generated artifact was reported as uncommitted source. Only the trailing
    newline may be removed.
    """
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ReceiptError(f"git status --porcelain failed: {proc.stderr.strip()[:200]}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _git_optional(root: Path, args: list[str], default: str = "UNCONFIGURED") -> str:
    """Read a Git fact that a repository may legitimately not have.

    A checkout with no ``origin`` remote is still perfectly bindable; the identity
    this module proves is which *code* runs, not which remote it came from. Only
    facts that must exist (HEAD, its tree, the index) are allowed to fail hard.
    """
    proc = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        return default
    return proc.stdout.strip() or default


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Runner identity
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RunnerIdentity:
    """The exact executing qualification code, bound cryptographically."""

    repository: str
    commit: str
    tree: str
    branch: str
    dirty: bool
    dirty_paths: tuple[str, ...]
    input_digests: dict[str, str]
    # Recorded so the exclusion of the run's own output is auditable, not silent.
    run_output_prefixes: tuple[str, ...] = ()
    built_utc: str = field(default_factory=_now)

    @property
    def schema_version(self) -> str:
        return RUNNER_IDENTITY_SCHEMA

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": RUNNER_IDENTITY_SCHEMA,
            "repository": self.repository,
            "commit": self.commit,
            "tree": self.tree,
            "branch": self.branch,
            "dirty": self.dirty,
            "dirty_paths": list(self.dirty_paths),
            "run_output_prefixes": list(self.run_output_prefixes),
            "input_digests": dict(sorted(self.input_digests.items())),
            "built_utc": self.built_utc,
        }

    def digest(self) -> str:
        """Content identity of the executing code, independent of capture time.

        ``built_utc`` remains in :meth:`to_document` as provenance, but is
        deliberately excluded from the digest: it is set at capture time, so
        including it would make two captures of the same clean tree disagree.
        The freshness gate compares this digest across the *runner* and
        *assembler* processes, and a receipt produced by one process could then
        never be credited by the other. Content drift (commit, tree, dirty
        state, any executed-input digest) still changes the digest, which is the
        property the gate exists for.
        """
        document = self.to_document()
        document.pop("built_utc", None)
        return _digest(document)


# Paths this qualification run writes as its own output. They are produced BY the
# run, so their uncommitted state is the result, not a provenance divergence.
_RUN_OUTPUT_PREFIXES: tuple[str, ...] = ("qualification/final-current-boundary-20260927/",)


def _is_run_output(relative: str) -> bool:
    normalised = relative.strip().strip('"')
    return normalised.startswith(_RUN_OUTPUT_PREFIXES)


def capture_runner_identity(root: Path) -> RunnerIdentity:
    """Capture the identity of the code that is actually about to execute.

    This reads live Git state and live file digests. It never asserts
    ``dirty=false`` without checking, and it records which paths are dirty rather
    than hiding them.
    """
    root = root.resolve()
    status_lines = _git_porcelain(root)
    # The run's own evidence outputs are excluded from the dirtiness judgement.
    # This gate exists so evidence cannot claim a provenance its bytes do not
    # have, and the evidence artifacts the run just wrote are exactly the bytes
    # being produced, not a divergence from committed code. Including them made
    # the pipeline unable to complete: the first phase writes tracked artifacts,
    # the tree becomes dirty by definition, and the native-suite phase then
    # refused. A CODE change is still dirty and still refused.
    dirty_paths = tuple(line[3:] for line in status_lines if not _is_run_output(line[3:]))
    digests: dict[str, str] = {}
    for pattern in _EXECUTED_INPUT_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                digests[str(path.relative_to(root))] = _file_digest(path)
    if not digests:
        raise ReceiptError("runner identity captured zero executed inputs; refusing to bind")
    return RunnerIdentity(
        repository=_git_optional(root, ["config", "--get", "remote.origin.url"]),
        commit=_git(root, ["rev-parse", "HEAD"]),
        tree=_git(root, ["rev-parse", "HEAD^{tree}"]),
        branch=_git(root, ["rev-parse", "--abbrev-ref", "HEAD"]),
        dirty=bool(dirty_paths),
        dirty_paths=dirty_paths,
        input_digests=digests,
        run_output_prefixes=_RUN_OUTPUT_PREFIXES,
    )


def require_clean_runner(identity: RunnerIdentity) -> None:
    """Fail closed when the executing code is not the committed code.

    A dirty runner means the bytes that will produce evidence are not the bytes
    any commit names. Issuing evidence anyway would let an artifact claim a clean
    provenance it does not have.
    """
    if identity.dirty:
        raise ReceiptError(
            "RUNNER_DIRTY: the executing qualification code has uncommitted changes "
            f"({len(identity.dirty_paths)} paths, e.g. {list(identity.dirty_paths)[:5]}); "
            "runtime evidence would claim a provenance it does not have. Commit first."
        )


def verify_runner_unchanged(root: Path, identity: RunnerIdentity) -> None:
    """Re-verify at receipt time that the executed inputs still hash as recorded."""
    current = capture_runner_identity(root)
    if current.input_digests != identity.input_digests:
        changed = sorted(
            name
            for name in set(current.input_digests) | set(identity.input_digests)
            if current.input_digests.get(name) != identity.input_digests.get(name)
        )
        raise ReceiptError(f"RUNNER_MUTATED: executed inputs changed during the run: {changed[:5]}")
    if current.commit != identity.commit:
        raise ReceiptError(
            f"RUNNER_MOVED: HEAD moved {identity.commit[:12]} -> {current.commit[:12]} during the run"
        )


# --------------------------------------------------------------------------- #
# Native suite receipts
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NativeSuiteReceipt:
    """One observed native-suite execution."""

    candidate: str
    group: str
    command: str
    candidate_repository: str
    candidate_commit: str
    candidate_tree: str
    build_identity: str
    started_utc: str
    ended_utc: str
    returncode: int
    tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    environment: dict[str, str]
    runner: RunnerIdentity
    classes: tuple[str, ...]
    positive_fixtures: tuple[dict[str, Any], ...] = ()
    # What actually executed, and the proof that the engine was the same engine.
    # A receipt naming only candidate_commit could attribute a result to a commit
    # that never ran, which is the defect this pair exists to prevent.
    executed_commit: str = ""
    engine_identity_proof: dict[str, Any] = field(default_factory=dict)
    # Observed per-class execution identity (surefire XML written during this
    # run), and every requested class that did not demonstrably execute.
    executed_classes: dict[str, dict[str, Any]] = field(default_factory=dict)
    unexecuted_classes: tuple[str, ...] = ()

    def to_document(self) -> dict[str, Any]:
        doc = {
            "schema_version": NATIVE_SUITE_RECEIPT_SCHEMA,
            "candidate": self.candidate,
            "group": self.group,
            "command": self.command,
            "candidate_repository": self.candidate_repository,
            "candidate_commit": self.candidate_commit,
            "candidate_tree": self.candidate_tree,
            "executed_commit": self.executed_commit,
            "engine_identity_proof": self.engine_identity_proof,
            "build_identity": self.build_identity,
            "started_utc": self.started_utc,
            "ended_utc": self.ended_utc,
            "returncode": self.returncode,
            "tests": self.tests,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "environment": dict(sorted(self.environment.items())),
            "runner": self.runner.to_document(),
            "runner_digest": self.runner.digest(),
            "classes": list(self.classes),
            "executed_classes": {
                name: dict(row) for name, row in sorted(self.executed_classes.items())
            },
            "unexecuted_classes": list(self.unexecuted_classes),
            "positive_fixtures": [dict(row) for row in self.positive_fixtures],
        }
        doc["receipt_digest"] = _digest(doc)
        return doc


_MVN_SUMMARY = re.compile(
    r"Tests run:\s*(?P<tests>\d+),\s*Failures:\s*(?P<failures>\d+),\s*"
    r"Errors:\s*(?P<errors>\d+),\s*Skipped:\s*(?P<skipped>\d+)"
)


def verify_candidate_identity(
    *, recorded_commit: str, actual_commit: str, recorded_label: str
) -> None:
    """Fail closed when the recorded candidate identity is not the executing one.

    The WSR22 evidence recorded ``ef958ee9`` as the Forge candidate while the
    bound native suites actually execute at ``18bba95a``, a descendant of it. A
    receipt that named the recorded value would therefore attribute a suite's
    result to an engine head that never ran. This is the same class of defect as
    PB-09, in the Lab's own harness, and it is the reason candidate identity is
    resolved live from the executing checkout rather than asserted.

    Ancestry is deliberately *not* accepted as identity: a descendant is a
    different tree, and the difference may include Rules-Core changes.
    """
    if recorded_commit != actual_commit:
        raise ReceiptError(
            f"CANDIDATE_IDENTITY_DIVERGENCE: {recorded_label} records "
            f"{recorded_commit[:12]} but the executing checkout is at "
            f"{actual_commit[:12]}. No credit: the recorded identity is not the "
            "engine that ran."
        )


def parse_maven_summary(text: str) -> dict[str, int]:
    """Parse the terminal Maven/JUnit summary. No summary means no credit."""
    matches = list(_MVN_SUMMARY.finditer(text))
    if not matches:
        raise ReceiptError("NO_SUMMARY: native suite produced no parseable Tests run summary")
    last = matches[-1]
    return {
        "tests": int(last.group("tests")),
        "failures": int(last.group("failures")),
        "errors": int(last.group("errors")),
        "skipped": int(last.group("skipped")),
    }


def observed_class_executions(
    report_dirs: list[Path], classes: tuple[str, ...], *, not_before: float
) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    """Per requested class, its surefire report written during this run.

    The aggregate ``Tests run:`` total cannot show that a requested class ran:
    a class that vanished (renamed, excluded, not compiled) leaves the other
    classes' total green. A class counts as executed only when a surefire
    report for exactly that class was written after ``not_before`` (so a stale
    report from an earlier run never counts), with at least one test that was
    not skipped, and no failure or error.
    """
    observed: dict[str, dict[str, Any]] = {}
    unexecuted: list[str] = []
    for name in classes:
        reports = [
            report
            for directory in report_dirs
            if directory.is_dir()
            for report in directory.glob(f"TEST-*{name}.xml")
            if report.name.endswith(f".{name}.xml") or report.name == f"TEST-{name}.xml"
        ]
        fresh = [report for report in reports if report.stat().st_mtime >= not_before]
        if len(fresh) != 1:
            unexecuted.append(name)
            observed[name] = {"reports_found": len(reports), "fresh_reports": len(fresh)}
            continue
        try:
            root = ElementTree.parse(fresh[0]).getroot()
            counts: dict[str, Any] = {
                key: int(root.get(key, "0")) for key in ("tests", "failures", "errors", "skipped")
            }
        except (OSError, ElementTree.ParseError, ValueError):
            unexecuted.append(name)
            observed[name] = {"unparseable_report": fresh[0].name}
            continue
        counts["report"] = fresh[0].name
        observed[name] = counts
        if (
            counts["tests"] == 0
            or counts["skipped"] >= counts["tests"]
            or counts["failures"]
            or counts["errors"]
        ):
            unexecuted.append(name)
    return observed, tuple(unexecuted)


def load_native_receipt(path: Path) -> dict[str, Any]:
    """Load and validate a native-suite receipt. Raises on any defect."""
    if not path.is_file():
        raise ReceiptError(f"{_NO_CREDIT}: no native receipt at {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReceiptError(f"{_NO_CREDIT}: unreadable native receipt at {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ReceiptError(f"{_NO_CREDIT}: native receipt is not an object")
    if doc.get("schema_version") != NATIVE_SUITE_RECEIPT_SCHEMA:
        raise ReceiptError(
            f"{_NO_CREDIT}: native receipt schema {doc.get('schema_version')!r} "
            f"!= {NATIVE_SUITE_RECEIPT_SCHEMA!r}"
        )
    for field_name in (
        "candidate",
        "candidate_commit",
        "candidate_tree",
        "command",
        "returncode",
        "tests",
        "passed",
        "failed",
        "errors",
        "receipt_digest",
    ):
        if field_name not in doc:
            raise ReceiptError(f"{_NO_CREDIT}: native receipt missing {field_name!r}")
    # The digest is verified against a copy so the verified value SURVIVES into
    # the returned document. Popping it meant the assembler, which records the
    # receipt digests as its evidence provenance, raised KeyError on the very
    # receipts it had just verified. A verified digest is the strongest fact a
    # receipt carries and must remain available to consumers.
    stated = doc["receipt_digest"]
    recomputed = {key: value for key, value in doc.items() if key != "receipt_digest"}
    if _digest(recomputed) != stated:
        raise ReceiptError(f"{_NO_CREDIT}: native receipt digest mismatch (tampered or truncated)")
    if doc["returncode"] != 0:
        raise ReceiptError(f"{_NO_CREDIT}: native suite exited {doc['returncode']}; no PASS credit")
    if doc["failed"] or doc["errors"]:
        raise ReceiptError(
            f"{_NO_CREDIT}: native suite reported {doc['failed']} failures / "
            f"{doc['errors']} errors; no PASS credit"
        )
    # Requested classes must equal executed classes; an aggregate count is not
    # an execution identity.
    executed = doc.get("executed_classes")
    if not isinstance(executed, dict) or set(executed) != set(doc.get("classes") or ()):
        raise ReceiptError(f"{_NO_CREDIT}: native receipt has no per-class execution identity")
    if doc.get("unexecuted_classes"):
        raise ReceiptError(
            f"{_NO_CREDIT}: requested classes did not execute: {doc['unexecuted_classes']}"
        )
    return doc


def native_suite_credit(
    receipts: list[dict[str, Any]],
    *,
    candidate: str,
    expected_commit: str,
    expected_runner_digest: str,
) -> dict[str, Any]:
    """Summarise credit from *observed* receipts only.

    A group with no receipt contributes nothing. A receipt bound to a different
    candidate head is stale and contributes nothing. A receipt whose Lab-side
    runner identity differs from the currently executing qualification code is
    likewise stale: the engine commit alone cannot prove the adapter, runner and
    protocol semantics that produced the observation are the ones running now.
    A missing or empty ``expected_runner_digest`` fails closed with zero credit
    rather than skipping the check, and a receipt without a recorded
    ``runner_digest`` can never satisfy it, so pre-guard receipts become
    stale/UNKNOWN instead of being grandfathered in.
    """
    credited: list[dict[str, Any]] = []
    stale_runner_excluded: list[str] = []
    for doc in receipts:
        if doc.get("candidate") != candidate:
            continue
        if doc.get("candidate_commit") != expected_commit:
            continue
        recorded = doc.get("runner_digest")
        if not expected_runner_digest or not recorded or recorded != expected_runner_digest:
            stale_runner_excluded.append(f"{doc.get('candidate')}:{doc.get('group')}")
            continue
        credited.append(doc)
    return {
        "groups_credited": [f"{d['candidate']}:{d['group']}" for d in credited],
        # Per-group detail so a consumer can see WHICH suite contributed which
        # count, and cannot mistake a total for a whole-candidate claim.
        "groups": [
            {
                "candidate": d["candidate"],
                "group": d["group"],
                "tests": int(d["tests"]),
                "passed": int(d["passed"]),
                "failed": int(d["failed"]),
                "errors": int(d["errors"]),
                "returncode": d["returncode"],
                "candidate_commit": d["candidate_commit"],
                "executed_commit": d.get("executed_commit", ""),
                "engine_identity_justification": d.get("engine_identity_proof", {}).get(
                    "justification", "UNKNOWN"
                ),
                "receipt_digest": d["receipt_digest"],
            }
            for d in credited
        ],
        "tests": sum(int(d["tests"]) for d in credited),
        "passed": sum(int(d["passed"]) for d in credited),
        "failed": sum(int(d["failed"]) for d in credited),
        "errors": sum(int(d["errors"]) for d in credited),
        "receipt_digests": {
            f"{d['candidate']}:{d['group']}": d["receipt_digest"] for d in credited
        },
        # The runner identity this credit decision was bound to, plus every
        # engine-commit-matching group excluded for runner staleness, so a zero
        # is auditable as STALE rather than silently absent.
        "expected_runner_digest": expected_runner_digest,
        "stale_runner_excluded": sorted(stale_runner_excluded),
    }


# --------------------------------------------------------------------------- #
# Positive fixture receipts (replaces source-regex promotion)
# --------------------------------------------------------------------------- #


def positive_fixture_credit(
    receipts: list[dict[str, Any]],
    *,
    candidate: str,
    expected_commit: str,
    denominator: set[str],
    expected_runner_digest: str,
) -> dict[str, list[str]]:
    """Fixture -> test identities, from positive observations only.

    A fixture earns native-test credit only when a positive receipt states the
    fixture, the test, the candidate head, the obligation exercised, the observed
    assertion, and PASS. A negative assertion, a bare mention, a stale head or a
    missing observation yields nothing. The receipt must additionally be bound to
    the currently executing Lab-side runner identity: an engine-commit match with
    a mismatched or missing ``runner_digest``, or a missing expected identity,
    yields nothing, so adapter/runner drift cannot inherit credit and pre-guard
    receipts become stale rather than grandfathered.
    """
    out: dict[str, list[str]] = {}
    for doc in receipts:
        if doc.get("schema_version") != POSITIVE_FIXTURE_RECEIPT_SCHEMA:
            continue
        if doc.get("candidate") != candidate:
            continue
        if doc.get("candidate_commit") != expected_commit:
            continue
        recorded = doc.get("runner_digest")
        if not expected_runner_digest or not recorded or recorded != expected_runner_digest:
            continue
        if doc.get("outcome") != "PASS":
            continue
        observation = doc.get("observed_assertion")
        if not observation:
            # A PASS with no observed assertion is construction/import evidence
            # at best, never behaviour evidence.
            continue
        if doc.get("assertion_kind") != "POSITIVE_BEHAVIOUR":
            continue
        fixture = str(doc.get("fixture_id", ""))
        if fixture not in denominator:
            continue
        out.setdefault(fixture, []).append(str(doc.get("test_identity", "")))
    return {fixture: sorted(set(names)) for fixture, names in sorted(out.items())}


# --------------------------------------------------------------------------- #
# Rules-RNG seed binding
# --------------------------------------------------------------------------- #

SEED_REQUESTED = "REQUESTED_SEED"
SEED_ACKNOWLEDGED = "ACKNOWLEDGED_ENGINE_SEED"
SEED_UNCONTROLLED = "UNCONTROLLED_ENGINE_RNG"


@dataclass(frozen=True)
class SeedBinding:
    """What the engine actually did with the requested seed.

    ``requested_seed`` is caller intent and is never evidence on its own.
    ``acknowledged_seed`` is what the engine reported back. Replay and RNG credit
    requires an acknowledged seed equal to the requested one; anything else is
    classified honestly as uncontrolled.
    """

    requested_seed: int | None
    acknowledged_seed: int | None
    acknowledgement_source: str
    controlled: bool
    schema_version: str = SEED_BINDING_SCHEMA

    @property
    def classification(self) -> str:
        if self.controlled and self.acknowledged_seed == self.requested_seed:
            return SEED_ACKNOWLEDGED
        return SEED_UNCONTROLLED

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "requested_seed": self.requested_seed,
            "acknowledged_seed": self.acknowledged_seed,
            "acknowledgement_source": self.acknowledgement_source,
            "controlled": self.controlled,
            "classification": self.classification,
            "rng_credit": self.classification == SEED_ACKNOWLEDGED,
        }


def classify_seed_binding(
    *, requested_seed: int | None, acknowledged_seed: Any, source: str
) -> SeedBinding:
    """Derive seed control from an observed acknowledgement, never from intent.

    A provider that echoes nothing, echoes a different value, or returns a
    non-numeric value is uncontrolled. Recording explicit seed ownership on the
    strength of the caller having passed a number is the defect this replaces.
    """
    acknowledged: int | None
    if isinstance(acknowledged_seed, bool):
        acknowledged = None
    elif isinstance(acknowledged_seed, int):
        acknowledged = acknowledged_seed
    elif isinstance(acknowledged_seed, str) and acknowledged_seed.strip().lstrip("-").isdigit():
        acknowledged = int(acknowledged_seed.strip())
    else:
        acknowledged = None
    controlled = (
        acknowledged is not None and requested_seed is not None and acknowledged == requested_seed
    )
    return SeedBinding(
        requested_seed=requested_seed,
        acknowledged_seed=acknowledged,
        acknowledgement_source=source,
        controlled=controlled,
    )


# --------------------------------------------------------------------------- #
# Persisted collection
# --------------------------------------------------------------------------- #


def persist(path: Path, document: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return path


def collect_receipts(directory: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (valid receipts, rejection reasons). Never raises on one bad file."""
    valid: list[dict[str, Any]] = []
    rejected: list[str] = []
    if not directory.is_dir():
        return valid, [f"{_NO_CREDIT}: receipt directory absent: {directory}"]
    for path in sorted(directory.glob("*.json")):
        try:
            valid.append(load_native_receipt(path))
        except ReceiptError as exc:
            rejected.append(str(exc))
    return valid, rejected


#: Positive fixture receipts live in their own subdirectory of the receipt
#: directory, so the native-suite loader never sees (and never rejects) them.
POSITIVE_RECEIPT_SUBDIR = "positive"

_POSITIVE_REQUIRED_FIELDS = (
    "candidate",
    "candidate_commit",
    "runner_digest",
    "fixture_id",
    "test_identity",
    "obligation_exercised",
    "observed_assertion",
    "assertion_kind",
    "outcome",
    "receipt_digest",
)


def load_positive_fixture_receipt(path: Path) -> dict[str, Any]:
    """Load and validate one positive fixture receipt. Raises on any defect.

    Structure and integrity only; whether it earns credit (candidate head,
    runner digest, outcome, positive assertion, denominator) is decided by
    :func:`positive_fixture_credit`.
    """
    if not path.is_file():
        raise ReceiptError(f"{_NO_CREDIT}: no positive receipt at {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReceiptError(f"{_NO_CREDIT}: unreadable positive receipt at {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ReceiptError(f"{_NO_CREDIT}: positive receipt is not an object")
    if doc.get("schema_version") != POSITIVE_FIXTURE_RECEIPT_SCHEMA:
        raise ReceiptError(
            f"{_NO_CREDIT}: positive receipt schema {doc.get('schema_version')!r} "
            f"!= {POSITIVE_FIXTURE_RECEIPT_SCHEMA!r}"
        )
    for field_name in _POSITIVE_REQUIRED_FIELDS:
        if not doc.get(field_name):
            raise ReceiptError(f"{_NO_CREDIT}: positive receipt missing {field_name!r}")
    recomputed = {key: value for key, value in doc.items() if key != "receipt_digest"}
    if _digest(recomputed) != doc["receipt_digest"]:
        raise ReceiptError(
            f"{_NO_CREDIT}: positive receipt digest mismatch (tampered or truncated)"
        )
    return doc


def collect_positive_fixture_receipts(directory: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (valid positive receipts, rejection reasons) from ``directory``."""
    valid: list[dict[str, Any]] = []
    rejected: list[str] = []
    if not directory.is_dir():
        return valid, rejected
    for path in sorted(directory.glob("*.json")):
        try:
            valid.append(load_positive_fixture_receipt(path))
        except ReceiptError as exc:
            rejected.append(str(exc))
    return valid, rejected


def environment_identity() -> dict[str, str]:
    """Non-secret environment facts that can change native-suite behaviour."""
    keys = (
        "JAVA_HOME",
        "MAVEN_OPTS",
        "COMMANDER_LAB_XMAGE_BRIDGE_CMD",
        "COMMANDER_LAB_FORGE_BRIDGE_CMD",
        "FORGE_ENGINE_SHA",
        "PYTHONHASHSEED",
    )
    out: dict[str, str] = {}
    for key in keys:
        value = os.environ.get(key)
        if value is not None:
            out[key] = value[:200]
    out["python"] = sys.version.split()[0]
    return out


__all__ = [
    "NATIVE_SUITE_RECEIPT_SCHEMA",
    "POSITIVE_FIXTURE_RECEIPT_SCHEMA",
    "POSITIVE_RECEIPT_SUBDIR",
    "RUNNER_IDENTITY_SCHEMA",
    "SEED_ACKNOWLEDGED",
    "SEED_BINDING_SCHEMA",
    "SEED_REQUESTED",
    "SEED_UNCONTROLLED",
    "NativeSuiteReceipt",
    "ReceiptError",
    "RunnerIdentity",
    "SeedBinding",
    "capture_runner_identity",
    "classify_seed_binding",
    "collect_positive_fixture_receipts",
    "collect_receipts",
    "document_digest",
    "engine_tree_equivalence",
    "environment_identity",
    "load_native_receipt",
    "load_positive_fixture_receipt",
    "native_suite_credit",
    "parse_maven_summary",
    "persist",
    "positive_fixture_credit",
    "require_clean_runner",
    "verify_candidate_identity",
    "verify_engine_identity",
    "verify_pb05_provenance",
    "verify_runner_unchanged",
]


# Forge module roots, split by what they decide.
#
# The Rules-Core modules are the ones that decide Magic legality, so a change in
# any of them means a different engine ran. Those are what the engine-drift check
# compares, and any difference fails closed.
#
# forge-protocol2-bridge is deliberately NOT in that set. It is the transport and
# provenance surface, not the Rules Core, and it legitimately differs between the
# recorded candidate and the executing commit: the PB-05 build-provenance repair
# lives entirely there. Collapsing the bridge into the engine check would both
# conflate two identities the project requires be bound separately and make the
# check fail for a repair that changed no Rules-Core source at all.
FORGE_RULES_CORE_MODULE_ROOTS: tuple[str, ...] = (
    "forge-game",  # the Forge Rules Core: cards, abilities, zones, stack, combat, SBA
    "forge-core",
    "forge-ai",
    "forge-gui",
    "forge-gui-desktop",
    "adventure-editor",
)

# The bridge/provider module. Tracked and bound as its own identity.
FORGE_BRIDGE_MODULE_ROOTS: tuple[str, ...] = ("forge-protocol2-bridge",)

# Retained for callers that predate the split; now Rules-Core only.
FORGE_ENGINE_MODULE_ROOTS: tuple[str, ...] = FORGE_RULES_CORE_MODULE_ROOTS


def engine_tree_equivalence(
    repo: Path,
    recorded_commit: str,
    actual_commit: str,
    module_roots: tuple[str, ...] = FORGE_RULES_CORE_MODULE_ROOTS,
) -> dict[str, Any]:
    """Compare the Forge Rules-Core main-source trees at two commits.

    Identity of a commit is not the question when a suite has to execute at a
    descendant of the recorded candidate. The real question is whether the Rules
    Core that executed is the Rules Core the evidence is about.

    For Forge the answer is measured, not assumed. Between the fork head
    ``ef958ee9`` and the executing commit the Rules-Core modules
    ``forge-game``/``forge-core``/``forge-ai``/``forge-gui``/
    ``forge-gui-desktop``/``adventure-editor`` are byte-identical, so the
    descendant executes the same Rules Core.

    The comparison is scoped to the Rules-Core modules on purpose.
    ``forge-protocol2-bridge`` is excluded and bound as its own identity: it is
    transport and provenance, not Magic legality, and the PB-05 build-provenance
    repair changed it while changing no Rules-Core source at all. Including it
    would conflate two identities the project requires be bound separately, and
    would fail this check for a repair that did not touch the engine.

    Equivalence is a property that can rot, so it is re-proven on every run and
    fails closed if any Rules-Core module differs or exists in only one commit.
    """
    import subprocess

    def tree_at(commit: str, module: str) -> str:
        # `--verify` is required: plain `git rev-parse` echoes an unknown ref
        # back verbatim instead of failing, which would compare the same
        # non-existent path in both commits and report the engine as identical.
        completed = subprocess.run(
            [
                "git",
                "rev-parse",
                "--verify",
                "--quiet",
                f"{commit}:{module}/src/main/java",
            ],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        value = completed.stdout.strip()
        return value if len(value) == 40 and all(c in "0123456789abcdef" for c in value) else ""

    modules: dict[str, dict[str, Any]] = {}
    differing: list[str] = []
    # A module present in one commit but not the other is a structural change to
    # the engine's module layout, so it fails closed rather than being skipped.
    one_sided: list[str] = []
    for module in module_roots:
        recorded_tree = tree_at(recorded_commit, module)
        actual_tree = tree_at(actual_commit, module)
        if recorded_tree and actual_tree:
            equal = recorded_tree == actual_tree
            modules[module] = {
                "recorded_tree": recorded_tree,
                "actual_tree": actual_tree,
                "identical": equal,
            }
            if not equal:
                differing.append(module)
        elif recorded_tree != actual_tree:
            one_sided.append(module)
    # An empty comparison proves nothing, so it is never equivalent.
    return {
        "engine_equivalent": bool(modules) and not differing and not one_sided,
        "compared_module_roots": list(module_roots),
        "modules": modules,
        "differing_modules": differing,
        "one_sided_modules": one_sided,
    }


def verify_engine_identity(
    repo: Path, recorded_commit: str, actual_commit: str, *, recorded_label: str
) -> dict[str, Any]:
    """Allow a commit difference only when the engine itself is provably identical.

    A suite must execute at the descendant that actually contains its test classes,
    so exact-commit equality is neither achievable nor the right requirement. What
    must hold is that the engine is the same engine. This returns the proof, and
    raises when the difference cannot be justified.
    """
    if recorded_commit == actual_commit:
        return {
            "engine_equivalent": True,
            "justification": "EXACT_COMMIT",
            "recorded_commit": recorded_commit,
            "actual_commit": actual_commit,
        }
    equivalence = engine_tree_equivalence(repo, recorded_commit, actual_commit)
    if not equivalence["engine_equivalent"]:
        raise ReceiptError(
            f"CANDIDATE_IDENTITY_DIVERGENCE: {recorded_label} records "
            f"{recorded_commit[:12]} but executes at {actual_commit[:12]}, and the engine "
            f"is not provably the same: differing={equivalence['differing_modules']} "
            f"one_sided={equivalence['one_sided_modules']} "
            f"compared={len(equivalence['modules'])}. No credit."
        )
    return {
        **equivalence,
        "justification": "RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL",
        "recorded_commit": recorded_commit,
        "actual_commit": actual_commit,
        "detail": "the commits differ only outside the Forge Rules-Core main sources, so "
        "the Rules Core that executed is the Rules Core the evidence is about. The bridge "
        "module is deliberately excluded and is bound as a separate identity.",
    }


# --------------------------------------------------------------------------- #
# PB-05: consume provider build provenance fail-closed.
# --------------------------------------------------------------------------- #
#
# A provider that merely CLAIMS a commit is not a verified build. PB-05 previously
# accepted an operator-supplied environment variable as the commit-to-build
# binding, which is not build-proven. Forge PR #5 (continuing the PR #4 repair)
# records the build's own git commit, tree, dirty state and source, and fails
# closed:
# `git rev-parse HEAD` and `HEAD^{tree}` are admitted only on exit code 0,
# `git status --porcelain` yields "unknown" rather than a false "clean" when it
# fails, a malformed value is rejected rather than passed through, and
# `engine_commit_verified` is true only when commit, tree and dirty state are all
# present and match.
#
# The Lab side must not undo that by trusting a claim. These checks are therefore
# independent of the provider's own self-assessment.

_SHA = re.compile(r"^[0-9a-f]{40}$")


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA.match(value.strip()))


def verify_pb05_provenance(
    identity: dict[str, Any], *, expected_rules_core: str, expected_tree: str | None = None
) -> dict[str, Any]:
    """Fail-closed consumption of the provider's build provenance.

    AF00 and PB-05 credit require all of: a build-derived commit equal to the
    expected Rules Core, a well-formed build tree, a clean build source, and
    ``engine_commit_verified`` true. A missing, malformed, unknown or dirty value
    yields no credit; it is never treated as clean by default.
    """
    findings: list[str] = []

    raw_commit = identity.get("engine_build_commit")
    raw_tree = identity.get("engine_build_tree")
    build_commit = raw_commit.strip() if isinstance(raw_commit, str) else None
    build_tree = raw_tree.strip() if isinstance(raw_tree, str) else None
    build_dirty = identity.get("engine_build_dirty")
    build_source = identity.get("engine_build_source")
    verified = identity.get("engine_commit_verified")

    if not _valid_sha(build_commit):
        findings.append(f"engine_build_commit is absent or malformed: {raw_commit!r}")
    elif build_commit is None or build_commit != expected_rules_core:
        findings.append(
            f"build commit {(build_commit or '<none>')[:12]} is not the expected Rules Core "
            f"{expected_rules_core[:12]}"
        )
    if not _valid_sha(build_tree):
        findings.append(f"engine_build_tree is absent or malformed: {raw_tree!r}")
    elif expected_tree and (build_tree is None or build_tree != expected_tree):
        findings.append(
            f"build tree {(build_tree or '<none>')[:12]} is not the expected Rules Core tree "
            f"{expected_tree[:12]}"
        )
    if build_dirty is None:
        findings.append("engine_build_dirty is absent")
    elif str(build_dirty).lower() == "unknown":
        # The provider could not determine dirtiness. That is not clean.
        findings.append("engine_build_dirty is 'unknown', which is not clean")
    elif str(build_dirty).lower() != "false":
        findings.append(f"the build source is dirty: {build_dirty!r}")
    if not build_source:
        findings.append("engine_build_source is absent")
    if verified is not True:
        findings.append(f"engine_commit_verified is {verified!r}, not True")

    return {
        "pb05_credit": not findings,
        "af00_credit": not findings,
        "build_commit": build_commit,
        "build_tree": build_tree,
        "build_dirty": build_dirty,
        "build_source": build_source,
        "engine_commit_verified": verified,
        "expected_rules_core": expected_rules_core,
        "expected_tree": expected_tree,
        "findings": findings,
        "rule": "no verified build provenance means no AF00 or PB-05 credit; an unknown "
        "or dirty build source is never treated as clean",
    }
