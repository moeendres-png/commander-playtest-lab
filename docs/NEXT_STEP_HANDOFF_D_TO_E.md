# NEXT_STEP_HANDOFF — D to E

`D_COMPLETE = true`

Merged implementation: PR #15 / `b70dda42778f61a8be5b62c79f39a385ad7c07e1`.

## D completed scope

- universal tool-run identity/provenance hardened
- run-identity drift rejection added
- policy-eval current-deck hash guard added
- counterfactual evidence-level validation hardened
- external counterfactual execution fails closed until a real executor exists
- focused D regression coverage added
- `compileall` and `git diff --check` passed
- changed-file Ruff lint and format checks passed
- full GitHub suite passed: 308 passed, 1 external-engine differential skip, 0 failures
- CI, Security, Release Artifacts and Windows Runtime Hygiene workflows passed
- no deck/inventory/opponent-content changes

## Explicit technical debt retained

- repository-wide strict Mypy is not clean: the existing baseline reports 268 errors in 36 files; D does not hide or reclassify this debt
- real XMage/Forge execution remains outside D
- model/rules-fidelity limitations remain outside D

## E — reproducible bug sprint

Proceed only with bugs that can be reproduced on the post-D `main` state.

### BUG-AUDIT-001

Hypothesis to verify: `audit-phase86 --skip-tests` or related read-only audit/acceptance commands can modify tracked audit/schema artifacts.

Required E sequence:

1. start from a clean checkout and record the exact commit;
2. run the smallest reproducer;
3. capture every changed tracked file;
4. determine the writer/root cause;
5. separate runtime outputs from versioned source artifacts;
6. route runtime output to `.runtime/`, a temporary directory, or an explicit output path when appropriate;
7. add a clean-tree-before / audit / clean-tree-after regression test.

### BUG-PERF-001

Hypothesis to verify: multiprocessing can be slower than one worker and/or leak ResourceTracker/semaphore cleanup warnings.

Required E sequence:

1. create a reproducible minimal benchmark;
2. collect timing/profiling evidence before changing code;
3. inspect process startup, pickling/serialization, card/profile lookup, chunk sizes, worker lifecycle, executor shutdown and semaphore cleanup;
4. optimize only demonstrated bottlenecks;
5. preserve single-worker performance;
6. test cleanup on success, timeout and exception;
7. claim a performance improvement only when measured before/after evidence supports it.

## E acceptance

- update bug register with reproduction status and evidence;
- add regression tests for every fixed bug;
- update performance and runtime-hygiene evidence;
- run tests, compileall, diff-check, Ruff and repository Mypy-baseline gate;
- publish a focused E PR;
- merge only after its required CI is green;
- create `NEXT_STEP_HANDOFF` for F.

Do not reopen D modeling boundaries as E bugs.
