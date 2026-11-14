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
import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 2

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
    "scripts/ci_change_scope.py",
    "scripts/ci_gate.py",
    "scripts/verify_packaging_smoke.py",
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


def _comparison_base(repo: Path, trusted: str, head: str) -> str:
    """The candidate's effective comparison base: the unique merge base of the
    trusted validator source and the candidate.

    Diffing the candidate against current trusted main would attribute every
    later main change to the candidate. The merge base is where the candidate
    forked from (or last merged) main, so a diff from it holds exactly what the
    candidate itself changed, as the pull request diff does. No merge base, or
    several (criss-cross history), cannot be adjudicated and fails closed.
    """
    try:
        payload = _git(repo, "merge-base", "--all", trusted, head)
    except InspectionError as exc:
        raise InspectionError("comparison_base_unavailable") from exc
    bases = sorted({line.strip() for line in payload.decode().splitlines() if line.strip()})
    if len(bases) != 1 or SHA_RE.fullmatch(bases[0]) is None:
        raise InspectionError(f"comparison_base_not_unique:{len(bases)}")
    return bases[0]


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
    return "||" in stripped or bool(re.search(r";\s*(?:true|exit\s+0)(?:\s|$)", stripped))


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
            if "rc=$?" not in run or 'exit "$rc"' not in run or has_unconditional_zero_exit:
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


_CI_GATE_RE = re.compile(r"^python3?\s+scripts/ci_gate\.py(?:\s|$)")
_STRICT_SET_RE = re.compile(r"^set\s+(?:-euo\s+pipefail|-eo\s+pipefail|-eu|-e)$")
_SKIP_OUTPUT_IF_RE = re.compile(
    r"^needs\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+)\s*==\s*'true'$"
)
_MATRIX_OUTPUT_RE = re.compile(
    r"^fromJSON\(\s*needs\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+)\s*\)$"
)


def _needs_list(value: Any) -> list[str] | None:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return None


def _step_always_blocks(step: dict[str, Any]) -> bool:
    """True when the step always runs with fail-closed bash run lines and no masking."""
    if _normalize_if(step.get("if")) not in (None, "always()"):
        return False
    if _continue_on_error(step.get("continue-on-error"))[0] != "PASS":
        return False
    if _shell_status(step)[0] != "PASS":
        return False
    if step.get("working-directory") is not None:
        return False
    run = step.get("run")
    if not isinstance(run, str) or not _run_lines(run):
        return False
    if "set +e" in run or any(ch in run for ch in (";", "|", "&", "<", ">", "`", "$(")):
        return False
    for command in _command_segments(run):
        if _masked_line(command) or re.fullmatch(r"exit\s+0", command) or command == "true":
            return False
        if re.match(r"^(?:if|elif|while|until|case)\b|!", command):
            return False
    return True


def _resolve_env(text: str, env_map: dict[str, str]) -> str:
    return re.sub(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)",
        lambda match: env_map.get(match.group(1) or match.group(2), match.group(0)),
        text,
    )


def _parse_ci_gate_invocation(
    step: dict[str, Any],
) -> tuple[dict[str, str], list[str], str] | None:
    """Parse an enforcing ``scripts/ci_gate.py`` step into ``(jobs, allow_skipped, needed_flag)``."""
    if not _step_always_blocks(step):
        return None
    run = step["run"]
    if not _matching_command_is_enforcing(run, (_CI_GATE_RE,)):
        return None
    commands = _command_segments(run)
    gate_segments = [seg for seg in commands if _CI_GATE_RE.search(seg)]
    other_segments = [seg for seg in commands if not _CI_GATE_RE.search(seg)]
    if len(gate_segments) != 1 or any(
        _STRICT_SET_RE.fullmatch(seg) is None for seg in other_segments
    ):
        return None
    if commands[-1] != gate_segments[0]:
        return None
    try:
        tokens = shlex.split(gate_segments[0])
    except ValueError:
        return None
    if len(tokens) < 2 or tokens[1] != "scripts/ci_gate.py":
        return None
    raw_env = step.get("env")
    env_map = (
        {str(k): str(v) for k, v in raw_env.items() if isinstance(v, (str, int, float, bool))}
        if isinstance(raw_env, dict)
        else {}
    )
    jobs_arg: dict[str, str] = {}
    allow_skipped: list[str] = []
    packaging_needed = ""
    index = 2
    while index < len(tokens):
        tok = tokens[index]
        if tok == "--job":
            if index + 1 >= len(tokens):
                return None
            val = _resolve_env(tokens[index + 1], env_map)
            index += 2
        elif tok.startswith("--job="):
            val = _resolve_env(tok.split("=", 1)[1], env_map)
            index += 1
        elif tok == "--allow-skipped":
            if index + 1 >= len(tokens):
                return None
            name = _resolve_env(tokens[index + 1], env_map)
            if not name:
                return None
            allow_skipped.append(name)
            index += 2
            continue
        elif tok.startswith("--allow-skipped="):
            name = _resolve_env(tok.split("=", 1)[1], env_map)
            if not name:
                return None
            allow_skipped.append(name)
            index += 1
            continue
        elif tok == "--packaging-needed":
            if index + 1 >= len(tokens):
                return None
            packaging_needed = _resolve_env(tokens[index + 1], env_map)
            index += 2
            continue
        elif tok.startswith("--packaging-needed="):
            packaging_needed = _resolve_env(tok.split("=", 1)[1], env_map)
            index += 1
            continue
        else:
            return None
        name, sep, rhs = val.partition("=")
        if not sep or not name or name in jobs_arg:
            return None
        jobs_arg[name] = rhs
    return jobs_arg, allow_skipped, packaging_needed


def _gate_assessment(jobs: dict[str, Any], job: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Check the gate pattern of a required job that has ``needs``.

    Returns ``(violations, skippable)``: the violated conditions (empty when the job is a
    verified gate) and the needed jobs that may legitimately be skipped.  A gate is safe only
    when (a) its own ``if`` is exactly ``always()``, (b) a step that always runs and cannot
    continue on error invokes ``scripts/ci_gate.py`` with ``needs.<id>.result`` for every
    needed job, and it is the single last step of a job whose other steps are all full-SHA-pinned
    actions of other repositories, (c) neither the gate nor a needed job can fail silently
    (``continue-on-error``), and (d) no needed job can be skipped unless it has no matrix,
    its ``if`` reads ``needs.changes.outputs.<out> == 'true'``, ``--allow-skipped`` names
    that exact job, and ``--packaging-needed`` binds that exact output.  Every dependency of
    a needed job must itself be needed.
    """
    violations: list[str] = []
    skippable: list[str] = []
    needs = _needs_list(job.get("needs"))
    if not needs:
        return ["needs_not_a_static_job_list"], skippable
    if _normalize_if(job.get("if")) != "always()":
        violations.append("gate_job_if_is_not_exactly_always()")
    if job.get("continue-on-error") not in (None, False):
        violations.append("gate_job_continue_on_error")
    steps = job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        return [*violations, "gate_steps_not_static_list"], skippable
    parsed_gates = [
        (index, parsed)
        for index, step in enumerate(steps)
        if (parsed := _parse_ci_gate_invocation(step)) is not None
    ]
    if not parsed_gates:
        return [*violations, "gate_does_not_execute_enforcing_ci_gate"], skippable
    gate_index, (gate_jobs_arg, gate_allow_skipped, gate_packaging_needed) = parsed_gates[0]
    if len(parsed_gates) != 1 or gate_index != len(steps) - 1:
        violations.append("gate_step_is_not_the_single_last_step")
    # Nothing may run before the gate that could change what it executes (a rewritten
    # scripts/ci_gate.py, a prepended PATH entry, a local action): every other step must be a
    # full-SHA-pinned action of another repository.
    for index, step in enumerate(steps):
        if index == gate_index:
            continue
        uses = step.get("uses")
        if (
            "run" in step
            or not isinstance(uses, str)
            or uses.startswith(("./", "docker://"))
            or "${{" in uses
            or IMMUTABLE_ACTION_RE.fullmatch(uses) is None
        ):
            violations.append(f"gate_job_has_a_step_that_is_not_a_pinned_action:{index}")

    for needed in needs:
        spec = jobs.get(needed)
        if not isinstance(spec, dict):
            violations.append(f"needed_job_missing_or_not_mapping:{needed}")
            continue
        if spec.get("continue-on-error") not in (None, False):
            violations.append(f"needed_job_continue_on_error:{needed}")
        spec_strategy = spec.get("strategy")
        if spec_strategy is not None and not isinstance(spec_strategy, dict):
            violations.append(f"needed_job_strategy_not_statically_safe:{needed}")
        elif (
            isinstance(spec_strategy, dict)
            and _continue_on_error(spec_strategy.get("continue-on-error"))[0] != "PASS"
        ):
            violations.append(f"needed_job_strategy_continue_on_error:{needed}")
        for dependency in _needs_list(spec.get("needs")) or (
            [] if spec.get("needs") is None else ["?"]
        ):
            if dependency not in needs:
                violations.append(f"needed_job_dependency_not_inspected:{needed}->{dependency}")
        if _normalize_if(gate_jobs_arg.get(needed)) != f"needs.{needed}.result":
            violations.append(f"gate_does_not_inspect_result_of:{needed}")
            continue
        condition = spec.get("if")
        if condition is None:
            if needed in gate_allow_skipped:
                violations.append(f"non_skippable_job_allowed_skipped:{needed}")
            continue
        if isinstance(spec_strategy, dict) and spec_strategy.get("matrix") is not None:
            violations.append(f"matrix_job_cannot_be_skippable:{needed}")
            continue
        norm_cond = _normalize_if(condition) or ""
        match = _SKIP_OUTPUT_IF_RE.fullmatch(norm_cond)
        if match is None:
            violations.append(f"needed_job_can_be_skipped_unaccepted:{needed}")
            continue
        src_job, out_name = match.groups()
        if (
            src_job != "changes"
            or src_job not in needs
            or src_job == needed
            or needed not in gate_allow_skipped
            or _normalize_if(gate_packaging_needed) != f"needs.{src_job}.outputs.{out_name}"
        ):
            violations.append(f"needed_job_can_be_skipped_unaccepted:{needed}")
            continue
        skippable.append(needed)
    return violations, skippable


def _needed_job_matrix_safe(matrix: Any, needed_ids: list[str], skippable: list[str]) -> bool:
    if isinstance(matrix, str):
        norm = _normalize_if(matrix) or ""
        match = _MATRIX_OUTPUT_RE.fullmatch(norm)
        return (
            match is not None and match.group(1) in needed_ids and match.group(1) not in skippable
        )
    if not isinstance(matrix, dict) or not matrix:
        return False
    exclude = matrix.get("exclude")
    if exclude is not None and exclude != []:
        return False
    include = matrix.get("include")
    if include is not None and (
        not isinstance(include, list)
        or not include
        or not all(isinstance(item, dict) and bool(item) for item in include)
    ):
        return False
    axes = {k: v for k, v in matrix.items() if k not in {"include", "exclude"}}
    if not axes and include is None:
        return False
    return all(isinstance(val, list) and bool(val) for val in axes.values())


def _scan_steps(
    prefix: str,
    steps: list[dict[str, Any]],
    workflow_path: str,
    findings: list[dict[str, str]],
    counters: list[int],
    local_actions: set[str],
) -> None:
    """Per-step continue-on-error and action-trust findings; ``counters`` is [fail, unknown]."""
    for index, step in enumerate(steps):
        coe_status, coe_reason = _continue_on_error(step.get("continue-on-error"))
        if coe_status != "PASS":
            findings.append(
                {
                    "id": f"{prefix}.step_{index}.continue_on_error",
                    "status": coe_status,
                    "reason": coe_reason,
                    "path": workflow_path,
                }
            )
        if "uses" in step:
            uses = step.get("uses")
            status, reason = _action_status(uses)
            if status == "FAIL":
                counters[0] += 1
            elif status == "UNKNOWN":
                counters[1] += 1
            findings.append(
                {
                    "id": f"{prefix}.step_{index}.action_trust",
                    "status": status,
                    "reason": reason,
                    "path": workflow_path,
                }
            )
            if isinstance(uses, str) and uses.startswith("./"):
                local_actions.add(uses[2:].rstrip("/"))


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

    needed_ids: list[str] = []
    gate_jobs: list[tuple[str, dict[str, Any]]] = []
    gate_skippable: list[str] = []
    gate_verified = False
    if job.get("needs") is not None:
        violations, gate_skippable = _gate_assessment(jobs, job)
        gate_verified = not violations
        if gate_verified:
            needed_ids = _needs_list(job.get("needs")) or []
            gate_jobs = [(name, jobs[name]) for name in needed_ids]
            findings.append(
                {
                    "id": f"{context}.needs",
                    "status": "PASS",
                    "reason": "required_job_is_a_verified_gate_over_its_needs",
                    "path": workflow_path,
                }
            )
        else:
            findings.append(
                {
                    "id": f"{context}.needs",
                    "status": "UNKNOWN",
                    "reason": "required_job_needs_dependency_can_suppress_context_execution",
                    "detail": ",".join(violations),
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
    if strategy is not None and not isinstance(strategy, dict):
        findings.append(
            {
                "id": f"{context}.strategy",
                "status": "UNKNOWN",
                "reason": "required_job_strategy_not_statically_understood",
                "path": workflow_path,
            }
        )
    elif isinstance(strategy, dict):
        if strategy.get("matrix") is not None:
            findings.append(
                {
                    "id": f"{context}.matrix",
                    "status": "UNKNOWN",
                    "reason": "required_job_matrix_can_change_check_context_identity",
                    "path": workflow_path,
                }
            )
        scoe_status, scoe_reason = _continue_on_error(strategy.get("continue-on-error"))
        if scoe_status != "PASS":
            findings.append(
                {
                    "id": f"{context}.strategy_continue_on_error",
                    "status": scoe_status,
                    "reason": scoe_reason,
                    "path": workflow_path,
                }
            )

    def _defaults_safe(defaults: Any) -> bool:
        if defaults is None:
            return True
        if not isinstance(defaults, dict):
            return False
        run_defaults = defaults.get("run")
        if run_defaults is None:
            return True
        if not isinstance(run_defaults, dict):
            return False
        return (
            run_defaults.get("shell") in (None, "bash")
            and run_defaults.get("working-directory") is None
        )

    for defaults, scope in (
        (workflow.get("defaults"), "workflow"),
        (job.get("defaults"), "job"),
    ):
        if not _defaults_safe(defaults):
            findings.append(
                {
                    "id": f"{context}.{scope}_default_shell",
                    "status": "UNKNOWN",
                    "reason": "required_job_default_shell_not_statically_safe",
                    "path": workflow_path,
                }
            )

    job_if = _normalize_if(job.get("if"))
    if gate_verified:
        findings.append(
            {
                "id": f"{context}.job_if",
                "status": "PASS",
                "reason": "required_gate_job_always_runs",
                "path": workflow_path,
            }
        )
    elif job_if in {"false", "cancelled()"}:
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
    counters = [0, 0]
    # A verified gate also owns the steps of the jobs it needs; steps of a job that may be
    # skipped never count towards a required category.
    scopes: list[tuple[str, list[dict[str, Any]]]] = [(context, steps)]
    category_steps = list(steps)
    for name, spec_job in gate_jobs:
        if not _defaults_safe(spec_job.get("defaults")):
            findings.append(
                {
                    "id": f"{context}.{name}_default_shell",
                    "status": "UNKNOWN",
                    "reason": "needed_job_default_shell_not_statically_safe",
                    "path": workflow_path,
                }
            )
        spec_strategy = spec_job.get("strategy")
        if spec_strategy is not None and not isinstance(spec_strategy, dict):
            findings.append(
                {
                    "id": f"{context}.{name}.matrix",
                    "status": "UNKNOWN",
                    "reason": "needed_job_matrix_not_statically_safe",
                    "path": workflow_path,
                }
            )
        elif isinstance(spec_strategy, dict):
            spec_matrix = spec_strategy.get("matrix")
            if spec_matrix is not None and not _needed_job_matrix_safe(
                spec_matrix, needed_ids, gate_skippable
            ):
                findings.append(
                    {
                        "id": f"{context}.{name}.matrix",
                        "status": "UNKNOWN",
                        "reason": "needed_job_matrix_not_statically_safe",
                        "path": workflow_path,
                    }
                )
        needed_steps = spec_job.get("steps")
        if not isinstance(needed_steps, list) or not all(
            isinstance(step, dict) for step in needed_steps
        ):
            findings.append(
                {
                    "id": f"{context}.{name}.steps",
                    "status": "UNKNOWN",
                    "reason": "needed_job_steps_not_static_list",
                    "path": workflow_path,
                }
            )
            continue
        scopes.append((f"{context}.{name}", needed_steps))
        if name not in gate_skippable:
            category_steps.extend(needed_steps)

    for prefix, scope_steps in scopes:
        _scan_steps(prefix, scope_steps, workflow_path, findings, counters, local_actions)
    action_failures, action_unknowns = counters

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
        status, reason = _category_status(category, category_steps)
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
    """Explicit single-base mode: ``base`` is both the trusted policy source and
    the comparison base (a fresh candidate whose base is current main)."""
    return _inspect(repo, base, head, comparison_base=base, derivation="explicit_single_base")


def inspect_candidate(repo: Path, trusted: str, head: str) -> dict[str, Any]:
    """Three-identity mode: ``trusted`` is the executing validator's own source
    and the trusted policy baseline; the comparison base is derived as the
    merge base of ``trusted`` and ``head`` (``_comparison_base``)."""
    try:
        _validate_commit(repo.resolve(), trusted)
        _validate_commit(repo.resolve(), head)
        comparison = _comparison_base(repo.resolve(), trusted, head)
    except InspectionError as exc:
        return _unknown_report(trusted, head, None, str(exc))
    return _inspect(repo, trusted, head, comparison_base=comparison, derivation="merge_base")


def _unknown_report(trusted: str, head: str, comparison: str | None, reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "trusted_validator": {"sha": trusted},
        "comparison_base": {"sha": comparison},
        "candidate": {"sha": head},
        "inspected_files": [],
        "changed_protected_surfaces": [],
        "invariant_results": [
            {"id": "source_identity", "status": "UNKNOWN", "reason": reason, "path": None}
        ],
        "overall_classification": "UNKNOWN",
        "reasons": [reason],
        "candidate_code_executed": False,
    }


def _inspect(
    repo: Path, base: str, head: str, *, comparison_base: str, derivation: str
) -> dict[str, Any]:
    repo = repo.resolve()
    inspected: set[str] = set()
    try:
        base_tree = _validate_commit(repo, base)
        head_tree = _validate_commit(repo, head)
        comparison_tree = _validate_commit(repo, comparison_base)
        changed = _changed_paths(repo, comparison_base, head)
    except InspectionError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "trusted_validator": {"sha": base},
            "comparison_base": {"sha": comparison_base, "derivation": derivation},
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
        elif Path(path).name == "conftest.py":
            impact = "pytest_control_surface"
            review_reasons.append(f"pytest_control_surface_changed:{path}")
        elif Path(path).name in {
            "pyproject.toml",
            "ruff.toml",
            ".ruff.toml",
            "mypy.ini",
            ".mypy.ini",
            "pytest.ini",
            "tox.ini",
            "setup.cfg",
            "setup.py",
        }:
            impact = "quality_tool_configuration"
            review_reasons.append(f"quality_tool_configuration_changed:{path}")
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
        # The executing validator's own source, also the trusted policy baseline.
        "trusted_validator": {"sha": base, "tree": base_tree},
        # What the candidate's changes are measured against.
        "comparison_base": {
            "sha": comparison_base,
            "tree": comparison_tree,
            "derivation": derivation,
        },
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
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--trusted",
        help="trusted validator source; the comparison base is its merge base with --head",
    )
    source.add_argument(
        "--base", help="explicit single base: trusted policy source and comparison base"
    )
    parser.add_argument("--head", required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if args.trusted is not None:
        report = inspect_candidate(args.repo, args.trusted, args.head)
    else:
        report = inspect_required_check_definitions(args.repo, args.base, args.head)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return _exit_code(report["overall_classification"])


if __name__ == "__main__":
    raise SystemExit(main())
