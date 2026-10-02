"""Trusted static integrity guard for server-required CI definitions.

This program MUST be executed from trusted base code.  Candidate Git objects are
read as data only; candidate files are never checked out, imported, sourced, or
executed.  The policy intentionally proves a bounded set of invariants, not
semantic equivalence of arbitrary GitHub Actions programs.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1

REQUIRED_CONTEXTS: dict[str, dict[str, Any]] = {
    "quality": {
        "workflow": ".github/workflows/ci.yml",
        "categories": (
            "ruff_lint",
            "ruff_format",
            "mypy",
            "pytest",
            "compile",
            "package_wheel",
            "secret_sentinel",
        ),
    },
    "security": {
        "workflow": ".github/workflows/ci.yml",
        "categories": ("dependency_audit", "sbom", "license_report"),
    },
    "infrastructure": {
        "workflow": ".github/workflows/production-qualification.yml",
        "categories": ("qualification_tests", "manifest_harness_validation"),
    },
}

TRUSTED_POLICY_SURFACES = {
    ".github/workflows/repository-tree-integrity.yml",
    ".github/workflows/ci-definition-integrity.yml",
    "scripts/verify_repository_tree.py",
    "scripts/verify_required_check_definitions.py",
}

ENTRYPOINT_DEFINITION_SURFACES = {
    "pyproject.toml",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "pytest.ini",
    "tox.ini",
    "setup.cfg",
    "setup.py",
    "requirements/lock.txt",
    "qualification/harness.py",
    "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json",
    "qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json",
}

WORKFLOW_SURFACES = {spec["workflow"] for spec in REQUIRED_CONTEXTS.values()}

CATEGORY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "ruff_lint": (re.compile(r"^\s*ruff\s+check(?:\s|$)"),),
    "ruff_format": (re.compile(r"^\s*ruff\s+format\s+--check(?:\s|$)"),),
    "mypy": (
        re.compile(r"^\s*mypy(?:\s|$)"),
        re.compile(r"^\s*python\s+-m\s+mypy(?:\s|$)"),
    ),
    "pytest": (
        re.compile(r"^\s*pytest(?:\s|$)"),
        re.compile(r"^\s*python\s+-m\s+pytest(?:\s|$)"),
    ),
    "compile": (re.compile(r"^\s*python\s+-m\s+compileall(?:\s|$)"),),
    "package_wheel": (re.compile(r"^\s*python\s+-m\s+pip\s+wheel(?:\s|$)"),),
    "dependency_audit": (re.compile(r"^\s*pip-audit\b.*\s--strict(?:\s|$)"),),
    "sbom": (re.compile(r"^\s*cyclonedx-py\s+environment(?:\s|$)"),),
    "license_report": (re.compile(r"^\s*pip-licenses(?:\s|$)"),),
    "qualification_tests": (
        re.compile(r"^\s*pytest\b.*\btests/qualification(?:\s|$)"),
        re.compile(r"^\s*python\s+-m\s+pytest\b.*\btests/qualification(?:\s|$)"),
    ),
    "manifest_harness_validation": (
        re.compile(r"^\s*python\s+qualification/harness\.py\s+validate(?:\s|$)"),
    ),
}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
IMMUTABLE_ACTION_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
SAFE_STEP_IF = {
    "always()",
    "success() || failure()",
    "failure() || success()",
    "true",
}


class InspectionError(RuntimeError):
    """Candidate data could not be safely or deterministically inspected."""


def _git(repo: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise InspectionError("git_object_inspection_failed") from exc


def _validate_commit(repo: Path, revision: str) -> str:
    if SHA_RE.fullmatch(revision) is None:
        raise InspectionError("exact_40_hex_commit_sha_required")
    if _git(repo, "cat-file", "-t", revision).strip() != b"commit":
        raise InspectionError("candidate_or_base_object_is_not_a_commit")
    tree = _git(repo, "rev-parse", f"{revision}^{{tree}}").decode().strip()
    if SHA_RE.fullmatch(tree) is None:
        raise InspectionError("commit_tree_identity_invalid")
    return tree


def _changed_paths(repo: Path, base: str, head: str) -> list[str]:
    payload = _git(repo, "diff", "--name-only", "-z", base, head, "--")
    return sorted(
        item.decode("utf-8", errors="surrogateescape") for item in payload.split(b"\0") if item
    )


def _blob(repo: Path, revision: str, path: str, *, max_bytes: int = 1_000_000) -> bytes:
    if path.startswith("/") or ".." in Path(path).parts or "\x00" in path:
        raise InspectionError(f"unsafe_candidate_path:{path}")
    try:
        payload = _git(repo, "show", f"{revision}:{path}")
    except InspectionError as exc:
        raise InspectionError(f"candidate_blob_unavailable:{path}") from exc
    if len(payload) > max_bytes:
        raise InspectionError(f"candidate_blob_too_large:{path}")
    return payload


def _yaml_document(repo: Path, revision: str, path: str) -> Any:
    payload = _blob(repo, revision, path)
    try:
        return yaml.safe_load(payload.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise InspectionError(f"yaml_parse_failed:{path}") from exc


def _workflow_events(workflow: dict[str, Any]) -> Any:
    if "on" in workflow:
        return workflow["on"]
    # PyYAML 1.1 resolves the unquoted GitHub Actions key 'on' as boolean True.
    return workflow.get(True)


def _normalize_if(value: Any) -> str | None:
    if value is None:
        return None
    if value is False:
        return "false"
    if value is True:
        return "true"
    if not isinstance(value, str):
        return "<unknown>"
    text = value.strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    return " ".join(text.split())


def _pr_trigger_status(workflow: dict[str, Any]) -> tuple[str, str]:
    events = _workflow_events(workflow)
    if not isinstance(events, dict):
        return "UNKNOWN", "workflow_on_mapping_not_statically_understood"
    if "pull_request" not in events:
        return "FAIL", "pull_request_trigger_missing"
    pr = events["pull_request"]
    if pr is None:
        return "PASS", "pull_request_trigger_covers_main"
    if not isinstance(pr, dict):
        return "UNKNOWN", "pull_request_trigger_shape_not_statically_understood"
    if "paths" in pr or "paths-ignore" in pr:
        return "UNKNOWN", "pull_request_path_filter_can_skip_required_context"
    types = pr.get("types")
    if types is not None:
        values = [types] if isinstance(types, str) else types
        required_types = {"opened", "synchronize", "reopened"}
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            return "UNKNOWN", "pull_request_types_not_statically_understood"
        if not required_types.issubset(values):
            return "FAIL", "pull_request_types_do_not_cover_required_pr_updates"
    ignored = pr.get("branches-ignore")
    if ignored is not None:
        values = [ignored] if isinstance(ignored, str) else ignored
        if isinstance(values, list) and "main" in values:
            return "FAIL", "pull_request_trigger_explicitly_ignores_main"
        return "UNKNOWN", "pull_request_branches_ignore_not_statically_safe"
    branches = pr.get("branches")
    if branches is None:
        return "PASS", "pull_request_trigger_covers_main"
    values = [branches] if isinstance(branches, str) else branches
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        return "UNKNOWN", "pull_request_branches_not_statically_understood"
    if any(item.startswith("!") for item in values):
        return "UNKNOWN", "pull_request_branch_negation_not_statically_safe"
    if "main" not in values:
        return "FAIL", "pull_request_trigger_does_not_cover_main"
    return "PASS", "pull_request_trigger_covers_main"


def _masked_line(line: str) -> bool:
    stripped = line.strip()
    return "||" in stripped or bool(
        re.search(r";\s*(?:true|exit\s+0)(?:\s|$)", stripped)
    )


def _run_lines(run: str) -> list[str]:
    return [
        line.strip()
        for line in run.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _command_segments(run: str) -> list[str]:
    segments: list[str] = []
    for line in _run_lines(run):
        segments.extend(part.strip() for part in line.split("&&") if part.strip())
    return segments


def _matching_command_is_enforcing(run: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    matches = [
        line for line in _command_segments(run) if any(pattern.search(line) for pattern in patterns)
    ]
    if not matches:
        return False
    for line in matches:
        if _masked_line(line):
            continue
        if (
            "|" in line
            and "||" not in line
            and "set -o pipefail" not in run
            and "set -euo pipefail" not in run
        ):
            continue
        if "set +e" in run:
            has_unconditional_zero_exit = any(
                re.fullmatch(r"exit\s+0", command) for command in _command_segments(run)
            )
            if (
                "rc=$?" not in run
                or 'exit "$rc"' not in run
                or has_unconditional_zero_exit
            ):
                continue
        return True
    return False


def _step_condition(step: dict[str, Any]) -> tuple[str, str]:
    condition = _normalize_if(step.get("if"))
    if condition is None or condition in SAFE_STEP_IF:
        return "PASS", "critical_step_condition_runs"
    if condition in {"false", "cancelled()"}:
        return "FAIL", f"critical_step_trivially_skipped:{condition}"
    return "UNKNOWN", f"critical_step_condition_not_statically_safe:{condition}"


def _continue_on_error(value: Any) -> tuple[str, str]:
    if value in (None, False):
        return "PASS", "continue_on_error_disabled"
    if value is True:
        return "FAIL", "continue_on_error_true"
    return "UNKNOWN", "continue_on_error_expression_not_statically_safe"


def _shell_status(step: dict[str, Any]) -> tuple[str, str]:
    shell = step.get("shell")
    if shell is None or shell == "bash":
        return "PASS", "critical_step_shell_preserves_fail_closed_bash_semantics"
    if not isinstance(shell, str):
        return "UNKNOWN", "critical_step_shell_not_statically_understood"
    return "UNKNOWN", f"critical_step_custom_shell_not_statically_safe:{shell}"


def _category_status(category: str, steps: list[dict[str, Any]]) -> tuple[str, str]:
    if category == "secret_sentinel":
        candidates = []
        for step in steps:
            run = step.get("run")
            if isinstance(run, str) and "git grep" in run:
                candidates.append(step)
        if not candidates:
            return "FAIL", "project_secret_sentinel_missing"
        for step in candidates:
            shell_status, shell_reason = _shell_status(step)
            if shell_status != "PASS":
                return shell_status, shell_reason
            condition_status, condition_reason = _step_condition(step)
            if condition_status != "PASS":
                return condition_status, condition_reason
            coe_status, coe_reason = _continue_on_error(step.get("continue-on-error"))
            if coe_status != "PASS":
                return coe_status, coe_reason
            run = step["run"]
            if "exit 1" in run and "Potential secret material found" in run:
                return "PASS", "project_secret_sentinel_fail_path_present"
        return "FAIL", "project_secret_sentinel_has_no_blocking_fail_path"

    patterns = CATEGORY_PATTERNS[category]
    seen_unknown = False
    for step in steps:
        run = step.get("run")
        if not isinstance(run, str) or not any(
            pattern.search(line) for line in _command_segments(run) for pattern in patterns
        ):
            continue
        shell_status, shell_reason = _shell_status(step)
        if shell_status != "PASS":
            return shell_status, shell_reason
        condition_status, condition_reason = _step_condition(step)
        if condition_status == "FAIL":
            return "FAIL", condition_reason
        if condition_status == "UNKNOWN":
            seen_unknown = True
            continue
        coe_status, coe_reason = _continue_on_error(step.get("continue-on-error"))
        if coe_status == "FAIL":
            return "FAIL", coe_reason
        if coe_status == "UNKNOWN":
            seen_unknown = True
            continue
        if _matching_command_is_enforcing(run, patterns):
            return "PASS", f"blocking_{category}_command_present"
    if seen_unknown:
        return "UNKNOWN", f"{category}_present_but_execution_not_statically_proven"
    return "FAIL", f"blocking_{category}_command_missing"


def _action_status(uses: Any) -> tuple[str, str]:
    if not isinstance(uses, str):
        return "UNKNOWN", "action_reference_not_a_string"
    if uses.startswith("./"):
        return "PASS", "candidate_local_action_reference"
    if uses.startswith("docker://") or "${{" in uses:
        return "UNKNOWN", f"action_reference_not_statically_pinned:{uses}"
    if IMMUTABLE_ACTION_RE.fullmatch(uses):
        return "PASS", "third_party_action_immutable_sha"
    return "FAIL", f"third_party_action_not_immutable_sha:{uses}"


def _job_analysis(
    repo: Path,
    revision: str,
    context: str,
    spec: dict[str, Any],
    inspected: set[str],
) -> tuple[list[dict[str, str]], set[str]]:
    workflow_path = spec["workflow"]
    inspected.add(workflow_path)
    try:
        workflow = _yaml_document(repo, revision, workflow_path)
    except InspectionError as exc:
        return [
            {
                "id": f"{context}.workflow_parse",
                "status": "FAIL",
                "reason": str(exc),
                "path": workflow_path,
            }
        ], set()
    if not isinstance(workflow, dict):
        return [
            {
                "id": f"{context}.workflow_shape",
                "status": "UNKNOWN",
                "reason": "workflow_root_not_mapping",
                "path": workflow_path,
            }
        ], set()

    findings: list[dict[str, str]] = []
    trigger_status, trigger_reason = _pr_trigger_status(workflow)
    findings.append(
        {
            "id": f"{context}.pull_request_trigger",
            "status": trigger_status,
            "reason": trigger_reason,
            "path": workflow_path,
        }
    )

    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        findings.append(
            {
                "id": f"{context}.job",
                "status": "UNKNOWN",
                "reason": "jobs_mapping_not_statically_understood",
                "path": workflow_path,
            }
        )
        return findings, set()
    job = jobs.get(context)
    if job is None:
        findings.append(
            {
                "id": f"{context}.job",
                "status": "FAIL",
                "reason": "required_context_job_missing_or_renamed",
                "path": workflow_path,
            }
        )
        return findings, set()
    if not isinstance(job, dict):
        findings.append(
            {
                "id": f"{context}.job",
                "status": "UNKNOWN",
                "reason": "required_context_job_not_mapping",
                "path": workflow_path,
            }
        )
        return findings, set()

    job_name = job.get("name")
    if job_name is None or job_name == context:
        findings.append(
            {
                "id": f"{context}.check_context_name",
                "status": "PASS",
                "reason": "required_check_context_name_preserved",
                "path": workflow_path,
            }
        )
    elif not isinstance(job_name, str) or "${{" in job_name:
        findings.append(
            {
                "id": f"{context}.check_context_name",
                "status": "UNKNOWN",
                "reason": "required_check_context_name_not_statically_understood",
                "path": workflow_path,
            }
        )
    else:
        findings.append(
            {
                "id": f"{context}.check_context_name",
                "status": "FAIL",
                "reason": f"required_check_context_renamed:{job_name}",
                "path": workflow_path,
            }
        )

    if job.get("needs") is not None:
        findings.append(
            {
                "id": f"{context}.needs",
                "status": "UNKNOWN",
                "reason": "required_job_needs_dependency_can_suppress_context_execution",
                "path": workflow_path,
            }
        )
    else:
        findings.append(
            {
                "id": f"{context}.needs",
                "status": "PASS",
                "reason": "required_job_has_no_needs_skip_dependency",
                "path": workflow_path,
            }
        )

    strategy = job.get("strategy")
    if isinstance(strategy, dict) and strategy.get("matrix") is not None:
        findings.append(
            {
                "id": f"{context}.matrix",
                "status": "UNKNOWN",
                "reason": "required_job_matrix_can_change_check_context_identity",
                "path": workflow_path,
            }
        )

    for defaults, scope in (
        (workflow.get("defaults"), "workflow"),
        (job.get("defaults"), "job"),
    ):
        if isinstance(defaults, dict):
            run_defaults = defaults.get("run")
            if isinstance(run_defaults, dict) and run_defaults.get("shell") not in (None, "bash"):
                findings.append(
                    {
                        "id": f"{context}.{scope}_default_shell",
                        "status": "UNKNOWN",
                        "reason": "required_job_default_shell_not_statically_safe",
                        "path": workflow_path,
                    }
                )

    job_if = _normalize_if(job.get("if"))
    if job_if in {"false", "cancelled()"}:
        findings.append(
            {
                "id": f"{context}.job_if",
                "status": "FAIL",
                "reason": f"required_job_trivially_skipped:{job_if}",
                "path": workflow_path,
            }
        )
    elif job_if is None:
        findings.append(
            {
                "id": f"{context}.job_if",
                "status": "PASS",
                "reason": "required_job_has_no_skip_condition",
                "path": workflow_path,
            }
        )
    else:
        findings.append(
            {
                "id": f"{context}.job_if",
                "status": "UNKNOWN",
                "reason": f"required_job_condition_not_statically_safe:{job_if}",
                "path": workflow_path,
            }
        )

    coe_status, coe_reason = _continue_on_error(job.get("continue-on-error"))
    findings.append(
        {
            "id": f"{context}.job_continue_on_error",
            "status": coe_status,
            "reason": coe_reason,
            "path": workflow_path,
        }
    )

    steps = job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        findings.append(
            {
                "id": f"{context}.steps",
                "status": "UNKNOWN",
                "reason": "required_job_steps_not_static_list",
                "path": workflow_path,
            }
        )
        return findings, set()

    local_actions: set[str] = set()
    action_failures = 0
    action_unknowns = 0
    for index, step in enumerate(steps):
        coe_status, coe_reason = _continue_on_error(step.get("continue-on-error"))
        if coe_status != "PASS":
            findings.append(
                {
                    "id": f"{context}.step_{index}.continue_on_error",
                    "status": coe_status,
                    "reason": coe_reason,
                    "path": workflow_path,
                }
            )
        if "uses" in step:
            uses = step.get("uses")
            status, reason = _action_status(uses)
            if status == "FAIL":
                action_failures += 1
            elif status == "UNKNOWN":
                action_unknowns += 1
            findings.append(
                {
                    "id": f"{context}.step_{index}.action_trust",
                    "status": status,
                    "reason": reason,
                    "path": workflow_path,
                }
            )
            if isinstance(uses, str) and uses.startswith("./"):
                local_actions.add(uses[2:].rstrip("/"))

    if action_failures == 0 and action_unknowns == 0:
        findings.append(
            {
                "id": f"{context}.action_pins",
                "status": "PASS",
                "reason": "all_required_job_third_party_actions_use_immutable_sha_pins",
                "path": workflow_path,
            }
        )

    for category in spec["categories"]:
        status, reason = _category_status(category, steps)
        findings.append(
            {
                "id": f"{context}.category.{category}",
                "status": status,
                "reason": reason,
                "path": workflow_path,
            }
        )

    return findings, local_actions


def _local_action_definition(
    repo: Path, revision: str, root: str, inspected: set[str]
) -> tuple[str, str, str | None]:
    if root.startswith("/") or ".." in Path(root).parts:
        return "UNKNOWN", "unsafe_local_action_path", None
    for name in ("action.yml", "action.yaml"):
        path = f"{root}/{name}"
        try:
            document = _yaml_document(repo, revision, path)
        except InspectionError:
            continue
        inspected.add(path)
        if not isinstance(document, dict):
            return "UNKNOWN", "local_action_definition_not_mapping", path
        runs = document.get("runs")
        if not isinstance(runs, dict):
            return "UNKNOWN", "local_action_runs_not_mapping", path
        using = runs.get("using")
        if using == "composite":
            steps = runs.get("steps")
            if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
                return "UNKNOWN", "local_composite_steps_not_static_list", path
            for step in steps:
                coe_status, coe_reason = _continue_on_error(step.get("continue-on-error"))
                if coe_status != "PASS":
                    return coe_status, f"local_action:{coe_reason}", path
                if "uses" in step:
                    status, reason = _action_status(step.get("uses"))
                    if status != "PASS":
                        return status, f"local_action:{reason}", path
            return "PASS", "local_composite_action_statically_inspected", path
        if isinstance(using, str):
            return "PASS", f"local_action_runtime_declared:{using}", path
        return "UNKNOWN", "local_action_runtime_not_statically_understood", path
    return "FAIL", "referenced_local_action_definition_missing", None


def _is_under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def inspect_required_check_definitions(repo: Path, base: str, head: str) -> dict[str, Any]:
    repo = repo.resolve()
    inspected: set[str] = set()
    try:
        base_tree = _validate_commit(repo, base)
        head_tree = _validate_commit(repo, head)
        changed = _changed_paths(repo, base, head)
    except InspectionError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "base": {"sha": base},
            "candidate": {"sha": head},
            "inspected_files": [],
            "changed_protected_surfaces": [],
            "invariant_results": [
                {
                    "id": "source_identity",
                    "status": "UNKNOWN",
                    "reason": str(exc),
                    "path": None,
                }
            ],
            "overall_classification": "UNKNOWN",
            "reasons": [str(exc)],
            "candidate_code_executed": False,
        }

    base_results: list[dict[str, str]] = []
    head_results: list[dict[str, str]] = []
    base_local: set[str] = set()
    head_local: set[str] = set()

    for context, spec in REQUIRED_CONTEXTS.items():
        results, local = _job_analysis(repo, base, context, spec, inspected)
        base_results.extend(results)
        base_local.update(local)
        results, local = _job_analysis(repo, head, context, spec, inspected)
        head_results.extend(results)
        head_local.update(local)

    invariant_results: list[dict[str, str | None]] = []
    base_bad = [item for item in base_results if item["status"] != "PASS"]
    if base_bad:
        invariant_results.append(
            {
                "id": "trusted_base_policy",
                "status": "UNKNOWN",
                "reason": "trusted_base_does_not_satisfy_current_static_policy",
                "path": None,
            }
        )
    else:
        invariant_results.append(
            {
                "id": "trusted_base_policy",
                "status": "PASS",
                "reason": "trusted_base_satisfies_current_static_policy",
                "path": None,
            }
        )
    invariant_results.extend(head_results)

    all_local = base_local | head_local
    for root in sorted(head_local):
        status, reason, path = _local_action_definition(repo, head, root, inspected)
        invariant_results.append(
            {
                "id": f"local_action.{root}",
                "status": status,
                "reason": reason,
                "path": path,
            }
        )

    protected_changes: list[dict[str, str]] = []
    review_reasons: list[str] = []
    for path in changed:
        impact: str | None = None
        if path in WORKFLOW_SURFACES:
            impact = "required_workflow_definition"
            review_reasons.append(f"required_workflow_changed:{path}")
        elif path in TRUSTED_POLICY_SURFACES:
            impact = "trusted_integrity_policy"
            review_reasons.append(f"trusted_policy_changed:{path}")
        elif path in ENTRYPOINT_DEFINITION_SURFACES:
            impact = "required_check_entrypoint_or_configuration"
            review_reasons.append(f"required_check_entrypoint_changed:{path}")
        elif path.startswith("tests/qualification/"):
            impact = "quality_and_infrastructure_test_definition"
            review_reasons.append(f"qualification_test_definition_changed:{path}")
        elif path.startswith("tests/"):
            impact = "quality_test_definition"
            review_reasons.append(f"quality_test_definition_changed:{path}")
        elif path.startswith(".github/actions/"):
            consumed = any(_is_under(path, root) for root in all_local)
            impact = (
                "required_workflow_consumed_local_action"
                if consumed
                else "local_action_surface_not_currently_consumed_by_required_jobs"
            )
            if consumed:
                review_reasons.append(f"required_local_action_changed:{path}")
        if impact is not None:
            protected_changes.append({"path": path, "impact": impact})

    statuses = [item["status"] for item in invariant_results]
    reasons: list[str] = []
    if "FAIL" in statuses:
        overall = "FAIL"
        reasons.extend(item["reason"] for item in invariant_results if item["status"] == "FAIL")
    elif "UNKNOWN" in statuses:
        overall = "UNKNOWN"
        reasons.extend(item["reason"] for item in invariant_results if item["status"] == "UNKNOWN")
    elif review_reasons:
        overall = "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"
        reasons.extend(sorted(set(review_reasons)))
    else:
        overall = "PASS"
        reasons.append("all_defined_invariants_satisfied_and_no_gate_definition_change_detected")

    return {
        "schema_version": SCHEMA_VERSION,
        "base": {"sha": base, "tree": base_tree},
        "candidate": {"sha": head, "tree": head_tree},
        "inspected_files": sorted(inspected),
        "changed_files": changed,
        "changed_protected_surfaces": protected_changes,
        "required_contexts": sorted(REQUIRED_CONTEXTS),
        "invariant_results": invariant_results,
        "overall_classification": overall,
        "reasons": reasons,
        "candidate_code_executed": False,
        "static_analysis_claim": "bounded_invariants_only_not_semantic_equivalence",
    }


def _exit_code(classification: str) -> int:
    return {
        "PASS": 0,
        "FAIL": 1,
        "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED": 2,
        "UNKNOWN": 3,
    }.get(classification, 3)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = inspect_required_check_definitions(args.repo, args.base, args.head)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return _exit_code(report["overall_classification"])


if __name__ == "__main__":
    raise SystemExit(main())
