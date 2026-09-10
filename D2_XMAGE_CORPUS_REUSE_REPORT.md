# D2 — XMage Commander/Multiplayer Corpus Reuse Probe

- Execution: OpenCode Go + `opencode-go/muse-spark-1.3-contributor`, Effort HIGH
- Date (UTC): 2026-09-10
- Workstream isolation: branch `research/xmage-corpus-reuse-20260910` in
  `moeendres-png/commander-playtest-lab`, worktree
  `/home/moeen/code/commander-xmage-corpus-reuse`, based at
  `c391a7616df98f66249ce00790904eb3015b340d` (origin/main at probe time).
- WS49 branch/worktree (`muse/ws49-xmage-local-execution-readiness`) was
  **not written to**. The WS49 mage worktree
  (`/home/moeen/code/xmage-ws49-baseline`) was **not modified**; all XMage
  reads below use pristine git objects at the pinned commit. That worktree's
  pre-existing dirty files (7 modified files, e.g. `PlayerImpl.java`,
  `RandomUtil.java`) were left untouched and are **not** part of this probe.
- No behavior credit claimed. No Full107. Nothing pushed (push requires
  explicit approval).

## Freshly verified WS49 XMage pin (evidence: DIRECTLY_VERIFIED)

Source: `WS49_SOURCE_LOCK.json` in the WS49 workstream
(`candidate-qualification/ws49-xmage-v1.0.5/`), cross-checked against the live
worktree object store on 2026-09-10:

- repository: `moeendres-png/mage`
- branch: `foundry/ws39-commander-history-state-restore`
- commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`
  (`git rev-parse HEAD` + `HEAD^{tree}` in the baseline worktree match both
  values exactly; HEAD message: `WS42 add native commander-damage state
  restore API`).

Every file read below is `git show <commit>:<path>` at exactly this commit.

## License record (evidence: DIRECTLY_VERIFIED)

- `LICENSE.txt` at the pinned commit is the MIT License,
  `Copyright (c) 2010 betasteward@gmail.com`, requiring the copyright + permission
  notice in all copies/substantial portions.
- Every adapted draft in `research/d2-xmage-corpus-reuse/adapted_*.json` and
  the probe script carries `repository/branch/commit/tree/source_path/
  source_method/license` provenance. Reuse condition satisfied by construction;
  any downstream importer must keep the per-record provenance block intact.
- No XMage test expectation, assertion value, or rules outcome was copied as
  truth anywhere in this probe.

## Probe constraints (hard rules, enforced by validator)

1. XMage results are scenario/evidence-generation **input only**, never
   qualification truth. Authoritative results come from the tested Rules Core /
   official rules validation.
2. No manual outcome injection, no engine AI, no fabricated legal choices, no
   card-name-specific legality code.
3. Adapted drafts contain setup + action script + stop point + observable
   checklist **without expected values** (`expected`/`assert` keys are
   validator-rejected). Checklist items name the observable and cite
   `authoritative_source: rules_core`.

## Phase A — inventory (evidence: DIRECTLY_VERIFIED object reads)

Total `Mage.Tests` files at pin: **2021**. Targeted inventory set:

| Area | Files | @Test methods (sum) | Notes |
| --- | --- | --- | --- |
| `multiplayer/*` | 19 | 71 | FFA order/range/leave/voting/triggers/control |
| `commander/**` (duel, FFA3, piper, color/type) | 33 incl. 2 bases | 85 | tax, replacement, partner, mutate, piper |
| `turnmod/` (ExtraTurns, SkipTurn) | 2 | 4 | extra/skip turn mechanics |
| `rollback/*` | 7 | 15 | engine state-restore infra, incl. 1 extra-turn test |
| `sba/` | 1 | 3 | planeswalker uniqueness (legend-rule successor) |
| `mulligan/*` | 6 + base | 29 | London/Paris/Vancouver/Smoothed/CanadianHighlander + sorter |
| `combat/*` | 12 | 101 | incl. AttackBlockRestrictions (40), FirstStrike (16) |
| `cards/continuous/` Commander-relevant | 4 | ~22 sampled | CommandZone cast/tax (629-line CommandersCastTest), Karn restart, PlayerLeavesGame (9) |
| facedown/morph/manifest/disguise | 14 | — | hidden-state corpus (MorphTest 1316 lines / 10 tests) |
| Strict-choice mechanism | 1295 files use `setStrictChooseMode` | — | the corpus default is explicit deterministic choice, not AI |

Mechanic classification applied: COMMANDER_TAX, COMMAND_ZONE_REPLACEMENT,
COMMANDER_DAMAGE, MULTIPLAYER_ORDER, PLAYER_LEAVE, TARGET_AFTER_PLAYER_DEATH,
EXTRA_TURNS, TRIGGERS, HIDDEN_INFO, MULLIGAN, COMBAT, SBA, OTHER.

Corpus-level findings:

- **COMMANDER_DAMAGE has zero dedicated tests at the pin.** Only incidental
  mentions (CastBRGCommanderTest, CommanderMutateTest, TeferiMageOfZhalfirTest).
  The flagship Commander win condition is a corpus gap (evidence:
  DIRECTLY_VERIFIED grep over all 2021 test paths).
- **Strict mode is the norm, AI is the exception.** 1295/2021 files call
  `setStrictChooseMode`; engine-AI drivers (`aiPlayPriority`,
  `CardTestCommander4PlayersWithAIHelps`) appear only in pockets (VotingTest AI
  variants, Karn-restart AI variant). This favors adaptation: most scenarios
  already enumerate legal choices explicitly.
- **`runCode`/`rollbackTurns` harness hooks** (ExtraTurnsTest turn-control
  probes, BloodchiefAscension range probes, rollback ExtraTurnTest) embed
  engine-internal assertions that cannot be ported; they delimit the rewrite
  bucket precisely.
- **Pre-game procedures** (MulliganScenarioTest driver) sit outside any match
  fixture scope and always need driver-level rewrite.

## Phase B — 20 scenarios (deliberately mixed; hard cases included)

Method-level LOC measured by brace-depth span at the pin (evidence:
DIRECTLY_VERIFIED). Verdicts: CODE_DERIVED probe judgment (see Phase C rule).

| # | Source (method) | LOC | Mechanic | Verdict |
| --- | --- | --- | --- | --- |
| 1 | commander/duel/CastCommanderTest.testCastCommander | 13 | COMMANDER_TAX | DIRECT |
| 2 | commander/duel/MythUnboundTest.castCommanderTwice | 28 | COMMANDER_TAX | DIRECT |
| 3 | commander/duel/CommanderReplaceEffectTest.saveCommanderWithGiftOfImmortality | 31 | COMMAND_ZONE_REPLACEMENT | DIRECT |
| 4 | commander/duel/CastCommanderTest.testCastCommanderAndUnexpectedlyAbsent | 31 | COMMAND_ZONE_REPLACEMENT | DIRECT |
| 5 | multiplayer/PlayersListAndOrderTest.test_GameState_GetPlayersInRange | 20 | MULTIPLAYER_ORDER (+OTHER: engine list API) | REWRITE |
| 6 | multiplayer/VotingTest.test_TyrantsChoice_AI_Normal | 22 | MULTIPLAYER_ORDER (AI-driven votes) | REWRITE |
| 7 | multiplayer/PlayerLeftGameRangeAllTest.TestControlledByEnchantment | 23 | PLAYER_LEAVE | DIRECT |
| 8 | cards/continuous/PlayerLeavesGameTest.test_PlayerLeaveGameWithOwnPermanentAndUntilSourceLeavesBattlefielEffect | 10 eff. (3 + 35-line shared helper / 5) | PLAYER_LEAVE | REWRITE |
| 9 | commander/FFA3/PlayerLeftTest.TestCommanderRemoved | 11 | PLAYER_LEAVE | DIRECT |
| 10 | multiplayer/PlayerDiedStackTargetHandlingTest.TestDeadPlayerIsNoLongerValidTarget | 18 | TARGET_AFTER_PLAYER_DEATH | DIRECT |
| 11 | multiplayer/PlayerDiedStackTargetHandlingTest.TestDeadPlayerIsNoLongerValidTarget2 (storm vs dead player) | 23 | TARGET_AFTER_PLAYER_DEATH | DIRECT |
| 12 | turnmod/ExtraTurnsTest.test_EmrakulMustGiveExtraTurn_OnOwnTurn | 26 | EXTRA_TURNS | REWRITE |
| 13 | rollback/ExtraTurnTest.testThatRollbackWorksCorrectlyWithExtraTurn | 17 | EXTRA_TURNS/OTHER (engine state-restore) | UNUSABLE |
| 14 | multiplayer/MultiplayerTriggerTest.testMultiplayerAttackStinkdrinkerBanditTrigger | 21 | TRIGGERS | DIRECT |
| 15 | multiplayer/BloodchiefAscensionTest.test_BloodchiefAscension_DieBeforeEndTurn | 67 | TRIGGERS (+range probes) | REWRITE |
| 16 | cards/abilities/keywords/MorphTest.testCastFaceDown | 13 | HIDDEN_INFO | REWRITE |
| 17 | mulligan/LondonMulliganTest.testLondonMulligan_TwoMulligan | 67 | MULLIGAN | REWRITE |
| 18 | combat/FirstStrikeTest.firstStrikeAttacker | 14 | COMBAT | DIRECT |
| 19 | sba/PlaneswalkerRuleTest.testDestroySamePlaneswalkers | 12 | SBA | DIRECT |
| 20 | COMMANDER_DAMAGE — no scenario exists at pin (corpus gap) | n/a | COMMANDER_DAMAGE | UNUSABLE |

Coverage: all 13 mechanic classes represented. 19 measured scenarios total
**467 LOC, mean 24.6 LOC**; enclosing files total **4336 lines** (~9.3x — the
bulk is siblings/boilerplate/helpers, which adaptation skips entirely).

Verdict rationale (one line each):

- DIRECT (11): setup DSL maps 1:1 to fixture fields
  (`addCard`→placements, `castSpell`/`attack`/`concede`→action script,
  `setChoice`/`addTarget`→explicit choices, `setStopAt`→stop point);
  assertion *intent* (which observables to check) re-expresses as a valueless
  checklist. Applies to #1, #2, #3, #4, #7, #9, #10, #11, #14, #18, #19.
- REWRITE (7): #5 asserts engine collection-order APIs (re-derive as turn-order
  behavior checks); #6 AI casts the votes (replace `aiPlayPriority` with
  explicit vote scripts); #8 assertions couple to engine duration bookkeeping
  (re-express as stop-point state checks); #12/#15 embed `runCode` turn probes
  and `rollbackTurns` infra calls; #16 asserts via the
  `EmptyNames.FACE_DOWN_CREATURE` test hook (map to hidden-opaque-identity
  surface); #17 is a pre-game driver program, not a match fixture.
- UNUSABLE (2): #13 tests engine state-restore machinery, not game rules;
  #20 does not exist (commander-damage gap must be authored from rules text).

## Phase C — adaptation probe (evidence: DIRECTLY_VERIFIED run)

Fixture target: the lab's `TacticalScenario` ActionType vocabulary
(`schemas/models/TacticalScenario.schema.json` on this branch:
`cast_spell`, `cast_commander`, `declare_attackers`, `choose_targets`,
`choose_mode`, `pay_cost`, `concede`, …) under the WS49 fixture contract rule
(provider translation creates only setup metadata, never legality/choices —
`candidate-qualification/ws49-xmage-v1.0.5/canonical_v105.py`,
`successor_contract_v105.py`, read-only reference).

Bounded sample: 3 drafts adapted by hand (#1 → D2-ADAPT-01, #14 →
D2-ADAPT-02, #10 → D2-ADAPT-03), 58/68/95 JSON lines (mean ~74; more verbose
than the 13/21/18 Java LOC because provenance + checklist travel with the
draft — the saving is decision time, not characters).

Run on 2026-09-10 (`research/d2-xmage-corpus-reuse/adapt_probe.py`):

```text
D2-ADAPT-01: VALID violations=none
D2-ADAPT-02: VALID violations=none
D2-ADAPT-03: VALID violations=none
NEG-outcome-import: REJECTED violations=['outcome_field_present:...expected', ...]
NEG-engine-ai: REJECTED violations=['forbidden_token:aiPlayPriority...']
NEG-ai-flag: REJECTED violations=['engine_ai_true...']
validator_elapsed_s=0.001 drafts_valid=3/3 negatives_rejected=3/3
PROBE_RESULT=PASS
```

The validator fails closed on: any `expected`/`assert`/outcome key, any AI /
harness-hook token, non-explicit choices, non-`rules_core` checklist authority,
unknown actions, missing provenance. All three negatives (outcome import, AI
driver, AI flag) are rejected.

What was deliberately NOT done: no XMage expectation value was copied; no
scenario was executed against any engine; no Rules Core result is claimed. The
drafts are evidence-generation input awaiting authoritative adjudication.

## Measures (evidence classes labeled per row)

| Measure | Value | Evidence |
| --- | --- | --- |
| XMage scenario size (19 measured) | 467 LOC, mean 24.6 | DIRECTLY_VERIFIED |
| Manual authoring, current method (estimate, this scenario class) | simple duel 20–30 min; FFA/multi-choice 45–90 min; 20-set mean ~50 min | MODELED (basis: WS47 107-record requested-state authoring shape + multi-actor choice enumeration + review) |
| Adaptation, DIRECT (estimate) | 10–20 min, mean ~15 (verify pin text, map fields, independent checklist, review) | MODELED, anchored on measured probe pace below |
| Adaptation, REWRITE (estimate) | 30–60 min, mean ~45 (re-derive checks, replace AI/runCode/pre-game drivers) | MODELED |
| Measured probe pace | classification of 20 scenarios ~40 min wall (~2 min/scenario incl. pin reads); 3-draft transcription ~2 min post-analysis; validator 0.001 s | DIRECTLY_VERIFIED (session timestamps / tool output) |
| Directly reusable | **11/20 = 55%** | CODE_DERIVED verdicts |
| Requiring semantic rewrite | **7/20 = 35%** | CODE_DERIVED verdicts |
| Unusable (infra test / corpus gap) | **2/20 = 10%** | CODE_DERIVED verdicts |
| Scenario-authoring work removable | **~40–45%** — (11×35 + 7×10 + 2×0)/20 ≈ 22.75 min saved off a ~50 min mean | MODELED arithmetic on the above |
| One-time adapter cost | 271-line validator + mapping table, amortized over all imports | DIRECTLY_VERIFIED (`adapt_probe.py`) |

Common adapter mechanisms that could systemically automate import (all
mechanical, none touches truth):

1. **Setup-DSL→fixture mapper**: `addCard`→zone placements (counts are setup,
   not outcomes); `castSpell`/`attack`/`block`/`concede`→typed action script;
   `setChoice`/`setChoices`/`addTarget`→explicit choice lists;
   `setStopAt`→stop point; `setStrictChooseMode(true)`→deterministic flag.
2. **Card-identity resolver**: names flow only into identity/template fields;
   any card-name-conditioned legality branch is a validator rejection.
3. **Assertion-intent translator**: `assertLife`/`assertPermanentCount`/
   `assertPowerToughness`/`assertTappedCount`/`assertCommandZoneCount`/
   `assertActivePlayer`→observable checklist entries with values left blank
   for Rules Core. `Assert.*` on engine internals (player-list order,
   `hasPlayerInRange`, turn-controller probes)→flag for semantic rewrite.
4. **Driver filter (fail-closed)**: `aiPlayPriority`/AI-help bases,
   `runCode`, `rollbackTurns`, `MulliganScenarioTest`-style pre-game drivers,
   `EmptyNames.*` test hooks→route to REWRITE/UNUSABLE, never silently adapt.
5. **Provenance stamper**: per-record MIT notice + repository/branch/commit/
   tree/source path/method (as demonstrated in the 3 shipped drafts).

## Conclusion

**BOUNDED_REUSE.**

A modest majority (55%) of sampled high-value XMage Commander/multiplayer
scenarios converts mechanically to fixture setup + explicit choice scripts +
valueless observable checklists, with strict-mode explicitness already doing
most of the disambiguation work. But outcomes are never importable by design,
35% need semantic rewrite (AI voters, engine-API probes, hidden-state hooks,
pre-game drivers, duration bookkeeping), 10% is unusable-or-absent, and the
corpus has **zero commander-damage coverage** — the highest-value Commander
mechanic must still be authored from rules text. Estimated scenario-authoring
work removable: **~40–45%**, concentrated in setup drafting and choice
enumeration, not in adjudication (which remains fully with Rules Core).

Recommended next step (if commissioned): productionize adapters 1–5 as a
linted importer emitting provenance-stamped, valueless drafts, and measure
real authoring minutes on a 20-scenario pilot before projecting Full107-scale
savings. That pilot is evidence-generation tooling only and grants no
behavior credit.
