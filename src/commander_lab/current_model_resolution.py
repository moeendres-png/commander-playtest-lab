from __future__ import annotations

import json
import string
from pathlib import Path
from typing import Any

from commander_lab.model_resolution_software_identity import (
    ModelResolutionSoftwareIdentityError,
    model_resolution_software_identity,
)
from commander_lab.whole_deck.lab_context import enriched_context
from commander_lab.whole_deck.orchestrator import WholeDeckCampaignOrchestrator
from commander_lab.whole_deck.search_context import current_control_mainboard


class CurrentModelResolutionError(ValueError):
    """Raised when stored model-resolution evidence is absent, malformed, or stale."""


CURRENT_MODEL_RESOLUTION_PATH = Path("data/diagnostics/MODEL_RESOLUTION_CURRENT.json")


def _require_hex_digest(payload: dict[str, Any], key: str, *, length: int) -> str:
    value = payload.get(key)
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in string.hexdigits for character in value)
    ):
        raise CurrentModelResolutionError(
            f"current model resolution has invalid {key}; expected {length} hexadecimal characters"
        )
    return value.lower()


def _validated_stored_software_identity(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("software_identity")
    if not isinstance(raw, dict):
        raise CurrentModelResolutionError(
            "current model resolution has no content-addressed software identity"
        )
    if raw.get("schema_version") != "1.1.0":
        raise CurrentModelResolutionError(
            "current model resolution has an unsupported software identity schema"
        )
    source_objects = raw.get("source_objects")
    scope_paths = raw.get("scope_paths")
    if not isinstance(source_objects, dict) or not source_objects:
        raise CurrentModelResolutionError(
            "current model resolution has no auditable resolution-source manifest"
        )
    if not isinstance(scope_paths, list) or not scope_paths:
        raise CurrentModelResolutionError(
            "current model resolution has no auditable resolution-source scope"
        )
    normalized_objects: dict[str, str] = {}
    for path, digest in source_objects.items():
        if not isinstance(path, str) or not path:
            raise CurrentModelResolutionError("current model resolution has invalid source path")
        normalized_objects[path] = _require_hex_digest({"digest": digest}, "digest", length=40)
    normalized_scope = [str(path) for path in scope_paths]
    if sorted(normalized_scope) != sorted(normalized_objects):
        raise CurrentModelResolutionError(
            "current model resolution software scope and source manifest disagree"
        )
    identity = {
        **raw,
        "resolution_source_manifest_sha256": _require_hex_digest(
            raw, "resolution_source_manifest_sha256", length=64
        ),
        "measurement_entrypoint_blob_sha1": _require_hex_digest(
            raw, "measurement_entrypoint_blob_sha1", length=40
        ),
        "package_manifest_blob_sha1": _require_hex_digest(
            raw, "package_manifest_blob_sha1", length=40
        ),
        "identity_sha256": _require_hex_digest(raw, "identity_sha256", length=64),
        "source_objects": normalized_objects,
        "scope_paths": normalized_scope,
    }
    return identity


def load_current_model_resolution(root: str | Path) -> dict[str, Any]:
    """Load and live-validate the current Structural resolution contract.

    Freshness is defined by the same Whole-Deck control materialization, data snapshot, opponent
    registry, and content-addressed Structural-measurement software inputs used by the measurement
    protocol. A mismatch fails closed rather than silently falling back to a zero or historical
    resolution threshold. Unrelated external-engine code is intentionally outside that identity.
    """

    project = Path(root).resolve()
    path = project / CURRENT_MODEL_RESOLUTION_PATH
    if not path.is_file():
        raise CurrentModelResolutionError(f"current model-resolution file is missing: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CurrentModelResolutionError(f"invalid current model-resolution JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise CurrentModelResolutionError("current model-resolution payload must be an object")
    payload: dict[str, Any] = raw

    if payload.get("status") != "MEASURED":
        raise CurrentModelResolutionError("current model resolution is not measured")
    if payload.get("metric") != "placement_improvement":
        raise CurrentModelResolutionError("current model resolution uses an unexpected metric")
    if payload.get("evidence_class") != "structural_model_estimates":
        raise CurrentModelResolutionError("current model resolution lost its evidence boundary")
    resolution = payload.get("effective_resolution")
    if isinstance(resolution, bool) or not isinstance(resolution, int | float) or resolution <= 0:
        raise CurrentModelResolutionError("current model resolution has no positive threshold")
    decision_use = payload.get("decision_use")
    if (
        not isinstance(decision_use, dict)
        or decision_use.get("paired_candidate_comparisons_allowed") is not True
    ):
        raise CurrentModelResolutionError(
            "current resolution does not authorize paired candidate comparisons"
        )

    stored_control_hash = _require_hex_digest(
        payload,
        "structural_control_deck_hash",
        length=64,
    )
    stored_snapshot_hash = _require_hex_digest(payload, "data_snapshot_hash", length=64)
    stored_opponent_hash = _require_hex_digest(payload, "opponent_registry_hash", length=64)
    stored_software_identity = _validated_stored_software_identity(payload)

    context, _, _ = enriched_context(project)
    control = context.materialize(
        current_control_mainboard(project),
        label="model-resolution-current-control",
    )
    orchestrator = WholeDeckCampaignOrchestrator(project)
    try:
        current_software_identity = model_resolution_software_identity(project)
    except ModelResolutionSoftwareIdentityError as exc:
        raise CurrentModelResolutionError(
            "current model-resolution software freshness cannot be proven"
        ) from exc

    current = {
        "structural_control_deck_hash": control.deck_hash,
        "data_snapshot_hash": control.data_snapshot_hash,
        "opponent_registry_hash": orchestrator.opponents.registry_hash,
    }
    stored = {
        "structural_control_deck_hash": stored_control_hash,
        "data_snapshot_hash": stored_snapshot_hash,
        "opponent_registry_hash": stored_opponent_hash,
    }
    mismatches = {
        key: {"stored": stored[key], "current": current[key]}
        for key in stored
        if stored[key] != current[key]
    }
    if mismatches:
        raise CurrentModelResolutionError(
            "current model-resolution evidence is stale for the live decision inputs: "
            + json.dumps(mismatches, sort_keys=True)
        )

    software_keys = (
        "identity_version",
        "resolution_source_manifest_sha256",
        "measurement_entrypoint_blob_sha1",
        "package_manifest_blob_sha1",
        "identity_sha256",
    )
    software_mismatches = {
        key: {
            "stored": stored_software_identity.get(key),
            "current": current_software_identity.get(key),
        }
        for key in software_keys
        if stored_software_identity.get(key) != current_software_identity.get(key)
    }
    if stored_software_identity.get("scope_paths") != current_software_identity.get("scope_paths"):
        software_mismatches["scope_paths"] = {
            "stored": stored_software_identity.get("scope_paths"),
            "current": current_software_identity.get("scope_paths"),
        }
    if stored_software_identity.get("source_objects") != current_software_identity.get(
        "source_objects"
    ):
        software_mismatches["source_objects"] = {
            "stored_manifest": stored_software_identity.get("resolution_source_manifest_sha256"),
            "current_manifest": current_software_identity.get("resolution_source_manifest_sha256"),
        }
    if software_mismatches:
        raise CurrentModelResolutionError(
            "current model-resolution evidence is stale for the live software identity: "
            + json.dumps(software_mismatches, sort_keys=True)
        )

    artifact = payload.get("measurement_artifact")
    if not isinstance(artifact, dict):
        raise CurrentModelResolutionError("current model resolution has no measurement provenance")
    source_head = _require_hex_digest(artifact, "source_head", length=40)
    measurement_json_sha256 = _require_hex_digest(
        artifact,
        "measurement_json_sha256",
        length=64,
    )
    report_hash = _require_hex_digest(artifact, "report_hash", length=64)

    return {
        **payload,
        "software_identity": stored_software_identity,
        "measurement_artifact": {
            **artifact,
            "source_head": source_head,
            "measurement_json_sha256": measurement_json_sha256,
            "report_hash": report_hash,
        },
        "freshness_validated": True,
        "freshness_inputs": {
            **current,
            "software_identity": current_software_identity,
        },
        "truth_boundary": (
            str(payload.get("truth_boundary", ""))
            + " Freshness validation does not convert Structural evidence into empirical "
            "gameplay evidence."
        ).strip(),
    }


__all__ = [
    "CURRENT_MODEL_RESOLUTION_PATH",
    "CurrentModelResolutionError",
    "load_current_model_resolution",
]
