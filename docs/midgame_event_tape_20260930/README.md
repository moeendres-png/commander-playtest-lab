# Midgame lane: public semantic event tape and one-shot arrival completion (2026-09-30)

Claude Opus 5.5. Lab main `c7f420fb`, live XMage pin `9375f35a`.

## Why

The current-boundary runner credits no mid-game row. Every row that needs a constructed starting state is classified `BLOCKED`: "no current-boundary execution seam … closing them requires Lab execution work". The midgame lane now constructs many of those states exactly, but a runner that executes their obligations also has to **verify** them. A row's `required_events` (`damage:P2:2`, `creature_enters:…`, `player_loses:P2`, …) are engine events. Until now the lane exposed only zone counts and an arrival readback (`event_log_supported=false`), so no obligation was verifiable from engine facts.

## What

**`XmagePublicEventWatcher`** is a native XMage watcher, registered by the restoration right after placement. It records the engine's own `GameEvent`s of a bounded set of types:

- zone changes;
- spell casts, counters and copies;
- triggered abilities;
- player and permanent damage, prevented damage;
- life gained and lost;
- loss, win and draw;
- declared attackers and blockers;
- tokens and counters;
- destruction and sacrifice;
- control changes;
- coin flips, extra turns, turn starts and shuffles.

Its list is part of the game state, so an engine rollback (for example an aborted cast) rolls the tape back with it.

**`get_midgame_events {after_offset}`** returns the tape after an offset:

- Players are named by requested-state seat (`P1..PN`).
- Objects are named by the semantic id the restoration placed them under.
- Names are included only for public identities.
- **No native id is ever emitted.**

The capability manifest now reports `event_log_supported=true` with `event_log_scope=public_semantic_event_tape`.

**Hidden information:**

- A zone change whose origin and destination are both hidden (a draw, a card put into a library) records owner and zones only. It carries no name and no object.
- Any other event names only objects that are in a public zone at the event.

The opening hands are drawn inside `GameImpl.init`, which fires no watched events, so the tape begins with the running game.

**Example** (`CARD_24` on the lane after arrival: P1 casts the recorded Grizzly Bears, and Warstorm Surge targets P2):

```
ZONE_CHANGE        HAND -> STACK        obj:card24-enter  (Grizzly Bears)   P1
SPELL_CAST         source obj:card24-enter                                    P1
ZONE_CHANGE        STACK -> BATTLEFIELD obj:card24-enter                      P1
TRIGGERED_ABILITY  source obj:card_24-subject (Warstorm Surge)                P1
LOST_LIFE          P2  2   source obj:card_24-subject
DAMAGED_PLAYER     P2  2   source obj:card24-enter  combat=false
```

That is the row's `creature_enters`, `Warstorm_trigger` and `entering_creature_damage:P2:2`, each as an engine fact.

## Hardening: arrival completion is one-shot

`complete_midgame_arrival` is queried repeatedly: at every arrival readback, and by the causal route before the stack. Before this change, every call re-applied the commander cast counts and commander damage through `restoreStateForGameLoad`. A completion query after a real commander cast would therefore have reset the count (3 back to the restored 2), and so the next tax. `restoreAfterArrival` now runs once, and later calls are pure queries.

The single-use guards that F-38 (placement) and F-40 (starting life) needed become redundant and are removed.

## Evidence

- `XmageMidgameCausalTest.thePublicEventTapeRecordsTheCausalRouteWithoutHiddenIdentities`, on the production JSONL lane (WS05-CMD-ZONE-GY-NO), asserts:
  - Doom Blade's cast by P2, the commander's destruction and its move to the graveyard, all by semantic id;
  - the turn draw is anonymous;
  - no native id anywhere in the tape;
  - an out-of-range offset fails closed.
- `XmageFullGameTaxExecutionTest.ws05CmdTax2CastsCommanderWithTax` checks that a repeated completion after the real cast keeps the cast count at 3.
- Python: `MidgameLaneClient.events` and its fail-closed path.
- Bridge suite 836/0/1, checkstyle clean.

## Next

A runner execution path for rows that the lane constructs exactly by placement. It executes the scripted decisions and verifies each `required_events` token against this tape. Causal-route rows stay `GENUINE_CAUSAL_DEVIATION`; whether they earn credit is a Coordinator ruling.
