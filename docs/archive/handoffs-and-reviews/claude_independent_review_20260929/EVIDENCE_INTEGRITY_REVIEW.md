# Independent Current-Boundary Evidence Integrity Review — 2026-09-29

Reviewer: Claude Opus 5.5, independent and read-only against every audited
surface. This file is a review record. It changes no canonical evidence, no
denominator, no provider identity and no gate verdict.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

Evidence tags:
- `DV`: directly verified, by reading source or evidence.
- `RV`: runtime verified by this review, with the exact command given.
- `CD`: code-derived.
- `INF`: inference.
- `U`: unknown.

## A. Source lock

| Item | Identity |
|---|---|
| Lab `origin/main` | `afe09c61d4ad90f89c28ff75ac7439a20b89cfdd`, tree `0d5b3f0d9020cc99131dd92a41a9615c61bbac8a` (PR #291 merged 2026-09-29 01:19; it touched no qualification evidence) |
| Lab PR #289 (`sbmax/final-pre-freeze-20260928`) | OPEN draft. The audited head is `3f852485`; the branch later advanced to `0d010fe1`. Its evidence runner is `f432605e`, and nothing after it changed the runner or the driver except `hidden_obligations.py` |
| Lab PR #284 (`sol/final-integration-salvage-20260928`) | OPEN draft, head `46e971c0` |
| Lab PR #287 (`docs/final-adversarial-audit-20260928`) | OPEN draft, head `a84a39d0`, docs only |
| Forge PR #6 (`sol/final-candidate-successor-20260929`) | OPEN draft, head `6f70e32e` (tree `5fa5b947`); it changes `forge-game/.../Card.java` |
| New branch | `sol/muse-pb03-runtime-salvage-20260929`, head `2c1df76f`, test files only |
| Evidence directory | `qualification/final-current-boundary-20260927/` |
| Main XMage column | runner and adapter `1c8de8e3`, which predates #283 |
| Main Forge column | runner `f5d3197a`, adapter `e15f37d6`. The runner, assembler and `current_boundary/` code are byte-identical between `f5d3197a` and main (`git diff` empty) |
| XMage full-game AF01 artifact | runner `dfb490e2`, which is **not** an ancestor of main; it exists only on the closed WSR22 branch |
| Directory `SOURCE_LOCK.json` | binds `c5f9418e`, not the runners that produced the artifacts |
| Engine pins | XMage `b19596980f27…` (tree `04c00f25`). Forge executing Rules Core `ef958ee9` (tree `fc3387bf`); bridge/evidence head `e15f37d6` (tree `a1d4d4a8`); native-suite root `18bba95a`; bridge-source pin `4753bb7c`; upstream `a37a865a`, ancestry only |

## B. Current standing (recomputed from the rows)

| Source | XMage P/F/U/B | Forge P/F/U/B |
|---|---|---|
| main | 4/0/59/44 | 5/0/58/44 |
| PR #289 | 5/0/58/44 | 5/0/58/44 |

Each file has 107 unique rows and the `counts` fields match the rows `DV`.
`native_promotions = 0` on both sides.

## C. PASS credit matrix

| Row | Provider (source) | What the classifier checks | Contract obligation not checked | Review label |
|---|---|---|---|---|
| PLAYER_COUNT_2P..5P | XMage and Forge (main and #289) | All of: created count equals N; the lifecycle steps are present; `priority_reached`; at least one bound choice | 40 life; commander in the command zone; library of exactly 99 Mountains; hand of 7 after scripted keeps; the turn/priority ring. The executed deck is not the contracted one (Isamaru, 10 vanillas and 89 Plains, against the contract's 99 Mountains) | `SOUND_BUT_NARROW`. The observed state happens to show 40 life, the commander in the command zone and a 7-card hand, but nothing enforces it. For XMage, the "bound choice" is a single-option priority pass, and the mulligan keep is a bridge-internal default (F-03). Forge's `player_count` echoes the request handles, and the driver falls back to `len(handles)` |
| WS05-CMD-START-2 | Forge (main) | No DRAW-*kind* frame; no semantic event containing "draw" (Forge emits none); zone counts non-empty; an acting principal; `priority_reached` | Whether hand and library are **unchanged** from the post-mulligan state through entry to precombat main | `VACUOUS_RISK`, and the PASS reason is contradicted (F-02) |
| WS05-CMD-START-2 | XMage (#289 only) | Same classifier | Same | `UNSUPPORTED_CREDIT`. The committed evidence records a CR 103.8a violation (F-01) |

Counterfactual `RV`. Source: main `afe09c61`, `start2_row` byte-identical on #289. With `drive_commander_game` stubbed, `start2_row` returns PASS for hand/library 7/92, for 8/91 and for 40/−5. The count values never participate in the verdict.

## D. AF gate audit (main)

- **AF00, both PASS: tautological.**
  - XMage: `XmageProvider.ENGINE_COMMIT` is a hard-coded string constant, compared with the same constant.
  - Forge: the launcher injects `FORGE_ENGINE_SHA = FORGE_CANDIDATE_COMMIT`, and `source_lock_verdict` compares that echo back to `FORGE_CANDIDATE_COMMIT`.
  - `verify_pb05_provenance` has **no production call site**; only tests import it. The packet's "PB-05 RESOLVED … verify_pb05_provenance … Forge AF00 PASS" is therefore not how AF00 is computed.
  - This review found no actual identity error (see E).
- **AF01.** XMage FAIL is justified (`fail_closed_unsupported_decision`). Forge PASS rests partly on the `no_adapter_legality_reconstruction` invariant, an identifier regex over 11 Python files that never scans the Java adapters where defaults live.
- **AF02, PASS both.** Lifecycle only (see C).
- **AF03, PASS both.** Engine refusals on negative deck probes. Upheld.
- **AF04.** XMage FAIL and Forge UNKNOWN are justified.
- **AF05 to AF09, UNKNOWN.** Justified, with no overclaim found.
- **AF10, PASS both.**
  - The formula is: no crash, timeout or protocol failure, plus `native_green`.
  - The gate catalog also requires "no stale evidence". The main XMage column is admitted stale (pre-#283), and its native receipts ran at Lab `1c8de8e3`, before four #283 commits to `engine-bridge/src/main`.
  - Receipt freshness is keyed only on `candidate_commit` (the Mage commit), so an adapter change inside the Lab never invalidates XMage native credit. The XMage AF10 PASS overclaims.
- **AF11.** FAIL on main, UNKNOWN on #289 (recomputed). No overclaim.

## E. Identity and provenance

**XMage.**
- The identity is a Lab-bridge constant plus the jar location `~/.m2/.../mage-1.4.61.jar`, a mutable shared cache that is not digest-bound in receipts.
- `RV` by this review:
  - `~/.m2` `mage-1.4.61.jar` (built 2026-09-28T04:22Z) is class-identical to the jar built in the clean pin worktree `mage-rg-candidate-build@b1959698` (4456 class and txt files, 0 differ).
  - The `mage-game-commanderfreeforall` classes are identical.
  - The CommanderDuel classes are bytecode-identical to the pin source recompiled with `javac --release 8`.
- The identity therefore holds today, but the pipeline does not prove it. The `candidate_tree` field in XMage receipts holds the **Lab runner tree** (`aa923dd9`), not the Mage tree (`04c00f25`).

**Forge.**
- The build-derived commit (`e15f37d6`, from `bridge.properties`) and Rules-Core tree equivalence to `ef958ee9` exist and are verified for native receipts only.
- The Protocol-2 AF00 uses the env echo.
- The `candidate_tree` field in Forge receipts holds the bridge-head tree `a1d4d4a8`, not `ef958ee9`'s tree `fc3387bf`.
- PB-09 is untouched (Coordinator).

## F. Receipts and reproducibility

- All four committed receipts validate under the committed validator (`RV`).
- The digest is a self-hash: tamper evidence, not authenticity.
- The Forge column is regenerable by the current runner: its source is identical.
- The XMage column on main is not regenerable by the current runner and adapter; the drift is admitted.
- The full-game AF01 artifact was produced outside main's history.

## G. Anti-vacuity

**Robust (upheld):**
- Fixture-mention credit is removed.
- Denominator accounting is 107/107.
- Principal distinctness is content-only.
- Actual-card completeness derives from executed rows.
- The prose-claim guard is conditional.

**Vulnerable:**
- The START-2 guards are **source-text tests**: they assert that strings exist in `full107.py` and `game_driver.py`. They stayed green on #289 (104 passed, `RV`) while its committed evidence records the violation.
- Draw-step detection keys on decision *kind*. XMage exposes a draw-step checkpoint as kind `PRIORITY`.
- The observation's phase and step are not persisted, so "first checkpoint was precombat main" cannot be audited.

## H. Actual-card evidence

- `COMMON_FIXTURE_MANIFEST_v1` has 135 fixtures, including 29 CARD fixtures. The 107-row denominator contains only `CARD_02`, which is UNKNOWN on both sides.
- Behaviourally executed cards: 0 on both sides.
- The artifacts state this honestly (`DV`).
- Caveat: every FULL107 row, including BLOCKED rows, carries a 12-name `actual_cards` list. These are deck names, not card evidence.

## I. Hidden information, RNG and replay

**Seed control.**
- Forge's seed is acknowledged from engine state (`CD`: `installSeedBindingForCreation`).
- XMage's generic lane is uncontrolled, and is recorded as such.
- Replay rows are UNKNOWN.

**#289 PB-06.**
- It marks XMage `HIDDEN_01/02` `SATISFIED_BY_GENERIC_SCOPING`/`DIRECTLY_VERIFIED` against a paraphrase ("opponent hand identities absent while count visible").
- The contract postconditions also require "no prohibited metadata in **any** tested channel", knowledge invalidation, and the absence of the honey card `WS30_HONEY_P2_PRIVATE_7F3A`. None of these were exercised.
- It flips no row (disclaimed). The label still overclaims.

## J. Findings

- **F-01, P1 (#289, not main): demonstrated false credit, XMage START-2 PASS.**
  - Evidence: the row records `hand_count 8, library_count 91` for P1.
  - Cause:
    - Both XMage bridge lanes build every table as `CommanderFreeForAll`.
    - At the pin, that type sets `startingPlayerSkipsDraw = false` unconditionally, and its match type declares `minPlayers = 3`.
    - The Lab's own disabled `XmageFullGameStart2ExecutionTest` documents "P1 draws on turn 1 (hand 8 at the draw step)".
  - Classification: `DV` (evidence, source, Lab test comment) plus `RV` (classifier counterfactual).
  - Remediation surfaces:
    - Engine side: the bridge's game-type selection (taken up in this branch).
    - Evidence side: `full107.start2_row` must compare the observed counts to the post-mulligan baseline and require the observation at or after precombat main; `game_driver` must persist step and phase and detect draw-step checkpoints by step. That evidence side belongs to #289's owner.
- **F-02, P1 (main): Forge START-2 PASS is not supported by an observation of the obligation.**
  - Forge's first priority frame on turn 1 is `UPKEEP`. See `PLAYER_CARDINALITY_FORGE.json` 2P: after p1's pass, priority moves to p2 still in UPKEEP.
  - The START-2 drive has the identical decision tape and breaks right after that pass, so the 7/92 counts were read **before the draw step**.
  - A Forge that drew on turn 1 would also PASS (`RV` counterfactual).
  - The PASS reason ("first observable external checkpoint was the normal precombat decision handoff") contradicts the evidence.
  - Classification: `CD` plus `INF` from identical tapes. The step at observation is not persisted.
  - Remediation surface: the same as F-01's evidence side.
- **F-03, P1 (main, policy): forbidden default on the XMage generic B4-D lane, which `config/rules_engines.json` designates `production_bridge`.**
  - `XmageBridgePlayer.chooseMulligan` returns `false` (keep) with no `failIfExternallyControlled` guard.
  - The XMage PLAYER_COUNT PASS reason claims "external discretionary choices bound to engine-offered options", but no mulligan decision was external.
  - Classification: `DV`.
  - Remediation surface: `XmageBridgePlayer.chooseMulligan` (fail closed, or externalise). The Coordinator decides whether the B4-D compatibility lane counts as production-reachable.
- **F-04, P2: AF00 is tautological for both candidates.**
  - `verify_pb05_provenance` is not wired into AF00.
  - Maven artifacts are not digest-bound.
  - Surfaces: `assemble_current_boundary_evidence.source_lock_verdict`, and the receipts' environment identity.
- **F-05, P2: native-receipt staleness ignores Lab-side adapter drift.**
  - This makes XMage AF10 PASS an overclaim on main.
  - Surface: `receipts.native_suite_credit`, which should also bind `executed_commit` to the adapter tree when the engine is `ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT`.
- **F-06, P2: stale out-of-lineage artifact cited.**
  - `AF01_XMAGE_FULLGAME_LANE.json` (runner `dfb490e2`, not in main; 5 bridge files changed since) is cited in XMage AF01 limitations and in SLOT-07 reasoning.
- **F-07, P2: PLAYER_COUNT rows are narrower than claimed.**
  - They carry the contract's requested-state digest while executing a different deck.
  - None of the six postconditions is checked.
- **F-08, P2 (#289): PB-06 `SATISFIED`/`DIRECTLY_VERIFIED` labels overclaim** relative to the contract postconditions.
- **F-09, P2 (#284, forward risk): new positive-fixture path.**
  - Credit comes from JUnit XML plus **Lab-authored** obligation and assertion strings keyed by method name.
  - At least one string does not describe its test: `microContinuousCrawlerPowerToughnessFromHand` is described as a "Bonehoard Dracosaur-era continuous-state fixture".
  - The Coordinator's known P1 (sorted-first mana helpers) applies.
  - Once receipts carry these, the assembler's native promotion would flip BLOCKED rows to PASS. A per-case wrong-reason audit is required before merge.
- **F-11, P1: the Forge candidate executes a Lab-authored Rules change that contradicts Oracle for CARD_28 Find // Finality.** Added 2026-09-29; `DV`.
  - Lab Forge commit `bc347e62` ("WS234: systemic Cleave identity plus Aftermath script fix", 2026-09-15) is part of the executing Rules Core `ef958ee9`.
  - It added `K:Aftermath` to Finality in `forge-gui/res/cardsfolder/f/find_finality.txt` and rewrote the Oracle line to "Aftermath (Cast this spell only from your graveyard. Then exile it.)".
  - Upstream Forge at the pinned baseline `a37a865a` has no aftermath, which is correct. Oracle (Scryfall, layout `split`, keywords `[]`) and the official WotC rulings (2018-10-05, 2022-12-08) treat Find // Finality as an ordinary split card. The 2018 ruling says: "Finality doesn't target the creature… You can cast it even if you control no creatures". Scryfall's 27-card `keyword:aftermath` list does not include it.
  - The frozen CARD_28 fixture only names the card and states no aftermath obligation.
  - Consequences:
    - On the Forge candidate, Finality cannot be cast from hand and can be cast from the graveyard, both contrary to the rules.
    - Forge's Forge-local "28/29, Find // Finality aftermath gap" framing, DeepSeek DS-01 (PR #287) and Forge PR #6 ("require Finality aftermath cast and real resolution") are built on the false premise. Forge #6's test asserts a graveyard Finality cast.
  - XMage handles the card correctly: `XmageActualCardCorpusTest.findFinalityIsAPlainSplitCardCastableFromHandOnly`, runtime.
  - The smallest remediation is reverting the WS234 hunk for `find_finality.txt` in the Forge fork. The Forge lane owner and the Coordinator decide, because it changes the executing Rules Core (PB-09) and PR #6's premise. Before crediting Forge #6, its test must be re-derived from Oracle.
  - Scope check (`DV`): `find_finality.txt` is the only card script that Lab-authored commits changed between `a37a865a` and `ef958ee9`; the other 464 changed scripts come from upstream sync commits. Whether the Lab's Java changes in `forge-game` drift from Oracle is not covered here and remains UNKNOWN.
- **F-12, P2 — FIXED on branch `claude/xmage-special-mana-actions-20260929`: delve was not reachable for an external pilot on the XMage full-game lane.** `RV`, pin `b1959698`, Lab base `74841a08`.
  - For Dig Through Time, with six cards in the graveyard and two Islands, the `mana_payment` decision offers only the Island mana abilities and "Cancel mana payment" (`pay_cost`). No delve option is projected, so {6}{U}{U} is unpayable.
  - Recorded as the disabled `XmageActualCardCorpusTest.digThroughTimeDelvesSixAndKeepsTwoOfSeven`.
  - Remediation surface: the lane's payment projection (`XmageFullGamePlayer` mana payment and special actions).
  - Fix (reuse class `ENGINE_NATIVE_REUSE`): `XmageFullGamePlayer.playMana` now projects the engine's own special mana actions (`game.getState().getSpecialActions().getControlledBy(playerId, true)`). That is the same set XMage's human player offers during payment (`HumanPlayer.playManaHandling` → `activateSpecialAction`). The new option type `special_mana_action` maps to `pay_cost`, and the chosen action is activated through the engine.
  - Runtime: Dig Through Time now passes. Each delve activation exiles one graveyard card chosen by the pilot; six picks pay the {6}.
  - Convoke and improvise use the same engine path, but were not runtime-tested here (`CODE_DERIVED`).
- **F-13 — WITHDRAWN (reviewer error): Path of Ancestry.** The test assumed Rograkh is an "Ape Ninja". Oracle says **Kobold Warrior**, so Kird Ape correctly got no scry. With Goblin Piker (Goblin Warrior) paid partly with Path mana, XMage scries 1 as required, and Kird Ape still does not; both are runtime probes. Original, incorrect note: `RV`.
  - Kird Ape (Ape) was paid entirely with Path mana under Rograkh (Ape Ninja). No scry decision followed, although Oracle and the 2020-11-10 ruling require scry 1.
  - Candidates: the engine's delayed `MANA_PAID` trigger, an artefact of the restored board, or a bridge gap. Not attributed. Disabled test `pathOfAncestryScriesForACreatureSharingACommanderType`.
- **F-14 — RESOLVED, test-harness shape, not a defect: Magma Opus divided damage.** The lane expects the target and its share in one `target_amount` response (selected option plus `numeric_choice`). With that, Magma Opus passes: 4 damage to P2, two permanents tapped, a 4/4 Elemental, two cards drawn. Original note: Answering the `target_amount` decision ("Select targets (selected 0 of 4) (damage)") with a single-target selection ended the game. The accepted response shape is not established. Disabled test `magmaOpusDividesFourTapsTwoMakesAFourFourAndDrawsTwo`. This is not a Rules claim.
- **F-15, P2: restoration arrival runs beginning-phase triggers of restored permanents (XMage native state restoration).**
  - `applyPreStart` puts requested permanents onto the battlefield before the game starts.
  - Arrival then plays the restored turn through untap, upkeep and draw to the requested main phase, so those permanents' triggers fire and resolve.
  - Example: with one Sulfuric Vortex per seat, the restored active player arrives at 40 − 2N life, although the plan requests 40.
  - `compare()` detects this (life mismatch), but `XmageNativeStateRestorationTest.completeArrival`, which most runtime tests use, never runs `compare()`, so the drift is silent.
  - An experiment enforcing `compare()` in that helper across the bridge suite found no existing test affected by *trigger* drift. Its other mismatches are known and expected by their tests: later combat steps driven after arrival, and requested life not restored. *Correction:* the life mismatches are not state-based-action settlement. The engine re-derives starting life at game start, so a requested life other than the table's starting life never arrives. This is already documented by `XmageFullGameElimExecutionTest`. Under the F-15 policy (post-arrival compare, mismatch = no credit), restored life is not an exact-restoration dimension today. Fixtures needing low life use the engine's starting-life setting plus real damage (see `XmageMultiplayerSimultaneousLossTest`).
  - Impact: any restored plan containing permanents with untap/upkeep/draw triggers (for example Phyrexian Arena, Howling Mine, Sulfuric Vortex) starts from a state other than the requested one.
  - Owner decision (restoration lane / #304): fail closed on such plans, restore after arrival, or compare after arrival. This review does not change the shared helper, because the fix changes restoration semantics.
  - Also observed: the engine seats counterclockwise (turns, priority and APNAP pass P1 → PN → … → P2). This is consistent and already documented in `XmagePb03Tier2StackTest`. Consumers must take turn order from the engine, not assume ascending seat numbers. **Superseded 2026-09-30 by F-41:** the frozen contract orders turns by seat number, so this rotation was a bridge seating defect, not a harmless convention. Every lane now seats for P1 → P2 → … → PN; see `docs/multiplayer_findings/F-41_TURN_ORDER_RAN_AGAINST_SEAT_ORDER.md`.
  - `XmageMultiplayerApnapTriggerTest` measures against the post-arrival baseline and pins the drift.
  - **Addendum (opening hands).** Pre-start placement happens before the opening hands are drawn, so a restored permanent can even trigger on the opening-hand draws. Observed with Smothering Tithe ("whenever an opponent draws a card"): arrival stopped on an unexpected `trigger_order` decision. In a real game no such permanent can exist at that point. `XmageMultiplayerOpponentTriggerTest` therefore casts the Tithe during P1's main phase instead of restoring it. Routed to the restoration owner under the Coordinator's F-15 policy (post-arrival compare, mismatch = no credit).
- **F-16, P1: FIXED. The full-game lane offered blocks against creatures attacking other players (CR 802.4a).**
  - `XmageFullGamePlayer.selectBlockers` built block options from `Permanent.canBlock`, which checks only that the attacker's controller is an opponent.
  - In any game with attacks at two or more players, each defending player's creature was offered every attacker.
  - When the pilot picked an attacker attacking someone else, the engine's `declareBlocker` rejected it through `CombatGroup.canBlock` and dropped it silently, because non-human players get no notice. This is a forbidden silent skip on an over-offered option.
  - Fix: offer exactly what the engine will accept (`CombatGroup.canBlock`, which covers the defending player plus every attacker in the group).
  - Pinned by `XmageMultiplayerSplitCombatTest` (Hellrider + Raging Goblin attacking P3 and P2; 3–6P). The test is red before the fix.
  - `XmagePb03Tier1RowsTest.mpBlock4P2BlocksOnlyItsAttacker` had worked around it by holding the second attacker.
  - Impact: any full-game-lane evidence from 3+P games in which one combat attacked two or more players has different block option sets and may contain silently dropped blocks, so it needs impact adjudication. 2P and single-defender combats are unaffected. The generic lane fails closed on blocks and is unaffected.
- **F-17, P3: per-blocker block decisions can offer a block that is illegal only as a whole declaration. Outcome is rules-correct.**
  - The full-game lane asks one `declare_blocker` decision per blocker. Menace (702.111b) and similar "two or more" restrictions are judged on the whole declaration (509.1b), so a lone blocker is still offered the menace attacker.
  - The engine settles it in `Combat.selectBlockers` / `CombatGroup.checkBlockRestrictions`:
    - if a legal menace block exists, it rejects the declaration and re-asks every blocker;
    - if none exists, it discards the lone block, which is the only legal declaration, and logs the discard with `informPlayers`.
  - Pinned by `XmageMultiplayerMenaceTest` (Broadside Bombardiers; 3–6P; P2 with one or two Bears). Other players' creatures are never offered the menace attacker (802.4b, via F-16).
  - Consequence for decision analytics: the pilot's recorded choice can differ from the executed declaration. Evidence consumers must read blocks from engine combat state, not from pilot selections.
  - A declaration-level blocker surface would remove this. That is a protocol change, left to the decision-surface owner.
- **F-18, P3: engine (pinned `b19596980f27` and upstream master): simultaneous command-zone choices are not asked in APNAP order.**
  - `GameImpl.checkStateBasedActions` handles CR 903.9a / 704.6d by looping over `state.getPlayers().values()`. That is seat insertion order (P1, P2, …, PN), whereas the engine's turn order is counterclockwise (P1, PN, …, P2), so the choices should run in that APNAP order (101.4).
  - Each player's commanders are also moved before the next player chooses, where the state-based action should apply to all players simultaneously.
  - Every owner is still asked exactly once through the external surface, and every choice is honoured. In the probed case outcomes are unaffected, because each choice concerns only the chooser's own commander.
  - Pinned by `XmageMultiplayerCommanderZoneChoiceTest` (Pyroclasm kills every Rograkh; 3–6P). The CR order is a `@Disabled` test naming F-18.
  - The fix is an engine-fork change (iterate `state.getPlayerList(activePlayerId)` and move after all choices). That needs Sol's Rules Core / pin authority and is not done here.
- **F-19, P2: engine card implementations (pinned and upstream): "you may draw a card unless that player pays {N}" asks the controller before the payer.** Tracker #323.
  - `RhysticStudyDrawEffect` and Mystic Remora's effect ask the controller "Draw a card?" first, and only then ask the opponent "Pay {N}?", even when the opponent cannot pay.
  - The official rulings say the payer decides first and the controller decides afterwards. The pinned order leaks the controller's intent and skips the payment decision whenever the controller declines.
  - Lab evidence: `XmageMultiplayerUnlessCostTest` (4P/5P). Both principals are asked and outcomes are honoured; the payer-first test is `@Disabled` and names F-19.
  - Engine fix: Mage branch `claude/f19-unless-pays-order-20260929` from the exact pin, with native `UnlessThatPlayerPaysOrderTest`. Lab repin is a separate workstream.
- **Each-opponent APNAP order: see F-21 (#328, engine fix moeendres-png/mage#22), found and fixed by the parallel XMage multiplayer lane.**
  - This review found the same defect independently via a tempting offer: Tempt with Discovery cast by active P4 at 4P asks P1, P3, P2 instead of P3, P2, P1.
  - Its duplicate tracker (#330) and engine PR (mage#23) are closed. Its native tempting-offer tests are offered on mage#22.
  - Lab evidence: `XmageMultiplayerTemptingOfferTest` (3–6P). Every opponent is asked once and every search is honoured; the APNAP expectation is `@Disabled` and names F-21.
  - F-numbers from here on: this review's F-18/F-19 and the parallel lane's F-20 (initiative, #327) / F-21 (#328) are distinct findings.
- **F-24, P1: FIXED. The full-game lane made attack taxes unpayable (#338).**
  - `XmageFullGamePlayer.playMana` listed mana abilities via `getPlayable`. XMage returns nothing there while declare attackers is in its pre-step part (`SILENT_PHASES_STEPS`, a UI shortcut), and that is when attack costs are paid (CR 508.1h/i).
  - Ghostly Prison's "Pay {2} to attack?" therefore offered only "Cancel mana payment".
  - Fix: union with the engine's own `getUseableManaAbilities` for the player's permanents, the API XMage's human player uses while paying.
  - Pinned by `XmageMultiplayerAttackTaxTest` (3–6P, split and double attacks; red 6/6 → green 6/6).
  - Impact: any full-game-lane evidence involving attack taxes was unreachable before and is new capability now. Mana-payment option frames outside that window are unchanged (full bridge suite green).
- **Note:** Sol's hardening commit `746a0f44` failed 5 corpus tests; single-step payment was not yet supported. Sol's follow-up `2ca4313c`/`b239a161`, merged with #294, resolves it. This review's own alternative payer was discarded in favour of Sol's.
- **F-10, P3:**
  - Receipt `candidate_tree` fields hold executed or Lab trees.
  - The directory `SOURCE_LOCK.json` is stale.
  - `actual_cards` appears on all rows.
  - Mulligan tape entries have `chosen_option_id = null` (keep verb, not an offered option).
  - Forge `player_count` echoes the request.
  - The static legality scan excludes the Java adapters.

## K. Claims challenged but upheld

- The Forge evidence column was produced by source identical to current main.
- XMage engine bytes equal the pin (`RV`, jar class identity).
- Actual-card artifacts do not overclaim.
- Principal distinctness is content-only.
- The 107-row accounting is intact.
- Forge AF03 comes from the Rules Core's `deck_not_legal`.
- The Forge seed is acknowledged from engine state.
- No row is promoted from fixture-name mention (`native_promotions = 0`).

## L. UNKNOWN

- Exact step and phase of each START-2 observation, since they are not persisted.
- Whether Forge actually skips the turn-1 draw in 2P: not observed on the current boundary. The WSR20 native test exists but is not current-boundary credit.
- Whether the Maven jar present at any *past* receipt time equals today's jar. The mtime is 2026-09-28T04:22Z, which precedes all current receipts. This is `INF`.

## M. Impact on the provider comparison (facts only)

- The current-boundary START-2 credit is unsupported for both candidates: Forge on main, XMage on #289.
- The honest XMage count on #289 is 4 PASS. The honest START-2 status for both is UNKNOWN until the classifier discriminates.
- PLAYER_COUNT credit is lifecycle-only for both candidates.

## N. Smallest next actions

- **F-01 and F-02 (#289 owner):**
  - Persist the observation step and phase.
  - Require observation at or after `PRECOMBAT_MAIN` of turn 1.
  - Compare hand/library to the post-mulligan baseline.
  - Detect draw-step checkpoints by step.
- **F-01, engine side:** this branch.
- **F-03:** fail closed in `XmageBridgePlayer.chooseMulligan` under external control (the generic lane's owner, or a successor).
- **F-04 to F-06:**
  - Wire build-derived identity into AF00.
  - Bind adapter drift into receipt freshness.
  - Stop citing `dfb490e2` artifacts.
- **F-09:** a wrong-reason audit of every `XMAGE_PB03_POSITIVE_CASES` entry before #284 merges.
