# F-30: priority hid activated abilities with identical rule text (bridge)

Status: FIXED in the full-game lane (this PR). Found by the full-game replay harness (`XmageFullGameReplayTwinTest`) with real decks. Claude Opus 5.5, 2026-09-30.

- **Classification:** `BRIDGE_SURFACE_DEFECT` in `XmageFullGamePlayer.priority` and `playMana`. It also affects semantic replay.
- **Source lock:** Lab main `23977253`, live XMage pin `f79e4168`.
- **Rules:** CR 117.1b / 602.2. Every activatable ability of every permanent is a separate legal action.

## Defect

The lane called `getPlayable(game, false)`. That is XMage's AI variant (`hideDuplicatedAbilities = true`), which drops activated abilities of **different** permanents when their rule text is equal. It keys them by `ability.toString()` in a `HashMap`.

- **Incomplete options.** A second copy of a creature, several tokens with the same ability (Treasures, for example), or two lands with "{T}: Add {U}." (Island, Prairie Stream): only one of each was ever offered at priority.
- **Nondeterministic options.** Which one survived depended on hash order. Identical replays of the same game with the same seed showed different option sets.

## Fix

Both call sites now use `getPlayable(game, false, Zone.ALL, false)`, which offers every object's ability. Option ids were already per object.

## Evidence

- `XmageFullGamePriorityCompletenessTest`, 2–4P: two Prodigal Pyromancers, Island and Prairie Stream.
  - Red 3/3 on the unfixed lane: only one Pyromancer was offered.
  - Green 3/3 with the fix.
- `XmageFullGameReplayTwinTest`: the 3P seed-1234 twin diverged before the fix, with one of Island / Prairie Stream randomly missing from priority. It replays identically after the fix.

## Impact and routing

- **Impact:** full-game-lane transcripts whose priority decisions involved duplicate-text abilities lacked legal options, and are not replay-stable on the old lane.
- **Generic Protocol-2 lane:** fixed as well, in a follow-up PR. `ExternalDecisionController` enumerates and `XmageActionExecutor` resolves through the same complete `getPlayable(..., false)` set. An unexpected player type fails closed.
  - `ExternalDecisionControllerCompletenessTest`: Prodigal Pyromancer and Prodigal Sorcerer. Red: only the Pyromancer was offered, because the Sorcerer's equal rule text was deduplicated. Green after the fix.
  - Both lanes now share one twin-stable ordering, `XmageStableOrder` (F-36).
