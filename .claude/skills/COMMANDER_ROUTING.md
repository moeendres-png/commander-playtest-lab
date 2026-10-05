# Commander Simulator Next — Claude skill routing

This directory is an on-demand Claude workflow layer. It supplements, and never
replaces, `AGENTS.md`, the current execution-authority document, or active
workstream contracts.

## Current project mode

The overall end product is greenfield, but the current engineering environment is
**brownfield qualification/integration work** across an existing Lab repository and
existing engine repositories. For current work:

1. `prime-codebase` — orient on the actual current repository/source lock.
2. `plan-architecture` in **brownfield mode** — decide how a new capability lands
   in the existing system without re-deciding settled project authority.
3. `piv-slice-epic` / `piv-plan-implementation` — create bounded, dependency-aware
   work packets where useful.
4. `piv-investigate-issue` → `piv-implement-issue` for defect/RCA work.
5. `piv-validate`, `piv-review-changes`, and preferably a fresh-context
   `piv-review-pr` before integration.
6. `rules-check-drift` checks whether durable agent policy became stale; it is
   advisory and must not rewrite `AGENTS.md` without explicit adjudication.

## PRD usage

`plan-create-prd` is upstream greenfield-first. It is useful here only for the
**product-level intent of Commander Simulator Next or a genuinely new product/epic
boundary**. Do not use it to replace the existing mission, Source Truth, Rules
Authority, or current #479 issue contracts. Current brownfield implementation work
should normally start from the existing mission/epic/issue plus `plan-architecture`.

## Imported skills intentionally not treated as authority

- Generic PIV branch/PR workflows must still obey active ownership and source-lock rules.
- A green test suite does not automatically imply Qualification PASS.
- Human/agent review language in upstream skills does not weaken project-specific
  evidence, Rules, security, merge, Provider Selection, or Freeze gates.
- Any conflict resolves in favor of `AGENTS.md` and the newest active contract.


## CI / gate / remediation routing

For material engineering changes, CI/check work, remediation, or pre-merge
adjudication, prefer this sequence when applicable:

1. `systematic-debugging` — use on a failing test/build/workflow or unexpected
   runtime result before proposing fixes. Establish root cause and defect layer.
2. `post-patch-validation` — use after a defect/gate blind spot has a patch and a
   meaningful vulnerable baseline. Demand baseline reproduction plus an independent
   root-cause variant, preserved behavior, regression/security checks and suite evidence.
3. `differential-review` — use for material source/workflow/qualification/test diffs
   to inspect history, blast radius, coverage, regressions and adversarial scenarios.
4. `agentic-actions-auditor` — additionally use whenever AI-agent GitHub Actions,
   prompts, permissions, sandbox/tool access, reusable workflows or untrusted event
   data are touched.
5. `commander-quality-gate` — use as the Commander-specific integration controller:
   source lock, project-native mechanical floor, required evidence lenses, bounded
   repair, exact-head CI, drift adjudication and protected merge.
6. `verification-before-completion` — always apply before claiming a fix, gate,
   PR, milestone or workstream complete.

The specialized skills are complementary, not interchangeable. A `commander-quality-gate`
run may invoke several of them depending on impact. None of them turns advisory
review into Rules qualification or overrides the active issue contract.


## Context and navigation efficiency routing

1. repo-map — first broad orientation with a 512–1024 token structural map.
2. Serena/LSP — targeted symbol definitions, references and semantic navigation.
   The committed Claude Serena project is read-only and memory-disabled.
3. find-docs — current external library/API docs via Context7 only when material.
4. bounded-context-pack — portable compressed snapshot only when a bounded
   multi-file/cross-repo review genuinely needs one.
5. context-engineering — when changing prompts, skills, routing, MCP/tool
   configuration, or when context bloat/drift is observed.

Efficiency views never promote evidence. Use raw authoritative source/output for
material PASS/FAIL claims.
