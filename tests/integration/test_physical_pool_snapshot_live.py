"""Live verification of the pinned 2026-09-19 snapshot (opt-in, env-gated).

Runs ONLY when ``COMMANDER_LAB_SNAPSHOT_DIR`` points at an out-of-repo directory
holding the 19 canonical originals. Never commits snapshot bytes; asserts the
full verified counts, the eligibility derivation, and the known TARGET leakage.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from commander_lab.physical_pool.snapshot import SnapshotStatus, load_snapshot

SNAPSHOT_DIR = os.environ.get("COMMANDER_LAB_SNAPSHOT_DIR", "")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def snapshot():
    if not SNAPSHOT_DIR:
        pytest.skip("COMMANDER_LAB_SNAPSHOT_DIR not set")
    return load_snapshot(Path(SNAPSHOT_DIR))


def test_live_snapshot_is_date_bound_verified(snapshot) -> None:
    assert snapshot.status == SnapshotStatus.DATE_BOUND_SNAPSHOT
    assert len(snapshot.identities()) == 1413
    assert len(snapshot.lots()) == 1480
    assert len(snapshot.candidates()) == 1398
    assert len(snapshot.physical_identities()) == 1401


def test_live_eligibility_derivation(snapshot) -> None:
    assert len(snapshot.unknown_location_lots()) == 6
    assert len(snapshot.eligible_identity_ids()) == 1398
    assert len(snapshot.commander_legal_identity_ids("rogshai")) == 828
    assert len(snapshot.commander_legal_identity_ids("chulane")) == 791
    assert len(snapshot.commander_legal_identity_ids("koma")) == 556
    assert len(snapshot.commander_legal_identity_ids("golgari")) == 535


def test_live_target_leakage_is_detected(snapshot) -> None:
    scope = snapshot.rows("TARGET_CARD_SCOPE_CURRENT.jsonl")
    physical = snapshot.rows("TARGET_PHYSICAL_CARD_IDENTITY_CURRENT.jsonl")
    assert len(snapshot.unknown_lot_leak(scope)) == 4
    assert len(snapshot.unknown_lot_leak(physical)) == 4
    # Full-Pool candidates carry no unknown lots.
    candidates = snapshot.candidates()
    assert snapshot.unknown_lot_leak(candidates) == []
