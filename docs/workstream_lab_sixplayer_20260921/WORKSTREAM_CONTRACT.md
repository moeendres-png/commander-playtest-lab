# Workstream Contract — R19 Lab XMage Six-Player Parity (2026-09-21)

## Objective

Bring the Lab XMage line to 2–6P parity with the Forge line (R16):
verify xmage-1.4.61 engine 6P capability; widen Python + Java gates
2–5 → 2–6 (minimal); qualify lifecycle + actual-card + hidden-info +
determinism at 6P; move 7+ fail-closed boundary; full requalification.
Mirrors R16 scope on the successor-integration line.

## Source Lock

- Base: `faffab8493c45469adf61824a582cf1ba7637fa0` (successor tip).
- This branch: `cpl/xmage-six-player-20260921`.
- This worktree: `/home/moeen/code/ws-lab-six-player-20260921`.
- Repo `moeendres-png/commander-playtest-lab`. No Forge/mage edits.
  No push/merge.

## In Scope

- Engine 6P probe (xmage native create/start at 6 seats).
- Gate widening (Python Field/range/MIN-MAX/lane + Java gate/message)
  ONLY if engine proves capable; else keep + seal boundary.
- 6P lifecycle, actual-card spot (combat/concession), hidden-info spot,
  twin determinism spot, 7+ fail-closed negatives.
- Full requal: engine-bridge mvn + impacted python suites + live 6P
  gate spot.
- Evidence (root cause, matrix delta, seal, handoff).

## Out of Scope

- 7P+ support; Lab main merge; stale-consumer migration; decks;
  FULL107; promotion; Freeze; Provider.

## Ownership

Single writer: this session on this branch/worktree only. All other
Lab worktrees/branches read-only (physical-pool/three-deck especially).

## Dependencies

- Successor tip (2–5P established); R16 Forge precedent (same pattern).

## Hard Gates

- 6P must never weaken 2–5P correctness (full requal green).
- Rules Authority: engine owns legality/seats/RNG; no second Rules
  Engine; unsupported fail closed; UNKNOWN stays UNKNOWN.
- No weakening to pass; fail-before + root cause for any repair.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no duplicated-deck fake six seats (distinct
decks/handles required); no truncation; no green-suite equality.

## Evidence Requirements

Engine verdict → gate decision → per-capability dispositions →
regression → seal.

## Persistence

Per validated milestone: scoped validation, state update, focused local
commit. End with §13 handoff.

## Stop Conditions

Stop only when: 6P qualified with green requal, or a genuine technical
gate is proven (engine cap) with fail-closed preserved. Remediable
failures are diagnostic.
