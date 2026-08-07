from __future__ import annotations

from pathlib import Path

from commander_lab.mcp import MCP_PROTOCOL_VERSION, CommanderMcpServer

ROOT = Path(__file__).resolve().parents[2]


def request(server: CommanderMcpServer, ident: int, method: str, params=None):
    return server.handle({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}})


def test_mcp_lifecycle_tools_resources_prompts_and_shutdown() -> None:
    server = CommanderMcpServer(ROOT)
    before = request(server, 1, "tools/list")
    assert before["error"]["code"] == -32002

    initialized = request(server, 2, "initialize", {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "1"},
    })
    assert initialized["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    tools = request(server, 3, "tools/list")
    assert len(tools["result"]["tools"]) == 100
    assert tools["result"]["tools"][0]["annotations"]["readOnlyHint"] is True

    called = request(server, 4, "tools/call", {
        "name": "validate_deck", "arguments": {"deck_id": "korvold/current"}
    })
    assert called["result"]["isError"] is False
    assert called["result"]["structuredContent"]["status"] == "completed"

    resources = request(server, 5, "resources/list")
    assert {row["uri"] for row in resources["result"]["resources"]} >= {
        "commander-lab://status", "commander-lab://rules-coverage"
    }
    read = request(server, 6, "resources/read", {"uri": "commander-lab://status"})
    assert read["result"]["contents"][0]["mimeType"] == "application/json"

    prompts = request(server, 7, "prompts/list")
    assert {row["name"] for row in prompts["result"]["prompts"]} == {
        "optimize-deck", "compare-swap"
    }
    prompt = request(server, 8, "prompts/get", {
        "name": "optimize-deck", "arguments": {"deck_id": "korvold/current"}
    })
    assert prompt["result"]["messages"][0]["role"] == "user"

    timeout = request(server, 9, "tools/call", {
        "name": "validate_deck",
        "arguments": {"deck_id": "korvold/current"},
        "_meta": {"timeoutMs": 0},
    })
    assert timeout["error"]["code"] == -32001

    unknown = request(server, 10, "tools/call", {"name": "does_not_exist", "arguments": {}})
    assert unknown["error"]["code"] == -32602
    malformed = request(server, 11, "resources/read", {})
    assert malformed["error"]["code"] == -32602

    assert server.handle({
        "jsonrpc": "2.0", "method": "notifications/cancelled",
        "params": {"requestId": 77, "reason": "test"},
    }) is None
    assert request(server, 77, "ping") is None

    stopped = request(server, 12, "shutdown")
    assert stopped["result"] == {}
    assert server.session.shutdown_requested is True
