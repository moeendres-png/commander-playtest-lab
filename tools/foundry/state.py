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
import os
import re
import subprocess
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+$")
SUPPORTED_VERSIONS = ("1.0", "2.0")
MATERIALITY_VALUES = ("MATERIAL", "NON_MATERIAL")
REVIEW_VERDICTS = ("PASS", "FAIL", "PARTIAL", "UNKNOWN", "BLOCKED", "STALE")
REVIEW_ALIAS_CLASSES = ("CANONICAL", "LEGACY_ALIAS")
REVIEW_EXECUTOR_PROFILES = ("deepseek", "space-bunny")

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

REASONING_TIERS = {"high", "xhigh", "max"}  # high retained for historical state compatibility


def _git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _validate_review_mirror(value: Any, errors: list[str]) -> None:
    """Structural validation of the cross_executor_review mirror (policy fields).

    Historical states omit this field entirely; presence opts the workstream
    into the fail-closed review policy. Deep admission checks live in
    review_gate.py; this layer only guarantees parseable structure.
    """
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append("cross_executor_review must be a mapping or null")
        return
    if not isinstance(value.get("required"), bool):
        errors.append("cross_executor_review.required must be a bool")
    if value.get("logical_profile") not in (None, "space-bunny"):
        errors.append("cross_executor_review.logical_profile must be space-bunny")
    if value.get("review_executor") not in (None, *REVIEW_EXECUTOR_PROFILES):
        errors.append(
            f"bad cross_executor_review.review_executor: {value.get('review_executor')!r}"
        )
    if value.get("implementation_executor") not in (None, *REVIEW_EXECUTOR_PROFILES):
        errors.append(
            f"bad cross_executor_review.implementation_executor: "
            f"{value.get('implementation_executor')!r}"
        )
    if value.get("model_alias_class") not in (None, *REVIEW_ALIAS_CLASSES):
        errors.append(
            f"bad cross_executor_review.model_alias_class: {value.get('model_alias_class')!r}"
        )
    if value.get("verdict") not in (None, *REVIEW_VERDICTS):
        errors.append(f"bad cross_executor_review.verdict: {value.get('verdict')!r}")
    for field in ("reviewed_sha", "reviewed_tree"):
        item = value.get(field)
        if item is not None and not SHA_RE.match(str(item)):
            errors.append(f"bad cross_executor_review.{field}: {item!r}")
    if value.get("resolved_model_id") is not None and not str(value["resolved_model_id"]).strip():
        errors.append("cross_executor_review.resolved_model_id must be a non-empty string")
    if value.get("review_record_path") is not None and not str(value["review_record_path"]).strip():
        errors.append("cross_executor_review.review_record_path must be a non-empty string")


def _validate_remote_checkpoint(value: Any, errors: list[str]) -> None:
    """Structural validation of the recorded remote milestone checkpoint."""
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append("remote_checkpoint must be a mapping or null")
        return
    for field in ("sha", "tree"):
        if not SHA_RE.match(str(value.get(field, ""))):
            errors.append(f"bad remote_checkpoint.{field}: {value.get(field)!r}")
    for field in ("remote", "branch"):
        if not str(value.get(field, "")).strip():
            errors.append(f"remote_checkpoint.{field} must be a non-empty string")


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
    validated_tree = data.get("validated_tree")
    if validated_tree is not None and not SHA_RE.match(str(validated_tree)):
        errors.append(f"bad validated_tree: {validated_tree!r} (want 40 hex chars or null)")
    declared_materiality = data.get("materiality")
    if declared_materiality is not None and declared_materiality not in MATERIALITY_VALUES:
        errors.append(
            f"bad materiality: {declared_materiality!r} (want one of {list(MATERIALITY_VALUES)})"
        )
    _validate_review_mirror(data.get("cross_executor_review"), errors)
    _validate_remote_checkpoint(data.get("remote_checkpoint"), errors)
    logical_profile = data.get("logical_executor_profile")
    if logical_profile is not None and logical_profile not in REVIEW_EXECUTOR_PROFILES:
        errors.append(
            f"bad logical_executor_profile: {logical_profile!r} (want one of "
            f"{list(REVIEW_EXECUTOR_PROFILES)})"
        )
    alias_class = data.get("model_alias_class")
    if alias_class is not None and alias_class not in REVIEW_ALIAS_CLASSES:
        errors.append(f"bad model_alias_class: {alias_class!r}")
    for field in ("resolved_provider", "resolved_model_id"):
        value = data.get(field)
        if value is not None and not str(value).strip():
            errors.append(f"{field} must be a non-empty string when present")


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


class StateWriteError(ValueError):
    """Fail-closed state-write refusal (invalid, forged, or unsafe replacement)."""


IMMUTABLE_IDENTITY_FIELDS = (
    "repository",
    "worktree",
    "branch",
    "audit_base_sha",
    "audit_base_tree",
)

_UNSET: Any = object()


def dump_state(doc: dict) -> str:
    """Serialize a state mapping via the single structured choke point.

    Only ever called on parsed mappings; free-form scalars are quoted/escaped
    by the serializer, never by hand, so malformed YAML is structurally
    impossible through the normal write API.
    """
    if not isinstance(doc, dict):
        raise StateWriteError("state document must be a mapping")
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync (durability hint; failure is never fatal)."""
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_write_text(state_path: str, text: str) -> None:
    """Same-directory temp + flush/fsync + atomic os.replace + dir fsync.

    A crash at any point leaves the old complete file or the new complete
    file, never a partial truncation. Preserves the existing file mode; new
    files use 0o644 (repo convention for state YAML).
    """
    target = Path(state_path)
    parent = target.parent if str(target.parent) else Path(".")
    parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = target.stat().st_mode & 0o777
    except OSError:
        mode = 0o644
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(parent))
    temp_path = Path(temp_name)
    descriptor_open = True
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor_open = False
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        _fsync_directory(parent)
    except BaseException:
        if descriptor_open:
            with suppress(OSError):
                os.close(descriptor)
        with suppress(OSError):
            temp_path.unlink(missing_ok=True)
        raise


def _read_existing_mapping(state_path: str) -> dict | None:
    """On-disk mapping, or None when absent, unparseable, or a non-mapping."""
    try:
        with open(state_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _check_proposed_ancestry(doc: dict, workdir: str) -> list[str]:
    """Validation-credit ancestry for a PROPOSED document (not the file).

    Mirrors check_validated_ancestry semantics: a non-null validated_head must
    descend from the proposed audit_base_sha and be an ancestor-or-equal of
    live HEAD. Null stays honest and yields no problem.
    """
    validated = doc.get("validated_head")
    if validated is None:
        return []
    base = doc.get("audit_base_sha")
    problems: list[str] = []
    if base and not _is_ancestor(str(base), str(validated), workdir):
        problems.append(
            f"VALIDATED_OUTSIDE_LOCK: validated_head {validated} does not "
            f"descend from audit_base_sha {base}"
        )
    try:
        live = _git(["rev-parse", "HEAD"], workdir)
    except RuntimeError as exc:
        return [*problems, f"cannot read live HEAD: {exc}"]
    if not _is_ancestor(str(validated), live, workdir):
        problems.append(
            f"VALIDATED_REWRITTEN: validated_head {validated} is not an "
            f"ancestor of live HEAD {live} (history moved; revalidate)"
        )
    tree = doc.get("validated_tree")
    if tree is not None:
        try:
            live_tree = _git(["rev-parse", f"{validated}^{{tree}}"], workdir)
        except RuntimeError:
            live_tree = None
        if live_tree != str(tree):
            problems.append(
                f"VALIDATED_TREE_MISMATCH: validated_tree {tree} != live tree of "
                f"{validated} ({live_tree!r}); revalidate the exact identity"
            )
    return problems


def write_state(
    state_path: str,
    doc: dict,
    *,
    workdir: str | None = None,
    allow_identity_change: bool = False,
) -> dict:
    """Validate-then-atomically-replace the state file. Returns the doc.

    Fail-closed: schema-invalid state, silent source-lock identity mutation,
    and ancestry-violating validation credit are all refused BEFORE the
    on-disk file is touched. validated_head is taken exactly as given and
    never auto-promoted. No enum normalization exists: invalid vocabulary
    (e.g. candidate-prefixed failure classes) is rejected, never coerced.

    Validation-credit invariant (PR #178 P1): NO canonical normal writer path
    may persist non-null validated_head without a workdir and proven
    ancestry. A non-null validated_head with workdir=None fails closed here,
    at the shared API boundary, so write_state and update_state (which
    delegates here) are both covered -- including update_state preserving a
    previously stored non-null credit without a workdir. Null stays honest
    and needs no workdir; clearing to null stays possible without a workdir.
    """

    if not isinstance(doc, dict):
        raise StateWriteError("state document must be a mapping")
    errors = validate(doc)
    if errors:
        raise StateWriteError(f"invalid state: {errors[0]}")
    existing = _read_existing_mapping(state_path)
    if existing is None:
        if Path(state_path).exists() and not allow_identity_change:
            raise StateWriteError(
                "existing state is missing, unparseable, or a non-mapping: "
                "identity cannot be compared; pass allow_identity_change=True "
                "as an explicit rebind to replace it"
            )
    else:
        for field in IMMUTABLE_IDENTITY_FIELDS:
            if existing.get(field) != doc.get(field) and not allow_identity_change:
                raise StateWriteError(
                    f"immutable source-lock field {field!r} differs "
                    f"(existing {existing.get(field)!r} vs proposed {doc.get(field)!r}); "
                    "pass allow_identity_change=True as an explicit rebind to change it"
                )
    if doc.get("validated_head") is not None:
        if workdir is None:
            raise StateWriteError(
                "validated_head is non-null but no workdir was supplied: "
                "validation-credit ancestry cannot be proven without live Git; "
                "pass workdir=... (or --workdir) to ancestry-check the claim, "
                "or clear validation credit to null"
            )
        problems = _check_proposed_ancestry(doc, workdir)
        if problems:
            raise StateWriteError(problems[0])
    atomic_write_text(state_path, dump_state(doc))
    try:
        with open(state_path, encoding="utf-8") as handle:
            reread = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise StateWriteError(f"write readback failed: {exc}") from exc
    reread_errors = validate(reread if isinstance(reread, dict) else {})
    if reread_errors:
        raise StateWriteError(f"write readback invalid: {reread_errors[0]}")
    return doc


def update_state(
    state_path: str,
    patch: dict,
    *,
    workdir: str | None = None,
    validated_head: Any = _UNSET,
    validated_tree: Any = _UNSET,
    stamp_head: bool = False,
    allow_identity_change: bool = False,
) -> dict:
    """Merge a MUTABLE-field patch onto the existing file, then write_state.

    "validated_head" inside the patch mapping is rejected: validation credit
    changes only via the explicit validated_head parameter (None = honest
    null, str = claimed SHA, omitted = preserved). validated_tree travels with
    validated_head through the same explicit parameter. stamp_head stamps
    state_written_against_head from live workdir HEAD (descriptive only).
    """
    if not isinstance(patch, dict):
        raise StateWriteError("state patch must be a mapping")
    if "validated_head" in patch:
        raise StateWriteError(
            "validated_head must be supplied via the explicit validated_head "
            "parameter, not the patch mapping"
        )
    if "validated_tree" in patch:
        raise StateWriteError(
            "validated_tree must be supplied via the explicit validated_tree "
            "parameter, not the patch mapping"
        )
    for field in IMMUTABLE_IDENTITY_FIELDS:
        if field in patch and not allow_identity_change:
            raise StateWriteError(
                f"immutable source-lock field {field!r} cannot be set via a "
                "checkpoint update; pass allow_identity_change=True as an "
                "explicit rebind to change it"
            )
    try:
        with open(state_path, encoding="utf-8") as handle:
            existing = yaml.safe_load(handle)
    except OSError as exc:
        raise StateWriteError(f"cannot read existing state: {exc}") from exc
    except yaml.YAMLError as exc:
        raise StateWriteError(f"existing state is not parseable YAML: {exc}") from exc
    if not isinstance(existing, dict):
        raise StateWriteError("existing state is not a mapping")
    merged = dict(existing)
    merged.update(patch)
    if validated_head is not _UNSET:
        merged["validated_head"] = validated_head
        if validated_head is None:
            merged["validated_tree"] = None
    if validated_tree is not _UNSET:
        merged["validated_tree"] = validated_tree
    if stamp_head:
        if workdir is None:
            raise StateWriteError("stamp_head requires workdir")
        try:
            merged["state_written_against_head"] = _git(["rev-parse", "HEAD"], workdir)
        except RuntimeError as exc:
            raise StateWriteError(f"cannot read live HEAD to stamp: {exc}") from exc
    return write_state(
        state_path, merged, workdir=workdir, allow_identity_change=allow_identity_change
    )


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
    tree = data.get("validated_tree")
    if tree is not None:
        try:
            live_tree = _git(["rev-parse", f"{validated}^{{tree}}"], workdir)
        except RuntimeError:
            live_tree = None
        if live_tree != str(tree):
            problems.append(
                f"VALIDATED_TREE_MISMATCH: validated_tree {tree} != live tree of "
                f"{validated} ({live_tree!r}); revalidate the exact identity"
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


def _load_structured(path: str, role: str) -> Any:
    """Parse a JSON/YAML input file structurally (never string-concatenated)."""
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except OSError as exc:
        raise StateWriteError(f"cannot read {role} file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise StateWriteError(f"cannot parse {role} file {path}: {exc}") from exc


def _main_write(args: argparse.Namespace) -> int:
    if args.write_from and args.patch_file:
        print("STATE_REJECT: --write-from and --patch-file are mutually exclusive", file=sys.stderr)
        return 1
    if (args.set_validated_head is not None or args.clear_validated_head) and not args.patch_file:
        print(
            "STATE_REJECT: --set-validated-head/--clear-validated-head require --patch-file",
            file=sys.stderr,
        )
        return 1
    if args.set_validated_head is not None and args.clear_validated_head:
        print(
            "STATE_REJECT: --set-validated-head and --clear-validated-head are mutually exclusive",
            file=sys.stderr,
        )
        return 1
    if args.set_validated_tree is not None and args.set_validated_head is None:
        print(
            "STATE_REJECT: --set-validated-tree requires --set-validated-head "
            "(tree credit always travels with commit credit)",
            file=sys.stderr,
        )
        return 1
    if args.set_validated_tree is not None and not SHA_RE.match(str(args.set_validated_tree)):
        print(
            "STATE_REJECT: --set-validated-tree must be a 40-hex tree",
            file=sys.stderr,
        )
        return 1
    if args.stamp_head and (not args.patch_file or not args.workdir):
        print("STATE_REJECT: --stamp-head requires --patch-file and --workdir", file=sys.stderr)
        return 1
    # P1 (PR #178): claiming non-null validation credit without a workdir
    # fails closed at the CLI as well as the shared API boundary. Clearing to
    # null stays possible without a workdir; the preserved-credit case is
    # enforced inside write_state/update_state.
    if args.set_validated_head is not None and not args.workdir:
        print(
            "STATE_REJECT: --set-validated-head requires --workdir for "
            "ancestry-checked validation credit",
            file=sys.stderr,
        )
        return 1
    try:
        if args.write_from:
            doc = _load_structured(args.write_from, "input")
            if isinstance(doc, dict) and doc.get("validated_head") is not None and not args.workdir:
                print(
                    "STATE_REJECT: --write-from document carries non-null "
                    "validated_head without --workdir (ancestry cannot be proven)",
                    file=sys.stderr,
                )
                return 1
            write_state(
                args.state,
                doc,
                workdir=args.workdir,
                allow_identity_change=args.allow_identity_change,
            )
        else:
            patch = _load_structured(args.patch_file, "patch")
            if patch is None:
                patch = {}
            validated: Any = _UNSET
            validated_tree_value: Any = _UNSET
            if args.set_validated_head is not None:
                validated = args.set_validated_head
                if args.set_validated_tree is not None:
                    validated_tree_value = args.set_validated_tree
                else:
                    try:
                        validated_tree_value = _git(
                            ["rev-parse", f"{args.set_validated_head}^{{tree}}"], args.workdir
                        )
                    except RuntimeError as exc:
                        print(
                            f"STATE_REJECT: cannot derive validated_tree for "
                            f"{args.set_validated_head!r}: {exc}",
                            file=sys.stderr,
                        )
                        return 1
            elif args.clear_validated_head:
                validated = None
            update_state(
                args.state,
                patch,
                workdir=args.workdir,
                validated_head=validated,
                validated_tree=validated_tree_value,
                stamp_head=args.stamp_head,
                allow_identity_change=args.allow_identity_change,
            )
    except StateWriteError as exc:
        print(f"STATE_REJECT: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"STATE_REJECT: write failed: {exc}", file=sys.stderr)
        return 1
    print(f"STATE_WRITTEN: {args.state}")
    return 0


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
    parser.add_argument(
        "--write-from",
        default=None,
        metavar="INPUT",
        help="Replace --state with the full state document in INPUT "
        "(JSON or YAML file, parsed structurally; validated before replace).",
    )
    parser.add_argument(
        "--patch-file",
        default=None,
        metavar="PATCH",
        help="Merge the mutable-field mapping in PATCH onto the existing "
        "--state file (checkpoint update; validated before replace).",
    )
    parser.add_argument(
        "--set-validated-head",
        default=None,
        metavar="SHA",
        help="Explicit validation-credit claim for update mode "
        "(requires --patch-file and --workdir for ancestry proof).",
    )
    parser.add_argument(
        "--set-validated-tree",
        default=None,
        metavar="TREE",
        help="Exact 40-hex tree for the validated implementation identity; "
        "requires --set-validated-head (derived from Git when omitted).",
    )
    parser.add_argument(
        "--clear-validated-head",
        action="store_true",
        help="Reset validation credit to null (requires --patch-file).",
    )
    parser.add_argument(
        "--stamp-head",
        action="store_true",
        help="Stamp state_written_against_head from live --workdir HEAD "
        "(descriptive only; requires --patch-file and --workdir).",
    )
    parser.add_argument(
        "--allow-identity-change",
        action="store_true",
        help="Explicit rebind: permit source-lock identity field changes "
        "(requires --write-from or --patch-file).",
    )
    parser.add_argument(
        "--check-review-gate",
        action="store_true",
        help="Evaluate the cross-executor review gate for this state document.",
    )
    parser.add_argument(
        "--fail-on-review-gate",
        action="store_true",
        help="Exit nonzero when the review gate is unsatisfied or stale.",
    )
    parser.add_argument(
        "--check-remote-checkpoint",
        action="store_true",
        help="Verify the recorded remote checkpoint against live remote state.",
    )
    parser.add_argument(
        "--fail-on-remote-checkpoint",
        action="store_true",
        help="Exit nonzero when the recorded remote checkpoint is missing or mismatched.",
    )
    parser.add_argument(
        "--check-completion-gate",
        action="store_true",
        help="Evaluate the full PR_READY/COMPLETE gate (review + remote checkpoint).",
    )
    parser.add_argument(
        "--completion-claim",
        choices=("PR_READY", "COMPLETE"),
        default=None,
        help="Claim to evaluate with --check-completion-gate "
        "(default: state status when it is COMPLETE).",
    )
    parser.add_argument(
        "--fail-on-completion-gate",
        action="store_true",
        help="Exit nonzero when a PR_READY/COMPLETE claim fails the policy gate.",
    )
    args = parser.parse_args(argv)
    # P2 (PR #178): any write-intent flag without a valid write mode must
    # return nonzero STATE_REJECT and must never silently fall through to
    # read-only validation (which would return STATE_OK). Valid write modes
    # are --write-from / --patch-file (structured writes) and --migrate
    # --in-place (migration write). Plain --migrate prints and stays read-only.
    has_structured_write = bool(args.write_from or args.patch_file)
    if args.in_place and not args.migrate:
        print("STATE_REJECT: --in-place requires --migrate", file=sys.stderr)
        return 1
    if args.migrate and has_structured_write:
        print(
            "STATE_REJECT: --migrate is mutually exclusive with --write-from/--patch-file",
            file=sys.stderr,
        )
        return 1
    if (
        args.set_validated_head is not None
        or args.clear_validated_head
        or args.set_validated_tree is not None
        or args.stamp_head
        or args.allow_identity_change
    ) and not has_structured_write:
        print(
            "STATE_REJECT: --set-validated-head/--set-validated-tree/"
            "--clear-validated-head/--stamp-head/--allow-identity-change require "
            "--write-from or --patch-file (refusing silent no-op)",
            file=sys.stderr,
        )
        return 1
    if args.write_from or args.patch_file:
        return _main_write(args)
    try:
        with open(args.state, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        print(f"STATE_INVALID: cannot read: {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"STATE_INVALID: cannot parse: {exc}", file=sys.stderr)
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
        if args.in_place:
            out_errors = validate(out)
            if out_errors:
                print(f"STATE_INVALID: {out_errors[0]}", file=sys.stderr)
                return 1
            try:
                atomic_write_text(args.state, dump_state(out))
            except OSError as exc:
                print(f"STATE_INVALID: migration write failed: {exc}", file=sys.stderr)
                return 1
            print(f"STATE_MIGRATED: {args.state} -> schema 2.0")
        else:
            print(dump_state(out), end="")
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
    try:
        rel_state = str(Path(args.state).resolve().relative_to(Path(args.workdir or ".").resolve()))
    except ValueError:
        rel_state = args.state
    review_result = None
    remote_result = None
    if args.check_review_gate or args.check_completion_gate:
        import review_gate as review_gate_mod

        review_result = review_gate_mod.evaluate_review_gate(
            data, workdir=args.workdir, state_path=rel_state
        )
        if args.check_review_gate:
            print(f"STATE_REVIEW: {review_result.status}: {review_result.reasons[0]}")
    if args.check_remote_checkpoint or args.check_completion_gate:
        import remote_checkpoint as remote_checkpoint_mod

        remote_result = remote_checkpoint_mod.verify_remote_checkpoint(
            data, workdir=args.workdir, state_paths=(rel_state,)
        )
        if args.check_remote_checkpoint:
            print(f"STATE_REMOTE: {remote_result.status}: {remote_result.reasons[0]}")
    version = data.get("schema_version") if isinstance(data, dict) else "?"
    print(f"STATE_OK: schema={version} status={data['status']} branch={data['branch']}")
    if args.fail_on_head_mismatch and warnings:
        return 1
    if args.fail_on_validated_problem and any(
        n.startswith("VALIDATED_OUTSIDE_LOCK")
        or n.startswith("VALIDATED_REWRITTEN")
        or n.startswith("VALIDATED_TREE_MISMATCH")
        for n in validated_notes
    ):
        return 1
    if args.fail_on_review_gate and review_result is not None and not review_result.ok:
        return 1
    if args.fail_on_remote_checkpoint and remote_result is not None and not remote_result.ok:
        return 1
    if args.check_completion_gate:
        claim = args.completion_claim
        if claim is None and str(data.get("status")) == "COMPLETE":
            claim = "COMPLETE"
        if claim is None:
            print("STATE_COMPLETION: SKIPPED (no PR_READY/COMPLETE claim)")
        else:
            import review_gate as review_gate_mod

            result = review_gate_mod.evaluate_completion_claim(
                data,
                claim=claim,
                workdir=args.workdir,
                state_path=rel_state,
                remote_verdict=(remote_result.status if remote_result else None),
            )
            if result.ok:
                print(f"STATE_COMPLETION: PASS ({claim})")
            else:
                print(f"STATE_COMPLETION: FAIL ({claim}): {result.reasons[0]}", file=sys.stderr)
                if args.fail_on_completion_gate:
                    return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
