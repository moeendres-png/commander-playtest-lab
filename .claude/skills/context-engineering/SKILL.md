---
name: context-engineering
description: Optimizes agent prompts, skills, policy files, tool surfaces and workstream context for high signal with minimal tokens. Use when editing AGENTS.md, CLAUDE.md, skills, subagents, MCP/tool configuration, durable state/handoffs, or when a session repeatedly rereads large files or suffers context drift.
---

# Commander Context Engineering

Treat context as a finite engineering resource. Optimize signal per token, never
policy or evidence away.

## Decision order

1. Is this truly always-on? If not, route it on demand.
2. Can the always-on layer keep only a path, symbol, run ID or query and retrieve
   payload just in time?
3. Can a deterministic tool answer first? Prefer repo-map, Serena/LSP, Git,
   grep/ast-grep, parsers and tests over bulk raw context.
4. Scope to the smallest relevant subtree, range or result set.
5. Preserve raw authority. Compact views navigate; material PASS claims bind to
   authoritative source/output/artifacts.
6. Avoid overlapping tools. One strong mechanism per capability beats duplicated
   MCPs and schemas.
7. Use fresh sessions/subagents for independent work instead of accumulating
   unrelated history.

## Progressive disclosure

- Root policy: high-frequency invariants plus routing index.
- Routed docs: detailed task-specific policy.
- Skill description: only enough for correct activation.
- Skill body/references: loaded only when selected.
- Workstream state: compact continuation index with durable references, not a
  prose transcript.
- Tool output: compact/navigation view first, raw evidence retained/retrievable.

## Context hazards

Remove or isolate stale SHAs/PASS claims, duplicated instructions, full files
when a symbol/range suffices, repeated artifact logs, unused MCP schemas,
summaries that silently replace raw evidence, and unrelated history from other
workstreams.

## Acceptance

A context optimization is accepted only when task correctness and evidence
fidelity stay equal or improve. Token/output size and wall time are useful
metrics, but never trade against missed findings, authority errors, hidden-info
leaks or weaker verification.
