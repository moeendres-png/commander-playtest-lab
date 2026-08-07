from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from pydantic import ValidationError

from commander_lab.tools import CommanderToolService, ToolRegistry

MCP_PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "commander-playtest-lab"
SERVER_VERSION = "1.10.2"


class McpProtocolError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass(slots=True)
class McpSession:
    initialized: bool = False
    client_info: dict[str, Any] = field(default_factory=dict)
    cancelled_requests: set[str] = field(default_factory=set)
    shutdown_requested: bool = False


class CommanderMcpServer:
    """Minimal dependency-free MCP stdio server over the central ToolRegistry.

    Stdout is protocol-only. Operational diagnostics belong on stderr.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.service = CommanderToolService(self.root)
        self.registry = ToolRegistry(self.service)
        self.session = McpSession()

    @staticmethod
    def _error(request_id: Any, error: McpProtocolError) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": error.code, "message": error.message},
        }
        if error.data is not None:
            payload["error"]["data"] = error.data
        return payload

    @staticmethod
    def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _require_initialized(self) -> None:
        if not self.session.initialized:
            raise McpProtocolError(-32002, "Server has not completed initialization")

    def _resources(self) -> list[dict[str, Any]]:
        return [
            {
                "uri": "commander-lab://status",
                "name": "Commander Lab status",
                "description": "Current verified phase and external-engine truth boundary.",
                "mimeType": "application/json",
            },
            {
                "uri": "commander-lab://optimization-context",
                "name": "Optimization context",
                "description": "Read-only deck, allocation, coverage, pilot and engine context.",
                "mimeType": "application/json",
            },
            {
                "uri": "commander-lab://rules-coverage",
                "name": "Card rules coverage",
                "description": "Current card and provider coverage registry.",
                "mimeType": "application/json",
            },
        ]

    def _read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "commander-lab://status":
            rows = {}
            for phase in ("12_12", "12_13", "12_14", "12_15", "12_16"):
                path = self.root / f"artifacts/phase{phase}/PHASE{phase}_RESULT.json"
                if path.exists():
                    rows[phase.replace("_", ".")] = json.loads(path.read_text(encoding="utf-8"))
            payload = {
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
                "tool_count": len(self.registry.list_schemas()),
                "phases": rows,
            }
        elif uri == "commander-lab://optimization-context":
            response = self.registry.invoke("build_optimization_context", {})
            payload = response.model_dump(mode="json")
        elif uri == "commander-lab://rules-coverage":
            path = self.root / "data/rules/card_rules_coverage.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            raise McpProtocolError(-32602, f"Unknown resource URI: {uri}")
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(payload, ensure_ascii=False, sort_keys=True),
                }
            ]
        }

    @staticmethod
    def _prompts() -> list[dict[str, Any]]:
        return [
            {
                "name": "optimize-deck",
                "description": "Build a read-only multifidelity optimization plan for one deck.",
                "arguments": [
                    {"name": "deck_id", "description": "Current deck ID", "required": True},
                    {"name": "profile", "description": "quick_screen, standard_validation, deep_validation, external_engine_validation, or full_optimization", "required": False},
                ],
            },
            {
                "name": "compare-swap",
                "description": "Validate a proposed card swap without applying it.",
                "arguments": [
                    {"name": "deck_id", "required": True},
                    {"name": "current_card", "required": True},
                    {"name": "candidate_id", "required": True},
                ],
            },
        ]

    def _get_prompt(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "optimize-deck":
            deck_id = arguments.get("deck_id", "korvold/current")
            profile = arguments.get("profile", "standard_validation")
            text = (
                f"Optimize {deck_id} using profile {profile}. Load the current read-only context, "
                "generate candidates, run only the necessary multifidelity gates, preserve the "
                "truth boundary, and do not apply any deck or allocation change."
            )
        elif name == "compare-swap":
            text = (
                f"Validate {arguments.get('current_card')} to {arguments.get('candidate_id')} in "
                f"{arguments.get('deck_id')}. Report formal, structural, holdout, tactical coverage, "
                "external provider status, uncertainty, and do not apply the swap."
            )
        else:
            raise McpProtocolError(-32602, f"Unknown prompt: {name}")
        return {
            "description": f"Commander Lab prompt: {name}",
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
        }

    def _call_tool(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str):
            raise McpProtocolError(-32602, "tools/call requires a string name")
        if not isinstance(arguments, dict):
            raise McpProtocolError(-32602, "tools/call arguments must be an object")
        if name not in {schema["name"] for schema in self.registry.list_schemas()}:
            raise McpProtocolError(-32602, f"Unknown tool: {name}")
        meta = params.get("_meta", {})
        timeout_ms = 120_000
        if isinstance(meta, dict) and "timeoutMs" in meta:
            try:
                timeout_ms = max(0, int(meta["timeoutMs"]))
            except (TypeError, ValueError) as exc:
                raise McpProtocolError(-32602, "timeoutMs must be an integer") from exc
        if timeout_ms == 0:
            raise McpProtocolError(-32001, "Tool call timed out after 0 ms")
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mcp-tool")
        future = executor.submit(self.registry.invoke, name, arguments)
        try:
            response = future.result(timeout=timeout_ms / 1000)
        except FutureTimeout as exc:
            future.cancel()
            raise McpProtocolError(-32001, f"Tool call timed out after {timeout_ms} ms") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        body = response.model_dump(mode="json")
        is_error = body.get("status") != "completed"
        return {
            "content": [{"type": "text", "text": json.dumps(body, ensure_ascii=False, sort_keys=True)}],
            "structuredContent": body,
            "isError": is_error,
        }

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        try:
            if message.get("jsonrpc") != "2.0":
                raise McpProtocolError(-32600, "jsonrpc must be '2.0'")
            method = message.get("method")
            if not isinstance(method, str):
                raise McpProtocolError(-32600, "method must be a string")
            params = message.get("params", {})
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise McpProtocolError(-32602, "params must be an object")

            if method == "initialize":
                requested = params.get("protocolVersion", MCP_PROTOCOL_VERSION)
                if requested not in {MCP_PROTOCOL_VERSION, "2026-07-28"}:
                    raise McpProtocolError(-32602, f"Unsupported protocol version: {requested}")
                self.session.client_info = dict(params.get("clientInfo") or {})
                self.session.initialized = True
                return self._result(request_id, {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"listChanged": False},
                        "prompts": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "title": "Commander Playtest Lab",
                        "version": SERVER_VERSION,
                        "description": "Read-only multifidelity Commander deck analysis and optimization tools.",
                    },
                    "instructions": "Never treat structural estimates as empirical winrates or Tactical Oracle as an external engine.",
                })
            if method == "notifications/initialized":
                self._require_initialized()
                return None
            if method == "notifications/cancelled":
                cancelled = params.get("requestId")
                if cancelled is not None:
                    self.session.cancelled_requests.add(str(cancelled))
                return None

            self._require_initialized()
            if str(request_id) in self.session.cancelled_requests:
                return None
            if method == "ping":
                return self._result(request_id, {})
            if method == "tools/list":
                tools = [
                    {
                        "name": row["name"],
                        "description": row["description"],
                        "inputSchema": row["parameters"],
                        "annotations": {"readOnlyHint": True, "destructiveHint": False},
                        "execution": {"taskSupport": "forbidden"},
                    }
                    for row in self.registry.list_schemas()
                ]
                return self._result(request_id, {"tools": tools})
            if method == "tools/call":
                return self._result(request_id, self._call_tool(request_id, params))
            if method == "resources/list":
                return self._result(request_id, {"resources": self._resources()})
            if method == "resources/read":
                uri = params.get("uri")
                if not isinstance(uri, str):
                    raise McpProtocolError(-32602, "resources/read requires uri")
                return self._result(request_id, self._read_resource(uri))
            if method == "prompts/list":
                return self._result(request_id, {"prompts": self._prompts()})
            if method == "prompts/get":
                name = params.get("name")
                if not isinstance(name, str):
                    raise McpProtocolError(-32602, "prompts/get requires name")
                arguments = params.get("arguments") or {}
                if not isinstance(arguments, dict):
                    raise McpProtocolError(-32602, "prompt arguments must be an object")
                return self._result(request_id, self._get_prompt(name, arguments))
            if method == "shutdown":
                self.session.shutdown_requested = True
                return self._result(request_id, {})
            raise McpProtocolError(-32601, f"Method not found: {method}")
        except ValidationError as exc:
            return self._error(request_id, McpProtocolError(-32602, "Invalid tool arguments", exc.errors()))
        except McpProtocolError as exc:
            return self._error(request_id, exc)
        except Exception as exc:  # protocol boundary
            return self._error(request_id, McpProtocolError(-32603, f"Internal error: {type(exc).__name__}: {exc}"))

    def serve_stdio(self, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
        for raw in stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ValueError("message must be an object")
                response = self.handle(message)
            except (json.JSONDecodeError, ValueError) as exc:
                response = self._error(None, McpProtocolError(-32700, f"Parse error: {exc}"))
            if response is not None:
                stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                stdout.flush()
            if self.session.shutdown_requested:
                break
        return 0


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    return CommanderMcpServer(root).serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
