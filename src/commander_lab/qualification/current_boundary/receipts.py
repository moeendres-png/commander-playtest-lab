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

RUNNER_IDENTITY_SCHEMA = "commander-lab.runner-identity/1.0.0"
NATIVE_SUITE_RECEIPT_SCHEMA = "commander-lab.native-suite-receipt/1.0.0"
POSITIVE_FIXTURE_RECEIPT_SCHEMA = "commander-lab.positive-fixture-receipt/1.0.0"
SEED_BINDING_SCHEMA = "commander-lab.seed-binding/1.0.0"

#: Classes the runner digest must cover. A change to any of these changes what the
#: evidence means, so the receipt must change with it.
_EXECUTED_INPUT_GLOBS = (
    "scripts/run_current_boundary_qualification.py",
    "scripts/assemble_current_boundary_evidence.py",
    "src/commander_lab/qualification/current_boundary/*.py",
    "src/commander_lab/engine/rules/*.py",
    "schemas/engine_adapter_protocol.schema.json",
    "config/rules_engines.json",
)

_NO_CREDIT = "NO_CREDIT"


class ReceiptError(RuntimeError):
    """A receipt is missing, malformed, stale, or not positive. Never credit-worthy."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _git(root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise ReceiptError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


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
            "input_digests": dict(sorted(self.input_digests.items())),
            "built_utc": self.built_utc,
        }

    def digest(self) -> str:
        return _digest(self.to_document())


def capture_runner_identity(root: Path, *, output_paths: tuple[str, ...] = ()) -> RunnerIdentity:
    """Capture the identity of the code that is actually about to execute.

    This reads live Git state and live file digests. It never asserts
    ``dirty=false`` without checking, and it records which paths are dirty rather
    than hiding them.

    ``output_paths`` names this run's own declared output locations. A run that
    has just written its evidence is necessarily dirty in exactly that place, and
    the evidence it is about to issue describes the run's *inputs*. Counting the
    run's own output as uncommitted runner code would make a run impossible to
    complete on a clean tree. The exclusion is scoped: any other uncommitted
    change still fails closed, and the executed-input digests below are captured
    and re-verified independently, so a mutated runner cannot slip through by
    hiding behind an output exclusion.
    """
    root = root.resolve()
    status = _git(root, ["status", "--porcelain"])
    # git reports repository-relative paths; normalise each declared output to
    # the same form so an absolute caller path still matches.
    normalised: list[str] = []
    for output in output_paths:
        candidate = Path(output)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(root)
            except ValueError:
                continue
        normalised.append(str(candidate).rstrip("/"))
    outputs = tuple(normalised)
    dirty_paths = tuple(
        line[3:]
        for line in status.splitlines()
        if line.strip() and not any(line[3:].rstrip("/") == out for out in outputs)
    )
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
            "positive_fixtures": [dict(row) for row in self.positive_fixtures],
        }
        doc["receipt_digest"] = _digest(doc)
        return doc


_MVN_SUMMARY = re.compile(
    r"Tests run:\s*(?P<tests>\d+),\s*Failures:\s*(?P<failures>\d+),\s*"
    r"Errors:\s*(?P<errors>\d+),\s*Skipped:\s*(?P<skipped>\d+)"
)
_PER_CLASS = re.compile(r"^\[(?:INFO|ERROR)\]\s+(\w+)\s*(?:--.*)?$", re.MULTILINE)


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
    stated = doc.pop("receipt_digest")
    if _digest(doc) != stated:
        raise ReceiptError(f"{_NO_CREDIT}: native receipt digest mismatch (tampered or truncated)")
    if doc["returncode"] != 0:
        raise ReceiptError(f"{_NO_CREDIT}: native suite exited {doc['returncode']}; no PASS credit")
    if doc["failed"] or doc["errors"]:
        raise ReceiptError(
            f"{_NO_CREDIT}: native suite reported {doc['failed']} failures / "
            f"{doc['errors']} errors; no PASS credit"
        )
    return doc


def native_suite_credit(
    receipts: list[dict[str, Any]], *, candidate: str, expected_commit: str
) -> dict[str, Any]:
    """Summarise credit from *observed* receipts only.

    A group with no receipt contributes nothing. A receipt bound to a different
    candidate head is stale and contributes nothing.
    """
    credited: list[dict[str, Any]] = []
    for doc in receipts:
        if doc.get("candidate") != candidate:
            continue
        if doc.get("candidate_commit") != expected_commit:
            continue
        credited.append(doc)
    return {
        "groups_credited": [f"{d['candidate']}:{d['group']}" for d in credited],
        "tests": sum(int(d["tests"]) for d in credited),
        "passed": sum(int(d["passed"]) for d in credited),
        "failed": sum(int(d["failed"]) for d in credited),
        "errors": sum(int(d["errors"]) for d in credited),
        "receipt_digests": {
            f"{d['candidate']}:{d['group']}": d["receipt_digest"] for d in credited
        },
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
) -> dict[str, list[str]]:
    """Fixture -> test identities, from positive observations only.

    A fixture earns native-test credit only when a positive receipt states the
    fixture, the test, the candidate head, the obligation exercised, the observed
    assertion, and PASS. A negative assertion, a bare mention, a stale head or a
    missing observation yields nothing.
    """
    out: dict[str, list[str]] = {}
    for doc in receipts:
        if doc.get("schema_version") != POSITIVE_FIXTURE_RECEIPT_SCHEMA:
            continue
        if doc.get("candidate") != candidate:
            continue
        if doc.get("candidate_commit") != expected_commit:
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
    "collect_receipts",
    "engine_tree_equivalence",
    "environment_identity",
    "load_native_receipt",
    "native_suite_credit",
    "parse_maven_summary",
    "persist",
    "positive_fixture_credit",
    "require_clean_runner",
    "verify_candidate_identity",
    "verify_engine_identity",
    "verify_runner_unchanged",
]


# The Forge engine's main-source module roots. The engine under test is exactly
# these trees; the bound native suite's test classes and the wsr20-full107
# harness are not engine.
FORGE_ENGINE_MODULE_ROOTS: tuple[str, ...] = (
    "forge-core",
    "forge-game",
    "forge-ai",
    "forge-gui",
    "forge-gui-desktop",
    "forge-protocol2-bridge",
    "adventure-editor",
)


def engine_tree_equivalence(repo: Path, recorded_commit: str, actual_commit: str) -> dict[str, Any]:
    """Compare the engine's main-source trees at two commits.

    Identity of a commit is not the question when a suite has to execute at a
    descendant of the recorded candidate. The real question is whether the engine
    that executed is the engine the evidence is about.

    For Forge the answer is measured, not assumed. Between the fork head
    ``ef958ee9`` and the WSR20/WSR24 tip ``18bba95a`` the only differences are one
    added test class and the ``wsr20-full107`` harness/evidence directory; every
    engine module's main-source tree is byte-identical. So the descendant executes
    the same engine, and crediting the fork head is correct.

    That equivalence is a property that can rot, so it is re-proven here on every
    run and fails closed if any engine module's main-source tree differs.
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
    for module in FORGE_ENGINE_MODULE_ROOTS:
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
        "justification": "ENGINE_MAIN_SOURCE_TREES_IDENTICAL",
        "recorded_commit": recorded_commit,
        "actual_commit": actual_commit,
        "detail": "the commits differ only outside the engine's main sources, so the "
        "engine that executed is the engine the evidence is about",
    }
