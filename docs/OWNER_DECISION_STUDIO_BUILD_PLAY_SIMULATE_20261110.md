# Owner decision: Commander Studio — Build + Play + Simulate as one product (2026-11-10)

**Decision source:** direct Owner instructions on 2026-11-10 (C087.2 brief and the two
follow-up answers of the same day). This is governance only: no code, engine pin, sealed
evidence, canonical deck, inventory or pilot behavior changes with this document.

## Binding product scope

- The project is one connected, free, local Commander application with three areas that share
  the same decks, card data, rules and game states:
  - **BUILD** (highest product priority): a deck-building tool that is as good as it can be.
    It works on the Owner's own physical collection first; a deck is one legal commander plus
    cards inside its color identity, 100 cards in total.
  - **PLAY**: one human chooses a deck and plays complete Commander games against a chosen
    number of AI seats (2–6 seats in total, default 4).
  - **SIMULATE**: automated games between AI seats, whose game logs and win rates are analysed.
- **Form:** a local web application with a starter (local Python service, the pinned XMage
  bridge, browser front end). No hosted service, no paid service.
- **Order of work:** two tracks at once — the BUILD foundation (data contract, deck revisions,
  collection) and a PLAY proof (read-only live view of a real XMage game, then the human seat).

## Play rules

- The human seat has **no time limit** for turns or decisions.
- While AI seats act, the game runs on in a flow whose speed the human can set, until the
  human has a decision again.
- The human chooses only among the options the Rules Core offers. No sandbox table, no free
  undo.
- Each AI seat has a **style setting** (from aggressive to controlling). The setting shapes how
  a seat plays, never how well: every seat plays to win.

## Simulation and pilot doctrine

- The goal is AI seats that play as strongly as possible in general: take the best available
  option, or wait when waiting is better, as a good human player would, including greedy
  choices.
- A seat should understand its deck and may get a **game plan** for it before the game. The
  plan informs choices; it never ranks above winning the game.
- **New series of small per-decision pilot measurements and decision-explanation work are
  frozen.** Merged pilot code, its tests and its measurements stay. Open pilot pull requests
  are decided by the Owner one by one.
- The product of a simulated game is a chronological log of what was actually played, plus
  win rates over many games, always labelled as simulated with seed, policy and engine
  version. Explaining each internal pilot decision is not a product goal.

## Card images and data

- **Complete card images are shown in all tools.** For this purpose the Owner allows card
  names of his collection and decks to be sent to a free public card-image source. Images are
  cached locally. This is the only exception to the rule that deck, collection and ownership
  data go to no external service; quantities, storage locations, reservations, notes, deck
  structure and game states stay local.
- Studio data (collection, selections, deck revisions, saved games) lives in the Owner data
  folder outside the Git tree (`COMMANDER_LAB_OWNER_DATA`), never in this repository.
- Every value shown carries its origin: original source, normalized source, derived
  descriptive figure, heuristic model, simulated result or unknown. Missing data is unknown,
  never zero.

## Later, not now

- A tool for cards the Owner does **not** own: trying them in a deck with the simulator and
  planning purchases. This lifts the earlier "no shopping function" line of the C087.2 brief
  for a later stage only; nothing of it is built in the first stages, and no paid service is
  used.
- Other commanders from the collection; five and six seats after their own qualification;
  hot-seat or remote multiplayer.

## Unchanged

Architecture Freeze (CLAIMED), XMage as the sole Rules authority, the live engine pin and all
sealed qualification records, the six-player maximum
(`docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`), Chulane as the only active Owner deck
(`docs/OWNER_DECK_FOCUS_CURRENT.md`), no paid services, branch protection and merge rules.
XMage's own AI players are still not used as seats.

## Steps that need their own Owner go

- Any change to the Java bridge (for example a configurable decision timeout for the human
  seat, or an engine look-ahead interface for stronger pilots), every fork push, repin and new
  qualification epoch.
- Five- and six-seat release, publication, licence, repository visibility.
