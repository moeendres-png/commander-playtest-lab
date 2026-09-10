"""Reproducible campaign manifests.

A manifest binds an ordered set of routed scaffolding records (intake IDs,
states, content hashes) plus queue summaries under a single manifest hash.
Same corpus pin + input set + tool version + configuration (+ seed, if
sampling is used) reproduces identical intake IDs, tags, skeleton
identities, queue assignments, ordering, and hashes.

Manifests carry preparation status only: no behavior results, no coverage,
no credit. :func:`verify_manifest` fails closed on any tampering or drift.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from . import Q6_SCAFFOLDING_VERSION, SCHEMA_MANIFEST_V1
from .gate import validate_output


@dataclass
class CampaignManifest:
    """One reproducible campaign snapshot."""

    manifest_id: str
    schema: str = SCHEMA_MANIFEST_V1
    tool_version: str = Q6_SCAFFOLDING_VERSION
    source_locks: list = field(default_factory=list)
    configuration: dict = field(default_factory=dict)
    records: list = field(default_factory=list)
    queue_summary: dict = field(default_factory=dict)
    manifest_hash: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_manifest(
    routed: list[dict],
    queues: dict[str, list[dict]],
    *,
    configuration: dict | None = None,
    manifest_id: str = "q6-campaign",
) -> CampaignManifest:
    """Build a deterministic manifest from routed records and queues."""
    config = dict(configuration or {})
    ordered = sorted(routed, key=lambda r: r["intake_id"])
    record_entries = [
        {
            "intake_id": r["intake_id"],
            "card_name_hint": r.get("card_name_hint", ""),
            "state": r["state"],
            "reasons": sorted(set(r.get("reasons", []))),
            "capability": r.get("capability", "UNCLUSTERED"),
            "capability_families": sorted(r.get("capability_families", [])),
            "skeleton_id": r.get("skeleton_id", ""),
            "input_hash": r.get("input_hash", ""),
            "source_commit": r.get("source_commit", ""),
            "source_path": r.get("source_path", ""),
        }
        for r in ordered
    ]
    locks = sorted(
        {
            (
                r.get("source_corpus", ""),
                r.get("source_repository", ""),
                r.get("source_commit", ""),
            )
            for r in ordered
        }
    )
    queue_counts = {name: len(items) for name, items in sorted(queues.items())}
    body = {
        "manifest_id": manifest_id,
        "schema": SCHEMA_MANIFEST_V1,
        "tool_version": Q6_SCAFFOLDING_VERSION,
        "source_locks": [
            {"source_corpus": c, "source_repository": r, "source_commit": s} for c, r, s in locks
        ],
        "configuration": config,
        "records": record_entries,
        "queue_summary": queue_counts,
    }
    manifest_hash = hashlib.sha256(_canonical(body)).hexdigest()
    manifest = CampaignManifest(
        manifest_id=manifest_id,
        tool_version=Q6_SCAFFOLDING_VERSION,
        source_locks=body["source_locks"],
        configuration=config,
        records=record_entries,
        queue_summary=queue_counts,
        manifest_hash=manifest_hash,
    )
    validate_output(manifest.as_dict(), artifact="campaign-manifest")
    return manifest


def verify_manifest(manifest: dict) -> None:
    """Recompute and compare the manifest hash; fail closed on mismatch."""
    stored = manifest.get("manifest_hash", "")
    body = {
        "manifest_id": manifest.get("manifest_id"),
        "schema": manifest.get("schema"),
        "tool_version": manifest.get("tool_version"),
        "source_locks": manifest.get("source_locks"),
        "configuration": manifest.get("configuration"),
        "records": manifest.get("records"),
        "queue_summary": manifest.get("queue_summary"),
    }
    recomputed = hashlib.sha256(_canonical(body)).hexdigest()
    if recomputed != stored:
        raise ValueError(
            f"manifest hash mismatch: stored {stored} != recomputed {recomputed} "
            "(manifest fails closed; regenerate from the pinned inputs)"
        )
    if manifest.get("schema") != SCHEMA_MANIFEST_V1:
        raise ValueError(
            f"unknown manifest schema: {manifest.get('schema')} (expected {SCHEMA_MANIFEST_V1})"
        )
