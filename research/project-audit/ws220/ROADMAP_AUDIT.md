# WS220 Roadmap Audit

Question: is systemic → pilot → requal → compare → Freeze still optimal?

## Verdict: ORDER MOSTLY RIGHT, TWO CORRECTIONS + ONE RETIREMENT

Dependency-corrected order:
1. Publish WS213/215 + refresh manifests (clear RED; unblock merge train).
2. WS218 replay contract (AF09 closure input) + WS219 freshness (Forge input)
   — in flight, do not preempt.
3. G01 re-acquisition (long lead, start now, Coordinator-owned upstream).
4. Source-truth reconciliation + vocab unification + rollup matrix (cheap,
   unblocks reading evidence correctly).
5. Trigger-rich setup/pilot successors (APNAP, extra-turns, CR800.4,
   damage thresholds, zone/partner closers) + numeric disposition +
   name-canary negatives + per-class live negatives.
6. N-scoped rerun of CARD_29/MICRO_13/replay at 2P/3P/5P.
7. 135-disposition refresh (RETAINED→RERUN where thinnest).
8. Candidate comparison (only after 3+7; G01 at least path-closed).
9. Architecture Freeze (only after all-AF-PASS computable + passing).

Corrections to the current narrative:
- Comparison BEFORE G01 re-acquisition ranks ungrounded numbers. Gate it.
- Freeze talk before replay contract + AF rollup is premature. Sequence it.
- FULL107 retires; its budget funds steps 5–6.

Freeze distance (honest): NOT close. Gating items: G01 (externally hard),
AF09 (WS218), 10 material UNKNOWNs (2+ workstreams), AF rollup (1 stream),
comparison (1 stream), plus merge/publish hygiene. Realistic shape: several
bounded workstreams over weeks, not one big push. No date is claimed —
velocity evidence (WS203→215 in ~17h wall for the XMage chain) suggests the
machine is fast once unblocked; the blocks are G01-upstream and replay
contract, not throughput.

Immediately after WS218/WS219: consume replay tapes + freshness as
predecessors for AF09/G01; charter S-SETUP-1/S-PILOT-2 trigger-rich streams;
refresh the 135 disposition; do NOT charter comparison or claim Freeze.
