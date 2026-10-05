---
name: piv-validate
description: Runs the Commander Playtest Lab validation suite (ruff, ruff format, mypy, the qualification and unit tests, and the engine bridge test suites when Java changed) and reports one PASS/FAIL verdict. Use before committing, before pushing to a PR, or after finishing a chunk of work.
---

# Validate (Commander Playtest Lab)

Run every check below from the repository root (or the worktree root). Keep going after a failure so the
report covers everything; capture the output of any command that fails. Do not fix anything here.

Use a Python >= 3.12 virtualenv; delete `src/*.egg-info` after an editable install. Engine builds are
offline against a local Maven repository (`-Dmaven.repo.local=…`, `LAB_M2_REPO` in `lab-ops`).

## 1. Lint and format

```bash
ruff check src tests
ruff format --check src tests
```

## 2. Type check

```bash
mypy <every changed module under src/>
```
`mypy src/` also reports long-standing errors in `agents/openai_workflow.py`, `api/tool_server.py` and
`cli/app.py` (optional dependencies); judge only the modules the change touches.

## 3. Python tests

```bash
python -m pytest -q tests/qualification
python -m pytest -q tests/unit -p no:cacheprovider --continue-on-collection-errors
```
Commit (or WIP-commit) first: unit tests that hash the tracked tree fail on a dirty worktree
("stale canonical inputs rejected"). Modules needing optional deps (e.g. fastapi) fail to collect locally;
compare the failure set with main's instead of reading it as a regression.

## 4. Hash manifests (when anything under `qualification/` changed)

```bash
python scripts/regenerate_hash_manifests.py   # then re-run tests/qualification/test_ws17_qualification.py
```

## 5. XMage engine bridge (when `engine-bridge/` changed)

```bash
cd engine-bridge && mvn -o -B test -Dmaven.repo.local=$LAB_M2_REPO
```

## 6. Forge bridge (when working in the Forge repository's `forge-protocol2-bridge/`)

```bash
xvfb-run -a mvn -o -B test -pl forge-protocol2-bridge -am -Dcheckstyle.skip \
  -Dmaven.repo.local=$FORGE_M2_REPO -Dtest='forge.bridge.**' -Dsurefire.failIfNoSpecifiedTests=false
```

## 7. Real engines (when a row's behaviour can change)

`lab-ops` `scripts/real_rows.py` re-runs only the affected rows against the real producers (LOCAL_OBSERVED,
never credit). Run the Java suites and long engine runs in the background.

## Summary

One line per check with a ✅ or ❌, then **Overall: PASS or FAIL**. For every ❌, include the failing
command and the relevant output.

- `ci-definition-integrity-shadow` is red by design (CI-02); it is a CI check, not part of this local suite.
- A green suite is not Qualification PASS: credit comes only from PB-03 on an exact head plus a sealed epoch.
- A checker that cannot fail is worthless: when changing this list, break something on purpose once and
  confirm it reports ❌.
