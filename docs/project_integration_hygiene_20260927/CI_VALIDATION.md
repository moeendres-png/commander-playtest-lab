# WSR23 — CI / Validation

All validation below was run in `/home/moeen/code/wsr23-project-integration-hygiene` on branch
`wsr23/project-integration-hygiene-20260927`.

## 1. Why a dedicated environment

The ambient interpreter (`/home/moeen/.local`, Python 3.14.4) is missing three **declared**
dependencies — `typer` (a *core* dependency), `httpx2` and `pytest-asyncio` (both in the `dev`
extra). `pytest tests` there aborts collection on all three. That is an interpreter gap, not a
repository defect: all three are pinned in `requirements/lock.txt` (`typer==0.27.2`,
`httpx2==2.13.0`, `pytest-asyncio==1.4.0`) and `.github/workflows/ci.yml` installs that file.

Validation therefore reproduced CI's own install path exactly, in a venv **outside** the
worktree so the working tree stays clean:

```text
python3 -m venv /tmp/…/venv
pip install --require-hashes -r requirements/lock.txt      # exit 0
pip install --no-deps --no-build-isolation -e .
```

## 2. Results on current `main` (baseline, before any WSR23 change)

| Gate | Command | Result |
|---|---|---|
| Test suite | `pytest -q` | **1628 passed, 5 skipped, 0 failed** (213.21s) |
| Foundry subset | `pytest tests/foundry -q` | **437 passed, 1 skipped** |
| Lint | `ruff check` | **All checks passed** |
| Format | `ruff format --check` | **953 files already formatted** |
| Types | `mypy src/commander_lab` (strict) | **Success: no issues found in 261 source files** |

The 5 skips are pre-existing and each is environment- or history-bound, not broken:
`tests/differential/test_phase6_differential.py` (needs a configured XMage/Forge command),
`tests/foundry/test_telemetry.py` (no live export snapshot),
`tests/integration/test_forge_bridge_h4f_live.py` (needs `FORGE_SOURCE_DIR` with Java+Maven),
and two `tests/qualification/test_ws232_retention_predicates.py` skips whose own skip messages
state the successor residual-repin workstream owns current requalification.

**Conclusion: `main` has no CI defect to repair.** Remote `main` agrees — all six workflows
(`CI`, `Production Qualification`, `Release Artifacts`, `Exact Main Recovery`, `Windows Runtime
Hygiene`, `opencode`) report `success` at `613cd57b` and `60fc3c8a`.

## 3. Results on the WSR23 tip

| Gate | Command | Result |
|---|---|---|
| Test suite | `pytest -q` | see §4 |
| Foundry subset | `pytest tests/foundry -q` | see §4 |
| Lint / format | `ruff check`, `ruff format --check` | see §4 |
| Types | `mypy src/commander_lab` | see §4 |
| Compile | `python -m compileall -q src tests` | see §4 |
| State schema | `python tools/foundry/state.py --state … --workdir … --check-validated --fail-on-validated-problem` | see §4 |
| Worktree inventory | `python tools/foundry/worktree_inventory.py --workdir … --fail-on-duplicate-writer` | see §4 |

## 4. WSR23 change impact

WSR23's diff is **documentation and JSON inventory only** — no `.py`, no `.java`, no workflow,
no `pyproject.toml`, no lock file. Therefore:

- No Rules semantics are altered, and no qualification evidence is invalidated, so
  **no requalification is justified** (§20).
- `pytest`, `mypy` strict and `compileall` are expected to be bit-identical in behaviour to the
  baseline; they were re-run anyway rather than assumed.
- The only behavioural surface touched is prose in a governance document.

Exact per-gate output for the published tip is recorded in `PUBLICATIONS.md`.

## 5. Validation NOT performed, and why

- `FULL107`, XMage qualification matrices, Forge qualification matrices, and the WSR22 matrix
  were **not** run. WSR23 is not a qualification campaign and changed no qualification
  semantics; running them would add cost without adding information and risks colliding with
  the active WSR22 writer.
- No live XMage/Forge integration test was run; those tests are environment-gated in CI too and
  the engine checkouts are read-only to WSR23.
