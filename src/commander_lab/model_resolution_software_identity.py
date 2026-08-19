from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


class ModelResolutionSoftwareIdentityError(ValueError):
    """Raised when the model-resolution software identity cannot be proven."""


MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION = "model-resolution-software-identity-1.1.0"

# This scope intentionally follows the software that can change the bounded Structural
# resolution measurement. External-engine gameplay contracts such as models/game.py,
# engine/rules, and the XMage bridge are deliberately outside this identity: changing
# them must not silently reclassify a same-model Structural calibration as stale.
# Adding a new dependency to the measurement path requires adding it here.
_RELEVANT_GIT_PATHS = (
    "src/commander_lab/model_resolution_measurement.py",
    "src/commander_lab/engine/structural",
    "src/commander_lab/whole_deck",
    "src/commander_lab/agents",
    "src/commander_lab/fresh_rebuild.py",
    "src/commander_lab/repositories/candidates.py",
    "src/commander_lab/canonical_features.py",
    "src/commander_lab/deck_registry.py",
    "src/commander_lab/semantic_features.py",
    "src/commander_lab/mana_analysis.py",
    "src/commander_lab/decision_statistics.py",
    "src/commander_lab/pod_scheduling.py",
    "src/commander_lab/pod_scheduling_5p.py",
    "src/commander_lab/project_context.py",
    "src/commander_lab/storage",
    "src/commander_lab/models/cards.py",
    "src/commander_lab/models/common.py",
    "src/commander_lab/models/pilots.py",
    "src/commander_lab/models/roles.py",
    "src/commander_lab/models/structural.py",
    "src/commander_lab/models/opponents.py",
    "src/commander_lab/models/opponent_ensembles.py",
    "scripts/measure_model_resolution.py",
    "pyproject.toml",
)


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ModelResolutionSoftwareIdentityError(
            "model-resolution software identity requires an intact Git checkout"
        ) from exc


def model_resolution_software_scope() -> tuple[str, ...]:
    """Return the auditable tracked path scope for Structural resolution freshness."""

    return _RELEVANT_GIT_PATHS


def model_resolution_software_identity(root: str | Path) -> dict[str, Any]:
    """Return a content-addressed identity for software that can affect the measurement.

    Git object identities are deliberately used instead of the commit SHA. A merge commit therefore
    preserves freshness when the relevant content is byte-identical. Dirty tracked files in the
    declared resolution scope fail closed. Unrelated external-engine/UI code does not invalidate a
    same-model Structural calibration merely because it lives under ``src/commander_lab``.
    """

    project = Path(root).resolve()
    dirty = _git(
        project,
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        *_RELEVANT_GIT_PATHS,
    )
    if dirty:
        raise ModelResolutionSoftwareIdentityError(
            "model-resolution software identity is unavailable for dirty tracked software inputs"
        )

    source_objects = {
        path: _git(project, "rev-parse", f"HEAD:{path}").lower() for path in _RELEVANT_GIT_PATHS
    }
    for path, value in source_objects.items():
        if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
            raise ModelResolutionSoftwareIdentityError(
                f"invalid Git object identity for resolution source path {path}"
            )

    source_manifest_sha256 = hashlib.sha256(
        json.dumps(source_objects, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    canonical = {
        "identity_version": MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION,
        "resolution_source_manifest_sha256": source_manifest_sha256,
        "measurement_entrypoint_blob_sha1": source_objects["scripts/measure_model_resolution.py"],
        "package_manifest_blob_sha1": source_objects["pyproject.toml"],
    }
    identity_sha256 = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "1.1.0",
        **canonical,
        "identity_sha256": identity_sha256,
        "source_objects": source_objects,
        "scope_paths": list(_RELEVANT_GIT_PATHS),
        "freshness_semantics": "content_addressed_resolution_relevant_software_not_commit_identity",
    }


__all__ = [
    "MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION",
    "ModelResolutionSoftwareIdentityError",
    "model_resolution_software_identity",
    "model_resolution_software_scope",
]
