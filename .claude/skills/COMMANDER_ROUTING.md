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
