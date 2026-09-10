# RQ-A1 — Argentum Unknown Ledger

Every material unknown encountered. `UNKNOWN != PASS`. Items are ordered by qualification significance. Each names the exact next probe that would resolve it.

## A. Rules-correctness unknowns (require official-rules validation + Sol High adjudication)

- U1. Correctness of all 23 rules mechanisms (priority/stack/costs/mana/targets/combat/SBAs/triggers/replacement/layers/copy/control/zones/LKI/simultaneity/elimination/concession). Presence + unit tests are established; `EXTERNALLY_RULE_VALIDATED` is established for none. Next: qualification campaign with official CR/Oracle/rulings cross-check.
- U2. Correct CR 800.4 behavior for the two documented `PlayerLeavesGameProcessor` simplifications (remaining players' LTB triggers off mass removals; static-ability exile of leaver-controlled objects). Next: `AUTHORITY_GATE: MTG_RULES` + targeted tests.
- U3. Per-opposing-teammate trigger fan-out (`TriggerMatcher.kt:1718` fires once). Next: `AUTHORITY_GATE: MTG_RULES` + 2HG test.
- U4. Loyalty-excess / battle-above-defense-excess damage (explicitly unmodelled). Next: confirm whether any Commander-relevant card needs these paths; targeted tests if so.

## B. Coverage-measurement unknowns

- U5. Card↔behavior-test linkage: which of the 13,915 declared names has a behavior-oriented test. Next: cross-reference scenario-test card mentions vs declarations (mechanical script).
- U6. Live set-completion percentages + Scryfall cache freshness (cache outside repo). Next: run `scripts/card-status` in an environment with fresh Scryfall data.
- U7. Per-era set-directory listing beyond 1993-1999 (24 dirs); per-set draft/extra denominators. Next: extend the count script.
- U8. Per-card multiplayer/Commander behavior tests: none found; unknown whether any era scenariotest uses >2 seats. Next: grep era tests for multi-seat helpers.
- U9. Whether all 18,345 card files compile at the lock (only executed-test-scope modules were compiled). Next: full `:mtg-sets` compile (expensive cold; cheap warm).

## C. Player-count unknowns

- U10. 5-player and 6-player runtime behavior (no tests found; code unbounded). Next: 5-/6-seat smoke + Commander pod tests (new tests would be *qualification* work, permitted only under a qualification workstream — NOT under RQ-A1's no-repair/no-implement gate; running *existing* tests at other counts is allowed but none exist).
- U11. 2–5P technical conformance in the qualification sense for every evidenced count. Next: formal conformance campaign; 4P results must not be extrapolated.

## D. Decision-seam unknowns

- U12. Starting-player live seam (config-only observed). Next: confirm whether production needs it as a decision (likely yes for tournament play) and where it would live.
- U13. Voting / will-of-the-council (no implementation found). Next: confirm absence via broader search (card corpus may reference it: `rg -il "vote|council" mtg-sets`), then record as coverage gap.
- U14. `web-client/src` option-filtering behavior (e.g. PlayLand-face collapsing hazard noted in stale doc). Next: trace client action construction; confirm no production-reachable filtering drops legal variants.
- U15. Trigger-ordering UI per path (option vs order decision). Next: map each `TriggerProcessor` pause site to its question type at runtime.

## E. Hidden-information unknowns

- U16. No-leak property over live traffic (logs/errors/events/replay viewers). Authorities exist; adversarial verification absent. Next: masked-vs-full differential test across perspectives (existing `ObservationVisibilityTest` + `GameMaskingTest` are the starting point, not the conclusion).
- U17. Hidden-name leakage in error strings. Next: grep error paths for entity-name interpolation; test with hidden entities.
- U18. Replay-viewer projection (stored replays hold full inputs server-side). Next: confirm viewers can only access projected frames.

## F. RNG/replay unknowns

- U19. Seed+input round-trip fidelity (`EXACT` claim). Next: reconstruct N games from `CompactReplay`, compare digests — small, well-defined, recommended first runtime probe inside qualification.
- U20. RNG consumption-order stability across versions (seed-only replay sufficiency). Next: same round-trip across two builds.
- U21. RNG statistical quality (SplitMix64 is fine in principle; not measured). Next: standard test battery if qualification demands it (low priority — determinism/control matter more than statistical strength here).
- U22. `AbilityId` process-global counter impact on cross-process replay identity. Next: normalize-or-thread decision + test.

## G. Process unknowns

- U23. `docs/engine-server-interface.md` staleness blast radius (which consumers, if any, rely on it). Next: grep references; either refresh or mark superseded (doc work, allowed in a follow-up workstream).
- U24. Full-suite green status at the lock (only narrow scopes executed in RQ-A1). Next: CI history or broader runs under a qualification workstream.
- U25. Throughput/headless performance numbers (GameLimits/replay caps observed; no benchmarks run). Next: measure only if simulation throughput becomes a selection criterion.

## Explicit non-unknowns (closed in RQ-A1)

- Source locks (LOCK_OK). No action-ID seam (rejected claim). Assay≠behavior (rejected implication). Partner/background/companion absent (negative searched). Range-of-influence absent (negative searched). Voting absent from engine (pending corpus cross-check U13). Engine revision token absent (negative grepped). `EntityId.generate()` absent from live paths (searched). Production-reachable `sa.resolve()`/`AbilitySub` substitutes (none found in searched prod paths).
