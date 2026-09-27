# L6 — RG-05 Causal Multiplayer Elimination Reconstruction

## Terminal Handoff (integrity remediation + re-closure)

**Disposition:** COMPLETE / PASS (remediated; prior invalid cells removed)

**Branch:** `sol/rg05-causal-elimination-20260924`

**Exact predecessor L5:** `fffff1a4eed12d44bd6e3460fd6a730feb9596eb`

**Runtime-qualified L6 head:** `8d3e69ed02a3bd992a4c27b599db8f210c67c777`

**Runtime-qualified L6 tree:** `ebb9ea8865888fe20ae044e93ac60dcac6212ac6`

**Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd` (unchanged)

**Draft PR:** #247, stacked on `sol/rg04-control-divergence-20260924`, OPEN/UNMERGED

**Rules authority:** official Wizards Comprehensive Rules effective 2026-08-07
(current version at verification 2026-09-26; Reality Fracture bulletin
2026-09-21 announces future changes only). Predicates: CR 100.1a/100.1b,
104.3b/104.5, 800.4a/800.4j/800.4k (texts reverified verbatim).

**ARCHITECTURE_FREEZE:** NOT CLAIMED

**PRODUCTION_PROVIDER:** NOT SELECTED

## Prior Invalid PASS Claims (corrected)

The previous terminal handoff (docs head `703af39f`, runtime head `b19149dd`)
credited three cells that manufactured preconditions outside authorized
initial configuration, plus one first-N fallback:

1. `flameRiftEliminatesThreeOpponentsSimultaneouslyAndProducesWinnerInFourPlayer`
   — mid-game `setLife(8)` after start. REMOVED as a PASS cell; replaced by a
   genuine Worship-based 4P winner cell (uniform initial life 4, no mutation).
2. `ninePoisonPlusActualPrologueCausesNativePoisonLoss` — direct
   `addCounters(...9 poison)` after start. REMOVED from PASS; poison retained
   UNKNOWN (no poison ledger added; genuine paths documented as follow-up).
3. `emptyLibraryPlusActualDrawCausesNativeDeckOut` — mid-game
   `cheat(...LIBRARY "clear")`. REMOVED from PASS; deck-out retained UNKNOWN.
4. Cleanup-discard `candidates.subList(0, required)` — first-N fallback.
   REPLACED by explicit semantic selection (below).

No production Rules logic was weakened or bypassed at any point. The three
removed cells' underlying native loss transactions were never in doubt; only
their manufactured setups were disqualified as evidence.

## Work Completed

- Causal runner `XmageCausalEliminationReconstruction` preserved unchanged in
  architecture (no lost/left/life/terminal mutation; observes native state).
- R1: discard transport selects exactly the native required count by stable
  semantic key (`name|zone_index` descending) with ambiguity/underflow throws
  and exact-or-null shape gating; 4 adversarial unit tests (top-N order,
  ambiguity, underflow, non-exact shape).
- R2: Worship-4P genuine winner cell; double-Bolt 4P continuing-game cleanup
  cell; setLife/cheat-clear/addCounters cells removed per above.
- R3: bounded genuine 2P terminal cell (initial life 3, Bolt, native win,
  null-decision terminality, no survivor loop).
- R4: active-leave cell proves T3 active-slot retention (800.4j
  representation), survivor-only decisions after handoff (transition-frame
  tolerant), T4→P1/T5→P3 rotation, T6 skip of P2's slot (800.4k).

## Tests / Evidence (runtime head `8d3e69ed`)

- `XmageCausalEliminationReconstructionTest`: **18/18 green locally**
  (14 inherited − 3 removed + 3 live additions + 4 unit).
- Full bridge suite locally: **283 green, 1 pre-existing skip**.
- Live cells by count: 2P (terminal), 3P ×8 (bolt, priority, active-leave,
  replay, commander-combat, control-cleanup, stack-cleanup, worship-3P,
  angel, draw), 4P ×2 (worship-winner, single-victim cleanup), 5P (middle
  seat). No 2P/5P inference beyond exercised cells; no 6P claim.
- Evidence classes: causal executions DIRECTLY_VERIFIED (+TECHNICALLY_CONFORMANT
  harness transport where noted); CR predicates EXTERNALLY_RULE_VALIDATED;
  absence-of-mutation CODE_DERIVED; poison/deck-out UNKNOWN (honest residual).

## PASS / FAIL / UNKNOWN

**PASS:** `RG05_CAUSAL_MULTIPLAYER_ELIMINATION = PASS` — G01–G20 hold for the
cells listed above; PASS list contains no forbidden-setup cell.

**FAIL:** none in bounded L6 scope.

**UNKNOWN (retained, non-blocking):** poison-counter causation, empty-library
causation, MICRO/RNG/REPLAY families, FULL107 mapping promotion (separate
qualification scope).

## Remaining Blockers

None for L6; none blocking L7 start.

## Outputs

- Draft stacked PR #247 (head `8d3e69ed`, then this docs-only handoff).
- Causal runner (unchanged architecture) + 18-test qualification suite.
- This corrected handoff.

## Dependencies Unblocked

L7 hidden-state/replay integration is dependency-unblocked once required
workflows on the runtime head are terminal SUCCESS. L6 must not be reopened
for poison/deck-out without a new genuine-causation design.

## Exact Next Action

Watch the exact-head (`8d3e69ed`) workflows CI / External XMage Integration /
XMage Full Game Conformance / Real 4P Smoke / H4 Docker Materialization to
terminal SUCCESS; on any failure classify per ambient/L6-attributable rules
before any further mutation. Then Coordinator may dispatch L7 from the
terminal docs head. Do not merge the stacked chain; no freeze/provider change.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
