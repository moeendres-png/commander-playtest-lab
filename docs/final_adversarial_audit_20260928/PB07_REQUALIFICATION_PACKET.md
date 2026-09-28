# PB-07 Requalification Packet — Engine Rebinding + 29-Row Plan

Independent DeepSeek lab. Read-only/evidence engineering: nothing in Forge PR #6, #284, #289,
#292, or any foreign implementation surface was modified. Machine-readable twins:
`ENGINE_REBINDING_RECEIPT.json`, `PB07_29_ROW_REQUALIFICATION_MATRIX.json`.

## 1. ENGINE_REBINDING_RECEIPT

- Forge PR #6 commit: `6f70e32e81025fd8a6eaf08d475f8282b7f03dc9`
- PR #6 full tree: `5fa5b9470ef6dcdc3383c23652f18b81c1abe364`
- PR #6 `forge-game` main-source tree: `3d31b13fbc8db6963998af551724ea3ff775f625`
- Predecessor Rules Core: `ef958ee91ac6c9ce0152189f2654bf6e05abf273` / tree `fc3387bf37aab19d780b2939a235309ed32b0492`
- Predecessor bridge/evidence: `e15f37d6b2b5c0ad682948f86f037e07b6aaded5` / tree `a1d4d4a8fe421e57b919e8e0bd9fda7d9deb0d3b`
- Modules identical to the predecessor: `forge-core`, `forge-ai`, `forge-gui`, `forge-gui-desktop`, `adventure-editor`
- Modules differing: `forge-game`
- Engine change: `Card.java` +24 (alternate split-card state enumeration in getAllPossibleAbilities)
- Lab `verify_engine_identity(ef958 -> PR #6)`: raised=True, `ReceiptError`: CANDIDATE_IDENTITY_DIVERGENCE: forge PR6 engine records ef958ee91ac6 but executes at 6f70e32e8102, and the engine is not provably the same: differing=['forge-game'] one_sided=[] compared=6. No credit.
- **`RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL = FALSE` for this successor.** Identity
  validation was not weakened to make it pass; the bridge-only-descendant equivalence
  simply does not cover an engine-tree change.

### Evidence invalidated by that fact

- native-forge-direct.json and native-forge-mechanism.json: their engine identity proof (RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL ef958) does not hold for the PR #6 engine tree
- SOURCE_LOCK.json forge engine binding FORGE_CANDIDATE_COMMIT=ef958 and every engine-identity-derived field
- AF00/PB-05 provenance credit conditioned on the ef958 engine identity
- FULL107_FORGE_RESULTS.json runtime_identity rows (engine_candidate_commit ef958, adapter_commit e15f37d6) and any row claiming the old engine identity
- PROVIDER_READINESS_PACKET Forge identity table and native receipt table

### Evidence that may survive impact adjudication

- XMage evidence and XMage candidate identity (untouched by the Forge engine change)
- Lab harness/runner code and its tests (no semantic dependency on the change)
- Non-split actual-card obligations: the engine delta only adds alternate split-half abilities, so non-split runtime behavior is semantically unaffected; their prior outcomes may be reused as candidate-side input once re-bound to PR #6 identity
- Committed split-family tests re-executed at the PR #6 head in CI (WsR11FuseBridgeFamilyTest, WsR11BoseijuBridgeFamilyTest, desktop suite)

### Native-suite receipts requiring rebinding

- `qualification/final-current-boundary-20260927/receipts/native-forge-direct.json` (recorded candidate `ef958ee91ac6`, executed `e15f37d6b2b5`) -> re-execute at the PR #6 checkout and re-bind candidate/executed identity
- `qualification/final-current-boundary-20260927/receipts/native-forge-mechanism.json` (recorded candidate `ef958ee91ac6`, executed `e15f37d6b2b5`) -> re-execute at the PR #6 checkout and re-bind candidate/executed identity

## 2. PB-07 29-ROW REQUALIFICATION MATRIX

Denominator: 29 rows from `commander-playtest-lab/qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json#regression_corpus_29`; order preserved. Lab behavior credit currently **0/29**.

| # | Card | Prior | Candidate-side evidence | Classification | Reason (short) |
|---|---|---|---|---|---|
| 1 | Ishai, Ojutai Dragonspeaker | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 2 | Rograkh, Son of Rohgahh | RUNTIME_QUALIFIED | `BridgeEngineTest`, `Ws234S3CardBehaviorTest`, `WsR11JeskaBridgeFamilyTest`, `WsR20Full107DenominatorTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 3 | Esior, Wardwing Familiar | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 4 | Kediss, Emberclaw Familiar | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR10KedissBridgeFamilyTest`, `WsR11JeskaBridgeFamilyTest`, `WsR15MulticountTriggerTest`, `WsR16SixPlayerFamilyTest`, `WsR20Full107DenominatorTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 5 | Veyran, Voice of Duality | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `WS236F4BridgeTest`, `Ws234S3CardBehaviorTest`, `Ws236F4SpellcastDiscriminatorTest`, `Ws236S1KaervekDrainTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 6 | Harmonic Prodigy | RUNTIME_QUALIFIED | `WS236F4BridgeTest`, `Ws234S3CardBehaviorTest`, `Ws236F4SpellcastDiscriminatorTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 7 | Narset, Parter of Veils | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest`, `WsR6DrawEventFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 8 | Jeska, Thrice Reborn | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR11JeskaBridgeFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 9 | Magma Opus | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR10MagmaBridgeFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 10 | Wash Away | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `Ws234CleaveAftermathTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 11 | Wear // Tear | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR11FuseBridgeFamilyTest` | `SPLIT_SURFACE_REQUIRED` | engine delta touches alternate split-half enumeration; the obligation must be re-observed at the PR #6 engine identit... |
| 12 | Dig Through Time | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 13 | Flare of Duplication | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR9RetargetBridgeFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 14 | Vandalblast | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest`, `WsR8OverloadFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 15 | Finale of Revelation | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR9FinaleX10BridgeFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 16 | Psychosis Crawler | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `Ws234S3CardBehaviorTest`, `WsR20Full107DenominatorTest`, `WsR24Pb07MechanicProbesTest`, `WsR6DrawEventFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 17 | Kaervek the Merciless | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `Ws234S3CardBehaviorTest`, `Ws236S1KaervekDrainTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 18 | Shriekmaw | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest`, `WsR9EvokeFearFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 19 | Butcher of Malakir | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 20 | Syphon Mind | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 21 | Gratuitous Violence | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 22 | Bolt Bend | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR9RetargetBridgeFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 23 | Makeshift Mannequin | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 24 | Warstorm Surge | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `Ws234S3CardBehaviorTest`, `WsR20Full107DenominatorTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 25 | Basilisk Collar | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 26 | Burn Down the House | RUNTIME_QUALIFIED | `WS234S3BridgeTest`, `WsR24Pb07MechanicProbesTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 27 | Path of Ancestry | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR10PathSimFamilyTest`, `WsR13PathBridgeFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |
| 28 | Find // Finality | RUNTIME_QUALIFIED_FRONT_PLUS_ENGINE_GAP | `DeepseekAftermathDiscoveryTest`, `Ws234CleaveAftermathTest`, `WsR24Pb07MechanicProbesTest` | `SPLIT_SURFACE_REQUIRED` | engine delta touches alternate split-half enumeration; the obligation must be re-observed at the PR #6 engine identit... |
| 29 | Boseiju Reaches Skyward // Branch of Boseiju | RUNTIME_QUALIFIED | `Ws234S3CardBehaviorTest`, `WsR11BoseijuBridgeFamilyTest` | `INHERITABLE_AFTER_IMPACT_ADJUDICATION` | committed behavior test class at the PR #6 head names this obligation and ran in the PR #6 CI suites; usable as candi... |

Counts (independently re-derived from current source truth): **INHERITABLE_AFTER_IMPACT_ADJUDICATION = 27, SPLIT_SURFACE_REQUIRED = 2**.

Derivation method: a card counts as candidate-side covered when at least one committed
behavior test class at the PR #6 head names it; preparation-only classes and the deck
recognizer are excluded. Name mention is necessary, not sufficient - the classification is
candidate-side input subject to the Lab's own impact adjudication.

Correction note: a preliminary v1 derivation based only on the stale PB-07 evidence strings
gave 11 inheritable / 16 fresh / 2 split. Re-deriving from the PR #6 test sources shows the
probe class `WsR24Pb07MechanicProbesTest` (and `Ws234S3CardBehaviorTest`) now contain
committed behavioral tests for those cards and ran in the PR #6 CI suites, so the v1.1
counts above supersede the preliminary ones.

Per-row commands, expected artifacts and terminal classification rules are in the JSON
matrix. The promotion rule is explicit: no row receives Lab PASS from Forge unit/native
tests; Lab credit requires a fresh pinned runtime observation at the exact candidate
identity.

## 3. EXACT_RERUN_COMMANDS

Candidate-side (committed test classes at the PR #6 checkout):

```sh
mvn -o -pl <module> -am test -Dtest=<Class> \
  -Dsurefire.failIfNoSpecifiedTests=false -Dcheckstyle.skip=true
# module is forge-protocol2-bridge for Ws*/WS*/BridgeEngineTest classes,
# forge-gui-desktop for forge.gamesimulationtests classes
```

Canonical Lab rerun (after the DS-07 repair lands; FORGE_WORKSPACE must be the exact
PR #6 checkout):

```sh
FORGE_WORKSPACE=<PR6-exact-checkout> PYTHONPATH=$PWD/src <venv>/bin/python scripts/run_current_boundary_qualification.py --candidate forge
```

DS-07 repair gate command (attribute to the PR #6 owner, do not push):

```sh
mvn -o -pl forge-protocol2-bridge -am test \
  -Dtest='WsR24Pb07MechanicProbesTest,WsR11FuseBridgeFamilyTest,WsR11BoseijuBridgeFamilyTest' \
  -Dsurefire.failIfNoSpecifiedTests=false -Dcheckstyle.skip=true
```

## 4. EVIDENCE_IMPACT_ADJUDICATION

- **Binding-level impact**: every Forge artifact that names `engine_candidate_commit`
  `ef958ee9` or relies on the `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL` proof must be
  re-bound to the PR #6 engine tree (`forge-game` main-source tree
  `3d31b13fbc8db6963998af551724ea3ff775f625`). Prior PASS is not carried forward silently.
- **Behavioral impact**: the engine delta only adds alternate split-half abilities in
  `getAllPossibleAbilities`. Only the two split corpus cards change their enumerable
  option sets; non-split card behavior is semantically untouched, so non-split prior
  outcomes remain valid as *candidate-side input* once re-bound.
- **Split surfaces**: `Wear // Tear` (Fuse) is green at the PR #6 head in independent runs
  (6/6 with Boseiju collateral). `Find // Finality` becomes green once the validated
  13-line `answerCommon` `COPY_CHOICE` repair lands; that repair is harness-only and does
  not alter product behavior.
- **Lab credit**: unchanged at 0/29. Import/construction/readback never count; Forge
  unit/native green is candidate-side input only.

## 5. DS07_GATE_STATUS

- Forge PR #6 final read: **unchanged at `6f70e32e81025fd8a6eaf08d475f8282b7f03dc9`**, DRAFT,
  `mergeStateStatus: UNSTABLE`; the Java 17/21 CI failure is exactly DS-07
  (`WsR24Pb07MechanicProbesTest.testFindAndAftermath -> unexpected COPY_CHOICE for p1`).
- Gate classification: **`PB07_RUNTIME_ENTRY = WAIT_FOR_DS07_INTEGRATION`**.
- The validated repair (13 lines, first entity option on `COPY_CHOICE`) is posted on PR #6
  and makes the class 16/16 locally; the packet is fully prepared so the green-head rerun
  can begin without another audit cycle.
- When the head changes: verify the new head/tree, run the full affected bridge suite, run
  the Fuse/Boseiju collateral checks, sample the 16 fresh rows where technically possible,
  and update the receipt to the new exact identity.

## 6. CURRENT_SOURCE_LOCK

| Item | Value |
|---|---|
| Lab main | `afe09c61d4ad90f89c28ff75ac7439a20b89cfdd`, tree `0d5b3f0d9020cc99131dd92a41a9615c61bbac8a` |
| Forge PR #6 | `6f70e32e81025fd8a6eaf08d475f8282b7f03dc9`, tree `5fa5b9470ef6dcdc3383c23652f18b81c1abe364`, DRAFT |
| PR #6 engine tree | `forge-game` main-source `3d31b13fbc8db6963998af551724ea3ff775f625` |
| Predecessor Rules Core | `ef958ee91ac6c9ce0152189f2654bf6e05abf273`, tree `fc3387bf37aab19d780b2939a235309ed32b0492` |
| Predecessor bridge/evidence | `e15f37d6b2b5c0ad682948f86f037e07b6aaded5`, tree `a1d4d4a8fe421e57b919e8e0bd9fda7d9deb0d3b` |
| #289 (Space Bunny) | `0d010fe16d0ba5d50d41300223f83d5bc6b679b3`, DRAFT, WAIT_FOR_MERGE |
| #292 (Muse PB-03) | `2c1df76fc6a03f4e786c766ca5bc02e8ebbed578`, OPEN, NON_OVERLAPPING |
| Audit branch | `docs/final-adversarial-audit-20260928` at `e5c892fb` + this packet commit |

## 7. Exact Next Action

1. Coordinator routes the validated DS-07 repair to the PR #6 owner (no DeepSeek write).
2. On the repaired head: re-run the packet's Phase-3 checks and update
   `ENGINE_REBINDING_RECEIPT.json` to the new exact identity.
3. Lab owner re-binds `FORGE_CANDIDATE_COMMIT`/engine identity to the PR #6 engine tree,
   re-executes the two native receipts, and runs the canonical Forge-only current-boundary
   rerun; then requalify the 29 rows per the matrix (27 inheritable candidate-side after re-binding, 0 fresh, 2 split-surface).
4. No PB-07 29/29 promotion before that pinned runtime execution.

Flags: `ENGINE_REBINDING_PACKET = COMPLETE`; `PB07_RERUN_PACKET = COMPLETE`;
`DS07_GATE = WAIT_FOR_INTEGRATION`; `LAB_PB07_BEHAVIOR_CREDIT = 0/29`;
`PRODUCTION_PROVIDER = NOT SELECTED`; `ARCHITECTURE_FREEZE = NOT CLAIMED`.

