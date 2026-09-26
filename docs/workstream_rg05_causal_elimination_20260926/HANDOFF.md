# L6 — RG-05 Causal Multiplayer Elimination Reconstruction

## Terminal Handoff (final semantic-integrity closure)

**Disposition:** COMPLETE / PASS

**Branch:** `sol/rg05-causal-elimination-20260924`

**Exact predecessor L5:** `fffff1a4eed12d44bd6e3460fd6a730feb9596eb`

**Runtime-qualified L6 head:** `4117aff09d9bd2c9e46c834bb53672d24af53c29`

**Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd` (unchanged)

**Draft PR:** #247, stacked on `sol/rg04-control-divergence-20260924`, OPEN/UNMERGED

**Rules authority:** official Wizards Comprehensive Rules effective 2026-08-07
(current version at verification 2026-09-26; Reality Fracture bulletin
2026-09-21 announces future changes only). Predicates: CR 100.1a/100.1b,
104.3b/104.3c/104.3d/104.5, 800.4a/800.4j/800.4k (800.4a/800.4j/800.4k texts
reverified verbatim; 104.x cited as long-stable).

**ARCHITECTURE_FREEZE:** NOT CLAIMED

**PRODUCTION_PROVIDER:** NOT SELECTED

## Prior Invalid PASS Claims (corrected, retained for the record)

An earlier terminal handoff (docs head `703af39f`, runtime head `b19149dd`)
credited cells that manufactured preconditions outside authorized initial
configuration, plus a first-N fallback. All corrected in the current
qualification; none of the invalid cells survive in PASS:

1. Flame Rift 4P winner via mid-game `setLife(8)` — REMOVED; replaced by a
   genuine Worship-based 4P winner cell (uniform initial life 4, no mutation).
2. Poison via direct `addCounters(...9 poison)` — REMOVED from PASS; poison
   causation retained UNKNOWN (no poison ledger added).
3. Deck-out via mid-game `cheat(...LIBRARY "clear")` — REMOVED from PASS;
   deck-out causation retained UNKNOWN.
4. Cleanup-discard `candidates.subList(0, required)` first-N — REPLACED by
   caller-owned identity selection (Gate A below).

No production Rules logic was weakened or bypassed at any point.

## Work Completed (final round)

- Gate A: discard transport selects ONLY caller-named expendable names from
  the exact current offer (structural exclusion of unrequested options),
  exact native cardinality, ambiguity/underflow/empty-set fail-closed;
  within-name fungible tiebreak (lowest zone_index) is declared transport
  with needed-card survival proven per test. The `...PrefersHighest...`
  test that proved the old ranking policy was deleted.
- Gate B: pinned-source 800.4j diagnostic completed — Outcome B: XMage
  retains the departed UUID in the scheduling slot (`GameState.activePlayerId`
  written once per turn in `GameImpl.playTurn`, never cleared) while every
  Rules-relevant behavior treats the turn as playerless (turn order via
  `PlayerList.getNext` skipping non-`isInGame`, priority callbacks gated by
  `canRespond()`, `leave()` implementing 800.4a incl. zone clearing,
  `checkIfGameIsOver` winner logic). No Mage defect; no Lab patch.
- Active-leave test proves behaviorally: T3 slot stability (anti-reassignment
  tripwire, explicitly NOT claimed as conformance), survivor-only decisions
  after handoff (single pass-only P2 transition frame tolerated with exact
  falsifiable rule), T4→P1/T5→P3 rotation, T6 P2-slot skip (800.4k).
- Transition-frame 800.4g/800.4h analysis recorded: cleanup-discard allowance
  is dead-defensive here (P2 zones cleared on leave); bridge submit path has
  no departed-principal liveness gate (recorded follow-up, out of L6 scope).
- Raw-null-active observable: no authoritative native null signal exists;
  retained UNKNOWN with reason (conformance carried behaviorally instead).

## Tests / Evidence (runtime head `4117aff0`)

- `XmageCausalEliminationReconstructionTest`: **21/21 green locally**
  (14 live + 7 unit), 0 failures/errors/skips.
- Full bridge suite locally: **286 green, 1 pre-existing skip**.
- Live cells: 2P terminal; 3P bolt/priority/active-leave/replay/commander/
  control-cleanup/stack-cleanup/worship/angel/draw; 4P worship-winner +
  single-victim cleanup; 5P middle-seat. No 2P/5P inference beyond exercised
  cells; no 6P claim. Same-seed reproduction kept at honest non-replay level.
- Forbidden-token audit of qualification-driving code: zero occurrences of
  setLife/setLost/setLeft/setWon/submitConcede/cheat/addCounters/first-N.
- Evidence classes: causal executions DIRECTLY_VERIFIED
  (+TECHNICALLY_CONFORMANT transport where noted); CR predicates
  EXTERNALLY_RULE_VALIDATED; no-mutation CODE_DERIVED; poison/deck-out and
  raw-null-active UNKNOWN with reasons.

## PASS / FAIL / UNKNOWN

**PASS:** `RG-05_CAUSAL_MULTIPLAYER_ELIMINATION = PASS` — G01–G20 hold;
PASS list contains no forbidden-setup cell and no ranking-fallback cell.

**FAIL:** none in bounded L6 scope.

**UNKNOWN (retained, non-blocking):** poison-counter causation,
empty-library causation, raw-null-active signal, MICRO/RNG/REPLAY families,
FULL107 mapping promotion (separate qualification scope).

## Player-Count Matrix (mechanism-specific)

- 2P: DIRECTLY_VERIFIED (native terminal Bolt loss, winner, null-decision end).
- 3P: DIRECTLY_VERIFIED (loss, cleanup, priority exclusion, active-leave
  800.4j/k, commander combat, control/stack cleanup, prevention, draw-case).
- 4P: DIRECTLY_VERIFIED (Worship winner + terminality; single-victim
  continuing cleanup).
- 5P: DIRECTLY_VERIFIED (middle-seat live ring). Generic 4P smoke is
  supporting only, never cited as mechanism evidence.

## Qualification-Integrity Audit

- No first/first-N/random/default/AI/GUI/skip/filtering/fabrication patterns
  in qualification-driving paths (token audit above).
- Caller-owned discard names per drive; unrequested options structurally
  unselectable; survival proven by later casts.
- No Lab-side Rules patch for 800.4j (readback untouched — production
  observation change avoided by impact adjudication).

## Workflow Evidence (exact SHAs and run IDs)

- Runtime head `4117aff0` round (triggered by remediation push): CI,
  External XMage Integration, XMage Full Game Conformance, Real 4P Smoke,
  H4 Docker Materialization — terminal SUCCESS required (recorded below on
  completion; IN_PROGRESS is not PASS).
- Superseded history: `8d3e69ed` round (CI CANCELLED by docs push — never
  claimed); `060869e5` tip round (all five SUCCESS on identical code plus
  docs-only handoff — supporting, not primary).
- Historical `b19149dd` PASS survives ONLY for unaffected predicates
  (arch/runner/infrastructure), never for remediated semantics.

## Remaining Blockers

None for L6; none blocking L7 start.

## Outputs

- Draft stacked PR #247 (exact head recorded above; unmerged).
- Causal runner (architecture preserved) + 21-test qualification suite.
- Mage 800.4j diagnostic (Outcome B, source-bound).
- This corrected handoff.

## Dependencies Unblocked

L7 hidden-state/replay integration is dependency-unblocked from the terminal
docs head once its workflows are terminal SUCCESS. Recorded follow-ups (not
L6 scope): bridge departed-principal liveness gate; poison/deck-out genuine
designs; FULL107 promotion; per-decision UUID-naming if a future board needs
it.

## Exact Next Action

Coordinator dispatches L7 from the terminal docs head after confirming all
five exact-head workflows terminal SUCCESS. Do not merge the stacked chain;
no freeze/provider change.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
