# Causal-stack rows: the first scripted decision is measured (2026-09-30)

Claude Opus 5.5. Lab main `4c72da6a`, live XMage pin `9375f35a`.

Placement rejects stack spells by design. The midgame lane's `causal_stack` entry rebuilds a stack by casting it for real, but only a handful of rows were configured for it. Nine more stack rows are now configured in `scripts/run_midgame_capability_probe.py`.

Each row gets one **declared fuel land** per stack spell for the spell's caster. It is published in the plan payload and never inferred. The record's own lands stay untapped for the responses the records script.

Each row uses the new terminal `scripted_decision_offered`. After the stack is verified:

1. The probe passes priority through engine-offered passes only.
2. The terminal is observed only if the engine asks the row's first `decision_script` decision:
   - the decision class equals the scripted family **exactly**;
   - it is asked of the scripted actor;
   - **exactly one** engine offer matches the scripted selection (the script's own FAIL_CLOSED contract).
3. For a scripted priority action, the scripted actor's priority is never passed; the scripted cast must be among its offers.

This is reachability of the row's obligation, not its execution. No FULL107 verdict is claimed.

## Result (same pin and seed; main vs. this branch)

| Row | Main | Now | What the engine asked |
|---|---|---|---|
| `PILOT_CHOOSE_OBJECT` (Raven's Crime) | ENGINE_REJECTED | CAUSAL_ROUTE_REACHABLE | `choose_object` to P1; `obj:p1-hand-a` offered |
| `PILOT_CHOICE` (Utopia Sprawl) | ENGINE_REJECTED | CAUSAL_ROUTE_REACHABLE | `choice` to P1; exactly one "Red" |
| `PILOT_MANA_PAYMENT` (Bolt → Counterspell) | ENGINE_REJECTED | CAUSAL_ROUTE_REACHABLE | P1 holds priority with Counterspell castable |
| `MICRO_MANA_PAYMENT` | ENGINE_REJECTED | CAUSAL_ROUTE_REACHABLE | same |
| `MICRO_PRIORITY` (Bolt → Giant Growth) | ENGINE_REJECTED | CAUSAL_ROUTE_REACHABLE | P2 holds priority with Giant Growth castable |
| `MICRO_STACK` | ENGINE_REJECTED | CAUSAL_ROUTE_REACHABLE | same |
| `CARD_13` (Bolt → Flare of Duplication) | ENGINE_REJECTED | CAUSAL_ROUTE_REACHABLE | P1 holds priority with Flare castable |
| `PILOT_REPLACEMENT_EFFECT` (Unsummon on the commander) | ENGINE_REJECTED | CAUSAL_ROUTE_MEASURED_BLOCKED | `choose_use` to P1, but the script says `replacement_effect` |
| `CARD_20` (Syphon Mind) | ENGINE_REJECTED | CAUSAL_ROUTE_MEASURED_BLOCKED | `choose_object` to **P4** first, but the script says P2 |

## The two measured blockers

- **`PILOT_REPLACEMENT_EFFECT`: decision-family vocabulary.** XMage asks the commander replacement (CR 903.9b) through `chooseUse`. The same gap is recorded in F-38 for the zone rows. Whether the family vocabulary maps provider classes is a Coordinator question; the probe reports it and does not alias it.
- **`CARD_20`: seating.** XMage's `CircularList.add` inserts each player at the current position, so the engine's turn order is the reverse of the order the bridge adds players: P1 → PN → … → P2. The frozen contract orders turns by seat number:
  - `WS05-MP-PRIO-5`: "Priority traverses exactly P1..P5";
  - `WS05-MP-TRIG-*`: APNAP groups `[P1, P2, …]`.

  So Syphon Mind's discards start with P4. This is a bridge seating defect (F-41), fixed separately.

## Not yet configured

These need their own terminal and are left for later:

- `NEGATIVE_PARENT_CLASS_FALLBACK`, `MICRO_COPY`, `MICRO_RULES_RANDOMNESS`: they have no decision script.
- `CARD_22`: counters.
- `CARD_10`: a commander spell.
- `PILOT_PILE`, `NEGATIVE_DEFAULT_YES_NO`, `CARD_07`, `CARD_16`: they need library or revealed cards.
