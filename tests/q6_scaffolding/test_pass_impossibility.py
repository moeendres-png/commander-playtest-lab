"""Tests: structural PASS-impossibility (the hard gate).

Each test proves one contamination route cannot yield behavior PASS,
qualification credit, or coverage promotion. If the data model ever grows a
behavior-credit field, these tests fail by construction.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.gate import (
    PromotionRejected,
    reject_promotion_fields,
    validate_output,
)
from q6_scaffolding.intake import IntakeError, intake_card
from q6_scaffolding.provenance import SourceLock

from q6_scaffolding import cli

from .support import FIXTURES, run_pipeline

PIN = "8c7e9afb8e6caee88644b94e25da5852e36f8928"


def _lock():
    return SourceLock(
        source_corpus="forge-card-scripts",
        source_repository="https://github.com/Card-Forge/forge.git",
        source_commit=PIN,
        source_path="forge-gui/res/cardsfolder/l/lightning_bolt.txt",
    )


RAW = (FIXTURES / "cards" / "lightning_bolt.txt").read_bytes()


def test_malicious_behavior_pass_in_metadata_rejected():
    with pytest.raises(IntakeError):
        intake_card(RAW, _lock(), extra_metadata={"behavior_pass": True})


def test_malicious_pass_result_in_metadata_rejected():
    with pytest.raises(IntakeError):
        intake_card(RAW, _lock(), extra_metadata={"nested": {"behavior_result": "PASS"}})


def test_imported_fixture_claiming_pass_rejected():
    with pytest.raises(PromotionRejected):
        reject_promotion_fields(
            {"card": "X", "tests": [{"behavior_pass": True}]}, source="external"
        )


def test_xmage_expected_outcome_rejected():
    with pytest.raises(PromotionRejected):
        reject_promotion_fields(
            {"assertLife": 20, "expected": {"life": 20}}, source="xmage-adaptation"
        )


def test_xmage_assertion_keys_rejected():
    with pytest.raises(PromotionRejected):
        reject_promotion_fields({"assertPermanentCount": 3}, source="xmage")


def test_outcome_key_rejected():
    with pytest.raises(PromotionRejected):
        reject_promotion_fields({"outcome": "win"}, source="external")


def test_engine_ai_markers_rejected():
    with pytest.raises(PromotionRejected):
        reject_promotion_fields({"script": "aiPlayPriority(player)"}, source="xmage-driver")
    with pytest.raises(PromotionRejected):
        reject_promotion_fields({"engine_ai": True}, source="xmage-driver")


def test_harness_hook_text_rejected():
    with pytest.raises(PromotionRejected):
        reject_promotion_fields({"notes": "uses runCode probes"}, source="harness")


def test_coverage_promotion_rejected():
    with pytest.raises(PromotionRejected):
        reject_promotion_fields({"coverage_increment": 3}, source="operator")
    with pytest.raises(PromotionRejected):
        reject_promotion_fields({"qualified": True}, source="operator")
    with pytest.raises(PromotionRejected):
        reject_promotion_fields({"externally_rule_validated": True}, source="operator")


def test_expected_hash_integrity_field_allowed():
    # Content-integrity hashes are not behavioral outcomes.
    reject_promotion_fields({"expected_hash": "ab" * 32}, source="inputs-spec")


def test_output_gate_catches_smuggled_behavior_pass():
    with pytest.raises(PromotionRejected):
        validate_output({"skeleton_id": "s", "behavior_pass": False}, artifact="t")


def test_output_gate_catches_nested_legal_options():
    with pytest.raises(PromotionRejected):
        validate_output({"outer": {"legal_options": ["a", "b"]}}, artifact="smuggled")


def test_output_gate_catches_expected_life_total():
    with pytest.raises(PromotionRejected):
        validate_output({"expected_life_total": 20}, artifact="smuggled")


def test_full_pipeline_artifacts_carry_no_credit_fields(tmp_path):
    out = run_pipeline(tmp_path)
    for artifact_name, artifact in out.items():
        validate_output(artifact, artifact=f"pipeline:{artifact_name}")
    manifest = out["manifest"]
    blob = repr(manifest)
    for forbidden in (
        "behavior_pass",
        "behavior_result",
        "coverage_increment",
        "qualified",
        "externally_rule_validated",
        "legal_options",
        "expected_outcome",
        "expected_life",
    ):
        assert forbidden not in blob, f"credit field leaked: {forbidden}"


def test_maximal_confidence_parse_still_yields_no_pass(tmp_path):
    out = run_pipeline(tmp_path)
    ready = [
        r for r in out["skeletons"]["records"] if r["state"] == "READY_FOR_RUNTIME_QUALIFICATION"
    ]
    assert ready, "sample must contain READY records for this negative proof"
    for record in ready:
        assert record["state"] != "PASS"
        assert "PASS" not in record["state"]
        assert record["skeleton"]["state"] == "SKELETON_GENERATED"


def test_skeleton_completion_is_not_a_verdict(tmp_path):
    out = run_pipeline(tmp_path)
    for record in out["skeletons"]["records"]:
        skeleton = record["skeleton"]
        assert "verdict" not in skeleton
        assert "result" not in skeleton
        for witness in skeleton["witness_requirements"]:
            assert witness["evidence"] is None
            assert witness["required"] is True


def test_cli_rejects_promotion_in_configuration(tmp_path):
    out = run_pipeline(tmp_path)
    manifest_p = tmp_path / "manifest.json"
    bad_config = tmp_path / "bad_config.json"
    bad_config.write_text('{"coverage_increment": 1}')
    code = cli.main(
        [
            "build-manifest",
            "--in",
            str(tmp_path / "skel.json"),
            "--queues",
            str(tmp_path / "queues.json"),
            "--configuration",
            str(bad_config),
            "--out",
            str(manifest_p),
        ]
    )
    assert code == 2
    _ = out


def test_registries_carry_no_credit_fields():
    import json as _json
    from pathlib import Path as _Path

    from q6_scaffolding.registries import (
        static_mode_registry,
        trigger_mode_registry,
        unsupported_registry,
        verb_registry,
    )

    for doc in (
        verb_registry(),
        trigger_mode_registry(),
        static_mode_registry(),
        unsupported_registry(),
    ):
        validate_output(doc, artifact="registry")
    _ = _json, _Path


def test_contaminated_registry_like_dict_rejected():
    with pytest.raises(PromotionRejected):
        validate_output(
            {"verbs": {"Draw": {"shape": "DRAW_SHAPE", "behavior_pass": True}}},
            artifact="contaminated-registry",
        )


def test_before_inventory_evidence_carries_no_credit_fields():
    import json as _json
    from pathlib import Path as _Path

    before = _json.loads(
        (
            _Path(__file__).resolve().parents[2]
            / "docs"
            / "qualification"
            / "q6-scaffolding"
            / "evidence"
            / "corpus-inventory-before.json"
        ).read_text(encoding="utf-8")
    )
    validate_output(before, artifact="corpus-inventory-before")


def test_contaminated_script_fails_closed_at_classify(tmp_path):
    import json as _json

    from q6_scaffolding.provenance import SourceLock

    lock = SourceLock(
        source_corpus="forge-card-scripts",
        source_repository="https://github.com/Card-Forge/forge.git",
        source_commit=PIN,
        source_path="forge-gui/res/cardsfolder/x/synthetic_evil.txt",
    )
    record = intake_card(b"Name:Evil\nA:SP$ Draw | behavior_pass$ True\n", lock)
    intake_p = tmp_path / "intake.json"
    intake_p.write_text(
        _json.dumps({"records": [record.as_dict()], "tool_version": "q6-scaffolding-0.1.0"})
    )
    out_p = tmp_path / "classified.json"
    code = cli.main(["classify", "--in", str(intake_p), "--out", str(out_p)])
    assert code == 2
    assert not out_p.exists(), "contaminated input must not produce partial output"


def test_manual_review_verbs_carry_no_credit(tmp_path):
    out = run_pipeline(tmp_path)
    manual = [r for r in out["skeletons"]["records"] if r["state"] == "MANUAL_REVIEW_REQUIRED"]
    assert manual, "sample must contain MANUAL records for this negative proof"
    for record in manual:
        validate_output(record, artifact="manual-record")
        assert record["state"] != "PASS"


def test_new_question_skeletons_carry_no_verdicts(tmp_path):
    out = run_pipeline(tmp_path)
    for record in out["skeletons"]["records"]:
        for question in record["skeleton"]["rules_questions"]:
            assert question["status"] == "OPEN"
            assert question["resolving_authority"] == "human_coordinator_rules_adjudication"
            validate_output(question, artifact="rules-question")


def test_unknown_tripwire_never_routes_ready():
    from q6_scaffolding.classify import classify_card
    from q6_scaffolding.forge_parser import extract_features, parse_script
    from q6_scaffolding.skeleton import generate_skeleton, route_state

    parsed = parse_script("Name:X\nT:Mode$ FrobnicateMode | Execute$ Foo\n", "synthetic")
    feats = extract_features(parsed, "Name:X\nT:Mode$ FrobnicateMode | Execute$ Foo\n")
    assert feats["unknown_trigger_modes"] == ["FrobnicateMode"]
    classification = classify_card("id-unk", feats)
    skeleton = generate_skeleton("id-unk", "Unk", feats, classification)
    state, _ = route_state(
        ambiguous=parsed["ambiguous"],
        unsupported=parsed["unsupported"],
        features=feats,
        classification=classification,
        skeleton=skeleton,
    )
    assert state.value == "MANUAL_REVIEW_REQUIRED"
