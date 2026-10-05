---
name: find-docs
description: Retrieves current external library, framework, SDK, CLI and tool documentation through Context7. Use for version-sensitive API syntax, configuration, setup, migration or library-specific debugging. Do not use as Magic Rules authority or as a substitute for fresh repository source.
---

# Current Library Documentation

Use Context7 on demand rather than a permanent Context7 MCP.

Pinned CLI:

    npx -y ctx7@0.5.13 library <name> "<specific query>"
    npx -y ctx7@0.5.13 docs <libraryId> "<specific query>"

Resolve the library ID first unless an exact /org/project[/version] ID is
already known. Keep one topic per query and use at most three lookups before
switching to another authoritative source.

## Commander boundaries

- Never include secrets, credentials, private deck data, proprietary source or
  raw evidence in Context7 queries.
- Prefer version-specific docs when the repository pins a version.
- Current repository source/tests outrank external docs for project behavior.
- Official Magic Comprehensive Rules / Oracle / rulings remain MTG authority.
- Record the external doc/version when it materially affects a decision.

The upstream find-docs skill is retained as SKILL.upstream.md for provenance.
