# F-22: a battle keeps a protector who left the game

Status: REMEDIATION_CANDIDATE — Mage PR #25 / Lab successor repin. Tracker: #334. Found and proven by the multiplayer discovery lane (Claude Opus 5.5), 2026-09-29.


## Classification
`RULES_CORE_DEFECT`, XMage engine, state-based actions. **Multiplayer only:** in 2P, the protector leaving ends the game.

## Source lock
- Lab main `b31f144b5e1ae2d5e3203a2f1cc87797806cb736`.
- XMage pin `b19596980f2734496ea1896504253e1bdd2756dd` (not moved).
- Rule: battles/Sieges. A battle can be attacked by any player other than its protector. If a battle's protector is not an appropriate player (for example, has left the game), its controller chooses a new protector as a state-based action.
  - The CR rule numbers and verbatim text were **not re-read** (egress to the CR and Scryfall is blocked), so they are UNKNOWN here.

## Defect
- `GameImpl.checkStateBasedActions` (battle branch) re-chooses a protector only when `this.getPlayer(perm.getProtectorId()) == null`, or when the controller protects its own battle.
- A player who left the game is still returned by `getPlayer`, so the check never fires.
- The battle keeps the departed protector. `Combat.setDefenders` only offers battles protected by an opponent of the attacker (`ProtectedByOpponentPredicate`), so **nobody can attack the battle for the rest of the game**.

## Evidence
- Native, at the pin: `Mage.Tests` `org.mage.test.commander.multiplayer.BattleProtectorLeavesProbe4PTest`, on mage-fork branch `claude/mp-discovery-20260929`. Card: Invasion of Zendikar, 4P.
  - Control, protector D stays: C's Bears attacks the battle and its defense goes 3 → 1. **Pass.**
  - D (protector) concedes: the protector is still D. **Fail.**
  - D concedes, then C attacks the battle: defense stays 3, because the attack is impossible. **Fail.**
- Lab lane: `engine-bridge/.../XmageMultiplayerBattleTest`, 3–6P.
  - Enabled and green on the pin: the protector choice offers exactly P1's opponents; PN may attack the battle and its Bears deal 2; the protector is never offered the battle.
  - `@Disabled` F-22 expectation: when enabled it fails 4/4 at the pin, because the departed player is still the protector.

## Ownership / next step
- The fix belongs in `GameImpl` state-based actions: test `isInGame()` instead of `getPlayer(...) == null`, then `chooseProtector` among in-game opponents.
- `GameImpl` currently belongs to the XMage candidate-integration/repin lane, so this lane does **not** implement it. It is handed to that owner.
- Once a fix is admitted, enable the disabled Lab test.


## 2026-09-29 successor remediation
- Candidate engine: `4277b90b4ee49acd945e82335a9a04c4536f5340` (Mage PR #25).
- Commander Lab repin workstream: `xmage-f22-f23-successor-repin-20260929`.
- Runtime status remains UNKNOWN until exact-candidate and Lab CI complete; this note does not itself close F-22.
