# WS222 IMPACT_ADJUDICATION

Question: does the v2 authority refresh grant behavior credit, preserve
existing runtime evidence, or require targeted requalification?

## Findings (DIRECTLY_VERIFIED reads + captures)

1. **No behavior credit granted.** `BEHAVIOR_CREDIT_CHANGE = 0`. An
   authority-lock refresh re-anchors the 135 rows' authority basis; it proves
   no runtime behavior. Aggregate remains 0-PASS/135-NOT_RUN at the rollup
   layer; ws213/ws215 scoped lifecycle seals keep exactly their sealed scope
   (no expansion, no re-interpretation under v2).
2. **Rules-version continuity.** The previously *identified* (never captured)
   family was `MagicCompRules 20260807`, effective 2026-08-07. The v2 artifact
   (`...20260819.txt`) states the SAME effective date (republish, 2026-08-19).
   There is no byte baseline to diff against (v1 bytes were honestly null), so
   no byte-level drift can be computed; effective-date continuity means no
   known Rules-version change versus the identified baseline. Recent
   adjudications that cited current-2026 CR text from external reads (WS79
   614.12; WS213 I01 110.2/303.4e/400.3) are text-consistent with the v2
   artifact family; spot-check obligation passes to behavior tracks, not to
   this lock.
3. **Oracle continuity for the denominator.** No prior authoritative Oracle
   snapshot existed (subset explicitly non-authoritative; engine DBs are
   implementation), so there is no prior Oracle baseline to conflict with.
   The v2 snapshot is the first authoritative pin; nothing is invalidated.
4. **Targeted requalification list: EMPTY.** No fixture's prior PASS is
   voided by this refresh (no PASS depended on a different pinned domain),
   and no fixture gains PASS from it. Future behavior runs execute under the
   v2 pin from the start.

## G13 consequence

G01 ceases to be the admission blocker. G13 remains FAIL on independent
grounds (G02–G12 behavior/provider evidence NOT_RUN/UNKNOWN; no production
provider selected). Authority tracks and behavior tracks stay separated.

Machine companion: `IMPACT_ADJUDICATION.json`.
