# Workstream Contract — FULL107 CARD_02 execution (2026-09-22)

## Objective

Execute CARD_02 faithfully: restore the exact 4-commander starting
state, execute the scripted P1 commander cast through engine-enumerated
legal actions with engine-owned resolution, and verify required events
plus terminal postconditions from native facts, including construction
digest equality for this fixture. Execution evidence only; NO mapping
promotion (forbidden by the grant while gated).

## Source Lock

- Base: `origin/main` `8da8a502a927b5e85d7d4c0f8456b300cdf8c037`.
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Engine (READ-ONLY, no pin change): xmage maven `1.4.61`.
- Depends on: WS2 restoration, executor cast routing, digest comparison
  (all merged).
- This branch: `cpl/full107-card02-execution-20260922`.
- This worktree: `/home/moeen/code/ws-full107-card02-execution-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- CARD_02: 4P Rograkh commanders (casts 0), no battlefield, turn-1-main;
  scripted cast-commander P1 exact-one match; fresh count implies no tax
  and no payment decisions (fail closed if any appear); resolution via
  passes; terminal (battlefield presence, count 1, no tax).
- Construction digest verification for CARD_02 (same gate as the six).
- Scoped validation (bridge suite, guard, predicates, manifests) +
  commit + push + PR.

## Out of Scope

- Frozen WS47 mutation; engine-repo edits; pin changes; mapping promotion
  (explicitly forbidden by the grant while gated — this workstream proves
  execution + digest, promotion is a later adjudication); START-2
  (separate workstream next); provider/freeze decisions.

## Ownership

Single writer: this session on this branch/worktree only. All other
worktrees/branches read-only.

## Hard Gates

- Exact frozen state/procedure/events/postconditions; scripted step only.
- Engine owns legality/costs/timing/payment/resolution/SBAs/layers; no
  injection, fabrication, first-option, silent skips, internal AI.
- No digest fabrication; digest equality required for the credit claim
  (fail closed otherwise).
- Bridge suite green, guard green, predicates 47/47, manifests verify.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no PASS from construction alone (execution with
events + terminal required); no promotion in this workstream.

## Evidence Requirements

Execution transcript (construction MATCH + digest equality + cast +
resolution + terminal), event assertions from native facts, digest bytes
compared to frozen hex.

## Stop Conditions

Complete when CARD_02 execution + digest are proven and integrated with
green post-merge CI — or a genuine technical/authority blocker.
