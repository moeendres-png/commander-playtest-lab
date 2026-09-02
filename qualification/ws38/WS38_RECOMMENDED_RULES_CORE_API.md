# WS-38 Recommended Forge Rules-Core API

## Status

**Feasibility design only.** This document grants no Forge provider qualification and no AF04 PASS.

Recommended remediation base: `Card-Forge/forge@ef4c834dbbca21a099ae751fb52b2326abdf1e02`.

## Rules premise

The current official Comprehensive Rules are effective 2026-08-07. Under CR 510.1c-d, Damage Assignment Order is obsolete for normal current rules: a creature blocked by / blocking multiple creatures divides damage among them as its controller chooses. CR 510.1e validates the **total damage assignment made by a player**, not merely each creature in isolation. CR 702.19b modifies this for trample and explicitly counts damage from other creatures being assigned during the same combat damage step. CR 702.2c makes any nonzero combat damage from deathtouch lethal for excess-damage purposes.

This makes a player/step-level transaction safer than a naïve per-creature callback.

## Recommended engine-side shape

Names are illustrative; package placement should be `forge.game.combat`.

```java
public final class CombatDamageDecision {
    Player assigningPlayer();
    boolean firstStrikeStep();
    List<CombatDamageSourceFrame> pendingSources();
    CombatDamageSourceFrame currentSource();
    List<DamageRecipient> legalRecipients();
    IntRange legalAmountRange(DamageRecipient recipient);
    CombatDamageDecision assign(DamageRecipient recipient, int amount);
    boolean sourceComplete();
    CombatDamageDecision nextSource();
    boolean complete();
    CombatDamageAssignment finalizeAndValidate();
}

public final class CombatDamageAssignmentValidator {
    ValidationResult validate(
        Combat combat,
        Player assigningPlayer,
        boolean firstStrikeStep,
        CombatDamageAssignment proposed
    );
}
```

The important contract is semantic, not these class names.

## Core-owned invariants

The Rules Core must derive and enforce:

1. which creatures assign in the current first-strike/regular damage step;
2. which player assigns each source's damage, including banding/Defensive Formation effects;
3. source damage amount from native combat state;
4. legal recipient set;
5. exact total assignment;
6. trample permission to spill and required blocker lethal thresholds;
7. deathtouch treatment for lethal assignment;
8. same-step damage from other sources when determining trample lethal;
9. trample-over-planeswalkers loyalty threshold;
10. current-rule free division among multiple blockers/attackers;
11. legacy order only when Forge's legacy `orderCombatants` rules mode is explicitly enabled;
12. special native card-rule assignment modes such as assign-as-unblocked/divide-as-you-choose;
13. no negative amount, overassignment, omitted mandatory amount, foreign recipient, or stale object;
14. final CR 510.1e transaction validity before `damageMap` mutation.

The final validator must be the same authority used by game execution. There must be no provider-only validator.

## Transaction and commit

`Combat.assignAttackersDamage` / `assignBlockersDamage` should stop ingesting arbitrary controller maps directly.

Preferred flow:

1. `Combat` builds a core decision transaction from native combat state.
2. Forced allocations are resolved by core without a discretionary callback.
3. When discretion exists, controller receives a core-owned decision surface.
4. Controller selects only from recipient/amount choices exposed by the transaction.
5. The transaction records proposed allocations without mutating `damageMap`.
6. After that assigning player's complete damage assignment is supplied, core invokes the canonical validator over the total proposed assignment (CR 510.1e).
7. Only a valid transaction is committed to assigned-damage bookkeeping / `damageMap`.
8. `dealAssignedDamage()` remains the later simultaneous damage-application boundary.

A malformed/stale controller submission must throw/fail closed; it must not be repaired, clamped, auto-filled or sent to AI/GUI fallback.

## Why not complete enumeration

For total damage `D` split among `k` recipients, the unconstrained complete allocation count is `C(D+k-1, k-1)`. It reaches 10,015,005 at D=20/k=10 and 2,054,455,634 at D=40/k=10 before rule filters. Materializing all complete alternatives is therefore unsuitable.

An incremental rules-owned range/candidate surface keeps the pilot ignorant of legality algorithms while avoiding enumeration.

## GUI migration

`VAssignCombatDamage` should become presentation only:

- render recipients and core-provided ranges;
- request amount choice;
- never calculate lethal/deathtouch/trample legality itself;
- disable/enable controls from core decision state;
- submit a selected amount to the core transaction.

Its current `getDamageToKill`, `canAssignTo`, `checkDamageQueue` legality responsibilities should move to core or become display-only projections of core facts.

## AI migration

`ComputerUtilCombat.distributeAIDamage` may retain tactical preferences but must choose only from the same core-provided legal decision surface. AI may rank legal ranges/options; it may not generate legality independently.

## External headless provider

The GPL Forge process may serialize a semantic frame containing opaque source/recipient IDs plus core-authorized amount ranges/candidates. Commander Lab's pilot selects among those choices and returns the semantic selection. The Forge process resolves IDs against the live decision and revalidates before commit.

No Forge object graph or GPL code needs to be embedded in proprietary Commander Lab.

## Adjacent noncombat reuse

`DamageDealEffect` currently reuses `assignCombatDamage` for `divideOnResolution`. Do not force that noncombat path through the new combat-specific transaction. Preserve the old callback temporarily only if isolated from production, or introduce a separate core constrained `AmountDistributionDecision` with its own rules validation.

## Required failure behavior

- stale decision ID: reject;
- unknown source/recipient: reject;
- amount outside current core range: reject;
- incomplete transaction: reject;
- invalid final assignment: reject and return to pre-assignment decision state;
- missing external decision handler on a reachable discretionary path: fail closed;
- no GUI/AI/default/random/first-option fallback.

## Qualification status

`SOURCE PATCH != PROVIDER QUALIFIED`

`UNIT TEST PASS != SUCCESSOR RUNTIME PASS`
