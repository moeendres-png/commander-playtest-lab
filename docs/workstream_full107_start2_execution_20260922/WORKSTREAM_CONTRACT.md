# Workstream Contract — FULL107 START-2 execution (2026-09-22)

## Objective

Execute WS05-CMD-START-2 faithfully: restore the exact starting state
(Rograkh commanders, Bears placed, life 40, seed 424242), observe the
turn-1 draw step natively (starting player P1, P1 hand unchanged = first-
turn draw skipped under the 2P rule), and verify construction digest
equality plus required events and terminal postconditions from native
facts. Execution evidence only; NO mapping promotion.

## Source Lock

- Base: `origin/main` `c03d144f00b4a7c04455f71a44611c94b9baeded`.
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Engine (READ-ONLY, no pin change): xmage maven `1.4.61`.
- Depends on: WS2 restoration + digest comparison (merged).
- This branch: `cpl/full107-start2-execution-20260922`.
- This worktree: `/home/moeen/code/ws-full107-start2-execution-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- Temporal envelope extension to turn-1 beginning/upkeep + beginning/draw
  (natural-arrival waypoints, fail closed otherwise) + readback inverse
  map for those points (explicit table, fail closed otherwise).
- START-2 test: construct + digest + draw-step observation (hand counts,
  starting player, active/priority) + terminal; negatives as needed.
- Scoped validation (bridge suite, guard, predicates, manifests) +
  commit + push + PR.

## Out of Scope

- Frozen WS47 mutation; engine-repo edits; pin changes; mapping promotion
  (explicitly forbidden); other fixtures; provider/freeze decisions.

## Ownership

Single writer: this session on this branch/worktree only. CARD_02
workstream closed after its close-out; all other worktrees read-only.

## Hard Gates

- Exact frozen state/procedure/events/postconditions; empty script stays
  empty (observation only, no decisions invented).
- Engine owns turn structure, draws, priority, SBAs; no injection,
  fabrication, first-option, silent skips, internal AI.
- Digest equality required (fail closed otherwise); no digest fabrication.
- Bridge suite green, guard green, predicates 47/47, manifests verify.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no arrival-at-main substitution for draw-step
observation (the temporal point is the obligation); no PASS without the
draw-skip fact.

## Evidence Requirements

Execution transcript (construction MATCH + digest + draw observation +
starting player + terminal), event assertions from native facts.

## Stop Conditions

Complete when START-2 execution + digest are proven and integrated with
green post-merge CI — or a genuine technical/authority blocker.
