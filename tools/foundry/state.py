"""Validator for .foundry/WORKSTREAM_STATE.yaml (schema versions 1.0 and 2.0).

Stdlib plus PyYAML only. Mirrors .foundry/WORKSTREAM_STATE.schema.json (2.0).
The state file is an operational index, not Source Authority.

Identity semantics (2.0):

- ``audit_base_sha`` / ``audit_base_tree`` (source_lock_head/tree): immutable
  bootstrap identity of the workstream. Never rewritten after bootstrap.
- ``validated_head`` (nullable): newest commit whose relevant tests/evidence
  were actually validated. ``null`` means nothing beyond the audit base has
  been validated yet. A state file must never imply its own checkpoint commit
  was validated before validation occurred: the flow is commit code ->
  validate -> write state naming the tested commit -> checkpoint-commit state.
- ``state_written_against_head`` (required): descriptive HEAD the tree was at
  when this document was produced. Never a validation claim.
- ``current_runtime_head``: deliberately NOT a file field. Derive it live via
  ``state.py --state ... --workdir ...`` (``HEAD_MISMATCH`` drift signal).

Version 1.0 files (``current_head``) remain parseable; ``migrate`` upgrades
them explicitly: ``current_head`` -> ``state_written_against_head`` and
``validated_head`` -> ``null`` (v1 never distinguished the two, so claiming
otherwise would fabricate validation credit).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+$")
SUPPORTED_VERSIONS = ("1.0", "2.0")

REQUIRED_V1 = [
    "schema_version",
    "repository",
    "worktree",
    "branch",
    "audit_base_sha",
    "audit_base_tree",
    "current_head",
    "objective",
    "in_scope",
    "out_of_scope",
    "ownership",
    "status",
    "exact_next_action",
]

REQUIRED_V2 = [
    "schema_version",
    "repository",
    "worktree",
    "branch",
    "audit_base_sha",
    "audit_base_tree",
    "state_written_against_head",
    "objective",
    "in_scope",
    "out_of_scope",
    "ownership",
    "status",
    "exact_next_action",
]

LIST_FIELDS = [
    "in_scope",
    "out_of_scope",
    "dependencies",
    "hard_gates",
    "forbidden_shortcuts",
    "validated_gates",
    "failed_gates",
    "invalidated_gates",
    "do_not_rerun",
    "files_modified",
    "tests_run",
    "evidence",
    "artifacts",
    "remaining_scope",
    "hypotheses_rejected",
    "technical_decisions",
    "authority_gates",
]

STATUS_VOCABULARY = {"ACTIVE", "WAITING", "BLOCKED", "STALE", "SUPERSEDED", "COMPLETE"}

FAILURE_CLASSES = {
    "NONE",
    "ENGINE_DEFECT",
    "PROVIDER_ADAPTER_DEFECT",
    "HARNESS_DEFECT",
    "FIXTURE_DEFECT",
    "EVIDENCE_PIPELINE_DEFECT",
    "INFRASTRUCTURE_DEFECT",
    "UPSTREAM_DEFECT",
    "UNKNOWN",
}

REASONING_TIERS = {"high", "xhigh"}


def _git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _check_common(data: dict, errors: list[str], sha_fields: list[str]) -> None:
    for field in ("in_scope", "out_of_scope"):
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} must be a list")
    for field in sha_fields:
        value = data.get(field)
        if value is not None and not SHA_RE.match(str(value)):
            errors.append(f"bad {field}: {value!r} (want 40 hex chars)")
    for field in LIST_FIELDS:
        if field in data and data[field] is not None and not isinstance(data[field], list):
            errors.append(f"{field} must be a list")
    status = data.get("status")
    if status is not None and status not in STATUS_VOCABULARY:
        errors.append(f"bad status: {status!r} (want one of {sorted(STATUS_VOCABULARY)})")
    failure_class = data.get("failure_class")
    if failure_class is not None and failure_class not in FAILURE_CLASSES:
        errors.append(f"bad failure_class: {failure_class!r}")
    tier = data.get("current_reasoning_tier")
    if tier is not None and tier not in REASONING_TIERS:
        errors.append(f"bad current_reasoning_tier: {tier!r}")
    for field in ("technical_decision_authority", "first_failing_boundary", "next_action"):
        if field in data and data[field] is not None and not str(data[field]).strip():
            errors.append(f"{field} must be a non-empty string when present")
    root_cause = data.get("root_cause_class")
    if root_cause is not None and root_cause not in FAILURE_CLASSES:
        errors.append(f"bad root_cause_class: {root_cause!r}")


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["state file must be a mapping"]
    version = str(data.get("schema_version", ""))
    if not version:
        return ["missing required field: schema_version"]
    if not VERSION_RE.match(version):
        return [f"bad schema_version: {version!r}"]
    if version not in SUPPORTED_VERSIONS:
        return [
            f"unsupported schema_version: {version!r} "
            f"(supported: {sorted(SUPPORTED_VERSIONS)}; "
            "run `state.py migrate --state PATH` for migration instructions)"
        ]
    required = REQUIRED_V1 if version == "1.0" else REQUIRED_V2
    for field in required:
        missing = field not in data or data[field] is None
        blank = isinstance(data.get(field), str) and not str(data[field]).strip()
        if missing or blank:
            errors.append(f"missing required field: {field}")
    if version == "1.0":
        _check_common(data, errors, ["audit_base_sha", "audit_base_tree", "current_head"])
    else:
        if "current_head" in data:
            errors.append(
                "current_head was removed in schema 2.0 (ambiguous identity): "
                "use state_written_against_head (descriptive) and validated_head "
                "(validation claim), or run migrate on a 1.0 file"
            )
        validated = data.get("validated_head")
        if validated is not None and not SHA_RE.match(str(validated)):
            errors.append(f"bad validated_head: {validated!r} (want 40 hex chars or null)")
        _check_common(
            data, errors, ["audit_base_sha", "audit_base_tree", "state_written_against_head"]
        )
    return errors


def migrate(data: dict) -> dict:
    """Upgrade a 1.0 state mapping to 2.0. 2.0 input returns unchanged."""
    if not isinstance(data, dict):
        raise ValueError("state file must be a mapping")
    version = str(data.get("schema_version", ""))
    if version == "2.0":
        return data
    if version != "1.0":
        raise ValueError(
            f"cannot migrate schema_version {version!r} "
            f"(supported sources: {sorted(SUPPORTED_VERSIONS)})"
        )
    out = dict(data)
    out["schema_version"] = "2.0"
    # v1 current_head never distinguished description from validation credit:
    # preserve it as description, claim nothing as validated.
    out["state_written_against_head"] = out.pop("current_head")
    out["validated_head"] = None
    out.setdefault(
        "technical_decisions",
        [],
    )
    if isinstance(out["technical_decisions"], list):
        out["technical_decisions"] = [
            *out["technical_decisions"],
            "State semantics migrated 1.0 -> 2.0: current_head preserved as "
            "state_written_against_head (descriptive); validated_head reset to "
            "null because v1 never distinguished the two (no validation credit "
            "carried across migration).",
        ]
    return out


def _recorded_head(data: dict) -> str | None:
    version = str(data.get("schema_version", ""))
    key = "state_written_against_head" if version == "2.0" else "current_head"
    value = data.get(key)
    return str(value).strip() if value else None


def check_head_mismatch(state_path: str, workdir: str) -> list[str]:
    """Compare the recorded descriptive HEAD against live ``git rev-parse HEAD``.

    Returns warnings (empty when matching). The state file is never Source
    Authority: on mismatch, live Git wins and the state must be updated.

    Termination rule for the checkpoint loop: writing the state file dirties
    the tree, and checkpoint-committing it advances HEAD by one. A live HEAD
    whose parent is the recorded HEAD and whose diff touches ONLY the state
    file is reported as CHECKPOINT_CLEAN (informational, not a warning), so
    the write -> commit cycle terminates instead of demanding another update.
    """
    try:
        with open(state_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        return [f"cannot read state for HEAD check: {exc}"]
    if not isinstance(data, dict):
        return ["state has no comparable HEAD (not a mapping)"]
    recorded = _recorded_head(data)
    if not recorded:
        return ["state has no descriptive HEAD to compare"]
    try:
        live = _git(["rev-parse", "HEAD"], workdir)
    except RuntimeError as exc:
        return [f"cannot read live HEAD: {exc}"]
    if live == recorded:
        return []
    if _is_state_only_checkpoint(state_path, workdir, recorded, live):
        print(
            f"CHECKPOINT_CLEAN: live HEAD {live} is a state-only checkpoint on "
            f"recorded {recorded} (expected; no update required)"
        )
        return []
    return [
        f"HEAD_MISMATCH: state records {recorded} != live HEAD {live} "
        "(live Git wins; update the state file)"
    ]


def _is_state_only_checkpoint(state_path: str, workdir: str, recorded: str, live: str) -> bool:
    """True when live HEAD = recorded + a commit touching only the state file."""
    try:
        parent = _git(["rev-parse", f"{live}~1"], workdir)
    except RuntimeError:
        return False
    if parent != recorded:
        return False
    try:
        files = _git(["diff-tree", "--no-commit-id", "--name-only", "-r", live], workdir)
    except RuntimeError:
        return False
    try:
        rel = str(Path(state_path).resolve().relative_to(Path(workdir).resolve()))
    except ValueError:
        rel = str(state_path)
    touched = [line for line in files.splitlines() if line.strip()]
    return len(touched) == 1 and touched[0] == rel


def check_validated_ancestry(state_path: str, workdir: str) -> list[str]:
    """Verify validation-credit integrity against live Git (2.0 only).

    - ``validated_head`` (when set) must descend from ``audit_base_sha``
      (never leaves the source lock) and must be an ancestor of (or equal to)
      live HEAD (history must not have been rewritten away).
    - ``null`` validated_head is honest, not an error: it yields an
      informational note, never a failure.
    """
    try:
        with open(state_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        return [f"cannot read state for ancestry check: {exc}"]
    if not isinstance(data, dict):
        return ["state is not a mapping"]
    if str(data.get("schema_version", "")) != "2.0":
        return ["ancestry check requires schema 2.0 (migrate first)"]
    problems: list[str] = []
    validated = data.get("validated_head")
    base = data.get("audit_base_sha")
    if validated is None:
        return ["VALIDATED_NONE: no commit validated beyond the audit base (honest null)"]
    try:
        live = _git(["rev-parse", "HEAD"], workdir)
    except RuntimeError as exc:
        return [f"cannot read live HEAD: {exc}"]
    if base and not _is_ancestor(str(base), str(validated), workdir):
        problems.append(
            f"VALIDATED_OUTSIDE_LOCK: validated_head {validated} does not "
            f"descend from audit_base_sha {base}"
        )
    if not _is_ancestor(str(validated), live, workdir):
        problems.append(
            f"VALIDATED_REWRITTEN: validated_head {validated} is not an "
            f"ancestor of live HEAD {live} (history moved; revalidate)"
        )
    return problems


def _is_ancestor(older: str, newer: str, workdir: str) -> bool:
    if older == newer:
        return True
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a WORKSTREAM_STATE.yaml file.")
    parser.add_argument("--state", required=True, help="Path to the state YAML file.")
    parser.add_argument(
        "--workdir",
        default=None,
        help="Optional worktree to compare live HEAD against the recorded HEAD.",
    )
    parser.add_argument(
        "--fail-on-head-mismatch",
        action="store_true",
        help="Exit nonzero when live HEAD differs from the recorded HEAD.",
    )
    parser.add_argument(
        "--check-validated",
        action="store_true",
        help="Verify validated_head ancestry against live Git (2.0).",
    )
    parser.add_argument(
        "--fail-on-validated-problem",
        action="store_true",
        help="Exit nonzero on VALIDATED_* problems (informational notes excluded).",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Print (or with --in-place, write) the 2.0 migration of the file.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Write migration back to --state (requires --migrate).",
    )
    args = parser.parse_args(argv)
    try:
        with open(args.state, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        print(f"STATE_INVALID: cannot read: {exc}", file=sys.stderr)
        return 1
    if args.migrate:
        if args.in_place and not isinstance(data, dict):
            print("STATE_INVALID: state file must be a mapping", file=sys.stderr)
            return 1
        try:
            out = migrate(data if isinstance(data, dict) else {})
        except ValueError as exc:
            print(f"STATE_INVALID: {exc}", file=sys.stderr)
            return 1
        text = yaml.safe_dump(out, sort_keys=False, allow_unicode=True)
        if args.in_place:
            with open(args.state, "w", encoding="utf-8") as handle:
                handle.write(text)
            print(f"STATE_MIGRATED: {args.state} -> schema 2.0")
        else:
            print(text, end="")
        return 0
    errors = validate(data if isinstance(data, dict) else {})
    if not isinstance(data, dict):
        errors = ["state file must be a mapping"]
    if errors:
        for error in errors:
            print(f"STATE_INVALID: {error}", file=sys.stderr)
        return 1
    warnings: list[str] = []
    if args.workdir:
        warnings = check_head_mismatch(args.state, args.workdir)
        for warning in warnings:
            print(f"STATE_WARN: {warning}", file=sys.stderr)
    validated_notes: list[str] = []
    if args.check_validated:
        validated_notes = check_validated_ancestry(args.state, args.workdir or ".")
        for note in validated_notes:
            print(f"STATE_VALIDATED: {note}", file=sys.stderr)
    version = data.get("schema_version") if isinstance(data, dict) else "?"
    print(f"STATE_OK: schema={version} status={data['status']} branch={data['branch']}")
    if args.fail_on_head_mismatch and warnings:
        return 1
    if args.fail_on_validated_problem and any(
        n.startswith("VALIDATED_OUTSIDE_LOCK") or n.startswith("VALIDATED_REWRITTEN")
        for n in validated_notes
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
