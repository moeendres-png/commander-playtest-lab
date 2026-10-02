# Restoration placement point: adjudication (AF07, #453)

Status: **ADJUDICATED, Option 2** (restored permanents enter when the first turn begins).
Answers `PLACEMENT_POINT_DECISION_REQUEST.md`, which stays unchanged as the record
of the question. `PRODUCTION_PROVIDER = NOT_SELECTED`, `ARCHITECTURE_FREEZE = NOT_CLAIMED`.

Adjudicated by the Claude campaign session acting as the sole project executor and
temporary technical Coordinator (owner instruction, 2026-10-02). A newer direct owner
or Coordinator ruling supersedes this record.

## Question

Should the XMage restoration vehicle place requested battlefield permanents before
game start (status quo), after the start-of-game procedure, or at the checkpoint step?

## Rules basis

The question concerns the construction vehicle, not a card's behaviour. It still has
an official-rules answer, because the vehicle replays a real start-of-game procedure
and real arrival turns, and the history it produces must be one a legal game can show.

- **CR 103 (starting the game).** The players' decks become their libraries, they draw
  their opening hands and take mulligans (London mulligan, CR 103.5). No permanent
  exists on the battlefield during any of this.
- **CR 103.6 (opening-hand actions).** Once the mulligan process is complete, cards
  that allow a player to begin the game with them on the battlefield (for example
  Leylines) are put onto the battlefield (CR 103.6a). This is the **earliest** point
  at which any permanent can be on the battlefield in a legal game.
- **CR 103.8 (first turn).** The starting player then takes the first turn. In a
  multiplayer game other than Two-Headed Giant no player skips the draw of their
  first turn (CR 103.8c).

Both candidate engines implement this order. XMage's `GameImpl.init` (pinned
`37e4df6c`) shuffles, sets life, draws the opening hands, runs the mulligan phase,
then performs the opening-hand actions before the first `Turn.play`.

Official-text receipt: **PENDING_EXTERNAL_FETCH**. `media.wizards.com`,
`magic.wizards.com`, `api.scryfall.com` and the rules mirrors are denied by this
runner's egress policy (the same limitation recorded for the CARD_06/CARD_07 Oracle
receipts). The citation follows the project's recorded Comprehensive Rules authority
(effective 2026-08-07, `candidate-qualification/ws47-successor-v1.0.5/WS47_CURRENT_RULES_AUTHORITY.md`).
The receipt must be attached when a runner with access is available. Evidence class
of the rules citation until then: `CODE_DERIVED` plus rule-number citation, not
`EXTERNALLY_RULE_VALIDATED`.

## Ruling

1. **Option 1 (pre-start placement) is rejected.** A permanent on the battlefield
   during CR 103.1-103.5 is a history no legal game shows. The defect is in the
   vehicle, not in the records:
   - a restored Narset, Parter of Veils cut the opponents' opening hands to one card;
   - a restored Psychosis Crawler triggered on all seven opening draws.
2. **Option 2 is adopted.** Restored face-up permanents enter at the first turn's
   `BEGIN_TURN` event. That is the vehicle's equivalent of CR 103.6a: after the
   mulligans, before the first turn's beginning phase. The engine fires
   `BEGIN_TURN` before `Battlefield.beginningOfTurn`, so the active player's
   restored permanents are controlled continuously since that turn began, as a
   Leyline's would be.
3. **Option 3 (checkpoint-step placement) is rejected.** The vehicle does play the
   real turns up to the checkpoint. Multi-turn arrivals, combat checkpoints and
   upkeep triggers legitimately depend on the restored permanents existing during
   those turns. Hiding the permanents until the checkpoint step would replace one
   impossible history with another one, in which permanents appear mid-game
   without an event.

- **Battlefield commanders.** A commander requested on the battlefield is the
  genuine commander. Game start puts it into the command zone (CR 903.6). It
  leaves the command zone at the same `BEGIN_TURN` point, in the same way as every
  other restored permanent. Before this ruling it was moved at the checkpoint
  through the engine's setup primitive, which also cleared summoning sickness, so
  its control history was set rather than derived. Its requested
  `controlled_since_turn_began` is now verified like any permanent's.

Unchanged by this ruling:

- **Face-down objects.** They are still turned face down before game start (SLOT-04),
  so no observation ever shows them face up. They are hidden objects, not observers
  of the opening draws.
- **Cards whose battlefield permanent is another part or face.** These stay setup
  placements. Placing one from inside the engine's watcher iteration would register
  new watchers during that iteration. They remain an explicit, bounded residual of
  this vehicle.
- **Hand, graveyard, exile and library objects.** Unchanged. The start-of-game draws
  come from the library, and requested libraries are applied at the checkpoint.

## Consequences

- **Requalification.** Every row whose arrival history the change affects must be
  requalified in the same epoch: the AF07 corpus, the FULL107 midgame rows, the AF05
  knowledge-projection rows, and the bridge Java suite.
- **`XmagePb03Tier1RowsTest` (MICRO_CONTINUOUS_EFFECTS vehicle).** The Crawler's
  start-trigger expectation changes from 32 to 39 life per opponent. Only the
  turn-1 draw triggers; that draw is a real draw on a turn on which the Crawler is
  on the battlefield (CR 103.8c).
- **CARD_07 and CARD_16** are re-measured under the new placement. CARD_07 passes
  with its lossless checks run. CARD_16's hand-composition blocker is independent
  of this ruling; it is closed by `CARD16_OBLIGATION_ERRATUM.md`.
- **F-40 starting life.** A recorded starting life is setup (CR 103.4). It is set at
  the same first-turn setup point, while the player is still at the table's starting
  life. A current life the arrival caused (a restored Crawler seeing the turn-1 draw)
  is compared, never set.
- **Summoning sickness (CR 302.6).** Restored permanents enter as new objects. The
  engine's own beginning-of-turn step marks the turn-1 active player's permanents as
  controlled since the turn began. Every other player's stay summoning sick until that
  player's turn begins. A record's `controlled_since_turn_began` is verified at the
  checkpoint and never set.
- **MICRO_COSTS** (provider denominator). This verification exposed a fixture
  defect: on P2's turn 1, the record requested a control history for the
  permanents of P1, P3 and P4 that no game can reach. It is corrected by
  `MICRO_COSTS_CONTROL_HISTORY_ERRATUM.md`.
- **Public tape.** The setup placement is muted on the public event tape. For example,
  an entering planeswalker's loyalty counters are setup, as they were when placement
  preceded the tape.
- **Bounded residual.** Face-down and multi-part setup placements are still made
  before game start through the engine's setup primitive, which removes summoning
  sickness. A record that requests `controlled_since_turn_began` for such an object
  is verified and fails closed on a mismatch.

Implementation: `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFirstTurnSetupWatcher.java`
and `XmageNativeStateRestoration.applyPreStart`. A deferred permanent still outside
the game at the checkpoint fails closed with `FIRST_TURN_PLACEMENT_MISSED`.
