# Phase 12.17 – MCP and orchestrator integration

Status: `passed_with_limitations`

- Real local stdio MCP JSON-RPC server implemented over the same central 100-tool registry as FastAPI.
- Negotiated protocol: `2025-11-25`; a 2026-07-28 request is accepted with 2025 compatibility response because the requested acceptance gates require `initialize`.
- Tested: initialize, initialized notification, tools/list, tools/call, resources/list, resources/read, prompts/list, prompts/get, timeout, cancellation notification, structured errors, shutdown and EOF lifecycle.
- Three read-only resources and two prompt templates are exposed.
- Tool annotations declare read-only/non-destructive behavior; no deck change can be applied.
- Five deterministic run profiles are implemented: quick_screen, standard_validation, deep_validation, external_engine_validation, full_optimization.
- OpenAI agent instructions now prohibit manual real-playtest calibration and false external-engine claims.
- External-engine validation remains blocked by the Phase 12.13 runtime limitations.
