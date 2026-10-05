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
6. `lab-ops` for day-to-day operations: compact PR/CI status, open review threads, failing-job
   lines, CI waiting, PB-03 packet summaries and real-engine row runs (token- and time-efficient).
7. `rules-check-drift` checks whether durable agent policy became stale; it is
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

Security and review support:

- `sharp-edges` — when designing or reviewing containment, qualification or policy
  surfaces (for example SecurityManager admissions or fail-open defaults).
- `fp-check` — before acting on a security or audit finding, settle whether it is a
  true or false positive with code evidence.
- `receiving-code-review` — when review threads arrive, verify each point against the
  code before changing it or pushing back.

The specialized skills are complementary, not interchangeable. A `commander-quality-gate`
run may invoke several of them depending on impact. None of them turns advisory
review into Rules qualification or overrides the active issue contract.
