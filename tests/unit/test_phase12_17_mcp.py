from __future__ import annotations

import io
import json
import time
from pathlib import Path

from commander_lab.mcp import (
    CURRENT_MCP_PROTOCOL_VERSION,
    LEGACY_MCP_PROTOCOL_VERSION,
    CommanderMcpServer,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
SERVER_META = "io.modelcontextprotocol/serverInfo"


def modern_params(**values):
    meta = dict(values.pop("_meta", {}))
    meta[PROTOCOL_META] = CURRENT_MCP_PROTOCOL_VERSION
    return {**values, "_meta": meta}


def request(server: CommanderMcpServer, ident: int, method: str, params=None):
    return server.handle({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}})


def test_modern_mcp_is_stateless_and_exposes_tools_resources_prompts() -> None:
    server = CommanderMcpServer(ROOT)

    discover = request(server, 1, "server/discover")
    assert CURRENT_MCP_PROTOCOL_VERSION in discover["result"]["protocolVersions"]
    assert discover["result"]["_meta"][SERVER_META]["name"] == "commander-playtest-lab"

    tools = request(server, 2, "tools/list", modern_params())
    assert len(tools["result"]["tools"]) == 100
    assert tools["result"]["tools"] == sorted(tools["result"]["tools"], key=lambda row: row["name"])
    assert tools["result"]["tools"][0]["annotations"]["readOnlyHint"] is True
    assert tools["result"]["ttlMs"] == 300_000
    assert tools["result"]["cacheScope"] == "private"

    called = request(server, 3, "tools/call", modern_params(
        name="validate_deck", arguments={"deck_id": "korvold/current"}
    ))
    assert called["result"]["isError"] is False
    assert called["result"]["structuredContent"]["status"] == "completed"

    resources = request(server, 4, "resources/list", modern_params())
    assert {row["uri"] for row in resources["result"]["resources"]} >= {
        "commander-lab://status", "commander-lab://rules-coverage"
    }
    read = request(server, 5, "resources/read", modern_params(uri="commander-lab://status"))
    assert read["result"]["contents"][0]["mimeType"] == "application/json"

    prompts = request(server, 6, "prompts/list", modern_params())
    assert {row["name"] for row in prompts["result"]["prompts"]} == {
        "optimize-deck", "compare-swap"
    }
    prompt = request(server, 7, "prompts/get", modern_params(
        name="optimize-deck", arguments={"deck_id": "korvold/current"}
    ))
    assert prompt["result"]["messages"][0]["role"] == "user"

    timeout = request(server, 8, "tools/call", modern_params(
        name="validate_deck", arguments={"deck_id": "korvold/current"},
        _meta={"timeoutMs": 0},
    ))
    assert timeout["error"]["code"] == -32001

    unknown = request(server, 9, "tools/call", modern_params(name="does_not_exist", arguments={}))
    assert unknown["error"]["code"] == -32602
    malformed = request(server, 10, "resources/read", modern_params())
    assert malformed["error"]["code"] == -32602

    # 2026-07-28 removed initialize and the custom shutdown lifecycle from the core.
    init = request(server, 11, "initialize", {
        "protocolVersion": CURRENT_MCP_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "1"},
    })
    assert init["error"]["code"] == -32602
    stopped = request(server, 12, "shutdown", modern_params())
    assert stopped["error"]["code"] == -32601
    assert server.session.initialized is False


def test_legacy_2025_compatibility_requires_initialize_and_can_shutdown() -> None:
    server = CommanderMcpServer(ROOT)
    before = request(server, 1, "tools/list")
    assert before["error"]["code"] == -32002

    initialized = request(server, 2, "initialize", {
        "protocolVersion": LEGACY_MCP_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "pytest-legacy", "version": "1"},
    })
    assert initialized["result"]["protocolVersion"] == LEGACY_MCP_PROTOCOL_VERSION
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert request(server, 3, "ping")["result"] == {}
    stopped = request(server, 4, "shutdown")
    assert stopped["result"] == {}
    assert server.session.shutdown_requested is True


def test_stdio_cancellation_interrupts_protocol_wrapper_without_waiting_for_tool(monkeypatch) -> None:
    server = CommanderMcpServer(ROOT)

    original = server.registry.invoke

    def slow_invoke(name, arguments):
        if name == "validate_deck":
            time.sleep(1.0)
        return original(name, arguments)

    monkeypatch.setattr(server.registry, "invoke", slow_invoke)
    call = {
        "jsonrpc": "2.0", "id": 77, "method": "tools/call",
        "params": modern_params(name="validate_deck", arguments={"deck_id": "korvold/current"}),
    }
    cancel = {
        "jsonrpc": "2.0", "method": "notifications/cancelled",
        "params": {"requestId": 77, "reason": "test cancellation"},
    }
    ping = {"jsonrpc": "2.0", "id": 78, "method": "ping", "params": modern_params()}
    stdin = io.StringIO("\n".join(json.dumps(row) for row in (call, cancel, ping)) + "\n")
    stdout = io.StringIO()

    started = time.monotonic()
    code = server.serve_stdio(stdin, stdout)
    elapsed = time.monotonic() - started
    rows = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    by_id = {row.get("id"): row for row in rows}

    assert code == 0
    assert 77 not in by_id
    assert by_id[78]["result"]["_meta"][SERVER_META]["version"] == "1.10.3"
    assert elapsed < 0.75, f"cancellation wrapper blocked for {elapsed:.3f}s"
