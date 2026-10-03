# Restoration placement point: decision request (AF07, #453)

Status: ADJUDICATED 2026-10-02, Option 2 (see `PLACEMENT_POINT_ADJUDICATION.md`). The question below is kept as it was asked.
`PRODUCTION_PROVIDER = NOT_SELECTED`, `ARCHITECTURE_FREEZE = NOT_CLAIMED`.

## The question

The XMage restoration puts requested battlefield permanents onto the battlefield
**before game start** (`XmageNativeStateRestoration.applyPreStart`, the engine's
setup primitive). The arrival then plays the real start-of-game procedure
(opening hands, mulligans) and the real turns up to the checkpoint. The placed
permanents therefore observe that whole history.

CR 103 has no permanents on the battlefield during the start-of-game procedure,
so a permanent that reacts to the opening-hand draws produces a history no legal
game can show. Should the vehicle keep that history, or should restored
permanents enter later?

## Evidence

| Row | Pre-start placement (current) | Effect |
| --- | --- | --- |
| CARD_07 (Narset, Parter of Veils) | Narset limits each opponent to one draw a turn, so the opponents' opening hands hold 1 card each (libraries 98). | The SLOT-04 complete libraries fail closed: `INCOMPLETE_LIBRARY_ORDER`. |
| CARD_16 (Psychosis Crawler) | The Crawler triggers on P1's 7 opening draws and the turn-1 draw. | The opponents lose 8 life before the checkpoint. |
| MICRO_CONTINUOUS_EFFECTS (denominator) | The same Crawler start triggers. | The opponents are at 32 against a requested 40. `XmagePb03Tier1RowsTest` asserts 32 as "genuine start triggers". |

The causal-stack route used to hide the CARD_07 case. It built its restoration
with an empty lossless plan, so the record's complete libraries and hands were
never applied or verified, and the construction still read EXACT. That
soundness defect is fixed on this branch; CARD_07's earlier pass is withdrawn.

## Options

1. **Keep pre-start placement** (status quo). Arrival history, including the
   start-of-game procedure, is treated as genuine. CARD_07 stays fail-closed.
   MICRO_CONTINUOUS_EFFECTS keeps its life mismatch.
2. **Place after the start-of-game procedure** (at turn 1's first event). The
   opening hands are clean. Turn history up to the checkpoint stays as today:
   combat checkpoints and multi-turn upkeep arrivals keep their attackers and
   triggers. The Crawler test changes from 32 to 39: the turn-1 draw still
   triggers.
3. **Place at the start of the checkpoint step** (prototype:
   `checkpoint_placement_prototype.patch`). Restored permanents observe nothing
   before the checkpoint step.
   - Local result: CARD_07 DIRECT_PASS with the lossless checks run (hand 4,
     library 1, library objects 2, no mismatch), CARD_16 construction gets past
     the trigger issue, and the 107-row midgame and AF05 hidden regressions are
     unchanged.
   - It also breaks 17 bridge tests whose checkpoints need permanents earlier:
     combat checkpoints after declare attackers, multi-turn upkeep arrivals, and
     the "start triggers" assertions.

Every option keeps face-down permanents pre-start: they turn face down before
the public tape exists (SLOT-04). The prototype also keeps double-faced or
multi-part cards pre-start, where placement could register new watchers.

## What follows from each option

- Option 1: CARD_07 is terminally `FAIL_CLOSED_CONSTRUCTION` on XMage.
- Option 2 or 3: CARD_07 requalifies. The changed tests and any denominator
  rows whose evidence depends on start-of-game triggers must be requalified in
  the same epoch.

CARD_16 is blocked independently of this decision. Its hand of exactly three
cards in P1's own main phase is below the natural hand (opening seven plus the
first draw). No native hand-composition game-load API exists (RG-06A restores
library order only), and SLOT-04 L7 forbids a Lab-side hand mutation.
