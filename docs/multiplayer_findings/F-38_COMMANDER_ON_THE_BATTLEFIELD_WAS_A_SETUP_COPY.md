# F-38: native restoration placed a battlefield commander as a setup copy, so commander rules never applied to it

Status: FIXED in the XMage native state restoration (this PR). Claude Opus 5.5, 2026-09-30.

- **Classification:** `BRIDGE_SURFACE_DEFECT` in `engine-bridge/.../XmageNativeStateRestoration`. The engine was right; the rows were misattributed to it.
- **Source lock:** Lab main `1242f79f`, live XMage pin `9375f35a`.
- **Affected records:** every frozen record (`qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`) whose `commander_state.commanders[].zone` is `battlefield`:
  - the 8 `WS05-CMD-ZONE-*` rows;
  - `WS05-CMD-ELIM-4`, `WS05-CMD-DMG-SAME-21`, `WS05-CMD-DMG-CONTROL`;
  - `MICRO_COSTS`, `CARD_03`, `CARD_04`;
  - `PILOT_REPLACEMENT_EFFECT`.

## What happened

The restoration ignored `commander_state.commanders[].zone`. It left every commander in the command zone and placed the record's battlefield object (`semantic_objects[]` with `commander_id`) as a generic card from the materialization vehicle. That permanent had the right name but was not the commander, so:

- the commander zone choice (CR 903.9a/b) never came when it left the battlefield;
- its combat damage never reached the commander-damage ledger (CR 903.10a).

Two tests had pinned this artifact as an engine limitation:

- `XmagePb03Tier2CmdZoneTest` and `XmageMidgameCausalTest`, 8 rows each: "duality", no choice decision, BLOCKED.
- `XmagePb03Tier1RowsTest.elim4…`: "setup copies do not accrue commander damage", BLOCKED.

The midgame probe reported the 8 zone rows as `CAUSAL_ROUTE_MEASURED_BLOCKED` ("the engine resolved to cleanup with no zone-choice decision").

## Fix

1. **Plan.** `planFromFrozenRecord` reads the commander zone. It supports `command` and `battlefield`; anything else is rejected with `UNSUPPORTED_COMMANDER_ZONE`. The battlefield object with `commander_id` binds 1:1 to that commander, and is never a generic object. Everything else fails closed before any mutation:
   - `COMMANDER_ZONE_CONFLICT`: zone mismatch, a second object for the same commander, or a different owner or identity;
   - `COMMANDER_OBJECT_MISSING`;
   - `UNSUPPORTED_CONTROL_DIVERGENCE`: same code as for every other permanent;
   - `UNSUPPORTED_COMMANDER_OBJECT_STATE`: tapped.
2. **Pre-start binding.** `applyPreStart` binds the commander to the owner's one sideboard card of that identity. `GameCommanderImpl.init` makes exactly those cards the commanders. The native id is published in the causal plan's `placed_objects`, so a pilot can match the engine's target offers.
3. **Placement.** At arrival completion, the genuine commander leaves the command zone through `Card.removeFromZone(COMMAND)`. It enters the battlefield silently through `CardUtil.putCardOntoBattlefieldWithEffects`, the same no-ETB primitive the rest of the placement uses. Placement requires:
   - the engine's commander id to equal the pre-start binding;
   - that it happens exactly once. The causal route completes commanders before the stack and arrival completion repeats it; the compare, not a second move, judges the result.
4. **Readback and compare.** Commanders are read from the engine's own commander set with their zone. The compare checks the requested zone, so a board with the commander on the battlefield no longer matches a command-zone request.
5. **Lane diagnostics.** A `complete_midgame_arrival` rejection now carries the engine's reason in the row detail, not just the code.

## Evidence

**Midgame capability probe, 35 rows** (the default set plus every affected record), run twice with the same pin, seed and rows:

- baseline: main `1242f79f`;
- after: this branch.

| Rows | Before | After |
|---|---|---|
| `WS05-CMD-ZONE-{GY,EXILE,HAND,LIB}-{YES,NO}` (8) | `CAUSAL_ROUTE_MEASURED_BLOCKED`, no zone choice | `CAUSAL_ROUTE_REACHABLE`, `terminal_obligation.observed: true`, trace ends in `choose_use` |
| The other 27 rows | — | Same outcome and code, with no change in any detail or mismatch except the two below |
| `WS05-CMD-DMG-CONTROL` | `ENGINE_REJECTED`, `UNSUPPORTED_CONTROL_DIVERGENCE` (at restoration) | Same code, now at plan parsing |
| `CARD_10` (commander on the stack) | `ENGINE_REJECTED`, `UNSUPPORTED_ZONE … requests stack` | `ENGINE_REJECTED`, `UNSUPPORTED_COMMANDER_ZONE … requests stack` |

The state digests change, by design:

- **Constructed-state digests** change for every row that constructs, because the readback now carries each commander's zone.
- **Requested-state digests** change for the rows that request a battlefield commander:
  - `WS05-CMD-ELIM-4`;
  - `WS05-CMD-DMG-SAME-21`;
  - `MICRO_COSTS`, `CARD_03`, `CARD_04`.

The historical sealed probe artifacts keep their digests.

**Executed obligations, red before and green after:**

- `XmagePb03Tier2CmdZoneTest`, 8 rows. For each row:
  - cast the real cause, answering targets, mode and payment from the engine's offers;
  - answer the owner's zone choice with the `decision_script` boolean, from the engine-offered options only;
  - assert the terminal zone of the genuine commander: the command zone for yes, the cause's destination for no;
  - check that the game reaches cleanup without asking again.
- `XmageMidgameCausalTest`, the same 8 rows on the production JSONL lane. The choice is offered to seat 0 (the owner) and names the genuine commander's id. It is answered once and never asked again.
- `XmagePb03Tier1RowsTest.elim4TwentyOneCommanderDamageEliminatesAndCleansUp`. The genuine Isamaru attacks unblocked, which gives:
  - `commander_damage_total:P2:21` on the native ledger (19 restored + 2 dealt);
  - `player_loses:P2` through the engine's SBA (CR 704.6c);
  - P2 leaves the game;
  - `obj:p2-owned` leaves the game (CR 800.4a).
- `XmageNativeStateRestorationTest.genuineCommanderIsRestoredOnTheBattlefield`. The permanent is in the engine's commander set, and there is no second copy. A repeated completion is idempotent, and a command-zone request does not match the board.
- `commanderOutsideTheCommandZoneFailsClosedWhenUnbound` covers every rejection code above.
- `XmageCommanderDamageRestorationTest`: SAME-21's battlefield Isamaru now carries the genuine commander identity.
- Full bridge suite: 822 tests, 0 failures, checkstyle clean.

## Not done here

- **FULL107 re-evaluation.** The current-boundary artifacts are not rewritten. A successor current-boundary run on `9375f35a` is a Coordinator gate.
- **Decision family mismatch.** The frozen `decision_script` names the family `choice` for graveyard/exile and `replacement_effect` for hand/library. XMage asks all four as `choose_use`: the SBA choice and the replacement choice share one engine prompt. A runner that matches the family literally will need that mapping. This is measured here, not decided.
- **Control divergence and tapped commanders** stay unsupported: `WS05-CMD-DMG-CONTROL` needs a resolved control-change effect, not a placement.
- **A commander on the stack** (`CARD_10`) needs a causal commander cast from the command zone.
