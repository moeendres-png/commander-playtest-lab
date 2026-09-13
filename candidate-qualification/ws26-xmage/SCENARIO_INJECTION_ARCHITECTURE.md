# WS-26 XMage Scenario Injection Architecture

## Boundary

`XmageWs26QualificationMain` is a qualification-only XMage provider process. It is deliberately separate from the WS-22 production-shaped `full-game` bridge so WS-22 behavior cannot be silently changed by fixture setup.

Commander Lab sends a provider-neutral semantic scenario. The provider validates identity and shape, resolves declared card names against the already XMage-validated Commander decks, and invokes XMage-native `Game.cheat(...)` plus `GameOptions.testMode/skipInitShuffling`. Subsequent mulligan, turn, priority, stack, trigger, replacement, SBA, combat and card behavior is executed by XMage.

The adapter does **not** compute legal targets, layers, state-based actions, replacement outcomes, mana legality or legal actions.

## Supported semantic setup dimensions in this viability slice

- exact 2-5 seats already created through the real Commander game;
- exact starting seat;
- positive life totals;
- commander identity validated against the deck XMage already accepted;
- hand;
- deterministic top-to-bottom library content/order;
- graveyard;
- face-up exile;
- battlefield permanents owned and controlled by the same declared player;
- battlefield tapped state;
- exact card main face;
- explicit Rules RNG seed.

## Explicit fail-closed dimensions

The qualification surface rejects rather than approximates:

- arbitrary control assignment;
- counters;
- attachments;
- face-down injection;
- raw stack-object injection;
- direct priority-holder mutation;
- direct turn/phase/step mutation;
- direct mana-pool mutation;
- external KnowledgeLedger grants;
- raw/native object IDs.

A later workstream may add one of these only through a native XMage mechanism with its own validation and runtime evidence.

## Validation

Validation is two phase. Structural/card-reference preflight completes before any zone mutation. Native post-construction validation then checks life, zone, ownership, battlefield controller/tapped state, and synchronizes every actor view through the single WS-22 `XmageKnowledgeLedger`. Failure aborts the scenario; there is no repair path.

## Replay

WS-26 carries a reproducible source patch to the pinned XMage `RandomUtil`. The patch replaces the single `Random` instance with a behavior-equivalent subclass that records every `Random.next(bits)` draw. Because callers of `RandomUtil.getRandom()` and wrapper methods share that instance, seeded rules draws are attributable without mixing Commander Lab pilot RNG.

DecisionTape and semantic checkpoints are recorded at external-decision boundaries. EventTape is a semantic boundary tape of state-hash changes caused by accepted decisions; it is not represented as a claim that every internal XMage `GameEvent` has been serialized. Clean-process replay requires the same patched XMage identity, semantic scenario, Rules RNG seed and semantic decisions and compares RNG, decisions, events, checkpoints and final semantic state.
