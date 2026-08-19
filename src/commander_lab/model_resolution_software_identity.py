from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


class ModelResolutionSoftwareIdentityError(ValueError):
    """Raised when the model-resolution software identity cannot be proven."""


MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION = "model-resolution-software-identity-1.0.0"
_RELEVANT_GIT_PATHS = {
    "commander_lab_tree_sha1": "src/commander_lab",
    "measurement_entrypoint_blob_sha1": "scripts/measure_model_resolution.py",
    "package_manifest_blob_sha1": "pyproject.toml",
}


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


def model_resolution_software_identity(root: str | Path) -> dict[str, Any]:
    """Return a content-addressed identity for software that can affect the measurement.

    Git object identities are deliberately used instead of the commit SHA. A merge commit therefore
    preserves freshness when the relevant content is byte-identical, while any tracked change to
    the Commander Lab source tree, measurement entry point, or package manifest invalidates the
    stored measurement. Dirty tracked files in the same scope fail closed.
    """

    project = Path(root).resolve()
    dirty = _git(
        project,
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        *_RELEVANT_GIT_PATHS.values(),
    )
    if dirty:
        raise ModelResolutionSoftwareIdentityError(
            "model-resolution software identity is unavailable for dirty tracked software inputs"
        )

    components = {
        key: _git(project, "rev-parse", f"HEAD:{path}").lower()
        for key, path in _RELEVANT_GIT_PATHS.items()
    }
    for key, value in components.items():
        if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
            raise ModelResolutionSoftwareIdentityError(f"invalid Git object identity for {key}")

    canonical = {
        "identity_version": MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION,
        **components,
    }
    identity_sha256 = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "1.0.0",
        **canonical,
        "identity_sha256": identity_sha256,
        "freshness_semantics": "content_addressed_relevant_software_not_commit_identity",
    }


__all__ = [
    "MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION",
    "ModelResolutionSoftwareIdentityError",
    "model_resolution_software_identity",
]
