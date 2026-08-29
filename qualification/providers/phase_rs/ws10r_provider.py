#!/usr/bin/env python3
"""Fail-closed WS-10R transport for the WS-20 phase.rs candidate.

This process is deliberately not a second Rules Core. It never derives legality,
targets, costs, priority, or outcomes. For qualification fixtures, it only reports a
runtime result that was produced by an engine-native probe and written to the result
map by the WS-20 workflow. A fixture without such native evidence is UNSUPPORTED.

The production provider remains non-admitted until a native phase.rs session/decision
bridge can represent the complete RSP 1.1.0 surface losslessly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROTOCOL = "commander-lab.rules-service/1.1.0"
SOURCE_COMMIT = "bc218c51cec9cc2cec56f5c4de7c72be3d8e331c"


def emit(request: dict, payload: dict, message_type: str = "FIXTURE_RESULT") -> None:
    print(
        json.dumps(
            {
                "protocol": PROTOCOL,
                "message_type": message_type,
                "request_id": request.get("request_id"),
                "session_id": request.get("session_id"),
                "payload": payload,
            },
            sort_keys=True,
        )
    )


def load_runtime_map() -> dict:
    value = os.environ.get("WS20_RUNTIME_RESULT_MAP")
    if not value:
        return {}
    path = Path(value)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def main() -> int:
    line = sys.stdin.readline()
    if not line.strip():
        return 2
    try:
        request = json.loads(line)
    except Exception as exc:
        print(json.dumps({"protocol": PROTOCOL, "message_type": "ERROR", "payload": {"code": "MALFORMED_JSON", "detail": str(exc)}}))
        return 0

    if request.get("protocol") != PROTOCOL:
        emit(
            request,
            {
                "code": "PROTOCOL_MISMATCH",
                "expected": PROTOCOL,
                "received": request.get("protocol"),
            },
            "ERROR",
        )
        return 0

    message_type = request.get("message_type")
    if message_type == "HANDSHAKE":
        emit(
            request,
            {
                "candidate": "phase.rs-ws20-patched",
                "upstream_commit": SOURCE_COMMIT,
                "protocol": PROTOCOL,
                "production_capable": False,
                "native_action_authority": "phase_engine::types::actions::GameAction",
                "qualification_fixture_materialization": "engine-native-evidence-only",
                "unsupported_policy": "fail-closed",
            },
            "HANDSHAKE_RESULT",
        )
        return 0

    if message_type == "RUN_FIXTURE":
        fixture = request.get("payload", {}).get("fixture", {})
        fixture_id = fixture.get("fixture_id")
        runtime_map = load_runtime_map()
        result = runtime_map.get(fixture_id)
        if isinstance(result, dict):
            # The map is workflow-generated from engine-native execution.  Do not
            # reinterpret it here; transport exactly its adjudicated payload.
            emit(request, result)
            return 0
        emit(
            request,
            {
                "verdict": "UNSUPPORTED",
                "evidence_class": "NOT_RUN",
                "reason": (
                    "WS-20 has no engine-native materialization for this exact common fixture. "
                    "The adapter refuses to reconstruct rules state/actions or synthesize a PASS."
                ),
                "artifact_hashes": {},
            },
        )
        return 0

    # A full production RSP session bridge is not asserted by this workstream
    # unless the native engine route is actually implemented and runtime-qualified.
    emit(
        request,
        {
            "code": "UNSUPPORTED_OPERATION",
            "detail": (
                f"{message_type!r} is not implemented on the WS-20 qualification route; "
                "no fallback or internal AI is permitted"
            ),
        },
        "ERROR",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
