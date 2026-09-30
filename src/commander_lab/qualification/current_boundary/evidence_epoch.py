"""Current-boundary evidence epoch identity (B1).

``qualification/final-current-boundary-20260927`` is the historical WSR22
current-boundary evidence epoch. It is a research record, not a scratch space:
every run that reuses the runner and writes into it replaces the historical
bytes in place, so "the historical evidence" and "the latest execution" become
the same directory and neither identity can be trusted.

This module defines the successor/runtime epoch instead:

* runs never write the historical epoch; resolution refuses it outright;
* a runtime epoch lives under ``qualification/current-boundary-epochs/`` and its
  identity is the producing source: the epoch id is derived from the executing
  commit and tree, so a new source cannot silently overwrite another source's
  evidence and the path itself names what produced it;
* an explicit ``CURRENT_BOUNDARY_EVIDENCE_EPOCH`` override may select a
  different epoch root, but only inside this repository's ``qualification/``
  tree and never the historical epoch;
* ``EPOCH_IDENTITY.json`` inside the epoch is machine-readable proof of the
  producing source and is written once; a run whose source differs from an
  existing identity fails closed instead of overwriting.

The runner and the assembler both resolve through :func:`epoch_root`, so they
cannot disagree about where the evidence lives.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .receipts import clean_git_environment

#: Git reads that identify the producing source must complete or fail closed.
_GIT_TIMEOUT_SECONDS = 60

EPOCH_IDENTITY_SCHEMA = "commander-lab.current-boundary-epoch-identity/1.0.0"
HISTORICAL_EPOCH_ID = "final-current-boundary-20260927"
EPOCH_PARENT = "current-boundary-epochs"
EPOCH_ENV = "CURRENT_BOUNDARY_EVIDENCE_EPOCH"
EPOCH_IDENTITY_FILENAME = "EPOCH_IDENTITY.json"

_SHA = re.compile(r"[0-9a-f]{40}")

#: The epoch id is a source identity, so an inherited Git redirection must not
#: be able to name another repository's commit; receipts.clean_git_environment
#: owns the canonical list of variables that are stripped.


class EvidenceEpochError(RuntimeError):
    """The evidence epoch is absent, ambiguous, historical, or foreign-sourced."""


def _git(repo_root: Path, *args: str) -> str:
    """A Git fact the epoch identity needs; unavailable means fail closed.

    The read uses the canonical sanitized environment and the same completion
    timeout as receipts so an epoch identity can never be answered by another
    checkout or by a hung Git process.
    """
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=clean_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceEpochError(
            f"git {' '.join(args)} in {repo_root} did not complete: {exc}. An evidence epoch "
            "cannot be identified without a source identity."
        ) from exc
    if completed.returncode != 0:
        raise EvidenceEpochError(
            f"git {' '.join(args)} failed in {repo_root} (exit {completed.returncode}): "
            f"{completed.stderr.strip()[:200]}. An evidence epoch cannot be identified without "
            "a source identity."
        )
    return completed.stdout.strip()


def _git_sha(repo_root: Path, *args: str) -> str:
    value = _git(repo_root, *args)
    if not _SHA.fullmatch(value):
        raise EvidenceEpochError(
            f"git {' '.join(args)} in {repo_root} returned {value!r}, not a full SHA"
        )
    return value


def source_identity(repo_root: Path) -> dict[str, str]:
    """The producing source identity: commit, tree and branch of the checkout."""
    repository = "UNCONFIGURED"
    try:
        repository = _git(repo_root, "config", "--get", "remote.origin.url") or "UNCONFIGURED"
    except EvidenceEpochError:
        # A checkout with no origin is still bindable; the identity that matters
        # is which bytes run, not which remote they came from.
        repository = "UNCONFIGURED"
    return {
        "repository": repository,
        "commit": _git_sha(repo_root, "rev-parse", "HEAD"),
        "tree": _git_sha(repo_root, "rev-parse", "HEAD^{tree}"),
        "branch": _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD") or "UNKNOWN",
    }


def source_bound_epoch_id(commit: str, tree: str) -> str:
    """The epoch id a source identity produces: commit and tree, never a label."""
    if not _SHA.fullmatch(commit) or not _SHA.fullmatch(tree):
        raise EvidenceEpochError(
            f"epoch identity requires full commit and tree SHAs, got {commit!r}/{tree!r}"
        )
    return f"{commit[:12]}-{tree[:12]}"


def _qualification_root(repo_root: Path) -> Path:
    return (repo_root / "qualification").resolve()


def _reject_historical(path: Path, repo_root: Path) -> None:
    historical = (_qualification_root(repo_root) / HISTORICAL_EPOCH_ID).resolve()
    if path == historical or historical in path.parents:
        raise EvidenceEpochError(
            f"{path} is inside the historical WSR22 evidence epoch "
            f"({historical}). Historical evidence is read-only: a new execution must write to a "
            f"successor epoch under qualification/{EPOCH_PARENT}/."
        )


def historical_epoch_root(repo_root: Path) -> Path:
    """The read-only historical WSR22 evidence epoch."""
    return _qualification_root(repo_root) / HISTORICAL_EPOCH_ID


def epoch_root(repo_root: Path | None = None, *, environ: Mapping[str, str] | None = None) -> Path:
    """Resolve the runtime evidence epoch root, fail closed on ambiguity.

    Default: ``qualification/current-boundary-epochs/<commit12>-<tree12>/`` for
    the executing checkout, so the epoch path itself is bound to the source that
    produced it. The ``CURRENT_BOUNDARY_EVIDENCE_EPOCH`` override is explicit and
    must stay inside this repository's ``qualification/`` tree; the historical
    epoch is never a legal target.
    """
    if repo_root is None:
        raise EvidenceEpochError("repo_root is required to resolve the evidence epoch")
    source = os.environ if environ is None else environ
    explicit = str(source.get(EPOCH_ENV) or "").strip()
    if explicit:
        candidate = Path(explicit)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        candidate = candidate.resolve()
        qualification = _qualification_root(repo_root)
        epochs_parent = qualification / EPOCH_PARENT
        if candidate != epochs_parent and epochs_parent not in candidate.parents:
            raise EvidenceEpochError(
                f"{EPOCH_ENV}={explicit!r} resolves to {candidate}, outside {epochs_parent}; a "
                "runtime evidence epoch must live under the epochs parent, so every run output "
                "is attributable and excluded from source dirtiness. The historical epoch is "
                "never a legal target."
            )
        _reject_historical(candidate, repo_root)
        return candidate
    identity = source_identity(repo_root)
    return (
        _qualification_root(repo_root)
        / EPOCH_PARENT
        / source_bound_epoch_id(identity["commit"], identity["tree"])
    )


def relative_epoch_root(repo_root: Path, *, environ: Mapping[str, str] | None = None) -> str:
    """The epoch root as a repository-relative POSIX path (machine-readable)."""
    root = epoch_root(repo_root, environ=environ)
    return _relative_to_repo(root, repo_root)


def _relative_to_repo(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        # An explicit override is required to be inside qualification/, but the
        # report must never silently fabricate a location.
        return str(path.resolve())


def _epoch_id_for(root: Path, repo_root: Path) -> str:
    qualification = _qualification_root(repo_root)
    for base in (qualification / EPOCH_PARENT, qualification):
        try:
            return root.relative_to(base).as_posix()
        except ValueError:
            continue
    # An explicitly located epoch outside the repository still needs an id; its
    # directory name is the explicit identity the operator chose.
    return root.name


def epoch_identity_path(epoch_root_path: Path) -> Path:
    return epoch_root_path / EPOCH_IDENTITY_FILENAME


def load_epoch_identity(epoch_root_path: Path) -> dict[str, Any] | None:
    """Read an existing epoch identity; malformed identity fails closed."""
    path = epoch_identity_path(epoch_root_path)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceEpochError(f"unreadable epoch identity at {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise EvidenceEpochError(f"epoch identity at {path} is not an object")
    if document.get("schema_version") != EPOCH_IDENTITY_SCHEMA:
        raise EvidenceEpochError(
            f"epoch identity at {path} has schema {document.get('schema_version')!r}, "
            f"expected {EPOCH_IDENTITY_SCHEMA!r}"
        )
    producing = document.get("producing_source")
    if not isinstance(producing, dict) or not _SHA.fullmatch(str(producing.get("commit", ""))):
        raise EvidenceEpochError(f"epoch identity at {path} names no producing source commit")
    return document


def ensure_epoch_identity(
    epoch_root_path: Path,
    *,
    repo_root: Path,
    now: str | None = None,
) -> dict[str, Any]:
    """Create the epoch identity on first use; refuse a foreign-producing source.

    The identity is written exactly once per epoch. A later run whose source
    commit/tree differs cannot reuse the epoch: it must resolve a different
    epoch (the default already does) rather than overwriting evidence that
    another source produced.
    """
    identity = source_identity(repo_root)
    existing = load_epoch_identity(epoch_root_path)
    if existing is not None:
        producing = existing["producing_source"]
        if (
            str(producing.get("commit")) != identity["commit"]
            or str(producing.get("tree")) != identity["tree"]
        ):
            raise EvidenceEpochError(
                f"epoch {epoch_root_path} was produced by {str(producing.get('commit'))[:12]}/"
                f"{str(producing.get('tree'))[:12]}, not by the executing source "
                f"{identity['commit'][:12]}/{identity['tree'][:12]}. Refusing to overwrite another "
                "source's evidence; select a different epoch explicitly with "
                f"{EPOCH_ENV}, or re-run from the producing source."
            )
        return existing
    document: dict[str, Any] = {
        "schema_version": EPOCH_IDENTITY_SCHEMA,
        "epoch_id": _epoch_id_for(epoch_root_path, repo_root),
        "epoch_root": _relative_to_repo(epoch_root_path, repo_root),
        "predecessor_epoch": f"qualification/{HISTORICAL_EPOCH_ID}",
        "predecessor_is_read_only": True,
        "producing_source": identity,
        "created_utc": now or datetime.now(UTC).isoformat(timespec="seconds"),
        "authority": (
            "operational evidence identity, not a qualification verdict: it names which source "
            "produced the bytes in this epoch"
        ),
    }
    epoch_root_path.mkdir(parents=True, exist_ok=True)
    target = epoch_identity_path(epoch_root_path)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    os.replace(temporary, target)
    return document


def require_epoch_identity(
    epoch_root_path: Path,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    """Load the epoch identity and require it to name the executing source.

    This is the assembler's gate: evidence is credited only from an epoch whose
    recorded producing source is the source executing the assembly. An absent
    identity means no runner produced this epoch in this run, and a foreign one
    means the bytes belong to another source.
    """
    existing = load_epoch_identity(epoch_root_path)
    if existing is None:
        raise EvidenceEpochError(
            f"no epoch identity at {epoch_identity_path(epoch_root_path)}: this epoch has no "
            "recorded producing source, so its evidence cannot be attributed. Run "
            "scripts/run_current_boundary_qualification.py first."
        )
    identity = source_identity(repo_root)
    producing = existing["producing_source"]
    if (
        str(producing.get("commit")) != identity["commit"]
        or str(producing.get("tree")) != identity["tree"]
    ):
        raise EvidenceEpochError(
            f"epoch {epoch_root_path} was produced by {str(producing.get('commit'))[:12]}/"
            f"{str(producing.get('tree'))[:12]}, but the assembling source is "
            f"{identity['commit'][:12]}/{identity['tree'][:12]}; refusing to credit evidence "
            "produced by a different source"
        )
    return existing
