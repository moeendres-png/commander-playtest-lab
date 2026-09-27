# Phase 1 Closeout — P0 Native State Restoration Closure

Source lock: `2231ff4b`. Terminal condition (§9): every blocked-fixture state
dimension classified as now-supported+proven, still-unsupported-with-reason,
or requiring engine-side remediation. Met below.

## Dimension dispositions

| Dimension | Fixtures | Classification | Disposition |
|---|---|---|---|
| hand_identity | 4 (`MP-PRIO-3/5`, `MP-TRIG-3/5`) | `WRAP` + `HARDEN` | **IMPLEMENTED_AND_RUNTIME_VERIFIED** (v2) |
| stack_spells / stack_objects | 11 | `REFERENCE_ONLY` | fail closed (`UNSUPPORTED_ZONE`); executor-driven follow-up |
| commander_damage | 5 | `REFERENCE_ONLY` | fail closed (`UNSUPPORTED_DAMAGE_MATRIX`); engine-side follow-up |
| temporal non-v1 points | 7 | `NEW_IMPLEMENTATION_REQUIRED` (deferred) | fail closed (`UNSUPPORTED_TEMPORAL_POINT`/step); progression-driver follow-up |
| control_divergence | 2 | `REFERENCE_ONLY` | fail closed (`UNSUPPORTED_CONTROL_DIVERGENCE`, probe-proven) |
| already-supported subset | 4 (`ELIM-OWNED-3/PRIO-3/TURN-3`, `ELIM-5`) | `REUSE_AS_IS` | no code change; Phase 2 exact execution |
| library/facedown/counters/attachments/tapped/poison/revealed | 0 blocked fixtures require | — | no expansion (theoretical completeness refused); fail closed stands |

Global `starting_state_injection_supported` remains `false` (asserted by
`globalCapabilityFlagStaysFalse`). Dimensions schema bumped
`1.0.0 → 1.1.0` (hand moved to supported, library stays unsupported).

## v2 hand implementation (A–E proofs)

- **Construction**: per-player hand lists through `Game.cheat` hand slot (same
  qualified primitive as battlefield; `WRAP`, no new primitive).
- **Native readback**: per-seat sorted hand identity, engine-direct (test-only;
  pilot observation untouched — redactor still counts-only).
- **Digest/compare**: requested hand ⊆ observed hand (superset justified: the
  scaffolding vehicle's opening seven + natural draws are harness content) +
  `hand_count >= requestedHand`; public zones keep exact multiset equality.
- **Genuine transition** (`trig3HandIdentityMatchesNativeReadback`, frozen
  `WS05-MP-TRIG-3`): P1's restored Grizzly Bears is offered through the
  engine's own cast-legality pipeline (2 Forests ⇒ `{1}{G}` payable); a real
  priority pass advances priority, preserves the hand card and 40-life totals.
- **Adversarial negatives**: `restoredHandHoneycardNeverLeaksToWrongPrincipal`
  (Shivan Dragon honeycard in P2's hand invisible to non-P2 pilot views,
  opponent `hand` arrays structurally absent); `rejectsLibraryIdentity…`
  (library still `UNSUPPORTED_ZONE`); pre-existing stack/temporal/control
  negatives untouched and green.

## Incidental systemic fix (proven by new tests)

`materializeCards` now calls `XmageDeckImporter.ensureRepositoryReady()` first.
Before, card-repository readiness depended on JVM test-execution order (new
tests exposed `UNKNOWN_CARD_NAME` on first-run paths); the importer's own
comment documents the routine as "shared with card materialization". No
behavior change for ready repositories; fail-closed codes preserved.

## Runtime evidence (current bytes, source lock `2231ff4b` + worktree HEAD)

- `XmageNativeStateRestorationTest`: 17/17 green.
- Neighbors: `XmageDigestCreditTest` 9/9, Tax 2/2, Card02 1/1, Partner 6/6,
  HiddenInformation 1/1, Start2 suite 1 skipped (pre-existing disabled
  blocker record) — all green.
- Impact: restoration tests requalified (semantically affected); digest/
  executor/hidden suites re-run (structurally affected, unaffected results
  retained); all other evidence retained.

## Unblock tally from this phase

- Newly restorable: `WS05-MP-TRIG-3`, `WS05-MP-TRIG-5` (hand-only gap closed;
  downstream `NATIVE_CAST_SPELL` executor work remains Phase 2 scope).
- `WS05-MP-PRIO-3/5`: hand closed, stack still blocks (stay `NOT_RUN_BLOCKED`).
- 4 already-supported cells ready for Phase 2 exact execution with zero code
  change. All other blocked cells keep exact fail-closed reasons above.
