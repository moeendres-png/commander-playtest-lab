# Claude efficiency setup

Repository configuration is shared in Git. A machine only needs the external
executables for the features it wants.

## Serena symbolic navigation

Required locally: uv/uvx.

1. Install uv if uvx is not already on PATH.
2. Start Claude Code from this repository.
3. Approve the project-scoped .mcp.json server the first time Claude asks.
4. Run /mcp in Claude Code and verify that serena is connected.

The MCP command pins Serena to commit
b4a83eec1097042f34a09985783c9491f99919c4. The committed
.serena/project.yml makes Serena read-only and disables Serena memories, so it
acts as code-navigation intelligence rather than an independent mutation or
memory authority.

## Optional RTK Bash-output compression

Install the RTK binary from rtk-ai/rtk using its documented installer/package
method. The repository does not curl-pipe or install it automatically.

The committed Claude hook detects rtk on PATH and uses it automatically. If RTK
is absent or errors, the hook emits no rewrite and Claude falls back to raw Bash
output.

For authoritative evidence commands use:

    COMMANDER_RAW_EVIDENCE=1 <command>

That marker bypasses RTK for the command.

## Context7 and Repomix

No global install is required. The skills invoke pinned packages through npx:

- Context7 CLI: ctx7@0.5.13
- Repomix: repomix@1.18.1

Node/npm/npx must be present when those skills are used. Context7 can be used
without login at lower limits. Never commit an API key.

## Diagnose local readiness

    python scripts/verify_claude_efficiency_setup.py

This command reports availability only. It does not install software, mutate
user-level Claude settings, or inspect credentials.
