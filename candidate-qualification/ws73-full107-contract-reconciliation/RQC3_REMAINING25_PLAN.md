# RQ-C3 Remaining-25 Plan — 25 Non-First-Wave Actual-Card Scenarios (Not Full107)

Workstream: `WS73-FULL107-CONTRACT-RECONCILIATION` (plan only; no execution).
Authority: RQ-C1 `714ad417c1c090eb4ddf1ccd0828a2e869a80a74` (40 families, 15 First Wave) +
RQ-C3 `897d72f0b57bb8febe045870acaa3d2dba4bde56` (18 corrected: 15 FW + F02/H02/K02).
These 25 are RQ-C3-continuation scenarios. Do not call them Full107. `FULL107 = NOT_RUN`.

## 0. Population (mechanical, 25 = 40 − 15)

Defined unique corpus 40 = RQ-C1 families with 18 RQ-C3 overlays preferred.
First Wave 15 (RQ-C3 IDs): `RQ-C3-A03, RQ-C3-A04, RQ-C3-B01, RQ-C3-C01, RQ-C3-C03,
RQ-C3-D06, RQ-C3-E01, RQ-C3-E02, RQ-C3-F01, RQ-C3-G02, RQ-C3-G03, RQ-C3-G04,
RQ-C3-H01, RQ-C3-I01, RQ-C3-J02`.

Remaining 25 (use RQ-C3 overlay where it exists, else RQ-C1):

- `RQ-C1-A01` (Rest in Peace replacement dogfood)
- `RQ-C1-A02` (pure-prevention baseline; Oracle-direct, no adjudication question)
- `RQ-C1-B02` (delayed trigger)
- `RQ-C1-B03` (intervening-if)
- `RQ-C1-B04` (dies + fan-out; Murder Oracle now verified)
- `RQ-C1-C02` (additional-cost sacrifice; Altar's Reap)
- `RQ-C1-C04` (commander-conditioned cost; Cultivate Oracle now verified)
- `RQ-C1-D01` (choose-two; Cryptic Command)
- `RQ-C1-D02` (Twincast spell-copy; reassigned ID)
- `RQ-C1-D03` (stack survival)
- `RQ-C1-D04` (copy-trigger)
- `RQ-C1-D05` (chooser-division; Casualties-class division)
- `RQ-C1-E03` (deathtouch; Deadly Recluse)
- `RQ-C3-F02` (corrected non-FW: scoped reveal+choice, public-to-ALL during reveal)
- `RQ-C1-F03` (morph; Willbender)
- `RQ-C1-F04` (scry; Preordain; Oracle-direct)
- `RQ-C1-G01` (vote; Council's Judgment)
- `RQ-C1-G05` (each-opponent; Braids)
- `RQ-C3-H02` (reframed non-FW: 7b/7c sublayer precedence, both paths 4/4 Frog)
- `RQ-C1-I02` (reanimation; Reanimate)
- `RQ-C1-I03` (token lifecycle; Doomed Traveler + Altar's Reap + Blood Artist)
- `RQ-C1-J01` (coin; Mana Crypt)
- `RQ-C1-J03` (random discard; Hymn to Tourach)
- `RQ-C1-K01` (mass trigger accounting; Soul Warden + Blood Artist)
- `RQ-C3-K02` (promoted non-FW: legend-rule 704.5j/700.4 + variant path)

Count check: 22 RQ-C1 + 3 RQ-C3 overlays = 25. RQ-C3 manifest `count 18` + RQ-C1 `scenario_count 40`
jointly imply this 25; no 92 is manufactured.

## 1. Authority prerequisites (per scenario)

- Use the corrected RQ-C3 text where an overlay exists (F02/H02/K02 as corrected in
  `RQ_C3_COORDINATOR_ADJUDICATION.md` + `RQ_C3_CORRECTION_APPLICATION.json`); otherwise use the
  RQ-C1 scenario JSON verbatim plus RQ-C2/RQ-C3 authority promotions that apply
  (G04/K02/item-10 exact packets; rule-number corrections 702.13→701.19 etc. only where RQ-C2 mapped;
  Murder/Cultivate/Ornithopter `ORACLE_TEXT_VERIFIED`).
- Respect native setup boundaries (`RQ_C1_NATIVE_SETUP_BOUNDARIES.json` + `RQ_C3_SETUP_BOUNDARIES.json`):
  35 `NATURAL_GAME_START`, 4 `PRE_STEP_NATIVE_PROGRESSION`, 1 `PRE_DECISION_CONSTRUCTION` (G03-class;
  seeded ledger `BEHAVIOR_CREDIT=0`, credit only for post-boundary native behavior).
- Decision requirements are the RQ-C3-corrected union (`RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json` +
  `RQ_C3_DECISION_REQUIREMENT_DELTA.json` as new authority; WS55 impact-adjudicated): no `may`,
  no generic `ordering`, no Damage Assignment Order; `hidden-zone selection` includes C01-pitch;
  `combat damage assignment` per AG-3 (E02 2/1/4, no ordering step).
- Hidden-info expectations per `RQ_C3_HIDDEN_INFO_EXPECTATIONS.json` (F02 public-during-reveal,
  C01 pitch hidden-until-exile, F01/J03 contrasts). RNG shapes per `RQ_C1_RNG_EXPECTATIONS.json`
  (F01 shuffle, J01 coin, J02 d20+recursion, J03 random-select; seeds at execution, never prescribed outcomes).

## 2. Candidate binding

- Forge at `a9a95db` (WS62/WS65 lineage; WS68 payCombatCost/concession pending): E01-class (tax),
  G04-class (concession), and any copy/Humility-adjacent scenarios in the 25 require WS68/WS67
  disposition first; do not force PASS through known gaps (fail closed UNKNOWN with packets).
- XMage at `7135d5e` (WS56 + WS60 lineage): harness proven 14/15 on First Wave; B01-class lessons
  apply (bounded native assembly + absolute-total reachability must be authority-checked per scenario;
  nominal totals that are unreachable natively are fixture-authority gaps, not engine FAILs).
- Card presence for all 25 is already preflighted ALL_FOUND (WS72 25/25 both candidates, 55-card corpus);
  presence is not readiness and not credit.

## 3. Execution discipline (per scenario, each candidate)

- Fresh processes, authoritative engine-offered options only, 1:1 unique match (zero/multiple fail closed),
  principal-scoped hidden info, recorded explicit Rules seeds, semantic replay for every PASS (0 divergences),
  100-card deck reconciliation, 0 out-of-option selections.
- Per-scenario packets mirror WS60/WS65: fixture, intent, gzipped journal + replay, run receipt,
  adjudication (PASS/FAIL/UNKNOWN), hidden/RNG sub-verdicts. Replay grants no credit; prerequisites grant none.
- Failure taxonomy per scenario (FIXTURE_AUTHORITY_GAP vs ENGINE vs PROVIDER_TRANSPORT vs HARNESS);
  remediation packets bounded, no repairs inside the execution workstream.

## 4. Credit semantics (separate from Full107)

- Denominator is 15 (First Wave) + 25 (this continuation) = 40-scenario RQ-C3 corpus; plus RQ-C3-corrected
  derivatives counted once each. Report as `RQC3_N/40` and `RQC3_FIRST_WAVE_N/15` / `RQC3_REMAINING25_N/25`.
- Never report these as `/107`. Full107 credit (`/107`) arises only under `FULL107_EXECUTION_PLAN.md`.
- `BEHAVIOR_CREDIT_CHANGE` for this continuation is tracked in its own workstream; WS73 grants 0.

## 5. Order and leverage (suggested, not binding)

- High-leverage first: B04/K01 (fan-out/accounting), D02 (spell-copy), H02 (layers-sublayer),
  K02 (legend-rule), F02/F03/F04 (hidden family), J01/J03 (RNG), G01/G05 (multiplayer), then costs/
  targets/combat breadth (C02/C04/D01/D03/D04/D05/E03/A01/A02/B02/B03/I02/I03).
- WS66 authority-closure notes apply: B01 CORRECTION_REQUIRED (relative-delta), J02 VALID_AS_WRITTEN;
  carry those dispositions into any B01/J02-adjacent remaining work; coordinator counts stand.

## 6. Outputs

- `RQC3_REMAINING25_MATRIX.json` (25 rows: verdict/credit/frames/failure-class), decision-kind coverage
  delta vs First Wave, hidden/replay audits, remediation packets, final report, state with `validated_head`.
- Validate denominator 40/15/25 mechanically (no 92, no 107-conflation) before any push.

*Planned, not executed. Not Full107.*
