"""Lane integrity: a legal game start requires a shuffle (CR 103.3).

The XMage shuffle defect survived observation because its footprint was recorded
-- "no shuffle/order-knowledge invalidation scenario reachable" -- and read as an
ordinary coverage gap. These tests pin the connection that was missing: a lane
that demonstrates no shuffling cannot have executed a legal game start, so
order-knowledge obligations cannot be credited on it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary.lane_integrity import (
    LANE_INTEGRITY_OK,
    LANE_INTEGRITY_UNPROVEN,
    assess_lane_integrity,
    blocking_obligations,
)

OUT = Path("qualification/final-current-boundary-20260927")


def _document(
    *,
    seed: Any = None,
    rng_counter: Any = None,
    seed_controlled: Any = None,
    unreached: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "runtime_identity": {"seed_controlled": seed_controlled},
        "principal_observations": {
            "p1": {
                "state": {"seed": seed, "rng_counter": rng_counter},
                "seed_controlled": seed_controlled,
            }
        },
        "historical_forge_seams_classified_freshly": unreached or {},
    }


def test_a_lane_with_no_shuffle_and_no_seed_is_not_demonstrated() -> None:
    out = assess_lane_integrity(_document(unreached={"HIDDEN_11": "no shuffle reachable"}))
    assert out["disposition"] == LANE_INTEGRITY_UNPROVEN
    assert out["rule_basis"].startswith("CR 103.3")


def test_an_unreached_shuffle_obligation_blocks_order_knowledge_credit() -> None:
    out = assess_lane_integrity(
        _document(seed=424242, seed_controlled=True, unreached={"HIDDEN_11": "not reachable"})
    )
    assert out["disposition"] == LANE_INTEGRITY_UNPROVEN
    assert out["blocking_reasons"]


def test_a_seeded_lane_without_an_unreached_shuffle_is_demonstrated() -> None:
    out = assess_lane_integrity(_document(seed=424242, seed_controlled=True))
    assert out["disposition"] == LANE_INTEGRITY_OK
    assert blocking_obligations(out) == []


def test_seed_binding_can_come_from_the_artifact_that_records_it() -> None:
    """Under-reporting a candidate whose binding lives elsewhere is its own error."""
    doc = _document(unreached=None)
    without = assess_lane_integrity(doc)
    with_binding = assess_lane_integrity(doc, seed_binding={"controlled": True})
    assert without["signals"]["seed_controlled"] is not True
    assert with_binding["signals"]["seed_controlled"] is True


def test_blocked_obligations_come_from_the_rule_not_from_the_run() -> None:
    """An obligation is blocked by its nature, not by whether the harness noticed."""
    out = assess_lane_integrity(_document())  # mentions no obligation at all
    assert "HIDDEN_11" in blocking_obligations(out)
    assert "HIDDEN_02" in blocking_obligations(out)


def test_a_blocked_lane_blocks_even_obligations_the_run_did_not_mention() -> None:
    out = assess_lane_integrity(_document(unreached={"HIDDEN_11": "no shuffle"}))
    blocked = blocking_obligations(out)
    assert len(blocked) >= 4
    assert blocked == sorted(blocked)


def test_the_check_does_not_diagnose_the_engine() -> None:
    out = assess_lane_integrity(_document())
    assert "that the engine is defective" in out["does_not_claim"]
    assert "a fresh run at the repaired revision" in out["does_not_claim"]


def test_the_consequence_names_the_inconsistency_not_a_coverage_gap() -> None:
    out = assess_lane_integrity(_document(unreached={"HIDDEN_11": "no shuffle reachable"}))
    assert "ordinary coverage gap" in out["consequence"]
    assert "inconsistency with a legal game start" in out["consequence"]


# ---------------------------------------------------------------------------
# The committed evidence must be read exactly as it is, and both candidates must
# be scrutinised. Forge was not the candidate whose defect was published; that
# is not a reason to exempt it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("candidate", ["XMAGE", "FORGE"])
def test_committed_evidence_is_assessed(candidate: str) -> None:
    hidden = json.loads((OUT / f"HIDDEN_INFO_{candidate}.json").read_text(encoding="utf-8"))
    rng = json.loads((OUT / f"RNG_REPLAY_{candidate}.json").read_text(encoding="utf-8"))
    out = assess_lane_integrity(hidden, seed_binding=rng.get("rules_rng_binding"))
    assert out["disposition"] in {LANE_INTEGRITY_OK, LANE_INTEGRITY_UNPROVEN}
    assert out["signals"]


@pytest.mark.parametrize("candidate", ["XMAGE", "FORGE"])
def test_committed_evidence_leaves_shuffle_invalidation_unreached(candidate: str) -> None:
    """Records the finding: neither committed lane demonstrated a shuffle.

    For XMage this is the footprint of the removed shuffleLibrary no-op. For
    Forge it is an unexplained gap. Both are recorded rather than assumed benign.
    """
    hidden = json.loads((OUT / f"HIDDEN_INFO_{candidate}.json").read_text(encoding="utf-8"))
    out = assess_lane_integrity(hidden)
    assert "HIDDEN_11" in out["signals"]["unreached_shuffle_obligations"]
    assert out["disposition"] == LANE_INTEGRITY_UNPROVEN
    assert "HIDDEN_02" in blocking_obligations(out)


def test_xmage_committed_lane_reports_no_seed_control() -> None:
    hidden = json.loads((OUT / "HIDDEN_INFO_XMAGE.json").read_text(encoding="utf-8"))
    rng = json.loads((OUT / "RNG_REPLAY_XMAGE.json").read_text(encoding="utf-8"))
    out = assess_lane_integrity(hidden, seed_binding=rng.get("rules_rng_binding"))
    assert out["signals"]["seed_controlled"] is False
    assert len(out["blocking_reasons"]) >= 2


def test_forge_committed_lane_records_seed_control_but_still_no_shuffle() -> None:
    hidden = json.loads((OUT / "HIDDEN_INFO_FORGE.json").read_text(encoding="utf-8"))
    rng = json.loads((OUT / "RNG_REPLAY_FORGE.json").read_text(encoding="utf-8"))
    out = assess_lane_integrity(hidden, seed_binding=rng.get("rules_rng_binding"))
    assert out["signals"]["seed_controlled"] is True
    # Seed control is not the same as demonstrating that a shuffle invalidated
    # order knowledge, so the lane is still not demonstrated.
    assert out["disposition"] == LANE_INTEGRITY_UNPROVEN
