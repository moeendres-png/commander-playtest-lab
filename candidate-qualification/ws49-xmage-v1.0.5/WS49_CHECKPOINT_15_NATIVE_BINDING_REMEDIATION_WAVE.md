# WS49 CHECKPOINT 15 — Native-Binding Remediation Wave (Phases 0-5, no Full107)

Status: **IMPLEMENTATION COMPLETE / NO BEHAVIOR CREDIT / NO FULL107**
`COVERAGE_PROMOTION=FALSE`. `TASK_COMPLETE=NO`. `TURN_STATUS=INTERRUPTED` (workstream continues).

## 1. Source Lock

- Commander-Lab successor implementation branch (this checkpoint):
  `ws49/xmage-v1.0.5-native-remediation` @ base `7c3e3d2af474cbf9cdda6f9dd694f68e5cdb2c10`
  / tree `8dfc4bcbe65f1b3f43ef9805a6363343d137414b` (exact expected source).
  Worktree: `/home/moeen/code/ws49-remediation` (isolated; canonical
  `ws49/xmage-v1.0.5-successor-qualification` at same HEAD left untouched,
  its pre-existing dirty `run_full107_behavior_probe_v105.py` patch preserved
  at `/tmp/opencode/ws49_canonical_dirty.patch`, NOT committed here).
- Canonical qualification branch verified before fork:
  `origin/ws49/xmage-v1.0.5-successor-qualification` =
  `7c3e3d2af474cbf9cdda6f9dd694f68e5cdb2c10`, tree `8dfc4bc...`, remote match.
- XMage immutable inspection pin (read-only, terminal authority):
  `moeendres-png/mage@0c1f455ea8c8fa48ab9d638ad5068ec242800428`
  / tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649` — HEAD/TREE MATCH.
  Baseline worktree `/home/moeen/code/xmage-ws49-baseline` dirty (7 local-only
  files incl. WS-39 RNG-tape instrumentation) — NOT committed, NOT used as
  terminal evidence; all XMage facts below via `git show`/`git grep` at pin.
- WS47 immutable contract: freeze `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`,
  materialization SHA-256 `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`.
- Retained sealed Full107 baseline: run `34412882569`
  (workflow `WS49 XMage v1.0.5 Full107 Behavior`, head `925d21a9`,
  conclusion `success`, behavior credit `0/107`). **Not rerun. No promotion.**

## 2. Branch / Ownership

- New branch `ws49/xmage-v1.0.5-native-remediation` from exact `7c3e3d2a`;
  worktree `/home/moeen/code/ws49-remediation`, clean at fork, owned by this
  remediation wave. Canonical branch NOT rewritten in place.
- Authority: XMage Rules Core owns legality. Provider/harness exposes native
  options and matches externally specified discretionary selection uniquely
  against those options. No second rules engine. All forbidden fallbacks
  (label-guessed legality, expected-outcome selection, first option, default
  yes/no, cancel filtering, auto-pass, AI fallback, fabricated identity,
  manual injection) remain prohibited and fail closed.

## 3. Broad-Pass Revert (Phase 0)

- Reverted runner-v3 broad predicate
  (`ops != ["NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE"]` → True for
  107/107 records) to the explicit v2 allowlist (True for 47/107):
  `NATIVE_CONTINUE_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES_UNTIL_NEXT_DECLARED_DECISION`,
  `NATIVE_RESOLVE_CAST_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES`,
  `NATIVE_RESOLVE_OR_EVALUATE_DECLARED_RULES_CAUSE_TO_TERMINAL_CHECKPOINT`,
  `NATIVE_RESOLVE_TOP_OF_STACK`, `NATIVE_RESOLVE_TRIGGER`.
- 60 records lose pass authority under the revert, including the regression
  case `PILOT_DECLARE_ATTACKER` (`NATIVE_ENTER_DECLARE_ATTACKERS_STEP` +
  `NATIVE_DECLARE_ATTACKERS`): broad=True, allowlist=False → now correctly
  `WS49_BEHAVIOR_PRIORITY_PASS_NOT_DECLARED` instead of auto-pass.
- HIDDEN `NATIVE_KNOWLEDGE_PROJECTION` and bare-construct sequences grant no
  pass authority. R2 normalization untouched.

## 4. Native Selector Binding (Phase 1, R-c)

- Source proof at pin: `Target.possibleTargets` / `canTarget`
  (`Mage/target/Target.java:100-186`, `TargetCard:64`, `TargetAmount:204`);
  bridge `XmageFullGamePlayer.chooseTargetInternal` / `chooseTargetAmount`
  builds offers **exclusively** from `possibleTargets` (already native legal
  set). `TestPlayer` strict-choose mode fails closed on unscripted choices
  (`TestPlayer.java:setChooseStrictMode`, `chooseStrictModeFailed`) — the
  runner mirrors this discipline.
- Runner hardening: `profile_match_object` now reads native `pilot_state`
  `players[]` buckets (fixing top-level-only inventory that missed
  battlefield/hand/etc.), preserves exact native handles/provenance,
  requires 1:1 unique match (zero/multiple fail closed), and checks offer
  provenance coherence (`owner_ref`/`controller_ref`/`zone`/`counters` where
  published). `_profile_agrees` now enforces owner/controller/counters
  (empty-vs-nonempty counters mismatch fails). `semantic_player` retains
  seat-label coherence but requires native `player_ref`/`seat` provenance
  where published; label alone never authorizes.
- Bridge enrichment (`XmageFullGamePlayer.objectOptions/objectMetadata`):
  player options carry `player_ref`+`seat`; permanents carry
  `owner_ref`/`controller_ref`/`zone`/`tapped`/`face_down` — all from native
  `game` lookups, no legality invention. Evidence: CODE_DERIVED (bridge
  runtime UNKNOWN pending CI build; Maven offline cannot resolve
  `org.mage:mage:1.4.61` without the CI XMage install step).
- Negative tests (offline): same-name different owner / controller reject;
  same-name same-zone multiples fail; stale handle fails; illegal target
  fails; player multi-offer and provenance-mismatch fail.

## 5. Native Mana Binding (Phase 2, R-g)

- Source proof at pin: `Player.getPlayable` / `getPlayableOptions` /
  `getManaAvailable` (`Player.java:852-864`), `ManaOptions`
  (`abilities/mana/ManaOptions.java`); bridge `playMana` publishes ONLY
  native `getPlayable` mana abilities + native pool contents.
- Runner hardening: `match_mana_payment` merge is now actor-scoped (global
  singleton for another actor → `MANA_SOURCES_UNAVAILABLE`, not silent use);
  cast arming in `execute_decision_driven` is source-scoped even for
  singletons (`source_semantic_id == cast_object` required; commander
  null==null still arms). Multiple payables without unique source match arm
  nothing (downstream mana frame fails closed). No "best" payment invented.
- Fixtures: `PILOT_MANA_PAYMENT` + `MICRO_MANA_PAYMENT` (independent, same
  capability) validated structurally.

## 6. Hidden-Information Binding (Phase 3, R-h)

- Source proof at pin / bridge: `GameView(GameState, game,
  createdForPlayerId, watcherUserId)` (`Mage.Common/.../GameView.java:72`),
  `RevealedView`/`LookedAtView`, `CardView` face-down handling, ledger
  `snapshot(game, viewer, subject)` + `forbiddenIdentityTokens` + gateway
  `HIDDEN_INFORMATION_LEAK` fail-closed audit.
- Runner hardening: `execute_hidden` queries the NATIVE principal set
  (P1..Pn), not just declared viewers; `knowledge_projection:` events emit
  ONLY after native per-viewer verification (observation-gated);
  `verify_viewer_states` requires the native player set, checks own-hand
  visible / opponent-hand hidden from native buckets, face-down exile
  redaction (`Hidden card`), face-down battlefield observation, library
  entitlement (`known_library`), with missing surfaces emitting nothing (no
  false PASS). Declared viewer list alone grants zero credit; unverified
  declared viewers fail (`HIDDEN_NATIVE_VERIFICATION_MISSING`).
- Covers the 7 required cases (own/opponent/revealed/face-down-exile/
  face-down-battlefield/library/stale) at the observation-gate level;
  post-shuffle stale knowledge never retained (no cross-call cache).

## 7. Extra-Turn / SBA Binding (Phase 4, R-k)

- Source proof at pin: `TurnMod.isExtraTurn` (`turn/TurnMod.java:188`),
  `TurnMods` extra-turn LIFO (`TurnMods.java:44`), `GameState.isExtraTurn`,
  SBA `hasLost/hasLeft` buckets (already native products).
- Runner hardening: `derive_elim_and_ring` keeps SBA-derived elim
  (`has_left`/`has_lost` decide; cleanup gates on owned-object zones) but
  (a) extra-turn emits ONLY on attributed native turn surfaces (never UUID
  identity; unattributed → no emit, fail closed), and (b) priority-ring order
  is NEVER derived from the runner's own pass transcript (transcript ignored;
  ring = native live players in seat order or nothing).
- Fixtures: `WS05-MP-TURN-3` (extra-turn) + `WS05-MP-ELIM-OWNED-3` (elim).

## 8. RNG Funnel Audit (Phase 5)

- Enumeration at pin (`Mage/src/main/java`): PROVEN funnel via
  `RandomUtil.setSeed` — `Library.shuffle` (Fisher-Yates `nextInt`),
  `PlayerImpl.flipCoinResult` (`nextBoolean`), `rollDiceInner` (`nextInt`),
  `GameImpl` starting-player pick (`nextInt`), `CardsImpl.getRandom`
  (`randomFromCollection`), `Rotater`/`MatchImpl` via `getRandom()`.
  `XmageFullGameSession` applies `RandomUtil.setSeed(seed)` pre-shuffle:
  the native seed seam IS the deterministic construction seam for the
  qualification `NATIVE_LIBRARY_SHUFFLE` channel (all 5 replay_rng records).
- UNCOVERED (exact, NOT via seed seam): `PlayerImpl:1061`
  `putCardsOnBottomOfLibrary` random order (`Collections.shuffle` default),
  `PlayerImpl:1204` `putCardsOnTopOfLibrary` ditto, `RandomBoosterDraft:47`,
  `SwissPairingMinimalWeightMatching:45`, `TokenRepository:423`
  `new Random(ID)`. None in the 107 denominator; all production-reachable
  and UNKNOWN for per-channel completeness.
- Implementation: `assert_rules_shuffle_tape` now emits ONLY generic
  `rules_rng_tape_valid` (authority + pilot-mixed + count gates); per-channel
  `rules_rng:*` withheld absent tape operation attribution. No global-seed
  completeness claim. Per-channel attribution + semantic replay remain
  separate (double-run in `DOUBLE_RUN_FIXTURES` retained).

## 9. Changes

- `candidate-qualification/ws49-xmage-v1.0.5/run_full107_behavior_probe_v105.py`
  (Phases 0-5 runner hardening, R2 untouched).
- `engine-bridge/.../XmageFullGamePlayer.java` (R-c provenance enrichment).
- `candidate-qualification/ws49-xmage-v1.0.5/test_ws49_native_binding_remediation.py`
  (new, 54 offline assertions).
- This checkpoint file.

## 10. Tests / Evidence

- `py_compile` runner: PASS.
- `test_ws49_r2_frame_vocabulary.py`: ALL PASS (R2 preserved).
- `test_ws49_native_binding_remediation.py`: **54 passed, 0 failed** (offline,
  no engine; per-phase source proof + synthetic negative tests + WS47 fixture
  structural checks for two independent fixtures per phase).
- Bridge `mvn compile`: NOT runnable offline (missing `org.mage:mage:1.4.61`
  until CI installs the pinned XMage build) → bridge runtime UNKNOWN.
- No Full107 launched. No engine behavior executed here.
- Evidence classification: runner logic CODE_DERIVED; WS47 byte checks
  DIRECTLY_VERIFIED; native API existence CODE_DERIVED (not runtime);
  all engine-runtime PASS claims UNKNOWN.

## 11. Actual Fixtures Exercised (offline structural, no engine credit)

- P0: `PILOT_PRIORITY` (allow), `PILOT_TARGET` (allow, independent),
  `PILOT_DECLARE_ATTACKER` (regression, no pass).
- P1: `MICRO_TARGETS` (semantic_player), `PILOT_CHOOSE_OBJECT`
  (semantic_object, independent).
- P2: `PILOT_MANA_PAYMENT`, `MICRO_MANA_PAYMENT` (independent).
- P3: `HIDDEN_01`, `HIDDEN_02` (independent).
- P4: `WS05-MP-TURN-3` (extra-turn), `WS05-MP-ELIM-OWNED-3` (elim).
- P5: `RNG_RULES_TAPE`, `REPLAY_DECISION_TAPE` (independent).
- PASS claims NOT combined across phases.

## 12. PASS / FAIL / UNKNOWN

- Offline regression: 54/54 PASS (CODE_DERIVED).
- R2 preservation: PASS (DIRECTLY_VERIFIED).
- Engine behavior (all phases): UNKNOWN (no Full107 by order).
- Full107: NOT_RUN (retained baseline `34412882569` untouched, 0/107).
- FAIL: 0. No new engine/rules defect established.

## 13. Retained R2 Impact

- R2 files/logic unchanged; R2 test suite passes unmodified. No bounded R2
  adjustment was required (frame/event aliases orthogonal to pass/target/
  mana/hidden/sequence/RNG gates). Impact: NO_IMPACT on R2 evidence.

## 14. Remaining Repair DAG

- CI build + qualified Full107 on this branch (future work, NOT this wave):
  needs XMage `mvn install` at pin, bridge `mvn verify`, inventory +
  behavior probe from record 1 with sealed artifacts; expect new
  fail-closed diagnostics (provenance mismatches, actor-scoped mana gaps,
  hidden native-set deltas, ring/extra-turn attribution gaps) to triage.
- Per-channel RNG attribution tape (operation→channel) still open.
- Revealed/looked-at/library-range positive hidden proofs need live-offer
  corroboration in CI.
- `CARD_02`/AF04-09 gates remain NOT_RUN (blocked on G49-09).

## 15. Full107 Readiness

- NOT READY for credit: this wave authorizes NO Full107 and grants zero
  behavior credit. Next qualified Full107 must run from a frozen HEAD of
  THIS branch via `.github/workflows/ws49-xmage-v105-behavior.yml` with
  exact WS47/XMage pins, full 107 from record 1, sealed artifacts, and
  independent adjudication. `COVERAGE_PROMOTION=FALSE`.

## 16. Outputs

- Branch `ws49/xmage-v1.0.5-native-remediation` (this checkpoint + code + tests).
- Test report above; `git diff --stat` runner + bridge + new test.

## 17. Exact Next Action

- Commit this checkpoint + runner + bridge + test on
  `ws49/xmage-v1.0.5-native-remediation`, push, open NO PR merge; then freeze
  an exact HEAD/TREE, register a PENDING CI behavior run (workflow
  `WS49 XMage v1.0.5 Full107 Behavior`) WITHOUT claiming credit, and triage
  its fail-closed diagnostics per-phase. Do NOT touch the canonical
  qualification branch or rerun construction/normalization for reassurance.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
