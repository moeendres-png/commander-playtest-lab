# Historical Archaeology — WS-CSN-CAPABILITY-DELTA-20260929

Read-only investigation. Nothing in this document was executed; every claim is
either `CODE_DERIVED` from source, `DIRECTLY_VERIFIED` from a fetched upstream
file, or explicitly labelled `HYPOTHESIS`.

## 1. Inside our own repository: the capability existed all along, unreachable

### 1.1 A 1381-line engine-native seam with no production caller

`engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java`
exists at `main` (`2e28866f…`). Its own class javadoc states:

> Translates an explicit requested starting state … into engine-native state
> through public engine APIs only, then validates with engine-authoritative
> state-based actions plus layers and proves the result with a strict native
> readback compared field-by-field against the request. Anything outside the
> supported dimensions fails closed with a coded reason before any game
> mutation.

Call-site census (`grep -rn "new XmageFullGameSession"`):

| Location | Restoration passed? |
|---|---|
| `XmageFullGameJsonlBridge.java:183` — the **only** production site | **no** (`null`) |
| `XmageNativeStateRestorationTest.java` ×8 | yes |
| `XmagePb03Tier1RowsTest`, `XmagePb03Tier2StackTest`, `XmagePb03Tier2CmdZoneTest`, `XmagePb03Tier2ControlTurnTest`, `XmageFull107ResidualRequalificationTest`, `XmageControlDivergenceReconstructionTest`, `XmageCausalEliminationReconstructionTest`, `XmageCausalStackReconstructionTest`, `XmageTemporalProgressionDriverTest`, `XmageTemporalAdvancedProgressionTest`, `XmageHiddenReplayIntegrationTest`, `XmageCommanderDamageRestorationTest`, `XmageHiddenStateRestorationTest` (the remaining ~30 sites) | yes |

The identical pattern holds for the whole causal family: `XmageCausalStackReconstruction`,
`XmageCausalEliminationReconstruction`, `XmageControlDivergenceReconstruction`,
`XmageTemporalProgressionDriver`, `XmageHiddenStateRestoration` have **no caller
outside `src/test/java`**.

And `dimensionsPayload()` — the machine-readable statement of which dimensions
the seam can construct — has exactly one caller:
`XmageNativeStateRestorationTest.java:801`.

### 1.2 The project already knew, and recorded it, and then did not route it

`docs/pre_freeze_completion_20260927/PB03_ROOT_CAUSE_AND_REMEDIATION.md`, quoted
verbatim in the delta audit:

> `dimensionsPayload()` … So the bridge says, in machine-readable form, exactly
> which starting-state dimensions it can and cannot construct. **Nothing
> consumes that manifest at the qualification boundary.**

And `docs/architecture_freeze_readiness_20260927/XMAGE_FREEZE_READINESS.json`
separately refuses the coarse bit as a ranking input:

> `confusion_forbidden`: "Ancestry is not identity and a fork is not pristine
> upstream. A result observed on this fork must never be reported as an upstream
> XMage result."

Two independent audits had already located the missing route. Neither closed it.

### 1.3 Prior residual workstreams were not the cause

`MAGE_RESIDUAL_ADJUDICATION_HANDOFF_20260927.md` and
`docs/workstream_wsr25_terminal_closure_20260927.md` show RG-02, RG-06A, RG-07
and RG-08 all landed in `b1959698…` and were already `DIRECTLY_VERIFIED` on
`main`. None of them is the cause of the 44 blocked rows. The cause was always
that the seam was never on a production path.

### 1.4 Prior deep-research reuse findings that are still binding

From `docs/workstream_deep_research_closure_20260923/DEEP_RESEARCH_IMPLEMENTATION_LEDGER.md`
(13/13 terminal, `BLOCKED_FAIL_CLOSED` only for `PRED-REPL-05`):

- stack reconstruction: "No engine-native stack-reconstruction path preserving
  object/ability/target/mode/cost semantics was found in the pinned API surface."
  → **superseded** by `XmageCausalStackReconstruction`, which resolves
  `SpellStack.push` and never fabricates a `Spell`. Still JUnit-only.
- temporal points: "`GameState.setTurnNum` exists but is not a
  correctness-preserving arrival mechanism." → **still true**; arrival is
  correctly reached by driving the running engine.
- control divergence: "layers re-derive control from owners + continuous
  effects", probe-proven. → **reproduced** on the new production lane
  (`UNSUPPORTED_CONTROL_DIVERGENCE`).
- hand identity: the one successful find was `Game.cheat(...)`, "with a
  dedicated hand slot currently passed as empty". → **consumed** by the
  restoration seam and now production-reachable.
- life-0: "the engine re-derives starting life to 40 during game start." →
  **reproduced** on the new production lane (`life P2: requested 0 observed 40`).

### 1.5 A precedent for exactly this kind of fix, in our own history

`docs/xmage_generic_rules_rng_20260929/HANDOFF.md` records the identical shape of
defect one layer down: the engine-level seed binding "already existed
(`Game.setRulesSeed` / `setRequireExplicitSeed`, WS54) and was already used by the
full-game lane (WS213); **only the generic lane never bound it**." That fix is a
route fix, not a semantics fix, and it is the precedent this workstream follows.

## 2. Upstream XMage (`magefree/mage`, MIT, master, pushed 2026-09-29T02:52Z)

All `DIRECTLY_VERIFIED` from raw file fetches at `master`.

### 2.1 The setup primitive is in main sources, and its only caller is a test

`Mage/src/main/java/mage/game/Game.java`:

```java
633:    // game cheats (for tests only)
634:    void cheat(UUID ownerId, Map<Zone, String> commands);
636:    void cheat(UUID ownerId, List<Card> library, List<Card> hand,
                    List<PutToBattlefieldInfo> battlefield, List<Card> graveyard,
                    List<Card> command, List<Card> exiled);
```

The comment says "for tests only", but the method ships in the `Mage` artifact
and is reachable from `Mage.Server`. `PutToBattlefieldInfo`
(`Mage/src/main/java/mage/game/PutToBattlefieldInfo.java`) carries
summoning-sickness/timestamp control per permanent, and the `command` zone list
is the only built-in channel that seeds a Commander into `Zone.COMMAND` in the
same call.

The **only** verified caller is
`Mage.Tests/src/test/java/org/mage/test/serverside/base/impl/CardTestPlayerAPIImpl.java:306-324`
— i.e. upstream has the same route gap we have.

### 2.2 `GameOptions` is the generic turn-boundary and determinism knob surface

`Mage/src/main/java/mage/game/GameOptions.java`, `implements Serializable, Copyable<GameOptions>`:
`testMode`, `stopOnTurn`, `stopAtStep`, `skipInitShuffling`, `rollbackTurnsAllowed`,
`bannedUsers`, `perPlayerEmblemCards`, `globalEmblemCards`. Production class.
The Lab already uses `rollbackTurnsAllowed`; `stopOnTurn`/`stopAtStep`/
`skipInitShuffling` are unconsumed by the Lab.

### 2.3 The scenario DSL is designed to be driven from outside the test harness

`Mage.Tests/.../CardTestPlayerBase.java::setStrictChooseMode(boolean)`:
"Raise error on any miss choices/targets setup in tests (if AI try to make
decision itself instead of user defined actions)". The XMage wiki page
`Development-Testing Tools` documents `-Dxmage.testMode=true` plus an
`init.txt` of `add:`/`check:`/`show:`/`ai:`/`run:` commands read by the
**shipped server**. Same engine, same DSL, production-reachable by design.

### 2.4 `TestPlayer`'s pre-target seeding and RNG sentinels are instance methods

`Mage.Tests/src/test/java/org/mage/test/player/TestPlayer.java:349`
`addTargets(Ability, Game)`; response channels `setResponseString`,
`setResponseManaType`, `setResponseUUID`, `setResponseBoolean`, `setResponseInteger`
(all delegating to an internal `ComputerPlayer`); sentinels `TARGET_SKIP`,
`CHOICE_SKIP`, `MODE_SKIP`, `MANA_CANCEL`, `BLOCK_SKIP`, `ATTACK_SKIP`,
`FLIPCOIN_RESULT_TRUE/FALSE`, `DIE_ROLL`.

The Lab bridge uses **none** of these; it drives XMage's own blocking
`Player` callbacks instead, which is the stronger route because the decisions
are authored by the engine rather than scripted into the engine.

**Flagged, not tested:** `addTargets` is an instance method whereas
`setResponse*` delegate to a shared internal `ComputerPlayer`. Mounting both on
one production `Player` across concurrent seats is a plausible cross-seat
contamination vector. `HYPOTHESIS` — the Lab's own concurrency test must decide,
not this document.

### 2.5 A second, productised, *deprecated* production mid-game route

`Mage.Server/src/main/java/mage/server/game/GameController.java` `saveGame()`
(~line 999) writes the live `Game` plus `GameStates` through a gzipped
`ObjectOutputStream`; `GameReplay.java` `loadGame()` reads it back with
`CopierObjectInputStream` and `getGame()` returns a live mid-game `Game`.
Reachable through `ClientCallbackMethod.REPLAY_GAME` →
`User#ccReplayGame` → `ReplayManagerImpl#replayGame`; the writer is
`GameManagerImpl#saveGame` line ~172.

**This is the decisive historical finding of the audit, and it cuts against
reliance:** the class's own javadoc reads

> Replay system, outdated and not used. TODO: delete

So the mechanism is real and production-reachable *today*, and upstream intends
to remove it. A dependency on it would be a dependency on a class scheduled for
deletion; the `Game.cheat(...)` route has no such mark.
`HYPOTHESIS`: a deserialised `Game` can be *resumed* rather than merely viewed —
untested here.

### 2.6 Upstream regression tests that are the strongest available evidence

`Mage.Tests/src/test/java/org/mage/test/`:

| Package | Verified test methods relevant to our open rows |
|---|---|
| `combat` | `DamageDistributionTest#test2x2Block`, `#testTrampleDeathtouch`, `#testDoubleStrikeTrampleVersusIndestructible`, `#testCombatDamagePhyrexianUnlife`; `CanBlockMultipleCreaturesTest#testCanBlockMultiple`, `#testMultipleBlockWithTrample`, `#testCanOnlyBlockSingle`, `#testNightMarketGuardShouldNotBlockCreatureWithMenace` |
| `multiplayer` | `ControlChangeTest`, `PlayerLeftGameRange1Test`, `PlayerLeftGameRangeAllTest`, `MultiplayerTriggerTest`, `PlayersListAndOrderTest`, `MyriadTest`, `AngelOfSerenityTest` |
| `rollback` | 7 files including `ExtraTurnTest`, `TransformTest`, `StateValuesTest`, `NewCreaturesAreRemovedTest` |
| `lki` | `LastKnownInformationTest#testPersistTriggersInTime`, `#testTrostaniSelesnyasVoice1/2/3` |
| `mulligan` | `LondonMulliganTest`, `ParisMulliganTest`, `VancouverMulliganTest`, `CanadianHighlanderMulliganTest`, `SmoothedLondonMulliganTest` |
| `turnmod` | `ExtraTurnsTest`, `SkipTurnTest` |
| `commander` | `CommanderColorIdentityTest`, `CommanderTypeTest` |
| `cards/continuous` | `CommandersCastTest`, `CommandersGameRestartTest` |
| `cards/replacement` | 32 files incl. `ZoneChangeReplacementTest`, `DoublingSeasonTest`, `GrindstoneTest`, `LeylineOfTheVoidTest`, `SkullbriarTest` |

`#test2x2Block` and `#testCanBlockMultiple` are upstream's own multi-defender
combat evidence — stronger than any issue number, and directly reusable as
adversarial controls for our `WS05-MP-COMBAT-4` / `WS05-MP-BLOCK-4` obligations.

**Honest gap.** I could not obtain verifiable open-or-closed XMage issue/PR
numbers for: multi-defender attacker assignment, commander damage persistence
across game load, CR 103.8a two-player draw, non-GUI mulligan control, exact-N
target offering, or replacement-effect ordering prompts. No numbers were
invented. `magefree/mage`'s `magefork/mage` could not be found at all; it is
either private, absent, or named differently. No claim is made.

## 3. Pristine Forge (`Card-Forge/forge` @ `a37a865a…`, GPL-3.0, pushed 2026-09-29T00:45Z)

All `DIRECTLY_VERIFIED` from the pinned tree (58,949 paths).

### 3.1 `PlayerController` is the complete, generic decision surface

`forge-game/src/main/java/forge/game/player/PlayerController.java` — the
abstract method set *is* the rule-acknowledged decision list, and it maps
one-to-one onto the mechanisms the Lab currently cannot reach:

| CR | `PlayerController` member | line |
|---|---|---|
| 510.1c | `CardCollection orderBlockers(Card, CardCollection)` | ~159 |
| 510.1c incremental | `CardCollection orderBlocker(Card, Card, CardCollection)` | ~168 |
| 510.1d | `CardCollection orderAttackers(Card, CardCollection)` | ~169 |
| 601.2d | `Map<Card,Integer> assignCombatDamage(Card, CardCollectionView, CardCollectionView, int, GameEntity, boolean)` | ~110 |
| 603.3b | `List<SpellAbility> orderSimultaneousSa(List<SpellAbility>)` | ~102 |
| 616 | `boolean confirmReplacementEffect(ReplacementEffect, SpellAbility, GameEntity, String)` | ~149 |
| 103.8a | `Player chooseStartingPlayer(boolean isFirstGame)` | ~244 |
| 601.2c | `boolean willPutCardOnTop(Card)` / `CardCollectionView orderMoveToZoneList(CardCollectionView, ZoneType, SpellAbility)` | ~195 / ~203 |
| 701.9d | `Map<GameEntity,Integer> divideShield(Card, Map<GameEntity,Integer>, int)` | ~111 |

`forge-game/src/main/java/forge/game/combat/Combat.java` consumes them
generically (lines 500, 501, 532, 801-802, 877). Multiple blockers are
structural: `blockersOrderedForDamageAssignment` is a `Map<Card, CardCollection>`
of arbitrary cardinality, with banding in a separate
`forge/game/combat/AttackingBand.java`.

### 3.2 Forge has a headless-capable stack and a GUI-free snapshot — but no scenario API

- `forge-ai/src/main/java/forge/ai/PlayerControllerAi.java` (71 KB) is a
  complete non-GUI `PlayerController` implementing `assignCombatDamage`,
  `confirmReplacementEffect`, `orderBlockers`, `orderBlocker`, `orderAttackers`,
  `willPutCardOnTop`, `chooseStartingPlayer`, `orderSimultaneousSa`.
- `forge-game/src/main/java/forge/game/GameSnapshot.java` — production
  `makeCopy()`, `assignGameState(...)`, `assignPlayerState(...)`, per-card zone
  positions, meld handling, entity-id remapping. In-memory only.
- `forge-game/src/main/java/forge/game/GameState.java` — a **text** save-game
  format with per-card attributes including `|IsCommander` (line ~276/1349),
  `|Damage:<n>` (line ~346/1371), `|IsRingBearer`, `|SummonSick`, `|Counters:`,
  `|PhasedOut:`, `|Meld:`, restored through `markedDamage` +
  `handleMarkedDamage()` (line ~1010) and `p.getCommanders()` +
  `p.createCommanderEffect()` (line ~1205). In-code known gap: merged
  commanders are not supported (line ~1125) — relevant to Commander 2014's
  Bruna/Israfel meld pair.
- Exhaustive filename search over the pinned tree for
  `scenario|inject|setup|fixture|sandbox|replay|loadgame|gamerestorer|snapshot|testplayer|harness|headless`
  returned no scenario format and no `TestPlayer`. `forge-game/src/test`
  contains **two** files.
- `forge/game/mulligan/MulliganService.java` is engine-side and
  player-rotation-based (`offset = whoCanMulligan.indexOf(firstPlayer)`;
  `firstMullFree = game.getPlayers().size() > 2 || …`), with pluggable
  algorithms in `forge/game/mulligan/`.

**Consequence for the delta audit:** pristine Forge has *no* equivalent of the
mid-game injection seam, so the Lab's own Forge-fork additions are **not**
redundant with upstream here. That reverses the usual expectation and is worth
recording.

### 3.3 Forge issue tracker (verified via the GitHub issues API)

| Issue | Title | State | Relevance |
|---|---|---|---|
| `#10142` | Can't cast commander after restarting game with Karn | **open** | Quotes the 2020-08-07 ruling verbatim: "The amount of combat damage dealt to players by each commander is reset to 0." A live commander-damage bug **at a newer commit than our pin**. |
| `#9156` | Add support for Duel Commander mode | **open** | States "No commander damage rule (the 21 damage condition does not apply)" as not-yet-implemented: CR 903.10a is variant-gated, not per-card. |
| `#6389` | Cloned Grothama triggering improperly | **open** | Copy-vs-original commander damage identity. |

Search `repo:Card-Forge/forge is:issue commander damage` returned 29 results.
**Honest gap:** no *closed* Forge PR/issue carrying regression tests for
multi-defender attack declaration or the 2-player starting-draw skip was found.
Given `forge-game/src/test` holds two files the absence is suggestive, but it is
labelled **partially-searched, not proven-absent**. The non-GUI
`PlayerController` mulligan-decision method was also not located.

## 4. Manabrew (`witchesofthehill/manabrew`, **AGPL-3.0-or-later**, pre-release)

Mechanically verified, from the four most relevant Java/Rust files.

- **Pinning**: a git submodule, not a Maven coordinate —
  `.gitmodules` → `forge` at `witchesofthehill/forge` branch `manabrew`, pinned
  at submodule commit `e7d2b93ba9f800a1f5f3a5de91db1aad3ed46831`. A *third*
  Forge fork, distinct from the Lab's.
- **RNG**: `forge-harness/.../common/CountingRandom.java` — `extends
  java.util.Random`, an `AtomicInteger` per-call ordinal, an optional
  `-Dforge.parity.rng.trace` stderr trace, and
  `-Dforge.parity.rng.bt.bounds=<bound>` to dump a stack trace for one specific
  bound so a divergent draw can be localised. This is the direct answer to the
  `RandomUtil` static-global hazard in §6.1.
- **Decision injection**: `forge-harness/.../parity/DeterministicController.java`
  (85 KB) and `DeterministicLobbyPlayer.java` — a `PlayerController`
  implementation. This independently corroborates that `PlayerController` is
  Forge's decision seam.
- **Trace identity**: `forge-harness/.../common/ParityOrder.java` sorts cards by
  `(name, ParityCardMap::parityId)` and actions by a composite
  `label|bucket|hostParity|variant|fallback` key, so two independently
  implemented engines can be compared **positionally** rather than by pointer
  identity.
- **Harness**: `parity/regression.json` and `parity/parity_ignore.json`
  baselines, first-mismatch reporting, a GUI-repro minimiser, matrix mode with
  `--master-seed`, rayon parallelism. `parity/README.md`: "compares the Rust
  Forge engine against the Java reference implementation snapshot-by-snapshot".
- **Status caveat**: PR `#426 feat(parity): trace-replay parity harness` is
  **open, Draft**. The snapshot-comparison path is the live one; trace *replay*
  is not merged.

**Licence posture.** `LICENSE.md` states **AGPL-3.0-or-later**, and the Rust
engine is additionally a rewrite of GPL-3.0 Forge. No line of
`manabrew-rs/crates/parity/**`, `parity-debugger/**` or `forge-harness/**` may be
copied, transliterated or adapted into the Lab. The four techniques above are
**methodology** and are reimplemented independently. The architectural fact that
`PlayerController` is a single decision seam is not copyrightable and is
reusable as design.

## 5. phase.rs (`phase-rs/phase`, **dual MIT OR Apache-2.0**, pushed 2026-09-29T02:36Z)

The prompt's uncertainty is resolved: the tree ships **both** `LICENSE-MIT` and
`LICENSE-APACHE`; the README reads "Dual-licensed under MIT or Apache 2.0, at
your option". Both are permissive, so transfer is licence-clean subject to
notice/attribution. It is nevertheless treated `REFERENCE_ONLY` here, because
phase.rs is a *different* engine and borrowing its semantics would move Rules
authority out of the pinned core.

### 5.1 The most valuable external artefact found: a production scenario builder

`crates/engine/src/game/scenario.rs` (267 KB) is declared `pub mod scenario;` in
`crates/engine/src/game/mod.rs:168`, with `#[cfg(test)] mod tests` only at line
4486 — so it is **shipped engine code**, not a test artefact:

```rust
pub fn new_n_player(count: u8, seed: u64) -> Self
pub fn at_phase(&mut self, phase: Phase) -> &mut Self
pub fn with_life(&mut self, player: PlayerId, life: i32)
pub fn with_cards_in_hand(&mut self, player, names: &[&str])
pub fn with_library_top(&mut self, player, names_top_first: &[&str])
pub fn with_graveyard(&mut self, player, names: &[&str])
pub fn with_mana_pool(&mut self, player, mana: Vec<ManaUnit>)
pub fn with_counter(&mut self, object_id, counter, count)
pub fn with_commander(&mut self, object_id: ObjectId)
pub fn build(self) -> GameRunner
pub fn build_and_run(self, actions: Vec<GameAction>) -> ScenarioResult
```

`with_commander` moves the object to `Zone::Command` and sets `is_commander`
(lines 338-355); `add_creature` explicitly clears summoning sickness with a CR
citation (lines 383-391): "CR 302.6: Scenario builder places pre-existing
creatures (entered on a prior turn)". That is the exact discipline the Lab's
`controlled_since_turn_began` flag encodes. The deployed UI exposes a **"Load
Game State"** control, and `crates/server-core/src/persist.rs` +
`PersistedGameState`'s hand-written `Serialize`/`Deserialize` give a
disk-persisted restore with production DoS bounds
(`MAX_SNAPSHOT_OBJECTS`, `MAX_SNAPSHOT_EVENTS = 2_000`,
`MAX_SNAPSHOT_LOG_ENTRIES = 5_000`).

**Why it is not integrated:** phase.rs is 92% Commander coverage and is
agent-generated, with a large open blocking-issue backlog. Borrowing its
scenario *semantics* would be a second Rules engine. Its *shape* — declarative
`(phase, step)` targeting, seeded construction, summoning-sickness as an
explicit field — is the design our records already follow.

### 5.2 Tests and filed issues worth reading

| Source | Verified names / numbers |
|---|---|
| `crates/engine/src/game/triggers_ordering_parity_tests.rs` (113 KB) | `ordering_parity_sweep`, `n_c_case_a_same_event_prompts`, `n_d_intervening_if_case_a_prompts`, `n_d2_commander_intervening_if_is_fed_by_a_sibling_membership_write`, `n_b_frozen_vs_live_discriminator`, `s5_multiplayer_three_players`, `n_f_die_result_conjunct` |
| `crates/engine/tests/integration/rules/combat.rs` (108 KB, 60+ tests) | `multiple_attackers_mixed_blocking`, `bushido_becomes_blocked_fires_once_when_double_blocked`, `becomes_blocked_by_creature_fires_for_each_blocker`, `per_defender_cap_limits_only_that_defender`, `global_attacker_cap_rejects_over_cap_accepts_at_cap`, `venom_destroys_the_creature_that_blocked_it_at_end_of_combat` |
| `crates/engine/tests/integration/rules/sba.rs` | `zero_life_player_loses`, `negative_life_player_loses`, `lethal_damage_destroys_creature`, `sbas_checked_automatically_after_action` |
| `crates/engine/tests/integration/rules/layers.rs` | `timestamp_ordering_both_lords_apply`, `layer_evaluation_resets_and_recomputes` |
| `crates/engine/src/game/commander.rs` (77 KB) | CR 903.8 tax and cast counts; CR 903.10a 21-damage over a per-object `commander_damage` map; CR 903.9a/b/c meld handling |
| `crates/engine/src/game/players.rs` / `turns.rs` | `apnap_order(state)` and `apnap_order_from(state, anchor)` — the single generic APNAP primitive with an explicit anchor override for turn transitions (CR 101.4 / 103.8a) |
| Issues | **#6337** non-deterministic draft color selection (missing `HashMap` tie-break); **#6914** Kediss deals extra damage; **#9021** Duel Commander limitations; **#6416** extra turn out of sequence; **#6416**/**#4264** APNAP-adjacent |

**Two readings that change our own posture.** (a) Issue **#6337** proves
`phase.rs` has the *same* RNG-determinism defect class as XMage's
`RandomUtil`/`Collections.shuffle` split, so engine comparison must not assume
any donor is determinism-clean. (b) APNAP lives in `apnap_order` /
`apnap_order_from`, which is exactly the primitive a Commander simulator's turn
order should call rather than reimplement.

**Honest gap.** Test *names* and *paths* were read, not bodies, except
`with_commander` and `add_creature`. "No test named for menace / CR 510.1c
blocker ordering / CR 601.2d assignment order" is based on scanning ~60 function
names in `combat.rs`; a differently-named test could cover it. Issue titles are
verbatim from the API; bodies were not opened.

## 6. Other donors

| Project | Licence | Activity | Verdict |
|---|---|---|---|
| `Baldugar/mtg-forge-ts` | GPL-3.0 | 2026-05-04, 0 stars | Claims "TypeScript port of Card-Forge/forge … deterministic replay, save/load, and network-authoritative multiplayer" and a headless server. **Every claim is `HYPOTHESIS`** — no source was read. The single lead worth an hour if a second candidate is needed. |
| `Cockatrice/Cockatrice` | GPL-2.0 | 2026-09-27, 1.8k stars | Serious and active, but a virtual tabletop. Arbitrates zones and hidden information server-side; implements no CR. Not a Rules authority. |
| `wanqizhu/mtg-python-engine` | MIT | 2025-05-05, 86 commits, 70 stars | Real CR-replication attempt, permissive, but dormant since 2017. Design reference only. |
| `thelamesaucegit/forgeSim` | GPL-3.0 | — | A headless-only AI-vs-AI CLI emitting event-by-event JSON. No rule semantics beyond upstream. |
| `manaflow-ai/manaflow` | MIT | active, 1.1k stars | **False positive**: a coding-agent orchestration tool, not an MTG engine. |
| `tjonestj3/mtg-engine`, `Forkei/mtg-ai`, `TiesWestendorp/MTG-Mana-Simulator`, `francoep/MTGsim`, `sleeyax/mtgalib` | various | 0-1 commits or card-curve only | Excluded by the project's own bar. |
| `fenhl/lands` / `lands/lands` | — | 404 | **Could not be verified to exist.** No claim. |
| `magentic-ui`, `cardflow`, `swordfish`, `mse`, `open-spellbook`, `helios`, `vent`, `magic-ts` | — | — | **Could not be verified to exist as open-source MTG rules engines.** No claim. |

**Net result of the donor sweep.** Beyond XMage, Forge, Manabrew and phase.rs
there is **no fourth serious open-source MTG rules engine** with real rule
semantics, a test corpus and historical depth. The project's existing four-donor
universe is complete.

## 7. Cross-cutting finding that is not in any prior project report

**XMage's Rules RNG is split, and one branch is unseedable.**
`Mage/src/main/java/mage/util/RandomUtil.java` is a single **process-wide
static** `java.util.Random` with `setSeed(long)`. `Mage/src/main/java/mage/game/GameState.java`
(68 KB) was grepped and has **no per-game RNG field**.
`PlayerImpl.putCardsOnTopOfLibrary(Cards, Game, Ability, boolean anyOrder)` at
lines ~1199-1233 uses bare `java.util.Collections.shuffle(ids)` on the
"any order" branch, which constructs a **fresh clock-seeded** `Random` and
therefore ignores `RandomUtil.setSeed` entirely. `PlayerImpl.seekCard` (line
~3061) *does* use `RandomUtil.randomFromCollection`.

Consequences for a seeded qualification lane:

1. "In any order" library effects are **not** seed-controlled → traces are not
   bit-reproducible.
2. Seed-controlled effects share one global mutable stream → **per-game seed
   isolation does not hold** under concurrency.
3. The Lab's `XmageRulesSeedBinding` proves `setRulesSeed` +
   `setRequireExplicitSeed` are honoured for the paths that use `RandomUtil`, but
   it cannot fix a branch that bypasses it.

Already-available mitigations: `GameOptions.skipInitShuffling` plus
`removeAllCardsFromLibrary` for the opening hand, and deterministic library
pinning. A real fix needs an upstream change, which is why this is an
engine-side dispatch packet (CAP-08) and not a second Lab write lane.
phase.rs issue **#6337** is the same defect class, filed.
