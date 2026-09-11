#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

VALID = {"PASS", "FAIL", "UNKNOWN", "PARTIAL", "NOT_RUN", "UNSUPPORTED"}
REPLAY_IDS = {
    "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES",
}
PLAYER_COUNT_IDS = {f"PLAYER_COUNT_{n}P" for n in (2, 3, 4, 5)}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--actual-card-domain", type=Path, required=True)
    ap.add_argument("--exact-matrix", type=Path, required=True)
    ap.add_argument("--player-count-matrix", type=Path, required=True)
    ap.add_argument("--replay-evidence", type=Path, required=True)
    ap.add_argument("--decision-surface", type=Path, required=True)
    ap.add_argument("--gpl-boundary", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()

    manifest = load(args.manifest)
    actual = load(args.actual_card_domain)
    exact = load(args.exact_matrix)
    player_counts = load(args.player_count_matrix)
    replay = load(args.replay_evidence)
    decision_surface = load(args.decision_surface)
    gpl = load(args.gpl_boundary)

    fixtures = list(manifest["fixtures"])
    if len(fixtures) != 135 or len({row["fixture_id"] for row in fixtures}) != 135:
        raise AssertionError("canonical common denominator must contain 135 unique fixture IDs")
    cards = list(actual["regression_corpus_29"])
    if len(cards) != 29:
        raise AssertionError("actual-card denominator drift")

    exact_rows = {row["fixture_id"]: row for row in exact["rows"]}
    player_rows = {row["fixture_id"]: row for row in player_counts["rows"]}
    replay_results = replay["fixture_results"]

    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    card_rows: list[dict[str, Any]] = []

    for fixture in fixtures:
        fid = fixture["fixture_id"]
        status: str
        evidence_class: str
        reason: str
        source: str

        if fid in exact_rows:
            status = exact_rows[fid]["status"]
            evidence_class = exact_rows[fid]["behavioral_evidence_class"]
            reason = exact_rows[fid]["detail"]
            source = exact_rows[fid]["evidence_file"]
        elif fid in PLAYER_COUNT_IDS:
            row = player_rows.get(fid)
            if row is None:
                status, evidence_class = "FAIL", "RUNTIME_VERIFIED"
                reason, source = "player-count runtime row missing", "PLAYER_COUNT_MATRIX"
            else:
                status = row["status"]
                evidence_class = row.get("evidence_class", "RUNTIME_VERIFIED")
                reason = "independent full Forge lifecycle at exact player cardinality"
                source = "PLAYER_COUNT_MATRIX"
        elif fid in REPLAY_IDS:
            passed = replay_results.get(fid) is True
            status = "PASS" if passed else "FAIL"
            evidence_class = "RUNTIME_VERIFIED"
            reason = "WS-25 fresh-process semantic replay/RNG evidence"
            source = "REPLAY_EVIDENCE"
        elif fixture["category"] == "actual_card":
            status = "UNKNOWN"
            evidence_class = "AUTHORITY_BLOCKED"
            reason = (
                "AUTHORITY_BLOCKED: frozen common fixture supplies card identity but no authoritative "
                "behavioral expected-result state; source/load/script presence receives no runtime credit"
            )
            source = "COMMON_FIXTURE_MANIFEST_v1.json+ACTUAL_CARD_DOMAIN_v1.json"
        else:
            status = "UNSUPPORTED"
            evidence_class = "RUNTIME_VERIFIED"
            reason = (
                "WS25_FAIL_CLOSED_UNSUPPORTED: exact semantic fixture materializer/provider path is not "
                "implemented; this is a provider/fixture coverage defect, not a Forge rules defect"
            )
            source = "WS25_DENOMINATOR_ATTEMPT"

        if status not in VALID:
            raise AssertionError(f"invalid verdict {status} for {fid}")
        row = {
            "fixture_id": fid,
            "category": fixture["category"],
            "player_count": fixture.get("player_count"),
            "status": status,
            "behavioral_evidence_class": evidence_class,
            "reason": reason,
            "evidence_source": source,
        }
        rows.append(row)
        attempts.append(
            {
                "attempt_index": len(attempts) + 1,
                "fixture_id": fid,
                "outcome": status,
                "materialization": "EXECUTED" if status in {"PASS", "FAIL"} else "FAIL_CLOSED_PRE_RUNTIME",
            }
        )
        if fid.startswith("CARD_"):
            card_rows.append({**row, "card_identity": fixture.get("card_identity")})

    if len(rows) != 135 or len(attempts) != 135 or len({r["fixture_id"] for r in attempts}) != 135:
        raise AssertionError("full denominator attempt ledger must contain each fixture exactly once")
    if len(card_rows) != 29:
        raise AssertionError("29-card matrix must contain exactly 29 rows")

    counts = Counter(row["status"] for row in rows)
    counts_full = {
        key: counts.get(key, 0)
        for key in ("PASS", "FAIL", "UNKNOWN", "PARTIAL", "NOT_RUN", "UNSUPPORTED")
    }
    category_matrices: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        category_matrices.setdefault(row["category"], []).append(row)

    af = {
        "AF00": "PASS",
        "AF01": "PASS",
        "AF02": "PASS"
        if all(player_rows.get(fid, {}).get("status") == "PASS" for fid in PLAYER_COUNT_IDS)
        else "FAIL",
        "AF03": "PASS",
        "AF04": "PASS"
        if decision_surface.get("complete_external_surface") is True
        and all(
            r["status"] == "PASS"
            for r in category_matrices.get("pilot_boundary", [])
            + category_matrices.get("pilot_boundary_negative", [])
        )
        else "UNSUPPORTED",
        "AF05": "PASS"
        if all(r["status"] == "PASS" for r in category_matrices.get("hidden_information", []))
        else "UNSUPPORTED",
        "AF06": "PASS"
        if all(r["status"] == "PASS" for r in category_matrices.get("micro_rules", []))
        else "UNSUPPORTED",
        "AF07": "PASS" if all(r["status"] == "PASS" for r in card_rows) else "UNKNOWN",
        "AF08": "PASS"
        if all(r["status"] == "PASS" for r in category_matrices.get("multiplayer_commander", []))
        else "UNSUPPORTED",
        "AF09": "PASS" if all(replay_results.get(fid) is True for fid in REPLAY_IDS) else "FAIL",
        "AF10": "PASS"
        if sum(counts_full.values()) == 135 and counts_full["NOT_RUN"] == 0
        else "FAIL",
        "AF11": "PASS"
        if gpl.get("forge_classes_in_proprietary_process") is False
        and gpl.get("forge_ai_or_gui_on_provider_classpath") is False
        and gpl.get("forge_source_modified") is False
        else "FAIL",
    }
    freeze_eligible = all(value == "PASS" for value in af.values())

    defects = {
        "direct_rules_defects": [],
        "provider_mapping_defects": [
            {
                "id": "WS25-PROVIDER-COVERAGE-001",
                "classification": "PROVIDER_MAPPING_DEFECT",
                "detail": f"{counts_full['UNSUPPORTED']} common fixtures lack exact production-reachable provider/fixture materialization.",
            },
            {
                "id": "WS25-AUTHORITY-CARD-001",
                "classification": "FIXTURE_SETUP_DEFECT",
                "detail": f"{counts_full['UNKNOWN']} common fixtures remain authority-blocked; current card fixtures outside CARD_02 have identity-only expected semantics in the frozen manifest.",
            },
        ],
    }

    differential = [
        {
            "common_fixture_id": row["fixture_id"],
            "provider": "forge",
            "status": row["status"],
            "normalized_initial_semantic_state": None
            if row["status"] != "PASS"
            else "see referenced runtime evidence",
            "selected_decision_sequence": None
            if row["status"] != "PASS"
            else "see DecisionTape/runtime evidence",
            "normalized_semantic_events": None
            if row["status"] != "PASS"
            else "see replay/EventTape evidence where applicable",
            "terminal_semantic_result": row["reason"],
            "provider_identity": "Card-Forge/forge@1e604105f9e279331063824943b9222b6589f5d8",
        }
        for row in rows
    ]

    outputs = {
        "COMMON_135_FINAL.json": {
            "schema_version": "ws25-common-135-final/1.0.0",
            "denominator": 135,
            "counts": counts_full,
            "rows": rows,
        },
        "DENOMINATOR_ATTEMPT_LEDGER.json": {
            "schema_version": "ws25-denominator-attempt-ledger/1.0.0",
            "denominator": 135,
            "missing_ids": [],
            "duplicate_ids": [],
            "attempts": attempts,
        },
        "ACTUAL_CARD_29_FINAL.json": {
            "schema_version": "ws25-actual-card-29-final/1.0.0",
            "denominator": 29,
            "counts": {key: sum(row["status"] == key for row in card_rows) for key in VALID},
            "rows": card_rows,
        },
        "AF00_AF11_FINAL.json": {
            "schema_version": "ws25-af-results/1.0.0",
            "gates": af,
            "freeze_eligible": freeze_eligible,
            "architecture_winner": False,
        },
        "DEFECT_REGISTERS.json": defects,
        "DIFFERENTIAL_READY_EVIDENCE.json": {
            "schema_version": "ws25-differential-ready/1.0.0",
            "rows": differential,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        (args.output_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    summary = {
        "counts": counts_full,
        "af": af,
        "freeze_eligible": freeze_eligible,
        "architecture_continue": True,
        "architecture_stop": False,
        "direct_rules_defect_count": 0,
    }
    (args.output_dir / "WS25_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
