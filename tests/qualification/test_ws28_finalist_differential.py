from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/ws28"
MANIFEST_SHA256 = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"


def _load(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_source_lock_is_exact():
    p = _load("WS28_SOURCE_LOCK.json")
    assert p["protocol"] == "commander-lab.rules-service/1.1.0"
    assert p["common_denominator"] == 135
    assert p["common_manifest_sha256"] == MANIFEST_SHA256
    assert p["forge"]["commander_lab_head"] == "09cfad8a24be12a87761e6645c48577387f0521b"
    assert p["forge"]["engine_commit"] == "1e604105f9e279331063824943b9222b6589f5d8"
    assert p["forge"]["engine_tree"] == "994976e06aaf99b807646b60b1aa2ac9f7703df4"
    assert p["xmage"]["behavioral_head"] == "a53c2312983384eb0870746132e281bbed2f5a1d"
    assert p["xmage"]["engine_commit"] == "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
    assert p["xmage"]["engine_tree"] == "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"


def test_strict_shared_passes_are_not_promoted_without_isomorphism():
    p = _load("WS28_STRICT_18_DIFFERENTIAL.json")
    assert p["starting_independent_shared_pass"] == 18
    assert p["differential_agreement_pass"] == 0
    assert len(p["rows"]) == 18
    assert {r["differential_verdict"] for r in p["rows"]} == {"SETUP_NONISOMORPHIC"}
    assert all(r["both_executed"] for r in p["rows"])
    assert not any(r["semantic_setup_equivalent"] for r in p["rows"])


def test_all_asymmetric_passes_were_attempted_opposite_and_remain_unsupported():
    p = _load("WS28_CROSS_MATERIALIZATION_RESULTS.json")
    assert p["forge_to_xmage"] == {"attempted": 16, "new_pass": 0, "unsupported": 16}
    assert p["xmage_to_forge"] == {"attempted": 16, "new_pass": 0, "unsupported": 16}
    assert len(p["rows"]) == 32
    assert all(r["attempted_on_exact_candidate"] for r in p["rows"])
    assert not any(r["behavior_executed_on_opposite_candidate"] for r in p["rows"])
    assert {r["differential_verdict"] for r in p["rows"]} == {"CANDIDATE_UNSUPPORTED"}


def test_135_matrix_is_complete_and_fail_closed():
    p = _load("WS28_FINALIST_MATRIX_135.json")
    rows = p["rows"]
    assert p["denominator"] == 135
    assert p["manifest_sha256"] == MANIFEST_SHA256
    assert len(rows) == 135
    assert len({r["fixture_id"] for r in rows}) == 135
    counts = {}
    for row in rows:
        counts[row["differential_verdict"]] = counts.get(row["differential_verdict"], 0) + 1
    assert counts == {"SETUP_NONISOMORPHIC": 18, "CANDIDATE_UNSUPPORTED": 91, "AUTHORITY_BLOCKED": 26}
    assert not any(r["differential_verdict"] == "DIFFERENTIAL_AGREEMENT_PASS" for r in rows)


def test_direct_rules_defect_register_does_not_overclaim():
    p = _load("WS28_DIRECT_RULES_DEFECT_REGISTER.json")
    assert p["xmage_rules_defects"] == []
    assert p["forge_rules_defects"] == []
    assert p["both_rules_defects"] == []
    assert p["rules_defect_conclusion"] == "NONE_IDENTIFIED_NOT_EQUIVALENT_TO_RULES_PASS"


def test_ws28_hash_manifest_matches_files():
    for line in (EVIDENCE / "WS28_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        actual = hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest()
        assert actual == digest
