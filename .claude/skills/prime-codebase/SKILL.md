---
name: prime-codebase
description: Builds a fast, token-bounded understanding of the current repository before planning or implementation. Use at session/workstream start or when entering an unfamiliar area. Starts from source identity and repo-map, then reads only task-relevant files instead of dumping the repository.
---

# Prime Codebase — Commander Edition

## 1. Lock current source

Read AGENTS.md, the active workstream/campaign contract, and only the routed
policy modules required by that task. Then record:

    git status --short --branch
    git rev-parse HEAD
    git rev-parse HEAD^{tree}
    git log -8 --oneline

Fresh source identity outranks historical summaries.

## 2. Build a compact map

    python .claude/skills/repo-map/scripts/repo_map.py . --budget-tokens 512

Raise to 1024 only if insufficient. If the task already names a subtree, map
that subtree instead of the whole repository.

## 3. Read just in time

Read only the task/state files named by the workstream, build/config files needed
for the touched surface, symbols surfaced by repo-map/Serena/LSP/Git/failing
tests, and architecture docs whose trigger directly applies.

Do not recursively read README/docs/source trees merely to feel oriented.

## 4. Verify relationships

Use Serena/LSP, Git history, targeted grep/ast-grep and tests to verify callers,
interfaces and invariants that matter. Repo-map is navigation only.

## Output

Return a concise orientation: Source Lock; objective/mutation surface; relevant
architecture and entry points; likely dependency/caller surface; discriminating
tests/evidence; unresolved UNKNOWNs; exact next action.
