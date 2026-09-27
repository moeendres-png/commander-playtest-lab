# Phase 12.17 – MCP integration

## Protocol eras

The server implements two deliberately separated protocol paths:

- **MCP 2026-07-28 (primary):** stateless core; `server/discover` is optional; every normal request carries the protocol version and client identity in `_meta`. `initialize`, protocol sessions, and the custom `shutdown` request are not treated as 2026 core methods.
- **MCP 2025-11-25 (compatibility):** `initialize` / `notifications/initialized`, legacy cancellation notifications, and the local shutdown handshake remain available for older clients.

The two paths are not silently mixed. A 2026 request cannot be upgraded from a 2025 initialize response.

## Transport

`python -m commander_lab.mcp.server <repo-root>` starts a real newline-delimited JSON-RPC stdio server. stdout is protocol-only. Diagnostics belong on stderr.

The server exposes the same central `ToolRegistry` as FastAPI, plus three read-only resources and two prompt templates. Tool annotations are read-only and non-destructive; task-based asynchronous mutation is forbidden.

## Cancellation and timeout

Tool calls execute behind a cancellable protocol wrapper. The stdio reader remains able to accept a cancellation notification while a tool invocation is in flight. Cancellation suppresses the cancelled response and releases the protocol wrapper without waiting for an uncooperative tool body. Timeout behaves the same way; underlying workers are daemon threads and cannot pin process shutdown.

The cancellation notification belongs to the legacy compatibility path. The 2026 core itself is kept stateless.

## OpenAI Agents SDK

The current project configuration is stored in `config/openai_mcp_stdio.json`. The intended SDK integration is `agents.mcp.MCPServerStdio`, which launches the Commander Lab process and owns the stdio pipes. The optional `openai-agents` package is not installed in the current execution runtime, so a live Agents-SDK-to-server process test is **blocked**, not passed. The server transport itself is tested directly by real subprocess stdio tests.

## Run profiles

The orchestrator exposes exactly five profiles:

1. `quick_screen`
2. `standard_validation`
3. `deep_validation`
4. `external_engine_validation`
5. `full_optimization`

No profile applies deck changes automatically. `external_engine_validation` can only succeed when the external-rules provider itself passes the real process/handshake/action-loop gates.
