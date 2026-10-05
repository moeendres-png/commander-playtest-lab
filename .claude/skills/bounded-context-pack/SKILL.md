---
name: bounded-context-pack
description: Creates a deliberately bounded compressed code snapshot for cross-file or cross-repository reasoning when repo-map or symbolic navigation is insufficient. Use for fresh independent reviews or integration analysis that needs a portable packet. Never pack an entire repository by default.
---

# Bounded Context Pack

Use Repomix only after the active workstream identifies the exact files/subtrees
that genuinely need to travel together.

    npx -y repomix@1.18.1 --compress --include "<comma-separated-globs>" --output "/tmp/commander-context-pack.xml"

Rules:

1. Derive include globs from the active workstream or changed surface.
2. Exclude secrets, environment files, credentials, raw private artifacts and
   unrelated generated/vendor trees.
3. Write to /tmp or run-scoped scratch, not the Git worktree, unless a durable
   artifact is explicitly required.
4. Treat compressed output as navigation/review context, not evidence.
5. Re-open authoritative source for findings affecting PASS/FAIL, Rules,
   security, hidden information, replay/RNG or merge eligibility.
6. Prefer repo-map plus Serena/LSP if they answer with less context.
7. Record included paths and source HEAD when handing a pack to a fresh reviewer.

Repomix is external and is not vendored into this repository.
