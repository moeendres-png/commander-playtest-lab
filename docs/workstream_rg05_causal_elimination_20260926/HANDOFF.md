# L6 — RG-05 Causal Multiplayer Elimination Reconstruction

## Terminal Handoff

**Disposition:** COMPLETE / PASS

**Branch:** `sol/rg05-causal-elimination-20260924`

**Exact predecessor L5 head:** `fffff1a4eed12d44bd6e3460fd6a730feb9596eb`

**Runtime-validated L6 implementation head:** `b19149dda18221c7cbcadc8b4339092af2b1f541`

**Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd`

**Draft PR:** #247, stacked on L5

**WORKTREE:** NOT_AVAILABLE_IN_CONNECTOR_EXECUTION

**ARCHITECTURE_FREEZE:** NOT CLAIMED

**PRODUCTION_PROVIDER:** NOT SELECTED

## Work Completed

- Added/qualified causal multiplayer elimination reconstruction driven only by genuine XMage Rules execution.
- No Lab code sets player lost/left/won flags and no terminal result is injected.
- Actual-card causes cover lethal damage, self-loss, empty-library draw loss, poison, Commander combat damage, simultaneous loss/winner/draw, active-player loss and multiplayer continuation.
- Qualified owned-object cleanup, controlled-but-foreign-owned cleanup, leaver-owned stack-object cleanup, priority-ring removal, turn recomputation, survivor continuation and 3P/4P/5P live rings.
- Reused L3 temporal progression and L4/L5 native cast/target/mana seams rather than adding a second action legality path.
- Same-seed fresh-session elimination behavior remains bound to native execution.

## Failure / Remediation History

The leaver-owned-stack test initially used a bespoke cast helper. It failed because the helper did not bind an offered cast at the actual current decision state.

A first simplification from Giant Growth to targetless Opt reproduced the same zero-offer failure, proving target legality was not the cause.

Final remediation:
- removed the bespoke cast setup from the affected test;
- reused the already runtime-qualified L4 sequence:
  exact pass-to-actor -> offered Lightning Bolt cast -> exact native target -> native mana payment;
- only after the P2-owned spell genuinely existed on the stack did the test causally eliminate P2 with P1's genuine Lightning Bolt;
- native leaver cleanup then had to remove the P2-owned stack object without resolving it.

No Rules-Core or production legality behavior was weakened to satisfy the test.

## Tests / Evidence

All five workflows on exact L6 implementation head
`b19149dda18221c7cbcadc8b4339092af2b1f541` completed SUCCESS:

- External XMage Integration — `36230385741`
- XMage Full Game Conformance — `36230385743`
- XMage Real 4P Technical Smoke — `36230385754`
- CI — `36230385766`
- H4 Docker Materialization — `36230385779`

The final bridge suite includes the full `XmageCausalEliminationReconstructionTest`
matrix with all 14 cells passing on the same cumulative stacked source.

## PASS / FAIL / UNKNOWN

### PASS

- native lethal-damage elimination
- active-player/self-loss progression
- deck-out loss
- poison loss
- Commander-damage loss
- simultaneous winner/draw semantics
- eliminated player priority removal
- live-ring / next-active-player continuation
- owned battlefield cleanup
- foreign-control / owner-leaves cleanup
- leaver-owned stack-object removal
- 3P/4P/5P causal multiplayer behavior
- cumulative L1-L6 regression surface

### FAIL

None in L6 scope.

### UNKNOWN / intentionally outside L6

- Hidden ordered-library restoration and private/public projection integration
- Face-down hidden identity projection and replay
- Public/principal replay privacy against hidden-state oracle hashes

These are L7 scope.

## Remaining Blockers

None for L7 start.

## Outputs

- Draft stacked PR #247
- causal elimination implementation/tests
- this terminal handoff

## Dependencies Unblocked

L7 must start from the exact terminal head produced by this handoff commit.

## Exact Next Action

Create/resume `sol/rg06-hidden-replay-integration-20260924` from the exact L6 terminal head.

Integrate the already qualified Mage ordered-library and bounded face-down game-load
APIs into a lossless Lab hidden-state request surface, harden the sole
principal-scoped redactor, and qualify semantic replay so public/principal tapes
cannot act as hidden-card oracle hashes. Ambiguous old frozen records must stay
fail-closed rather than infer library order or face-down subtype.

`ARCHITECTURE_FREEZE = NOT CLAIMED`
`PRODUCTION_PROVIDER = NOT SELECTED`
