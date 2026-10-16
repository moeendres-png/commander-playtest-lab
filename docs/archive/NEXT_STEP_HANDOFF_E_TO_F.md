# NEXT_STEP_HANDOFF — E to F

This handoff becomes authoritative after Audit-E PR #18 is merged with all required CI green.

## Canonical starting point for F

Start from the merge commit of PR #18 on `main`, or a verified descendant of that commit.

Do not restart D or E. Do not alter decklists, inventory, opponent content, or external-engine truth boundaries unless F explicitly requires it.

## E completed scope

- reproduced `BUG-AUDIT-001` before repair;
- isolated Phase-8.6 generated evidence from the tracked source checkout;
- published audit runtime output under `.runtime/audit/phase86`;
- added clean-tree-before / audit / clean-tree-after regression coverage;
- reproduced and fixed `BUG-AUDIT-002`, the hard-coded quality-tool availability claim;
- reproduced negative scaling for `BUG-PERF-001` on the controlled 32-game workload;
- profiled process startup/shutdown instead of guessing at serialization or card lookup;
- added an effective-worker scheduler with CPU cap and a small-workload serial fallback;
- preserved the requested single-worker path unchanged;
- kept deterministic structural-simulation semantics and the existing large-batch implementation;
- did not claim a resource-tracker/semaphore fix because the warning was not reproduced.

## Evidence boundaries carried into F

- Structural simulation remains `structural_model_estimates`, not real-game evidence.
- Tactical Oracle remains non-external.
- Real XMage/Forge execution remains a separate external-engine validation boundary.
- Repository-wide strict Mypy debt is still an explicit baseline limitation and is not silently represented as clean.
- Performance claims require measured before/after evidence; scheduler policy tests alone are not a throughput claim.
- Historical resource-tracker/semaphore warnings remain unconfirmed unless a future controlled run reproduces them.

## F entry checks

Before changing F-scope code:

1. verify `main` contains the merged E commit;
2. verify the E report and this handoff exist on `main`;
3. verify the final E CI/Release/Windows runs were green;
4. verify `commander-lab audit-phase86 --skip-tests` leaves tracked status unchanged;
5. verify generated Phase-8.6 evidence appears under `.runtime/audit/phase86`;
6. retain the E performance evidence and scheduler threshold unless new measurements justify changing it.

## Do not reopen as E bugs

- model/rules fidelity;
- pilot quality;
- opponent realism/uncertainty;
- meta freshness;
- external-engine execution;
- unrelated repository-wide typing debt.

These remain separate roadmap/audit scopes.
