# Phase 2 Closeout — P0 FULL107 / N-Scoped Direct Execution

Source lock (execution): worktree HEAD `ab33b642` on `2231ff4b`
(engine `1.4.61`/`db134b97`, seed 424242 throughout).

## Denominator partition (fresh)

- `ALREADY_DIRECT_VALID` (7): CARD_02, TAX-2/4, PARTNER-TAX/ZONE, MULL-2/4 —
  not rerun (no relevant byte change; retention standing).
- `NEWLY_UNBLOCKED_BY_PHASE1` (2): TRIG-3/5 → **executed and promoted**.
- `EXECUTOR_GAP` (0 new): TRIG cast path executed through existing generic
  bridge; no new executor built.
- `ENGINE_CAPABILITY_BLOCKER` (4 clarified + 22 standing): life-0 elimination
  (new exact mechanism below), stack (11), damage (5), temporal (7),
  control (2), hand+stack PRIO (2, hand closed/stack remains).
- `AUTHORITY_BLOCKER`: none new.

## Executed (current bytes, DIRECTLY_VERIFIED)

1. `WS05-MP-TRIG-3` (3P) — `XmageFullGameTrigExecutionTest`: hand restore →
   engine-offered cast → `{1}{G}` Forest payment → ETB → 3× Soul Warden
   triggers → life 41/41/41. Promoted `NOT_RUN_BLOCKED → DIRECT`.
2. `WS05-MP-TRIG-5` (5P) — same shape, life 41×5. Promoted.
3. `WS05-MP-ELIM-OWNED-3` / `WS05-MP-ELIM-5` — executed as blocker
   characterization (`XmageFullGameElimExecutionTest`): stays
   `NOT_RUN_BLOCKED` with exact mechanism (below), fail-closed pinned.

## New finding (executed, not inferred)

Life-0 elimination is not restorable via pre-start `setLife(0)`: the engine
re-derives starting life (40) during game start — readback proves P2/P3 at 40,
alive, no cleanup (Sol Ring stays). Corrects the Phase 1 matrix row that
marked these 4 cells "already-supported": elimination requires genuine loss
causation (real damage through the engine), which is executor scope. The
characterization tests pin this so future pin/engine changes are caught.

## Census delta (this phase)

```text
DIRECT 7 → 9 (+TRIG-3, +TRIG-5)
NOT_RUN_BLOCKED 30 → 28
SUPPORTING 13, UNKNOWN 57 unchanged
```

No other cell touched: no supporting-evidence promotion, no inference across
player counts (TRIG-3 ≠ TRIG-5 evidence; both executed exactly).

## Impact

- Mapping file updated (counts + 2 entries with evidence pointers).
- Prior DIRECT evidence retained (semantically unaffected paths).
- Follow-ups: stack-reconstruction executor workstream; damage/engine-side
  dispatch; temporal progression-driver dispatch (Final Adjudication).
