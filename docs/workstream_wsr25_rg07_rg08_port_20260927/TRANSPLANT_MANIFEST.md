# WSR25 Camp-Carrier Transplant Manifest (2026-09-27)

Immutable source: `camp/rg-closure-20260925 @ ca8950e59876bf1de2dfc3b7c74e94446d1dded1` (provenance, never merged/rebased).
Destination branch: `wsr25/xmage-rg07-rg08-current-pin-evidence-port-20260927` from `origin/main 8d2aacd5`.
Current-main production is authority; camp production mods are NOT ported.

## Ported (test-only, zero production change)

1. `engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameHexOfferTest.java`
   - Old blob commit: `22121f8c` (RG-07 Lab, 6/6 on camp). Destination: same path.
   - Mode: BYTE-COPIED verbatim. Compiles unchanged against current-main 11-arg `Plan`
     constructor + `XmageFullGameSession`/`XmageNativeStateRestorationTest` helpers.
   - Justification: current main already contains equivalent native offering behavior
     (RG-07 ancestor of `b1959698`); only qualification was missing. Port proves it.
   - Tests: `XmageFullGameHexOfferTest` 6/6 green on current pin (see HANDOFF).

2. `engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameReplacementTest.java`
   - Old blob commit: `684939fe` (RG-08 Lab, 8/8 on camp). Destination: same path.
   - Mode: REWRITTEN minimally (test-only): `battlefield/graveyard/handCard` helpers now
     build unique semantic keys via `semanticKey()` (card-name slug appended).
   - Justification: current-main `validatePlan` (PR #249 lineage) rejects
     `DUPLICATE_SEMANTIC_OBJECT`; camp helpers reused `obj:<zone>-<pid>-<index>` across
     different cards (e.g. Plains-0 + Mountain-0). Behavior identical; keys only.
   - Tests: `XmageFullGameReplacementTest` 8/8 green on current pin (see HANDOFF).

## NOT ported (superseded / provenance)

- `XmageNativeStateRestoration.java` camp delta (damageMatrix/libraryOrders/faceDown inline,
  ACTIVATED_ABILITY guard): `SUPERSEDED_BY_CURRENT_MAIN` — PR #249 canonical split
  (`XmageHiddenStateRestoration` L7 + commander-damage wrapper + public-view hash) covers it.
- `XmageFullGameDecisionController.java` camp delta (transcript masking): `SUPERSEDED_BY_CURRENT_MAIN`.
- `XmageFullGameTemporalDriver/StackExecution/CommanderDamage/ControlDivergence/Elimination/TemporalProgression/Ws05Temporal` + `TrigExecution` + `NativeStateRestorationTest` deltas + `FULL107_MAPPING/FIXTURE_REGISTER/generate_full107_mapping/correspondence-test` deltas: not in RG-07/08 scope; remain on camp branch as provenance.
- `docs/workstream_rg_closure_20260925/HANDOFF.md`: historical, stays on camp branch.
