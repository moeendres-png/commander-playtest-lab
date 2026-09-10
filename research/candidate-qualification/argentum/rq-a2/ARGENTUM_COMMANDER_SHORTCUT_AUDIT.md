# RQ-A2 — Commander Shortcut Audit (forced-divert reachability)

Required output: `FORCED_COMMANDER_SHORTCUT_PRODUCTION_REACHABLE = NO`

## Flag mechanics (CODE_DERIVED)

- `Format.alwaysDivertToCommand` (default `false`; `mtg-sdk/.../sdk/core/Format.kt:28,87,175`).
- When true, `CommanderZoneChoiceCheck` skips the CR 903.9a yes/no prompt
  (`rules-engine/.../mechanics/sba/permanent/CommanderZoneChoiceCheck.kt:42-44`) and
  `ZoneMovementUtils` diverts synchronously (`handlers/effects/ZoneMovementUtils.kt:758-777`).
- KDoc purpose: "AI/headless tooling can flip this on to skip the prompt" (`Format.kt:76-79`).

## Reachability review (DIRECTLY_VERIFIED by search at the lock)

- `alwaysDivertToCommand = true` appears NOWHERE outside `rules-engine/src/test`
  (3 test files only). No production, AI, gym, gym-server, gym-trainer, or game-server
  main-source setter exists.
- Production construction chain: lobby preset selection (`CommanderPreset` BRAWL/COMMANDER/POD
  via `LobbyHandler.kt:2630`, none carrying the flag) → `toFormat()` (default false) →
  `FreeForAllHandler.kt:98,119` copies the flag (false) → `GameConfig` → engine.
  No wire/client input sets it.
- Gym/AI layers reference the flag zero times.

## Runtime behavior (DIRECTLY_VERIFIED)

- Default path (`false`): RQ-A2 P11 probe raises the 903.9a yes/no
  (`CommanderZoneChoice@...:Put Test Hasty Prospector into the command zone instead...`),
  YES diverts, tax (+2) charged on recast (3 Mountains tapped), commander damage tracked (2).
- Forced path (`true`): covered by candidate's own `CommanderZoneChoiceCheckTest` and
  `CommanderZoneRedirectTest` (bypass semantics asserted there; not re-run here).

## Verdict

`FORCED_COMMANDER_SHORTCUT_PRODUCTION_REACHABLE = NO`. The shortcut is test-only surface
today. Integration constraint carried forward: any CSN provider topology that enables the
flag on a production path would bypass a discretionary Commander replacement/zone choice
and must be re-audited (topology exclusion, not engine repair).
