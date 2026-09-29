"""PB-09 pristine-upstream Forge runtime smoke.

Launches the transplanted Lab Protocol-2 bridge inside the PRISTINE upstream
checkout (engine byte-identical to a37a865a) and performs the identity/handshake
requests. Captures the exact request/response transcript as evidence.

This proves (or refutes) PRISTINE_FORGE_RUNTIME_REACHABLE at the process +
handshake + capability level. It grants no FULL107 row credit.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

WS = pathlib.Path("/home/moeen/code/csn-final-bakeoff/muse/forge-upstream-pristine")
MODULE = WS / "forge-protocol2-bridge"
CP = (MODULE / "target/cp-wsr22.txt").read_text().strip()
CLASSES = str(MODULE / "target/classes")
ENGINE_SHA = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"

env = dict(os.environ)
env.update(
    {
        "FORGE_ENGINE_SHA": ENGINE_SHA,
        "FORGE_ASSETS_DIR": str(WS / "forge-gui"),
        "JAVA_TOOL_OPTIONS": "",
    }
)

proc = subprocess.Popen(
    [
        "java",
        "-cp",
        f"{CLASSES}:{CP}",
        "forge.bridge.BridgeMain",
    ],
    cwd=str(WS),
    env=env,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)

requests = [
    {"request_id": "smoke-1", "protocol_version": "2.0.0", "message_type": "start_engine",
     "payload": {}},
    {"request_id": "smoke-2", "protocol_version": "2.0.0", "message_type": "get_capabilities",
     "payload": {}},
    {"request_id": "smoke-3", "protocol_version": "2.0.0",
     "message_type": "get_provider_version", "payload": {}},
]

transcript = []
assert proc.stdin and proc.stdout
try:
    for req in requests:
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            break
        transcript.append({"request": req, "response": json.loads(line)})
finally:
    proc.stdin.close()

try:
    proc.wait(timeout=60)
except subprocess.TimeoutExpired:
    proc.kill()
    proc.wait(timeout=20)

stderr = proc.stderr.read() if proc.stderr else ""
out = {
    "pristine_engine_sha": ENGINE_SHA,
    "workspace": str(WS),
    "returncode": proc.returncode,
    "transcript": transcript,
    "stderr_tail": stderr[-4000:],
}
print(json.dumps(out, indent=1, sort_keys=True))

reachable = False
for entry in transcript:
    resp = entry["response"]
    if resp.get("status") == "ok" and resp.get("request_id") in ("smoke-1", "smoke-3"):
        reachable = True
print("PRISTINE_FORGE_RUNTIME_REACHABLE =", "YES" if reachable else "NO", file=sys.stderr)
sys.exit(0 if reachable else 1)
