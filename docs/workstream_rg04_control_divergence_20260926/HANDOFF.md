# L5 — RG-04 Causal Control-Divergence Reconstruction

## Terminal Handoff

**Disposition:** COMPLETE / PASS

**Branch:** `sol/rg04-control-divergence-20260924`

**Exact predecessor L4:** `3f6eb944e0b137062cc5af6b5b89d1cabeeeac39`

**Runtime-qualified L5 head:** `8dd283feebde5cced91d5655a188b61040d992ca`

**Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd`

**Draft PR:** #246, stacked on `sol/rg01-causal-stack-reconstruction-20260924`

**WORKTREE:** NOT_AVAILABLE_IN_CONNECTOR_EXECUTION

**ARCHITECTURE_FREEZE:** NOT CLAIMED

**PRODUCTION_PROVIDER:** NOT SELECTED

## Work Completed

Implemented causal owner/controller divergence using only genuine XMage control-changing cards/effects.

- Added `XmageControlDivergenceReconstruction`.
- The implementation never assigns a Permanent controller field directly and never injects a continuous effect.
- Exact live spell offers are bound by native source-card UUID.
- Every target and mana/payment choice is supplied explicitly from the current authoritative decision.
- Priority hand-off uses exact offered `pass_priority` actions only.
- Resolution is native; the engine creates/removes control-changing continuous effects.
- Owner/controller assertions are read back from authoritative native permanents.
- L3 temporal progression is reused to reach another actor's legal main phase without clock mutation.

## Actual-Card Qualification

`XmageControlDivergenceReconstructionTest` — 7 PASS:

1. persistent `Control Magic` control and controller-leaves cleanup;
2. owner leaves while opponent controls the permanent;
3. temporary `Act of Treason` expires through native end-of-turn cleanup;
4. overlapping `Control Magic` effects use native timestamp/layer behavior and revert when newest controller leaves;
5. `Switcheroo` exchanges controllers using an exact two-target native selection;
6. stolen genuine Commander preserves owner identity and native `CommanderInfoWatcher`;
7. zone change via real `Unsummon` clears the control effect using normal new-object/owner-zone semantics.

## Initial Failure / Remediation

The first L5 runtime attempt at `72916b17624ff2b8a08f65589cbbf46363364760` failed five test cells. All were test/harness contract defects, not Rules-Core defects:

- `Switcheroo` and later progression hit native decisions requiring exactly 2 selections while the harness submitted one;
- concession proposals omitted the already-required `player_id`;
- the `Act of Treason` expiry assertion observed only the integer turn increment, before XMage had completed the relevant cleanup/turn transition.

Remediation on `8dd283feebde5cced91d5655a188b61040d992ca`:

- exact native minimum-selection cardinality is honored through explicit `selected_option_ids`;
- cleanup-discard multi-selection uses explicit semantic `name|zone_index` keys and fails closed on ambiguity;
- concession uses the existing principal-bound `actor_id == player_id` contract;
- temporary-control expiry is asserted only after native progression reaches the next player's actual precombat main.

No production Rules logic was weakened or bypassed.

## Exact Runtime Evidence

All five workflows on exact runtime head `8dd283feebde5cced91d5655a188b61040d992ca` completed SUCCESS:

- CI `36227015287`
- External XMage Integration `36227015292`
- XMage Full Game Conformance `36227015275`
- XMage Real 4P Technical Smoke `36227015273`
- H4 Docker Materialization `36227015297`

External bridge job `108362878980`:

- `XmageControlDivergenceReconstructionTest`: **7 tests, 0 failures, 0 errors**
- complete bridge suite: **265 tests, 0 failures, 0 errors, 1 intentional skip**
- Maven BUILD SUCCESS
- inherited L2/L3/L4 suites remained green
- provider-bound Phase-6, deterministic replay and downstream B4 regressions passed.

H4:
- preflight PASS
- Forge lane PASS
- XMage direct-source build PASS
- Lab bridge verify/staging PASS
- canonical XMage image/provenance/handshake/negative controls PASS.

## Evidence Classification

- branch ancestry/source lock: DIRECTLY_VERIFIED
- causal control-change execution: DIRECTLY_VERIFIED + TECHNICALLY_CONFORMANT
- absence of direct controller mutation/effect injection: CODE_DERIVED
- leave/zone-change cleanup: DIRECTLY_VERIFIED
- Commander identity under stolen control: DIRECTLY_VERIFIED
- overlapping continuous-control behavior: DIRECTLY_VERIFIED

## PASS / FAIL / UNKNOWN

**PASS:** `RG04_CAUSAL_CONTROL_DIVERGENCE = PASS`

**FAIL:** none in bounded L5 scope.

**UNKNOWN / deferred:** causal elimination reconstruction remains L6; hidden-state/replay integration remains L7.

## Remaining Blockers

None for L6 start.

## Outputs

- Draft stacked PR #246
- `XmageControlDivergenceReconstruction`
- actual-card control-divergence regression suite
- this handoff

## Dependencies Unblocked

L6 may start only from the exact terminal head produced by this documentation-only handoff commit.

## Exact Next Action

Create `sol/rg05-causal-elimination-20260924` from the exact L5 terminal head. Reconstruct player loss/elimination only through genuine native rules causes, then verify CR-style multiplayer cleanup, priority/turn recomputation and survivor continuation. Do not set lost/eliminated flags or inject outcomes.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
