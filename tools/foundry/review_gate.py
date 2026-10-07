"""Canonical cross-executor review gate for MATERIAL implementation workstreams.

One machine-readable structure and one validator. A MATERIAL policy-enabled
workstream may claim PR_READY/COMPLETE only when a fresh-context READ-ONLY
Space Bunny MAX reviewer reviewed the exact validated implementation SHA AND
TREE and returned PASS.

Fail-closed semantics:

- DeepSeek implementation + DeepSeek review stays unsatisfied.
- a PASS record is only admitted with independently verified external evidence
  (``review_evidence``): a self-declared record the implementation executor
  writes can never fabricate a Space Bunny run;
- the review runtime must be one of the two admitted Space Bunny runtime ids;
- missing/blocked/unknown/partial/fail/stale review blocks completion;
- an unknown or invalid materiality declaration is UNSATISFIED: only an exact
  NON_MATERIAL declaration can seek the Git-verified exemption, and every
  other value is treated as MATERIAL;
- a NON_MATERIAL claim cannot self-exempt by rebinding the audit base onto the
  validated head, and a policy-less state cannot certify a new completion;
- a MATERIAL delta after the review (including a P1/P2 repair) marks the prior
  review STALE and requires exact new SHA/TREE re-review;
- a generated-state-only checkpoint commit is NON_MATERIAL and preserves the
  reviewed validated implementation identity without pretending the later
  commit itself was reviewed;
- historical states without the new policy fields stay parseable and are not
  retroactively failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import executor_profiles as executor_mod
import materiality as materiality_mod
import review_evidence as evidence_mod

REVIEW_RECORD_TYPE = "cross_executor_review"
REVIEW_RECORD_SCHEMA_VERSION = "1.0"
REVIEW_MODE = "READ_ONLY_FRESH_CONTEXT"
VERDICTS = ("PASS", "FAIL", "PARTIAL", "UNKNOWN", "BLOCKED", "STALE")
PASS_VERDICT = "PASS"
# Only the top-level agent of the trusted read-only direct lane can carry
# verifiable review evidence. A writable top-level run (bunny-verifier) or a
# subagent it dispatches (bunny-auditor) can never satisfy the gate.
READ_ONLY_REVIEW_AGENTS = frozenset({"foundry-reviewer"})
REQUIRED_FIELDS = (
    "schema_version",
    "record_type",
    "required",
    "materiality",
    "logical_profile",
    "resolved_provider",
    "resolved_model_id",
    "model_alias_class",
    "native_variant",
    "review_mode",
    "review_agent",
    "reviewed_sha",
    "reviewed_tree",
    "verdict",
    "findings",
    "implementation_executor",
    "review_executor",
    "review_evidence",
)
OPTIONAL_FIELDS = ("source_lock", "reviewed_utc")
FINDING_KEYS = ("P1", "P2", "P3")


@dataclass(frozen=True)
class ReviewGateResult:
    status: str  # SATISFIED | UNSATISFIED | STALE | EXEMPT_HISTORICAL | NOT_REQUIRED
    reasons: tuple[str, ...]
    review_record_path: str | None = None
    materiality: dict | None = None

    @property
    def ok(self) -> bool:
        return self.status in ("SATISFIED", "EXEMPT_HISTORICAL", "NOT_REQUIRED")


def _is_sha(value: object) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(c in "0123456789abcdef" for c in text)


def validate_review_record(
    record: dict, *, registry: executor_mod.ExecutorRegistry | None = None
) -> list[str]:
    """Validate the canonical review structure; every deviation fails closed."""
    if not isinstance(record, dict):
        return ["review record must be a mapping"]
    errors: list[str] = []
    unknown = sorted(set(record) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
    if unknown:
        errors.append(f"review record has unknown fields: {unknown}")
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"review record missing required field {field!r}")
    if record.get("schema_version") != REVIEW_RECORD_SCHEMA_VERSION:
        errors.append(f"review schema_version must be {REVIEW_RECORD_SCHEMA_VERSION!r}")
    if record.get("record_type") != REVIEW_RECORD_TYPE:
        errors.append(f"review record_type must be {REVIEW_RECORD_TYPE!r}")
    if not isinstance(record.get("required"), bool):
        errors.append("review required must be a bool")
    if record.get("materiality") not in (materiality_mod.MATERIAL, materiality_mod.NON_MATERIAL):
        errors.append("review materiality must be MATERIAL or NON_MATERIAL")
    if record.get("logical_profile") != "space-bunny":
        errors.append("review logical_profile must be space-bunny")
    if record.get("review_executor") != "space-bunny":
        errors.append("review_executor must be the logical space-bunny profile")
    implementation_executor = record.get("implementation_executor")
    reg = registry or executor_mod.load_registry()
    if implementation_executor not in reg.logical_profiles:
        errors.append(
            f"implementation_executor {implementation_executor!r} is not an admitted logical profile"
        )
    if implementation_executor == "space-bunny":
        errors.append("review_executor must differ from implementation_executor (self-review)")
    if record.get("resolved_provider") != reg.provider:
        errors.append(f"review resolved_provider must be {reg.provider!r}")
    runtime_id = str(record.get("resolved_model_id", ""))
    admitted = reg.admitted_runtime(runtime_id)
    if admitted is None or admitted.logical_profile != "space-bunny":
        errors.append(f"resolved_model_id {runtime_id!r} is not an admitted space-bunny runtime id")
    else:
        alias_class = record.get("model_alias_class")
        if alias_class != admitted.alias_class:
            errors.append(
                f"model_alias_class {alias_class!r} does not match admitted "
                f"{admitted.alias_class!r} for {runtime_id!r}"
            )
    if record.get("model_alias_class") not in executor_mod.ALIAS_CLASSES:
        errors.append("model_alias_class must be CANONICAL or LEGACY_ALIAS")
    if record.get("native_variant") != executor_mod.NATIVE_VARIANT:
        errors.append(f"review native_variant must be {executor_mod.NATIVE_VARIANT!r}")
    if record.get("review_mode") != REVIEW_MODE:
        errors.append(f"review_mode must be {REVIEW_MODE!r} (read-only fresh context)")
    if record.get("review_agent") not in READ_ONLY_REVIEW_AGENTS:
        errors.append(
            f"review_agent {record.get('review_agent')!r} is not a structurally "
            f"read-only reviewer ({sorted(READ_ONLY_REVIEW_AGENTS)})"
        )
    if not _is_sha(record.get("reviewed_sha")):
        errors.append("reviewed_sha must be a 40-hex commit")
    if not _is_sha(record.get("reviewed_tree")):
        errors.append("reviewed_tree must be a 40-hex tree")
    verdict = record.get("verdict")
    if verdict not in VERDICTS:
        errors.append(f"verdict {verdict!r} not in {list(VERDICTS)}")
    findings = record.get("findings")
    if not isinstance(findings, dict) or set(findings) != set(FINDING_KEYS):
        errors.append(f"findings must map exactly {list(FINDING_KEYS)}")
    else:
        for key in FINDING_KEYS:
            if not isinstance(findings.get(key), list):
                errors.append(f"findings.{key} must be a list")
        if verdict == PASS_VERDICT and not errors:
            blocking = [item for item in ("P1", "P2") if findings.get(item)]
            if blocking:
                errors.append(
                    f"PASS verdict cannot carry unresolved blocking findings {blocking} "
                    "(evidenced P1/P2 repairs require re-review)"
                )
    evidence = record.get("review_evidence")
    if evidence is not None:
        errors.extend(evidence_mod.validate_evidence_shape(evidence))
    source_lock = record.get("source_lock")
    if source_lock is not None:
        if not isinstance(source_lock, dict):
            errors.append("source_lock must be a mapping when present")
        else:
            for key in ("audit_base_sha", "audit_base_tree"):
                if key in source_lock and not _is_sha(source_lock[key]):
                    errors.append(f"source_lock.{key} must be 40-hex")
    return errors


def load_review_record(path: str | Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read review record {path}: {exc}") from exc


def _record_problems(
    record: dict,
    *,
    registry: executor_mod.ExecutorRegistry,
    validated_head: str,
    validated_tree: str,
) -> list[str]:
    """Return fail-closed problems for one record against the validated identity."""
    errors = validate_review_record(record, registry=registry)
    if errors:
        return [f"REVIEW_RECORD_INVALID: {errors[0]}"]
    verdict = str(record.get("verdict"))
    problems: list[str] = []
    if record.get("required") is not True:
        problems.append("REVIEW_NOT_REQUIRED_BUT_MATERIAL")
    if str(record.get("reviewed_sha")) != validated_head or str(record.get("reviewed_tree")) != (
        validated_tree
    ):
        problems.append(
            "REVIEW_IDENTITY_MISMATCH: reviewed "
            f"{str(record.get('reviewed_sha'))[:12]}/{str(record.get('reviewed_tree'))[:12]} != "
            f"validated {validated_head[:12]}/{validated_tree[:12]} (STALE; exact re-review required)"
        )
    if verdict != PASS_VERDICT:
        problems.append(f"REVIEW_VERDICT_{verdict}")
    return problems


def _git_head(workdir: str) -> str | None:
    import subprocess

    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workdir, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _effective_state_paths(state_paths: tuple[str, ...], state_path: str | None) -> tuple[str, ...]:
    if not state_path:
        return state_paths
    return tuple({*state_paths, state_path})


def evaluate_review_gate(
    doc: dict,
    *,
    registry: executor_mod.ExecutorRegistry | None = None,
    workdir: str | None = None,
    review_record: dict | None = None,
    review_record_path: str | None = None,
    live_head: str | None = None,
    state_paths: tuple[str, ...] = (),
    state_path: str | None = None,
    evidence_verifier: Callable[[dict], evidence_mod.ReviewEvidenceResult] | None = None,
    evidence_transport: evidence_mod.EvidenceTransport | None = None,
    expected_repository: str | None = None,
) -> ReviewGateResult:
    """Evaluate the cross-executor review requirement for one state document.

    A PASS record is only admitted when its ``review_evidence`` is independently
    verified against GitHub evidence by ``evidence_verifier`` (production
    default) or an injected verifier/transport (tests). The implementation
    executor cannot satisfy the gate by writing a record that merely declares
    Space Bunny identity/verdict.
    """
    state_paths = _effective_state_paths(state_paths, state_path)
    reg = registry or executor_mod.load_registry()
    repository = expected_repository or str(doc.get("repository") or "") or None
    policy_engaged = "materiality" in doc or "cross_executor_review" in doc
    if not policy_engaged:
        return ReviewGateResult(
            status="EXEMPT_HISTORICAL",
            reasons=("REVIEW_GATE_EXEMPT_HISTORICAL: no review policy fields present",),
        )
    declared = doc.get("materiality")
    if declared is not None and (
        not isinstance(declared, str)
        or declared not in (materiality_mod.MATERIAL, materiality_mod.NON_MATERIAL)
    ):
        # Wrong-reason control: an unknown/lowercase/"N/A" declaration must not
        # fall through to the NON_MATERIAL exemption path and self-exempt.
        return ReviewGateResult(
            status="UNSATISFIED",
            reasons=(
                "MATERIALITY_DECLARATION_INVALID: declared materiality "
                f"{declared!r} is not one of "
                f"{[materiality_mod.MATERIAL, materiality_mod.NON_MATERIAL]}",
            ),
        )
    mirror = doc.get("cross_executor_review")
    if mirror is not None and not isinstance(mirror, dict):
        return ReviewGateResult(
            status="UNSATISFIED",
            reasons=("REVIEW_MIRROR_INVALID: cross_executor_review must be a mapping",),
        )

    validated_head = str(doc.get("validated_head") or "")
    validated_tree = str(doc.get("validated_tree") or "")
    base = str(doc.get("audit_base_sha") or "")
    report: materiality_mod.MaterialityReport | None = None
    if workdir and base and validated_head:
        report = materiality_mod.classify_commit_range(
            workdir,
            base,
            validated_head,
            declared=declared if isinstance(declared, str) else None,
            state_paths=state_paths,
        )
    declared_materiality = declared if isinstance(declared, str) else materiality_mod.MATERIAL
    # Any declaration that is not exactly NON_MATERIAL is treated as MATERIAL;
    # a missing declaration never exempts material work.
    material_required = declared_materiality != materiality_mod.NON_MATERIAL
    if declared_materiality == materiality_mod.NON_MATERIAL and (
        not _is_sha(base) or not _is_sha(validated_head) or base == validated_head
    ):
        # Wrong-reason control: rebinding audit_base_sha onto validated_head
        # produces an empty delta; that must never grant a NON_MATERIAL
        # exemption for the work that actually happened.
        return ReviewGateResult(
            status="UNSATISFIED",
            reasons=(
                "MATERIALITY_SELF_EXEMPT: a NON_MATERIAL exemption requires a Git-verified "
                "change set beyond the declared audit base (validated_head != audit_base_sha)",
            ),
            materiality=report.to_dict() if report else None,
        )
    if declared_materiality == materiality_mod.NON_MATERIAL and report is not None:
        claimed = materiality_mod.declared_materiality_problems(declared_materiality, report)
        if claimed:
            return ReviewGateResult(
                status="UNSATISFIED",
                reasons=tuple(claimed),
                materiality=report.to_dict(),
            )
    if not material_required:
        if workdir is None or report is None:
            return ReviewGateResult(
                status="UNSATISFIED",
                reasons=(
                    "MATERIALITY_UNVERIFIABLE: a NON_MATERIAL exemption requires a "
                    "Git-verified change-set classification (--workdir)",
                ),
            )
        if isinstance(mirror, dict) and mirror.get("required") is True:
            return ReviewGateResult(
                status="UNSATISFIED",
                reasons=(
                    "REVIEW_REQUIRED_BUT_MATERIALITY_NON_MATERIAL: a workstream cannot "
                    "self-declare NON_MATERIAL while requiring a material review",
                ),
                materiality=report.to_dict() if report else None,
            )
        return ReviewGateResult(
            status="NOT_REQUIRED",
            reasons=("REVIEW_NOT_REQUIRED: computed change set is generated-state/document only",),
            materiality=report.to_dict() if report else None,
        )

    if not _is_sha(validated_head) or not _is_sha(validated_tree):
        return ReviewGateResult(
            status="UNSATISFIED",
            reasons=(
                "NO_VALIDATED_IMPLEMENTATION: material workstream has no validated_head/"
                "validated_tree to review",
            ),
            materiality=report.to_dict() if report else None,
        )
    if isinstance(mirror, dict) and mirror.get("required") is not True:
        return ReviewGateResult(
            status="UNSATISFIED",
            reasons=(
                "REVIEW_REQUIREMENT_MISMATCH: MATERIAL workstream mirror declares "
                "required != true; a material workstream cannot self-exempt",
            ),
            materiality=report.to_dict() if report else None,
        )

    path = review_record_path or (
        str(mirror.get("review_record_path"))
        if isinstance(mirror, dict) and mirror.get("review_record_path")
        else None
    )
    if path and not os.path.isabs(path) and workdir:
        # Canonical records live in the worktree; resolve relative pointers
        # against it, never against the process CWD.
        path = str(Path(workdir) / path)
    if review_record is None:
        if not path:
            return ReviewGateResult(
                status="UNSATISFIED",
                reasons=(
                    "REVIEW_RECORD_MISSING: material workstream has no canonical review record",
                ),
                materiality=report.to_dict() if report else None,
            )
        try:
            review_record = load_review_record(path)
        except ValueError as exc:
            return ReviewGateResult(
                status="UNSATISFIED",
                reasons=(f"REVIEW_RECORD_UNREADABLE: {exc}",),
                review_record_path=path,
                materiality=report.to_dict() if report else None,
            )
    record = review_record
    problems = _record_problems(
        record, registry=reg, validated_head=validated_head, validated_tree=validated_tree
    )
    if isinstance(mirror, dict):
        for mirror_key, record_key in (
            ("resolved_model_id", "resolved_model_id"),
            ("model_alias_class", "model_alias_class"),
            ("review_executor", "review_executor"),
            ("implementation_executor", "implementation_executor"),
        ):
            mirror_value = mirror.get(mirror_key)
            if mirror_value is not None and mirror_value != record.get(record_key):
                problems.append(
                    f"REVIEW_MIRROR_MISMATCH: state {mirror_key}={mirror_value!r} != "
                    f"record {record.get(record_key)!r}"
                )
        mirror_sha = mirror.get("reviewed_sha")
        if mirror_sha is not None and str(mirror_sha) != str(record.get("reviewed_sha")):
            problems.append("REVIEW_MIRROR_MISMATCH: state reviewed_sha != record reviewed_sha")
        mirror_tree = mirror.get("reviewed_tree")
        if mirror_tree is not None and str(mirror_tree) != str(record.get("reviewed_tree")):
            problems.append("REVIEW_MIRROR_MISMATCH: state reviewed_tree != record reviewed_tree")
        mirror_verdict = mirror.get("verdict")
        if mirror_verdict is not None and mirror_verdict != record.get("verdict"):
            problems.append("REVIEW_MIRROR_MISMATCH: state verdict != record verdict")

    # Any material implementation/evidence mutation after the reviewed identity
    # stales the review, even when validated_head was correctly bumped.
    effective_live = live_head
    if effective_live is None and workdir:
        effective_live = _git_head(workdir)
    if not problems and workdir and effective_live and effective_live != validated_head:
        post = materiality_mod.classify_commit_range(
            workdir, validated_head, effective_live, state_paths=state_paths
        )
        if post.is_material:
            problems.append(
                "REVIEW_STALE_MATERIAL_DELTA: material changes after the reviewed "
                f"identity ({', '.join(post.material_paths[:5]) or post.reason}); re-review required"
            )

    # Authenticity: a PASS is only admitted when its external evidence is
    # independently verified. A fabricated record with plausible Space Bunny
    # fields fails here because the verifier reads the real GitHub evidence.
    if not problems and record.get("verdict") == PASS_VERDICT:
        try:
            if evidence_verifier is not None:
                evidence_result = evidence_verifier(record)
            else:
                evidence_result = evidence_mod.verify_review_evidence(
                    record, expected_repository=repository, transport=evidence_transport
                )
        except Exception as exc:
            problems.append(f"REVIEW_EVIDENCE_UNVERIFIABLE: verifier raised {type(exc).__name__}")
        else:
            if not evidence_result.ok:
                first = evidence_result.reasons[0] if evidence_result.reasons else "no detail"
                problems.append(f"REVIEW_EVIDENCE_{evidence_result.status}: {first}")
    if problems:
        stale = any("STALE" in problem or "IDENTITY_MISMATCH" in problem for problem in problems)
        return ReviewGateResult(
            status="STALE" if stale else "UNSATISFIED",
            reasons=tuple(problems),
            review_record_path=path,
            materiality=report.to_dict() if report else None,
        )
    return ReviewGateResult(
        status="SATISFIED",
        reasons=(
            f"REVIEW_GATE_SATISFIED: space-bunny {record.get('resolved_model_id')} "
            f"({record.get('model_alias_class')}) PASS on "
            f"{validated_head[:12]}/{validated_tree[:12]}",
        ),
        review_record_path=path,
        materiality=report.to_dict() if report else None,
    )


def evaluate_completion_claim(
    doc: dict,
    *,
    claim: str,
    registry: executor_mod.ExecutorRegistry | None = None,
    workdir: str | None = None,
    review_record_path: str | None = None,
    remote_verdict: str | None = None,
    state_paths: tuple[str, ...] = (),
    state_path: str | None = None,
    evidence_verifier: Callable[[dict], evidence_mod.ReviewEvidenceResult] | None = None,
    evidence_transport: evidence_mod.EvidenceTransport | None = None,
    expected_repository: str | None = None,
) -> ReviewGateResult:
    """Combined policy gate for a PR_READY/COMPLETE claim.

    ``remote_verdict`` is the result of the remote-checkpoint check; a missing
    or mismatched remote checkpoint blocks the claim (the caller supplies it so
    this module stays free of Git remote I/O). A policy-less state cannot use
    the historical exemption to certify a new completion claim.
    """
    if claim not in ("PR_READY", "COMPLETE"):
        return ReviewGateResult(status="NOT_REQUIRED", reasons=(f"claim {claim!r} not gated",))
    result = evaluate_review_gate(
        doc,
        registry=registry,
        workdir=workdir,
        review_record_path=review_record_path,
        state_paths=state_paths,
        state_path=state_path,
        evidence_verifier=evidence_verifier,
        evidence_transport=evidence_transport,
        expected_repository=expected_repository,
    )
    problems = list(result.reasons) if not result.ok else []
    if result.status == "EXEMPT_HISTORICAL":
        # Historical states stay parseable, but absence of the policy fields
        # never certifies a PR_READY/COMPLETE claim: a fresh workstream gets
        # the policy fields from bootstrap, so omitting them is an evasion.
        problems.append(
            "COMPLETION_POLICY_FIELDS_MISSING: a PR_READY/COMPLETE claim requires "
            "materiality/cross_executor_review policy fields; a policy-less state "
            "cannot be certified as a new completion"
        )
    if remote_verdict is None:
        problems.append(
            f"REMOTE_CHECKPOINT_UNVERIFIED: {claim} claim requires an explicit "
            "remote-checkpoint verdict"
        )
    elif remote_verdict != "SATISFIED":
        problems.append(
            f"REMOTE_CHECKPOINT_{remote_verdict}: {claim} claim requires remote equality"
        )
    if problems:
        return ReviewGateResult(
            status="STALE" if result.status == "STALE" else "UNSATISFIED",
            reasons=tuple(problems),
            review_record_path=result.review_record_path,
            materiality=result.materiality,
        )
    return result


def _load_state(path: str) -> dict:
    import yaml

    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    if not isinstance(doc, dict):
        raise ValueError("state is not a mapping")
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-executor review gate validator.")
    parser.add_argument("--state", required=True, help="Workstream state YAML.")
    parser.add_argument("--workdir", default=None, help="Worktree for Git-materiality checks.")
    parser.add_argument("--review-record", default=None, help="Canonical review record JSON.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result.")
    args = parser.parse_args(argv)
    try:
        doc = _load_state(args.state)
    except (OSError, ValueError) as exc:
        print(f"REVIEW_GATE_FAIL: cannot read state: {exc}", file=sys.stderr)
        return 2
    result = evaluate_review_gate(
        doc,
        workdir=args.workdir,
        review_record_path=args.review_record,
    )
    payload = {
        "status": result.status,
        "ok": result.ok,
        "reasons": list(result.reasons),
        "review_record_path": result.review_record_path,
        "materiality": result.materiality,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if result.ok:
            print(f"REVIEW_GATE_OK: {result.status}")
        else:
            print(f"REVIEW_GATE_FAIL: {result.status}: {result.reasons[0]}", file=sys.stderr)
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
