"""Impact adjudication for evidence produced under the XMage shuffle defect.

The load-bearing property is narrowness: a finding is impacted only when its
obligation depends on the behaviour the defect corrupted. Marking everything
impacted would be as dishonest as marking nothing, and marking nothing is the
silent failure this exists to catch.
"""

from __future__ import annotations

import json
from pathlib import Path

from commander_lab.qualification.current_boundary.impact_adjudication import (
    IMPACTED,
    UNAFFECTED,
    adjudicate_xmage_shuffle_impact,
    default_defect_change,
)


def test_the_three_state_dependent_findings_are_impacted() -> None:
    out = adjudicate_xmage_shuffle_impact(defect_change=default_defect_change())
    for finding_id in (
        "xmage_hidden_01",
        "xmage_hidden_02",
        "xmage_pb08_seed_precondition",
    ):
        assert out["dispositions"][finding_id]["disposition"] == IMPACTED, finding_id


def test_topology_findings_are_left_alone() -> None:
    """Over-marking is its own failure: AF11 does not depend on library order."""
    out = adjudicate_xmage_shuffle_impact(defect_change=default_defect_change())
    assert out["dispositions"]["af11_technical_facts"]["disposition"] == UNAFFECTED


def test_adjudication_never_moves_a_verdict_or_rewrites_a_disposition() -> None:
    out = adjudicate_xmage_shuffle_impact(defect_change=default_defect_change())
    assert out["consequences"]["gate_verdicts_changed"] is False
    assert out["consequences"]["dispositions_rewritten"] is False


def test_adjudication_does_not_claim_the_repaired_bridge_passes() -> None:
    out = adjudicate_xmage_shuffle_impact(defect_change=default_defect_change())
    joined = " ".join(out["what_this_does_not_say"])
    assert "only a fresh run at the repaired revision" in joined
    assert "faithfully reports the lane that existed" in joined


def test_adjudication_is_bound_to_a_specific_revision() -> None:
    out = adjudicate_xmage_shuffle_impact(defect_change=default_defect_change())
    assert out["defect"]["repaired_by"] == "938719d0"
    assert out["defect"]["source"]


def test_requalification_is_handed_over_not_raced() -> None:
    out = adjudicate_xmage_shuffle_impact(defect_change=default_defect_change())
    assert out["consequences"]["requalification_required"], "something must require requalification"
    assert "PR #284" in out["consequences"]["why_not_requalified_here"]


def test_a_finding_that_does_not_depend_on_the_defect_is_not_marked() -> None:
    findings = {
        "pure_topology_thing": {
            "description": "adapter process boundary",
            "depends_on_corrupted_behaviour": False,
            "channel": "process",
        }
    }
    out = adjudicate_xmage_shuffle_impact(defect_change=default_defect_change(), findings=findings)
    assert out["counts"][IMPACTED] == 0
    assert out["counts"][UNAFFECTED] == 1
    assert out["consequences"]["requalification_required"] == []


def test_counts_cover_every_disposition() -> None:
    out = adjudicate_xmage_shuffle_impact(defect_change=default_defect_change())
    assert out["counts"][IMPACTED] + out["counts"][UNAFFECTED] == out["counts"]["total"]


# ---------------------------------------------------------------------------
# The durable bridge-validation artifact must be reproducible and must not
# overclaim: the bridge suite passing is not the current-boundary column
# passing.
# ---------------------------------------------------------------------------

ARTIFACT = Path("qualification/final-current-boundary-20260927/BRIDGE_VALIDATION_XMAGE.json")


def _artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_bridge_validation_artifact_exists_and_binds_a_revision() -> None:
    document = _artifact()
    assert document["lab_revision"]["commit"]
    assert document["lab_revision"]["tree"]


def test_bridge_validation_was_captured_on_a_clean_bridge() -> None:
    """The bridge is what was tested, so its cleanliness is the binding fact."""
    revision = _artifact()["lab_revision"]
    assert revision["bridge_dirty"] is False
    assert revision["bridge_matches_recorded_revision"] is True


def test_bridge_validation_records_no_failures() -> None:
    totals = _artifact()["suite_totals"]
    assert totals["failures"] == 0
    assert totals["errors"] == 0
    assert totals["tests"] > 0


def test_bridge_validation_covers_the_shuffle_and_seed_suites() -> None:
    document = _artifact()
    assert document["focus_suites_missing"] == []
    names = {str(s["suite"]).split(".")[-1] for s in document["focus_suites"]}
    assert names == {
        "XmageGenericLaneRulesSeedTest",
        "XmageBridgePlayerFailClosedTest",
        "XmageFullGameRulesSeedBindingTest",
    }
    cases = {case for suite in document["focus_suites"] for case in suite["cases"]}
    # The two claims the adjudication rests on must be directly covered.
    assert "genericBridgePlayerNeverOverridesTheEngineShuffle" in cases
    assert "differentSeedChangesTheOpeningShuffle" in cases


def test_bridge_validation_does_not_claim_the_column_is_requalified() -> None:
    document = _artifact()
    joined = " ".join(document["what_this_does_not_establish"])
    assert "run_current_boundary_qualification.py" in joined
    assert "AF05/AF09 stay UNKNOWN" in joined
