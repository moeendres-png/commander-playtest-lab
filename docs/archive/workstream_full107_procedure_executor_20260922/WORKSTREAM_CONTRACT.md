# Workstream Contract — FULL107 native-procedure + decision-script executor (2026-09-22)

## Objective

Execute frozen NATIVE decision scripts on restored states through projected
legal actions only: scripted keeps/passes (proven transport), semantic
selection → exact-one-match action resolution (fail closed both directions,
forbidden fallbacks prohibited), native execution with engine-owned costs /
targets / timing, required/forbidden event assertion from the executor
observation log, and terminal-postcondition verification via native
readback. First target: WS05-CMD-TAX-2 (cast Rograkh with {4} tax, no
targets/modes). No mapping promotion in this workstream until execution is
proven; then promote only exactly executed fixtures with evidence.

## Source Lock

- Base: `origin/main` `57caa2dc7ad63c8d54c43097a6ac92e0433fdc3e`
  (tree `cfd97ef9ae71ae608f3127de6d34c9cbe853bc50`).
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Engine (READ-ONLY, no pin change): xmage maven `1.4.61`.
- Depends on: WS2 restoration capability (merged PR #218).
- This branch: `cpl/full107-procedure-executor-20260922`.
- This worktree: `/home/moeen/code/ws-full107-procedure-executor-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- Decision-script executor: pregame plan + per-step semantic selections
  resolved against projected actions; scripted priority passes; event-log
  required/forbidden assertion; post-execution readback vs terminal
  postconditions.
- Cast-action projection gap analysis at TAX-2 arrival (targets/modes/choice
  classes known-incomplete); smallest compliant projection extension if the
  gap is local, else fail-closed disposition with exact residual.
- Actual-card runtime tests (TAX-2 first; then TAX-4/PARTNER-TAX by the same
  path if green); bridge suite stays green.
- Contract/state/docs; scoped validation; commit + push + PR.

## Out of Scope

- Mock-card injection (never); frozen WS47 mutation; engine-repo edits; pin
  changes; mapping reclassification (separate adjudicated step after proof);
  provider/freeze decisions; stack-spell/hand-identity/hidden/temporal
  dimensions (WS2 fail-closed set stands).

## Ownership

Single writer: this session on this branch/worktree only. All other
worktrees/branches read-only. WS1/WS2 closed.

## Hard Gates

- Pilots choose only among engine-authorized discretionary alternatives;
  zero/multiple semantic matches fail closed; forbidden fallbacks
  prohibited; unsupported production paths fail closed.
- Engine owns costs, mana, targets, timing, stack, SBAs, layers; no
  `sa.resolve()` substitutes, no outcome injection, no legality bypass.
- Credit requires: exact construction match (WS2) + executed script with
  asserted required events + terminal readback match. Parsing, static
  checks, or green CI alone award nothing.
- Bridge suite green, ruff clean (python touched only if needed), retention
  predicates kept green (re-baseline by the R24 process if owned bytes move).

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no first/random/default option selection; no
requested-option filtering reconstructing legality; no partial-credit
masquerading; no silent setup correction during execution.

## Evidence Requirements

Per-fixture execution transcripts (executor observation log), required-event
assertion results, post-execution readback + terminal-postcondition compare,
per-step match records (exact-one proofs).

## Stop Conditions

Complete when the technically achievable executor subset + first fixture
execution(s) are integrated on main with green post-merge CI, or a genuine
technical/authority blocker (fail closed with exact residual).
