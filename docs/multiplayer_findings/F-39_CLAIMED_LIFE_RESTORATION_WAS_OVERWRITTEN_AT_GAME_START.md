# F-39: the restoration claimed life totals, but game start overwrote them

Status: FIXED in the XMage native state restoration (this PR, stacked on F-38). Claude Opus 5.5, 2026-09-30.

- **Classification:** `BRIDGE_SURFACE_DEFECT` in `engine-bridge/.../XmageNativeStateRestoration`. It was a claimed-but-ineffective dimension; the compare caught it, so there was no false PASS.
- **Source lock:** Lab main `1242f79f` + F-38, live XMage pin `9375f35a`.
- **Affected records:** every frozen record in which a player's `starting_life` differs from the table's 40:
  - `CARD_04`, `CARD_16`, `CARD_24`: P2–P4 or P2 at 20;
  - `CARD_25`: P1 at 20.

## What happened

- The dimensions payload listed "life totals (pre-start assembly)" as supported.
- `applyPreStart` called `Player.setLife` before the game started.
- `GameImpl.init` then ran `player.initLife(startingLife)` for every player, so every requested life came back as the table's starting life.
- The compare reported `life P2: requested 20 observed 40`.

Result: CARD_04 and CARD_24 were `CONSTRUCTION_MISMATCH`, although nothing about their state is historical: 20 is those players' recorded **starting** life.

## Fix

The rule follows the project's causal principle ("a player at zero life must have lost that life"):

- **Starting life equals requested life.** Nothing was gained or lost, so it is set once after arrival, silently, through the engine's own `Player.initLife` (the call game start uses). No gain or loss event is fabricated.
- **Only while untouched.** It is set only while that player's life is still what game start left: the table's starting life, and no life lost or gained. Life the engine already changed during arrival is real history and is never overwritten. Example: in `MICRO_CONTINUOUS_EFFECTS`, a restored Psychosis Crawler's start triggers cost every opponent 8 life.
- **Any other requested life is history.** Life 0 in the elimination rows must be caused through the engine (the elimination route's Bolts). It is compared, never set; this is unchanged.
- **Cleanup.** The ineffective pre-start `setLife` is removed. `restoreCommanderCasts` is renamed `restoreAfterArrival`: it now restores cast counts, commander damage, commanders outside the command zone (F-38) and starting life.
- **Limit (documented).** The engine keeps one table starting life (`Game.getStartingLife`). A card that reads "starting life" sees the table's value, not the player's.
- **Relation to the L6 integrity decision.** `docs/residual_closure_campaign_20260926/HANDOFF.md` removed *manufactured mid-game preconditions* (for example, life lowered so that an elimination is cheap) and permits "bounded initial game configuration". A player's own recorded starting life is initial configuration.
  - It is applied at arrival rather than inside `GameImpl.init`. The engine's `initLife` runs after the starting-player choice, and the bridge does not use the engine's test mode (which would keep pre-start life but skip opening hands).
  - The "untouched" guard makes the result observationally identical to an init-time setting in every case where it applies, and inapplicable in every other case.
  - Life 0, or any value other than the starting life, is still never set.

## Evidence

**Midgame probe, 38 rows** (the F-38 set plus CARD_16/24/25), F-38 branch vs. this branch:

| Row | Before | After |
|---|---|---|
| `CARD_24` | `CONSTRUCTION_MISMATCH` (life P2 20/40) | `ENGINE_NATIVE_REACHABLE`, construction `EXACT` |
| `CARD_04` | `CONSTRUCTION_MISMATCH` (life P2–P4, priority) | `ENGINE_NATIVE_REACHABLE`, `ALLOWED_VARIANCE` (the declaration-step priority allowance, reported openly) |
| The other 36 | — | Same outcome, code, detail and mismatches |

CARD_16 (a stack spell) and CARD_25 (counters) remain rejected for their own dimensions.

**Tests:**

- `XmagePb03Tier1RowsTest.card24WarstormSurgeTakesP2FromItsStartingTwentyToEighteen` executes the obligation:
  - P2 starts at 20 while P3 stays at the table's 40;
  - P1 casts the recorded Grizzly Bears with the recorded Forests, and Warstorm Surge's trigger targets P2;
  - P2 ends at 18;
  - the engine's `PlayerLostLifeWatcher` holds exactly 2, so the restoration fabricated no loss;
  - a repeated completion does not reset life after the damage.
- `XmageNativeStateRestorationTest.aLifeTotalOtherThanTheStartingLifeIsNeverSet`: 30 at a starting life of 40 is not set (`life P1: requested 30 observed 40`), while P2's starting 20 is restored.
- The existing Psychosis Crawler test (`MICRO_CONTINUOUS_EFFECTS`) stays green. It was the red case for the first, unconditional version of this fix.
- Full bridge suite: 824/0/1.

## Not done here

- **CARD_04 constructs but is not executable as frozen (fixture gap, Coordinator).**
  - Bruse Tarl's attack trigger is mandatory: "target creature you control gains double strike and lifelink" (XMage `EntersBattlefieldOrAttacksSourceTriggeredAbility` with `TargetControlledCreaturePermanent`).
  - The record's `decision_script` declares only the attack and the empty block, not this target.
  - The recorded outcome (3 commander damage, P2 = P3 = P4 = 17) holds only if the trigger targets Kediss. Targeting Bruse gives double strike: 6 commander damage, 14 each, and P1 gains 6.
  - A strict runner must fail closed on the undeclared decision (`first_option` and `silent_skip` are forbidden).
- **WS05-MP-ELIM-STACK-3** (P2 at 0 with its own Bolt on the stack) needs a combined route: stack first, then the elimination caused in response.
- **FULL107 re-evaluation** is a Coordinator gate.
