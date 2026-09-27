# MCP Integration Report

- Package: `1.13.0`
- Product code commit: `29e5568197f3660c227ba41116ed068fffc721e2`
- Primary protocol: MCP `2026-07-28` stateless core.
- Compatibility protocol: `2025-11-25`.
- Transport: stdio JSON-RPC.
- Registered tools: 100.
- Resources: 3. Prompts: 2.
- `server/discover`, `tools/list`, `tools/call`, `resources/list/read`, `prompts/list/get`, timeout, structured errors, EOF lifecycle and in-flight cancellation are implemented/tested.
- Modern requests require protocol metadata; `initialize` is rejected for 2026-07-28 and retained only for legacy compatibility.
- OpenAI Agents SDK integration targets `MCPServerStdio`; no API credential was consumed during release acceptance.
