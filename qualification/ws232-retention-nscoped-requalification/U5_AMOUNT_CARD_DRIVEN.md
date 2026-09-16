# U5-A Card-Driven Amount: CLOSED (PASS)

## Claim

A real card/effect drives the native XMage amount callback through the
full path: actual card -> engine callback -> bridge -> Lab -> pilot ->
native submission -> observable game advancement.

## Evidence (DIRECTLY_VERIFIED)

Run `runs/u5/U5_AMOUNT_DAMNATIONS_2P.json` (2P Toshiro/Swamp symmetric
singleton-legal decks, fresh process, production lane + spotlight):

- Engine offered `Choice of Damnations` as a cast at offset 276; pilot
  selected among authorized options; engine consumed.
- Native `amount` frame at offset 277/292 with context
  `{numeric_min: 0, numeric_max: 2147483647}` (native span, O(1) range
  representation, no enumeration); pilot submitted lawful in-domain 4
  through the repaired WS229 scalar path; engine consumed.
- Observable advancement: game continued 300+ further decisions with no
  failure; seat-0 life 40 -> 36 (exactly the chosen 4: resolution life loss
  observed); terminal/budget state clean.

## Machine companion

`U5_AMOUNT_CARD_DRIVEN.json` (this file's table is the summary).
WS229's callback-level synthetic driver is superseded for the
card-driven half; it remains valid for the callback-traversal half.
