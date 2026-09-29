# F-25: per-defender attack limits were offered past the limit (bridge)

Status: FIXED in this PR. Tracker: #345. Found by the multiplayer discovery lane (Claude Opus 5.5), 2026-09-29.

- **Classification:** `BRIDGE_SURFACE_DEFECT` in the XMage full-game lane, `XmageFullGamePlayer.selectAttackers`. The Rules Core is correct (native probe green).
- **Source lock:** Lab main `f7bbeb93`, live XMage pin `f79e4168`.
- **Defect:** with Crawlspace ("No more than two creatures can attack you each combat"), the per-creature `declare_attacker` decision still offered the limited player after two attackers had been declared against that player.
  - The engine (`Combat.canDefenderBeAttacked`) then refused the attacker, and `PlayerImpl.declareAttacker` undid it silently.
  - The pilot's choice was dropped without any decision, and the engine chose which creature did not attack.
- **Fix:** a defending player whose engine limit `Player.getMaxAttackedBy()` is already reached is no longer offered. The count comes from the creatures already declared against that player in the engine's combat state.
  - Global limits such as Silent Arbiter go through `canAttack`, which the lane already checks per attacker.
- **Evidence:** `XmageMultiplayerAttackLimitTest`, 3–6P.
  - Red 4/4 before the fix, green 4/4 after.
  - Full bridge suite with the fix: 579 run, 0 failures.
