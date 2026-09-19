"""Unit tests for the versioned 2026-09-19 physical-pool snapshot loader.

Synthetic fixtures only: no packet bytes, no inventory data, and no stale
August sources are embedded here. A live-snapshot integration test lives in
``tests/integration/test_physical_pool_snapshot_live.py`` and runs only with
``COMMANDER_LAB_SNAPSHOT_DIR`` pointed at a verified out-of-repo snapshot.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from commander_lab.physical_pool.snapshot import (
    EXPECTED_JSONL_LINES,
    PINNED_SOURCE_SHA256,
    SNAPSHOT_DATE,
    SnapshotIntegrityError,
    SnapshotStatus,
    load_snapshot,
)


def _identity(card_id: str, **overrides: object) -> dict:
    row: dict = {
        "card_id": card_id,
        "oracle_name": card_id,
        "currently_physically_owned": True,
        "legality_status": "legal",
        "commander_legal": True,
        "color_identity": ["W"],
    }
    row.update(overrides)
    return row


def _lot(lot_id: str, card_id: str, location: str, available_lb: int) -> dict:
    return {
        "physical_lot_id": lot_id,
        "card_id": card_id,
        "location_id": location,
        "available_for_own_decks_quantity_lower_bound": available_lb,
        "quantity_lower_bound": available_lb,
    }


def _write_snapshot(root: Path, *, identities: list, lots: list,
                    candidates: list) -> Path:
    """Materialize a minimal snapshot dir; untouched files get byte-exact dummies.

    Dummy filler bytes cannot satisfy the pinned SHA gate, so tests that need
    full verification must override every pinned file (see live test).
    """
    root.mkdir(parents=True, exist_ok=True)
    layers = {
        "CARD_IDENTITY_REGISTRY_CURRENT.jsonl": identities,
        "PHYSICAL_CARD_IDENTITY_CURRENT.jsonl": lots,
        "FULL_PHYSICAL_DECKBUILDING_CANDIDATES_CURRENT.jsonl": candidates,
    }
    for filename in PINNED_SOURCE_SHA256:
        path = root / filename
        if filename in layers:
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in layers[filename]),
                encoding="utf-8",
            )
        else:
            path.write_bytes(b"")
    return root


def test_pinned_source_lock_matches_contract_shape() -> None:
    assert SNAPSHOT_DATE == "2026-09-19"
    assert len(PINNED_SOURCE_SHA256) == 19
    assert all(len(digest) == 64 for digest in PINNED_SOURCE_SHA256.values())
    assert EXPECTED_JSONL_LINES["CARD_IDENTITY_REGISTRY_CURRENT.jsonl"] == 1413
    assert EXPECTED_JSONL_LINES["PHYSICAL_CARD_IDENTITY_CURRENT.jsonl"] == 1480
    assert EXPECTED_JSONL_LINES["FULL_PHYSICAL_DECKBUILDING_CANDIDATES_CURRENT.jsonl"] == 1398


def test_missing_snapshot_dir_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(SnapshotIntegrityError, match="directory missing"):
        load_snapshot(tmp_path / "does-not-exist")


def test_tampered_bytes_fail_closed(tmp_path: Path) -> None:
    snap = _write_snapshot(
        tmp_path / "snap",
        identities=[_identity("card:a")],
        lots=[_lot("lot:1", "card:a", "location:leon_box", 1)],
        candidates=[{"card_id": "card:a"}],
    )
    tampered = snap / "PHYSICAL_CARD_IDENTITY_CURRENT.jsonl"
    with tampered.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_lot("lot:evil", "card:a", "location:unknown", 99)) + "\n")
    with pytest.raises(SnapshotIntegrityError, match=r"hash mismatch|line-count mismatch"):
        load_snapshot(snap)


def test_unknown_location_lots_contribute_zero_and_leak_detector_flags_them() -> None:
    from commander_lab.physical_pool.snapshot import PhysicalPoolSnapshot

    snapshot = PhysicalPoolSnapshot(snapshot_dir=Path("/nonexistent"))
    snapshot._rows = {
        "CARD_IDENTITY_REGISTRY_CURRENT.jsonl": [
            _identity("card:plains"),
            _identity("card:vernal-fen"),
        ],
        "PHYSICAL_CARD_IDENTITY_CURRENT.jsonl": [
            _lot("lot:box", "card:plains", "location:leon_box", 3),
            # Misleading raw flag on an unknown lot: must still count zero.
            {
                "physical_lot_id": "lot:unknown",
                "card_id": "card:plains",
                "location_id": "location:unknown",
                "available_for_own_decks_quantity_lower_bound": 47,
                "currently_available_for_own_decks": True,
                "quantity_lower_bound": 47,
            },
            _lot("lot:reserved", "card:vernal-fen", "location:unknown", 0),
        ],
        "FULL_PHYSICAL_DECKBUILDING_CANDIDATES_CURRENT.jsonl": [
            {"card_id": "card:plains"}
        ],
    }
    assert snapshot.box_eligible_quantities() == {"card:plains": 3}
    assert [row["physical_lot_id"] for row in snapshot.unknown_location_lots()] == [
        "lot:unknown", "lot:reserved",
    ]
    leaked = snapshot.unknown_lot_leak([
        {"physical_lot_id": "lot:box", "card_id": "card:plains"},
        {"physical_lot_id": "lot:unknown", "card_id": "card:plains"},
    ])
    assert leaked == ["lot:unknown"]


def test_eligibility_requires_box_availability_legality_and_commander_legality() -> None:
    from commander_lab.physical_pool.snapshot import PhysicalPoolSnapshot

    snapshot = PhysicalPoolSnapshot(snapshot_dir=Path("/nonexistent"))
    snapshot._rows = {
        "CARD_IDENTITY_REGISTRY_CURRENT.jsonl": [
            _identity("card:ok", color_identity=["W", "U", "R"]),
            _identity("card:banned", legality_status="banned", commander_legal=False),
            _identity("card:offcolor", color_identity=["B", "G"]),
            _identity("card:nonphysical", currently_physically_owned=False),
        ],
        "PHYSICAL_CARD_IDENTITY_CURRENT.jsonl": [
            _lot("lot:1", "card:ok", "location:leon_box", 1),
            _lot("lot:2", "card:banned", "location:leon_box", 1),
            _lot("lot:3", "card:offcolor", "location:moritz_box", 2),
            _lot("lot:4", "card:nonphysical", "location:alen_box", 1),
            _lot("lot:5", "card:reserved-out", "location:alen_box", 0),
        ],
        "FULL_PHYSICAL_DECKBUILDING_CANDIDATES_CURRENT.jsonl": [],
    }
    by_id = {row["card_id"]: row for row in snapshot.identities()}
    by_id["card:reserved-out"] = _identity("card:reserved-out")
    snapshot._rows["CARD_IDENTITY_REGISTRY_CURRENT.jsonl"].append(
        by_id["card:reserved-out"]
    )
    assert snapshot.eligible_identity_ids() == {"card:ok", "card:offcolor"}
    assert snapshot.commander_legal_identity_ids("rogshai") == {"card:ok"}
    assert snapshot.commander_legal_identity_ids("golgari") == {"card:offcolor"}
    with pytest.raises(SnapshotIntegrityError, match="unknown commander"):
        snapshot.commander_legal_identity_ids("urza")


def test_schema_header_rows_are_tolerated_not_counted() -> None:
    from commander_lab.physical_pool.snapshot import data_rows

    rows = [
        {"record_type": "schema", "record_count": 828},
        {"card_id": "card:a"},
    ]
    assert data_rows(rows) == [{"card_id": "card:a"}]


def test_snapshot_status_defaults_to_date_bound_not_live() -> None:
    from commander_lab.physical_pool.snapshot import SnapshotVerification

    verification = SnapshotVerification(checked_files=19)
    assert verification.status == SnapshotStatus.DATE_BOUND_SNAPSHOT
    assert verification.live_drive_readback is False


def test_sha256_helper_is_stable(tmp_path: Path) -> None:
    from commander_lab.physical_pool.snapshot import sha256_file

    path = tmp_path / "probe.bin"
    path.write_bytes(b"commander-lab")
    assert sha256_file(path) == hashlib.sha256(b"commander-lab").hexdigest()
