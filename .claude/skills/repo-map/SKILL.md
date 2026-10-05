---
name: repo-map
description: Ranked, token-budgeted symbol map for fast codebase orientation before broad file reading. Use for unfamiliar modules, refactors, review fan-out, or whenever the alternative is reading many files just to locate important entry points. Navigation aid only; never treat regex extraction or ranking as correctness/evidence coverage.
---

# Repo Map

Run the bundled zero-dependency mapper before opening many files.

    python .claude/skills/repo-map/scripts/repo_map.py . --budget-tokens 512
    python .claude/skills/repo-map/scripts/repo_map.py . --budget-tokens 1024 --json
    python .claude/skills/repo-map/scripts/repo_map.py path/to/subtree --budget-tokens 800

Start at 512 tokens. Raise the budget only when the map is insufficient. If the
workstream already identifies a bounded subtree, map that subtree rather than
the whole repository.

The mapper extracts definitions and references with language-specific regexes,
builds a file-reference graph, ranks centrality with PageRank, and emits only the
highest-ranked symbols until the approximate token budget is exhausted.

## Commander boundaries

- Result classification: NAVIGATION_ONLY.
- Verify material symbols/callers with source, Serena/LSP, Git and tests.
- Generated/vendor code can dominate rankings; constrain the root instead of
  blindly increasing the token budget.
- Missing symbols are not evidence of absence; use semantic/native search.
- The bundled mapper is byte-identical to its pinned MIT upstream source.

See .claude/skills/AGENT_EFFICIENCY_PROVENANCE.md.
