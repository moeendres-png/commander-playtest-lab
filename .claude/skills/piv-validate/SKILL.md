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

### 6a. Forge suites in a cloud container (any Forge test change)

- Desktop + bridge suite (about 3 minutes per JDK). `forge-gui-mobile` cannot build here
  (jitpack.io is blocked), so never build the whole reactor:
  `LANG=C.UTF-8 xvfb-run -a mvn -B -ntp -o -pl forge-gui-desktop,forge-protocol2-bridge -am test`
- Targeted classes: add `-Dtest='CardDb*,DeckRecognizerTest' -Dsurefire.failIfNoSpecifiedTests=false`.
- Known environmental failures. Record them as ENVIRONMENTAL with the proof, never as credit
  and never as this change's failure:
  - `NetworkPlayIntegrationTest.testServerStartAndStop`: port 55556 is held by the sandbox.
    Prove it with a plain socket bind of 55556.
  - `forge.PanelTest` "Cannot instantiate" on JDK 17: the container's JDK 17 is the headless
    package (no `libawt_xawt.so`). JDK 21 there has full AWT.
- `D24ExecutionGuardTest` pins the declared/enabled test denominators. Adding or enabling a
  test method changes them on purpose; update them in the same commit.
- D17 controls (`.github/qualification` in the Forge fork) need `D17_REQUIRE_TOOLCHAIN=1` and
  the sandbox users. The mutation check runs longer than 30 minutes, so start it in the
  background with a 2-hour timeout.

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
