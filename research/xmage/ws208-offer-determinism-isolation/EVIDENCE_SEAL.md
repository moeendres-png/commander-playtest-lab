# WS208 Evidence Seal — XMage Offer Enumeration Nondeterminism Isolation

Source Lock: repo `moeendres-png/commander-playtest-lab`,
branch `ws208/xmage-offer-determinism-isolation-20260914`,
audit base `1dee8b77f7243900eec5a7cc05fb1fe26467aea9`,
XMage pin `cfc36f445f917f101fa2ed588770e043f53bc44c` (unmutated).
WS205 evidence authority preserved (read-only; zero WS205 files touched).

## Verdict

`WS208_XMAGE_OFFER_DETERMINISM = XMAGE_ENGINE_SIDE_BLOCKED_WITH_SUCCESSOR`
(first divergence layer A — underlying XMage game state — with exact engine
mechanism; see ROOT_CAUSE below). No bridge production change. No behavior
credit. Semantic Completion: causal layer isolated ⇒ COMPLETE per contract
(`XMAGE_ENGINE_SIDE_BLOCKED_WITH_SUCCESSOR` is a valid terminal outcome).

## ROOT_CAUSE (DIRECTLY_VERIFIED runtime + CODE_DERIVED call chain)

`mage.game.GameImpl.<init>` seeds the per-game Rules RNG from unseeded entropy:

- `UUID uuid = UUID.randomUUID()` → `rulesSeed = msb ^ lsb` →
  `rulesRandom = new GameRandom(rulesSeed)` (`rulesSeedExplicit=false`).
- Game-start shuffle chain: `GameImpl.init(UUID)` → per player
  `player.shuffleLibrary(null, game)` → `PlayerImpl.shuffleLibrary` →
  `library.shuffle(game.getRulesRandom())`.
- The Lab bridge sets ONLY `RandomUtil.setSeed(seed)` (process-global
  `mage.util.Random`), which never reaches `rulesRandom`; `setRulesSeed`
  exists but has zero references in `engine-bridge/src/main/java`.

Runtime proof (32 fresh JVMs, twin-mode exact-prefix replay, budget 500):

- Pre-start library order + `RandomUtil` probes P1/P2: IDENTICAL across JVMs.
- Post-start (offset-1, pre-draw) libraries: DIFFER in every heterogeneous deck.
- Hands differ from the first draw; offer SETs diverge downstream (±1
  duplicate basic-land `PlayLandAbility`; H01 Clone never drawn in 6/6 reps
  vs cast in WS205 primary at offset 411).
- Native-SET diff offsets == projected-SET diff offsets EXACTLY in all 8
  constructions (bridge membership-transparent); ZERO offsets with equal
  hidden state but different native offers (native enumeration faithful);
  ZERO selection diffs (deterministic pilot).

Full per-construction table: `XMAGE_ENGINE_SUCCESSOR_SPEC.md` §5.

## Evidence classes

- DIRECTLY_VERIFIED: 32 layered traces (fresh JVM each), probe comparisons,
  offset-level diffs, wish-vs-twin pilot variance demonstration.
- CODE_DERIVED: engine call chain from `mage-1.4.61.jar` bytecode
  (`GameImpl.<init>`/`init`, `PlayerImpl.shuffleLibrary`,
  `Library.shuffle(Random)`, `RandomUtil`/`GameRandom`); bridge collection
  audit; stable-ID and no-filtering review.
- UNKNOWN: anything not isolated — none remaining for the layer question.
  In-game (post-setup) `rulesRandom` consumers (coin/dice/random-target paths)
  inherit the same seeding defect but are not separately exercised: UNKNOWN,
  listed for the successor.

## Commands (all in worktree unless noted)

- `mvn -o -q compile -DskipTests` (engine-bridge): PASS (exit 0).
- `javac` Ws208TraceDriver → `$FOUNDRY_RUN_DIR/ws208-classes`: PASS.
- `ws208_run.py --matrix --budget=500 --mode=twin` (background, 32 fresh JVMs):
  32/32 traces OK (H01×6 twin_diverged@410; others budget-500; zero JVM failures).
- `ws208_diff.py` per construction: all 8 diffed; verdicts in §ROOT_CAUSE.
- `python3 -m py_compile ws208_run.py ws208_diff.py`: PASS.
- `pytest`/WS204 battery/D1-D5 rerun: NOT_RUN — no production, test,
  qualification, or config file changed (`git diff HEAD` empty); regression
  scope is vacuous for this outcome. Requalification burden transfers to the
  engine successor on its new pin.

## Artifacts

- Repo (indexed): `ARTIFACT_INDEX.json` (6 files: HYPOTHESIS_MATRIX.md,
  XMAGE_ENGINE_SUCCESSOR_SPEC.md, driver Ws208TraceDriver.java, ws208_run.py,
  ws208_diff.py, ARTIFACT_INDEX.json itself).
- Run scratch (NOT committed, run-scoped): `$FOUNDRY_RUN_DIR/ws208-traces/`
  32 trace JSONs (~94 MB) + `SHA256SUMS` (32 entries) + `diff-summary.txt`;
  compiled classes in `$FOUNDRY_RUN_DIR/ws208-classes`; engine bytecode dumps
  `PlayerImpl.bytecode.txt`, `GameImpl.bytecode.txt` (analysis aids).
- Invalidated (superseded, not evidence): probe-less traces from the aborted
  first matrix run, including the wish-mode A04 pilot-variance demonstration
  (offset-1 starting-player pick Seat2 vs sealed Seat1, proving wish-mode
  smallest-action tie-break is JVM-random over per-JVM UUID action_ids). Those
  files were deleted before analysis; the observation is preserved in the
  workstream state file decision log, not as an artifact.

## Invariants (runtime-corroborated)

- `REQUESTED_OPTION_FILTERING = ABSENT` (CODE_DERIVED + zero submit_rejected
  anomalies across 32 runs; twin matching over authoritative offers only).
- `SECOND_RULES_ENGINE = ABSENT` (no Lab-side legality; projection is 1:1).
- Hidden information: diagnostic hands/libraries recorded to trace files only,
  captured AFTER selection and never supplied to the pilot.
- `GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`. `D5_TWIN_EQUALITY = UNKNOWN` (global).
  `FULL107 = NOT_RUN`. `ARCHITECTURE_FREEZE = NOT_CLAIMED`.
  `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Terminal fields

WS208_XMAGE_OFFER_DETERMINISM = XMAGE_ENGINE_SIDE_BLOCKED_WITH_SUCCESSOR;
FIRST_DIVERGENCE_LAYER = A (XMage game state: GameRandom-seeded library shuffle);
PRE_DIVERGENCE_STATE_EQUALITY = DIFFER (hidden library order differs post-start;
visible semantic state equal); NATIVE_OPTION_SET_EQUALITY = DIFFER (downstream
consequence); NATIVE_OPTION_ORDER_EQUALITY = DIFFER (order-only at offset 1 +
downstream); PROJECTED_OPTION_SET_EQUALITY = DIFFER (mirrors native exactly);
PROJECTED_OPTION_ORDER_EQUALITY = DIFFER (mirrors native); STABLE_ID_DETERMINISM
= STABLE_BY_CONSTRUCTION (SHA-256 decision ids; per-JVM UUID inputs correctly
excluded from semantics); SEMANTIC_NORMALIZER_CORRECTNESS = CORRECT (no artifact;
projected labels themselves differ); BRIDGE_PRODUCTION_CHANGE = NONE;
XMAGE_ENGINE_REMEDIATION_REQUIRED = YES (see successor spec).
