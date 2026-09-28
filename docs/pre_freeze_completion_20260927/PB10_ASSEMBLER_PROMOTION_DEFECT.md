# PB-10 — donor XMage column contains PASS rows promoted by name mention, not by obligation execution

Date: 2026-09-28
Lane: `muse-xhigh/full-completion`
Classification: `DIRECTLY_VERIFIED` (donor git objects at `208341c6` + current-HEAD test sources)
Status: OPEN finding with Wave-1 remediation (4 demotions applied in the recomputed column)

## 1. The defect

`scripts/assemble_current_boundary_evidence.py` (donor version) promoted any
non-PASS row to PASS when a fixture id merely APPEARED in a native test
source (`native_bindings()` regex over `.java` files). A passing test suite
plus a name mention became a row PASS without any obligation being executed.
Four XMage PASS rows rest exclusively on non-obligation harnesses:

| Row | Donor PASS basis | What the harness actually proves |
|---|---|---|
| `WS05-CMD-ZONE-LIB-YES` | `XmageNativeStateRestorationTest` | `rejectsFrozenStackSpell`: the record THROWS (`UNSUPPORTED_ZONE`) — fail-closed proof, zero obligated facts observed |
| `WS05-MP-ELIM-OWNED-3` | `XmageNativeStateRestorationTest` | `elimLifeZeroIsNotCredited`: asserts the verdict does NOT match; `XmageFullGameElimExecutionTest.characterizeElimBlocker` names the row `NOT_RUN_BLOCKED` by design |
| `HIDDEN_02` | `XmageHiddenReplayIntegrationTest` | `legacyFrozenLibraryAndFaceDownRecordsRemainFailClosed`: the record THROWS (`LEGACY_LIBRARY_ORDER_AMBIGUOUS`) — the obligation is unexecutable, not satisfied |
| `WS05-CMD-ELIM-4` | `XmageCommanderDamageRestorationTest` | `frozenSplitAndControlFixturesNowParseWithoutFabricatingCommanderIdentity`: the record parses and binds — no loss observed, no cleanup observed |

Each cited test name declares its non-credit nature (`rejects…`, `IsNotCredited`,
`RemainFailClosed`, `NowParse…`). The promotion rule could not see that.

## 2. Why this matters

PASS is defined as "the effective obligation was executed and the obligated
facts were observed". A rejection/parse test observes no obligated facts, so
these four cells are not row evidence — they are seam-integrity evidence
misfiled as row credit. This is the same defect family the L6 integrity
remediation removed (manufactured preconditions, first-N fallback): credit
without obligation observation. It inflates the XMage column by 4 and, through
`CURRENT_BOUNDARY_COMPARISON.json`, the `SAME_SEMANTICS` denominator.

## 3. What was verified in the same audit (sound, retained)

The other 21 native PASS rows each have an obligation-executing harness that
loads the row's own record and asserts its required events/postconditions as
game facts (execution tests for mulligan/tax/partner/damage/trig/micro/
card02/START, decision tests for pilot/negative rows, temporal tests for
turn/declaration rows, digest readback for construction-only rows). The full
per-row binding is `POSITIVE_NATIVE_BINDING_XMAGE` in
`src/commander_lab/qualification/current_boundary/pb03_evidence.py`.

## 4. Wave-1 remediation (this lane)

- The regex promotion is deleted from the assembler. Promotion requires an
  audited entry in `POSITIVE_NATIVE_BINDING_XMAGE`; characterization entries
  bind non-PASS outcomes; any PASS/NATIVE row without an audited binding
  demotes to BLOCKED with the proof attached.
- Recomputed XMage column (`qualification/pb03-wave1-20260928/`):
  `WS05-CMD-ZONE-LIB-YES` → BLOCKED (admitted TIER_2, Wave-2 execution
  pending); `WS05-MP-ELIM-OWNED-3` → BLOCKED (`LIFE_ZERO_PRESTART`);
  `HIDDEN_02` → UNKNOWN (no honest observation path);
  `WS05-CMD-ELIM-4` → BLOCKED (commander-identity duality characterization).
- Donor files are preserved byte-identical; the recompute records every
  transform with donor outcome, new outcome, and basis.

## 5. Open questions for the Coordinator

- Whether the four demotions should also amend the frozen donor packet
  (this lane leaves donor provenance untouched and reports both columns).
- PB-03's SLOT-02 ruling (mechanism-equivalence admission) now has four
  fewer rows resting on adjacent-mechanism credit, which sharpens but does
  not replace the ruling.
- The Forge column's 74 native promotions were bound by the same era of
  pointer mapping and need the same positive-execution audit before any
  provider comparison (Wave-F).

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
