#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys

PROTOCOL = "commander-lab.rules-service/1.1.0"


def fail(message: str, code: int) -> int:
    print(message, file=sys.stderr)
    return code


def main() -> int:
    command = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD", "").strip()
    if not command:
        return fail("COMMANDER_LAB_FORGE_PROVIDER_CMD is required; Forge provider absence fails closed", 64)

    raw = sys.stdin.read()
    if not raw.strip():
        return fail("empty WS-10R request", 65)
    try:
        request = json.loads(raw.splitlines()[-1])
    except Exception as exc:
        return fail(f"invalid WS-10R request JSON: {exc}", 65)
    if request.get("protocol") != PROTOCOL:
        return fail("request protocol is not commander-lab.rules-service/1.1.0", 66)
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return fail("request_id is required", 66)

    argv = shlex.split(command)
    if not argv:
        return fail("provider command parsed empty", 64)
    try:
        cp = subprocess.run(
            argv,
            input=json.dumps(request, separators=(",", ":")) + "\n",
            text=True,
            capture_output=True,
            timeout=float(os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_TIMEOUT_SECONDS", "120")),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return fail("Forge provider timed out", 70)
    if cp.returncode != 0:
        return fail(f"Forge provider exited {cp.returncode}: {cp.stderr.strip()}", 70)

    lines = [line for line in cp.stdout.splitlines() if line.strip()]
    if not lines:
        return fail("Forge provider produced no JSON response", 71)
    try:
        response = json.loads(lines[-1])
    except Exception as exc:
        return fail(f"Forge provider response is invalid JSON: {exc}", 71)
    if response.get("protocol") != PROTOCOL:
        return fail("Forge provider protocol mismatch", 72)
    if response.get("request_id") != request_id:
        return fail("Forge provider request_id mismatch", 72)
    payload = response.get("payload")
    if not isinstance(payload, dict):
        return fail("Forge provider payload must be an object", 72)

    # Transport/schema checks only: no legality, targeting, payment, ordering,
    # or observation content is created or changed on the proprietary side.
    sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
