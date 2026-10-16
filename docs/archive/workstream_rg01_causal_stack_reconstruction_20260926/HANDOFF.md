# L4 — RG-01 Causal Stack Reconstruction

## Terminal Handoff

**Disposition:** COMPLETE / PASS

**Branch:** `sol/rg01-causal-stack-reconstruction-20260924`

**Exact predecessor L3:** `d254855f5ca70f6c3d2fb3cf5fe6be9f21cbda2a`

**Runtime-qualified L4 head:** `ab4c0c259a84aae5715efd3d0f0340ca417a3f16`

**Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd`

**Draft PR:** #245, stacked on `sol/rg03-temporal-driver-20260924`

**WORKTREE:** NOT_AVAILABLE_IN_CONNECTOR_EXECUTION

**ARCHITECTURE_FREEZE:** NOT CLAIMED

**PRODUCTION_PROVIDER:** NOT SELECTED

## Work Completed

Implemented causal stack reconstruction without direct stack insertion.

- Added `XmageCausalStackReconstruction`.
- Frozen fully-cast stack frames are converted only into a pre-causal restoration state.
- Source cards exist in hand before reconstruction.
- Frames are recreated bottom-to-top exclusively through authoritative live XMage cast/activate/trigger/copy procedures and externally selected current legal options.
- Semantic stack identity binds to exact injected source UUIDs and native StackObject UUIDs; card-name matching is not used as identity.
- Targets, controller, order and selected modes are verified against the reached native stack checkpoint.
- Intermediate target/mode/mana/payment decisions must be supplied explicitly from the current offered decision.
- Priority rotation used to hand priority to the next historical caster is exact scripted `pass_priority`; no first/random/default fallback exists.
- Unsupported control-divergent historical stack sources fail closed for L5 rather than fabricating access/control.
- No `SpellStack.push`, fabricated `Spell`/`StackAbility`, manual target injection or manual `resolve()` is used by the reconstruction implementation.

## Actual-Card / Mechanism Qualification

`XmageCausalStackReconstructionTest` — 5 PASS:
- ordinary targeted Lightning Bolt reconstruction at 3P/4P/5P;
- modal Burn Down the House with native mode selection;
- nested Counterspell -> Lightning Bolt with exact lower native stack target;
- same-seed fresh-session semantic stack replay;
- fail-closed invalid/control-divergent frozen stack.

`XmageCausalStackMechanicsTest` — 7 PASS:
- activated ability created by native activation with real target + sacrifice cost;
- triggered ability generated after real creature resolution;
- Flare of Duplication creates a native copied spell;
- original-source/copy semantics are exercised through native copy handling;
- Morph cast produces a native face-down spell;
- target becoming illegal and all-target-illegal/fizzle behavior through native resolution;
- Counterspell counters the exact lower spell;
- player-leaves-game removes the leaver-owned spell and survivors continue.

Together these cover the required L4 mechanism classes including activated, triggered, copy, face-down, illegal target/fizzle, countered spell and leaver cleanup.

## Initial Remediation

The last L4 fix aligned a stale test assertion with the native concession contract:
- after a player leaves, a previously parked decision frame may remain observable until the game thread retires it;
- this does not restore authority to the leaver;
- the correct native proof is that concession/action authority for that player is gone and their owned stack object has been removed.

No Rules-Core or cleanup shortcut was added.

## Exact Runtime Evidence

All workflows on exact runtime head `ab4c0c259a84aae5715efd3d0f0340ca417a3f16` completed SUCCESS:

- CI `36224048863`
- External XMage Integration `36224048791`
- XMage Full Game Conformance `36224048813`
- XMage Real 4P Technical Smoke `36224048786`
- H4 Docker Materialization `36224048835`

External bridge job `108354541834`:
- full bridge suite: **258 tests, 0 failures, 0 errors, 1 intentional skip**
- `XmageCausalStackMechanicsTest`: 7/7
- `XmageCausalStackReconstructionTest`: 5/5
- `XmageTemporalProgressionDriverTest`: 7/7
- `XmageTemporalAdvancedProgressionTest`: 6/6
- `XmageCommanderDamageRestorationTest`: 8/8
- Maven BUILD SUCCESS
- Phase-6 differential replay: PASS
- downstream external bridge regression batteries: PASS

H4 Docker:
- preflight PASS
- Forge lane PASS
- XMage canonical direct-source build PASS
- Lab bridge verify/staging PASS
- canonical XMage image build/provenance/handshake/negative controls PASS
- overall workflow SUCCESS

## Evidence Classification

- branch ancestry/source lock: DIRECTLY_VERIFIED
- stack reconstruction runtime behavior: DIRECTLY_VERIFIED + TECHNICALLY_CONFORMANT
- absence of direct stack insertion in implementation: CODE_DERIVED
- actual-card target/mode/cost/copy/trigger/fizzle/counter/leaver semantics: DIRECTLY_VERIFIED
- semantic fresh-session replay: DIRECTLY_VERIFIED
- unsupported control-divergent stack history: fail-closed, not PASS

## PASS / FAIL / UNKNOWN

**PASS:** `RG01_CAUSAL_STACK_RECONSTRUCTION = PASS`

**FAIL:** none in bounded L4 scope.

**UNKNOWN / deferred:** exact owner/controller-divergent causal history remains L5; hidden-state reconstruction remains L7.

## Remaining Blockers

None for L5 start.

## Outputs

- Draft stacked PR #245
- `XmageCausalStackReconstruction`
- causal stack mechanism/regression suites
- this handoff

## Dependencies Unblocked

L5 may start only from the exact terminal head produced by this documentation-only handoff commit.

## Exact Next Action

Create/resume `sol/rg04-control-divergence-20260924` from the exact L4 terminal head. Reconstruct owner/controller divergence through genuine native continuous control-changing effects, never direct controller-field assignment.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
