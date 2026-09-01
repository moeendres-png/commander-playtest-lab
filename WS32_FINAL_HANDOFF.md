# WS-32 FINAL HANDOFF — SUCCESSOR CONTRACT + SEMANTIC EXECUTABILITY FREEZE

## Source Lock

Repository: `moeendres-png/commander-playtest-lab`

Dedicated branch: `ws32/successor-semantic-executability-freeze`

Freshly verified historical/source authority used by WS-32:

- verified `main`: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- Finalist Convergence branch: `program/finalist-convergence-final`
- Finalist Convergence final handoff commit: `36b8e8f241c92fe9baea2ea718f910fd31f5cf23`
- Finalist Convergence evidence-lock commit: `20ca41a01132c3d79eee2184c52b2d56a614dff2`
- immutable predecessor v1.0.1 commit: `9a8b8f5f5961466514eae6103be2d227324a27a8`
- immutable predecessor v1.0.1 tree: `a9eee7458b9c39fd473ea54fdf58f5572cb46a1b`
- immutable predecessor v1.0.1 bundle digest: `ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee`
- protocol: `commander-lab.rules-service/1.1.0`
- WS31 authority head: `1bee87b9a0c4db90ecbf1f5374fae0732d6dd16e`
- WS31 authority aggregate digest: `d8337dc0a243fddbede3e9d2cec7b3938a1007970a23dea04855149fbfc55d5e`
- current official Comprehensive Rules lock retained after fresh verification: SHA256 `9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c`, effective `2026-08-07`

Canonical generated WS-32 freeze identity:

- freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`
- freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`
- parent implementation/evidence-fix commit: `d0b8519bfa53e01a3adfef6515e067c1c385d508`
- parent tree: `77583fde9c7107cc4a44b3b4a0793cdfb4a016b8`

Independent exact-freeze validation source:

- validation trigger commit: `62d7bd4fdeca8ecc2435d29f35f4abf095021e55`
- validation trigger tree: `f3438f9f01ef4e87d2b74361858bdfcc82e7e31c`
- the validation trigger modifies no file under `qualification/ws32`

The generated freeze commit/tree above are the execution-authoritative successor identity. Later documentation-only commits on this branch do not change the frozen bundle.

No merge to `main` was performed.

## Work Completed

WS-32 created and froze a new provider-neutral semantic materialization instead of mutating v1.0.1 in place.

Completed work includes:

- selected patch successor `commander-lab.semantic-fixture-materialization/1.0.2`;
- preserved all 135 fixture identities;
- preserved the frozen semantic obligation projection for all 135 records;
- repaired all 63 predecessor `SEMANTIC_EXECUTABILITY_DEFECT` records through provider-neutral native causal/state construction;
- hardened an additional set of legacy-v1.0.1-PASS records where the stricter successor linter exposed incomplete explicit stack, pregame, cost or expected-event causality metadata;
- implemented explicit `NATURAL_GAME_START` versus `NATIVE_STATE_LOAD` execution semantics;
- implemented requested-state digests and mandatory requested-vs-constructed validation for future provider credit;
- implemented strict native decision causality and fail-closed external decision handling;
- implemented complete stack target/mode/cost-state checks;
- implemented commander current-incarnation uniqueness, attack eligibility, pregame completeness, target-cardinality, historical-effect and hidden-default checks;
- materialized replay/RNG transactions;
- corrected and isolated `CARD_02`;
- repaired Starter-18 and Union denominators;
- created a complete 135-row change ledger and an exact 63-row defect-closure ledger;
- preserved exact predecessor defect codes, explanations and authority references in the 63-row closure evidence;
- formally resolved Terminal A/B/C by deprecation rather than invention;
- added deterministic rebuild and checksum CI;
- performed a second exact-freeze CI validation that generated no changed freeze outputs and uploaded independent evidence.

No Forge or XMage provider implementation was changed and no provider runtime qualification was performed in this workstream.

## Successor Contract Identity

Successor version:

`commander-lab.semantic-fixture-materialization/1.0.2`

Canonical generated freeze commit:

`038d0f38635eecee4e331c99af41f148de267a26`

Canonical generated freeze tree:

`0d160128119f2bad30b220a17c43419b50b7edbe`

Frozen bundle digest:

`61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b`

Bundle digest definition:

`SHA-256(canonical JSON of contract_version + sorted authoritative file rows)`

Supersession invariants:

- predecessor v1.0.1 is immutable;
- fixture ID set preserved: `true`;
- frozen obligation projection preserved: `135 / 135`;
- provider model embedded: `false`;
- repaired predecessor semantic defects: `63`;
- successor records: `135`;
- successor semantic-executable records: `135`;
- successor contract defects: `0`.

The protected obligation projection is:

- `fixture_id`;
- `fixture_family`;
- `frozen_contract_binding`;
- `card_authority_binding`;
- `expected_events`;
- `terminal_postconditions`.

Any change to this projection versus v1.0.1 is `OBLIGATION_DRIFT` and fails successor construction.

## Semantic-Executability Results

Predecessor v1.0.1:

- records: `135`;
- semantic executable: `72`;
- semantic defects: `63`.

Frozen successor v1.0.2:

- records: `135`;
- semantic executable: `135`;
- `CONTRACT_DEFECT`: `0`;
- global linter errors: `0`;
- terminal report status: `PASS`.

Exact report:

`qualification/ws32/SEMANTIC_EXECUTABILITY_REPORT_v1_0_2.json`

Report SHA256:

`35b61c23a6640abb2f7abb741f6a5040993e3d71cc29a68b7054a6fee70e5b07`

The successor linter is deliberately stricter than the v1.0.1 admission gate. It checks the entire 135-record corpus rather than allowing known non-Starter defects to remain frozen.

Starter successor manifest:

- identity count: `18`;
- semantic executable: `18`;
- SHA256: `2c0bc55eaf6bc0b7208b0677738be97733401e7fb729b7450a2995fad2ae557d`.

Critical successor gate:

- count: `81`;
- definition: Starter-18 union all 63 v1.0.1 defects union replay/RNG canonical records union corrected `CARD_02`;
- SHA256: `e78a096ae6baeb157f9362cb4218b7341415972d5d84bb697196e7b9f2127f87`.

This is **contract semantic-executability PASS only**. It is not provider runtime PASS and does not prove actual-card behavioral correctness on Forge or XMage.

## 63-Defect Closure Ledger

Exact artifact:

`qualification/ws32/DEFECT_63_CLOSURE_LEDGER_v1_0_2.json`

SHA256:

`b0ec68d0e80950810227e49ed84ec56993f62c69d41276f3b50f4ad081807bfe`

Terminal accounting:

- predecessor defects: `63`;
- closed semantic-executable: `63`;
- contract defects: `0`.

Recovered exact predecessor-defect family counts:

- Pilot: `7`;
- Negative/fail-closed: `6`;
- Micro rules: `3`;
- Actual-card records: `27`;
- WS05 multiplayer/Commander records: `20`.

Each of the 63 ledger rows now stores:

- `fixture_id`;
- `old_digest`;
- `new_digest`;
- predecessor status;
- exact predecessor `defect_codes`;
- full copied `predecessor_defects` including predecessor explanation and authority reference;
- correction description;
- `old_obligation_digest`;
- `new_obligation_digest`;
- `unchanged_obligation: true`;
- current authority references;
- `linter_result: PASS`.

The final builder enforces exactly 63 closure rows and fails if any closure row has an empty `defect_codes` array.

The complete 135-row change ledger is:

`qualification/ws32/PER_RECORD_CHANGE_LEDGER_v1_0_2.json`

SHA256:

`538028fdbb06c29c114705fd69afea0470e17333d89ecb53712addc93dc711a2`

All 135 rows preserve their old/new obligation digest equality.

## Union Denominator

Historical v1.0.1 Known-PASS Union-50 represented 50 historical identities but only 42 semantic-executable records plus 8 semantic defects.

The successor manifest is:

`qualification/ws32/KNOWN_PASS_UNION_50_v1_0_2.json`

Frozen successor result:

- historical identity count: `50`;
- exact runtime denominator count: `50`;
- semantic executable count: `50`;
- blocked count: `0`.

SHA256:

`beb2b95f5e3c1d961ae195059eac4224eab2d123517724a9fc99cd0e5a97ea5d`

Therefore the successor filename/count/executable status are no longer contradictory: the successor Union-50 is exactly `50 / 50` semantic-executable at the contract layer.

This grants no provider runtime credit by itself.

## Replay/RNG Contract

Canonical replay/RNG artifact:

`qualification/ws32/REPLAY_RNG_CANONICAL_TRANSACTIONS_v1_0_2.json`

Contract version:

`commander-lab.replay-rng-transaction/1.0.0`

SHA256:

`7d6d4424852316d8c73a96e745fc8279d46d2b73ee57c29f2415f69458878a8b`

Canonical transaction semantics require:

1. construct the requested state inside the provider Rules process and verify its requested-state digest;
2. natively begin a payable `Burn Down the House` cast;
3. externally select the semantic `create_devils` mode only from provider-offered legal options;
4. natively resolve the cast using explicit scripted priority passes where needed;
5. execute the declared library shuffle through the provider's native Rules RNG channel;
6. capture semantic DecisionTape, EventTape and normalized semantic checkpoints;
7. replay in a fresh process.

Frozen replay requirements:

- pilot randomness prohibited: `true`;
- native Rules RNG calls recorded: `true`;
- fresh-process replay required: `true`;
- same-provider semantic tapes must match: `true`;
- same-provider semantic checkpoints must match: `true`;
- cross-provider raw PRNG call-sequence equality required: `false`.

The contract therefore compares semantic reproducibility rather than requiring unrelated engines to share an internal PRNG call topology.

## `CARD_02`

Corrected successor artifact:

`qualification/ws32/CARD_02_v1_0_2.json`

SHA256:

`fc9b2b66f3338ae44a19d2242bcc9b620f124a26185b8b37414da153bbaa5502`

Materialization digest:

`ea0e59519a11db94b668db92eb05738b8c78b12a8295d8cdc668ef4311129b2c`

Requested-state digest:

`8553b0408730f93d6358706ab04cf4aa61666b32063767c9e3e37e7ee51cce56`

Frozen semantics:

- P1 current commander identity: `cmd:P1-A`;
- exactly one current P1 Rograkh incarnation exists;
- P1 Rograkh starts in command zone;
- prior command-zone cast count: `0`;
- printed cost: `{0}`;
- commander tax: `{0}`;
- action cost is payable with minimum mana/equivalent `0`;
- native operation: `NATIVE_CAST_COMMANDER`;
- native resolution: `NATIVE_RESOLVE_TOP_OF_STACK`;
- terminal P1 commander cast count: `1`;
- no commander-tax increment is charged for the first command-zone cast.

Construction-validation credit requires requested-state digest equality with the provider's normalized constructed state. Any mismatch means canonical setup unsupported and grants no runtime credit.

## Terminal A/B/C

Canonical project-source search did not recover normative definitions for `Terminal A`, `Terminal B` or `Terminal C`.

WS-32 does not invent new meanings merely to preserve historical labels.

Frozen disposition:

`FORMALLY_DEPRECATED`

Artifact:

`qualification/ws32/TERMINAL_ABC_SUPERSESSION_v1_0_2.json`

SHA256:

`670051dc212279b68415c1005c8c06549e8bceadaab742700a41c760c10d63fa`

Replacement:

- contract layer: `G32-01` through `G32-07`;
- provider/architecture layer: existing `AF00` through `AF11`.

Scope:

`PROJECT_WIDE_LABEL_DEPRECATION; DOES_NOT_CHANGE_AF00_AF11`

Historical Terminal A/B/C `UNKNOWN` values remain provenance only and grant no PASS credit.

## Changes

Primary implementation/tooling files added or changed on the WS-32 branch:

- `scripts/ws32_lint_semantic_v1_0_2.py`;
- `scripts/ws32_build_successor.py`;
- `scripts/ws32_build_successor_final.py`;
- `.github/workflows/ws32-freeze.yml`;
- `WS32_WORKSTREAM_CONTRACT.md`;
- `WS32_FREEZE_VALIDATION_MARKER.md` — explicitly non-normative; used only to force independent exact-freeze CI after the generated-output commit;
- `WS32_FINAL_HANDOFF.md`.

The diagnostic-only `.github/workflows/ws32-inspect.yml` was removed before the final freeze validation.

Frozen generated outputs under `qualification/ws32`:

- `CARD_02_v1_0_2.json` — `fc9b2b66f3338ae44a19d2242bcc9b620f124a26185b8b37414da153bbaa5502`;
- `CRITICAL_SUCCESSOR_GATE_v1_0_2.json` — `e78a096ae6baeb157f9362cb4218b7341415972d5d84bb697196e7b9f2127f87`;
- `DEFECT_63_CLOSURE_LEDGER_v1_0_2.json` — `b0ec68d0e80950810227e49ed84ec56993f62c69d41276f3b50f4ad081807bfe`;
- `DIFFERENTIAL_STARTER_18_v1_0_2.json` — `2c0bc55eaf6bc0b7208b0677738be97733401e7fb729b7450a2995fad2ae557d`;
- `KNOWN_PASS_UNION_50_v1_0_2.json` — `beb2b95f5e3c1d961ae195059eac4224eab2d123517724a9fc99cd0e5a97ea5d`;
- `PER_RECORD_CHANGE_LEDGER_v1_0_2.json` — `538028fdbb06c29c114705fd69afea0470e17333d89ecb53712addc93dc711a2`;
- `REPLAY_RNG_CANONICAL_TRANSACTIONS_v1_0_2.json` — `7d6d4424852316d8c73a96e745fc8279d46d2b73ee57c29f2415f69458878a8b`;
- `REQUESTED_STATE_DIGEST_SPEC_v1_0_2.json` — `f23f9d446a0cdd17bab2549241240f718bf43e6a52cc00c651d0774e644735a3`;
- `SEMANTIC_EXECUTABILITY_REPORT_v1_0_2.json` — `35b61c23a6640abb2f7abb741f6a5040993e3d71cc29a68b7054a6fee70e5b07`;
- `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_2.json` — `0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261`;
- `SEMANTIC_FIXTURE_SCHEMA_v1_0_2.json` — `2195db64071550af66dfa7957e2f8d1bd9b65b3dcd0cbb403f7e86c0a6594f7f`;
- `SUPERSEDES_v1_0_1.json` — `1123c9c23f7e66fd8a5a7942869796089ab33a17775bd663fdcf056b1a87052a`;
- `TERMINAL_ABC_SUPERSESSION_v1_0_2.json` — `670051dc212279b68415c1005c8c06549e8bceadaab742700a41c760c10d63fa`;
- `WS32_BUNDLE_MANIFEST_v1_0_2.json` — `3c1e45faaa6b6de1db80bcb86a98055d461d715314d2215bb585303de00f4e83`;
- `WS32_SOURCE_LOCK.json` — `2e17418a80cc38f40c7d693e4ed3b4db4f747ecadd185dd423e441c42db7932d`.

Checksum ledger:

`qualification/ws32/SHA256SUMS_v1_0_2`

v1.0.1 was not modified.

## Tests / CI / Evidence

Fail-closed development evidence was preserved during WS-32. Important intermediate runs include:

- exact predecessor-defect extraction: run `33568293882`, job `100056407671`;
- first strict successor build: run `33568993292`, job `100058572268`, failed closed and exposed additional successor-hardening gaps;
- exact-error classification run: `33569050548`, job `100058749592`, failed closed as intended;
- historical-manifest path failure: run `33569249549`, job `100059366897`, failed closed before freeze credit;
- corrected pre-evidence freeze run: `33570174290`, job `100062200204`, green but later rejected as final WS-32 evidence because the 63-row ledger lacked exact `defect_codes`;
- pre-evidence exact validation: run `33570228793`, job `100062368230`, likewise superseded for final WS-32 evidence.

Final evidence-complete generated freeze run:

- run ID: `33570476199`;
- job ID: `100063127670`;
- source commit: `d0b8519bfa53e01a3adfef6515e067c1c385d508`;
- source tree: `77583fde9c7107cc4a44b3b4a0793cdfb4a016b8`;
- result: `SUCCESS`;
- generated freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`;
- generated freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`;
- artifact upload intentionally skipped because this run created the deterministic generated-output commit.

Final independent exact-freeze validation run:

- run ID: `33570562695`;
- job ID: `100063380651`;
- validation source commit: `62d7bd4fdeca8ecc2435d29f35f4abf095021e55`;
- validation source tree: `f3438f9f01ef4e87d2b74361858bdfcc82e7e31c`;
- generated `qualification/ws32` changes: none;
- workflow result: `SUCCESS`;
- compile tooling: `PASS`;
- build successor once: `PASS`;
- strict exact 135-record lint: `PASS`;
- deterministic second rebuild byte comparison: `PASS`;
- SHA256 manifest verification: `PASS`;
- evidence runtime metadata emission: `PASS`;
- artifact upload: `PASS`.

Final evidence artifact:

- artifact ID: `9824757757`;
- artifact name: `WS32_FREEZE_EVIDENCE`;
- artifact size: `153829` bytes;
- GitHub artifact digest: `sha256:41ff1b863f8f20f7b8c4fa7d689299dae937fb7d8f0586dc746dbb8d476a5d96`;
- independently downloaded ZIP SHA256: `41ff1b863f8f20f7b8c4fa7d689299dae937fb7d8f0586dc746dbb8d476a5d96`;
- GitHub and independently calculated artifact SHA256 match exactly.

Final bundle digest:

`61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b`

The CI workflow proves deterministic generation by rebuilding from authoritative inputs a second time and recursively diffing the generated directory before accepting the freeze.

## PASS / FAIL / UNKNOWN

| Gate / claim | Status |
|---|---|
| G32-01 Immutable provenance | **PASS** |
| G32-02 Complete 135-record accounting | **PASS — 135/135** |
| G32-03 No obligation drift | **PASS — 135/135 obligation projection preserved** |
| G32-04 Native causality | **PASS at contract/linter level** |
| G32-05 No provider bias | **PASS** |
| G32-06 Current authority | **PASS** |
| G32-07 Deterministic freeze | **PASS** |
| Predecessor 63-defect closure | **PASS — 63/63** |
| Starter successor | **PASS — 18/18 semantic executable** |
| Union successor | **PASS — 50/50 semantic executable** |
| Exact 135 successor | **PASS — 135/135 semantic executable** |
| Contract defects | **PASS — 0** |
| Exact predecessor defect-code evidence | **PASS — 63/63 non-empty and preserved** |
| Requested-state construction gate | **PASS — contract frozen; provider execution pending** |
| Replay/RNG transaction contract | **PASS — contract frozen; provider execution pending** |
| `CARD_02` semantic contract | **PASS — contract frozen; provider execution pending** |
| Forge successor runtime | **UNKNOWN / NOT_RUN_IN_WS32** |
| XMage successor runtime | **UNKNOWN / NOT_RUN_IN_WS32** |
| Actual-Card-29 provider behavioral PASS | **UNKNOWN / NOT_RUN_IN_WS32** |
| Production provider selection | **UNKNOWN** |
| Architecture Freeze | **NO / NOT CLAIMED** |

`PASS` in this handoff means the WS-32 contract/materialization obligation is satisfied. It does not promote code-derived contract executability into provider runtime behavior.

## Remaining Blockers

WS-32 itself has no remaining contract-layer blocker.

Remaining program-level blockers are deliberately outside WS-32:

- Forge must construct and execute the frozen successor records under the requested-state equality gate;
- XMage must construct and execute the same frozen successor records under the identical gate;
- AF04/AF05/AF06/AF08/AF09 and any other still-open Architecture-Freeze obligations require provider runtime evidence;
- Actual-Card records require actual provider behavior, not merely semantic materialization;
- finalist differential adjudication requires completed successor provider outputs from both finalists where both remain eligible;
- Architecture Freeze remains `NO` until the broader AF contract is actually satisfied.

The non-normative `WS32_FREEZE_VALIDATION_MARKER.md` has no semantic, denominator or provider-credit effect.

## Outputs

Execution-authoritative successor directory:

`qualification/ws32/`

Required successor artifacts are present:

1. `SEMANTIC_FIXTURE_SCHEMA_v1_0_2.json`;
2. `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_2.json`;
3. `SEMANTIC_EXECUTABILITY_REPORT_v1_0_2.json`;
4. `DIFFERENTIAL_STARTER_18_v1_0_2.json`;
5. `KNOWN_PASS_UNION_50_v1_0_2.json`;
6. `CRITICAL_SUCCESSOR_GATE_v1_0_2.json`;
7. `REPLAY_RNG_CANONICAL_TRANSACTIONS_v1_0_2.json`;
8. `CARD_02_v1_0_2.json`;
9. `REQUESTED_STATE_DIGEST_SPEC_v1_0_2.json`;
10. `DEFECT_63_CLOSURE_LEDGER_v1_0_2.json`;
11. `PER_RECORD_CHANGE_LEDGER_v1_0_2.json`;
12. `SUPERSEDES_v1_0_1.json`;
13. `TERMINAL_ABC_SUPERSESSION_v1_0_2.json`;
14. `WS32_SOURCE_LOCK.json`;
15. `WS32_BUNDLE_MANIFEST_v1_0_2.json`;
16. `SHA256SUMS_v1_0_2`.

Tooling/CI outputs:

- `scripts/ws32_lint_semantic_v1_0_2.py`;
- `scripts/ws32_build_successor.py`;
- `scripts/ws32_build_successor_final.py`;
- `.github/workflows/ws32-freeze.yml`.

Final evidence artifact:

- GitHub Actions artifact ID `9824757757`;
- SHA256 `41ff1b863f8f20f7b8c4fa7d689299dae937fb7d8f0586dc746dbb8d476a5d96`.

## Dependencies Unblocked

WS-32 now unblocks successor provider qualification against one immutable provider-neutral source of truth.

Specifically unblocked:

- WS-33 Forge successor provider qualification;
- WS-34 XMage successor provider qualification;
- later WS-35 finalist differential/convergence work once required provider outputs exist.

No provider receives successor runtime PASS merely because WS-32 is frozen. Provider credit begins only after construction validation and native runtime execution against this exact successor identity.

## Exact Inputs Required by WS-33

WS-33 must consume exactly:

- repository: `moeendres-png/commander-playtest-lab`;
- canonical WS-32 freeze commit: `038d0f38635eecee4e331c99af41f148de267a26`;
- canonical WS-32 freeze tree: `0d160128119f2bad30b220a17c43419b50b7edbe`;
- successor version: `commander-lab.semantic-fixture-materialization/1.0.2`;
- frozen bundle digest: `61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b`;
- `qualification/ws32/SEMANTIC_FIXTURE_SCHEMA_v1_0_2.json`;
- `qualification/ws32/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_2.json`;
- `qualification/ws32/SEMANTIC_EXECUTABILITY_REPORT_v1_0_2.json`;
- `qualification/ws32/DIFFERENTIAL_STARTER_18_v1_0_2.json`;
- `qualification/ws32/KNOWN_PASS_UNION_50_v1_0_2.json`;
- `qualification/ws32/CRITICAL_SUCCESSOR_GATE_v1_0_2.json`;
- `qualification/ws32/REPLAY_RNG_CANONICAL_TRANSACTIONS_v1_0_2.json`;
- `qualification/ws32/CARD_02_v1_0_2.json`;
- `qualification/ws32/REQUESTED_STATE_DIGEST_SPEC_v1_0_2.json`;
- `qualification/ws32/SHA256SUMS_v1_0_2`;
- protocol `commander-lab.rules-service/1.1.0`;
- WS31 authority head `1bee87b9a0c4db90ecbf1f5374fae0732d6dd16e`;
- authority aggregate `d8337dc0a243fddbede3e9d2cec7b3938a1007970a23dea04855149fbfc55d5e`;
- CR SHA256 `9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c`.

Before any Forge runtime credit, WS-33 must emit a normalized constructed-state digest equal to each record's requested-state digest. Mismatch is `CANONICAL_SETUP_UNSUPPORTED_PROVIDER / NO_RUNTIME_CREDIT`.

WS-33 must not substitute Forge-internal object identity for the semantic contract and must not receive credit from any earlier v1.0.1 execution.

## Exact Inputs Required by WS-34

WS-34 must consume the identical neutral WS-32 inputs listed for WS-33:

- freeze commit `038d0f38635eecee4e331c99af41f148de267a26`;
- freeze tree `0d160128119f2bad30b220a17c43419b50b7edbe`;
- successor version `commander-lab.semantic-fixture-materialization/1.0.2`;
- bundle digest `61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b`;
- the same schema/materialization/report/Starter/Union/critical/replay/CARD_02/requested-state/checksum artifacts;
- protocol `commander-lab.rules-service/1.1.0`;
- WS31 authority head/digest and CR SHA256 listed above.

Before any XMage runtime credit, WS-34 must emit a normalized constructed-state digest equal to the requested-state digest for the exact record being executed. Mismatch means canonical setup unsupported and no runtime credit.

XMage implementation details remain outside the canonical WS-32 contract.

## Exact Inputs Required by WS-35

WS-35 requires the frozen WS-32 identity plus completed successor provider outputs.

Required contract inputs:

- freeze commit `038d0f38635eecee4e331c99af41f148de267a26`;
- freeze tree `0d160128119f2bad30b220a17c43419b50b7edbe`;
- bundle digest `61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b`;
- successor schema/materialization/manifests/replay/CARD_02/requested-state specification and checksums.

Required provider evidence before same-record differential credit:

- completed WS-33 Forge successor evidence;
- completed WS-34 XMage successor evidence;
- exact provider source/build identity for each side;
- requested-state digest for every compared record;
- normalized constructed-state digest proving equality before execution;
- identical semantic discretionary selections where a comparison requires them;
- normalized DecisionTape;
- normalized EventTape;
- semantic replay/checkpoint state where applicable;
- normalized terminal semantic state/postconditions;
- current authority lock for adjudication.

A record with requested-state/constructed-state mismatch is ineligible for differential behavior credit.

## Exact Next Action

WS-32 is terminally complete.

The exact next project action is to run/continue WS-33 and WS-34 independently and in parallel against **only** the frozen v1.0.2 identity:

- commit `038d0f38635eecee4e331c99af41f148de267a26`;
- tree `0d160128119f2bad30b220a17c43419b50b7edbe`;
- bundle digest `61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b`.

Neither provider may receive successor runtime credit from older v1.0.1 materialization, from import/parsing success, from static source inspection, or from a requested state that the provider did not construct exactly under the frozen digest gate.

After both provider workstreams have produced technically valid successor evidence, WS-35 may perform same-record convergence/differential adjudication on the mutually eligible records.

Do not claim Architecture Freeze at WS-32 closure. `ARCHITECTURE_FREEZE = NO` until the separate provider and AF runtime obligations are actually satisfied.
