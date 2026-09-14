#!/usr/bin/env python3
"""Consolidate WS-34 successor evidence into an exact 107-record terminal ledger.

This is an evidence combiner, not a rules engine. It grants successor runtime
credit only when the exact v1.0.2 record has a trustworthy independent provider
construction proof and a successful native semantic transaction. The current
XMage successor bridge does not independently reconstruct all 15 requested
state dimensions, so behavior-only or provider-request-echo results remain
credit-withheld and fail closed.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

CORE_IDS = {
    "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN", "WS05-CMD-MULL-2", "WS05-CMD-MULL-4", "PILOT_PRIORITY",
    "PILOT_TARGET",
}
TERMINAL_IDS = {
    "PILOT_TARGET_AMOUNT", "PILOT_CHOOSE_USE", "PILOT_ANNOUNCE_X", "PILOT_MULTI_AMOUNT",
    "PILOT_CHOOSE_MODE", "NEGATIVE_FIRST_OPTION", "NEGATIVE_RANDOM_OPTION",
    "NEGATIVE_GUI_DEFAULT", "NEGATIVE_SILENT_SKIP", "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES", "MICRO_TARGETS", "MICRO_MODES", "MICRO_TRIGGERS",
    "MICRO_CONTINUOUS_EFFECTS", "MICRO_LAYERS", "MICRO_STATE_BASED_ACTIONS", "CARD_02",
    "WS05-MP-TRIG-3", "WS05-MP-TRIG-5",
}

GATE_SELECTORS = {
    "AF04": ("LEGAL_ACTION_AND_DECISION_BOUNDARY", lambda fid: fid.startswith("PILOT_") or fid.startswith("NEGATIVE_"), 24),
    "AF05": ("HIDDEN_INFORMATION", lambda fid: fid.startswith("HIDDEN_"), 20),
    "AF06": ("GENERAL_RULES_CORRECTNESS", lambda fid: fid.startswith("MICRO_"), 17),
    "AF08": ("MULTIPLAYER_COMMANDER", lambda fid: fid.startswith("WS05-"), 36),
    "AF09": ("RNG_REPLAY", lambda fid: fid == "RNG_RULES_TAPE" or fid.startswith("REPLAY_"), 5),
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        fid = row.get("fixture_id")
        if not isinstance(fid, str) or not fid:
            raise AssertionError(f"{label}: row without fixture_id")
        if fid in out:
            raise AssertionError(f"{label}: duplicate fixture_id {fid}")
        out[fid] = row
    return out


def terminalize(pre: dict[str, Any], core: dict[str, dict[str, Any]], attempts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fid = pre["fixture_id"]
    row = {
        "fixture_id": fid,
        "fixture_family": pre["fixture_family"],
        "materialization_digest": pre["materialization_digest"],
        "requested_state_digest": pre["requested_state_digest"],
        "execution_entry_mode": pre["execution_entry_mode"],
        "decision_families": pre.get("decision_families", []),
        "pre_runtime_status": pre["pre_runtime_status"],
        "construction_blockers": pre.get("construction_blockers", []),
        "decision_blockers": pre.get("decision_blockers", []),
        "successor_runtime_credit": "NO",
    }
    if pre["pre_runtime_status"] != "READY_FOR_EXACT_RUNTIME_QUALIFICATION":
        row.update({
            "terminal_status": "UNSUPPORTED_CANONICAL_SETUP_OR_DECISION",
            "terminal_reason": "PRE_RUNTIME_FAIL_CLOSED_BLOCKER",
            "runtime_attempted": False,
        })
        return row
    if fid in CORE_IDS:
        runtime = core.get(fid)
        if runtime is None:
            raise AssertionError(f"missing core runtime row: {fid}")
        if runtime.get("record_digest") != pre["materialization_digest"]:
            raise AssertionError(f"core materialization digest mismatch: {fid}")
        row["runtime_attempted"] = True
        row["runtime_source"] = "SUCCESSOR_CORE_9"
        row["runtime_status"] = runtime.get("status")
        if runtime.get("error_type"):
            row["error_type"] = runtime.get("error_type")
            row["error"] = runtime.get("error")
        if runtime.get("status") == "PASS":
            row["terminal_status"] = "BEHAVIOR_PASS_CONSTRUCTION_PROOF_INSUFFICIENT"
            row["terminal_reason"] = "FULL_SUCCESSOR_STATE_NOT_INDEPENDENTLY_RECONSTRUCTED_FROM_NATIVE_XMAGE"
        else:
            row["terminal_status"] = "FAIL_CLOSED_RUNTIME"
            row["terminal_reason"] = "CORE_RUNTIME_TRANSACTION_FAILED_CLOSED"
        return row
    if fid in TERMINAL_IDS:
        runtime = attempts.get(fid)
        if runtime is None:
            raise AssertionError(f"missing terminal attempt row: {fid}")
        if runtime.get("record_digest") != pre["materialization_digest"]:
            raise AssertionError(f"terminal materialization digest mismatch: {fid}")
        row["runtime_attempted"] = True
        row["runtime_source"] = "TERMINAL_23"
        row["terminal_status"] = "FAIL_CLOSED_RUNTIME"
        row["terminal_reason"] = runtime.get("terminal_reason", "RUNTIME_ATTEMPT_FAILED_CLOSED")
        row["native_execution_entered"] = bool(runtime.get("native_execution_entered", False))
        row["first_decision_class"] = runtime.get("first_decision_class")
        if runtime.get("error_type"):
            row["error_type"] = runtime.get("error_type")
            row["error"] = runtime.get("error")
        if fid == "CARD_02":
            row["card02_cast_attempted"] = bool(runtime.get("card02_cast_attempted", False))
            row["card02_cast_option_submitted"] = bool(runtime.get("card02_cast_option_submitted", False))
            row["card02_behavior_result"] = runtime.get("card02_behavior_result")
        return row
    raise AssertionError(f"runtime-ready fixture is not partitioned into core9/terminal23: {fid}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", type=Path, required=True)
    ap.add_argument("--core", type=Path, required=True)
    ap.add_argument("--attempts", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    preflight = load(args.preflight)
    core_payload = load(args.core)
    attempt_payload = load(args.attempts)
    pre_rows = preflight["records"]
    if len(pre_rows) != 107 or preflight.get("ws34_denominator") != 107:
        raise AssertionError("WS34 denominator must be exactly 107")

    core = by_id(core_payload.get("records", []), "core")
    attempts = by_id(attempt_payload.get("records", []), "attempts")
    if set(core) != CORE_IDS:
        raise AssertionError(f"core-9 identity mismatch: {sorted(set(core) ^ CORE_IDS)}")
    if set(attempts) != TERMINAL_IDS:
        raise AssertionError(f"terminal-23 identity mismatch: {sorted(set(attempts) ^ TERMINAL_IDS)}")

    pre_by = by_id(pre_rows, "preflight")
    ready_ids = {fid for fid, row in pre_by.items() if row["pre_runtime_status"] == "READY_FOR_EXACT_RUNTIME_QUALIFICATION"}
    if ready_ids != CORE_IDS | TERMINAL_IDS:
        raise AssertionError(f"runtime-ready partition mismatch: {sorted(ready_ids ^ (CORE_IDS | TERMINAL_IDS))}")
    if len(ready_ids) != 32 or len(pre_by) - len(ready_ids) != 75:
        raise AssertionError("expected exact 32 runtime-ready / 75 setup-blocked split")

    rows = [terminalize(pre, core, attempts) for pre in pre_rows]
    final = by_id(rows, "final")
    if len(final) != 107:
        raise AssertionError("final ledger is not exactly 107 unique records")
    if any(row.get("successor_runtime_credit") != "NO" for row in rows):
        raise AssertionError("current WS34 evidence must not grant successor runtime credit")
    if any("terminal_status" not in row for row in rows):
        raise AssertionError("every WS34 row must be terminally classified")

    status_counts = Counter(row["terminal_status"] for row in rows)
    runtime_attempted = sum(bool(row["runtime_attempted"]) for row in rows)
    not_attempted = len(rows) - runtime_attempted
    if runtime_attempted != 32 or not_attempted != 75:
        raise AssertionError("terminal execution count mismatch")

    gate_results = []
    for gate_id, (name, selector, expected_denominator) in GATE_SELECTORS.items():
        members = [row for row in rows if selector(row["fixture_id"])]
        if len(members) != expected_denominator:
            raise AssertionError(f"{gate_id} denominator mismatch: {len(members)} != {expected_denominator}")
        passed = sum(row["successor_runtime_credit"] == "PASS" for row in members)
        unsupported = len(members) - passed
        gate_results.append({
            "gate_id": gate_id,
            "name": name,
            "denominator": len(members),
            "successor_runtime_pass": passed,
            "successor_runtime_unsupported": unsupported,
            "final_verdict": "PASS" if passed == len(members) else "UNSUPPORTED",
            "freeze_satisfying": passed == len(members),
            "historical_credit_imported": False,
            "evidence_basis": "commander-lab.semantic-fixture-materialization/1.0.2 only",
            "member_fixture_ids": [row["fixture_id"] for row in members],
        })

    card02 = final["CARD_02"]
    output = {
        "schema_version": "commander-lab.ws34-xmage-successor-final/1.0.0",
        "candidate": "XMAGE_WS34_SUCCESSOR_PROVIDER",
        "workstream_status": "COMPLETE",
        "candidate_qualification": "FAIL_NOT_QUALIFIED",
        "source_lock": {
            "provider_runtime_commit": os.environ.get("WS34_PROVIDER_COMMIT", core_payload.get("candidate_commit")),
            "provider_runtime_tree": os.environ.get("WS34_PROVIDER_TREE"),
            "ws32_freeze_commit": preflight["ws32_freeze_commit"],
            "ws32_freeze_tree": preflight["ws32_freeze_tree"],
            "ws32_validation_marker_commit": preflight["ws32_validation_marker_commit"],
            "materialization_version": preflight["contract_version"],
            "canonical_materialization_digest": preflight["canonical_materialization_digest"],
            "materialization_file_sha256": preflight["materialization_file_sha256"],
            "xmage_commit": preflight["xmage_commit"],
            "xmage_tree": preflight["xmage_tree"],
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        },
        "denominator": {"count": 107, "unique": 107, "runtime_ready": 32, "pre_runtime_blocked": 75},
        "terminal_counts": dict(sorted(status_counts.items())),
        "runtime_execution": {"attempted": runtime_attempted, "not_attempted_due_to_preflight_blocker": not_attempted},
        "successor_runtime_credit": {"PASS": 0, "NO_CREDIT": 107, "historical_pass_imported": False},
        "card_02": {
            "fixture_id": "CARD_02",
            "cast_attempted": card02.get("card02_cast_attempted", False),
            "cast_option_submitted": card02.get("card02_cast_option_submitted", False),
            "behavior_result": card02.get("card02_behavior_result"),
            "terminal_status": card02["terminal_status"],
            "terminal_reason": card02["terminal_reason"],
            "successor_runtime_credit": card02["successor_runtime_credit"],
            "error_type": card02.get("error_type"),
            "error": card02.get("error"),
        },
        "architecture_freeze": gate_results,
        "blocking_reasons": [
            "75/107 exact v1.0.2 records are not constructible by the current XMage qualification loader",
            "32/107 runtime-ready records were attempted but none receives successor runtime credit",
            "current successor full-state proof is not an independent reconstruction of all requested native state dimensions",
            "historical v1.0.1/WS26 PASS evidence is not imported into v1.0.2 successor credit",
        ],
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "workstream_status": output["workstream_status"],
        "candidate_qualification": output["candidate_qualification"],
        "terminal_counts": output["terminal_counts"],
        "card02": output["card_02"],
        "af": {row["gate_id"]: row["final_verdict"] for row in gate_results},
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
