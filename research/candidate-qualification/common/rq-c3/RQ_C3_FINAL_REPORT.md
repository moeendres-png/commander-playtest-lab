# RQ-C3 Final Report — Rules Authority Closure + Corrected Execution Pack

## 0. Terminal verdict

**`RULES_AUTHORITY_CLOSURE_PASS`**

Rationale: the corrected 15-scenario First Wave is mechanically complete (same intended architecture coverage as RQ-C1 with all RQ-C2/Sol corrections applied; denominator preserved at 15 with no substitution) and every execution assertion has explicit authority status (`EXTERNALLY_RULE_VALIDATED` for Sol-approved expected outcomes with candidate `NOT_RUN`; `MODELED_PENDING_CANDIDATE_EXECUTION` for seeded construction; `UNKNOWN` closed-world for anything unlisted). Local validator `validate_rqc3.py` is green including 6 negative controls rejected. No candidate executed. RQ-C1/RQ-C2 byte-identical.

## 1. Source Lock

- RQ-C1 HEAD `714ad417c1c090eb4ddf1ccd0828a2e869a80a74`, TREE `709a5944c9826dbaaa433052f3538425c8f0573b`, branch `research/candidate-neutral-architecture-reverser-corpus-rq-c1-20260910`, disposition `NEUTRAL_CORPUS_READY_PENDING_RULES_ADJUDICATION`.
- RQ-C2 HEAD `fb7d493e6b04a59d09bc43d1de3cd8c2eaf59bc8`, TREE `7abcb331fd378a9663bd9222eb8135ad34dff102`, branch `research/rules-authority-verification-rq-c2-20260910`, disposition `RULES_AUTHORITY_PACK_READY_FOR_SOL`.
- RQ-C3 branch `research/rules-authority-closure-rq-c3-20260910`, worktree `/home/moeen/code/rq-c3-rules-authority-closure`. RQ-C3 HEAD/TREE recorded in `WORKSTREAM_STATE.yaml` (`state_written_against_head`) and in commit history at handoff (see Changes).
- Official CR baseline effective **August 7, 2026** (RQ-C2 captured; `media.wizards.com` TXT sha256 `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f`); Gatherer Oracle/rulings retrieved 2026-09-10 (11 direct pages); Scryfall 49/49 secondary only. No silent refresh in RQ-C3.
- Full lock: `RQ_C3_SOURCE_LOCK.md`. Parent hashes: `RQ_C3_PARENT_HASHES.json`. Immutability: `RQ_C3_PARENT_IMMUTABILITY.json`.

## 2. Work Completed

Built immutable corrected derivative under `research/candidate-qualification/common/rq-c3/**` (RQ-C1/RQ-C2 untouched): source lock, Coordinator-adjudication transcription, 18 corrected scenarios (15 FW + H02/F02/K02), correction application, authority promotions (G04/K02/item-10), rule-reference corrections (5+3), oracle confirmations (3), corrected manifest (JSON+CSV), First-Wave execution pack (15), decision requirements + delta, hidden-info expectations + delta, setup boundaries, execution-assertion authority, parent hashes/immutability, validator with negative controls, workstream state, this report. No candidate executed. No Full107. See Outputs.

## 3. Coordinator Directions Applied

All §3 directions implemented mechanically (see `RQ_C3_COORDINATOR_ADJUDICATION.md`):

- **C01 AMEND_REQUIRED**: Island retired as pitch; Turn to Frog (RQ-C2 `ORACLE_TEXT_VERIFIED` blue nonland) selected; 5 untapped Islands as `3UU` mana sources; both `NORMAL_COST_AVAILABLE`/`ALTERNATE_COST_AVAILABLE` distinguished then alternate chosen; pitch selection is hidden-zone decision.
- **H02 REFRAME**: both paths `4/4 blue Frog`; `LAYER_SUBLAYER_PRECEDENCE_OVERRIDES_TIMESTAMP_ACROSS_7B_7C`; PATH_A=1/1 retired; no replacement card.
- **F02 AMEND_REQUIRED**: reveal public to ALL during resolution; hidden-again after with retained usable knowledge (not leak); P0-only + amnesia retired.
- **A03 AMEND_REQUIRED**: fabricated `may` at destruction removed; activation+payment retained; replacement automatic.
- **E02 AMEND_REQUIRED**: blocker-ordering removed entirely (no step/permutations/option); 2/1/4 retained as compliant assignment; declaration + assignment + pass preserved.
- **G03 APPROVED WITH FIXTURE BOUNDARY**: seeded 12 as `PRE_DECISION_CONSTRUCTION` with `BEHAVIOR_CREDIT=0`; credit only for post-boundary native behavior; no combat injection; seeded 12 not claimed simulated.
- **G04 PROMOTE**: exact 800.4a packet claims promoted; scope not broadened.
- **K02 PROMOTE**: exact 704.5j/700.4 packet claims promoted (cross-controller + variant); scope not broadened.
- **ORACLE FLAGS**: Murder/Cultivate/Ornithopter `ORACLE_TEXT_VERIFIED` adopted; no substitution.
- **RULE NUMBERS**: 702.13->701.19, 702.36->702.37, 602->118.9/601.2b, 701.19b->701.23b, 704.5c->903.10a, plus 701.38a/700.2/701.9b, applied only to RQ-C2-identified assertions.
- **ITEM 10**: exact 29 packets batch-promoted; no adjacent/candidate/fixture promotion.

## 4. New Findings

1. Turn to Frog is the only RQ-C2 `ORACLE_TEXT_VERIFIED` blue nonland card, making it the uniquely simplest C01 pitch fuel without new Oracle work (all other blue corpus cards are crosscheck-only).
2. C01 decision surface corrects from `targets`-kind pitch to `hidden-zone selection` while retaining `targets` for the Force target itself (net +1 kind for C01; FW union hidden-zone selection now has 2 contributors).
3. FW union `may` and `ordering` both go 1->0 after A03/E02 corrections (no other FW contributor), becoming the new authority for later execution (WS55 impact-adjudicated separately).
4. G04 required an explicit 4th terminal (zero triggers) beyond RQ-C1's 3 to match the packet §6 scope exactly.
5. K02 variant promotion is scope-complete only when the same-controller dies+Artist-once reading is carried as a promoted second path (packet §7); withholding it would under-promote the documented pack.
6. Validator must scope retired-phrase checks to active semantic fields (notes/directions legitimately quote retired defects as provenance).

## 5. Scenario Corrections

- **C01**: fixture now 5 untapped Islands (mana) + Force + Turn to Frog (blue nonland pitch) in P0 hand + Elves in P1 hand; script distinguishes `NORMAL_COST_AVAILABLE` (3UU) vs `ALTERNATE_COST_AVAILABLE` (1 life+exile) then chooses alternate via hidden-zone selection; terminals P0 39 / Turn to Frog exiled + Force graveyard / Elves countered; Island-blue retired.
- **H02**: both terminals `4/4 blue Frog`; events cite 7b/7c sublayer precedence; objective/reverser reframed; PATH_A 1/1 retired.
- **F02**: events reveal public to ALL; terminals hidden-again + retained knowledge usable (not leak); checkpoints before/during/after + security scope; P0-only + amnesia retired.
- **A03**: kinds/script without `may`; events replacement automatic (701.19a); citation 701.19; terminals unchanged but validated.
- **E02**: kinds/script without `ordering`; events 702.19b-compliant 2/1/4 with no ordering step; checkpoints damage-only; terminals validated.
- **G03**: boundary `PRE_DECISION_CONSTRUCTION` with seeded 12 `BEHAVIOR_CREDIT=0` detail; events prior-state (zero-credit) + native attack/damage 12->24 + 903.10a loss + leave existence; citation 903.10a; terminals validated.

## 6. Authority Promotions

- **G04**: 4 claims (P0 left/P1-3 remain; Aura left with P0; Bear under P1; zero triggers) via 800.4a+example promoted to `EXTERNALLY_RULE_VALIDATED` (see `RQ_C3_AUTHORITY_PROMOTIONS.json`). Scope matches packet §6. Candidate NOT_RUN.
- **K02**: 3 claims (coexist/no-transit; zero triggers; variant one-dies+one-Artist+kept) via 704.5j/700.4/603.10 promoted (packet §7). Rejected (a)/(b) remain rejected. Candidate NOT_RUN.
- **Item-10**: exact 29 packets (Q-A01, Q-A04, Q-B01, Q-B02, Q-B03, Q-B04, Q-C03, Q-C04, Q-D01, Q-D02, Q-D03, Q-D04, Q-D05, Q-D06, Q-E01, Q-E03, Q-F01, Q-F03, Q-G01, Q-G02, Q-G05, Q-H01, Q-I01, Q-I02, Q-I03, Q-J01, Q-J02, Q-J03, Q-K01) with their `SUPPORTED_DIRECTLY` terminals promoted. Membership verified exact; no adjacent/candidate/fixture/setup promotion.

## 7. Oracle Confirmations

Murder (`938b4e2c-88d9-4637-bc00-e228920c9a78`, ANB #53, 0 rulings), Cultivate (`8b755881-a72d-4e21-a369-d2924eb4585a`, M21 #177 + 2010 ruling), Ornithopter (`a3a98bc9-caa0-49b7-951c-fe4e4f54e4ba`, M11 #211, 0 rulings): all `ORACLE_TEXT_VERIFIED` (Gatherer-direct 2026-09-10). No substitution. See `RQ_C3_ORACLE_CONFIRMATIONS.json`. C01 pitch reuses Turn to Frog verified record.

## 8. Rule Reference Corrections

5 corrections + 3 supplied, applied only to RQ-C2-identified assertions (see `RQ_C3_RULE_REFERENCE_CORRECTIONS.json`): 702.13->701.19 (A03), 702.36->702.37 (F03), 602->118.9/601.2b (C01), 701.19b->701.23b (F01), 704.5c->903.10a (G03), 701.38a (G01), 700.2 (D01/D06), 701.9b (J03). Internally consistent (validator checks mappings + active-field usage). No global replace.

## 9. Corrected First Wave

15 IDs (traceable to RQ-C1 FW; denominator preserved; no substitution; fail-closed not triggered):

`RQ-C3-A03` (corrected), `RQ-C3-A04` (carry), `RQ-C3-B01` (carry), `RQ-C3-C01` (corrected), `RQ-C3-C03` (carry), `RQ-C3-D06` (carry+provenance), `RQ-C3-E01` (carry), `RQ-C3-E02` (corrected), `RQ-C3-F01` (carry+citation), `RQ-C3-G02` (carry+provenance), `RQ-C3-G03` (boundary), `RQ-C3-G04` (promoted), `RQ-C3-H01` (carry), `RQ-C3-I01` (carry), `RQ-C3-J02` (carry).

Plus 3 corrected non-FW derivatives: `RQ-C3-H02`, `RQ-C3-F02`, `RQ-C3-K02` (total 18 scenarios). All `NOT_RUN`, credit 0. Pack: `RQ_C3_FIRST_WAVE_EXECUTION_PACK.json`. Manifest: `RQ_C3_CORRECTED_SCENARIO_MANIFEST.json/.csv`.

## 10. Decision Requirement Delta

`RQ_C1_DECISION_REQUIREMENTS` -> `RQ_C3_CORRECTED_REQUIREMENTS` (new authority for later execution; WS55 impact-adjudicated separately):

- `may`: A03 contributes -> none (FW union 1->0).
- `ordering`: E02 contributes -> none (FW union 1->0; not retained for WS55).
- `hidden-zone selection`: F01 only -> F01 + C01 (C01 pitch corrected from `targets` to hidden-zone; `alternate cost` fork retained with NORMAL/ALTERNATE distinguished).
- `combat damage assignment`: E02 retained (2/1/4).
- All other kinds unchanged (see `RQ_C3_DECISION_REQUIREMENT_DELTA.json` per-scenario added/removed + `RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json` union).

## 11. Hidden Information Delta

Authorized visibility vs learned vs leakage vs public vs hidden-again (pilots must not forget legitimately observed info; security = unauthorized disclosure):

- F02: before private to P1/authorized; during PUBLIC TO ALL (701.20a); after hidden again BUT retained knowledge usable (not leak); no forced forgetting.
- C01: pitch hidden-zone (Turn to Frog known only to P0 until exile, public after); stack + route availability public to ALL.
- Others carried (J03 no-reveal contrast preserved). See `RQ_C3_HIDDEN_INFO_EXPECTATIONS.json`.

## 12. Setup Boundary Status

35 `NATURAL_GAME_START` + 4 `PRE_STEP_NATIVE_PROGRESSION` (E01/E02/E03-equivalent; E02 reshape preserves verdict) carried as CAPABLE; G03 `PRE_DECISION_CONSTRUCTION` CAPABLE-WITH-SOL-CONFIRMATION now APPROVED with explicit `BEHAVIOR_CREDIT=0` for seeded 12 and candidate-credit scope limited to post-boundary native behavior. No injection during combat. No redesign required. See `RQ_C3_SETUP_BOUNDARIES.json`.

## 13. Parent Immutability

RQ-C1 and RQ-C2 remain byte-identical (validator: `git status --porcelain` and `git diff HEAD` clean for both dirs; per-file sha256/git-blob hashes in `RQ_C3_PARENT_HASHES.json` match current; scenario parent hashes match). All corrected material under `research/candidate-qualification/common/rq-c3/**`. No in-place amendment. See `RQ_C3_PARENT_IMMUTABILITY.json`.

## 14. Changes

All changes scoped to `research/candidate-qualification/common/rq-c3/` (new files only):

- 2 MD locks/transcriptions, 12 JSON layers, 1 CSV, 18 scenario JSONs, 1 validator, 1 state file, this report.
- No modification to `rq-c1/`, `rq-c2/`, engine, provider, harness, or test helpers. No fallback legality created. Final diff inspected for unrelated semantic changes, hidden fallback, weakened assertions, leakage, unintended API changes (none found; validator enforces no weakening).

## 15. Tests / Evidence

- `python3 research/candidate-qualification/common/rq-c3/validate_rqc3.py`: **PASS** all checks: parent immutability (2), 15 FW IDs + manifest match, no dups + files match, C01 pitch/routes/fixture (6), A03 (3), E02 (4), F02 (3), H02 (3), G03 (4), G04/K02 scope (7), item-10 exact 29 (2), no overbroad + no TECHNICALLY_CONFORMANT + NOT_RUN (3), rule refs (8 + 2 spot), parent hashes (3), NOT_RUN/credit (3), deterministic rebuild + CSV (2), plus **6 negative controls rejected** (Island-as-pitch, A03 may, E02 ordering, H02 1/1, F02 private-only, overbroad promotion).
- Evidence classes: `DIRECTLY_VERIFIED` (transformation/validation facts: branch/HEAD/tree/status, hashes, CR sha, validator PASS), `EXTERNALLY_RULE_VALIDATED` (Sol-approved expected outcomes only: 54 assertions), `MODELED_PENDING_CANDIDATE_EXECUTION` (seeded construction 1 + future conformance NOT_RUN), `UNKNOWN` (closed-world for unlisted), `SYNTHETIC` (negative controls only). No `TECHNICALLY_CONFORMANT` awarded. No candidate behavior credit.
- Determinism: all JSON canonical (`sort_keys`, indent 2); CSV sorted; double-serialization equal.

## 16. PASS / FAIL / UNKNOWN

**`RULES_AUTHORITY_CLOSURE_PASS`** (corrected 15-scenario First Wave mechanically complete; every execution assertion has explicit authority status).

## 17. Remaining Blockers

None for closure. Candidate execution blockers are external dependencies (see below), not RQ-C3 defects. No corpus redesign required.

`BEHAVIOR_CREDIT_CHANGE = 0`. `FULL107 = NOT_RUN`. `ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.

## 18. Outputs

Under `research/candidate-qualification/common/rq-c3/`:

`RQ_C3_SOURCE_LOCK.md`, `RQ_C3_COORDINATOR_ADJUDICATION.md`, `RQ_C3_PARENT_IMMUTABILITY.json`, `RQ_C3_CORRECTION_APPLICATION.json`, `RQ_C3_AUTHORITY_PROMOTIONS.json`, `RQ_C3_RULE_REFERENCE_CORRECTIONS.json`, `RQ_C3_ORACLE_CONFIRMATIONS.json`, `RQ_C3_CORRECTED_SCENARIO_MANIFEST.json`, `RQ_C3_CORRECTED_SCENARIO_MANIFEST.csv`, `RQ_C3_FIRST_WAVE_EXECUTION_PACK.json`, `RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json`, `RQ_C3_DECISION_REQUIREMENT_DELTA.json`, `RQ_C3_HIDDEN_INFO_EXPECTATIONS.json`, `RQ_C3_SETUP_BOUNDARIES.json`, `RQ_C3_EXECUTION_ASSERTION_AUTHORITY.json`, `RQ_C3_PARENT_HASHES.json`, `RQ_C3_FINAL_REPORT.md` (this file), `WORKSTREAM_STATE.yaml`, `validate_rqc3.py`, `scenarios/RQ-C3-*.json` (18).

## 19. Dependencies Unblocked

`FIRST_WAVE_RULES_AUTHORITY_READY = YES` — corrected 15-scenario First Wave is rules-ready for later candidate instantiation unchanged (Forge/XMage/Argentum-iff-qualified) after downstream gates.

`FORGE_EXECUTION_AWAITS_WS55 = YES` — Forge First-Wave execution awaits Coordinator impact-adjudication of WS55 against the new `RQ_C3_CORRECTED_REQUIREMENTS` delta (WS55 work not invalidated here).

`XMAGE_EXECUTION_AWAITS_WS54_SUCCESSOR_REQUALIFICATION = YES` — XMage execution awaits WS54-successor requalification (unchanged by RQ-C3).

`ARGENTUM_EXECUTION_AWAITS_RQ_A2 = YES` — Argentum execution awaits RQ-A2 justification (unchanged by RQ-C3).

Do not execute any candidate (none executed here).

## 20. Exact Next Action

Coordinator (Sol High): impact-adjudicate WS55 against `RQ_C3_DECISION_REQUIREMENT_DELTA.json` (may/ordering removals + C01 hidden-zone correction), then authorize unchanged-instantiation of the RQ-C3 First Wave against the next qualified candidate lane.

`BEHAVIOR_CREDIT_CHANGE = 0`. `FULL107 = NOT_RUN`. `ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
