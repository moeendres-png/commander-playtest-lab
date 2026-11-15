# Audit Point E — Reproducible Bug Remediation

Date: 2026-08-08
Canonical start: post-D `main` at `6937a95479db55924b92a9cc55c6b05b516ac855`
Scope: reproducible Audit-E bugs only. No deck, inventory, opponent-content, rules-fidelity, or model-quality changes.

## Executive result

Audit E reproduced two requested defects and one additional audit-evidence defect before changing product code:

- `BUG-AUDIT-001`: reproduced and fixed.
- `BUG-PERF-001`: negative multiprocessing scaling reproduced; targeted small-workload scheduling fix implemented and measured locally. Historical resource-tracker/semaphore warnings were **not reproduced** and therefore are not claimed fixed.
- `BUG-AUDIT-002`: reproduced and fixed. The Phase-8.6 report could claim quality tools were unavailable even when they had actually executed.

Structured evidence is checked in as:

- `artifacts/audit/E_RUNTIME_HYGIENE_EVIDENCE.json`
- `artifacts/audit/E_PERFORMANCE_EVIDENCE.json`

## BUG-AUDIT-001 — tracked-tree mutation by audit execution

### Reproduction

On a clean post-D checkout, `commander-lab audit-phase86 --skip-tests` modified 13 tracked files:

1. `PHASE86_VALIDATION_OUTPUT.json`
2. `artifacts/audit/dependency_graph.md`
3. `artifacts/audit/executive_summary.md`
4. `artifacts/audit/repository_inventory.json`
5. `artifacts/audit/reproducibility_report.md`
6. `artifacts/audit/security_report.md`
7. `artifacts/audit/static_analysis_raw.json`
8. `artifacts/audit/static_analysis_report.md`
9. `schemas/models/CounterfactualBranchpoint.schema.json`
10. `schemas/models/CounterfactualResult.schema.json`
11. `schemas/models/EngineRuntimeConfig.schema.json`
12. `schemas/models/ToolExecutionMetadata.schema.json`
13. `schemas/models/ToolResponse.schema.json`

Reproduction was repeated on the corrected post-D branch state. The source checkout was clean before the audit command; the tracked changes appeared only after the command.

### Root cause

The legacy Phase-8.6 generator writes generated audit evidence, regenerated schemas, SQLite audit state, and the validation output directly under project paths that are also version-controlled source/evidence locations.

### Fix

The public `commander_lab.audit.run_phase86_audit` entrypoint now executes the legacy generator in an isolated detached Git worktree at the exact current commit. Generated outputs are copied out only after the audit completes and are published under:

`.runtime/audit/phase86/`

The isolated worktree is removed and pruned in a `finally` block. The source checkout therefore does not need the legacy generator itself to become mutation-free.

Published runtime evidence includes:

- `.runtime/audit/phase86/artifacts/audit/`
- `.runtime/audit/phase86/schemas/`
- `.runtime/audit/phase86/data/runs/`
- `.runtime/audit/phase86/PHASE86_VALIDATION_OUTPUT.json`

`.runtime/` is already ignored by Git. CI now uploads runtime evidence instead of the tracked legacy locations.

### Regression coverage

`tests/unit/test_audit_e_runtime_hygiene.py` checks:

- full `git status --porcelain=v1 --untracked-files=all` before the audit;
- audit execution;
- byte-identical status after the audit;
- runtime validation output exists;
- runtime audit registry exists;
- runtime schemas exist;
- returned artifact paths point into the runtime boundary;
- the runtime bug registry contains the reproduced E bugs.

## BUG-AUDIT-002 — audit evidence could misstate tool availability

### Reproduction

The legacy Phase-8.6 prose can state that Ruff, mypy, and Hypothesis could not be installed or executed even on a GitHub runner where those tools were installed and Ruff/mypy had actually executed.

This was observed during D/E CI evidence collection and is a real audit-truthfulness defect, not a modeling issue.

### Root cause

Availability/readiness prose was partly hard-coded instead of derived from executed check status and the current runtime.

### Fix

The runtime publication layer normalizes the generated audit evidence from the actual `AuditCheck` states and installed Hypothesis availability. It also regenerates the runtime bug register, executive summary, performance boundary note, and readiness note without the false hard-coded availability claim.

A failed static-analysis status is represented as a finding. `blocked` is reserved for a command that could not execute.

## BUG-PERF-001 — negative multiprocessing scaling

### Reproduction environment

GitHub Ubuntu 24.04 runner, 2 vCPUs, Python 3.12, structural 4-seat batch, 32 iterations, fixed deterministic seed/configuration.

Three timing repetitions per requested worker count produced these medians before the fix:

| Requested workers | Median seconds | Approx. games/s | Relative to 1 worker |
|---:|---:|---:|---:|
| 1 | 2.5028 | 12.79 | baseline |
| 2 | 3.0240 | 10.58 | 20.8% slower |
| 4 | 3.7989 | 8.42 | 51.8% slower |

The controlled reproduction produced no `resource_tracker` or semaphore warning on stderr, and `multiprocessing.active_children()` was empty after the runs. The historical cleanup-warning portion of the bug was therefore **not reproduced**.

### Profile evidence

The measured parent-process profile identified process lifecycle cost as the dominant overhead:

- approximately 0.92 s cumulative in process spawning for the profiled two-worker run;
- approximately 1.79 s cumulative in ProcessPool shutdown/waiting for that sample;
- 32-task construction: approximately 0.00027 s;
- deck-payload serialization: approximately 0.0019 s;
- serialized deck payload: approximately 305 KB.

The data does not support optimizing task construction, card/profile lookup, or JSON/Pydantic serialization for this bug sprint. The demonstrated cost is process startup/lifecycle on undersized batches.

### Fix

A public structural scheduling layer now computes an effective worker count before entering the existing batch implementation:

- requested single-worker execution is never changed;
- effective parallelism is capped at available CPUs and iteration count;
- multiprocessing is used only when there are at least 32 games per effective process worker;
- undersized batches fall back to the existing serial implementation;
- the original batch implementation, deterministic seeds, simulator, aggregation, and large-batch process-pool behavior remain unchanged.

This policy directly covers the reproduced 32-game negative-scaling case without changing simulator semantics or introducing a speculative process-context change.

`tests/unit/test_audit_e_performance_scheduler.py` verifies the scheduling boundary, CPU oversubscription cap, single-worker preservation, and exception propagation. Existing worker-count reproducibility tests continue to exercise public `run_structural_batch`.

### Post-fix measurement

A guarded same-runtime raw-vs-scheduled benchmark was run locally on Linux/Python 3.13.5 with three repetitions of the same 32-game workload:

| Case | Median seconds |
|---|---:|
| raw 1 worker | 1.8904 |
| raw 2 workers | 2.5302 |
| scheduler, request 2 workers | 1.9231 |
| scheduler, request 4 workers | 1.8831 |

For the two-worker request, the scheduler path was approximately **24.0% faster than the raw two-process path in that same local runtime** (`2.5302 s` → `1.9231 s`). Both 2- and 4-worker requests intentionally resolved to one effective worker for 32 games, and no active child process remained after the measurement.

This is deliberately not represented as a universal speedup or as a GitHub-hosted post-fix percentage. The pre-fix GitHub benchmark and post-fix local benchmark are different runtime environments.

A broader GitHub break-even helper run was discarded as performance evidence because its helper script omitted an `if __name__ == '__main__'` guard while process-spawn was exercised. That caused recursive child execution, repeated output blocks, timeout/cancellation, and orphan cleanup. None of those contaminated timing blocks are used for the performance claim.

### Cleanup boundary

The reproduced small-workload case no longer creates a process pool, removing the measured startup/shutdown cost from that case. For larger process-backed batches, the existing implementation still owns its `ProcessPoolExecutor` through a context manager. Because the historical resource-tracker/semaphore warning was not reproduced in the controlled reproduction, E does not claim to have fixed an unobserved cleanup defect.

## Local regression verification

Using the last green D release/repository artifact as the code baseline with the final E net patch applied locally:

- targeted E/audit/structural regression set: 14 PASS;
- non-unit architecture/contract/differential/fuzz/golden/property/regression group: 43 PASS, 1 expected external-engine differential SKIP;
- structural/rules integration group: 14 PASS;
- remaining integration group: 13 PASS;
- unit group A: 96 PASS;
- unit group B: 148 PASS;
- aggregate collected execution across split groups: **314 PASS, 1 expected SKIP, 0 test failures**;
- `python -m compileall -q src tests`: PASS;
- `git diff --check`: PASS.

The local sandbox cannot install the repository's pinned Ruff/Mypy build environment from its restricted package index. Those gates remain mandatory in final GitHub CI and are not inferred from the local run.

A one-command local full-suite invocation under Python 3.13 emitted successful test progress but did not terminate cleanly within the container timeout after some integration cases; the same tests pass when split, and the repository's supported CI path is Python 3.12. This local-runtime behavior is not promoted to a new E bug without a supported-runtime reproduction.

## Final GitHub CI boundary

PR #18 must still pass on its final compact head:

- changed-file Ruff lint;
- changed-file Ruff format check;
- repository Mypy baseline gate;
- full pytest suite;
- compileall;
- security;
- Release Artifacts;
- Windows Runtime Hygiene.

At the time this report was finalized, newly started GitHub Actions jobs were being rejected by GitHub before execution with an account-level Billing/Spending-Limit message. This is an external CI execution blocker, not a passing gate and not a code failure. **PR #18 must not be merged until a fresh final-head CI/Release/Windows cycle actually completes green.**

Repository-wide strict Mypy debt from D is not reclassified as an E bug.
