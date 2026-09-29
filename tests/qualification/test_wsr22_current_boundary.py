"""WSR22 current-boundary evidence reconciliation (AF10 denominator accounting).

Mechanical guard: every denominator row has exactly one explicit outcome per
candidate, comparison rows are classified, AF00-AF11 each carry one verdict per
candidate, and no packet contains provider-ranking language or an inherited
historical verdict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

OUT = Path("qualification/final-current-boundary-20260927")
CANDIDATES = ("XMAGE", "FORGE")
DENOMINATOR = 107
OUTCOMES = {"PASS", "FAIL", "UNKNOWN", "BLOCKED", "CRASH", "TIMEOUT", "PROTOCOL_FAILURE"}
DISPOSITIONS = {
    "SAME_SEMANTICS",
    "RULES_VISIBLE_DIVERGENCE",
    "ENGINE_CAPABILITY_GAP",
    "HARNESS_OR_ADAPTER_GAP",
    "NON_COMPARABLE",
    "UNKNOWN_PENDING_RULES_ADJUDICATION",
}
GATES = [f"AF{index:02d}" for index in range(12)]
# Precise provider-ranking phrases only. Engine-produced "winner" data is
# legitimate Rules-visible game state (which player won), not a provider ranking.
RANKING_TOKENS = (
    "PREFERRED_PROVIDER",
    "PRODUCTION_PROVIDER_SELECTED",
    "PRODUCTION_PROVIDER = XMAGE",
    "PRODUCTION_PROVIDER = FORGE",
    "BETTER_ENGINE",
    "RECOMMENDED_PROVIDER",
    "WINNER: XMAGE",
    "WINNER: FORGE",
    "XMAGE_WINS",
    "FORGE_WINS",
)
# Only the analytical packets are scanned; raw engine observation payloads
# legitimately contain in-game winner identities.
RANKING_SCAN_PACKETS = (
    "CURRENT_BOUNDARY_COMPARISON.json",
    "DIVERGENCE_PACKET.json",
    "PROVIDER_BLOCKERS.json",
    "AF00_AF11_XMAGE.json",
    "AF00_AF11_FORGE.json",
    "EFFECTIVE_FULL107_MANIFEST.json",
    "FINAL_HANDOFF.md",
)


def _load(name: str) -> Any:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_effective_manifest_is_107_rows_with_successor_binding() -> None:
    manifest = _load("EFFECTIVE_FULL107_MANIFEST.json")
    assert manifest["provider_denominator_count"] == DENOMINATOR
    assert len(manifest["rows"]) == DENOMINATOR
    assert manifest["qualification_boundary"] == "commander-lab.pre-freeze-qualification/2.0.0"
    assert manifest["contract_id"] == "commander-lab.full107/1.0.6-successor"
    start2 = next(row for row in manifest["rows"] if row["fixture_id"] == "WS05-CMD-START-2")
    assert start2["effective_requested_state_digest"] == (
        "bc01a714cbaa035d2f7954d4fd2dcabb63c391160f78774749ab50ab63fa4342"
    )
    assert start2["materialization_status"] == "AUTHORITY_CORRECTED_SUCCESSOR"
    assert "draw_step_started:P1:turn1" in start2["forbidden_events"]
    assert "first_turn_draw_step_skipped:true" in start2["expected_events"]


def test_successor_inheritance_proof_is_mechanical() -> None:
    proof = _load("SUCCESSOR_INHERITANCE_PROOF.json")
    assert proof["changed_fixture_ids"] == ["WS05-CMD-START-2"]
    assert proof["identical_count"] == 106
    assert proof["differing"] == ["WS05-CMD-START-2"]
    assert len(proof["fields_compared"]) >= 10


def test_rules_authority_is_resolved_by_direct_official_capture() -> None:
    receipt = _load("CURRENT_RULES_AUTHORITY.json")
    assert receipt["effective_date"] == "2026-09-25"
    assert receipt["official_txt_sha256"] == (
        "8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca"
    )
    assert receipt["official_txt_bytes"] == 977752
    assert receipt["page_links_newer_than_2026_08_07"] is True
    assert receipt["rule_103_8a_exact_text"].startswith("103.8a In a two-player game")
    impact = receipt["qualification_relevant_rule_diff_2026_08_19_to_2026_09_25"][
        "full107_impact_adjudication"
    ]
    assert "SEMANTICS_CONFIRMED_STILL_CURRENT" in impact["WS05-CMD-START-2"]
    assert impact["contract_drift_classification"].startswith("NOT_SOURCE_CONTRACT_DRIFT")


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_full107_is_denominator_complete(candidate: str) -> None:
    results = _load(f"FULL107_{candidate}_RESULTS.json")
    assert results["total"] == DENOMINATOR
    assert len(results["rows"]) == DENOMINATOR
    assert set(results["counts"]) == OUTCOMES
    assert sum(results["counts"].values()) == DENOMINATOR
    assert results["evidence_class"] == "FRESH_CURRENT_BOUNDARY_EXECUTION"
    seen = set()
    for row in results["rows"]:
        assert row["fixture_id"] not in seen, row["fixture_id"]
        seen.add(row["fixture_id"])
        assert row["exit_state"] in OUTCOMES, row
        assert row["qualification_boundary"] == "commander-lab.pre-freeze-qualification/2.0.0"
        assert row["reason"], row
        if row["exit_state"] != "PASS":
            assert row["failure_reason"], row
        else:
            assert row["failure_reason"] is None, row
    for group in results["native_runs"].values():
        assert group["returncode"] == 0
        assert group["failures"] == 0 and group["errors"] == 0
        assert group["tests"] > 0


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_af01_is_current_boundary_and_exact_identity(candidate: str) -> None:
    af01 = _load(f"AF01_{candidate}.json")
    assert af01["boundary"] == "FRESH_CURRENT_BOUNDARY_EXECUTION"
    assert af01["transport_protocol"] == "2.0.0"
    assert af01["verdict"] in {"PASS", "FAIL", "UNKNOWN"}
    assert af01["invariant_count"] >= 20
    names = {item["invariant"] for item in af01["invariants"]}
    for required in (
        "canonical_handshake_start_engine",
        "canonical_handshake_get_provider_version",
        "canonical_handshake_get_capabilities",
        "protocol_version_exact",
        "request_id_matches",
        "provider_identity_exact",
        "engine_version_or_commit_exact",
        "capabilities_provider_reported_not_inferred",
        "fail_closed_protocol_mismatch",
        "fail_closed_unknown_message",
        "fail_closed_illegal_action",
        "fail_closed_stale_or_unknown_decision",
        "fail_closed_unsupported_decision",
    ):
        assert required in names, required
    # The successor current-boundary epoch binds the canonical live XMage pin
    # (config/rules_engines.json). The prior WSR22 pin stays accepted as a
    # documented historical epoch; the artifact is regenerated in place, so a
    # fresh run must name the live pin.
    from commander_lab.qualification.current_boundary.bridge_launcher import (
        canonical_xmage_engine_pin,
    )

    expected = {
        "XMAGE": {
            canonical_xmage_engine_pin(),
            "b19596980f2734496ea1896504253e1bdd2756dd",
        },
        "FORGE": {"ef958ee91ac6c9ce0152189f2654bf6e05abf273"},
    }[candidate]
    assert af01["engine_commit_reported"] in expected, (candidate, af01["engine_commit_reported"])


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_af_matrix_has_one_verdict_per_gate(candidate: str) -> None:
    matrix = _load(f"AF00_AF11_{candidate}.json")
    gates = [gate["gate"] for gate in matrix["gates"]]
    assert gates == GATES, gates
    for gate in matrix["gates"]:
        assert gate["verdict"] in {"PASS", "FAIL", "UNKNOWN"}, gate
        assert gate["evidence"], gate
        assert "blocking_rows" in gate and "nonblocking_limitations" in gate
    assert matrix["full107_counts"]["CRASH"] == 0
    assert matrix["full107_counts"]["TIMEOUT"] == 0
    assert matrix["full107_counts"]["PROTOCOL_FAILURE"] == 0


def test_comparison_classifies_every_row() -> None:
    comparison = _load("CURRENT_BOUNDARY_COMPARISON.json")
    assert comparison["denominator"] == DENOMINATOR
    assert len(comparison["rows"]) == DENOMINATOR
    for row in comparison["rows"]:
        assert row["disposition"] in DISPOSITIONS, row
        assert row["note"], row
        assert set(row["xmage"]) >= {"exit_state", "execution_mode"}
        assert set(row["forge"]) >= {"exit_state", "execution_mode"}
    assert sum(comparison["dispositions"].values()) == DENOMINATOR
    assert "game_id" in comparison["rows"][0]["engine_local_ids_excluded"]


def test_divergence_packet_has_no_unbacked_claim() -> None:
    packet = _load("DIVERGENCE_PACKET.json")
    assert packet["count"] == len(packet["ruled_visible_divergences"])
    for entry in packet["ruled_visible_divergences"]:
        for key in (
            "fixture",
            "xmage_identity",
            "forge_identity",
            "decision_tape",
            "rng_binding",
            "xmage_semantic_outcome",
            "forge_semantic_outcome",
            "minimal_reproduction",
            "official_rules_question",
        ):
            assert key in entry, key
    for fixture in packet["pending_rules_adjudication"]:
        row = next(
            r
            for r in _load("CURRENT_BOUNDARY_COMPARISON.json")["rows"]
            if r["fixture_id"] == fixture
        )
        assert row["disposition"] == "UNKNOWN_PENDING_RULES_ADJUDICATION", fixture


def test_provider_blockers_are_classified() -> None:
    blockers = _load("PROVIDER_BLOCKERS.json")
    assert blockers["blockers"]
    for entry in blockers["blockers"]:
        assert entry["classification"] in {
            "PROVIDER_BLOCKING",
            "BOUNDED_NON_BLOCKING",
            "UNKNOWN_IMPACT",
        }, entry
        assert entry["reason"], entry
        assert entry["smallest_remediation"], entry
        assert entry["affected_gates"], entry
    assert sum(blockers["counts"].values()) == len(blockers["blockers"])


def test_no_provider_ranking_language_in_analytical_packets() -> None:
    for name in RANKING_SCAN_PACKETS:
        path = OUT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").upper()
        for token in RANKING_TOKENS:
            assert token not in text, (name, token)


def test_terminal_states_remain_unclaimed() -> None:
    for name in ("AF00_AF11_XMAGE.json", "AF00_AF11_FORGE.json"):
        assert "PRODUCTION PROVIDER" not in (OUT / name).read_text(encoding="utf-8").upper()
