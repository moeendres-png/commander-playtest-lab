# PROJECT_STATE — WS-39

## Current assignment

Complete **WS-39 — XMage native Commander-history state restoration + complete WS-32 v1.0.2 successor requalification** for `moeendres-png/commander-playtest-lab` and the isolated `moeendres-png/mage` WS-39 fork. Work remains fail-closed and preserves the Rules-Core / pilot boundary.

## Target state

WS-39 is COMPLETE only when all of the following are freshly runtime-verified for the exact WS-32 v1.0.2 XMage denominator: mandatory Tax-3 = 3/3 PASS; total denominator = 107/107 PASS with mismatch 0 and no imported historical PASS; AF04 24/24; AF05 20/20; AF06 17/17; AF08 36/36; AF09 5/5; CARD_02 PASS; hidden/privacy regressions PASS; deterministic RNG/replay PASS; unsupported production decision paths = 0; exact construction/digest/transaction evidence, source locks, checksums and CI artifacts exist; `WS39_FINAL_HANDOFF.md` is complete. AF07 and Architecture Freeze are out of scope and must not be claimed.

## LAST_CONFIRMED_CHECKPOINT

`WS39-CHECKPOINT-2026-09-03-E`

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
   - Dedicated exact job installs the Commander-Lab package before runtime execution.
   - Runtime bridge classpath contains the bridge JAR plus copied Maven runtime dependencies.
   - At current runtime-evidenced head `09bf93a6c2d3736f87d0f896fbed16aad2ed12ff`, CI run `33762568284`, job `100672262008`, the following are fresh PASS: dependency installation; contract probe; native Commander-history test; all qualification overlays; exact XMage build; bridge verify; bridge runtime dependency materialization; evidence sealing/upload.

3. **WS-32 immutable authority — COMPLETE / VERIFIED.**
   - Contract: `commander-lab.semantic-fixture-materialization/1.0.2`
   - Freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`
   - Freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
   - Canonical materialization digest: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`
   - Materialization file SHA256: `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`
   - Exact XMage denominator: 107 unique fixture IDs.

4. **Tax-3 runner infrastructure remediations — COMPLETE / VERIFIED.**
   - `40da35e859cd5615dfa2170230b6c4ca6c9058e6`: repository source import path + Ruff B023 repair.
   - `abf79e26af773abedf4fb9deac62d76d4975cf19`: runtime bridge dependency classpath.
   - `0605d7d94d77a7e65180f40d236063cfbadc8c85`: persistent Tax-3 stdout/stderr/exit-code diagnostics.
   - `91a7101799dad2dfb8415f70fd6bdb056327559f`: install Commander-Lab declared Python dependencies in exact runtime job.
   - `abf949fb63d06bf06717ddd0da335f4d880e4120`: legal-size qualification bootstrap deck padding.
   - `09bf93a6c2d3736f87d0f896fbed16aad2ed12ff`: Tax-3 result binds actual checked-out provider commit/tree instead of relying on PR merge-ref `GITHUB_SHA`.

5. **Latest Tax-3 record-level evidence — COMPLETE / VERIFIED diagnosis, runtime gate still FAIL.**
   - CI run: `33762568284`.
   - Exact WS-39 job: `100672262008`.
   - Exact checked-out Commander Lab head: `09bf93a6c2d3736f87d0f896fbed16aad2ed12ff`.
   - Exact checked-out tree: `f2953cbcee2ac9ca8742043e7a4ed73babcf6c80`.
   - Artifact: `ws39-exact-engine-contract-09bf93a6c2d3736f87d0f896fbed16aad2ed12ff`, artifact id `9896365627`, artifact digest `sha256:4deed723b26f280071733f2791de0236d3b78ff0674b8fcea5a710c250b8e279`.
   - `WS39_TAX3_RESULTS.json` contains exactly three fresh rows; `historical_pass_imported = false`.
   - The legal deck-size defect is closed: validation progresses to Commander color-identity checking.
   - All three rows fail closed because semantically requested `Grizzly Bears` was incorrectly included in the qualification **import deck**, while Rograkh/Kediss Commander identities permit red only. Exact common error: `COMMANDER_VALIDATION_FAILED ... Grizzly Bears ... Invalid color identity (includes {G}, but your commander(s) allow only {R})`.
   - Classification: **qualification import-scaffolding defect**, not an established XMage Rules or Commander-tax defect.
   - Correct architecture is already available in the applied native-state overlay: the imported Commander deck is only a legal bootstrap; frozen semantic objects absent from it are materialized as real XMage cards through `CardRepository` + `Game.loadCards`, then placed/validated natively by the scenario loader.

6. **Current security and general test status — VERIFIED.**
   - CI run `33762568284`: security SUCCESS.
   - Mypy SUCCESS; pytest SUCCESS; compile SUCCESS; secret scan SUCCESS; wheel build SUCCESS.
   - Generic repository-wide Ruff lint/format still fails inherited historical qualification debt.

7. **WS-39-local quality audit — PARTIAL but bounded.**
   - Last fully downloaded quality artifact showed 0 Ruff lint findings in WS-39 files.
   - Five WS-39 Python files were still `ruff format` dirty; they must be formatted before terminal closure under unchanged configuration.

8. **107-record implementation audit — materially advanced.**
   - Denominator remains 107: player_count 4; pilot_boundary 17; negative_boundary 7; hidden_information 20; replay_rng 5; micro_rules 17; CARD_02 1; multiplayer_commander 36.
   - Historical WS-34 exercised at most 32 runtime paths and left 75 setup-blocked; historical PASS cannot be imported.
   - WS-36 native procedures reduce the full-run implementation surface to 63 reusable native operations across 47 recurring operation sets.
   - Existing v1.0.1 executors for natural start, HIDDEN_01/02, MICRO_STACK, MICRO_REPLACEMENT and WS05-MP-COMBAT-4 are implementation provenance only; v1.0.2 requires fresh execution.

### PARTIAL / FAILED / OPEN work packages

9. **Mandatory Tax-3 runtime — PARTIAL / 0-of-3 credit.**
   - All three records now reach native Commander deck validation.
   - They fail before state load/semantic transaction solely because semantic test cards were included in the bootstrap deck and violate Commander color identity.
   - No runtime PASS credit is granted yet.

10. **Fresh complete 107-record successor requalification — OPEN / NOT_RUN.**
   - Gated by mandatory Tax-3 3/3 PASS.
   - Requested-state echo alone is not runtime proof; each credited record needs native construction/transaction evidence.

11. **Terminal WS-39 handoff and provider qualification — OPEN.**
   - `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`.
   - `WS39_FINAL_HANDOFF.md` is not yet terminal.

## Important decisions

- Commander cast history is native Rules-Core state owned by `CommanderPlaysCountWatcher`; provider imports per-commander counts only and XMage derives player aggregates.
- Provider/pilot never calculates Commander tax; tax evidence must come from XMage-native cost/legal-option/readback behavior.
- No fabricated historical events are permitted.
- Qualification bootstrap decks are **not** frozen semantic state. They exist only to satisfy XMage's native Commander game/deck initialization and must be legal, inert and semantically excluded.
- Frozen semantic cards must be materialized independently through native XMage state-loader primitives and validated against the frozen state.
- Tax-3 must pass before 107 execution is unlocked.
- No unsupported production-reachable discretionary-decision fallback is acceptable.
- No AF07 or Architecture Freeze claim may be made in WS-39.
- No merges are authorized.

## Source locks

- XMage exact green head/tree: `7bde812727817723616c575759f39bfc4cda4607` / `a44f32e9d34109ac3f272494f0e8eb9ea3e6280c`.
- Commander Lab latest runtime-evidenced head/tree: `09bf93a6c2d3736f87d0f896fbed16aad2ed12ff` / `f2953cbcee2ac9ca8742043e7a4ed73babcf6c80`.
- Commander Lab branch: `ws39/xmage-engine-remediation-requalification`.
- Draft Commander Lab PR: `#153`.

## Tests already executed

- Native XMage Commander-history focused tests: **PASS**.
- WS-32 contract shape/source locks: **PASS**.
- XMage build + qualification bridge: **PASS**.
- Python project dependency installation: **PASS**.
- Runtime classpath materialization: **PASS**.
- Security: **PASS**.
- Mypy/pytest/compile/secret scan/wheel: **PASS**.
- Mandatory Tax-3: **0/3 PASS; 3/3 fail closed at Commander color-identity validation of the bootstrap deck**.
- Fresh 107/107: **NOT_RUN**.

## Known errors

1. `canonical_v102.py` currently carries frozen non-command semantic identities into the bootstrap `mainboard`. This is architecturally unnecessary because the native state loader can materialize those cards independently, and it can make the bootstrap deck illegal under Commander color identity.
2. Generic repository-wide Ruff has inherited historical debt; WS-39-local formatting remains to be closed without weakening configuration.
3. Full 107 requires additional native setup/transaction execution coverage after Tax-3.

## Exact next action

1. Change WS-39 qualification bootstrap deck construction so the import mainboard contains only a universally Commander-legal inert Basic Land (`Wastes`), with count `100 - number_of_commanders`. Do **not** include frozen semantic non-command cards in the imported deck and do not add filler to the scenario/requested-state projection.
2. Re-run exact-head Tax-3; inspect all three fresh records and remediate only the next concrete provider/setup/transaction defect.
3. Repeat to Tax-3 3/3 fresh PASS and checkpoint immediately.
4. Execute the full exact 107-record v1.0.2 requalification with native operation-family executors and no historical PASS import.
5. Close WS-39-local Ruff formatting under unchanged configuration, seal checksums/evidence, write `WS39_FINAL_HANDOFF.md`, and update this state terminally.

## Completion status

`TASK_COMPLETE = NO`
`WS39_STATUS = PARTIAL`
`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

Reason: mandatory Tax-3 is not yet 3/3 PASS and fresh 107/107 has not yet been executed.
