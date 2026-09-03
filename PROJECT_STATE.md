# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when all of the following are freshly runtime-verified for the exact WS-32 v1.0.2 XMage denominator: mandatory Tax-3 = 3/3 PASS; total denominator = 107/107 PASS with mismatch 0 and no imported historical PASS; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; hidden/privacy regressions PASS; deterministic RNG/replay PASS; unsupported production decision paths = 0; exact construction/digest/transaction evidence, source locks, checksums and CI artifacts exist; `WS39_FINAL_HANDOFF.md` is complete. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-B`

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
   - Exact WS-32 source lock and materialization SHA are checked.
   - Exact native history test, qualification overlays, XMage build and bridge build have passed in CI.
   - XMage runtime dependency materialization is now explicit in `.github/workflows/ci.yml` via Maven `dependency:copy-dependencies` and was observed green at Commander Lab commit `abf79e26af773abedf4fb9deac62d76d4975cf19`.

3. **WS-32 contract-shape / denominator probe — COMPLETE / VERIFIED.**
   - Contract: `commander-lab.semantic-fixture-materialization/1.0.2`
   - Freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`
   - Freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
   - Canonical materialization digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
   - Materialization file SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
   - Exact XMage denominator: 107 unique fixture IDs.
   - Mandatory IDs are present: `WS05-CMD-TAX-2`, `WS05-CMD-TAX-4`, `WS05-CMD-PARTNER-TAX`.

4. **Tax-3 runner repository import-path remediation — COMPLETE / VERIFIED.**
   - Commander Lab commit `40da35e859cd5615dfa2170230b6c4ca6c9058e6` repairs repository `src` imports and the local Ruff B023 issue in `run_tax3.py`.
   - Exact-head CI progressed beyond the previous Python import failure.

5. **Qualification bridge runtime classpath materialization — COMPLETE / VERIFIED as an infrastructure step.**
   - Commander Lab commit `abf79e26af773abedf4fb9deac62d76d4975cf19`, tree `8f40de7f81cdfd9b7ba343752569ab7d0bb7b994`.
   - Runtime classpath includes the bridge JAR plus `engine-bridge/target/dependency/*`.
   - The dependency-materialization step passed in CI run `33747687690`.
   - This closes the previously observed thin-JAR `NoClassDefFoundError: mage/game/Game` setup defect as the known checkpoint blocker; it does **not** itself grant Tax-3 semantic credit.

### PARTIAL / FAILED / OPEN work packages

6. **Mandatory Tax-3 runtime — PARTIAL / PRE-RESULT FAILURE.**
   - Latest exact-head Commander Lab commit examined: `abf79e26af773abedf4fb9deac62d76d4975cf19`.
   - Latest investigated CI run: `33747687690`.
   - Exact WS-39 job reached: native history PASS, overlays PASS, XMage build PASS, bridge verify PASS, runtime dependency materialization PASS.
   - `Execute mandatory Tax-3 runtime gate` still exits non-zero.
   - No `WS39_TAX3_RESULTS.json` is produced, so no record-level semantic PASS/FAIL is established.
   - Current classification: **runner/runtime pre-result failure after classpath materialization**, not an established Magic Rules defect.
   - Tax-3 remains 0/3 credited until all three records produce fresh PASS results.

7. **Repository quality — PARTIAL.**
   - Mypy, compile/tests and security checks observed green in the investigated quality run.
   - `run_tax3.py` B023 was repaired at `40da35e8…`.
   - Generic repository Ruff lint/format still contains inherited historical qualification-file debt; final WS-39 quality credit requires exact verification that all WS-39-modified files are clean without weakening project-wide quality configuration.

8. **Fresh complete 107-record successor requalification — OPEN / NOT_RUN.**
   - Gated by mandatory Tax-3 3/3 PASS.
   - Historical WS-34/WS-36 PASS results must not be imported.

9. **Terminal WS-39 handoff and provider qualification — OPEN.**
   - `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`.
   - `WS39_FINAL_HANDOFF.md` does not yet exist as a terminal validated handoff.

## Important decisions

- Commander cast history is native Rules-Core state owned by `CommanderPlaysCountWatcher`; the provider may import per-commander counts only. XMage derives player aggregates from native commander ownership.
- The provider/pilot must never calculate Commander tax. Tax evidence must come from XMage-native cost/legal-option/readback behavior.
- No fabricated historical events are permitted for restoration.
- Tax-3 must pass before the 107-record run is unlocked.
- No unsupported production-reachable discretionary-decision fallback is acceptable.
- No AF07 or Architecture Freeze claim may be made in WS-39.
- Draft PRs may remain open; no merges are authorized.

## Source locks

- XMage exact green head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`.
- Commander Lab latest verified pre-checkpoint head/tree: `abf79e26af773abedf4fb9deac62d76d4975cf19` / `8f40de7f81cdfd9b7ba343752569ab7d0bb7b994`.
- Commander Lab branch: `ws39/xmage-engine-remediation-requalification`.
- Draft Commander Lab PR: `#153`.

## Tests already executed

- XMage retained-base focused native Commander-history tests: **PASS**.
- Exact Commander Lab WS-39 contract-shape probe: **PASS**.
- Exact XMage + bridge build with overlays: **PASS**.
- Runtime dependency materialization: **PASS**.
- Mandatory Tax-3: **NOT PASS / PRE-RESULT FAILURE**; no result JSON yet.
- Fresh 107/107: **NOT_RUN**.

## Known errors

1. Tax-3 exits after all setup/build/classpath steps pass but before `WS39_TAX3_RESULTS.json` is written; exact stderr is not yet persisted by the workflow artifact.
2. Repository-wide Ruff has inherited historical debt; WS-39-local cleanliness must be proven separately without weakening configuration.

## Exact next action

1. Make the Tax-3 CI step fail-safe observable by persisting stdout, stderr and exit code under `artifacts/ws39-ci/` even when the runner exits before result creation.
2. Execute exact-head CI and inspect the newly persistent failure evidence.
3. Repair the concrete in-scope runner/provider/setup defect; repeat until mandatory Tax-3 = 3/3 fresh PASS.
4. Immediately checkpoint Tax-3 PASS.
5. Execute the exact fresh 107-record successor requalification and remediate bounded provider/setup defects until 107/107 fresh PASS or an objective non-remediable blocker is proven.
6. Seal final checksums/evidence, verify WS-39-local quality, write `WS39_FINAL_HANDOFF.md`, and update this file terminally.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: mandatory Tax-3 is not yet 3/3 PASS and fresh 107/107 has not yet been executed.
