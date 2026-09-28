"""Effective v1.0.6 materialization for the current qualification boundary.

Reuses the canonical resolver (``scripts/resolve_pre_freeze_contract.py``)
rather than re-implementing the overlay, so the effective records and their
digests are produced by exactly one code path.

REUSE_AS_IS: the successor overlay algorithm, the projection-key digest spec,
and the denominator are owned by the current contract resolver.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from .source_lock import (
    CURRENT_QUALIFICATION_BOUNDARY,
    FULL107_FROZEN_SOURCE,
    repo_root,
)

RESOLVER_RELATIVE_PATH = "scripts/resolve_pre_freeze_contract.py"


@lru_cache(maxsize=1)
def _resolver(root: str) -> ModuleType:
    """Load the canonical pre-Freeze contract resolver as a module."""
    path = Path(root) / RESOLVER_RELATIVE_PATH
    spec = importlib.util.spec_from_file_location("resolve_pre_freeze_contract", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load canonical contract resolver at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class EffectiveMaterialization:
    """The effective current materialization plus the 107-row denominator."""

    bundle: dict[str, Any]
    denominator: list[str]
    canonical_bundle_digest: str

    def record(self, fixture_id: str) -> dict[str, Any]:
        for item in self.bundle["records"]:
            if item["fixture_id"] == fixture_id:
                assert isinstance(item, dict)
                return item
        raise KeyError(f"fixture not in effective materialization: {fixture_id}")

    def records(self) -> list[dict[str, Any]]:
        return list(self.bundle["records"])

    def denominator_records(self) -> list[dict[str, Any]]:
        by_id = {item["fixture_id"]: item for item in self.bundle["records"]}
        missing = [fid for fid in self.denominator if fid not in by_id]
        if missing:
            raise RuntimeError(f"denominator rows absent from materialization: {missing}")
        return [by_id[fid] for fid in self.denominator]

    def receipt(self) -> dict[str, Any]:
        return {
            "schema_version": self.bundle["schema_version"],
            "contract_id": self.bundle.get("contract_id"),
            "qualification_boundary": CURRENT_QUALIFICATION_BOUNDARY,
            "frozen_full107_source": FULL107_FROZEN_SOURCE,
            "canonical_bundle_digest": self.canonical_bundle_digest,
            "materialization_record_count": self.bundle["record_count"],
            "provider_denominator_count": len(self.denominator),
            "changed_fixture_ids": self.bundle.get("evidence_migration", {}).get(
                "changed_fixture_ids", ["WS05-CMD-START-2"]
            ),
            "rules_authority": self.bundle.get("current_rules_authority"),
        }


def load_effective_materialization(root: Path | None = None) -> EffectiveMaterialization:
    """Load and validate the effective v1.0.6 materialization and denominator."""
    resolved_root = root or repo_root()
    module = _resolver(str(resolved_root))
    bundle = module.load_effective_materialization()
    denominator_doc = module._load(
        resolved_root / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json"
    )
    denominator = list(denominator_doc["fixture_ids"])
    if len(denominator) != 107:
        raise RuntimeError(f"provider denominator must be 107 rows, got {len(denominator)}")
    if denominator_doc.get("denominator_decreased_to_bypass_blocker") is not False:
        raise RuntimeError("provider denominator was decreased to bypass a blocker")
    return EffectiveMaterialization(
        bundle=bundle,
        denominator=denominator,
        canonical_bundle_digest=bundle["canonical_bundle_digest"],
    )
