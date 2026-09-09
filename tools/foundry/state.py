"""Validator for .foundry/WORKSTREAM_STATE.yaml (schema version 1.0).

Stdlib plus PyYAML only. Mirrors .foundry/WORKSTREAM_STATE.schema.json.
The state file is an operational index, not Source Authority.
"""

from __future__ import annotations

import argparse
import re
import sys

import yaml

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+$")

REQUIRED = [
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


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["state file must be a mapping"]
    for field in REQUIRED:
        if field not in data or data[field] is None:
            errors.append(f"missing required field: {field}")
        elif field in ("in_scope", "out_of_scope"):
            if not isinstance(data[field], list):
                errors.append(f"{field} must be a list")
        elif isinstance(data[field], str) and not data[field].strip():
            errors.append(f"missing required field: {field}")
    version = str(data.get("schema_version", ""))
    if version and not VERSION_RE.match(version):
        errors.append(f"bad schema_version: {version!r}")
    for field in ("audit_base_sha", "audit_base_tree", "current_head"):
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
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a WORKSTREAM_STATE.yaml file.")
    parser.add_argument("--state", required=True, help="Path to the state YAML file.")
    args = parser.parse_args(argv)
    try:
        with open(args.state, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        print(f"STATE_INVALID: cannot read: {exc}", file=sys.stderr)
        return 1
    errors = validate(data if isinstance(data, dict) else {})
    if not isinstance(data, dict):
        errors = ["state file must be a mapping"]
    if errors:
        for error in errors:
            print(f"STATE_INVALID: {error}", file=sys.stderr)
        return 1
    print(f"STATE_OK: status={data['status']} branch={data['branch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
