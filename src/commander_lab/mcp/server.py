from __future__ import annotations

import contextlib
import json
import queue
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from pydantic import ValidationError

from commander_lab import __version__
from commander_lab.project_context import load_project_context
from commander_lab.tools import CommanderToolService, ToolRegistry

CURRENT_MCP_PROTOCOL_VERSION = "2026-07-28"
LEGACY_MCP_PROTOCOL_VERSION = "2025-11-25"
MCP_PROTOCOL_VERSION = CURRENT_MCP_PROTOCOL_VERSION
SERVER_NAME = "commander-playtest-lab"
SERVER_VERSION = __version__
_PROTOCOL_META_KEY = "io.modelcontextprotocol/protocolVersion"
_CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
_SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"


class McpProtocolError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class McpCancelled(Exception):
    pass


@dataclass(slots=True)
class McpSession:
    """Legacy 2025-11-25 compatibility state only.

    The 2026-07-28 core is stateless and never depends on this object for request
    routing or capability discovery.
    """

    legacy_initialized: bool = False
    client_info: dict[str, Any] = field(default_factory=dict)
    cancelled_requests: set[str] = field(default_factory=set)
    shutdown_requested: bool = False

    @property
    def initialized(self) -> bool:  # compatibility for older internal callers/tests
        return self.legacy_initialized


class CommanderMcpServer:
    """Dependency-free MCP stdio server over the central ToolRegistry.

    Primary protocol: MCP 2026-07-28 stateless core. A deliberately isolated
    2025-11-25 compatibility path remains for clients that still use
    initialize/initialized and notifications/cancelled.

    Stdout is protocol-only; diagnostics belong on stderr.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.service = CommanderToolService(self.root)
        self.registry = ToolRegistry(self.service)
        self.session = McpSession()

    @staticmethod
    def _server_info() -> dict[str, str]:
        return {
            "name": SERVER_NAME,
            "title": "Commander Playtest Lab",
            "version": SERVER_VERSION,
            "description": (
                "Read-only multifidelity Commander deck analysis and optimization tools."
            ),
        }

    @classmethod
    def _error(
        cls,
        request_id: Any,
        error: McpProtocolError,
        *,
        modern: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": error.code, "message": error.message},
        }
        if error.data is not None:
            payload["error"]["data"] = error.data
        if modern:
            payload["error"]["_meta"] = {_SERVER_INFO_META_KEY: cls._server_info()}
        return payload

    @classmethod
    def _result(
        cls,
        request_id: Any,
        result: dict[str, Any],
        *,
        modern: bool = False,
    ) -> dict[str, Any]:
        body = dict(result)
        if modern:
            meta = dict(body.get("_meta") or {})
            meta[_SERVER_INFO_META_KEY] = cls._server_info()
            body["_meta"] = meta
        return {"jsonrpc": "2.0", "id": request_id, "result": body}

    def _require_legacy_initialized(self) -> None:
        if not self.session.legacy_initialized:
            raise McpProtocolError(-32002, "Legacy MCP session has not completed initialization")

    @staticmethod
    def _request_meta(params: dict[str, Any]) -> dict[str, Any]:
        value = params.get("_meta")
        return dict(value) if isinstance(value, dict) else {}

    @classmethod
    def _modern_request(cls, method: str, params: dict[str, Any]) -> bool:
        if method == "server/discover":
            return True
        return cls._request_meta(params).get(_PROTOCOL_META_KEY) == CURRENT_MCP_PROTOCOL_VERSION

    @classmethod
    def _validate_modern_meta(cls, params: dict[str, Any]) -> None:
        meta = cls._request_meta(params)
        version = meta.get(_PROTOCOL_META_KEY)
        if version != CURRENT_MCP_PROTOCOL_VERSION:
            raise McpProtocolError(
                -32602,
                (
                    "2026-07-28 requests require "
                    f"params._meta['{_PROTOCOL_META_KEY}']='{CURRENT_MCP_PROTOCOL_VERSION}'"
                ),
            )
        client_info = meta.get(_CLIENT_INFO_META_KEY)
        if client_info is not None and not isinstance(client_info, dict):
            raise McpProtocolError(-32602, "clientInfo metadata must be an object when supplied")

    def _resources(self) -> list[dict[str, Any]]:
        return [
            {
                "uri": "commander-lab://status",
                "name": "Commander Lab status",
                "description": "Current project scope, software identity and evidence boundaries.",
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
            context = load_project_context(self.root)
            payload = {
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
                "tool_count": len(self.registry.list_schemas()),
                "active_own_deck_ids": list(context.active_own_deck_ids),
                "historical_own_deck_ids": list(context.historical_own_deck_ids),
                "primary_deckbuilding_focus": context.primary_deckbuilding_focus,
                "project_snapshot_hash": context.snapshot_hash,
                "evidence_boundaries": {
                    "structural_model_estimates_are_empirical_winrates": False,
                    "tactical_oracle_is_external_rules_engine": False,
                    "real_playtest_calibration_active": False,
                },
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
            ],
            "ttlMs": 30_0000,
            "cacheScope": "private",
        }

    @staticmethod
    def _prompts() -> list[dict[str, Any]]:
        return [
            {
                "name": "compare-swap",
                "description": "Validate a proposed card swap without applying it.",
                "arguments": [
                    {"name": "deck_id", "required": True},
                    {"name": "current_card", "required": True},
                    {"name": "candidate_id", "required": True},
                ],
            },
            {
                "name": "optimize-deck",
                "description": "Build a read-only multifidelity optimization plan for one deck.",
                "arguments": [
                    {
                        "name": "deck_id",
                        "description": "Current deck ID",
                        "required": True,
                    },
                    {
                        "name": "profile",
                        "description": (
                            "quick_screen, standard_validation, deep_validation, "
                            "external_engine_validation, or full_optimization"
                        ),
                        "required": False,
                    },
                ],
            },
        ]

    def _get_prompt(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "optimize-deck":
            deck_id = arguments.get("deck_id")
            if not isinstance(deck_id, str) or not deck_id:
                deck_id = load_project_context(self.root).primary_deckbuilding_focus
            profile = arguments.get("profile", "standard_validation")
            text = (
                f"Optimize {deck_id} using profile {profile}. Load the current read-only context, "
                "generate candidates, run only the necessary multifidelity gates, preserve the "
                "truth boundary, and do not apply any deck or allocation change."
            )
        elif name == "compare-swap":
            text = (
                f"Validate {arguments.get('current_card')} to {arguments.get('candidate_id')} in "
                f"{arguments.get('deck_id')}. Report formal, structural, holdout, tactical "
                "coverage, external provider status, uncertainty, and do not apply the swap."
            )
        else:
            raise McpProtocolError(-32602, f"Unknown prompt: {name}")
        return {
            "description": f"Commander Lab prompt: {name}",
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
        }

    def _call_tool(
        self,
        request_id: Any,
        params: dict[str, Any],
        *,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str):
            raise McpProtocolError(-32602, "tools/call requires a string name")
        if not isinstance(arguments, dict):
            raise McpProtocolError(-32602, "tools/call arguments must be an object")
        if name not in {schema["name"] for schema in self.registry.list_schemas()}:
            raise McpProtocolError(-32602, f"Unknown tool: {name}")
        meta = self._request_meta(params)
        timeout_ms = 120_000
        if "timeoutMs" in meta:
            try:
                timeout_ms = max(0, int(meta["timeoutMs"]))
            except (TypeError, ValueError) as exc:
                raise McpProtocolError(-32602, "timeoutMs must be an integer") from exc
        if timeout_ms == 0:
            raise McpProtocolError(-32001, "Tool call timed out after 0 ms")

        done: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

        def invoke() -> None:
            try:
                done.put(("ok", self.registry.invoke(name, arguments)))
            except BaseException as exc:  # daemon worker boundary; re-raised on protocol thread
                with contextlib.suppress(queue.Full):
                    done.put(("error", exc))

        worker = threading.Thread(
            target=invoke,
            name=f"mcp-tool-{request_id}",
            daemon=True,
        )
        worker.start()
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise McpCancelled(f"request {request_id} cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise McpProtocolError(-32001, f"Tool call timed out after {timeout_ms} ms")
            try:
                kind, value = done.get(timeout=min(0.05, remaining))
            except queue.Empty:
                continue
            if kind == "error":
                raise value
            response = value
            body = response.model_dump(mode="json")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(body, ensure_ascii=False, sort_keys=True),
                    }
                ],
                "structuredContent": body,
                "isError": body.get("status") != "completed",
            }

    def _discover_result(self) -> dict[str, Any]:
        return {
            "protocolVersions": [CURRENT_MCP_PROTOCOL_VERSION, LEGACY_MCP_PROTOCOL_VERSION],
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False},
                "prompts": {"listChanged": False},
            },
            "instructions": (
                "Never treat structural estimates as empirical winrates or Tactical Oracle "
                "as an external engine."
            ),
            "ttlMs": 300_000,
            "cacheScope": "private",
        }

    def handle(
        self,
        message: dict[str, Any],
        *,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any] | None:
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})
        modern = (
            isinstance(method, str)
            and isinstance(params, dict)
            and self._modern_request(method, params)
        )
        try:
            if message.get("jsonrpc") != "2.0":
                raise McpProtocolError(-32600, "jsonrpc must be '2.0'")
            if not isinstance(method, str):
                raise McpProtocolError(-32600, "method must be a string")
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise McpProtocolError(-32602, "params must be an object")

            if method == "server/discover":
                return self._result(request_id, self._discover_result(), modern=True)

            if method == "initialize":
                requested = params.get("protocolVersion", LEGACY_MCP_PROTOCOL_VERSION)
                if requested == CURRENT_MCP_PROTOCOL_VERSION:
                    raise McpProtocolError(
                        -32602,
                        (
                            "MCP 2026-07-28 removed initialize; use server/discover "
                            "and per-request _meta"
                        ),
                    )
                if requested != LEGACY_MCP_PROTOCOL_VERSION:
                    raise McpProtocolError(
                        -32602,
                        f"Unsupported initialize-era protocol version: {requested}",
                    )
                self.session.client_info = dict(params.get("clientInfo") or {})
                self.session.legacy_initialized = True
                return self._result(
                    request_id,
                    {
                        "protocolVersion": LEGACY_MCP_PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"listChanged": False},
                            "prompts": {"listChanged": False},
                        },
                        "serverInfo": self._server_info(),
                        "instructions": (
                            "Legacy compatibility mode; prefer MCP 2026-07-28 server/discover."
                        ),
                    },
                )
            if method == "notifications/initialized":
                self._require_legacy_initialized()
                return None
            if method == "notifications/cancelled":
                cancelled = params.get("requestId")
                if cancelled is not None:
                    self.session.cancelled_requests.add(str(cancelled))
                return None

            if modern:
                self._validate_modern_meta(params)
            else:
                self._require_legacy_initialized()
                if str(request_id) in self.session.cancelled_requests:
                    return None

            if method == "ping":
                return self._result(request_id, {}, modern=modern)
            if method == "tools/list":
                tools = sorted(
                    (
                        {
                            "name": row["name"],
                            "description": row["description"],
                            "inputSchema": row["parameters"],
                            "annotations": {
                                "readOnlyHint": True,
                                "destructiveHint": False,
                            },
                            "execution": {"taskSupport": "forbidden"},
                        }
                        for row in self.registry.list_schemas()
                    ),
                    key=lambda row: row["name"],
                )
                return self._result(
                    request_id,
                    {
                        "tools": tools,
                        "ttlMs": 300_000,
                        "cacheScope": "private",
                    },
                    modern=modern,
                )
            if method == "tools/call":
                return self._result(
                    request_id,
                    self._call_tool(request_id, params, cancel_event=cancel_event),
                    modern=modern,
                )
            if method == "resources/list":
                return self._result(
                    request_id,
                    {
                        "resources": sorted(self._resources(), key=lambda row: row["uri"]),
                        "ttlMs": 300_000,
                        "cacheScope": "private",
                    },
                    modern=modern,
                )
            if method == "resources/read":
                uri = params.get("uri")
                if not isinstance(uri, str):
                    raise McpProtocolError(-32602, "resources/read requires uri")
                return self._result(request_id, self._read_resource(uri), modern=modern)
            if method == "prompts/list":
                return self._result(
                    request_id,
                    {
                        "prompts": self._prompts(),
                        "ttlMs": 300_000,
                        "cacheScope": "private",
                    },
                    modern=modern,
                )
            if method == "prompts/get":
                name = params.get("name")
                if not isinstance(name, str):
                    raise McpProtocolError(-32602, "prompts/get requires name")
                arguments = params.get("arguments") or {}
                if not isinstance(arguments, dict):
                    raise McpProtocolError(-32602, "prompt arguments must be an object")
                return self._result(
                    request_id,
                    self._get_prompt(name, arguments),
                    modern=modern,
                )
            if method == "shutdown":
                if modern:
                    raise McpProtocolError(
                        -32601,
                        (
                            "shutdown is not a 2026-07-28 core method; close stdio/HTTP "
                            "transport instead"
                        ),
                    )
                self.session.shutdown_requested = True
                return self._result(request_id, {})
            raise McpProtocolError(-32601, f"Method not found: {method}")
        except McpCancelled:
            return None
        except ValidationError as exc:
            return self._error(
                request_id,
                McpProtocolError(-32602, "Invalid tool arguments", exc.errors()),
                modern=modern,
            )
        except McpProtocolError as exc:
            return self._error(request_id, exc, modern=modern)
        except Exception as exc:  # protocol boundary
            return self._error(
                request_id,
                McpProtocolError(
                    -32603,
                    f"Internal error: {type(exc).__name__}: {exc}",
                ),
                modern=modern,
            )

    def serve_stdio(self, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
        write_lock = threading.Lock()
        inflight: dict[str, tuple[threading.Event, threading.Thread]] = {}

        def write_response(response: dict[str, Any] | None) -> None:
            if response is None:
                return
            with write_lock:
                # JSON-RPC is an ASCII-safe wire format. Escaping non-ASCII here keeps
                # stdio interoperable even when Windows inherits a legacy code page.
                stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
                stdout.flush()

        def run_tool(message: dict[str, Any], key: str, event: threading.Event) -> None:
            try:
                response = self.handle(message, cancel_event=event)
                if not event.is_set():
                    write_response(response)
            finally:
                inflight.pop(key, None)

        for raw in stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ValueError("message must be an object")
            except (json.JSONDecodeError, ValueError) as exc:
                write_response(self._error(None, McpProtocolError(-32700, f"Parse error: {exc}")))
                continue

            method = message.get("method")
            params = message.get("params") or {}
            if method == "notifications/cancelled" and isinstance(params, dict):
                cancelled = params.get("requestId")
                if cancelled is not None:
                    key = str(cancelled)
                    self.session.cancelled_requests.add(key)
                    item = inflight.get(key)
                    if item is not None:
                        item[0].set()
                continue

            if method == "tools/call" and message.get("id") is not None:
                key = str(message["id"])
                if key in inflight:
                    write_response(
                        self._error(
                            message["id"],
                            McpProtocolError(-32600, "duplicate in-flight request id"),
                        )
                    )
                    continue
                event = threading.Event()
                thread = threading.Thread(
                    target=run_tool,
                    args=(message, key, event),
                    name=f"mcp-request-{key}",
                    daemon=True,
                )
                inflight[key] = (event, thread)
                thread.start()
                continue

            response = self.handle(message)
            write_response(response)
            if self.session.shutdown_requested:
                break

        # Let protocol wrappers finish briefly. Their underlying tool workers are daemon
        # threads, so cancellation/timeout/EOF never pins process shutdown indefinitely.
        for event, thread in list(inflight.values()):
            thread.join(timeout=2.0)
            if thread.is_alive():
                event.set()
        return 0


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    return CommanderMcpServer(root).serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
