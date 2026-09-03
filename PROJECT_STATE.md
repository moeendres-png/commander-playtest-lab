# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when all of the following are freshly runtime-verified for the exact WS-32 v1.0.2 XMage denominator: mandatory Tax-3 = 3/3 PASS; total denominator = 107/107 PASS with mismatch 0 and no imported historical PASS; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; hidden/privacy regressions PASS; deterministic RNG/replay PASS; unsupported production decision paths = 0; exact construction/digest/transaction evidence, source locks, checksums and CI artifacts exist; `WS39_FINAL_HANDOFF.md` is complete. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-D`

### COMPLETE / VERIFIED work packages

1. **Native XMage Commander-history remediation — COMPLETE / VERIFIED.**
   - Repo: `moeendres-png/mage`
   - Branch: `foundry/ws39-commander-history-state-restore`
   - Exact green commit: `7bde812727817723616c575759f39bfc4cda4607`
   - Exact green tree: `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`
   - Retained base: commit `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`, tree `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`
   - Focused native `CommanderPlaysCountStateRestoreTest` and retained-base workflow are green.
   - Native watcher state is restored directly; no synthetic historical casts are emitted.

2. **Exact WS-39 Commander Lab engine/bridge prerequisites — COMPLETE / VERIFIED.**
   - Exact WS-32 source lock and materialization SHA are checked.
   - Dedicated exact job now installs the Commander-Lab package before runtime execution.
   - At Commander Lab head `91a7101799dad2dfb8415f70fd6bdb056327559f`, CI run `33761476508`, job `100668967454`, the following are fresh PASS: project dependency installation; contract probe; native Commander-history test; qualification overlays; exact XMage build; bridge verify; runtime dependency materialization; evidence sealing/upload.
   - This closes both earlier pre-result infrastructure defects: missing Python project dependencies and thin-JAR runtime classpath.

3. **WS-32 contract-shape / denominator probe — COMPLETE / VERIFIED.**
   - Contract: `commander-lab.semantic-fixture-materialization/1.0.2`
   - Freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`
   - Freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
   - Canonical materialization digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
   - Materialization file SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
   - Exact XMage denominator: 107 unique fixture IDs.
   - Mandatory IDs are present: `WS05-CMD-TAX-2`, `WS05-CMD-TAX-4`, `WS05-CMD-PARTNER-TAX`.

4. **Tax-3 runner import-path and dependency remediations — COMPLETE / VERIFIED.**
   - Commit `40da35e859cd5615dfa2170230b6c4ca6c9058e6` repaired repository `src` imports and local Ruff B023 in `run_tax3.py`.
   - Commit `91a7101799dad2dfb8415f70fd6bdb056327559f` added `python -m pip install -e .` to the dedicated exact runtime job.
   - The latest exact run progresses through Python imports and executes all three Tax-3 records.

5. **Qualification bridge runtime classpath materialization — COMPLETE / VERIFIED as infrastructure.**
   - Commit `abf79e26af773abedf4fb9deac62d76d4975cf19` adds the bridge JAR plus `engine-bridge/target/dependency/*` runtime classpath and materializes runtime dependencies.
   - The dependency step is fresh PASS in CI run `33761476508`.

6. **Fail-safe Tax-3 observability — COMPLETE / VERIFIED.**
   - Commit `0605d7d94d77a7e65180f40d236063cfbadc8c85` persists stdout, stderr and exit code even when the Tax-3 gate fails.
   - This observability produced both the earlier import diagnosis and the current record-level deck-import diagnosis.

7. **Latest Tax-3 record-level evidence — COMPLETE / VERIFIED diagnosis, runtime gate still FAIL.**
   - CI run: `33761476508`.
   - Exact WS-39 job: `100668967454`.
   - Exact Commander Lab head: `91a7101799dad2dfb8415f70fd6bdb056327559f`, tree `dbe35496bfafe37fe2b3200564ea01041d43bde8`.
   - Artifact: `ws39-exact-engine-contract-91a7101799dad2dfb8415f70fd6bdb056327559f`, artifact id `9895854529`, digest `sha256:59829ce445bea2363b240c3cabf4e3cfc4621359228e5d94edcda681ddcebef8`.
   - `WS39_TAX3_RESULTS.json` exists and contains exactly three fresh rows; historical PASS import is false.
   - All three rows are fail-closed before semantic transaction execution because the qualification import deck is not a legal Commander deck:
     - `WS05-CMD-TAX-2`: `INVALID_DECK_SIZE`, observed 6 cards.
     - `WS05-CMD-TAX-4`: `INVALID_DECK_SIZE`, observed 6 cards.
     - `WS05-CMD-PARTNER-TAX`: `INVALID_DECK_SIZE`, observed 3 cards.
   - Exact record digests remain bound:
     - Tax-2: `cdbc7107328befdd3189b70704e33f9aa6851b116b4bef0c345e470140bc5ebf`
     - Tax-4: `9dab6dfef8e3c03b35a70196ec1f457697a1ddfd75f6d07de6e82f4cb833ed01`
     - Partner-Tax: `95b16c730b203d945892fbed3cb23105627f6afa62156a50b625573dc2f55d4c`
   - Classification: **qualification import-scaffolding defect**, not an established Commander-tax or XMage Rules defect.

8. **WS-39 security — fresh PASS at latest head.**
   - CI run `33761476508`, security job `100668967800` completed SUCCESS including dependency audit, SBOM and license report.

9. **107-record implementation audit — IN PROGRESS, materially advanced.**
   - Exact denominator remains 107: player_count 4; pilot_boundary 17; negative_boundary 7; hidden_information 20; replay_rng 5; micro_rules 17; CARD_02 1; multiplayer_commander 36.
   - Historical WS-34 runtime path actually exercised at most 32 records and left 75 setup-blocked; historical results cannot be imported.
   - WS-36 native procedures reduce the future full-run implementation to 63 reusable native operations across 47 recurring operation sets, rather than 107 unrelated scripts.
   - Existing v1.0.1 native executors for natural start, HIDDEN_01/02, MICRO_STACK, MICRO_REPLACEMENT and WS05-MP-COMBAT-4 are reusable as implementation provenance only; all v1.0.2 credit must be freshly executed.

### PARTIAL / FAILED / OPEN work packages

10. **Mandatory Tax-3 runtime — PARTIAL / 0-of-3 credit.**
   - The runner now creates record-level results but all three fail before semantic transaction execution on legal-deck import validation.
   - No Tax-3 PASS credit is granted yet.

11. **Repository quality — PARTIAL.**
   - Mypy is fresh PASS at the latest investigated head.
   - Generic repository-wide Ruff lint/format still contains inherited historical qualification-file debt. Final WS-39 credit requires unchanged-config verification that all WS-39-modified Python files are clean; project-wide configuration must not be weakened.

12. **Fresh complete 107-record successor requalification — OPEN / NOT_RUN.**
   - Gated by mandatory Tax-3 3/3 PASS.
   - Historical WS-34/WS-36 PASS results must not be imported.
   - Complete fresh runtime requires provider-native setup/transaction executors for the frozen v1.0.2 native procedure families; requested-state echo alone is not runtime proof.

13. **Terminal WS-39 handoff and provider qualification — OPEN.**
   - `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`.
   - `WS39_FINAL_HANDOFF.md` does not yet exist as a terminal validated handoff.

## Important decisions

- Commander cast history is native Rules-Core state owned by `CommanderPlaysCountWatcher`; the provider may import per-commander counts only. XMage derives player aggregates from native commander ownership.
- The provider/pilot must never calculate Commander tax. Tax evidence must come from XMage-native cost/legal-option/readback behavior.
- No fabricated historical events are permitted for restoration.
- Qualification bootstrap decks may contain inert filler only to satisfy XMage's native legal Commander import requirement. Filler must not alter the frozen requested semantic state and receives no semantic credit.
- Tax-3 must pass before the 107-record run is unlocked.
- No unsupported production-reachable discretionary-decision fallback is acceptable.
- No AF07 or Architecture Freeze claim may be made in WS-39.
- Draft PRs may remain open; no merges are authorized.

## Source locks

- XMage exact green head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`.
- Commander Lab latest runtime-evidenced head/tree: `91a7101799dad2dfb8415f70fd6bdb056327559f` / `dbe35496bfafe37fe2b3200564ea01041d43bde8`.
- Commander Lab branch: `ws39/xmage-engine-remediation-requalification`.
- Draft Commander Lab PR: `#153`.

## Tests already executed

- XMage retained-base focused native Commander-history tests: **PASS**.
- Exact Commander Lab WS-39 contract-shape probe: **PASS**.
- Exact XMage + bridge build with overlays: **PASS**.
- Commander Lab runtime dependency installation: **PASS**.
- Bridge runtime dependency materialization: **PASS**.
- Security: **PASS**.
- Mypy: **PASS**.
- Mandatory Tax-3: **0/3 PASS; 3/3 fail-closed at native deck import due undersized qualification bootstrap decks**.
- Fresh 107/107: **NOT_RUN**.

## Known errors

1. `canonical_v102.py` currently builds import decks only from frozen semantically relevant objects. That produces 6/6/3-card Commander decks for the mandatory Tax records, which XMage correctly rejects before runtime setup.
2. Generic repository-wide Ruff has inherited historical debt; WS-39-local cleanliness must be proven separately without weakening configuration.
3. Full 107 requires native setup/transaction coverage beyond the historical WS-34 core9/terminal23 paths.
4. Tax-3 `candidate_commit` currently derives from `GITHUB_SHA`, which on PR execution may be the merge-ref SHA; terminal evidence must additionally bind the exact checked-out provider head already recorded in `PROVIDER_COMMIT.txt`.

## Exact next action

1. In `candidate-qualification/ws39-xmage-successor/canonical_v102.py`, pad each qualification import deck with inert `Mountain` cards so `len(mainboard) + len(commander_names) == 100`, failing closed if frozen semantic mainboard demand itself exceeds the legal mainboard capacity. Do not add filler to the frozen scenario or requested-state projection.
2. Re-run exact-head CI and inspect the fresh three-row Tax-3 evidence; remediate only the next concrete provider/setup/transaction defect.
3. Repeat until mandatory Tax-3 = 3/3 fresh PASS, then checkpoint immediately with exact head/tree/run/job/artifact/checksums and exact provider-head binding.
4. Execute the exact fresh 107-record successor requalification using reusable native operation-family executors; add only provider-native setup/transaction adapters required by frozen records, failing closed on unsupported semantics.
5. Seal final checksums/evidence, verify WS-39-local quality under unchanged configuration, write `WS39_FINAL_HANDOFF.md`, and update this file terminally.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: mandatory Tax-3 is not yet 3/3 PASS and fresh 107/107 has not yet been executed.
