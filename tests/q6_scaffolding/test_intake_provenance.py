"""Tests: deterministic intake identities and provenance preservation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding.gate import validate_output
from q6_scaffolding.intake import IntakeError, detect_conflicts, intake_card
from q6_scaffolding.provenance import (
    ProvenanceError,
    SourceLock,
    build_provenance,
    check_input_hash,
    compute_intake_id,
)
from q6_scaffolding.states import ScaffoldingState

PIN = "8c7e9afb8e6caee88644b94e25da5852e36f8928"
REPO = "https://github.com/Card-Forge/forge.git"


def _lock(**over):
    base = {
        "source_corpus": "forge-card-scripts",
        "source_repository": REPO,
        "source_commit": PIN,
        "source_path": "forge-gui/res/cardsfolder/l/lightning_bolt.txt",
    }
    base.update(over)
    return SourceLock(**base)


RAW = b"Name:Lightning Bolt\nManaCost:R\nTypes:Instant\n"


def test_same_input_same_tool_version_same_intake_id():
    first = intake_card(RAW, _lock())
    second = intake_card(RAW, _lock())
    assert first.intake_id == second.intake_id
    assert len(first.intake_id) == 32


def test_different_pin_different_intake_id():
    other_pin = "0" * 40
    assert compute_intake_id(_lock(), "ab" * 32) != compute_intake_id(
        _lock(source_commit=other_pin), "ab" * 32
    )


def test_different_content_different_intake_id():
    assert (
        intake_card(RAW, _lock()).intake_id != intake_card(RAW + b"Oracle:X\n", _lock()).intake_id
    )


def test_different_tool_version_different_intake_id():
    digest = "ab" * 32
    assert compute_intake_id(_lock(), digest, "v1") != compute_intake_id(_lock(), digest, "v2")


def test_missing_source_lock_field_fails_closed():
    with pytest.raises(ProvenanceError):
        intake_card(RAW, _lock(source_commit=""))
    with pytest.raises(ProvenanceError):
        intake_card(RAW, _lock(source_path="  "))
    with pytest.raises(ProvenanceError):
        intake_card(RAW, _lock(source_repository=""))


def test_ambiguous_commit_pin_fails_closed():
    with pytest.raises(ProvenanceError):
        intake_card(RAW, _lock(source_commit="not-a-sha"))
    with pytest.raises(ProvenanceError):
        intake_card(RAW, _lock(source_commit="xyz"))


def test_hash_mismatch_fails_closed():
    with pytest.raises(ProvenanceError, match="hash mismatch"):
        intake_card(RAW, _lock(), expected_hash="00" * 32)


def test_matching_expected_hash_accepted():
    provenance = build_provenance(_lock(), RAW)
    record = intake_card(RAW, _lock(), expected_hash=provenance.input_hash)
    assert record.provenance["input_hash"] == provenance.input_hash


def test_check_input_hash_case_insensitive():
    provenance = build_provenance(_lock(), RAW)
    check_input_hash(RAW, provenance.input_hash.upper(), source="test")


def test_duplicate_identical_intake_rejected():
    first = intake_card(RAW, _lock())
    second = intake_card(RAW, _lock())
    with pytest.raises(IntakeError, match="duplicate intake identity"):
        detect_conflicts([first, second])


def test_conflicting_identity_same_id_different_content_rejected():
    first = intake_card(RAW, _lock())
    second = intake_card(RAW + b"Oracle:X\n", _lock())
    # Force the ID collision to prove the conflict branch (same ID, other bytes).
    second.intake_id = first.intake_id
    with pytest.raises(IntakeError, match="conflicting identity"):
        detect_conflicts([first, second])


def test_conflicting_source_path_rejected():
    first = intake_card(RAW, _lock())
    second = intake_card(
        RAW + b"Oracle:X\n", _lock(source_path="forge-gui/res/cardsfolder/x/other.txt")
    )
    second.provenance["source_path"] = first.provenance["source_path"]
    with pytest.raises(IntakeError, match="conflicting source path"):
        detect_conflicts([first, second])


def test_non_utf8_input_rejected():
    with pytest.raises(IntakeError, match="not valid UTF-8"):
        intake_card(b"\xff\xfe\x00Name", _lock())


def test_intake_record_state_and_schema():
    record = intake_card(RAW, _lock())
    assert record.state == ScaffoldingState.INTAKE_ONLY.value
    assert record.card_name_hint == "Lightning Bolt"
    assert record.provenance["tool_version"]
    assert record.provenance["source_commit"] == PIN
    validate_output(record.as_dict(), artifact="test-intake")


def test_provenance_chain_complete():
    provenance = build_provenance(_lock(), RAW)
    data = provenance.as_dict()
    for key in (
        "source_corpus",
        "source_repository",
        "source_commit",
        "source_path",
        "input_hash",
        "tool_version",
        "intake_id",
    ):
        assert data[key], f"provenance chain missing {key}"
