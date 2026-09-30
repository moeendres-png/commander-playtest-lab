# F-35: offered options whose execution failed and aborted the game (bridge)

Status: FIXED in the full-game lane (this PR). Found by the full-game replay harness with real decks. Claude Opus 5.5, 2026-09-30.

- **Classification:** `BRIDGE_SURFACE_DEFECT`, a decision-option legality defect in `XmageFullGamePlayer.chooseMode`, `priority` and `playMana`.
- **Symptom:** a real 4P game (RogShai / Kaervek) aborted with `XMAGE_ACTION_EXECUTION_FAILED: priority cast failed`. A 6P game aborted with `... mana activation failed`. Both aborts were deterministic.

## Defects

1. **Illegal modes (CR 700.2a).** "If one of the modes would be illegal (due to an inability to choose legal targets …), that mode can't be chosen."
   - The mode decision offered every mode and only flagged `mode_targets_available`.
   - Example: Abrade with a creature but no artifact on the battlefield offered "destroy target artifact". Choosing it failed the cast, and the lane aborted the game.
   - The existing no-viable-mode rewind only covered the case where *every* mode lacked targets.
2. **Unaffordable mana abilities.** XMage's playable and usable lists check only `canActivate` for mana abilities, not the ability's own mana cost.
   - Example: Rakdos Signet "{1}, {T}: Add {B}{R}" was offered while its {1} could no longer be paid. Its activation failed, and the lane aborted the game.

## Fix

1. When at least one mode is choosable, only choosable modes are offered. When none is, all modes stay listed for the unchanged no-viable-mode rewind.
2. A mana ability with a mana cost of its own is offered, both at priority and during payment, only if the engine's own `canPayMinimumManaCost` (available mana, including the pool) says it can be paid. That is the same test `canPlay` applies to every other ability.

## Evidence

- `XmageFullGameIllegalOptionTest`, 2P and 4P, for Abrade and Rakdos Signet: red 4/4 on the unfixed lane, green 4/4 with the fix.
- `XmageFullGameReplayTwinTest` covers six real-deck games of up to 3000 decisions at 3–6P. Before the fix, two of them aborted. After the fix none aborts, and one ends in a regular game over.
