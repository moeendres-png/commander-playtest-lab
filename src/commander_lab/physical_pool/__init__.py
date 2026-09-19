"""Versioned physical-pool snapshot access (2026-09-19 vintage)."""

from commander_lab.physical_pool.coverage import (
    CardSourceCoverage,
    CoverageMatrix,
    build_source_matrix,
)
from commander_lab.physical_pool.snapshot import (
    BOX_LOCATIONS,
    COMMANDER_COLOR_IDENTITY,
    EXPECTED_JSONL_LINES,
    PINNED_SOURCE_SHA256,
    SNAPSHOT_DATE,
    PhysicalPoolSnapshot,
    SnapshotIntegrityError,
    SnapshotStatus,
    SnapshotVerification,
    data_rows,
    load_snapshot,
)

__all__ = [
    "BOX_LOCATIONS",
    "COMMANDER_COLOR_IDENTITY",
    "EXPECTED_JSONL_LINES",
    "PINNED_SOURCE_SHA256",
    "SNAPSHOT_DATE",
    "CardSourceCoverage",
    "CoverageMatrix",
    "PhysicalPoolSnapshot",
    "SnapshotIntegrityError",
    "SnapshotStatus",
    "SnapshotVerification",
    "build_source_matrix",
    "data_rows",
    "load_snapshot",
]
