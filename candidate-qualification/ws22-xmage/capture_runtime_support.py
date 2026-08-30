#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shlex
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.full_game import _RawFullGameClient

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "qualification/evidence/ws22-xmage/RUNTIME_SUPPORT_EVIDENCE.json"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
RELEVANT_SUITES = (
    "XmageFullGamePlayerBoundaryTest",
    "XmageAuditSurfaceRedactorTest",
    "XmageDecisionOptionIdentityTest",
    "XmageFullGameObservationGatewayTest",
    "XmageFullGameBridgeContractTest",
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _bridge_command() -> tuple[str, ...]:
    raw = os.environ.get("COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD", "").strip()
    if not raw:
        raise RuntimeError("XMAGE_BRIDGE_NOT_CONFIGURED")
    return tuple(shlex.split(raw))


def _suite_summary(name: str) -> dict[str, Any]:
    path = ROOT / "engine-bridge/target/surefire-reports" / f"TEST-org.commanderlab.xmage.{name}.xml"
    if not path.is_file():
        return {"present": False, "passed": False, "path": str(path.relative_to(ROOT))}
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    tests = int(root.attrib.get("tests", "0"))
    failures = int(root.attrib.get("failures", "0"))
    errors = int(root.attrib.get("errors", "0"))
    skipped = int(root.attrib.get("skipped", "0"))
    return {
        "present": True,
        "passed": tests > 0 and failures == 0 and errors == 0,
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "path": str(path.relative_to(ROOT)),
    }


def main() -> int:
    with _RawFullGameClient(
        _bridge_command(),
        cwd=ROOT,
        request_timeout_seconds=120.0,
    ) as client:
        started = client.request("start_engine")
        if started.get("lane") != "xmage_full_game_external_pilots":
            raise RuntimeError("bridge did not enter full-game lane")
        provider = client.request("get_provider_version")
        if provider.get("engine_commit") != XMAGE_COMMIT:
            raise RuntimeError("XMAGE_BUILD_IDENTITY_MISMATCH")
        capability_response = client.request("get_capabilities")

    capabilities = capability_response.get("capabilities")
    lane = capability_response.get("full_game_lane")
    if not isinstance(capabilities, dict) or not isinstance(lane, dict):
        raise RuntimeError("runtime capability payload incomplete")

    suites = {name: _suite_summary(name) for name in RELEVANT_SUITES}
    payload: dict[str, Any] = {
        "schema_version": "ws22-runtime-support-evidence/1.0.0",
        "github_sha": os.environ.get("GITHUB_SHA", "UNRESOLVED_OUTSIDE_CI"),
        "xmage_commit": XMAGE_COMMIT,
        "runtime_started": started,
        "provider": provider,
        "capabilities": capabilities,
        "full_game_lane": lane,
        "bridge_test_suites": suites,
    }
    payload["evidence_sha256"] = _sha256(payload)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "evidence_sha256": payload["evidence_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
