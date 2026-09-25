# XMage Residual Re-Pin — Impact Adjudication

## Change

Forward-repin Commander Lab from XMage `db134b9737e951367d65ef5806ad986319cc73ab` to cumulative residual candidate `b19596980f2734496ea1896504253e1bdd2756dd`.

The Mage delta contains qualification tests plus two RG-06A production state-load surfaces:

- `Library.restoreOrderForGameLoad(List<UUID>, Game)`
- `BecomesFaceDownCreatureEffect.restoreFaceDownStateForGameLoad(UUID, FaceDownType, Game)`

RG-02, RG-07 and RG-08 did not alter ordinary production Rules semantics; RG-06A adds bounded engine-native load seams.

## Current consumers migrated

The authoritative manifest, bridge self-identity, Phase-6 provider identity, bootstrap defaults, live/full-game runners, current pin tests, and XMage CI workflows are migrated to the new exact commit. Living architecture documentation defers to the manifest rather than duplicating the SHA.

Phase-6 Commander-damage injection is additionally migrated from direct mutation of `CommanderInfoWatcher.getDamageToPlayer()` to the engine-native `restoreDamageStateForGameLoad(...)` seam.

## Historical evidence impact

The engine pin is an explicit WS232 retention predicate. Therefore a forward re-pin invalidates the historical WS232 retention result for current-use claims by design.

Policy:

- do not rewrite WS232 predicates/results;
- do not rewrite WS218 tapes;
- do not rewrite DR-CLOSURE source locks or dated evidence;
- mark current WS232 tests as superseded/skipped when the live pin differs from their sealed pin;
- create fresh successor runtime evidence under this workstream.

Historical evidence remains valid only as evidence for its historical source lock.

## Required fresh requalification

This workstream requires fresh runtime evidence on `b19596980f2734496ea1896504253e1bdd2756dd` for:

1. bridge compilation and Maven verification;
2. B3/B4-A/B4-B/B4-C/B4-D runtime regressions;
3. Phase-6 differential execution with native Commander-damage restore;
4. provider pin/capability binding;
5. full-game 4P execution and same-seed semantic replay;
6. bounded 2P/3P/5P/6P smoke and 7P fail-closed boundary;
7. hidden-information boundary;
8. real 4P deck technical smoke;
9. direct bridge-runtime reachability of the new ordered-library and face-down Mage APIs.

## Hidden-state contract boundary

The current frozen Lab requested-state contract does not encode enough authoritative information to synthesize a full library permutation or an unambiguous native face-down subtype for arbitrary frozen records. This workstream therefore does not fabricate such data and does not promote global `starting_state_injection_supported`.

The two RG-06A APIs are runtime-reached directly by bridge qualification tests. Broader frozen-state library/facedown restoration remains fail-closed until a lossless Lab contract supplies the required semantics.

## Evidence retention rule

Any later code/pin/contract/harness change touching these surfaces requires impact adjudication and targeted requalification. A historical green workflow is not inherited automatically.

ARCHITECTURE_FREEZE = NOT CLAIMED

PRODUCTION_PROVIDER = NOT SELECTED
