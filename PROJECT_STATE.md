# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when all of the following are freshly runtime-verified for the exact WS-32 v1.0.2 XMage denominator: mandatory Tax-3 = 3/3 PASS; total denominator = 107/107 PASS with mismatch 0 and no imported historical PASS; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; hidden/privacy regressions PASS; deterministic RNG/replay PASS; unsupported production decision paths = 0; exact construction/digest/transaction evidence, source locks, checksums and CI artifacts exist; `WS39_FINAL_HANDOFF.md` is complete. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-C`

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
   - Exact native history test, qualification overlays, XMage build and bridge build pass at Commander Lab head `0605d7d94d77a7e65180f40d236063cfbadc8c85` in CI run `33760615072`.
   - XMage runtime dependency materialization via Maven `dependency:copy-dependencies` also passes in that run.

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

5. **Qualification bridge runtime classpath materialization — COMPLETE / VERIFIED as infrastructure.**
   - Commander Lab commit `abf79e26af773abedf4fb9deac62d76d4975cf19` adds the bridge JAR plus `engine-bridge/target/dependency/*` runtime classpath and materializes runtime dependencies.
   - The dependency step is fresh PASS again in CI run `33760615072`.

6. **Fail-safe Tax-3 observability — COMPLETE / VERIFIED.**
   - Commander Lab commit `0605d7d94d77a7e65180f40d236063cfbadc8c85`, tree `40f9d4b4ee7177231e7090db2af53ff69ffde219`.
   - CI run `33760615072`, exact job `100666009961` persisted `WS39_TAX3_STDOUT.log`, `WS39_TAX3_STDERR.log` and `WS39_TAX3_EXIT_CODE.txt` even though the gate failed.
   - Artifact: `ws39-exact-engine-contract-0605d7d94d77a7e65180f40d236063cfbadc8c85`, artifact id `9895489020`, artifact digest `sha256:4248359a2b385bb02b53f0013e12f706963d41ebbd9d327201943339826f6eb2`.

7. **Concrete current Tax-3 pre-result blocker identified — COMPLETE / VERIFIED diagnosis.**
   - Exit code: `1`.
   - Exact stderr terminates during Python import with `ModuleNotFoundError: No module named 'pydantic'`.
   - Import chain: `run_tax3.py` -> `run_ws26_gate.py` -> `commander_lab.engine.rules.full_game` -> `commander_lab.models.cards` -> `pydantic`.
   - `pyproject.toml` declares `pydantic>=2.10,<3` as a base project dependency.
   - Therefore the current blocker is a missing Commander-Lab package/dependency installation in the dedicated WS-39 CI job. It is **not** evidence of incorrect Commander-tax or XMage Rules semantics.

8. **WS-39 security job — fresh PASS at diagnostic head.**
   - CI run `33760615072`, security job `100666011444` completed SUCCESS including dependency audit, SBOM and license report.

### PARTIAL / FAILED / OPEN work packages

9. **Mandatory Tax-3 runtime — PARTIAL / PRE-RESULT FAILURE.**
   - No `WS39_TAX3_RESULTS.json` exists at diagnostic head because Python cannot import a declared project dependency.
   - Tax-3 remains 0/3 credited until all three exact records produce fresh PASS results.

10. **Repository quality — PARTIAL.**
   - Fresh Mypy PASS in run `33760615072`.
   - Generic repository-wide Ruff lint and format remain failing due inherited historical qualification-file debt. Final WS-39 credit requires unchanged-config verification that all WS-39-modified Python files are clean; configuration must not be weakened.

11. **Fresh complete 107-record successor requalification — OPEN / NOT_RUN.**
   - Gated by mandatory Tax-3 3/3 PASS.
   - Historical WS-34/WS-36 PASS results must not be imported.
   - Capability audit confirms historic WS-34 only had 32 runtime-ready records and 75 setup-blocked records; a complete WS-39 run therefore requires additional provider-native setup/transaction executors rather than replaying old terminal reports.

12. **Terminal WS-39 handoff and provider qualification — OPEN.**
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
- Commander Lab latest diagnostic head/tree: `0605d7d94d77a7e65180f40d236063cfbadc8c85` / `40f9d4b4ee7177231e7090db2af53ff69ffde219`.
- Commander Lab branch: `ws39/xmage-engine-remediation-requalification`.
- Draft Commander Lab PR: `#153`.

## Tests already executed

- XMage retained-base focused native Commander-history tests: **PASS**.
- Exact Commander Lab WS-39 contract-shape probe: **PASS**.
- Exact XMage + bridge build with overlays: **PASS**.
- Runtime dependency materialization: **PASS**.
- Security: **PASS**.
- Mypy: **PASS**.
- Mandatory Tax-3: **NOT PASS / PRE-RESULT IMPORT FAILURE** (`pydantic` not installed in dedicated job).
- Fresh 107/107: **NOT_RUN**.

## Known errors

1. Dedicated WS-39 exact job does not install the Commander-Lab package before executing `run_tax3.py`; declared dependency `pydantic` is therefore absent.
2. Repository-wide Ruff has inherited historical debt; WS-39-local cleanliness must be proven separately without weakening configuration.
3. Full 107 requires native setup/transaction coverage beyond the historical WS-34 core9/terminal23 paths.

## Exact next action

1. Add a minimal `python -m pip install -e .` step to the dedicated WS-39 exact job after Python setup; this installs the declared base dependencies without changing Rules behavior.
2. Execute exact-head CI, inspect `WS39_TAX3_RESULTS.json` and persistent logs, and remediate the next concrete defect if any.
3. Repeat until mandatory Tax-3 = 3/3 fresh PASS, then checkpoint immediately.
4. Execute the exact fresh 107-record successor requalification; implement only provider-native setup/transaction adapters required by frozen records, failing closed on unsupported semantics.
5. Seal final checksums/evidence, verify WS-39-local quality, write `WS39_FINAL_HANDOFF.md`, and update this file terminally.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: mandatory Tax-3 is not yet 3/3 PASS and fresh 107/107 has not yet been executed.
