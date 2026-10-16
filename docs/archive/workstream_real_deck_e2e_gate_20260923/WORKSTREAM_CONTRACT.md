# Workstream Contract — real-deck 4P end-to-end usability gate (2026-09-23)

## Objective

Determine by runtime execution whether the Commander Lab + pinned XMage
full-game path can play a real-card 4-player Commander game to terminal
Game Over under external pilots; prove replay + a 10-game isolated batch,
or identify/repair the first genuine production blocker in scope.

## Source Lock

- Base: `origin/main` `69d6beb8bc43a2cb578820e23270db3308502c65`.
- Frozen WS47 / pins: read-only, unchanged (not touched by this gate).
- Engine: xmage maven `1.4.61`, commit `db134b97` (verify at runtime).
- Decks (read-only, canonical truth): `rogshai/current` (Ishai+Rograkh,
  100 cards, photo-verified) + `kaervek/current` (Kaervek, 100 cards,
  verified list). Seats: 2× RogShai + 2× Kaervek, labeled
  REAL_CARD_TECHNICAL_USABILITY_GATE (not matchup evidence).
- This branch: `opencode/real-deck-e2e-gate-20260923`.
- This worktree: `/home/moeen/code/ws-real-deck-e2e-gate-20260923`.

## In Scope

- Reuse-first inspection; baseline build + focused tests.
- Small driver wiring around XmageFullGameRunner/batch/replay infra.
- Real-deck single game → replay → 10-game batch with classification.
- In-scope repairs (wiring, adapter, projection, handoff, orchestration).
- Required evidence artifacts (contract/state/lock/results/validation).

## Out of Scope

- Provider selection, Architecture Freeze, repin, Forge swap, new Rules
  Core, fixture semantics changes, deck-truth mutation, card-name hacks,
  outcome injection, loosened fail-closed behavior, deckbuilding.

## Ownership

Single writer: this session on this branch/worktree only.

## Hard Gates (§13)

Source identity; real 4P start; external-pilot discretion; no prohibited
fallback; hidden-info intact; seed bound; terminal Game Over; replay
match; 10 fresh-process games; failures preserved; no freeze/provider
claims. Else PASS forbidden.

## Stop Conditions

COMPLETE (single + replay + batch green with evidence) or TERMINAL
BLOCKER (provider/repin/fixture-change/secret/destructive/architecture
scope). Normal bugs are repaired, not stop conditions.
