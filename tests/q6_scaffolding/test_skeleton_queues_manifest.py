"""Tests: skeleton value-freedom, queue routing, manifests, determinism."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.manifest import build_manifest, verify_manifest
from q6_scaffolding.queues import (
    build_queues,
    cluster_scaffolding_failures,
    queue_item_id,
    scaffolding_failure_records,
)
from q6_scaffolding.skeleton import (
    WITNESS_KINDS,
    generate_skeleton,
    route_state,
    skeleton_id_for,
)
from q6_scaffolding.states import QUEUES, ScaffoldingState

from q6_scaffolding import cli

from .support import by_name, run_pipeline


def test_skeleton_ids_deterministic():
    assert skeleton_id_for("ab" * 16, "TARGET_SELECTION") == skeleton_id_for(
        "ab" * 16, "TARGET_SELECTION"
    )
    assert skeleton_id_for("ab" * 16, "TARGET_SELECTION") != skeleton_id_for(
        "ab" * 16, "MODAL_CHOICE"
    )


def test_skeleton_carries_no_outcome_values(tmp_path):
    out = run_pipeline(tmp_path)
    for record in out["skeletons"]["records"]:
        skeleton = record["skeleton"]
        assert skeleton["expected_decision_pretags"] is not None
        setup = skeleton["public_setup_requirements"]
        prereqs = skeleton["minimum_scenario_prerequisites"]
        for text in setup + prereqs:
            assert "20 life" not in text and "40 life" not in text


def test_witness_checklist_complete_and_unclaimed(tmp_path):
    out = run_pipeline(tmp_path)
    required = set(WITNESS_KINDS) - {"hidden_info_boundary"}
    for record in out["skeletons"]["records"]:
        kinds = {w["witness"] for w in record["skeleton"]["witness_requirements"]}
        assert required <= kinds
        for witness in record["skeleton"]["witness_requirements"]:
            assert witness["authoritative_source"] == "rules_core_runtime"


def test_hidden_info_cards_require_boundary_witness(tmp_path):
    out = run_pipeline(tmp_path)
    willbender = by_name(out["skeletons"]["records"], "Willbender")
    kinds = {w["witness"] for w in willbender["skeleton"]["witness_requirements"]}
    assert "hidden_info_boundary" in kinds


def test_routing_priority_ambiguous_first():
    state, _ = route_state(
        ambiguous=True,
        unsupported=["topkey:MeldPair"],
        features={},
        classification=None,
        skeleton=None,
        provenance_complete=True,
    )
    assert state == ScaffoldingState.AMBIGUOUS


def test_routing_priority_unsupported_before_rules():
    from q6_scaffolding.classify import Classification

    classification = Classification(intake_id="x", capability_families=[])
    skeleton = generate_skeleton("x", "Card", {"has_trigger": True}, classification)
    state, reasons = route_state(
        ambiguous=False,
        unsupported=["topkey:MeldPair"],
        features={"has_trigger": True},
        classification=classification,
        skeleton=skeleton,
    )
    assert state == ScaffoldingState.UNSUPPORTED
    assert any("MeldPair" in r for r in reasons)


def test_routing_ready_only_when_prerequisites_complete():
    from q6_scaffolding.classify import Classification

    classification = Classification(intake_id="x", capability_families=[])
    skeleton = generate_skeleton("x", "Card", {}, classification)
    state, reasons = route_state(
        ambiguous=False,
        unsupported=[],
        features={},
        classification=classification,
        skeleton=skeleton,
    )
    assert state == ScaffoldingState.READY_FOR_RUNTIME_QUALIFICATION
    assert reasons == ["mechanical_prerequisites_complete"]


def test_bounded_sample_routing_distribution(tmp_path):
    out = run_pipeline(tmp_path)
    states = {r["state"] for r in out["skeletons"]["records"]}
    assert "READY_FOR_RUNTIME_QUALIFICATION" in states
    assert "RULES_ADJUDICATION_REQUIRED" in states
    assert "UNSUPPORTED" in states
    gisela = by_name(out["skeletons"]["records"], "Gisela, the Broken Blade")
    assert gisela["state"] == "UNSUPPORTED"
    bolt = by_name(out["skeletons"]["records"], "Lightning Bolt")
    assert bolt["state"] == "READY_FOR_RUNTIME_QUALIFICATION"


def test_all_six_queues_exist_and_are_deterministic(tmp_path):
    first = run_pipeline(tmp_path / "a")
    second = run_pipeline(tmp_path / "b")
    assert set(first["queues"]["queues"]) == set(QUEUES)
    assert first["queues"]["queues"] == second["queues"]["queues"]
    assert first["queues"]["summary"] == second["queues"]["summary"]


def test_queue_items_actionable_and_stable_ids(tmp_path):
    out = run_pipeline(tmp_path)
    for name, items in out["queues"]["queues"].items():
        ids = [i["item_id"] for i in items]
        assert ids == sorted(ids)
        for item in items:
            assert item["required_next_action"]
            assert item["reason"]
            assert item["related_capability"]
            assert item["queue"] == name
            assert item["item_id"] == queue_item_id(name, item["intake_id"], item["reason"])


def test_provenance_review_queue_empty_when_complete(tmp_path):
    out = run_pipeline(tmp_path)
    assert out["queues"]["queues"]["PROVENANCE_REVIEW"] == []


def test_manifest_reproducible_across_runs(tmp_path):
    first = run_pipeline(tmp_path / "a", manifest_id="q6-repro")
    second = run_pipeline(tmp_path / "b", manifest_id="q6-repro")
    assert first["manifest"]["manifest_hash"] == second["manifest"]["manifest_hash"]
    assert first["manifest"] == second["manifest"]


def test_manifest_records_ordered_by_intake_id(tmp_path):
    out = run_pipeline(tmp_path)
    ids = [r["intake_id"] for r in out["manifest"]["records"]]
    assert ids == sorted(ids)


def test_verify_manifest_detects_tampering(tmp_path):
    out = run_pipeline(tmp_path)
    tampered = dict(out["manifest"])
    tampered["records"] = [dict(r) for r in tampered["records"]]
    tampered["records"][0] = dict(tampered["records"][0])
    current = tampered["records"][0]["state"]
    tampered["records"][0]["state"] = "INTAKE_ONLY" if current != "INTAKE_ONLY" else "AMBIGUOUS"
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_manifest(tampered)


def test_verify_manifest_rejects_unknown_schema(tmp_path):
    out = run_pipeline(tmp_path)
    tampered = dict(out["manifest"])
    tampered["schema"] = "q6.campaign-manifest.v9"
    with pytest.raises(ValueError, match="manifest"):
        verify_manifest(tampered)


def test_scaffolding_failures_separate_from_runtime(tmp_path):
    out = run_pipeline(tmp_path)
    records = scaffolding_failure_records(out["skeletons"]["records"])
    assert records
    for record in records:
        assert record["verdict"] == "UNKNOWN"
        # Scaffolding-side kinds only: preparation gaps *for* later runtime
        # qualification, never engine/runtime behavior failures.
        assert record["kind"].split("/")[0] == "scaffolding"
        assert "engine" not in record["kind"]
        assert "behavior" not in record["kind"]


def test_failure_clustering_groups_without_promoting(tmp_path):
    out = run_pipeline(tmp_path)
    clusters = cluster_scaffolding_failures(out["skeletons"]["records"])
    assert clusters
    total = sum(c["count"] for c in clusters)
    assert total == len(scaffolding_failure_records(out["skeletons"]["records"]))
    for cluster in clusters:
        for member in cluster["members"]:
            assert member["verdict"] == "UNKNOWN"


def test_build_manifest_rejects_unknown_intake_reference(tmp_path):
    out = run_pipeline(tmp_path)
    queues_p = tmp_path / "queues.json"
    bad = dict(out["queues"])
    bad["queues"] = {k: list(v) for k, v in out["queues"]["queues"].items()}
    bad["queues"]["MANUAL_SCENARIO_REVIEW"] = [
        *bad["queues"]["MANUAL_SCENARIO_REVIEW"],
        {
            "queue": "MANUAL_SCENARIO_REVIEW",
            "item_id": "x",
            "reason": "r",
            "source": "t",
            "intake_id": "missing-id",
            "card_name_hint": "Ghost",
            "related_capability": "C",
            "required_next_action": "a",
        },
    ]
    import json

    queues_p.write_text(json.dumps(bad))
    manifest_p = tmp_path / "manifest.json"
    code = cli.main(
        ["validate", "--manifest", str(tmp_path / "manifest.json"), "--queues", str(queues_p)]
    )
    assert code == 2
    _ = manifest_p


def test_empty_routing_builds_empty_queues_and_manifest():
    queues = build_queues([])
    assert all(items == [] for items in queues.values())
    manifest = build_manifest([], {name: [] for name in QUEUES})
    verify_manifest(manifest.as_dict())
