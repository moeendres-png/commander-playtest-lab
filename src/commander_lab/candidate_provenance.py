from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from commander_lab.models.common import FrozenModel
from commander_lab.storage import sha256_value

CANDIDATE_PROVENANCE_SCHEMA_VERSION = "1.0.0"


class OperationalBaselineStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class CandidatePoolIdentity(FrozenModel):
    schema_version: str = CANDIDATE_PROVENANCE_SCHEMA_VERSION
    candidate_pool_id: str
    candidate_pool_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    deck_id: str
    operational_baseline_status: OperationalBaselineStatus
    baseline_deck_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    inventory_source_id: str
    inventory_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    allocation_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligibility_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def baseline_matches_status(self) -> CandidatePoolIdentity:
        if self.operational_baseline_status is OperationalBaselineStatus.RESOLVED:
            if self.baseline_deck_hash is None:
                raise ValueError("resolved candidate pool requires baseline_deck_hash")
        elif self.baseline_deck_hash is not None:
            raise ValueError("unresolved candidate pool must not invent baseline_deck_hash")
        return self


class CandidateProvenance(FrozenModel):
    schema_version: str = CANDIDATE_PROVENANCE_SCHEMA_VERSION
    candidate_id: str
    candidate_provenance_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    deck_id: str
    oracle_name: str
    candidate_pool_id: str
    candidate_pool_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    inventory_source_id: str
    inventory_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    allocation_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligibility_reason: str
    physical_available_quantity: int = Field(ge=0)
    physical_copy_ids: tuple[str, ...] = ()
    aggregation_mode: str = "oracle_name_quantity_projection"


class VariantProvenance(FrozenModel):
    schema_version: str = CANDIDATE_PROVENANCE_SCHEMA_VERSION
    variant_id: str
    variant_provenance_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    deck_id: str
    baseline_deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_pool_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_ids: tuple[str, ...]
    swaps: tuple[tuple[str, str], ...]
    package_ids: tuple[str, ...] = ()


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"candidate provenance source is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"candidate provenance source is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"candidate provenance source must be an object: {path}")
    return payload


def build_candidate_pool_identity(root: str | Path, deck_id: str) -> CandidatePoolIdentity:
    """Build a deterministic identity for one deck's current candidate pool.

    This is additive evidence only: it never reserves a card or mutates inventory. If a globally
    active deck has no resolved current operational baseline, the pool remains explicitly
    UNRESOLVED and carries no fabricated deck hash.
    """

    root_path = Path(root).resolve()
    scope_path = root_path / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json"
    manifest_path = root_path / "data/decks/manifest.json"
    source_registry_path = root_path / "data/sync/current_sources.json"
    inventory_path = root_path / "data/canonical_import/2026-08-07/inventory_snapshot.json"
    allocation_path = root_path / "data/collections/current_deck_allocations.json"
    eligibility_path = root_path / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"

    scope = _load_json(scope_path)
    global_active = {str(value) for value in scope.get("global_active_own_decks", [])}
    if deck_id not in global_active:
        raise ValueError(f"candidate pool deck is not a globally active own deck: {deck_id}")
    unresolved = {str(value) for value in scope.get("unresolved_operational_baselines", [])}

    manifest = _load_json(manifest_path)
    decks = manifest.get("decks", {})
    if not isinstance(decks, dict):
        raise ValueError("deck manifest has no deck mapping")
    baseline_hash: str | None = None
    status = OperationalBaselineStatus.UNRESOLVED
    if deck_id not in unresolved:
        raw = decks.get(deck_id)
        if not isinstance(raw, dict):
            raise ValueError(f"resolved candidate pool deck is missing from manifest: {deck_id}")
        raw_hash = raw.get("deck_hash")
        if not isinstance(raw_hash, str) or len(raw_hash) != 64:
            raise ValueError(f"resolved candidate pool deck has invalid hash: {deck_id}")
        baseline_hash = raw_hash
        status = OperationalBaselineStatus.RESOLVED

    source_registry = _load_json(source_registry_path)
    inventory_spec = source_registry.get("sources", {}).get("inventory", {})
    inventory_source_id = inventory_spec.get("drive_file_id") if isinstance(inventory_spec, dict) else None
    if not isinstance(inventory_source_id, str) or not inventory_source_id:
        raise ValueError("candidate pool inventory source id is missing")

    eligibility = _load_json(eligibility_path)
    eligible_by_deck = eligibility.get("eligible_by_deck", {})
    if not isinstance(eligible_by_deck, dict):
        raise ValueError("candidate eligibility snapshot has no deck mapping")
    deck_rows = eligible_by_deck.get(deck_id)
    if not isinstance(deck_rows, dict):
        raise ValueError(f"candidate eligibility snapshot has no rows for {deck_id}")

    inventory_hash = _sha256_file(inventory_path)
    allocation_hash = _sha256_file(allocation_path)
    eligibility_hash = _sha256_file(eligibility_path)
    semantic_payload = {
        "deck_id": deck_id,
        "operational_baseline_status": status.value,
        "baseline_deck_hash": baseline_hash,
        "inventory_source_id": inventory_source_id,
        "inventory_snapshot_hash": inventory_hash,
        "allocation_snapshot_hash": allocation_hash,
        "eligibility_snapshot_hash": eligibility_hash,
        "eligible_rows": deck_rows,
    }
    pool_hash = sha256_value(semantic_payload)
    return CandidatePoolIdentity(
        candidate_pool_id=f"candidate-pool:{deck_id}:{pool_hash[:16]}",
        candidate_pool_hash=pool_hash,
        deck_id=deck_id,
        operational_baseline_status=status,
        baseline_deck_hash=baseline_hash,
        inventory_source_id=inventory_source_id,
        inventory_snapshot_hash=inventory_hash,
        allocation_snapshot_hash=allocation_hash,
        eligibility_snapshot_hash=eligibility_hash,
    )


def build_candidate_provenance(
    root: str | Path,
    *,
    deck_id: str,
    candidate_id: str,
    oracle_name: str,
) -> CandidateProvenance:
    root_path = Path(root).resolve()
    pool = build_candidate_pool_identity(root_path, deck_id)
    eligibility = _load_json(
        root_path / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
    )
    rows = eligibility.get("eligible_by_deck", {}).get(deck_id, {})
    row = rows.get(oracle_name) if isinstance(rows, dict) else None
    if not isinstance(row, dict):
        raise ValueError(f"candidate is not present in current deck eligibility: {deck_id}: {oracle_name}")
    if row.get("commander_legal") is not True:
        raise ValueError(f"candidate is not Commander-legal for {deck_id}: {oracle_name}")
    quantity = int(row.get("physical_available_quantity", 0))
    if quantity <= 0:
        raise ValueError(f"candidate has no physical availability for {deck_id}: {oracle_name}")

    semantic_payload = {
        "candidate_id": candidate_id,
        "deck_id": deck_id,
        "oracle_name": oracle_name,
        "candidate_pool_hash": pool.candidate_pool_hash,
        "inventory_source_id": pool.inventory_source_id,
        "inventory_snapshot_hash": pool.inventory_snapshot_hash,
        "allocation_snapshot_hash": pool.allocation_snapshot_hash,
        "eligibility_reason": "current_deck_scoped_physical_commander_legal_projection",
        "physical_available_quantity": quantity,
        "physical_copy_ids": [],
        "aggregation_mode": "oracle_name_quantity_projection",
    }
    provenance_hash = sha256_value(semantic_payload)
    return CandidateProvenance(
        candidate_id=candidate_id,
        candidate_provenance_hash=provenance_hash,
        deck_id=deck_id,
        oracle_name=oracle_name,
        candidate_pool_id=pool.candidate_pool_id,
        candidate_pool_hash=pool.candidate_pool_hash,
        inventory_source_id=pool.inventory_source_id,
        inventory_snapshot_hash=pool.inventory_snapshot_hash,
        allocation_snapshot_hash=pool.allocation_snapshot_hash,
        eligibility_reason="current_deck_scoped_physical_commander_legal_projection",
        physical_available_quantity=quantity,
    )


def build_variant_provenance(
    *,
    variant_id: str,
    deck_id: str,
    baseline_deck_hash: str,
    candidate_deck_hash: str,
    candidate_pool_hash: str,
    candidate_ids: tuple[str, ...],
    swaps: tuple[tuple[str, str], ...],
    package_ids: tuple[str, ...] = (),
) -> VariantProvenance:
    payload = {
        "variant_id": variant_id,
        "deck_id": deck_id,
        "baseline_deck_hash": baseline_deck_hash,
        "candidate_deck_hash": candidate_deck_hash,
        "candidate_pool_hash": candidate_pool_hash,
        "candidate_ids": list(candidate_ids),
        "swaps": [list(swap) for swap in swaps],
        "package_ids": list(package_ids),
    }
    return VariantProvenance(
        variant_id=variant_id,
        variant_provenance_hash=sha256_value(payload),
        deck_id=deck_id,
        baseline_deck_hash=baseline_deck_hash,
        candidate_deck_hash=candidate_deck_hash,
        candidate_pool_hash=candidate_pool_hash,
        candidate_ids=candidate_ids,
        swaps=swaps,
        package_ids=package_ids,
    )
