# Decision-surface audit — combat, optional costs, pay-to-prevent

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
This audit applied the same checks to both candidates and ranks neither.

## Why

Real Commander decks win or lose through combat, and many staples use optional costs (kicker and similar) or "unless a player pays" taxes. We audited each candidate's external-pilot bridge for three failure modes:

- **Illegal options:** the bridge offers a decision the Rules Core would reject.
- **Missing options:** a legal decision is never offered.
- **Blocked play:** a legal decision halts or ends the game.

Every defect below was demonstrated with actual cards: the test fails on the previous head and passes after the fix.

## Forge — moeendres-png/forge#7 (stacked on #5, **not merged by design**)

Head `23a2fccaae1`. Base is #5's branch at `e15f37d6`, which Lab evidence cites as an exact head. Only `forge-protocol2-bridge` changes.

| Defect | Rule | Before | After |
|---|---|---|---|
| Lone blocker offered against a menace attacker; the engine never re-checks blocks | CR 509.1b | illegal block applied | only engine-valid declarations (`CombatUtil.validateBlocks`) |
| "No attacks" offered for a must-attack creature | CR 508.1d | offered | filtered by `CombatUtil.validateAttackers` |
| No multi-block options (e.g. Palace Guard) | CR 509.1a | missing | every attacker set allowed by `canBlockMoreCreatures` |
| More than 4 candidate attackers or blockers | — | fail-closed (combat impossible on wide boards) | incremental per-creature declaration, then native whole-declaration validation |
| Kicker, buyback, entwine or other optional cost in hand | CR 601.2b/f | whole priority frame `UNSUPPORTED` (player halted) | `COST_SELECTION` over every subset of the engine-supplied optional costs |
| "... unless that player pays {X}" (Rhystic Study, Smothering Tithe, Mana Leak) | — | `session_failed` when the effect resolved | payer chooses pay or do not pay; native payment path. Non-mana prevention costs stay fail-closed. |

Evidence:

- `CombatBlockLegalityTest` 5/5, `OptionalCostChoiceTest` 2/2, `PayToPreventChoiceTest` 2/2.
- Full `forge.bridge.**` suite 310/310 (301 on `e15f37d6`); project checkstyle green.
- Classification: `DIRECTLY_VERIFIED` (bridge runtime tests).

**To consume it in the Lab**, point `FORGE_WORKSPACE` (see `scripts/run_current_boundary_qualification.py`) at a checkout of `claude/optimistic-bohr-6asye6` in `moeendres-png/forge`. The Forge capability note no longer claims that combat or optional costs fail closed.

## XMage — PR #298 (merged as `2e28866f`)

XMage encodes "can block any number of creatures" as `maxBlocks == 0`; the pinned engine says so in `CanBlockAdditionalCreatureEffect`. `XmageFullGamePlayer.selectBlockers` computed `min(maxBlocks, offered) = 0` and skipped the blocker, so those creatures could never block and the decision was silently dropped. `blockCapacity()` now maps 0 to every offered attacker.

The rest of XMage's combat surface is already sound:

- declarations are made per creature;
- attack requirements are applied natively before the pilot is asked (`checkAttackRequirements`);
- block restrictions and requirements are re-validated in the engine's own loop.

## Also found (Forge, not changed here)

- `ScenarioBootstrap` (starting-state injection) exists, and Forge declares `starting_state_injection_supported=true`. The Lab's current-boundary driver never sends a `scenario.neutral_initial_state`, which is why Forge's 44 `BLOCKED` FULL107 rows are a Lab execution-path gap (`PROVIDER_READINESS_PACKET_20260928.md` §9).
- Remaining fail-closed Forge surfaces seen during the audit: `AnnounceType` spells, splice, non-mana pay-to-prevent costs, and cost parts outside the framed set.

## Impact adjudication owed by evidence owners

Historical Forge evidence may have depended on an illegal block option, or on optional-cost or pay-to-prevent cards halting or ending a game. Historical XMage evidence with a "block any number" creature on the battlefield could not include that creature's blocks. Neither was re-run here.

## Exact next action

Re-run the Forge current-boundary column with `FORGE_WORKSPACE` on forge#7's head. After that, the largest Lab-side lever is exercising Forge's declared starting-state seam for the 44 `BLOCKED` rows.
