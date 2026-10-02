# CARD_16 (Psychosis Crawler): construction-vehicle obligation erratum

Status: **ADJUDICATED**. Recorded in `FULL107_SUCCESSOR_CONTRACT_v1_0_18.json` as an
`ACTUAL_CARD_OBLIGATION_ERRATUM`. `PRODUCTION_PROVIDER = NOT_SELECTED`,
`ARCHITECTURE_FREEZE = NOT_CLAIMED`. CARD_16 lies outside the 107-row provider
denominator, which is unchanged.

Adjudicated by the Claude campaign session as sole project executor and temporary
technical Coordinator (owner instruction, 2026-10-02). A newer owner or Coordinator
ruling supersedes it.

## The predecessor obligation

The checkpoint is P1's turn-1 precombat main phase, with Divination on the stack and
Psychosis Crawler on P1's battlefield. The predecessor requires:

1. "P1 hand size=5 and Crawler is 5/5 absent other modifiers."
2. "P2/P3/P4 are each at 18 life."

Obligation digest: `bda1a2e3…f764`.

The five-card hand assumes that P1 holds exactly the record's three named Mountains
before Divination draws two cards. The 18 life assumes the opponents are still at their
starting 20 at the checkpoint.

## Why it is unreachable

The construction vehicle plays the real start-of-game procedure and the real turns up
to the checkpoint. On its turn-1 main phase P1 therefore holds three things:

- the opening seven (CR 103.5);
- the turn-1 draw, which no player skips in a multiplayer game (CR 103.8c);
- the named Mountains.

A smaller hand is not reachable. It would need either of two routes:

- a Lab-side hand mutation, which SLOT-04 L7 forbids;
- an engine game-load seam that moves cards out of a hand. Neither candidate has one:
  XMage's RG-06A seam `Library.restoreOrderForGameLoad` only reorders cards already
  in the library and "never moves cards between zones".

The Crawler is on the battlefield from the moment the first turn begins (CR 103.6a; see
`PLACEMENT_POINT_ADJUDICATION.md`), so it sees P1's turn-1 draw. Each opponent's starting
life of 20 is set before the draw step, so the opponents are at 19 at the checkpoint, not
20. No legal history puts the Crawler on the battlefield on P1's turn-1 main phase
without it seeing that draw.

With the predecessor obligation, the 1.0.18 scenario erratum declared a complete
three-card hand. That hand always failed closed with `INCOMPLETE_LIBRARY_ORDER`:
101 library cards requested against 93 present, because eight drawn template cards
stayed in hand.

## The correction

- **Hand and library.** P1's checkpoint hand is declared as its natural turn-1 hand:
  the opening seven and the turn-1 draw as template Mountains (`template_count: 8`,
  exactly as CARD_07 declares), plus the three named Mountains, for eleven cards.
  The library is declared complete: the two named cards on top of the 91 remaining
  template Mountains.
- **Opponents' life.** The checkpoint life that the turn-1 draw's trigger caused is
  declared: 19 each, with starting life 20.
- **Postconditions.** Both are restated at that checkpoint:
  - "P1 hand size=13 and Crawler is 13/13 absent other modifiers."
  - "P2/P3/P4 are each at 17 life."
- **Unchanged.** The required events (two draws, two Crawler triggers), the objects,
  the stack, the temporal state, and the decision script. The script holds the
  CR 603.3b ordering of the two simultaneous triggers.

The Rules content of the obligation is preserved:

- the Crawler's power and toughness equal P1's hand size;
- each of Divination's two draws triggers it once;
- each opponent loses 1 life per draw;
- P1 orders the two simultaneous triggers.

Only the state at which these are measured changes. The new check
is an exact hand count (`hand_count`), not the former minimum (`hand_count_min`).

## Lineage

- The predecessor obligation digest and postconditions are preserved in the erratum's
  details and under `historical_digests`.
- The obligation digest changes explicitly (`CHANGED_OBLIGATION_ERRATUM`).
- No predecessor evidence transfers.
- The row needs fresh direct evidence under the corrected record.
