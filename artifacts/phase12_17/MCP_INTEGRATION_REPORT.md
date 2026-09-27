# Phase 12.17 – MCP and orchestrator integration

Status: `passed_with_limitations`

Package version: `1.10.3`  

## Protocol correction

The primary MCP path is now `2026-07-28`, not `2025-11-25`. The modern path is stateless, supports `server/discover`, deterministic/cacheable list responses and rejects the retired modern `initialize` handshake. A separate `2025-11-25` compatibility path retains initialize/initialized and shutdown semantics for legacy clients.

## Real local transport tests

- Modern stdio JSON-RPC subprocess: `passed`, return code 0, stderr empty: `True`.
- 100 tools exposed from the same central registry used by the HTTP/Function surface.
- Real `validate_deck` MCP tool call completed.
- 3 read-only resources and 2 prompts exposed.
- In-flight cancellation is tested while a deliberately slow tool call is running; the stdio reader continues processing messages and suppresses the cancelled response.
- Timeout, structured errors, EOF lifecycle and legacy subprocess roundtrip are tested.
- Tool annotations are read-only/non-destructive and Tasks are forbidden for this optimizer surface.

## OpenAI Agents SDK

`config/openai_mcp_stdio.json` is prepared for `agents.mcp.MCPServerStdio`. The current execution runtime does not have `openai-agents` installed, so the live SDK client test remains `blocked_not_installed`; this does not downgrade the already executed local MCP server/subprocess test into a mock.

## Run profiles

`quick_screen`, `standard_validation`, `deep_validation`, `external_engine_validation`, and `full_optimization` are registered. None can apply a deck change automatically.
