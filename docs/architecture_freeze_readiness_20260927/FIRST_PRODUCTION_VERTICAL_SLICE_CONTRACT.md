# First Production Vertical Slice Contract (POST-FREEZE WORKSTREAM SPEC)

Status: specified by WSR24; executed only after Architecture Freeze + production
repository bootstrap. This is the first real implementation workstream, and it
must be a real game slice — not a toy parser.

## 1. Objective

One complete, reproducible 4-player Commander game: real Rules provider,
real 100-card decks, external decision control, terminal state, replay proof.

## 2. Hard requirements (all must hold; each is an exit gate)

1. Selected real Rules provider at the Frozen ADR pin, in a separate provider
   process (one-game-per-process).
2. Real Commander deck import (four 100-card decks); engine validates legality
   (colour identity, card names); import failures fail closed.
3. Four principals with principal-scoped observations (no cross-principal
   leakage; honeycard negatives green).
4. External decision control (`external_control=true` mandatory); every
   engine-offered decision answered with exactly an offered option; no
   internal provider AI fallback (N3 test).
5. Authoritative engine legal Decision Options on every decision; adapter
   transports unchanged (shim provenance test green).
6. Explicit Rules-RNG authority: engine-owned seeds recorded per game; no
   harness-side randomness (RNG-ownership test).
7. Semantic replay: decision tape + Rules-RNG record + semantic events +
   terminal state; clean-process twin reproduces the terminal state hash.
8. Deterministic decision tape: the same tape + seed re-driven through a
   clean process reaches the same terminal state hash.
9. Game lifecycle runs to a terminal state (a player wins / all opponents
   eliminated / draw by Rules) — concession only if Rules-driven, never
   harness-forced.
10. Explicit crash/timeout/protocol-failure handling: typed terminal failure
    with evidence bundle if the provider process fails; never silent resume.
11. Process isolation: provider process boundary verified; no shared mutable
    engine state across games.
12. Real-card execution: game played with real cards under full Rules (pilot
    strategy may be deliberately simple — simple strategy must NOT become
    simple legality: the pilot may choose poorly but may never invent what is
    legal).
13. Debugging/evidence artifacts: per-game bundle (seed, tapes, events,
    terminal facts, hashes, identities) sealed without hidden-info leakage.

## 3. Exit gates carried from WSR24 (timing per Coordinator slots)

- SLOT-08 item: the effective 29-card actual-card corpus, if deferred to the
  slice — the slice is NOT complete until each corpus card is individually
  executed on the production lane.
- SLOT-09 item: per-fixture clean-process replay twins, if deferred — the
  slice is NOT complete until the twin matrix is green.
- SLOT-04 scope: the slice implements exactly the Coordinator-ruled channel
  scope; deferred channels are explicit fail-closed unsupported paths.

## 4. Pilot simplicity boundary (binding)

The initial pilot SHOULD be deliberately simple (e.g., priority-pass-first
legal heuristics chosen from offered options, scripted mulligan rule) so the
slice tests the Rules/bridge/replay machinery, not strategy strength. The
simplicity boundary is absolute: the pilot selects only among
engine-generated options presented through the decision contract. Any pilot
code path that constructs, filters-into-existence, or defaults an option is a
boundary breach and fails the slice.

## 5. Failure semantics for the slice

- Slice FAIL: any exit-gate breach, any N1–N8 invariant breach, any falsifier
  from SELECTED_PROVIDER_IMPACT_TEMPLATE §5.
- Slice BLOCKED: provider-process crash/timeout with completed evidence
  bundle — diagnosable, resumable after repair, never reclassified as PASS.
- Slice PASS: all 13 requirements + carried gates green with sealed evidence.

## 6. Non-goals (explicitly out of the slice)

Performance optimization, pilot strength, deckbuilding optimization, batch
runner scale-out (single-game determinism first), 6P, any second provider.
