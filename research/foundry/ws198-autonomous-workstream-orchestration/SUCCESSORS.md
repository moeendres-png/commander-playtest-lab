# WS198 Successor Proposals (plan-only; NOT executed)

Machine-checked: `autonomy.validate_successor_set` → no errors (3/3 ≤ max 3,
all 18 required fields, lanes valid, executability classed, SHAs carry
`sha_provenance`). Planning only — every successor needs a fresh explicit
Coordinator/operator launch; WS198 creates no branches, worktrees, or epochs.

1. `SUCCESSOR_1_TELEMETRY.json` — **IMMEDIATE**, HIGH — natural session
   telemetry capture hygiene (export → aggregate → provenance). Unblocks
   measurement of everything WS198 left UNKNOWN.
2. `SUCCESSOR_2_ROTATION.json` — **IMMEDIATE**, HIGH — rotation observability
   from state/Git facts, threshold-free, advisory-only. Depends informatively
   (not hard) on successor 1.
3. `SUCCESSOR_3_PREAUTH.json` — **COORDINATOR_DECISION**, XHIGH —
   preauthorized multi-phase execution design. Requires a Sol High authority
   ruling on the shape before any activation implementation; default stays
   `COORDINATOR_GATE`.

Priority order: 1 → 2 → 3. Throughput candidates beyond these three (general
Foundry improvements) were considered and deferred to keep the default
recommendation count at 3.
