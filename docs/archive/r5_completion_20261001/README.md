# R-5 completion: final current-boundary epoch on `main` (#425 → #255)

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`. No ranking and no recommendation.

## Source lock

| Role | Identity |
|---|---|
| Lab `main` (producer of the epoch) | `4cad91897216963010e8c3f689afea3ba31df33b`, tree `a43e80d96595b9fe4c984d7f70d99e3c769b982e` (merge of #436) |
| XMage candidate | `9375f35ac7c9a540ebcb8b262b8645b8c6b1b326` (tree `0fb7c2f9a038e471de3a6e56419244482a645218`), `config/rules_engines.json` `primary_engine` |
| Forge Rules-Core authority (R-1) | #11/#12 `bb0a740d2bef725194798383c2452213ecdd0b37`, tree `4989b5bb35b8279e82f79c1ca99dc698d63d093a` |
| Forge exact built/materialization source | #11 branch head `e8b8aec60720aee218338754224721597b8c6ec5`, tree `6c49f100fe61d1b2a71dd46a7347a2ff0f0da4ea` (= #11 + merged #13) |

**Forge relation (computed):** `bb0a740d..e8b8aec6` changes exactly two files, both under `forge-protocol2-bridge/`:
- `BridgeEngine.java`;
- `Af01UnsupportedDecisionClassTest.java`.

There are 0 Rules-Core main-source changes and 0 card-data changes. The Rules-Core equivalence is re-proven in the run (`RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL`, `EXACT_BRIDGE_COMMIT`).

**Exact-head gates:**
- Forge `e8b8aec6`: Test build #217/#218 (Java 17/21) and iOS #173/#174 all green.
- Lab #436 head `555abd32`: all 11 workflows green.
- Lab `main` `4cad9189`: PB-03 `workflow_dispatch` run **36798188914**, artifact `11136255408` (sha256 `7a72c4fdf982d270482cb626dfc9ba24f2e873b437b3a42dda522f8781d366ea`).

## Epoch

`qualification/current-boundary-epochs/4cad91897216-a43e80d96595/` holds the 61 files of that artifact. All 60 entries of its `CURRENT_BOUNDARY_SHA256SUMS` were verified after download, and the files are covered by `qualification/SHA256SUMS` and `WS17_SHA256SUMS`.

| | XMage | Forge |
|---|---|---|
| FULL107 PASS / FAIL / UNKNOWN / BLOCKED | **19 / 0 / 48 / 40** | **5 / 0 / 58 / 44** |
| PASS rows without a current direct receipt (R-4 demotions) | 0 | 0 |
| AF00 source/build lock | PASS | PASS (built source `e8b8aec6`; Rules-Core proven separately) |
| AF01 (20 v2 invariants, one run, one lane) | PASS 20/20 | **PASS 20/20** (R-3 closed by #13) |
| AF02 cardinality, AF03 | PASS, PASS | PASS, PASS |
| AF04 decision boundary | PASS (R-2 provenance verified on this run's live frame) | UNKNOWN (R-2: no class beyond PRIORITY exercised) |
| AF05–AF09 | UNKNOWN | UNKNOWN |
| AF10 runtime evidence reliability | PASS (219 native tests) | PASS (217 native tests) |
| AF11 | UNKNOWN: post-selection single-provider re-verification only | UNKNOWN: same |

**Direct receipts:** 24 positive receipts:
- 14 midgame rows for XMage;
- 5 direct lifecycle rows for each candidate.

Native suites remain supporting evidence and promote no row.

## What R-5 changed (merged through #436)

- **Forge authority:** R-1 dual identity (Rules-Core candidate and exact built source, bound separately), plus live consumers (#427/#429/#432).
- **FULL107 section C** (#431):
  - TAX-4, ANNOUNCE_X, CHOOSE_MODE, TRIGGER_ORDER and START-3;
  - the mana charge is measured from pool spends, not from taps.
- **R-4 credit:** the assembler's denominator rows carry `effective_*` digests, but credit compared them against the plain names. No receipt was ever credited, so every PASS was demoted. Fixed.
- **R-2:** AF04 is derived from a live provenance check instead of a literal.
- **B3:** per-class execution is now read from `<testcase>` elements. Forge's TestNG suites (`TEST-TestSuite.xml`) had been recorded as "0 tests", which made AF10 FAIL.
- **PB-03 and H4:** the Forge bridge classpath is resolved inside the reactor, because the R-1 fork versions with `${revision}`. The upload is guarded against an empty epoch path.
- **B5 workspace binding:** only the config authority is bindable.

## Residuals (explicit, not credit)

- **forge#15/#16** (no-default cost-order hardening): **not integrated**.
  - Their exact-head Test build failed (#213, #220: 16 bridge failures from the new `ORDER_CHOICE`).
  - Integrating them needs the tests, the replay children and a declared Lab cost-order pilot policy to answer that frame. See forge#16.
- **Coordinator questions from section C:**
  - scripts that start inside a cast (MICRO_MODES, PILOT_TARGET_AMOUNT, PILOT_MULTI_AMOUNT, four NEGATIVE_* rows);
  - MICRO_COSTS asks P2 to cast the sorcery Hex in P1's main phase (CR 307.1);
  - NEGATIVE_* `DECISION_TIMEOUT` vs `UNSUPPORTED_DISCRETIONARY_DECISION`. See `docs/full107_row_families_20260930/README.md`.
- **Causal-route rows** (stack state, mid-combat checkpoints, control divergence): the Coordinator decision slot.
- **Rows out of the midgame lane's reach by design:**
  - HIDDEN_*: partial library plus an untyped face-down object, under the L7 fail-closed policy;
  - REPLAY_* / RNG;
  - pregame (mulligan) rows.
- **The Forge FULL107 column has no midgame/placement lane.** Its 5 PASS are the lifecycle and START-2 rows; every other row is honestly UNKNOWN/BLOCKED.
- **AF05–AF09** list FULL107 rows as their blocking rows for both candidates. **AF11** follows selection.

## Exact next action

Coordinator adjudication on #255 from this matrix. Under R-4/#255's rule a candidate is eligible only if all of its gates PASS; neither candidate is all-PASS today.
