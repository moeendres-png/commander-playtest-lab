"""Final provider CDQ packet reconciliation (FINAL-PROVIDER-CDQ-20260927).

Guards the terminal evidence packet: refresh/normalization/targeted/
divergence/readiness must reconcile (107 rows, 101 common, 15 gaps, 38
dimensions), use only allowed evidence/comparison vocabularies, carry exact
pointers, emit no provider ranking, and preserve the six Forge residual
seams without remediation claims.
"""

from __future__ import annotations

import json
from pathlib import Path

PACKET_DIR = Path("docs/final_provider_adjudication_20260927")

REFRESH_ALLOWED = {
    "DIRECTLY_VERIFIED",
    "TECHNICALLY_CONFORMANT",
    "SUPPORTING",
    "CODE_DERIVED",
    "EXTERNALLY_RULE_VALIDATED",
    "UNKNOWN",
    "NOT_RUN_BLOCKED",
}

COMPARISON_ALLOWED = {
    "SAME_SEMANTICS",
    "NON_COMPARABLE",
    "ENGINE_CAPABILITY_GAP",
    "UNKNOWN_PENDING_RULES_ADJUDICATION",
}

READINESS_ALLOWED = {"DIRECT", "TECHNICALLY_CONFORMANT", "SUPPORTING", "BLOCKED", "UNKNOWN"}

SEAMS = {
    "HIDDEN_05",
    "HIDDEN_06",
    "HIDDEN_11",
    "HIDDEN_08",
    "HIDDEN_12",
    "WS05-CMD-MULL-2",
}

BANNED_RANKING_TOKENS = ("XMAGE_WIN", "FORGE_WIN", "BETTER_ENGINE", "PREFERRED_PROVIDER")


def _load(repo_root: Path, name: str) -> dict:
    return json.loads((repo_root / PACKET_DIR / name).read_text(encoding="utf-8"))


def test_refresh_reconciles_to_denominator(repo_root: Path) -> None:
    refresh = _load(repo_root, "XMAGE_FULL107_REFRESH.json")
    rows = refresh["rows"]
    assert len(rows) == 107, len(rows)
    assert refresh["denominator_identity"]["total_items"] == 107
    assert refresh["denominator_identity"]["frozen_source"] == (
        "5a2e4f462fd45bba25f2271153212aab9faf09f5"
    )
    counts = dict(refresh["result_counts"])
    assert sum(counts.values()) == 107, counts
    for row in rows:
        assert row["new_status"] in REFRESH_ALLOWED, row
        assert row["old_status"] in REFRESH_ALLOWED, row
        assert row["changed"] == (row["old_status"] != row["new_status"]), row
        assert row["why_promotion_is_valid_or_why_retained"], row
        assert row["impact_adjudication"], row
    # Mapping parity: refresh preserves the sealed mapping counts exactly.
    assert counts.get("DIRECTLY_VERIFIED", 0) == 15, counts
    assert counts.get("SUPPORTING", 0) == 13, counts
    assert counts.get("UNKNOWN", 0) == 54, counts
    assert counts.get("NOT_RUN_BLOCKED", 0) == 25, counts


def test_refresh_direct_rows_hold_exact_verdicts(repo_root: Path) -> None:
    refresh = _load(repo_root, "XMAGE_FULL107_REFRESH.json")
    for row in refresh["rows"]:
        if row["new_status"] == "DIRECTLY_VERIFIED":
            assert row["exact_evidence_pointer"], row
            assert row["identity_register_verdict"] == "EXACT", row
            assert "digest" in row["why_promotion_is_valid_or_why_retained"].lower() or (
                "digest" in (row["mapping_reason_preserved"] or "").lower()
            ), row


def test_normalization_is_101_common_without_seams(repo_root: Path) -> None:
    normalization = _load(repo_root, "COMMON_FIXTURE_NORMALIZATION.json")
    fixtures = normalization["fixtures"]
    assert normalization["fixture_count"] == 101, len(fixtures)
    assert len(fixtures) == 101
    ids = {f["fixture_id"] for f in fixtures}
    assert not (ids & SEAMS), ids & SEAMS
    excluded = {s["fixture_id"] for s in normalization["excluded_seams"]}
    assert excluded == SEAMS, excluded
    packet = json.loads((repo_root / PACKET_DIR / "wsr20-ingest"
                         / "COMMON_FIXTURE_SUCCESSOR_PACKET.json").read_text(encoding="utf-8"))
    packet_seed = {f["fixture_id"]: f.get("seed_request", 424242)
                   for f in packet["fixtures"]}
    counts = dict(normalization["comparison_counts"])
    assert sum(counts.values()) == 101, counts
    for key in counts:
        assert key in COMPARISON_ALLOWED, key
    for fixture in fixtures:
        assert fixture["comparison_disposition"] in COMPARISON_ALLOWED, fixture
        assert fixture["comparison_reason"], fixture
        assert fixture["seed_request"] == packet_seed[fixture["fixture_id"]], fixture
        record = fixture["comparison_record"]
        assert record["xmage_evidence"]["status"] in REFRESH_ALLOWED, fixture
        assert record["forge_evidence"]["status"] in REFRESH_ALLOWED, fixture
    # Finalized adjudicated split (both engines' evidence ingested).
    assert counts.get("SAME_SEMANTICS", 0) == 14, counts
    assert counts.get("NON_COMPARABLE", 0) == 62, counts
    assert counts.get("ENGINE_CAPABILITY_GAP", 0) == 25, counts
    assert counts.get("UNKNOWN_PENDING_RULES_ADJUDICATION", 0) == 0, counts


def test_gap_rows_are_xmage_injection_blocked(repo_root: Path) -> None:
    normalization = _load(repo_root, "COMMON_FIXTURE_NORMALIZATION.json")
    refresh = _load(repo_root, "XMAGE_FULL107_REFRESH.json")
    by_xm = {r["fixture_id"]: r["new_status"] for r in refresh["rows"]}
    gaps = [f for f in normalization["fixtures"]
            if f["comparison_disposition"] == "ENGINE_CAPABILITY_GAP"]
    assert len(gaps) == 25
    for fixture in gaps:
        assert by_xm[fixture["fixture_id"]] == "NOT_RUN_BLOCKED", fixture
        assert fixture["comparison_record"]["type"] == "capability_gap", fixture
    same = [f for f in normalization["fixtures"]
            if f["comparison_disposition"] == "SAME_SEMANTICS"]
    assert len(same) == 14
    for fixture in same:
        assert by_xm[fixture["fixture_id"]] == "DIRECTLY_VERIFIED", fixture
        assert fixture["comparison_record"]["forge_evidence"]["status"] in (
            "DIRECTLY_VERIFIED", "TECHNICALLY_CONFORMANT"), fixture


def test_wsr20_ingest_present_and_reconciled(repo_root: Path) -> None:
    ingest = repo_root / PACKET_DIR / "wsr20-ingest"
    for name in ("FULL107_FORGE_MAPPING.json",
                 "COMMON_FIXTURE_SUCCESSOR_PACKET.json",
                 "EXECUTION_RESULTS.json", "HIDDEN_INFO_RESULTS.json",
                 "RNG_REPLAY_RESULTS.json", "MULTIPLAYER_RESULTS.json"):
        assert (ingest / name).is_file(), name
    mapping = json.loads((ingest / "FULL107_FORGE_MAPPING.json").read_text(encoding="utf-8"))
    assert len(mapping["rows"]) == 107
    assert mapping["forge_head"] == "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
    assert mapping["counts"]["DIRECTLY_VERIFIED"] == 84
    assert mapping["counts"]["TECHNICALLY_CONFORMANT"] == 17
    assert mapping["counts"].get("FAIL", 0) == 0
    packet = json.loads((ingest / "COMMON_FIXTURE_SUCCESSOR_PACKET.json").read_text(encoding="utf-8"))
    assert len(packet["fixtures"]) == 101


def test_normalization_matches_refresh_xmage_status(repo_root: Path) -> None:
    refresh = _load(repo_root, "XMAGE_FULL107_REFRESH.json")
    normalization = _load(repo_root, "COMMON_FIXTURE_NORMALIZATION.json")
    by_fid = {r["fixture_id"]: r["new_status"] for r in refresh["rows"]}
    for fixture in normalization["fixtures"]:
        record = fixture["comparison_record"]
        assert record["xmage_evidence"]["status"] == by_fid[fixture["fixture_id"]], fixture


def test_targeted_gaps_ordered_and_bounded(repo_root: Path) -> None:
    targeted = _load(repo_root, "TARGETED_RUNTIME_RESULTS.json")
    gaps = targeted["gaps"]
    assert len(gaps) == 15, len(gaps)
    assert [g["rank"] for g in gaps] == list(range(15))
    assert gaps[0]["priority_dimension"].startswith("forge_packet_ingest"), gaps[0]
    assert gaps[0]["status"] == "COMPLETE", gaps[0]
    executions = targeted["gate_d_executions_performed"]
    assert executions, "Gate-D must record actually executed runs"
    forge_runs = [e for e in executions if e["kind"] == "forge-gate-d-denominator"]
    assert len(forge_runs) == 1, executions
    assert "31/31" in forge_runs[0]["result"], forge_runs[0]
    assert forge_runs[0]["mutation"] == "none (worktree clean, HEAD unchanged)"
    # Every gap fixture must belong to the 107 denominator.
    refresh = _load(repo_root, "XMAGE_FULL107_REFRESH.json")
    known = {r["fixture_id"] for r in refresh["rows"]} | {"ALL-101-COMMON"}
    for gap in gaps:
        assert gap["fixture_ids"], gap
        assert set(gap["fixture_ids"]) <= known, gap


def test_divergence_packet_compact_and_honest(repo_root: Path) -> None:
    divergence = _load(repo_root, "DIVERGENCE_PACKET.json")
    assert divergence["divergence_count"] == len(divergence["divergences"])
    for entry in divergence["divergences"]:
        for key in ("fixture_id", "xmage_observed_outcome", "forge_observed_outcome",
                    "rules_visible_delta", "candidate_official_rules_question"):
            assert key in entry, entry


def test_readiness_dimensions_complete_and_unranked(repo_root: Path) -> None:
    readiness = _load(repo_root, "PROVIDER_READINESS_PACKET.json")
    dims = readiness["dimensions"]
    assert len(dims) == 38, len(dims)
    assert readiness["terminal_states"]["ARCHITECTURE_FREEZE"] == "NOT CLAIMED"
    assert readiness["terminal_states"]["PRODUCTION_PROVIDER"] == "NOT SELECTED"
    assert "score" in readiness["scoring_disclaimer"].lower()
    for dim in dims:
        for side in ("xmage", "forge"):
            assert dim[side]["status"] in READINESS_ALLOWED, dim
            assert dim[side]["evidence_pointers"], dim


def test_no_provider_ranking_language_in_packets(repo_root: Path) -> None:
    names = ["XMAGE_FULL107_REFRESH.json", "COMMON_FIXTURE_NORMALIZATION.json",
             "TARGETED_RUNTIME_RESULTS.json", "DIVERGENCE_PACKET.json",
             "PROVIDER_READINESS_PACKET.json", "PROVIDER_READINESS_SUMMARY.md",
             "HIDDEN_INFO_COMPARISON.md", "RNG_REPLAY_COMPARISON.md",
             "MULTIPLAYER_COMPARISON.md", "FORBIDDEN_FALLBACK_COMPARISON.md",
             "FINAL_HANDOFF.md", "VALIDATION.md"]
    for name in names:
        text = (repo_root / PACKET_DIR / name).read_text(encoding="utf-8")
        for token in BANNED_RANKING_TOKENS:
            assert token not in text.upper(), (name, token)
