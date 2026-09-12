# WS71 — Coordinator Source-Truth Correction: Termination of the Invalid Remaining-92 Premise

## 0. Disposition

**`WS71_REMAINING92_AUDIT=FAIL`**
**`FAILURE_CLASS=CONTRACT_CATEGORY_MISMATCH`**
**`ROOT_CAUSE=CONTRACT_CATEGORY_MISMATCH`**

The commissioned `107 = 15 + 92` RQ-C3-scenario identity is not a missing
population to be found or built. It is an invalid cross-contract equation:
the `107` belongs to a separate provider-neutral semantic fixture contract,
not to the RQ-C3 actual-card scenario corpus. There is no authority
obligation to locate or fabricate 92 additional RQ-C3 scenarios.
`REMAINING92=NOT_APPLICABLE`.

No behavior runs. No engine/provider changes. No scope-expansion
implementation. WS71 is not broadened into a different qualification project.

## 1. Binding Source Truth (all mechanically read at pinned commits)

| # | Document | Pin | Verified fact |
| --- | --- | --- | --- |
| 1 | `research/candidate-qualification/common/rq-c1/RQ_C1_FULL107_RELATION.md` | RQ-C1 `714ad417c1c090eb4ddf1ccd0828a2e869a80a74` (tree `709a5944…`) | ARCHITECTURE_REVERSER_SUBSET = 40 actual-card families, 15 first-wave; Full107 is a SEPARATE evidence contract, `NOT_RUN`; nothing grants/implies/pre-counts Full107 credit |
| 2 | `research/candidate-qualification/common/rq-c1/RQ_C1_SCENARIO_MANIFEST.json` | same RQ-C1 pin | 40 scenarios, 15 first-wave, 25 non-first-wave, IDs unique (mechanically counted) |
| 3 | `research/candidate-qualification/common/rq-c3/RQ_C3_CORRECTED_SCENARIO_MANIFEST.json` | RQ-C3 `897d72f0b57bb8febe045870acaa3d2dba4bde56` (tree `1b8c8a4…`) | 18 corrected files = 15 First-Wave + `F02/H02/K02`; every parent traces into the RQ-C1 40 |
| 4 | `qualification/ws47/WS47_FREEZE_RESULT.json` | WS47 contract `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8` | `record_count = 135`, `provider_denominator = 107`, schema `commander-lab.semantic-fixture-materialization/1.0.5` |
| 5 | `qualification/ws44/WS44_PROVIDER_DENOMINATOR_107.json` | same WS47 pin | `provider_denominator_count = 107`; 107 unique fixture IDs; 28 excluded IDs exactly `CARD_01..CARD_29` except retained `CARD_02`; disjoint; union = 135 |

Mechanical verification: `ws71_correction_audit.py` → **22/22 checks PASS**,
evidence in `WS71_CORRECTION_EVIDENCE.json` (canonical JSON, no timestamps,
per-source sha256 provenance). Rerun reproduces byte-for-byte.

## 2. Separated Contracts

### A. RQ-C3 REVERSER CORPUS (actual-card scenarios)

- `RQ_C3_DEFINED_SCENARIOS=40` (continuation of the RQ-C1 40-family corpus)
- `RQ_C3_FIRST_WAVE=15` (corrected; suffixes `A03 A04 B01 C01 C03 D06 E01 E02
  F01 G02 G03 G04 H01 I01 J02`)
- `RQ_C3_NON_FIRST_WAVE=25` (the valid remaining planning corpus for any
  future RQ-C3-succession work; full ID list preserved in
  `WS71_REMAINING92_DENOMINATOR.json` → `derived_sets.rqc1_nonfw_ids`)
- RQ-C3 overlay shape: 15 corrected First-Wave files + 3 corrected non-FW
  derivatives (`F02/H02/K02`) + 22 carried-forward families under RQ-C1
  authority (incl. the 29 item-10 batch promotions and G04/K02 promotions).

### B. FULL107 (separate provider-neutral semantic fixture contract)

- `FULL107_PROVIDER_DENOMINATOR=107` (fixture IDs, e.g. `PLAYER_COUNT_2P`;
  NOT RQ-C3 scenario IDs — zero fixture IDs carry an `RQ-C*` prefix)
- `FULL107_MATERIALIZATION_RECORDS=135`
- Identity: all 135 v1.0.4 records minus `CARD_01..CARD_29` except retained
  successor sentinel `CARD_02` (28 excluded; 135 − 28 = 107, mechanically
  verified: uniqueness, exact exclusion set, disjointness, union).

### Consequence

`FULL107_COUNT_AS_RQC3_SCENARIOS=INVALID`. `REMAINING92=NOT_APPLICABLE`.
WS72's "67 authority-absent Full107 slots" reading (107 − 40) is superseded
by this cross-contract provenance finding: the 67 are not absent RQ-C3
scenarios but fixtures of a different contract. (WS72's 40-scenario RQ-C3
corpus observation itself was correct and is preserved.)

## 3. Valid RQ-C3 Planning Work Preserved

`VALID_RQC3_PLANNING_WORK_PRESERVED=YES`. Nothing valid is discarded because
the top-level denominator premise failed:

- Phase-A derived sets (RQ-C1 40 / FW 15 / non-FW 25 ID lists, titles/cards
  provenance via authority) remain the lawful input for any future 40-corpus
  planning: `WS71_REMAINING92_DENOMINATOR.json` (verdict FAIL as a
  92-denominator, valid as a 40-corpus inventory).
- Source locks (`WS71_SOURCE_LOCK.md`), audit tooling
  (`ws71_denominator_audit.py`, `ws71_correction_audit.py`), and this report.
- Honest scope record: no mechanic-clustering matrices, no candidate
  readiness matrices, and no execution waves were produced (Phase A gated
  them); their absence is preserved as fact, not backfilled.

## 4. Credit Impact (Coordinator authority impact, recorded — not executed)

- `XMAGE_RQC3_FIRST_WAVE=14/15` semantic PASS remains valid (WS60 sealed
  evidence; B01 UNKNOWN unchanged). Do NOT map to Full107 credit.
- `FORGE_RQC3_FIRST_WAVE=9/15` semantic PASS remains valid (WS65 sealed
  evidence; 6 UNKNOWN unchanged). Do NOT map to Full107 credit.
- `XMAGE_FULL107_CREDIT=0/107`. `FORGE_FULL107_CREDIT=0/107`.
- Current Full107 credit: **0/107** unless/until the exact Full107 evidence
  contract is satisfied on a qualifying candidate source lock.
- Historical WS60/WS65 `14/107` and `9/107` fields are **not rewritten**;
  classify them as `SUPERSEDED_CROSS_CONTRACT_ACCOUNTING`.

## 5. Terminal Fields

```text
WS71_REMAINING92_AUDIT=FAIL
FAILURE_CLASS=CONTRACT_CATEGORY_MISMATCH
RQ_C3_DEFINED_SCENARIOS=40
RQ_C3_FIRST_WAVE=15
RQ_C3_NON_FIRST_WAVE=25
FULL107_PROVIDER_DENOMINATOR=107
FULL107_MATERIALIZATION_RECORDS=135
REMAINING92=NOT_APPLICABLE
XMAGE_RQC3_FIRST_WAVE=14/15
FORGE_RQC3_FIRST_WAVE=9/15
XMAGE_FULL107_CREDIT=0/107
FORGE_FULL107_CREDIT=0/107
VALID_RQC3_PLANNING_WORK_PRESERVED=YES
FULL107=NOT_RUN
ARCHITECTURE_FREEZE=NOT_CLAIMED
PRODUCTION_PROVIDER=NOT_SELECTED
```

Evidence classes: `DIRECTLY_VERIFIED` (counts, derivations, pins).
No `RUNTIME_VERIFIED`. `BEHAVIOR_CREDIT=0/107`.
