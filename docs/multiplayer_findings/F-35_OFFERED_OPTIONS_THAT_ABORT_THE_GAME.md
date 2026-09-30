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
   - Example: Rakdos Signet "{1}, {T}: Add {B}{R}" was offered while its {1} could no longer be paid. Its activation failed, and the lane aborted the game (6P).
   - Example: Study Hall "{1}, {T}: Add one mana of any color" was offered when only its own "{T}: Add {C}" could fund the {1}. A permanent can't tap twice, so the activation failed and the lane aborted the game (4P).

## Fix

1. When at least one mode is choosable, only choosable modes are offered. When none is, all modes stay listed for the unchanged no-viable-mode rewind.
2. A mana ability with a mana cost of its own is offered, both at priority and during payment, only if the engine's own `canPayMinimumManaCost` (available mana, including the pool) says it can be paid. That is the same test `canPlay` applies to every other ability.
   - For a {T} ability, the available mana is computed by the engine (`getManaAvailable`) in a playable-calculation copy of the game with the source permanent tapped. The ability therefore can't be funded by its own permanent's other {T} abilities.

## Evidence

- `XmageFullGameIllegalOptionTest`, 2P and 4P each:
  - Abrade and Rakdos Signet: red 4/4 on the unfixed lane, green 4/4 with the fix.
  - Study Hall: red 2/2 on the Signet-only fix, green 2/2 with the tap-aware check.
- `XmageFullGameReplayTwinTest` (four real decks, 3–6P, up to 3000 decisions):
  - Before the fixes, three games aborted: Abrade, Rakdos Signet, Study Hall.
  - After the fixes, none of the nine extended games aborts, and four end in a regular game over.
