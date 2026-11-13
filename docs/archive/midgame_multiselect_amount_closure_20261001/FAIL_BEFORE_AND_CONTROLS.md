# Fail-before evidence and wrong-reason controls

All commands below ran on the workstream worktree with the production mid-game
lane against the machine-local XMage artifact. Classification: `MODELED`
(local development observation; the authoritative at-pin execution is the CI
PB-03 epoch). They are the forensic basis for the selector design; no
qualification credit is claimed by this file.

## 1. Fail-before: the three rows on the pre-change lane

With the three fixtures declared and the current lane code, each row stopped
unverified at the selector dispatch — the first failing boundary is the missing
selector, not the engine, the transport, or construction:

```
MICRO_COSTS: verified=False
  detail="execution failed closed: selector 'semantic_objects' is not executed by this lane"
  missing=['cost_determined:base_plus_3_generic']
PILOT_TARGET_AMOUNT: verified=False
  detail="execution failed closed: selector 'amount_assignment' is not executed by this lane"
  missing=['amount_assignment:2+2']
PILOT_MULTI_AMOUNT: verified=False
  detail="execution failed closed: selector 'amount_assignment' is not executed by this lane"
  missing=['amount_assignment:2+2']
```

Construction was `EXACT` for all three before the selector was reached.

## 2. Positive development execution after the change

`execute_and_persist` on a fresh lane process per row:

```
rows_verified 3 of 3
MICRO_COSTS verified=True  detail="obligation observed"
  cost_determined:base_plus_3_generic:
    base_mana="{4}{B}{B}", determined_mana="{7}{B}{B}", unpaid_mana="{7}{B}{B}",
    charged_mana=9, payment_frames=[2..19] (9 taps + 9 spends),
    decision_ids=<18 engine decision ids>
PILOT_TARGET_AMOUNT verified=True  detail="obligation observed"
  amount_assignment:2+2:
    assignments=[{target: P2, amount: 2}, {target: obj:pilot-p3-target, amount: 2}],
    total=4, engine_amount_remaining=4,
    decision_ids=[98c4..., 8c7c...]
  target_amount_frame:P1: decision_frames=[1, 2]
  terminal: assignment total 4 = true; every assignment >= 1 = true
PILOT_MULTI_AMOUNT verified=True  detail="obligation observed"
  multi_amount_frame:P1: decision_frames=[1, 2]
  amount_assignment:2+2: total=4, engine_amount_remaining=4,
    decision_ids=[f168..., e61c...]
  terminal: assignment total 4 = true; every assignment >= 1 = true
```

Positive receipts were persisted outside the repository
(`/tmp/opencode/dev-receipts/positive/`) and are deliberately not committed.

## 3. Live wrong-reason controls on the production executor

Each control mutates only the record's own `decision_script` in memory and
drives the real engine through the production `execute_row`; the obligation
tokens are unchanged.

| Control | Engine frames reached | Result |
|---|---|---|
| `MICRO_COSTS` with the six-creature step removed | `priority`, `target` (the real 6-of-6 frame) | `verified=false`, `missing=['cost_determined:base_plus_3_generic']` — reaching the target frame and never paying cannot satisfy the cost verifier |
| `PILOT_TARGET_AMOUNT` with one declared 2-damage leg | `priority`, `target_amount`, `target_amount` (the engine asked for the second leg) | `verified=false`, `missing=['amount_assignment:2+2']`, `assignment_total=false` — one accepted assignment is not `2+2`, and the extra frame fails closed |
| `PILOT_MULTI_AMOUNT` with one declared 2-damage leg | `priority`, `target_amount`, `target_amount` | `verified=false`, `missing=['amount_assignment:2+2']`, `assignment_total=false` |

Additional verifier-level controls are committed as unit tests: a reached-only
(not scripted) frame, a frame without an engine decision id, a final-board-only
tape, a determined cost that is not base+3, a payment run with no spends or an
unbalanced tap/spend count, and unreadable mana strings all yield no evidence.
