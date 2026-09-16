# U5-C Card-Driven Target_Amount: CLOSED (PASS)

## Claim

Structured target_amount path through an actual card: target selection
plus its authoritative numeric companion, natively emitted, pilot-answered,
engine-consumed, game advanced.

## Evidence (DIRECTLY_VERIFIED)

Run `runs/u5/U5_TARGET_ARC_2P.json` (2P Rograkh/Mountain symmetric
singleton-legal decks with 1 Arc Lightning, fresh process, production
lane + spotlight; reproduced across 4/4 calibration seeds):

- Engine offered `Arc Lightning` (deal 3 divided as you choose); pilot
  selected at offset 134; engine consumed (targets at 135/136 window).
- Native `target_amount` frames: `(135, min 1, max 3, choice 2)` then
  companion `(136, min 1, max 1, choice 1)` — target selection plus the
  authoritative numeric companion, exactly the WS229 companion shape,
  now firing from a real card in a live game.
- No failure; game advanced 350+ decisions; damage progressed.

The WS229 pinned blocker (unstarted-game `hasPlayerInRange`) is closed by
construction: the effect fires inside a started game with range-gated
targets, which is the only lawful way to reach the callback.

Screened non-vehicles (documented): Fireball and Fall of the Titans
divide EVENLY (automatic, no discretionary divide call) and additionally
hit the 5-6-mana last-tap payment wall in-test; they are not
target_amount vehicles in this lane.

## Machine companion

`U5_TARGET_AMOUNT_CARD_DRIVEN.json` (this file's table is the summary).
