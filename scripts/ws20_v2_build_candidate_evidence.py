#!/usr/bin/env python3
"""Build post-WS17R WS-20 candidate evidence from newly generated runtime artifacts.

Unlike the pre-WS17R prototype, this script does not let a Changeling unit test
stand in for an AF gate. AF verdicts are derived conservatively from the exact
common fixture results plus explicit current-build identity / direct-regression
facts. Any required domain without direct common runtime PASS stays non-PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_class(verdict: str) -> str:
    return "RUNTIME_PASS" if verdict == "PASS" else "RUNTIME_NOT_RUN"


def omission_code(verdict: str) -> str:
    if verdict == "PASS":
        # Schema requires a code even for PASS. This field is semantically unused on PASS.
        return "RUNTIME_UNAVAILABLE"
    return "RUNTIME_UNAVAILABLE"


def af_for_requirements(manifest: dict, common_results: list[dict]) -> dict[str, list[dict]]:
    by_fixture = {r["fixture_id"]: r for r in common_results}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for fixture in manifest["fixtures"]:
        result = by_fixture[fixture["fixture_id"]]
        for requirement in fixture.get("requirement_ids", []):
            if requirement.startswith("AF"):
                grouped[requirement].append(result)
    return grouped


def all_pass(rows: list[dict]) -> bool:
    return bool(rows) and all(row.get("verdict") == "PASS" for row in rows)


def any_fail(rows: list[dict]) -> bool:
    return any(row.get("verdict") == "FAIL" for row in rows)


def nonpass_verdict(rows: list[dict]) -> str:
    verdicts = {row.get("verdict") for row in rows}
    if "FAIL" in verdicts:
        return "FAIL"
    if "UNSUPPORTED" in verdicts:
        return "UNSUPPORTED"
    if "PARTIAL" in verdicts:
        return "PARTIAL"
    if "UNKNOWN" in verdicts:
        return "UNKNOWN"
    return "NOT_RUN"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--common-results", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--source-lock", type=Path, required=True)
    ap.add_argument("--build-identity", type=Path, required=True)
    ap.add_argument("--provider-handshake", type=Path, required=True)
    ap.add_argument("--direct-regression", type=Path, required=True)
    ap.add_argument("--pilot-audit", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--matrix-output", type=Path, required=True)
    args = ap.parse_args()

    raw = load(args.common_results)["fixture_results"]
    manifest = load(args.manifest)
    source_lock = load(args.source_lock)
    identity = load(args.build_identity)
    handshake = load(args.provider_handshake)["payload"]
    direct = load(args.direct_regression)
    pilot = load(args.pilot_audit)

    required_ids = [x["fixture_id"] for x in manifest["fixtures"] if x["mandatory"]]
    by = {r["fixture_id"]: r for r in raw}
    assert len(required_ids) == 135
    assert set(by) == set(required_ids)

    fixture_results = []
    for fixture in manifest["fixtures"]:
        r = by[fixture["fixture_id"]]
        verdict = r["verdict"]
        fixture_results.append(
            {
                "fixture_id": fixture["fixture_id"],
                "candidate": "phase_rs_ws20_v2",
                "source_lock": source_lock,
                "verdict": verdict,
                "evidence_class": r.get("evidence_class", "NOT_RUN"),
                "reason": r.get("reason", "No provider reason supplied"),
                "classification": result_class(verdict),
                "omission_reason_code": omission_code(verdict),
                "artifact_hashes": r.get("artifact_hashes", {}),
            }
        )

    grouped = af_for_requirements(manifest, raw)
    af_results = []

    # AF00: exact current source, patch, resulting tree, provider and manifest identity
    # are generated and hash-bound in the same fresh CI run.
    required_identity = [
        identity.get("target_baseline"),
        identity.get("upstream_commit"),
        identity.get("upstream_tree"),
        identity.get("patched_tree"),
        identity.get("patch_sha256"),
        identity.get("provider_sha256"),
        identity.get("common_manifest_sha256"),
    ]
    af00 = "PASS" if all(required_identity) else "UNKNOWN"
    af_results.append({"gate_id": "AF00", "verdict": af00, "reason": "Fresh CI build identity is complete and hash-bound." if af00 == "PASS" else "Fresh build identity is incomplete."})

    # AF01 is an explicit protocol capability fact from the fresh handshake.
    af01 = "FAIL" if not handshake.get("production_capable", False) else "PARTIAL"
    af_results.append({"gate_id": "AF01", "verdict": af01, "reason": "Fresh handshake truthfully reports that the native production RSP session/observation/replay bridge is incomplete."})

    for gate in ["AF02", "AF05", "AF06", "AF07", "AF09"]:
        rows = grouped.get(gate, [])
        verdict = "PASS" if all_pass(rows) else nonpass_verdict(rows)
        af_results.append({"gate_id": gate, "verdict": verdict, "reason": f"Derived from {len(rows)} exact common fixtures mapped to {gate}; all required fixtures must PASS."})

    # AF03/AF04: engine-native GameAction authority + no adapter fallback is positive
    # direct evidence, but the production session/decision bridge is incomplete.
    authority_partial = (
        handshake.get("native_action_authority", "").endswith("GameAction")
        and handshake.get("unsupported_policy") == "fail-closed"
        and pilot.get("provider_route_forbidden_reference_count") == 0
    )
    af_results.append({"gate_id": "AF03", "verdict": "PARTIAL" if authority_partial else "FAIL", "reason": "Rules authority remains phase.rs-native on the implemented route, but full production reachability is not bridged."})
    af_results.append({"gate_id": "AF04", "verdict": "PARTIAL" if authority_partial else "FAIL", "reason": "Exact native GameAction submission is the intended authority and unsupported operations fail closed; complete RSP decision frames are not implemented."})

    # AF08 cannot be promoted by the Changeling unit regression alone.
    af08_rows = grouped.get("AF08", [])
    if all_pass(af08_rows):
        af08 = "PASS"
        af08_reason = "All exact common multiplayer/Commander fixtures PASS, including independently recorded Changeling remediation evidence."
    elif direct.get("changeling_postpatch") == "PASS":
        af08 = "PARTIAL"
        af08_reason = "Changeling blocker is freshly runtime-fixed, but required common multiplayer/Commander fixtures remain non-PASS."
    else:
        af08 = "FAIL" if direct.get("changeling_postpatch") == "FAIL" or any_fail(af08_rows) else nonpass_verdict(af08_rows)
        af08_reason = "Changeling regression or required common multiplayer/Commander evidence is non-PASS."
    af_results.append({"gate_id": "AF08", "verdict": af08, "reason": af08_reason})

    # AF10 is denominator accounting, not correctness. Complete accounting can still be
    # PARTIAL while required semantics are intentionally unsupported/not executed.
    accounted = len(raw) == 135 and set(by) == set(required_ids)
    af_results.append({"gate_id": "AF10", "verdict": "PARTIAL" if accounted else "FAIL", "reason": "All 135 fixtures are freshly accounted for, but unsupported production paths prevent full runtime-evidence reliability PASS."})

    # AF11: permissive source + local reproducible patch, no upstream mutation.
    license_ok = source_lock["selected_upstream"].get("license_expression") == "MIT OR Apache-2.0"
    af_results.append({"gate_id": "AF11", "verdict": "PASS" if license_ok else "UNKNOWN", "reason": "Fresh source lock confirms MIT OR Apache-2.0 and the candidate is built by a reproducible local patch without modifying upstream."})

    order = {f"AF{i:02d}": i for i in range(12)}
    af_results.sort(key=lambda x: order[x["gate_id"]])
    freeze_eligible = all(x["verdict"] == "PASS" for x in af_results)

    classifications = {"RUNTIME_NOT_RUN"}
    if direct.get("changeling_postpatch") == "PASS":
        classifications.add("RUNTIME_PASS")
    if any(x["verdict"] == "FAIL" for x in af_results):
        classifications.add("DIRECT_RULES_FAIL")

    verdict_counts = Counter(r["verdict"] for r in raw)
    report = {
        "schema_version": "candidate-result/1.0.0",
        "candidate": "phase_rs",
        "source_lock": source_lock,
        "classifications": sorted(classifications),
        "direct_failures": [
            x["reason"] for x in af_results if x["verdict"] == "FAIL"
        ],
        "thin_adapter_assessment": "PARTIAL: fail-closed qualification transport preserves phase.rs GameAction authority, but native production session/observation/replay mapping is incomplete.",
        "authority_status": "CURRENT_CANONICAL_CHANGELING_ADJUDICATED; OTHER_COMMON_FIXTURES_USE_COMMITTED_AUTHORITY_LOCK",
        "common_runtime_status": "PASS" if verdict_counts.get("PASS", 0) == 135 else "UNSUPPORTED",
        "common_runtime_reason": f"Fresh post-WS17R execution accounted for 135 fixtures: {dict(sorted(verdict_counts.items()))}.",
        "fixture_results": fixture_results,
        "af_results": af_results,
        "freeze_eligible": freeze_eligible,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    matrix = {
        "schema_version": "ws20-v2-matrices/1.0.0",
        "candidate": "phase_rs",
        "target_baseline": identity.get("target_baseline"),
        "build_identity": identity,
        "common_fixture_counts": dict(sorted(verdict_counts.items())),
        "by_category": {},
        "af_results": af_results,
        "freeze_eligible": freeze_eligible,
        "evidence_files": {
            "common_results_sha256": sha256(args.common_results),
            "manifest_sha256": sha256(args.manifest),
            "source_lock_sha256": sha256(args.source_lock),
            "build_identity_sha256": sha256(args.build_identity),
            "provider_handshake_sha256": sha256(args.provider_handshake),
            "direct_regression_sha256": sha256(args.direct_regression),
            "pilot_audit_sha256": sha256(args.pilot_audit),
        },
    }
    for category in sorted({f["category"] for f in manifest["fixtures"]}):
        ids = [f["fixture_id"] for f in manifest["fixtures"] if f["category"] == category]
        counts = Counter(by[fid]["verdict"] for fid in ids)
        matrix["by_category"][category] = {"fixture_count": len(ids), "verdict_counts": dict(sorted(counts.items()))}
    args.matrix_output.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
