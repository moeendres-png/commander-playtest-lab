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
| 1 | APNAP order of simultaneous triggers (3–6P) | correct; the engine seats counterclockwise | — | Sulfuric Vortex 6/6 | #311 merged |
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
