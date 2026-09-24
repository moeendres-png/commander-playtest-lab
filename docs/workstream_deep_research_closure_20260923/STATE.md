# DR-CLOSURE-01 — Explicit Resumability State

Workstream: `DR-CLOSURE-01`
Branch: `dr-closure-01-deep-research-20260924`
Worktree: `/home/moeen/code/ws-dr-closure-20260924`
Source lock: see `SOURCE_LOCK.md`
(`HEAD 2231ff4bdd30753a127133e51a0d3657c668532d`,
tree `f759ed34d35fdf76ebbb04814edf4a470f960e27`, clean).

## Status ledger (one `in_progress` at a time)

- [x] Phase 0 — source lock, ownership, duplicate detection
- [x] Phase 1 — P0 native state restoration closure (hand v2 + fail-closed taxonomy)
- [x] Phase 2 — TRIG-3/5 promoted; ELIM life-0 blocker characterized
- [x] Phase 3 — LAYERS/TARGETS/CHOOSE_MODE promoted; negative evidence; Argentum verified; UNKNOWN-blocker correction
- [x] Phase 4 — candidate-domain invariant + Serum Visions regression + decoy
- [x] Phase 5 — first-divergence comparator + real tape-pair evidence
- [x] Phase 6 — EXTERNAL_RISK_SIGNAL pack (A/B/C/E/F + D partial; Hex-gap finding)
- [x] Phase 7 — process-isolation audit (verified, no change)
- [x] Final adjudication — re-lock, re-census, terminal ledger, handoff

## Campaign state: `DR-CLOSURE-01 = COMPLETE`

Final census: `DIRECT 12 / SUPPORTING 13 / UNKNOWN 54 / NOT_RUN_BLOCKED 28`
(from `7/13/57/30`). All 13 research findings terminally dispositioned
(9 implemented+verified, 2 already-verified, 1 rejected-by-invariant,
1 blocked-fail-closed). Architecture Freeze NOT CLAIMED; Production
Provider NOT SELECTED (untouched).
- [ ] Phase 3 — P1 hidden-information & decision-family closure (rerun-before-redesign + Argentum audit)
- [ ] Phase 4 — P1 bounded candidate-domain correctness (generic invariant + actual-card regression)
- [ ] Phase 5 — P1 provider-neutral first-divergence tooling (comparator + 8 unit cases + real replay pair)
- [ ] Phase 6 — P2 predictive regression pack (`EXTERNAL_RISK_SIGNAL` namespace, classes A–F)
- [ ] Phase 7 — P2 process-isolation audit (audit-before-edit)
- [ ] Final adjudication — re-lock, re-census, disposition ledger, handoff

## Dependency DAG (sequential default, single worker)

```text
Fresh Source Lock
        |
        v
Native State Restoration P0
        |
        +----------------------------+
        |                            |
        v                            v
N-Scoped Qualification P0      Hidden/Decision P1
        |                            |
        |                       Candidate Domain P1
        |                            |
        +--------------+-------------+
                       |
                       v
              Differential Trace P1
                       |
                       v
             Predictive Regressions P2
                       |
                       v
             Process Isolation Audit P2
                       |
                       v
               Final Adjudication
```

## Mutation-surface ownership (do not collide)

- Owned here: `XmageNativeStateRestoration.java` extensions (fail-closed),
  FULL107 mapping promotions (exact-evidence only), new `EXTERNAL_RISK_SIGNAL`
  regression namespace, differential comparator hardening, candidate-domain
  invariant tests, hidden/decision evidence runs, docs under
  `docs/workstream_deep_research_closure_20260923/`.
- Foreign/verify-only: PR #239 merged surface (reuse, don't duplicate),
  PR #240 do-not-redo list (§16), open PR #206 safe-push surface.

## Invariants (load-bearing)

- Rules Core alone decides legality; pilots choose only offered options.
- Forbidden production-reachable shortcuts stay forbidden (§2); unsupported
  paths fail closed.
- `starting_state_injection_supported` remains `false` (global flag untouched).
- Evidence semantics preserved exactly; `UNKNOWN != PASS`, `NOT_RUN != PASS`,
  `CODE_DERIVED != RUNTIME_VERIFIED`.
- `ARCHITECTURE_FREEZE = NOT CLAIMED`; `PRODUCTION_PROVIDER = NOT SELECTED`.
- No foreign code copy without license adjudication; every external influence
  recorded in `EXTERNAL_PROVENANCE_LEDGER.md`.

## Next single action

Phase 1 Step 1: build the blocked-fixture dimension matrix
(`BLOCKED_FIXTURE_MATRIX.json`) from the frozen FULL107 mapping + frozen
semantic records, rank missing dimensions by ordinal/Pareto leverage, then
reuse-first investigation per dimension.
