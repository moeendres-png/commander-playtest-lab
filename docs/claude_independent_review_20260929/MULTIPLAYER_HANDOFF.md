# AUTONOMOUS MULTIPLAYER ADVANCEMENT HANDOFF

Claude Opus 5.5 (Claude Code), 2026-09-29. There were two campaign phases: #311–#315, and then this continuation after the Coordinator update.
`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## Final Source Lock
- Lab `main` at the last verification: `92ac1cec` (after #329). #331 has auto-merge armed and this handoff PR follows it.
- XMage Lab pin: `b19596980f2734496ea1896504253e1bdd2756dd` (tree `04c00f25`). **Unchanged.**
- Rules: CR 2026-09-25 (sha256 `8d860e45…`). Oracle and rulings: Scryfall, 2026-09-29.
- State: `.foundry/claude-mp-campaign-20260929.json` (schema 2.0, STATE_OK, COMPLETE).

## Milestones Completed

| # | Problem | Root cause / result | Fix | Tests | Integration |
|---|---|---|---|---|---|
| 1 | APNAP order of simultaneous triggers (3–6P) | correct; the rotation then ran P1 → PN → … → P2, corrected to seat order by F-41 | — | Sulfuric Vortex 6/6 | #311 merged |
| 2 | Each-player choices (3–6P) | correct | — | Innocent Blood 4/4 | #312 merged |
| 3 | **F-16** split-attack blocks offered illegally, then silently dropped | lane used `Permanent.canBlock` | lane offers `CombatGroup.canBlock` | Hellrider split combat 4/4 (red before) | #313 merged |
| 4 | Defending-player targeting, menace, goad | correct; F-17 surface limitation recorded | — | 4/4, 6/6, 4/4 | #314 merged |
| 5 | Voting, monarch, leaving mid-combat, commander-zone choices | **F-18** found | engine fix, row 7 | 4/4, 8/8, 4/4, 4/4 + disabled | #315 merged |
| 6 | Hidden info in simultaneous discards; seeded random discards | correct, no leakage | — | Delirium Skeins 4/4, Burning Inquiry 2/2 | #318 merged |
| 7 | **F-18** commander-zone SBA choices in seat order, moved one owner at a time | `GameImpl` iterated `getPlayers()` and moved inside the loop | APNAP via the static turn-order list; collect all choices, then move | native 3–6P 12/12 (red 8/8 on pin); mutation killed; full Mage.Tests 6941 / 0 failures | **mage#19 draft** |
| 8 | Competing replacement effects (CR 616.1) | correct: the affected player orders them | — | Boon Reflection vs Tainted Remedy 8/8 | #319 merged |
| 9 | Random opponent selection | seed-authoritative | — | Vial Smasher 4P/5P, 8 seeds | #320 merged |
| 10 | Simultaneous losses; all-lose draw | correct (704.5a, 800.4k, 104.4a) | — | Flame Rift 6/6 | #322 merged |
| 11 | **F-19** Rhystic Study / Mystic Remora ask the controller before the payer | card scripts in the wrong order | payer first (only if able), then the controller's may-draw | native 4P 6/6 (red 6/6 on pin); `multiplayer` package 75/75 | **mage#20 draft**; Lab #324 merged |
| 12 | Opponent-driven choices and results | correct | — | Smothering Tithe 4/4, Curse of Opulence 4/4 | #329 merged |
| 13 | Tempting offer | order defect = the parallel lane's **F-21** | duplicate closed (mage#23, #330) | 4/4 + disabled | #331 |

## New Findings (details in `EVIDENCE_INTEGRITY_REVIEW.md`)
- **F-16 (fixed, #313).** The Coordinator ruled no blanket requalification. Pre-#313 split-attack legal-option evidence is STALE.
- **F-15 (restoration, open).** Restored permanents act during arrival. Addenda:
  - opening-hand draws also trigger restored permanents;
  - requested life is never restored, because game start re-derives it. My earlier "SBA settlement" note was wrong and is corrected.

  Coordinator policy applies: post-arrival compare, and a mismatch earns no credit.
- **F-17 (P3).** Per-blocker surface. Engine outcomes are correct; consumers must read executed blocks from engine combat state.
- **F-18 (engine, fix mage#19).** Commander-zone choices: APNAP order, simultaneous.
- **F-19 (engine, fix mage#20).** "May draw unless that player pays": payer first.
- **F-21 (parallel lane, #328 / mage#22).** Confirmed independently by the tempting-offer probe.

## Current Multiplayer Capability (stronger than at campaign start)
- **Runtime-evidenced at 3–6P on the XMage full-game lane with actual cards:**
  - APNAP triggers and each-player choices;
  - split-attack block legality (fixed), menace, goad, defending-player targeting;
  - voting and monarch (both 725.4 branches);
  - elimination mid-combat, simultaneous losses and draws, turn skipping for departed players;
  - commander-zone choices, replacement ordering by the affected player;
  - hidden-hand isolation in simultaneous choices;
  - Rules-RNG reproducibility for random discards and random opponents;
  - opponent-owned payments and results.
- **Engine-level fixes ready at the exact pin (not yet in the Lab pin):** F-18 and F-19, plus the parallel lane's F-20 and F-21.

## Actual-Card Evidence Added
Sulfuric Vortex, Innocent Blood, Hellrider, Raging Goblin, Impetuous Devils, Broadside Bombardiers, Disrupt Decorum, Council's Judgment, Palace Sentinels, Pyroclasm, Rograkh, Delirium Skeins, Burning Inquiry, Healing Salve, Boon Reflection, Tainted Remedy, Vial Smasher the Fierce, Flame Rift, Lightning Bolt, Lava Spike, Rhystic Study, Mystic Remora, Smothering Tithe, Curse of Opulence and Tempt with Discovery. Native Mage tests additionally use Wrath of God, Final Judgment, Isamaru and Ardenn.

Classification at the exact source lock + pin:
- TECHNICALLY_CONFORMANT for the exercised path;
- EXTERNALLY_RULE_VALIDATED where the scenario is bound to the CR plus Oracle/rulings.

No FULL107, denominator or AF promotion is claimed.

## Current PASS / FAIL / UNKNOWN
- **Lab engine-bridge suite:** 518 run, 0 failures, 7 skipped.
  - The skips are the START-2 provenance test plus disabled engine-finding expectations (F-18, F-19, F-21, and the parallel lane's).
  - These disabled tests are **known FAIL at the current pin**. They are not UNKNOWN and not PASS.
- **Native Mage:**
  - F-18 12/12, full suite 0 failures;
  - F-19 6/6, multiplayer package 75/75.

## Open Defects Routed Elsewhere
- **2P-only:** none found in this phase.
- **F-15:** restoration lane (#304/#316).
- **F-20/F-21:** the parallel lane owns them (#327/#328, mage#21/#22).
- **Forge ports of these scenarios:** Forge lanes.

## Active Dependencies / Ownership
- Mage draft PRs #19 and #20 (mine) and #21/#22 (parallel lane) all target PR #16's branch = the pin. Only #22 touches `Game.java`.
- The parallel lane `claude/optimistic-bohr-6asye6` is active on XMage multiplayer engine findings. A coordination note is on #328.

## Remaining Highest-Value Multiplayer Frontier
1. **Repin workstream (needs Coordinator authority):**
   - engine = pin + mage#19 + #20 + #21 + #22;
   - re-pin the Lab and impact-adjudicate;
   - enable the disabled F-18/F-19/F-21 Lab tests through the external-control path.
2. **F-15:** a restoration arrival compare or a fail-closed path (restoration owner).
3. **Forge ports** of the 3–6P scenarios once the Forge lanes free up.
4. **F-17:** a declaration-level blocker decision surface (P3).
5. **Card-local "each player" loops** that start from the controller (about 70; see the mage#22 handoff), after #22 lands.

## Exact Next Action
The Coordinator authorises the repin workstream. A fresh session then:
1. fetches the Mage fork and builds an integration branch from `b19596980f27` merging mage#19, #20, #21 and #22;
2. runs full `Mage.Tests`;
3. repins `config/rules_engines.json` on a Lab branch;
4. removes `@Disabled` from `XmageMultiplayerCommanderZoneChoiceTest.commanderZoneChoicesFollowApnapOrder`, `XmageMultiplayerUnlessCostTest.thePayingPlayerDecidesBeforeTheController` and `XmageMultiplayerTemptingOfferTest.opponentsAreOfferedInApnapOrder`;
5. runs `cd engine-bridge && mvn -o -Dcheckstyle.skip=true test` and impact-adjudicates the pin move.

---

## Addendum: phase 3 (after the Coordinator repin authority), 2026-09-29

- **XMage candidate integration (mage#24, `f79e4168`).**
  - Contents: F-18 + F-19 + F-20 + bounded F-21 (explicit APNAP primitive; `getOpponents` unchanged).
  - Native evidence: 72/72 targeted; full `Mage.Tests` 7001 / 0 failures / 0 errors / 125 skipped.
- **Lab successor repin (#337, merged as `ba629ced`).**
  - The live pin is `f79e4168`, and the WSR22 `source_lock.py` stays historical.
  - Successor lock: `qualification/xmage-mp-candidate-repin-20260929/SUCCESSOR_SOURCE_LOCK.json`.
  - The F-18 to F-21 regressions were re-enabled: red on the prior pin, green on the candidate.
  - Impact adjudication: `docs/workstream_xmage_mp_candidate_repin_20260929/`.
- **F-24 (#338 → #339), bridge fix.** Attack-tax payments (Ghostly Prison family) previously offered only "Cancel", because `getPlayable` is silent during declare attackers. The lane now uses the engine's `getUseableManaAbilities`. Red 6/6 before, green 6/6 after.
- **New probes (3–6P, all green, no defect):**
  - player protection, Teferi's Protection (#341);
  - join forces, Minds Aglow (#342);
  - overload, Cyclonic Rift (#343);
  - APNAP semantic replay, Grave Pact and Innocent Blood (#352);
  - extort, Syndic of Tithes (#353).
- **Forge unified successor (moeendres-png/forge#11, draft, not for master).**
  - Contents: #6 + #7 + #9 Finality Oracle correction; #6's Aftermath regression re-bound to Cut // Ribbons (the fix is real: 3/6 red without it).
  - Results: bridge 347/0, `forge-gui-desktop` 458/0/6, checkstyle pass, exact-head CI all pass.
  - Handoff: `forge-protocol2-bridge/forge-unified-successor-20260929/HANDOFF.md`.
- **Open decisions (Coordinator):**
  - Forge #11: accept the #9 inclusion, or require a pure #6 + #7 identity;
  - a successor FULL107 current-boundary run on the new XMage pin.
- **Not mine / routed:**
  - F-15 restoration (evidence posted on #304 and #333);
  - F-22, F-23, F-25 to F-27 belong to the parallel lane;
  - #333's `WS17_SHA256SUMS` conflict: guidance posted, left for its owner.

---

## Addendum: phase 4 (discovery campaign, continued), 2026-09-29

### New probes (3–6P, all green, no defect)

| PR | Probes |
|---|---|
| #361 | Assist (Gang Up), encore (Impulsive Pilferer), dethrone + melee (Marchesa's Emissary / Grenzo's Cutthroat / Wings of the Guard), undaunted (Sublime Exhalation), friend-or-foe (Pir's Whim) |
| #362 | Seat direction: Mystic Barrier and Order of Succession, left/right against CR 103.1 |
| #363 | Third-party combat triggers: Karazikar and Edric |
| #367 | Enter-attacking: Hero of Bladehold plus Ghostly Prison, CR 508.4 / 508.4c |
| #367 | Ninjutsu in a split attack: Ninja of the Deep Hours |
| this PR | Lure in a split attack: Prized Unicorn |

### New engine findings (RULES_CORE_DEFECT, fixed in the fork at the pin)

**F-28**, `docs/multiplayer_findings/F-28_*`:
- A "blocks if able" requirement demanded a block of a creature attacking another player (CR 802.4a).
- XMage's block declaration then looped forever on the engine thread, and the game hung.
- Fix: moeendres-png/mage#27.
- Evidence: native red is a 1260 CPU-s spin; green 2/2. Lab `XmageMultiplayerForcedBlockTest` hangs 4/4 on the pin.

**F-29**, `docs/multiplayer_findings/F-29_*`:
- With several defending players, blockers were declared in hash-set order, not APNAP (CR 802.4).
- The order also differed between identical games, which is a semantic-replay defect.
- Fix: moeendres-png/mage#28, stacked on #27.
- Evidence: native red 2/3, green 3/3. Lab `XmageMultiplayerBlockOrderTest` red 4/4 on the pin.

**Combined head `3c0fe388`** (F-28 + F-29 on top of `f79e4168`):
- Full `Mage.Tests`: 7006 run, 0 failures, 0 errors, 125 skipped. The baseline at the pin was 7001 / 125.

### Authority gate (user)

Integrating mage#27/#28 into the candidate branch (a fast-forward to `3c0fe388`) was **refused by the session's auto-mode classifier as a merge without review**. That integration, and the Lab successor repin v2 that depends on it, wait for a user or reviewer decision.

Until then:
- the Lab regressions for F-28 and F-29 stay `@Disabled`;
- the live pin stays `f79e4168`.

### Exact next action (after approval)

1. Merge mage#27, then mage#28, into `claude/xmage-mp-candidate-20260929`. This is a fast-forward to `3c0fe388`.
2. Build the isolated Maven repo `m2-xmage-candidate-3c0fe388`. Use the same recipe as for `f79e4168`: a real `org/mage` directory with the candidate `mage` / `mage-sets` installed, and everything else symlinked to `~/.m2`.
3. Repin the Lab through successor lock v2 (`qualification/xmage-mp-candidate-repin-v2-20260929/`), following #337:
   - consumers, workflows, scripts, unit pin tests;
   - a v2 guard test, with the v1 guard's current-pin checks marked superseded;
   - SHA256 manifests;
   - a fingerprint extension: `Combat` declares `canBlockInThisCombat` and `getPlayerDefendersInApnapOrder`.
4. Enable `XmageMultiplayerForcedBlockTest` and `XmageMultiplayerBlockOrderTest`. Run the bridge suite and impact-adjudicate, adding multi-defender combat evidence to the F-16 scope.

---

## Addendum: phase 5 (2026-09-30), engine integration, replay harness, CI hygiene

### Engine and pin
- **Candidate `9375f35a`** (moeendres-png/mage#24), assembled from `f79e4168` plus:
  - F-22/F-23 (mage#26, sol lane);
  - F-28/F-29 (mage#27/#28);
  - the F-34 donor `2786665809` (parallel lane).
- Full `Mage.Tests`: **7020 / 0 / 0 / 125**.
- **Repin v2 #385 merged (`24b355b7`).** The live pin is `9375f35a`.
  - Successor lock v2: `qualification/xmage-mp-candidate-repin-v2-20260930/`.
  - F-22, F-23, F-28 and F-29 regressions are enabled.
  - Lab bridge suite: 807/0/1. Python suite: 2364 passed.
  - #385 supersedes the draft #360; its owner has been informed.

### New lane findings (all fixed, red → green)

| Finding | PR | What was wrong |
|---|---|---|
| F-30 | #382 | Priority hid activated abilities with equal rule text on different permanents (XMage's AI `getPlayable` dedup), in hash order. |
| F-35 | #382 | Offered options that could only fail aborted real games: modes without legal targets (CR 700.2a), and mana abilities whose own cost can't be paid (Signet, Study Hall). |
| F-36 | #384 | Decision options were ordered by random object ids. A library search picked a different "first Plains" per replay, and the shuffle then diverged the game. |
| F-37 (AF01) | #390 | AF01 fail-closed probes credited malformed-request rejections as PASS, and the generic lane answered an unsupported decision class with the pending options. |
| F-30 (generic lane) | #393 | The generic Protocol-2 lane had the F-30 dedup and the F-36 ordering too; both lanes now share `XmageStableOrder`. |
| F-38 | #397 | Native restoration placed a battlefield commander as a setup copy. That is why the 8 `WS05-CMD-ZONE-*` rows never got their zone choice and ELIM-4 never accrued commander damage. All 9 obligations are now executed on the genuine commander. |
| F-41 | this PR | The bridge seated players so that turns ran P1 → PN → … → P2, against the contract's seat order ("Priority traverses exactly P1..PN"). XMage's `CircularList.add` reverses the add order. Every lane now seats for P1 → P2 → … → PN. The earlier "counterclockwise, consistent" reading (F-15..F-18) matched the engine, not the contract. |

### Whole-game replay harness
`XmageFullGameReplayTwinTest` plays real 100-card decks (RogShai, Kaervek, Hosts of Mordor, Lorehold Spirits) at 2–6P, up to 3000 decisions per game. Each game is played twice with the same seed by a semantic pilot.

- Options: `-Dtwin.extended`, `-Dtwin.seeds`, `-Dtwin.variant`.
- After F-30/F-35/F-36, 20+ games are identical in every pair, including combat-spreading and reversed-preference pilot variants, and many reach a regular game over.

### CI and hygiene
- **#374:** the XMage engine is cached by pin commit, the bridge suite runs once instead of four times, and H4 provider builds are scoped. About 30 of 48 runner-minutes per bridge PR are saved.
- **#383:** record in `docs/ci_efficiency_20260930/`.
- **#386:** the engine workflows always report, so their jobs can be required checks.
- **Owner actions**, listed in `docs/ci_efficiency_20260930/README.md`:
  - add the required checks;
  - disable 181 dead workflow registrations (a one-line command);
  - pause the Codex review bot.

### Next
- A successor FULL107 current-boundary run on `9375f35a` (Coordinator gate).
- The redundant nested WS17 manifest entry (Coordinator).
- Note: the F-number 37 was used twice: #390 (AF01) and #392 (leaver actions, parallel lane). Check both lanes before numbering.
