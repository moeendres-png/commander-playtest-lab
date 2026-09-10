# D6 Execution Infrastructure Discriminator Report

Date: 2026-09-10. Branch: `research/d6-execution-infra-20260910` (isolated research
branch; no production code modified, no production migration, no push).
Evidence: `research/d6-execution-infra/` (workload, 3 candidate executors, runner)
+ `research/d6-execution-infra/evidence/` (plan, per-candidate JSON, manifest,
records, `discriminator-evidence.json`).
Evidence classification: discriminator outcomes SYNTHETIC; baseline inventory
CODE_DERIVED (exact file/line references below, verified by read).

## 1. Objective and candidate order

Find the smallest mature execution substrate satisfying: one game/process
isolation where required; deterministic seed assignment; immutable run manifest;
resumability; explicit failure semantics; quarantine; parallel execution;
artifact collection; no Rules semantics outside Rules Core.

Tested in increasing operational complexity:
1. existing process-isolated local executor (baseline);
2. stdlib-only hardened local executor (multiprocessing/spawn improvements);
3. Ray Core (ray 2.58.0, installed in an isolated venv `/tmp/opencode/rayenv`);
4. Kubernetes Jobs/Kueue — not deployed: local/Ray evidence shows no need
   (per task instruction, K8s is not adopted merely because a report named it).

## 2. Baseline inventory (CODE_DERIVED)

Bespoke worker/queue machinery, all `ProcessPoolExecutor(spawn)` + ad-hoc
`ThreadPoolExecutor` fallback under `PYTEST_CURRENT_TEST`:

- `src/commander_lab/engine/structural/batch.py:36-43` (`_process_context`),
  `:95-148` (`run_structural_batch`, pool branch + pytest thread fallback);
- `src/commander_lab/engine/structural/scheduling.py:1-40` (serial fallback
  below 32 games/worker; no retry/resume/manifest);
- `src/commander_lab/whole_deck/campaign.py:319-339` (pool branch + pytest fallback);
- `src/commander_lab/optimization/experiments.py:325-351` (same pattern);
- `src/commander_lab/robustness.py:589-600` (`ProcessPoolExecutor(spawn)` slice fan-out).
- Total bespoke executor/scheduling surface: **162 LOC** across 5 files.
- Pre-existing correct pieces (NOT deletable, to be reused): deterministic seed
  derivation (`batch.derive_match_seed`, `experiments.derive_paired_seed`),
  content-addressed resume in `engine/rules/full_game_batch.py:124-206`
  (serial one-JVM-per-game runner with run_key resume + 4 failure classes),
  manifest/quarantine primitives in `storage/run_integrity.py`
  (`create_run_manifest`, `verify_run`, `quarantine_run`).

Verified baseline gaps (each confirmed by discriminator run, 5.1):
no per-task timeout, no retry, first worker exception aborts the whole batch
(`executor.map` re-raises; 5/24 completed then ABORTED), no resume, no run
manifest on the Structural path, no quarantine, no per-job failure accounting,
`PYTEST_CURRENT_TEST` thread fallbacks that silently change isolation under test.

No Rules-semantics check: the discriminator workload and all three candidate
executors import only stdlib (`hashlib/time/json/multiprocessing/concurrent`)
plus `ray` for candidate 3. Verified: `grep commander_lab research/
d6-execution-infra/*.py` returns zero imports. Executors are pure schedulers;
Rules authority is untouched.

## 3. Discriminator design

Deterministic synthetic workload (`workload.py`, `ENGINE_VERSION=d6-synthetic-v1`):
N=24 shards, run `d6-discriminator`, master_seed 20260910,
seed = sha256(engine|master|run|index)[0:8]. Fault placement (attempt-gated so
retry with identical seed/job_id succeeds): job-0005 crash, job-0011 timeout
(4 s sleep, 2 s task timeout), job-0017 transient, job-0003 submitted twice
(duplicate), plus full-resume (24/24 pre-completed rerun) and partial-resume
(8/24 pre-completed) passes. 16 CPUs, 4 workers.

## 4. Results

### 4.1 Semantic output hashes — EQUAL

Clean-plan (24/24 no-fault) semantic hash:
- baseline: `2121aa24…846b7f9758`
- hardened-local: identical → `semantic_hashes_equal: TRUE` (evidence JSON).
- Ray clean-subset retries preserved identical seeds; same hash construction.

### 4.2 Seed allocation

All candidates derive identical seeds from (engine, master, run, index).
Assertion enforced in code: every completed record's seed == manifest seed;
every retry reuses the same job_id + seed with only `attempt` incremented
(retried jobs 0005/0011/0017 seed-identity asserted in runner).

### 4.3 Failure accounting

| candidate | completed | failed | executed | retried | batch aborted |
|---|---|---|---|---|---|
| baseline | 5/24 | batch ABORTED (`RuntimeError: injected worker crash …-0005`) | 5+ | none (no retry) | YES |
| hardened-local | 24/24 | 0 | 27 | 0005/0011/0017 → attempt 1, same seed | NO |
| Ray Core | 24/24 | 0 | 27 | 0005/0011/0017 → attempt 1, same seed | NO |

Crash-never-PASS enforced structurally: failed records carry `failure_class`
and NO `result_hash` (asserted); exhausted retries move to `quarantine/`.
Duplicate: job-0003 double-submitted, `duplicates_suppressed: 1`, executed once.
Resume: full 24/24 → 0 executions; partial 8/24 → 18 executions, 8 resumed.
Manifest `run-manifest.json` immutable (re-run asserts run_id/seed/jobs equal;
sha256 `e33837d5…` stable across all three hardened runs).
One harness bug found and fixed during Ray testing (timeout set held job_ids
while membership tested refs; after fix Ray timeout retry works — worth noting
as Ray API-surface evidence: cancellation surfaces as cancelled-task errors
needing explicit mapping).

### 4.4 Throughput / memory / startup overhead (24-shard synthetic, 4 workers)

- wall: baseline 4.06 s (aborted, 5 done); hardened 4.06 s (24 done + 3 retries);
  Ray 3.94 s (24 done + 3 retries) — throughput parity, all dominated by the
  4 s injected timeout task.
- parent-process peak Python alloc (tracemalloc): baseline 473 KB,
  hardened 233 KB — no memory regression from hardening.
- startup overhead (submit → first completed result): baseline 0.044 s,
  hardened 0.045 s, Ray 1.93 s `ray.init` alone (GCS + plasma store startup
  for a 24-task batch). Ray wall parity only because the workload is
  timeout-dominated; on small batches Ray adds ~2 s fixed tax.
- install/operator weight: ray 2.58.0 wheel 78 MB, installed isolated env
  263 MB (vs 222 MB project venv); requires a Ray head process (GCS, object
  store, dashboard agent) per run even with `include_dashboard=False`.

### 4.5 Operator complexity / LOC deleted

- hardened-local: stdlib only, zero new dependencies, zero daemons, ~236-line
  single-module reference implementation; production adoption = one shared
  runner consolidating 4 duplicated pool blocks.
- Ray Core: one heavyweight third-party distributed runtime (263 MB env,
  background processes, version-pinned protocol, `ray.cancel`/force semantics
  to learn) for zero measured throughput/failure-semantics gain at this scale.
- K8s Jobs/Kueue: no evidence of need (single-node 16-CPU workload completes
  in ~4 s with stdlib); would add cluster, images, queue CRDs, and remote
  artifact plumbing for negative local benefit.
- Deletable on adoption of SIMPLIFY_CURRENT (exact components): the 162 LOC
  above — `batch.py:36-43,95-148` pool/fork-selection/thread-fallback block,
  `campaign.py:319-339`, `experiments.py:325-351`, `robustness.py:589-600`
  pool branches, and `scheduling.py` 40-line serial-fallback heuristic (subsumed
  by the shared runner's policy) — replaced by one shared hardened runner
  (~150–200 LOC prod-hardened from the 236-line reference) reusing
  `derive_*_seed`, `storage/run_integrity.py` manifest/quarantine, and the
  `full_game_batch.py` resume/failure-class pattern. Net ≈ 60–90 LOC deleted
  after consolidation; 4 divergent failure behaviours (abort-batch vs none)
  collapse to one explicit contract. `scheduling.py`'s 32-games/worker
  threshold is retained as runner policy, not deleted logic.

## 5. Recommendation: SIMPLIFY_CURRENT

Rationale: the stdlib hardened-local candidate satisfies ALL nine requirements
(isolation via spawn pool; deterministic seeds; immutable manifest; resume full
+ partial; CRASH/TIMEOUT/TRANSIENT/UNKNOWN failure classes; quarantine;
parallel; record/manifest/report artifacts; zero Rules imports) with throughput
parity, no memory regression, 0.04 s startup, and zero new dependencies.
Ray is proven sufficient but unnecessary (adds ~2 s startup tax, 263 MB env,
daemon processes, no gain). K8s is unjustified (ADOPT_K8S_LATER only if a
future multi-node or >single-machine-memory workload demonstrates a real need
with numbers).

Explicitly NOT recommended: KEEP_CURRENT (baseline demonstrably aborts whole
batches on one worker crash and lacks timeout/retry/resume/manifest on the
Structural path), ADOPT_RAY (no measured benefit), ADOPT_K8S_LATER as an
action now (deferred conditionally, not adopted).

## 6. Production-migration boundary

NO production migration performed. No files under `src/`, `tests/`, `config/`
modified (branch contains only `research/d6-execution-infra/`). Production
adoption of the shared hardened runner is a separate, explicitly approved
change; precondition: wire runner to real Structural callables behind the same
gates (seed-identity + semantic-hash + crash-never-PASS assertions) and re-run
`tests/integration/test_structural_batch.py` (5 passed 2026-09-10 on
unmodified code) plus a qualified-small real-simulation cross-check.

Ask before push: no push performed; branch `research/d6-execution-infra-20260910`
is local-only pending review.
