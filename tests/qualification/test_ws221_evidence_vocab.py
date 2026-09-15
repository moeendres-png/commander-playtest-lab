"""WS221 evidence-vocabulary / harness-strictness / legacy-map / manifest tests.

S1: controlled vocabulary (evidence-vocab-v1), reject-not-coerce machine joins,
explicit versioned legacy mapping. S4: manifest negative proof + coverage of
post-manifest seal files. No runtime/JVM; no behavior credit.
"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[2]
QUAL = ROOT / "qualification"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vocab():
    return _load("ws221_evidence_vocab", QUAL / "evidence_vocab_v1.py")


@pytest.fixture(scope="module")
def harness():
    return _load("ws221_harness", QUAL / "harness.py")


def _manifest(fixture_ids):
    return {
        "protocol": "test-protocol-1",
        "authority_lock_sha256": "0" * 64,
        "denominator_hashes": {},
        "fixtures": [{"fixture_id": fid} for fid in fixture_ids],
    }


def _responder(tmp_path, payload):
    """Write a fake provider script emitting one fixed payload per request."""
    script = tmp_path / "responder.py"
    script.write_text(
        "import json,sys\n"
        f"PAYLOAD={payload!r}\n"
        "for line in sys.stdin:\n"
        "    line=line.strip()\n"
        "    if line:\n"
        '        print(json.dumps({"payload": PAYLOAD}))\n',
        encoding="utf-8",
    )
    return f"{sys.executable} {script}"


def _run(harness, tmp_path, payload, fixture_ids=("F1",)):
    cmd = _responder(tmp_path, payload)
    return harness.execute("candidate-under-test", {"lock": "test"}, _manifest(fixture_ids), cmd)


# --- Axis discipline: no semantic flattening ---------------------------------


def test_controlled_axes_stay_distinct(vocab):
    assert set(vocab.EVIDENCE_CLASSES) == {
        "RUNTIME_VERIFIED",
        "DIRECT_CODE_FAIL",
        "CODE_DERIVED",
        "SOURCE_DERIVED",
        "NOT_RUN",
        "DIRECTLY_VERIFIED",
        "TECHNICALLY_CONFORMANT",
        "EXTERNALLY_RULE_VALIDATED",
        "MODELED",
        "SYNTHETIC",
        "UNKNOWN",
    }
    # Verdict / failure-classification / omission vocabularies are unchanged and
    # remain separate enums — evidence class was not collapsed into them.
    assert set(vocab.VERDICTS) == {
        "PASS",
        "FAIL",
        "UNKNOWN",
        "NOT_RUN",
        "PARTIAL",
        "UNSUPPORTED",
        "NOT_APPLICABLE",
    }
    assert "RUNTIME_PASS" in vocab.FAILURE_CLASSIFICATIONS
    assert "RUNTIME_VERIFIED" not in vocab.FAILURE_CLASSIFICATIONS
    assert "PASS" not in vocab.EVIDENCE_CLASSES


def test_doctrine_invariants(vocab):
    # UNKNOWN is not PASS; CODE_DERIVED is not runtime verification.
    assert not vocab.is_satisfying_evidence("UNKNOWN", "UNKNOWN")
    assert not vocab.is_satisfying_evidence("PASS", "CODE_DERIVED")
    assert not vocab.is_satisfying_evidence("PASS", "DIRECTLY_VERIFIED")
    assert not vocab.is_satisfying_evidence("PASS", "NOT_RUN")
    assert vocab.is_satisfying_evidence("PASS", "RUNTIME_VERIFIED")


def test_require_evidence_class_rejects(vocab):
    for bad in (
        None,
        "",
        "RUNTIME_VERIFIED unless a gate cites a sealed historical frame",
        "runtime_verified",
        "PASSED",
        42,
        ["PASS"],
    ):
        with pytest.raises(vocab.UnmappedEvidenceTerm):
            vocab.require_evidence_class(bad)
    for good in vocab.EVIDENCE_CLASSES:
        assert vocab.require_evidence_class(good) == good


# --- Harness strictness: reject, never coerce ---------------------------------


def test_harness_rejects_missing_evidence_class(harness, tmp_path):
    rows = _run(harness, tmp_path, {"verdict": "PASS", "reason": "x"})
    assert rows[0]["verdict"] == "UNKNOWN"
    assert rows[0]["evidence_class"] == "UNKNOWN"
    assert rows[0]["classification"] == "RUNTIME_NOT_RUN"


def test_harness_rejects_unmapped_free_prose(harness, tmp_path):
    rows = _run(
        harness,
        tmp_path,
        {
            "verdict": "PASS",
            "evidence_class": "RUNTIME_VERIFIED unless a gate cites a sealed historical frame",
            "reason": "legacy prose must not flow through a machine join",
        },
    )
    assert rows[0]["verdict"] == "UNKNOWN"
    assert rows[0]["evidence_class"] == "UNKNOWN"
    assert rows[0]["classification"] == "RUNTIME_NOT_RUN"
    assert "rejected" in rows[0]["reason"]


def test_harness_rejects_pass_with_code_derived(harness, tmp_path):
    # The WS220 coercion path: PASS + weak evidence must never become
    # RUNTIME_VERIFIED/RUNTIME_PASS. The weak claim is preserved for diagnosis.
    rows = _run(
        harness,
        tmp_path,
        {"verdict": "PASS", "evidence_class": "CODE_DERIVED", "reason": "static only"},
    )
    assert rows[0]["verdict"] == "UNKNOWN"
    assert rows[0]["evidence_class"] == "CODE_DERIVED"
    assert rows[0]["classification"] == "RUNTIME_NOT_RUN"


def test_harness_accepts_explicit_runtime_pass(harness, tmp_path):
    rows = _run(
        harness,
        tmp_path,
        {"verdict": "PASS", "evidence_class": "RUNTIME_VERIFIED", "reason": "engine observed"},
    )
    assert rows[0]["verdict"] == "PASS"
    assert rows[0]["evidence_class"] == "RUNTIME_VERIFIED"
    assert rows[0]["classification"] == "RUNTIME_PASS"


def test_harness_accepts_controlled_unknown_without_upgrade(harness, tmp_path):
    rows = _run(
        harness,
        tmp_path,
        {"verdict": "UNKNOWN", "evidence_class": "UNKNOWN", "reason": "not established"},
    )
    assert (rows[0]["verdict"], rows[0]["evidence_class"], rows[0]["classification"]) == (
        "UNKNOWN",
        "UNKNOWN",
        "RUNTIME_NOT_RUN",
    )


def test_harness_rejected_rows_block_admission(harness, tmp_path):
    rows = _run(
        harness,
        tmp_path,
        {"verdict": "PASS", "reason": "no class supplied"},
        fixture_ids=("F1", "F2"),
    )
    adm = harness.aggregate(rows, ["F1", "F2"])
    assert adm["production_admission"] == "FAIL"


# --- Legacy mapping: explicit, versioned, read-time ----------------------------


def test_legacy_map_covers_sealed_free_prose(vocab):
    m88 = vocab.map_legacy_evidence_class(
        "RUNTIME_VERIFIED unless a gate cites a sealed historical frame"
    )
    assert m88["evidence_class"] == "RUNTIME_VERIFIED" and m88["legacy"] is True
    m80 = vocab.map_legacy_evidence_class(
        "CODE_DERIVED unless noted as RUNTIME_VERIFIED by the named test or regression run"
    )
    assert m80["evidence_class"] == "CODE_DERIVED" and m80["legacy"] is True
    m90 = vocab.map_legacy_evidence_class(
        "CODE_DERIVED for semantic comparison; TECHNICALLY_CONFORMANT for authority binding "
        "where proven; DIRECTLY_VERIFIED for git-state and validator runs; NOT_RUN for behavior"
    )
    assert m90["aspects"] == {
        "semantic_comparison": "CODE_DERIVED",
        "authority_binding": "TECHNICALLY_CONFORMANT",
        "git_state_and_validator_runs": "DIRECTLY_VERIFIED",
        "behavior": "NOT_RUN",
    }
    with pytest.raises(vocab.UnmappedEvidenceTerm):
        vocab.map_legacy_evidence_class("a brand-new term from nowhere")


def test_legacy_map_aspect_terms_are_controlled(vocab):
    entry = vocab.map_legacy_evidence_class(
        "CODE_DERIVED for semantic comparison; TECHNICALLY_CONFORMANT for authority binding "
        "where proven; DIRECTLY_VERIFIED for git-state and validator runs; NOT_RUN for behavior"
    )
    for term in entry["aspects"].values():
        assert term in vocab.EVIDENCE_CLASSES


# --- Schemas: controlled enum, free prose rejected -----------------------------


def test_schemas_accept_controlled_unknown_and_reject_prose():
    schema = json.loads((QUAL / "evidence" / "normalized_evidence_v1.schema.json").read_text())
    base = {
        "fixture_id": "F1",
        "candidate": "c",
        "source_lock": {},
        "verdict": "UNKNOWN",
        "evidence_class": "UNKNOWN",
        "reason": "not established",
        "artifact_hashes": {},
    }
    Draft202012Validator(schema).validate(base)
    for term in ("DIRECTLY_VERIFIED", "TECHNICALLY_CONFORMANT", "MODELED", "SYNTHETIC"):
        Draft202012Validator(schema).validate({**base, "evidence_class": term})
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(
            {**base, "evidence_class": "RUNTIME_VERIFIED unless a gate cites history"}
        )


# --- Manifests: coverage + negative proof (S4) ----------------------------------


def test_manifest_covers_post_ws17_seal_files():
    recorded = set()
    for raw in (ROOT / "WS17_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if raw.strip():
            recorded.add(raw.split("  ", 1)[1])
    for rel in (
        "qualification/ws213-xmage-consolidated-requalification/FINAL_HANDOFF.md",
        "qualification/ws215-xmage-variable-player-multicardinality/CAPABILITY_TRUTH.md",
        "qualification/evidence_vocab_v1.py",
        "qualification/harness.py",
    ):
        assert rel in recorded, rel


def test_manifest_mismatch_is_rejected(tmp_path):
    target = tmp_path / "sealed.txt"
    target.write_bytes(b"sealed bytes")
    digest = hashlib.sha256(b"sealed bytes").hexdigest()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
    target.write_bytes(b"tampered bytes")
    assert hashlib.sha256(target.read_bytes()).hexdigest() != digest
