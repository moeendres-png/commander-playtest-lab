# WS-38 Forge Core Patch Specification (NOT IMPLEMENTED)

Target baseline: `Card-Forge/forge@ef4c834dbbca21a099ae751fb52b2326abdf1e02`

This is an isolated design/diff specification stored in Commander Lab. It is **not** a compiled Forge patch.

## Minimal change set

### 1. Add core transaction/validator under `forge-game/.../forge/game/combat/`

Add a `CombatDamageDecision` (or equivalent) and `CombatDamageAssignmentValidator`.

The transaction must own:
- assigning player;
- damage-step identity;
- eligible source set;
- source damage;
- legal recipients;
- partial proposed amounts;
- same-step cross-source assigned amounts;
- trample/deathtouch/trample-over-planeswalker/banding/legacy-order constraints;
- final CR 510.1e validation.

### 2. Change `PlayerController`

Replace or supplement the raw-map callback:

```diff
- Map<Card,Integer> assignCombatDamage(Card source, CardCollectionView blockers,
-     CardCollectionView remaining, int damage, GameEntity defender, boolean overrideOrder);
+ CombatDamageSelection chooseCombatDamage(CombatDamageDecisionView decision);
```

`CombatDamageSelection` must contain only opaque decision/source/recipient IDs and a choice already authorized by the core decision state. It must not carry rule-derived lethal values supplied by the controller.

### 3. Change `Combat.assignAttackersDamage` / `assignBlockersDamage`

```diff
- Map<Card,Integer> map = assigningPlayer.getController().assignCombatDamage(...);
- for (Entry<Card,Integer> e : map.entrySet()) {
-     ... mutate assignedDamage/damageMap ...
- }
+ CombatDamageDecision tx = CombatDamageDecision.from(this, assigningPlayer, firstStrikeDamage);
+ while (!tx.complete()) {
+     if (tx.currentChoiceIsForced()) tx = tx.applyForcedChoice();
+     else tx = tx.apply(assigningPlayer.getController().chooseCombatDamage(tx.toView()));
+ }
+ CombatDamageAssignment assignment = validator.validateOrThrow(tx);
+ commitValidatedAssignment(assignment);
```

The real implementation should create one transaction per assigning player / damage step, not one isolated source, so CR 510.1e and CR 702.19b shared-blocker accounting are native.

### 4. GUI

Remove legality authority from `VAssignCombatDamage`:
- `getDamageToKill` must not be the legal validator;
- `canAssignTo`/`checkDamageQueue` must not independently decide legality;
- render `decision.legalRecipients()` and core-provided amount ranges;
- return selected authorized amount only.

Display annotations such as “lethal” may be supplied by core as non-authoritative metadata.

### 5. AI

`ComputerUtilCombat.distributeAIDamage` must stop constructing potentially legal maps directly. Keep tactical scoring/ranking only over core-exposed legal choices/ranges.

### 6. Legacy order

Current CR makes Damage Assignment Order obsolete. When `GameRules.hasOrderCombatants()==false`, the core must permit current-rule free division. If legacy mode remains supported, its order constraints must be enforced by the validator and any order choice must also be core-constrained.

### 7. Adjacent `DamageDealEffect`

Do not route noncombat `divideOnResolution` into a combat transaction. Introduce a separate constrained distribution decision if this path is production-reachable.

## Required invariant

No controller-returned amount reaches `damageMap` until the canonical core validator accepts the complete assignment transaction.

## Status

- patch compiled: NO
- engine tests run: NO
- successor qualification: NOT RUN
- Forge PASS credit: ZERO
