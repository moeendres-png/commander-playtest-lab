# Decision-surface audit — combat, optional costs, pay-to-prevent, tap costs

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
This audit applied the same checks to both candidates and ranks neither.

## Why

Real Commander decks win or lose through combat, and many staples use optional costs (kicker and similar) or "unless a player pays" taxes. We audited each candidate's external-pilot bridge for three failure modes:

- **Illegal options:** the bridge offers a decision the Rules Core would reject.
- **Missing options:** a legal decision is never offered.
- **Blocked play:** a legal decision halts or ends the game.

Every defect below was demonstrated with actual cards: the test fails on the previous code and passes after the fix. For XMage, that actual-card runtime test (`XmagePalaceGuardBlockTest`) was added after review of this handoff; the initial fix was backed only by engine source and a helper unit test.

## Forge — moeendres-png/forge#7 (stacked on #5, **not merged by design**)

Head `eb3aacad`. Base is #5's branch at `e15f37d6`, which Lab evidence cites as an exact head. Only `forge-protocol2-bridge` changes.

| Defect | Rule | Before | After |
|---|---|---|---|
| Lone blocker offered against a menace attacker; the engine never re-checks blocks | CR 509.1b | illegal block applied | only engine-valid declarations (`CombatUtil.validateBlocks`) |
| "No attacks" offered for a must-attack creature | CR 508.1d | offered | filtered by `CombatUtil.validateAttackers` |
| No multi-block options (e.g. Palace Guard) | CR 509.1a | missing | every attacker set allowed by `canBlockMoreCreatures` |
| More than 4 candidate attackers or blockers | — | fail-closed (combat impossible on wide boards) | incremental per-creature declaration, then native whole-declaration validation |
| Kicker, buyback, entwine or other optional cost in hand | CR 601.2b/f | whole priority frame `UNSUPPORTED` (player halted) | `COST_SELECTION` over every subset of the engine-supplied optional costs |
| "... unless that player pays {X}" (Rhystic Study, Smothering Tithe, Mana Leak) | — | `session_failed` when the effect resolved | payer chooses pay or do not pay; native payment path |
| Non-mana "unless" cost (shock lands such as Watery Grave: pay 2 life or enter tapped) | CR 614.12 / 118.12 | `session_failed` on playing the land | pay or decline framed; life paid through the native cost path |
| "Tap an untapped creature you control" costs (Springleaf Drum, convoke-like tap costs) | CR 118.3 / 602.2b | whole priority frame `UNSUPPORTED` | one option per legal permanent, plus decline |
| Crew N (Smuggler's Copter and every vehicle) | CR 702.122a | whole priority frame `UNSUPPORTED` whenever a vehicle and a creature were out | one option per creature set reaching power N, plus decline |
| Return-to-hand (ninjutsu), pay-energy, reveal, exert and mill costs (~300 cards plus every ninjutsu card) | CR 118 / 702.49 | whole priority frame `UNSUPPORTED` whenever such an ability was in reach | framed `COST_SELECTION` mirroring `HumanCostDecision`; `SameColor` reveals stay fail-closed |
| "Pay" chosen on an unless-cost the bridge could not carry out (Blazing Salvo's `DamageYou`, `Draw`, …) | — | silently counted as not paid: the payer took no damage and the creature still took 3; optional loot triggers (Windrider Wizard, Baral) were never asked | unless-costs with an undecidable part fail closed (one shared `unframedCostPart` check); damage and draw costs are framed |
| Emerge / offering (Elder Deep-Fiend, Distended Mindbender, …) | CR 702.119 / 702.48 | could never be cast that way (payment refused) | caster chooses the sacrifice, cost reduced, sacrifice only after payment; failed payment sacrifices nothing |

Evidence:

- `CombatBlockLegalityTest` 5/5, `OptionalCostChoiceTest` 2/2, `PayToPreventChoiceTest` 2/2, `ShockLandChoiceTest` 2/2, `TapTypeCostTest` 1/1, `CrewCostTest` 1/1, `NonManaCostPartsTest` 11/11 (Longtusk Cub, Induce Despair, Fervent Paincaster, Ninja of the Deep Hours, Wretched Gryff, Blazing Salvo, Windrider Wizard).
- Full `forge.bridge.**` suite 325/325 (301 on `e15f37d6`); project checkstyle green.
- Classification: `DIRECTLY_VERIFIED` (bridge runtime tests).

**To consume it in the Lab**, moving `FORGE_WORKSPACE` is not enough. `src/commander_lab/qualification/current_boundary/source_lock.py` binds the Forge bridge evidence identity to #5 (`FORGE_BRIDGE_EVIDENCE_COMMIT` / `_TREE` / `_PR`). Receipts produced from #7 while that lock still names #5 would be internally inconsistent. The current-boundary owner must:

1. re-pin those three constants to #7's exact head commit and tree at the time of the run;
2. then point `FORGE_WORKSPACE` at that checkout and regenerate the column.

`engine_tree_equivalence` still applies unchanged, because #7 touches only `forge-protocol2-bridge`. The Forge capability note no longer claims that combat or optional costs fail closed.

## XMage — PR #298 (merged as `2e28866f`)

XMage encodes "can block any number of creatures" as `maxBlocks == 0`; the pinned engine says so in `CanBlockAdditionalCreatureEffect`. Evidence:

- `XmagePalaceGuardBlockTest` runs a live 2P full-game combat with actual cards: two Raging Goblins attack into Palace Guard.
  - With `blockCapacity()`, P2 gets one block decision with `maximum_selections == 2` and blocks both attackers; the engine's own `Combat` records the Guard blocking both.
  - With the previous `min(maxBlocks, offered)` restored, P2 is never asked and takes 2 damage.
- `XmageBlockCapacityTest` (unit) covers the capacity rule itself.
- Classification: `DIRECTLY_VERIFIED`. `XmageFullGamePlayer.selectBlockers` computed `min(maxBlocks, offered) = 0` and skipped the blocker, so those creatures could never block and the decision was silently dropped. `blockCapacity()` now maps 0 to every offered attacker.

The rest of XMage's combat surface is already sound:

- declarations are made per creature;
- attack requirements are applied natively before the pilot is asked (`checkAttackRequirements`);
- block restrictions and requirements are re-validated in the engine's own loop.

### Same staples on XMage (no change needed)

`XmageStapleDecisionTest` (8 tests, actual cards, full-game lane) runs the cards fixed on Forge above:

- **Watery Grave:** P1 gets `choose_use` Yes/No. Paying leaves the land untapped at 38 life; declining leaves it tapped at 40.
- **Rhystic Study:**
  - P2 decides whether to draw.
  - Only if P2 chooses to draw is P1 asked whether to pay {1}.
  - Paying taps a third Forest and P2 does not draw; declining lets P2 draw.
  - Grizzly Bears resolves in every branch.
- **Burst Lightning:** kicking is P1's choice. Kicked, it taps 5 Mountains and deals 4; unkicked, it taps 1 and deals 2.
- **Smuggler's Copter:** every untapped creature is offered. After Raging Goblin reaches Crew 1, the follow-up choice has `minimum_selections == 0`, so the pilot stops without tapping Grizzly Bears.

Classification: `DIRECTLY_VERIFIED` for these four surfaces on XMage. Two protocol notes for pilots:

- In a `mana_payment` decision, the land options use action type `pay_cost`, not `activate_ability`. The first option is "Cancel mana payment".
- An empty selection at `minimum_selections == 0` is submitted as `structural_decision` with an empty `selected_option_ids`. It does not appear as a listed action.

## Also found (Forge, not changed here)

- `ScenarioBootstrap` (starting-state injection) exists, and Forge declares `starting_state_injection_supported=true`. The Lab's current-boundary driver never sends a `scenario.neutral_initial_state`, which is why Forge's 44 `BLOCKED` FULL107 rows are a Lab execution-path gap (`PROVIDER_READINESS_PACKET_20260928.md` §9).
- Remaining fail-closed Forge surfaces seen during the audit: `AnnounceType` spells (6 cards), splice (30), `sharesCreatureTypeWith` tap costs (1), `SameColor` reveals, and cost parts outside the framed set (gain life, collect evidence, blight, flip coin, roll dice, …).

## Impact adjudication owed by evidence owners

Historical Forge evidence may have depended on an illegal block option, or on optional-cost, pay-to-prevent, shock-land, tap-cost, crew, ninjutsu, energy, reveal, exert, mill or emerge cards halting or ending a game, or on an unless-cost "pay" choice that was silently not carried out. Historical XMage evidence with a "block any number" creature on the battlefield could not include that creature's blocks. Neither was re-run here.

## Exact next action

Re-run the Forge current-boundary column with `FORGE_WORKSPACE` on forge#7's head. After that, the largest Lab-side lever is exercising Forge's declared starting-state seam for the 44 `BLOCKED` rows.
