"""Versioned physical-pool snapshot loader for the 2026-09-19 Drive vintage.

Reads a snapshot directory holding the 19 canonical Drive originals (placed OUTSIDE
the repository, e.g. the extracted source packet), verifies every file SHA-256
against the pinned manifest, and exposes identity / lot / eligibility / context
layers with fail-closed predicates.

Never falls back to stale in-repo August data or ``oracle_subset.json``: any
integrity mismatch raises :class:`SnapshotIntegrityError`. An offline packet is
reported as date-bound, never as live Drive truth.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

SNAPSHOT_DATE = "2026-09-19"
SCHEMA_ROW_MARKER = "schema"

BOX_LOCATIONS = frozenset(
    {"location:alen_box", "location:leon_box", "location:moritz_box"}
)

# Pinned source lock: filename -> sha256 of the 2026-09-19 Drive originals.
PINNED_SOURCE_SHA256: dict[str, str] = {
    "MTG_Kartensammlung_kanonisch_aktuell.xlsx":
        "dabfddfff597402a978d7f6b1e04e8a9cc83e4f593ca5484c6e8902bbd5994ba",
    "CARD_IDENTITY_REGISTRY_CURRENT.jsonl":
        "8d671c933d5132fbbb484db07bc7ca947aed0ab9ef21e2a0bc08173ee2e5a9dc",
    "PHYSICAL_CARD_IDENTITY_CURRENT.jsonl":
        "4dcbdcb877a375ed3bddf2343adb02d366c0412c5328721de1913788d48cec0d",
    "FULL_PHYSICAL_DECKBUILDING_CANDIDATES_CURRENT.jsonl":
        "df0409f6fcccfe401af3f7b9495518fb7289d68c42fd4281dbf2b0de1d21309c",
    "FULL_PHYSICAL_CARD_KNOWLEDGE_BASE_CURRENT.jsonl":
        "ffeabdcf16a0f12eea7c1beffd186bbcb2b3d02b7c2632342170b4de6bcd9a30",
    "FULL_PHYSICAL_CARD_FUNCTIONAL_SEMANTICS_CURRENT.jsonl":
        "8e97fde5c08780fc991dac456c17262d8c45339c169af57db57465831898de6a",
    "TARGET_CARD_IDENTITY_CURRENT.jsonl":
        "34a11d8a29805c4779dc2996fb5ad662260f51dd2afd836ec46b7c299d724a21",
    "TARGET_CARD_SCOPE_CURRENT.jsonl":
        "5267c9a93f96fc8462290b6d9ef1c9bd3e53b0b260434b50d328de7c9ad19caa",
    "TARGET_CARD_AI_CATALOG_CURRENT.jsonl":
        "771870e65e622989229654edb9cb22306cee339558cc3500b89e63626d909989",
    "TARGET_CARD_FUNCTIONAL_SEMANTICS_CURRENT.jsonl":
        "79017bfb2eded87935dd44aef7d259ea34bb9eebdb68155ea1f49fe07cf973e9",
    "ROGSHAI_CARD_CONTEXT_CURRENT.jsonl":
        "8e3b20663eb1357c8cb59b8ad3bf4d130587aded17b16879935d531961d9f8f4",
    "FULL_PHYSICAL_CARD_KNOWLEDGE_QUALITY_REPORT_CURRENT.json":
        "7005bd05f2b8c6e8e91997bc23181ca5fa2a89bd787dcae77227dff233d1bb23",
    "FULL_PHYSICAL_CARD_KNOWLEDGE_MANIFEST_CURRENT.json":
        "cc217e344f94718d8be2b55d9b97ccfedf3e486d6e2b6c17994de7b55f3f4334",
    "FULL_PHYSICAL_CARD_KNOWLEDGE_POINTER_CURRENT.json":
        "ec84bfb277c8a09a51c1b166caf24a42e57bc4deb411890c0318b41e9a9a9a75",
    "PHOTO_IMPORT_CANONICAL_STATUS_2026-09-19.md":
        "8e2154cf570720bfd6a9cf560724f2c6c37da36552b51c50bf4c220e875d9ffd",
    "CARD_KNOWLEDGE_POLICY_CURRENT.md":
        "97b6ac9b706cc94579fda53addfb528a1b68c5fa53547a5d58d3c50639e135cd",
    "TARGET_CARD_AI_README_CURRENT.md":
        "e97d34d8ab4fc21d8481102a6a4a3f2850f7c172e2ce7347b212a7996660a097",
    "MTG_PROJEKTINDEX_AKTUELL.md":
        "805fefc36be39d63a8da675bce836851bf68f332d6d0f98789778a0624151dc5",
    "TARGET_PHYSICAL_CARD_IDENTITY_CURRENT.jsonl":
        "ff9a1397405e07de8339f3f4173e3cdc0d6d813e813342d64a52f19e94817ad3",
}

# Expected raw line counts for JSONL originals (schema/header rows included).
EXPECTED_JSONL_LINES: dict[str, int] = {
    "CARD_IDENTITY_REGISTRY_CURRENT.jsonl": 1413,
    "PHYSICAL_CARD_IDENTITY_CURRENT.jsonl": 1480,
    "FULL_PHYSICAL_DECKBUILDING_CANDIDATES_CURRENT.jsonl": 1398,
    "FULL_PHYSICAL_CARD_KNOWLEDGE_BASE_CURRENT.jsonl": 1402,
    "FULL_PHYSICAL_CARD_FUNCTIONAL_SEMANTICS_CURRENT.jsonl": 1402,
    "TARGET_CARD_IDENTITY_CURRENT.jsonl": 1056,
    "TARGET_CARD_SCOPE_CURRENT.jsonl": 1123,
    "TARGET_CARD_AI_CATALOG_CURRENT.jsonl": 1057,
    "TARGET_CARD_FUNCTIONAL_SEMANTICS_CURRENT.jsonl": 1057,
    "ROGSHAI_CARD_CONTEXT_CURRENT.jsonl": 829,
    "TARGET_PHYSICAL_CARD_IDENTITY_CURRENT.jsonl": 1123,
}

COMMANDER_COLOR_IDENTITY: dict[str, frozenset[str]] = {
    "rogshai": frozenset({"W", "U", "R"}),
    "chulane": frozenset({"W", "U", "G"}),
    "koma": frozenset({"U", "G"}),
    "golgari": frozenset({"B", "G"}),
}


class SnapshotStatus(StrEnum):
    """Freshness classification for a physical-pool snapshot view."""

    CURRENT_VERIFIED_SNAPSHOT = "CURRENT_VERIFIED_SNAPSHOT"
    DATE_BOUND_SNAPSHOT = "DATE_BOUND_SNAPSHOT"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class SnapshotIntegrityError(ValueError):
    """Raised when a snapshot fails closed: missing/mismatched bytes or counts."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise SnapshotIntegrityError(f"non-object JSONL row in {path}")
                rows.append(payload)
    return rows


def data_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop embedded schema/header rows (``record_type == 'schema'``)."""
    return [row for row in rows if row.get("record_type") != SCHEMA_ROW_MARKER]


def is_box_location(location_id: Any) -> bool:
    return location_id in BOX_LOCATIONS


@dataclass(frozen=True)
class SnapshotVerification:
    snapshot_date: str = SNAPSHOT_DATE
    status: SnapshotStatus = SnapshotStatus.DATE_BOUND_SNAPSHOT
    checked_files: int = 0
    # NOTE: an offline packet is date-bound by construction; only a fresh
    # Drive readback could promote this to CURRENT_VERIFIED_SNAPSHOT.
    live_drive_readback: bool = False
    notes: tuple[str, ...] = ()


@dataclass
class PhysicalPoolSnapshot:
    """Verified, read-only view over one pinned snapshot vintage."""

    snapshot_dir: Path
    verification: SnapshotVerification = field(
        default_factory=SnapshotVerification
    )
    _rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict,
                                                  repr=False)

    @property
    def status(self) -> SnapshotStatus:
        return self.verification.status

    def rows(self, filename: str) -> list[dict[str, Any]]:
        try:
            return self._rows[filename]
        except KeyError as exc:
            raise SnapshotIntegrityError(
                f"snapshot layer not loaded: {filename}"
            ) from exc

    def identities(self) -> list[dict[str, Any]]:
        return data_rows(self.rows("CARD_IDENTITY_REGISTRY_CURRENT.jsonl"))

    def lots(self) -> list[dict[str, Any]]:
        return data_rows(self.rows("PHYSICAL_CARD_IDENTITY_CURRENT.jsonl"))

    def candidates(self) -> list[dict[str, Any]]:
        return data_rows(
            self.rows("FULL_PHYSICAL_DECKBUILDING_CANDIDATES_CURRENT.jsonl")
        )

    def physical_identities(self) -> list[dict[str, Any]]:
        """1,401 owned identities: the 12 historical nonphysical rows excluded."""
        return [
            row for row in self.identities()
            if row.get("currently_physically_owned") is not False
        ]

    def unknown_location_lots(self) -> list[dict[str, Any]]:
        return [
            row for row in self.lots()
            if not is_box_location(row.get("location_id"))
        ]

    def box_eligible_quantities(self) -> dict[str, int]:
        """card_id -> available lower-bound copies in the three boxes only.

        Raw ``currently_available_for_own_decks`` flags are NEVER trusted for
        unknown locations: unknown lots contribute exactly zero.
        """
        totals: dict[str, int] = {}
        for row in self.lots():
            if not is_box_location(row.get("location_id")):
                continue
            card_id = row.get("card_id")
            if card_id is None:
                raise SnapshotIntegrityError("lot row without card_id")
            available = row.get("available_for_own_decks_quantity_lower_bound") or 0
            totals[card_id] = totals.get(card_id, 0) + int(available)
        return totals

    def eligible_identity_ids(self) -> set[str]:
        """1,398 distinct Commander-legal identities with box availability."""
        eligible = self.box_eligible_quantities()
        by_id = {row.get("card_id"): row for row in self.identities()}
        return {
            card_id
            for card_id, qty in eligible.items()
            if qty > 0
            and (by_id.get(card_id) or {}).get("currently_physically_owned") is not False
            and (by_id.get(card_id) or {}).get("legality_status") == "legal"
            and (by_id.get(card_id) or {}).get("commander_legal") is True
        }

    def commander_legal_identity_ids(self, commander: str) -> set[str]:
        """Per-commander CI-filtered eligible identities (never the WUR target as pool)."""
        try:
            color_identity = COMMANDER_COLOR_IDENTITY[commander]
        except KeyError as exc:
            raise SnapshotIntegrityError(
                f"unknown commander for CI filter: {commander}"
            ) from exc
        by_id = {row.get("card_id"): row for row in self.identities()}
        return {
            card_id
            for card_id in self.eligible_identity_ids()
            if set((by_id.get(card_id) or {}).get("color_identity") or []) <= color_identity
        }

    def unknown_lot_leak(self, target_rows: list[dict[str, Any]]) -> list[str]:
        """Lot IDs from unknown locations that leaked into a target projection."""
        unknown_lots = {
            row.get("physical_lot_id") for row in self.unknown_location_lots()
        }
        return sorted({
            str(row.get("physical_lot_id"))
            for row in data_rows(target_rows)
            if row.get("physical_lot_id") in unknown_lots
        })


def load_snapshot(snapshot_dir: str | Path) -> PhysicalPoolSnapshot:
    """Verify and load a pinned snapshot vintage; fail closed on any mismatch."""
    root = Path(snapshot_dir)
    if not root.is_dir():
        raise SnapshotIntegrityError(f"snapshot directory missing: {root}")
    loaded: dict[str, list[dict[str, Any]]] = {}
    for filename, expected_sha in sorted(PINNED_SOURCE_SHA256.items()):
        path = root / filename
        if not path.is_file():
            raise SnapshotIntegrityError(f"snapshot file missing: {filename}")
        observed = sha256_file(path)
        if observed != expected_sha:
            raise SnapshotIntegrityError(
                f"snapshot hash mismatch for {filename}: "
                f"expected {expected_sha[:16]}…, observed {observed[:16]}…"
            )
        if filename.endswith(".jsonl"):
            rows = read_jsonl_rows(path)
            expected_lines = EXPECTED_JSONL_LINES.get(filename)
            if expected_lines is not None and len(rows) != expected_lines:
                raise SnapshotIntegrityError(
                    f"snapshot line-count mismatch for {filename}: "
                    f"expected {expected_lines}, observed {len(rows)}"
                )
            loaded[filename] = rows
    snapshot = PhysicalPoolSnapshot(snapshot_dir=root)
    snapshot._rows = loaded
    # Cross-layer invariant: every candidate identity must be box-eligible.
    candidate_ids = {
        row.get("card_id") for row in data_rows(
            loaded["FULL_PHYSICAL_DECKBUILDING_CANDIDATES_CURRENT.jsonl"]
        )
    }
    if not candidate_ids <= snapshot.eligible_identity_ids():
        raise SnapshotIntegrityError(
            "candidate identities are not a subset of box-eligible identities"
        )
    return snapshot
