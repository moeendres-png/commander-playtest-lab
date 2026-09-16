# U5-B Card-Driven Multi_Amount: CLOSED (PASS)

## Claim

A real card/effect whose Rules-Core path produces the joint bounded
integer-vector decision: one semantic pilot decision (single vector, not
sequential legs), native `isGoodValues` acceptance, game advancement.

## Evidence (DIRECTLY_VERIFIED)

Run `runs/u5/U5_MULTI_GEAR_2P.json` (2P Omnath/Forest symmetric
singleton-legal decks, fresh process, production lane + spotlight):

- Engine offered `Verdurous Gearhulk` (distribute four +1/+1 counters);
  pilot selected; engine consumed (arrival, combat, damage observed).
- Three native joint frames (offsets 342/446/554), each a SINGLE parked
  frame: legs `[{min: 0, max: 4}]`, total band `[1, 4]`, zero options.
- Pilot submitted ONE semantic vector `[4]` per frame (single-frame proof:
  frames served whole; no sequential legs).
- Native `isGoodValues` gate accepted (no failure, no rejection); game
  advanced 250+ decisions past the first frame; combat damage progressed
  (life moved to 18).

Negative screening (documented non-fires): Travel Preparations, Common
Bond, Hunger of the Howlpack get selected and consumed with NO joint
frame (their impls use sequential targets, not the joint path). The joint
path is proven by Gearhulk, not assumed from card text.

## Machine companion

`U5_MULTI_AMOUNT_CARD_DRIVEN.json` (this file's table is the summary).
