from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_real_stdio_mcp_roundtrip() -> None:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "stdio-test", "version": "1"},
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "validate_deck", "arguments": {"deck_id": "rogshai/current"},
        }},
        {"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}},
        {"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {
            "uri": "commander-lab://rules-coverage",
        }},
        {"jsonrpc": "2.0", "id": 6, "method": "prompts/list", "params": {}},
        {"jsonrpc": "2.0", "id": 7, "method": "invalid/method", "params": {}},
        {"jsonrpc": "2.0", "id": 8, "method": "shutdown", "params": {}},
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    # Reproduce the legacy Windows stdio code page even on UTF-8 CI hosts.
    # The MCP JSON-RPC wire must remain ASCII-safe regardless of inherited encoding.
    env["PYTHONIOENCODING"] = "cp1252"
    completed = subprocess.run(
        [sys.executable, "-m", "commander_lab.mcp.server", str(ROOT)],
        input="".join(json.dumps(row) + "\n" for row in messages),
        text=True,
        capture_output=True,
        timeout=30,
        env=env,
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    rows = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    by_id = {row.get("id"): row for row in rows}
    assert set(by_id) == {1, 2, 3, 4, 5, 6, 7, 8}
    assert len(by_id[2]["result"]["tools"]) == 100
    assert by_id[3]["result"]["isError"] is False
    assert len(by_id[4]["result"]["resources"]) == 3
    assert by_id[5]["result"]["contents"][0]["mimeType"] == "application/json"
    assert len(by_id[6]["result"]["prompts"]) == 2
    assert by_id[7]["error"]["code"] == -32601
    assert by_id[8]["result"] == {}
