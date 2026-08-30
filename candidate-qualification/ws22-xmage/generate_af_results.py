#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"
RESULTS_PATH = ROOT / "qualification/evidence/ws22-xmage/COMMON_RESULTS.json"
RUNTIME_PATH = ROOT / "qualification/evidence/ws22-xmage/RUNTIME_SUPPORT_EVIDENCE.json"
SOURCE_LOCK_PATH = ROOT / "candidate-qualification/ws22-xmage/WS22_SOURCE_LOCK.json"
CATALOG_PATH = ROOT / "qualification/protocol/ws10r/architecture_freeze_gate_catalog_v1.json"
SCHEMA_PATH = ROOT / "qualification/protocol/ws10r/architecture_freeze_contract_v1.schema.json"
OUTPUT_PATH = ROOT / "qualification/evidence/ws22-xmage/AF_RESULTS.json"
SUMMARY_PATH = ROOT / "qualification/evidence/ws22-xmage/AF_RESULTS.md"

PROTOCOL = "commander-lab.rules-service/1.1.0"
CANDIDATE = "XMAGE_WS22"
WS18_HEAD = "b48c5ff3e54b492f172760d66a669156b85bc037"
WS18_TREE = "079288a2117b58c43bf546531f3baa98d14b8abf"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
XMAGE_TREE = "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"
XMAGE_POM_BLOB = "510aa402b6bb7abce96b9a89e5471b016ba4134c"
XMAGE_LICENSE_BLOB = "3575e469d848ca405ccc8d0ac9d711c94120eb45"
COMMON_MANIFEST_SHA256 = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"
BLOCKING_PRECEDENCE = ("FAIL", "UNSUPPORTED", "PARTIAL", "NOT_RUN", "UNKNOWN", "NOT_APPLICABLE")


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return data


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _mapped_gate_verdict(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "UNKNOWN"
    verdicts = [str(row.get("verdict", "UNKNOWN")) for row in rows]
    if all(verdict == "PASS" for verdict in verdicts):
        return "PASS"
    for verdict in BLOCKING_PRECEDENCE:
        if verdict in verdicts:
            return verdict
    return "UNKNOWN"


def _source_lock_gate(
    source_lock: dict[str, Any], runtime: dict[str, Any]
) -> tuple[str, str, list[str]]:
    checks: dict[str, bool] = {}
    try:
        checks = {
            "ws18_ancestor": subprocess.run(
                ["git", "merge-base", "--is-ancestor", WS18_HEAD, "HEAD"],
                cwd=ROOT,
                check=False,
            ).returncode
            == 0,
            "ws18_tree": _git("rev-parse", f"{WS18_HEAD}^{{tree}}") == WS18_TREE,
            "xmage_commit": _git("rev-parse", "HEAD", cwd=ROOT / "vendor/engine-source/xmage")
            == XMAGE_COMMIT,
            "xmage_tree": _git("rev-parse", "HEAD^{tree}", cwd=ROOT / "vendor/engine-source/xmage")
            == XMAGE_TREE,
            "xmage_pom_blob": _git(
                "rev-parse", "HEAD:pom.xml", cwd=ROOT / "vendor/engine-source/xmage"
            )
            == XMAGE_POM_BLOB,
            "xmage_license_blob": _git(
                "rev-parse", "HEAD:LICENSE.txt", cwd=ROOT / "vendor/engine-source/xmage"
            )
            == XMAGE_LICENSE_BLOB,
            "common_manifest_sha256": _sha256_file(MANIFEST_PATH) == COMMON_MANIFEST_SHA256,
            "lock_protocol": source_lock.get("protocol", {}).get("id") == PROTOCOL,
            "lock_denominator": source_lock.get("protocol", {}).get("denominator_count") == 135,
            "runtime_xmage_commit": runtime.get("xmage_commit") == XMAGE_COMMIT,
        }
    except (OSError, subprocess.SubprocessError):
        return (
            "FAIL",
            "Exact source/build lock verification raised an execution error.",
            [
                "WS22_SOURCE_LOCK.json",
                "RUNTIME_SUPPORT_EVIDENCE.json",
            ],
        )
    verdict = "PASS" if checks and all(checks.values()) else "FAIL"
    failed = sorted(name for name, passed in checks.items() if not passed)
    reason = (
        "Exact WS-18 ancestry/tree, pinned XMage commit/tree/POM/license blobs, protocol and unchanged 135 denominator were reverified on the qualification head."
        if verdict == "PASS"
        else "Exact source/build lock verification failed: " + ", ".join(failed)
    )
    return verdict, reason, ["WS22_SOURCE_LOCK.json", "RUNTIME_SUPPORT_EVIDENCE.json"]


def _protocol_gate(runtime: dict[str, Any]) -> tuple[str, str, list[str]]:
    hello = runtime.get("rsp_hello")
    if not isinstance(hello, dict):
        return (
            "FAIL",
            "Exact RSP HELLO runtime evidence is missing.",
            ["RUNTIME_SUPPORT_EVIDENCE.json"],
        )
    payload = hello.get("payload")
    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    ok = (
        hello.get("protocol") == PROTOCOL
        and hello.get("message_type") == "HELLO_RESPONSE"
        and isinstance(metadata, dict)
        and metadata.get("protocol_version") == PROTOCOL
        and metadata.get("engine_source_commit") == XMAGE_COMMIT
        and metadata.get("supported_player_counts") == [2, 3, 4, 5]
        and metadata.get("typed_fail_closed") is True
    )
    return (
        "PASS" if ok else "FAIL",
        "Exact RSP 1.1 HELLO response and truthful provider metadata were executed and verified."
        if ok
        else "RSP 1.1 HELLO response or required provider metadata did not match the frozen contract.",
        ["RUNTIME_SUPPORT_EVIDENCE.json#rsp_hello"],
    )


def _rules_authority_gate(runtime: dict[str, Any]) -> tuple[str, str, list[str]]:
    hello = runtime.get("rsp_hello", {})
    payload = hello.get("payload", {}) if isinstance(hello, dict) else {}
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    suites = runtime.get("bridge_test_suites", {})
    boundary = suites.get("XmageFullGamePlayerBoundaryTest", {}) if isinstance(suites, dict) else {}
    ok = (
        isinstance(metadata, dict)
        and metadata.get("rules_authority") == "xmage"
        and metadata.get("decision_authority") == "external_rsp_client"
        and metadata.get("observation_authority") == "xmage_knowledge_ledger"
        and metadata.get("typed_fail_closed") is True
        and isinstance(boundary, dict)
        and boundary.get("passed") is True
    )
    return (
        "PASS" if ok else "FAIL",
        "Runtime RSP metadata assigns rules authority to XMage and discretion to the external client; the exact-head compiled discretionary-callback boundary suite passed."
        if ok
        else "Rules/pilot authority separation was not completely demonstrated by the exact-head runtime and boundary suite.",
        [
            "RUNTIME_SUPPORT_EVIDENCE.json#rsp_hello",
            "RUNTIME_SUPPORT_EVIDENCE.json#bridge_test_suites/XmageFullGamePlayerBoundaryTest",
        ],
    )


def _reliability_gate(
    manifest: dict[str, Any], results: dict[str, Any], runtime: dict[str, Any]
) -> tuple[str, str, list[str]]:
    fixtures = manifest.get("fixtures")
    rows = results.get("fixture_results")
    if not isinstance(fixtures, list) or not isinstance(rows, list):
        return "FAIL", "Denominator or result rows are missing.", ["COMMON_RESULTS.json"]
    expected_ids = [str(item.get("fixture_id")) for item in fixtures if isinstance(item, dict)]
    result_ids = [str(item.get("fixture_id")) for item in rows if isinstance(item, dict)]
    verdicts = Counter(
        str(item.get("verdict", "UNKNOWN")) for item in rows if isinstance(item, dict)
    )
    evidence_ok = all(
        isinstance(item, dict) and item.get("evidence_class") == "RUNTIME_VERIFIED" for item in rows
    )
    ok = (
        len(expected_ids) == 135
        and len(set(expected_ids)) == 135
        and len(result_ids) == 135
        and len(set(result_ids)) == 135
        and set(result_ids) == set(expected_ids)
        and verdicts.get("NOT_RUN", 0) == 0
        and verdicts.get("UNKNOWN", 0) == 0
        and verdicts.get("PARTIAL", 0) == 0
        and evidence_ok
        and runtime.get("github_sha") == os.environ.get("GITHUB_SHA", "UNRESOLVED_OUTSIDE_CI")
    )
    reason = (
        "All 135 frozen fixtures are present exactly once with terminal runtime evidence accounting and no NOT_RUN/UNKNOWN/PARTIAL gaps."
        if ok
        else "The exact 135-fixture runtime evidence set is incomplete, duplicated, non-runtime, or contains unresolved verdicts."
    )
    return (
        "PASS" if ok else "FAIL",
        reason,
        ["COMMON_RESULTS.json", "RUNTIME_SUPPORT_EVIDENCE.json"],
    )


def _interop_gate(
    source_lock: dict[str, Any], runtime: dict[str, Any]
) -> tuple[str, str, list[str]]:
    capabilities = runtime.get("capabilities")
    lane = runtime.get("full_game_lane")
    license_path = ROOT / "vendor/engine-source/xmage/LICENSE.txt"
    license_ok = (
        license_path.is_file()
        and _sha256_file(license_path) == hashlib.sha256(license_path.read_bytes()).hexdigest()
        and license_path.read_text(encoding="utf-8").startswith("MIT License")
        and _git("rev-parse", "HEAD:LICENSE.txt", cwd=ROOT / "vendor/engine-source/xmage")
        == XMAGE_LICENSE_BLOB
    )
    target_license_ok = "LicenseRef-Proprietary" in (ROOT / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    ok = (
        license_ok
        and target_license_ok
        and source_lock.get("xmage", {}).get("license_blob") == XMAGE_LICENSE_BLOB
        and isinstance(capabilities, dict)
        and capabilities.get("runtime_kind") == "external_rules_engine"
        and isinstance(lane, dict)
        and lane.get("one_game_per_process") is True
    )
    return (
        "PASS" if ok else "FAIL",
        "Pinned XMage is MIT-licensed and the actual qualification integration is an isolated external rules-engine JVM while the target remains proprietary."
        if ok
        else "Pinned license identity or actual external-process integration topology did not satisfy the WS-09 boundary.",
        [
            "WS22_SOURCE_LOCK.json",
            "RUNTIME_SUPPORT_EVIDENCE.json#capabilities",
            "vendor/engine-source/xmage/LICENSE.txt",
            "pyproject.toml",
        ],
    )


def main() -> int:
    manifest = _load(MANIFEST_PATH)
    results = _load(RESULTS_PATH)
    runtime = _load(RUNTIME_PATH)
    source_lock = _load(SOURCE_LOCK_PATH)
    catalog = _load(CATALOG_PATH)
    schema = _load(SCHEMA_PATH)

    rows = results.get("fixture_results")
    fixtures = manifest.get("fixtures")
    if not isinstance(rows, list) or not isinstance(fixtures, list):
        raise RuntimeError("COMMON_RESULTS or manifest fixture array missing")
    row_by_id = {
        str(row["fixture_id"]): row for row in rows if isinstance(row, dict) and "fixture_id" in row
    }

    gate_results: list[dict[str, Any]] = []
    for gate in catalog.get("gates", []):
        if not isinstance(gate, dict):
            continue
        gate_id = str(gate.get("id"))
        if gate_id == "AF00":
            verdict, reason, refs = _source_lock_gate(source_lock, runtime)
        elif gate_id == "AF01":
            verdict, reason, refs = _protocol_gate(runtime)
        elif gate_id == "AF03":
            verdict, reason, refs = _rules_authority_gate(runtime)
        elif gate_id == "AF10":
            verdict, reason, refs = _reliability_gate(manifest, results, runtime)
        elif gate_id == "AF11":
            verdict, reason, refs = _interop_gate(source_lock, runtime)
        else:
            mapped_ids = [
                str(fixture.get("fixture_id"))
                for fixture in fixtures
                if isinstance(fixture, dict) and gate_id in fixture.get("requirement_ids", [])
            ]
            mapped_rows = [
                row_by_id[fixture_id] for fixture_id in mapped_ids if fixture_id in row_by_id
            ]
            verdict = _mapped_gate_verdict(mapped_rows)
            counts = Counter(str(row.get("verdict", "UNKNOWN")) for row in mapped_rows)
            reason = (
                f"Derived from {len(mapped_ids)} frozen mandatory fixtures mapped to {gate_id}; "
                + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
                + ". PASS is the only satisfying verdict."
            )
            refs = [f"COMMON_RESULTS.json#{fixture_id}" for fixture_id in mapped_ids]
        gate_results.append(
            {
                "gate_id": gate_id,
                "verdict": verdict,
                "evidence_refs": refs,
                "reason": reason,
            }
        )

    if [item["gate_id"] for item in gate_results] != [f"AF{index:02d}" for index in range(12)]:
        raise RuntimeError("AF catalog did not yield exact AF00-AF11 ordering")

    output: dict[str, Any] = {
        "schema_version": "architecture-freeze-result/1.1.0",
        "protocol": PROTOCOL,
        "candidate": CANDIDATE,
        "source_lock": {
            "ws22_source_lock": source_lock,
            "evidence_github_sha": runtime.get("github_sha"),
            "common_manifest_sha256": _sha256_file(MANIFEST_PATH),
            "common_results_sha256": _sha256_file(RESULTS_PATH),
            "runtime_support_sha256": _sha256_file(RUNTIME_PATH),
        },
        "gate_results": gate_results,
        "freeze_eligible": all(item["verdict"] == "PASS" for item in gate_results),
        "architecture_winner": False,
    }
    Draft202012Validator(schema).validate(output)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# WS-22 XMage AF00-AF11",
        "",
        f"Freeze eligible: **{str(output['freeze_eligible']).upper()}**",
        "",
        "| Gate | Verdict | Reason |",
        "|---|---|---|",
    ]
    for item in gate_results:
        lines.append(f"| {item['gate_id']} | {item['verdict']} | {item['reason']} |")
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"freeze_eligible": output["freeze_eligible"], "gate_results": gate_results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
