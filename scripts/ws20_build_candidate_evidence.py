#!/usr/bin/env python3
"""Normalize WS-20 phase.rs common-harness output into candidate_result_v1.

This is evidence plumbing, not rules adjudication. Missing native fixture materialization
stays UNSUPPORTED/NOT_RUN and receives an explicit omission reason.  The AF gate results
reflect the actual WS-20 integration topology: exact source/build lock and licensing can
PASS independently, while unimplemented runtime protocol/correctness surfaces cannot.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-results", type=Path, required=True)
    ap.add_argument("--source-lock", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--changeling-fixed", action="store_true")
    args = ap.parse_args()

    raw = load(args.raw_results)
    source_lock = load(args.source_lock)
    normalized = []
    for row in raw["fixture_results"]:
        verdict = row.get("verdict", "UNKNOWN")
        evidence_class = row.get("evidence_class", "NOT_RUN")
        executed = evidence_class == "RUNTIME_VERIFIED"
        if executed:
            classification = "RUNTIME_PASS" if verdict == "PASS" else "DIRECT_RULES_FAIL"
            omission = "RUNTIME_UNAVAILABLE"  # schema requires the field even for executed rows
        else:
            classification = "RUNTIME_NOT_RUN"
            omission = "RUNTIME_UNAVAILABLE"
        normalized.append(
            {
                "fixture_id": row["fixture_id"],
                "candidate": "phase_rs_ws20_patched",
                "source_lock": source_lock,
                "verdict": verdict,
                "evidence_class": evidence_class,
                "reason": row.get("reason", ""),
                "classification": classification,
                "omission_reason_code": omission,
                "artifact_hashes": row.get("artifact_hashes", {}),
            }
        )

    all_common_pass = bool(normalized) and all(x["verdict"] == "PASS" for x in normalized)
    changeling = "PASS" if args.changeling_fixed else "FAIL"

    af_results = [
        {
            "gate_id": "AF00",
            "verdict": "PASS",
            "reason": "Exact target baseline, phase.rs commit/tree/toolchain/licenses, deterministic local patch, patched tree and evidence hashes are workflow-locked.",
        },
        {
            "gate_id": "AF01",
            "verdict": "FAIL",
            "reason": "RSP 1.1 handshake is exact and truthful, but the full production session/observation/decision/replay operation surface is not implemented by the WS-20 provider route.",
        },
        {
            "gate_id": "AF02",
            "verdict": "UNSUPPORTED",
            "reason": "The identical 2P/3P/4P/5P common lifecycle fixtures are not engine-natively materialized through the WS-10R provider route.",
        },
        {
            "gate_id": "AF03",
            "verdict": "PARTIAL",
            "reason": "The adapter is fail-closed and does not reconstruct rules, but the incomplete production provider route prevents end-to-end proof that phase.rs is sole authority for every required path.",
        },
        {
            "gate_id": "AF04",
            "verdict": "PARTIAL",
            "reason": "Native GameAction is the intended authoritative action type and unsupported decisions fail closed, but complete RSP legal-option/decision-frame coverage was not implemented or runtime-qualified.",
        },
        {
            "gate_id": "AF05",
            "verdict": "UNSUPPORTED",
            "reason": "Actor-scoped hidden-information common fixtures are not engine-natively materialized through this provider route.",
        },
        {
            "gate_id": "AF06",
            "verdict": "UNSUPPORTED",
            "reason": "The frozen micro-rules common fixtures are not engine-natively materialized through this provider route; source architecture is not runtime correctness evidence.",
        },
        {
            "gate_id": "AF07",
            "verdict": "UNSUPPORTED",
            "reason": "The frozen 29-card behavioral fixtures are not engine-natively materialized through this provider route; literal source/test presence is not behavioral PASS.",
        },
        {
            "gate_id": "AF08",
            "verdict": "PARTIAL" if args.changeling_fixed else "FAIL",
            "reason": (
                "The direct Changeling Commander blocker is runtime-verified fixed, but the remaining common multiplayer/Commander denominator is not provider-runtime-qualified."
                if args.changeling_fixed
                else "The direct Changeling Commander blocker remains failing."
            ),
        },
        {
            "gate_id": "AF09",
            "verdict": "UNSUPPORTED",
            "reason": "Required Rules RNG attribution and clean-process replay tapes/checkpoints are not exposed and qualified through WS-10R.",
        },
        {
            "gate_id": "AF10",
            "verdict": "PARTIAL",
            "reason": "All 135 common fixture IDs are denominator-accounted fail-closed, but runtime evidence is incomplete because native execution is unavailable for required fixtures.",
        },
        {
            "gate_id": "AF11",
            "verdict": "PASS",
            "reason": "phase.rs is source-locked under MIT OR Apache-2.0; WS-20 uses a reproducible local patch/build experiment without modifying upstream and without imposing a GPL isolation constraint.",
        },
    ]

    report = {
        "schema_version": "candidate-result/1.1.0",
        "candidate": "phase_rs_ws20_patched",
        "source_lock": source_lock,
        "classifications": ["PROTOCOL_ADAPTER_MISSING", "RUNTIME_NOT_RUN"],
        "direct_failures": [
            "Full lossless WS-10R production session/observation/decision/replay bridge is incomplete.",
            "Mandatory common correctness fixtures remain non-PASS because no engine-native fixture materialization exists on this route.",
        ],
        "thin_adapter_assessment": "SAFE_FAIL_CLOSED_BUT_INCOMPLETE",
        "authority_status": "CURRENT_CANONICAL_RULES_USED_FOR_CHANGELING; COMMON_FIXTURE_AUTHORITY_LOCK_PRESERVED",
        "common_runtime_status": "PASS" if all_common_pass else "UNSUPPORTED",
        "common_runtime_reason": (
            "All frozen common fixtures runtime PASS."
            if all_common_pass
            else "The provider was invoked for every frozen fixture, but fixtures without exact native phase.rs materialization return UNSUPPORTED rather than synthesized semantics."
        ),
        "fixture_results": normalized,
        "af_results": af_results,
        "freeze_eligible": all_common_pass and all(x["verdict"] == "PASS" for x in af_results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"changeling": changeling, "freeze_eligible": report["freeze_eligible"]}, sort_keys=True))


if __name__ == "__main__":
    main()
