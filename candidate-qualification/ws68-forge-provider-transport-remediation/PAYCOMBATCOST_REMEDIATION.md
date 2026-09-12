# WS68 — payCombatCost Transport Remediation (E01 attack-tax path)

- Workstream: `ws68/forge-provider-transport-remediation-20260912`
- Code commit: `903b3f4a6ff9f5228a3d8210429d5a0689383ec9`
- Provider build: `/tmp/ws68-ev` digest `c4fb2245…` (state/transport digests unchanged)
- Engine pin: `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` (read-only; no Forge edits)
- Remediated packet: `WS65-RP-PAYCOMBATCOST-01` (was `UNSUPPORTED_DECISION_KIND`, fail-closed by design)
- Behavior credit granted in WS68: `0/107` (remediation/requalification only)

## 1. Authority split (Rules Core owns everything semantic)

| Owned by Rules Core (engine) | Transported by provider (this overlay) |
|---|---|
| Whether a combat tax applies (`CombatUtil.getAttackCost/getBlockCost`, static-ability aggregation) | Nothing about applicability |
| Amount (`Cost` object, e.g. `{2}`) | Projects `String.valueOf(cost)` into the label for display only; never parses or computes |
| Mana legality (untapped native mana abilities) | Enumerates native abilities via qualified `applyManaToCost`; harness selects among offered |
| Payment procedure (`PlaySpellAbility.payCostDuringAbilityResolve`) | Delegates verbatim (Human parity, see §2) |
| Result on false (combatant removed, tapped restored — `PhaseHandler`) | Returns the engine-produced boolean untouched |
| Attack legality/result (`declareAttackers`/`CombatUtil`) | Untouched |

## 2. Implementation (Human parity, no new Rules)

`PlayerControllerHuman.payCombatCost` (`forge-gui/.../PlayerControllerHuman.java:1810`):

```java
if (cost.isOnlyManaCost() && cost.getTotalMana().isZero()
        && isFullControl(FullControlFlag.NoFreeCombatCostHandling)) return true;
return PlaySpellAbility.payCostDuringAbilityResolve(this, player, cost, sa, prompt);
```

The provider (`ws68_provider_overlay.py`, chained after the WS64 overlay) implements
byte-equivalent logic with two transport additions:

1. **Null guards** (`NULL_CARD`/`NULL_COST` fail-closed): engine-contract violations, never valid.
2. **One external `pay_combat_cost` frame** (`WS68:PAYCOMBATCOST:PAY` vs `:DECLINE`,
   attacker identity + cost text projected): externalizes the pay/decline discretion
   the Human expresses through the payment dialog (proceed vs cancel). `DECLINE`
   returns `false` so the engine applies its native result. Zero-match /
   multi-match / stale selection fail closed; unscripted frames fail closed
   harness-side (combat-tax disposition is scenario-specific, never defaulted).

On `PAY`, the method returns
`PlaySpellAbility.payCostDuringAbilityResolve(this, this.player, cost, sa, prompt)`
directly. Every discretionary sub-decision inside that engine procedure surfaces
through already-qualified transports: `confirmPayment` (PAY/DECLINE), `payManaCost`
→ `applyManaToCost` (native mana-source frames), `chooseCardsForCost`,
`getCostDecisionMaker` visits. Non-mana combat costs (sacrifice, exile, …) reach
the qualified `failClosed(costVisit:…)` stubs and fail closed — conformant, never
synthesized.

## 3. Rejected alternatives (recorded technical decisions)

- **Bare delegation without a PAY/DECLINE frame**: forces payment whenever mana
  exists; the decline half of the discretion would be unrepresentable. Rejected —
  the contract requires exposing authoritative native options where payment is
  discretionary.
- **DECLINE inside shared `applyManaToCost`**: would change the qualified mana
  surface for every spell cast (broader blast radius, casting-cancel semantics).
  Rejected — the combat-cost gate localizes the change; shared surfaces are
  byte-invariant (state digest `b6b0870f…` matches WS64/WS65).
- **Provider-side tax computation / card-name branches / first-source auto-pay /
  requested-option filtering**: forbidden; none present (build-time grep gates).

## 4. Forbidden-compliance (build-enforced, not asserted)

- No card-name literal (`Propaganda` grep gate over generated java).
- No amount computation (cost string only displayed, clipped to 120 chars).
- No fabricated sources (mana abilities enumerated from the player's zones only).
- No auto-payment (every tap is a harness-selected offered option).
- No priority/turn gating (`PhaseType` occurrence count invariant across the patch).
- No direct orchestration (no `player.concede()` / `Player.concede` /
  `getAction().concede`; no `ComputerUtilMana`; no `candidates.get(0)`).

## 5. Evidence (final build `c4fb2245`, accepted pin)

- `RQ-C3-E01/journal_pay.json.gz` (628 frames, hidden PASS): frame 528
  `pay_combat_cost` P2 — single `WS68:PAYCOMBATCOST:PAY` among 2 offered,
  attacker `MINTED-107`, cost `{2}` — followed by mana frames 529/530 selecting
  native `MINTED-167`/`MINTED-183` Island abilities; `attackers_declared 2`;
  zero blocker frames; 2 × `player_damaged amount=2 combat=true`; t15 CLEANUP
  life seat-1/seat-3 = 38/38 (taxed + untaxed attackers both dealt 2).
- `RQ-C3-E01/journal_decline.json.gz` (626 frames, hidden PASS): frame 528
  `DECLINE` selected; 7 mana frames (zero tax taps); 1 × damage event;
  t15 life seat-1 = 40 (declined attacker engine-removed, nothing paid),
  seat-3 = 38 (parallel untaxed attacker unaffected).
- 60/60 concession offers pilot-declined in each Leon (no interference).
- Frame census: exactly 1 `pay_combat_cost` frame per Leon (only the taxed
  attacker invokes the callback; the untaxed attacker costs `null` → engine
  `true` without a call — Rules Core applicability respected).

## 6. Re-entry readiness

All four E01 expected rules events are evidenced (declarations with defender
mapping; `{2}` paid for the taxed attacker only; no blockers; 2/2 damage).
`E01_REENTRY_PREREQUISITE=READY` for a future crediting wave. Tap flags and
zone outcomes are engine-procedure facts (transport lacks tapped-visibility,
as in WS65 A03) and are `EXTERNALLY_RULE_VALIDATED` via the seam identity:
payment success is proven by combat proceeding (failure would have removed
attacker 107 and left seat-1 at 40 — the DECLINE Leon is the exact control).

## 7. Remaining limits

- Non-mana combat costs fail closed (`costVisit:…` stubs) — no card in the
  qualified decks exercises them; a future overlay can extend the
  `getCostDecisionMaker` mirrors, with requalification.
- Block-cost path (`payRequiredBlockCosts`) shares the same transported method
  but has no card-level regression in the qualified decks (no block-tax card
  present); covered by construction (same method, same gates).
- Post-terminal intent exhaustion (`BLOCKED_AT:discardToMaximumHandSize`, class
  `HARNESS`) ends both runs after the behavior is complete; the game state at
  the behavior terminal is immutable evidence.
