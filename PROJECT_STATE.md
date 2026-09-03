# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work must remain fail-closed and preserve the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when all of the following are freshly runtime-verified for the exact WS-32 v1.0.2 XMage denominator: mandatory Tax-3 = 3/3 PASS; total denominator = 107/107 PASS with mismatch 0 and no imported historical PASS; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; hidden/privacy regressions PASS; deterministic RNG/replay PASS; unsupported production decision paths = 0; exact construction/digest/transaction evidence, source locks, checksums and CI artifacts exist; `WS39_FINAL_HANDOFF.md` is complete. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-A`

### COMPLETE / VERIFIED work packages

1. **Native XMage Commander-history remediation — COMPLETE / VERIFIED.**
   - Repo: `moeendres-png/mage`
   - Branch: `foundry/ws39-commander-history-state-restore`
   - Exact green commit: `7bde812727817723616c575759f39bfc4cda4607`
   - Exact green tree: `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
   - Retained base: commit `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`, tree `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`
   - Focused native `CommanderPlaysCountStateRestoreTest` and retained-base workflow are green.
   - Native watcher state is restored directly; no synthetic historical casts are emitted.

2. **Exact WS-39 Commander Lab engine/bridge build — COMPLETE / VERIFIED.**
   - Dedicated WS-39 workflow is pinned to the exact green XMage head/tree above.
   - Exact WS-32 source lock and materialization SHA are checked.
   - Exact native history test, qualification overlays, XMage build and bridge build have passed in CI.

3. **WS-32 contract-shape / denominator probe — COMPLETE / VERIFIED.**
   - Contract: `commander-lab.semantic-fixture-materialization/1.0.2`
   - Freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`
   - Freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
   - Canonical materialization digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
   - Materialization file SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
   - Exact XMage denominator: 107 unique fixture IDs.
   - Mandatory IDs are present: `WS05-CMD-TAX-2`, `WS05-CMD-TAX-4`, `WS05-CMD-PARTNER-TAX`.

### PARTIAL / FAILED / OPEN work packages

4. **Mandatory Tax-3 runtime — PARTIAL / FAILED (infrastructure, not established Rules defect).**
   - Latest investigated CI run: `33693783091`.
   - Latest investigated Tax-3 job: `100458157751`.
   - Earlier Python repository import-path failure was repaired by Commander Lab commit `f6c1db32ba57dd4584e51fa8a378a70193a064d0` (`WS39: ensure tax-3 runner imports repository modules`).
   - The next failure moved to Java runtime startup: `NoClassDefFoundError: mage/game/Game` while launching `org.commanderlab.xmage.XmageWs26QualificationMain` with only the bridge JAR on `-cp`.
   - Current diagnosis: qualification workflow runtime classpath is incomplete; this is not evidence of incorrect Commander-tax semantics.
   - Tax-3 status remains **NOT PASS** until 3/3 fresh runtime records pass.

5. **Repository quality / Ruff — UNKNOWN at this checkpoint.**
   - A prior run reported Ruff lint/format failures in new WS-39 Python files.
   - The latest quality job for the current branch head has not yet been re-read after the import-path fix. No PASS credit is granted.

6. **Fresh complete 107-record successor requalification — OPEN / NOT_RUN.**
   - It is gated by Tax-3 3/3 PASS.
   - Historical WS-34/WS-36 PASS results must not be imported.

7. **Terminal WS-39 handoff and provider qualification — OPEN.**
   - `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED` is not set.
   - `WS39_FINAL_HANDOFF.md` does not yet exist as a terminal validated handoff.

## Important decisions

- Commander cast history is native Rules-Core state owned by `CommanderPlaysCountWatcher`; the provider may import per-commander counts only. XMage derives player aggregates from native commander ownership.
- The provider/pilot must never calculate Commander tax. Tax evidence must come from XMage-native cost/legal-option/readback behavior.
- No fabricated historical events are permitted for restoration.
- Tax-3 must pass before the 107-record run is unlocked.
- No AF07 or Architecture Freeze claim may be made in WS-39.
- Draft PRs may remain open; no merges are authorized.

## Relevant evidence

- XMage exact green head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`.
- Commander Lab branch before this checkpoint commit: `f6c1db32ba57dd4584e51fa8a378a70193a064d0`, tree `a3ef7950b5b464ce0a716e1016f175634871d00a`.
- Commander Lab branch: `ws39/xmage-engine-remediation-requalification`.
- Draft Commander Lab PR: `#153`.
- Latest investigated failing runtime: run `33693783091`, job `100458157751`, Java `NoClassDefFoundError: mage/game/Game`.

## Changed files known in WS-39

- `.github/workflows/ws39-xmage-remediation.yml`
- `.github/workflows/ci.yml`
- `candidate-qualification/ws39-xmage-successor/apply_ws39_provider_overlay.py`
- `candidate-qualification/ws39-xmage-successor/canonical_v102.py`
- `candidate-qualification/ws39-xmage-successor/contract_probe.py`
- WS-39 Tax-3 qualification files under `candidate-qualification/ws39-xmage-successor/` (exact current listing must be read before editing).
- XMage production/test/workflow files in the isolated WS-39 branch.

## Tests already executed

- XMage retained-base focused native Commander-history tests: **PASS**.
- Exact Commander Lab WS-39 contract-shape probe: **PASS**.
- Exact XMage + bridge build with overlays: **PASS**.
- Mandatory Tax-3: **FAILED / PARTIAL**, currently stopped at bridge Java runtime classpath startup.
- Fresh 107/107: **NOT_RUN**.

## Known errors

1. Tax-3 Java runtime command does not include the XMage dependency graph; current observed failure is `NoClassDefFoundError: mage/game/Game`.
2. Latest Ruff quality status is not yet verified for current head.

## Exact next action

1. Read the current WS-39 qualification directory, current CI workflow and latest `quality` diagnostics.
2. Locate an already-working project-native XMage bridge runtime classpath pattern (or derive it from `engine-bridge/pom.xml` without changing rules semantics).
3. Repair only the qualification/runtime invocation and any exact Ruff diagnostics.
4. Run/observe fresh CI; require mandatory Tax-3 = 3/3 PASS before proceeding.
5. On Tax-3 PASS, execute the exact fresh 107-record successor requalification and remediate bounded provider/setup defects until the terminal contract is either fully PASS or an objective non-remediable blocker is proven.
6. Persist a checkpoint after each completed package.

## Completion status

`TASK_COMPLETE = NO`

Reason: mandatory Tax-3 is not yet 3/3 PASS and fresh 107/107 has not yet been executed.
