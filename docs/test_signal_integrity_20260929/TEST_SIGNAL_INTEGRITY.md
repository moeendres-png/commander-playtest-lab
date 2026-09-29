# Test Signal Integrity — Audit and Remediation

Workstream: `MAINTENANCE-TEST-SIGNAL-INTEGRITY-20260929`
Date: 2026-09-29

**Bottom line:** the local test baseline was permanently red for reasons unrelated to product
behaviour. That has been fixed for the 4 environment-dependent failures, the 2 remaining
failures are one missing declared dev dependency, and one permanently-skipped test that
asserted a retired executor has been replaced with real hermetic coverage.

---

## 1. The trap this campaign existed to remove

### 1.1 Mechanism

`pyproject.toml:51` sets:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
```

That applies to the **pytest process only**. It is not inherited by child interpreters, and it
does not install the project. So:

- CI runs `pip install --no-deps --no-build-isolation -e .` (`.github/workflows/ci.yml:36`,
  and again at `:122` for the security job). There, `commander_lab` is importable everywhere,
  including in subprocesses. **CI is green.**
- A bare local `python3 -m pytest` has no install. In-process imports work anyway because
  pytest injects `src` itself. **Any test spawning a child interpreter fails** with
  `ModuleNotFoundError: No module named 'commander_lab'`.

In this environment `/usr/bin/python3` is 3.14.4 and `commander_lab` is **not importable at
all** in it — yet 2242 tests pass, purely because of the in-process injection.

### 1.2 Why it was worth fixing

The previous hygiene campaign had to hand-build a pristine worktree and run the suite twice
to prove a zero-delta change. Every session rediscovers this. It also makes "is my change
broken?" unanswerable locally, which is the single most common question in this repository.

### 1.3 The baseline before and after

| | Failing | Passing | Skipped |
|---|---:|---:|---:|
| Before (6 distinct failures) | 6 | 2242 | 8 |
| After this workstream | **2** | **2252** | **7** |

The 6 were: 4 × subprocess import, 1 × missing `httpx2`, 1 × cascade of that same missing
`httpx2`. Details in §2 and §3.

---

## 2. The 4 subprocess tests — fixed

All four had the identical shape: `subprocess.run([sys.executable, …])` with no `PYTHONPATH`.

| Test | Change |
|---|---|
| `tests/unit/test_structural_profiles.py::test_profile_generation_is_stable_across_python_hash_seeds` | uses `subprocess_env` |
| `tests/unit/test_snapshot_reproducibility.py::test_local_snapshot_build_is_stable_across_python_hash_seeds` | uses `subprocess_env` |
| `tests/unit/test_first_run_preparation.py::test_full_runner_requires_a_prepared_spec_before_execution` | `env=subprocess_env` |
| `tests/integration/test_priority_racing_benchmark.py::test_frozen_adaptive_budget_policy_gate_preserves_material_finalists` | `env=subprocess_env` |

The fix is one shared fixture in `tests/conftest.py`:

```python
@pytest.fixture
def subprocess_env() -> dict[str, str]:
```

It prepends `src` to `PYTHONPATH` so the checked-out tree wins over any stale installed copy.
Function-scoped and freshly built per test, so a caller mutating it cannot leak.

**The import failure was masking nothing.** All four pass once the import resolves, which means
their assertions were already correct and had simply never executed on a bare local run.

Two `import os` lines became unused as a result and were removed; `ruff` is clean.

---

## 3. The 2 remaining failures — one root cause, not two

Both are the missing `httpx2` dev dependency, which **is declared** at `pyproject.toml:25` and
`requirements/lock.in:16`. It is simply not installed in this environment.

### 3.1 `test_api_self_test_runs_in_isolated_process`

Direct: the isolated child does `from fastapi.testclient import TestClient`, and
`starlette` requires `httpx2`.

### 3.2 `test_phase10_smoke_never_claims_external_validation` is NOT an independent defect

This one was flagged as *"möglicherweise echt — muss verifiziert werden"*. **It is not real.**
The causal chain is in source:

1. `src/commander_lab/acceptance/phase10.py:284-285` — the isolated API self-test raises when
   the child exits non-zero, and the child cannot import `TestClient`.
2. `src/commander_lab/acceptance/phase10.py:604` — an `except` handler catches it and sets
   `api_demo = {"status": "failed", …}`.
3. `src/commander_lab/acceptance/phase10.py:720` — `status` becomes
   `"passed_with_limitations" if local_acceptance_passed else "failed"`.
4. The test asserts `result["status"] == "passed_with_limitations"`, so it fails.

**Correcting an earlier classification:** in the first campaign I recorded this as a possibly
genuine assertion failure. It is a cascade of the same missing package. One root cause, two
failures — not one environmental and one real.

The fix is environmental (`pip install -e '.[dev]'`), not a code change, and installing
packages into the operator's environment is not this workstream's call. The trap is now
documented in `README.md` where a reader meets it.

---

## 4. The permanently-skipped test — replaced, not deleted

`tests/foundry/test_telemetry.py::test_session_stats_against_live_export_shape` was doubly
defective:

1. It read `/tmp/opencode/session-shape.json`, a path **nothing in the repository creates** —
   the only reference in the whole repo was the test itself. It therefore skipped on every CI
   run and every fresh checkout, and had **no effective coverage at all**.
2. It asserted `summary["model"] == "opencode-go/muse-spark-1.3-contributor"` — a **retired
   executor** under `AGENTS.md` §7 (Muse and GLM are inactive). If it had ever run, it would
   have demanded a retired executor's model id as the expected value.

Replaced by `test_session_stats_aggregates_a_multi_turn_export`, which is hermetic, exercises
the aggregation over a realistic multi-turn export, and uses an active executor. The retired
model id was also removed from the file's `_export_fixture()` so no stale executor name
remains as test data. `tests/foundry/test_telemetry.py` now reports **12 passed, 0 skipped**
instead of 11 passed, 1 skipped.

Coverage went **up**, not down. The docstring records what was replaced and why.

---

## 5. A regression guard, proven to work

The routing migration in PR #350 changed the executor policy in four canonical documents but
left `docs/foundry-execution/README.md` — the canonical Foundry index — describing the previous
routing. Nothing caught it.

`test_inactive_executors_are_declared_inactive_in_canonical_docs` did **not** cover that file.
Adding the file to the existing forbidden-phrase loop would have been a **false guarantee**: the
stale index said `"Space Bunny MAX default"` and `"explicit Muse XHIGH alternate"`, and neither
matches any phrase in that loop (`preferred and alternate`, `explicit alternate only`,
`Muse is an explicit alternate`, `supported alternate / continuation executor`).

Two discriminating assertions were added instead:

```python
index = (ROOT / "docs/foundry-execution/README.md").read_text()
assert "DeepSeek MAX default" in index
assert "Space Bunny MAX default" not in index
```

**Validated against the real bug, not just against the fix:** replaying the pre-fix index from
`72665dce` into the tree makes the test fail; restoring the fixed index makes it pass. A
regression test that has never been shown to fail on the bug is not evidence of anything.

---

## 6. Reviewed and deliberately unchanged

| Item | Why unchanged |
|---|---|
| `tests/foundry/test_drift.py:26` hardcodes `/home/moeen/code/mage-d3q6` | It is **environment-dependent, not permanently skipped** — it *runs here* (16 passed), because the path exists. Its fail-closed property is already covered hermetically at lines 71–90. Correcting an earlier classification of mine. Recorded, not altered |
| The 2 `httpx2` failures | Environmental; the dependency is declared. Installing packages is an operator decision |
| Any assertion strength | No assertion was weakened, relaxed, or removed. One test was replaced by a strictly stronger hermetic equivalent |

---

## 7. What a future session should take away

1. `pythonpath = ["src"]` is pytest-internal. It is not an install and not inherited.
2. Run the suite the way CI does, or expect 2 environmental failures.
3. A skipped test is not coverage. Verify that a test's fixture can actually occur.
4. Never assert a retired executor's identity as an expected value.
5. When adding a regression guard, **replay the bug** and confirm the test fails on it.

Companion documents: [`EVIDENCE_VOCABULARY_DECISION.md`](EVIDENCE_VOCABULARY_DECISION.md) ·
[`ENGINE_PIN_DIVERGENCE.md`](ENGINE_PIN_DIVERGENCE.md) ·
[`BRANCH_FORENSICS.md`](BRANCH_FORENSICS.md) ·
[`FOUNDRY_STATE_CONFORMANCE.md`](FOUNDRY_STATE_CONFORMANCE.md)
