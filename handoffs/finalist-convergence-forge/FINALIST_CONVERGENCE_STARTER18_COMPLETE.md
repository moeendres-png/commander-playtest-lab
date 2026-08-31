# COMMANDER SIMULATION FOUNDRY
# FINALIST CONVERGENCE — STARTER-18 COMPLETE HANDOFF

## Status

`STARTER18_CONVERGENCE = COMPLETE / PASS_CLOSED`

`FINALIST_CONVERGENCE_PROGRAM = CONTINUE`

`ARCHITECTURE_FREEZE = NO / UNFROZEN`

`PRODUCTION_PROVIDER = NONE`

`HOLDOUT_CONSUMED = NO`

This handoff closes the requested corrected-canonical Starter-18 execution and first true same-record Forge/XMage comparison. It does not claim that the larger Finalist Convergence Program, Union-50, full 135, or production admission are complete.

---

## Source Lock

### Neutral canonical contract

- branch: `program/finalist-convergence-contract`
- frozen contract head: `9a8b8f5f5961466514eae6103be2d227324a27a8`
- schema: `commander-lab.semantic-fixture-materialization/1.0.1`
- canonical bundle digest: `ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee`
- all-135 semantic executability: `72 PASS / 63 SEMANTIC_EXECUTABILITY_DEFECT`
- Starter-18 contract records: `18/18 executable`
- v1.0.0 remains immutable provenance.

### Forge finalist

- Commander Lab direct base: `09cfad8a24be12a87761e6645c48577387f0521b`
- convergence runtime head: `7e2525c7ee54af2da28aeca0d75e3a4009da2601`
- runtime tree: `6e4a7e2bce46de7457504bf108f3871a88da4c82`
- branch: `program/finalist-convergence-forge`
- pinned Forge: `Card-Forge/forge@1e604105f9e279331063824943b9222b6589f5d8`
- pinned Forge tree: `994976e06aaf99b807646b60b1aa2ac9f7703df4`
- Forge version: `2.0.15-SNAPSHOT`
- Forge source modified: `false`
- process topology: `SEPARATE_GPL_JVM`
- Forge AI/GUI in provider: `false`

### XMage finalist reference

- convergence head: `e1d19ff65ee08ce9fb1dcec846a38277b49fb5c8`
- behavioral candidate commit in evidence: `a53c2312983384eb0870746132e281bbed2f5a1d`
- pinned XMage: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`
- XMage tree: `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`
- successful reference run: `33395818923`
- reference artifact ID: `9759407784`
- reference artifact digest: `sha256:5e3fd1e06a24f55ab4c0fdad27ed4efdfe1a991d6d35789f235cede615944d4b`
- XMage `STARTER_18_RESULTS.json` SHA256: `feb7f8018bffc10e09717a717b468c2306c7ace12a5ac821ed644ad012f43d8c`

---

## Work Completed

1. Reconstructed `program/finalist-convergence-forge` directly from the exact WS-25 runtime base.
2. Preserved the WS-23/25 separate-GPL-JVM architecture and strict external `PlayerController` authority.
3. Reused pinned Forge native Commander construction via `RegisteredPlayer.forCommander`.
4. Created real canonical natural-start decks: one Rograkh commander plus 99 Mountains per player.
5. Preserved provider-side seeded Rules RNG injection through `MyRandom`.
6. Added semantic starting-player option labels instead of positional/default selection.
7. Added canonical Rules-seed and controlled-priority stop configuration to the qualification bootstrap.
8. Corrected headless Forge card loading without introducing image/GUI dependency or modifying upstream Forge.
9. Corrected Commander semantic projection to use `Player.getCommanders()` rather than counting Forge's internal Commander Effect object.
10. Corrected Forge mulligan actor identity after source verification of `MulliganService`: Forge invokes the actual mulligan player's controller but passes `firstPlayer` as the method argument, so the provider must bind actor identity to controller-owned `this.player`.
11. Executed exact v1.0.1 Starter-18 through separate Forge JVMs.
12. Downloaded and hash-verified the exact successful XMage Starter-18 evidence artifact.
13. Executed the neutral same-record comparator.
14. Materialized exact source lock and SHA256SUMS in CI.

No Forge upstream source was patched. No merge occurred. No holdout was consumed.

---

## Harness / Provider Defects Repaired

The following failures encountered during convergence were qualification/provider defects and were repaired without assigning Rules-core blame:

1. generator import-anchor multiplicity;
2. headless card-store lazy-load failure;
3. image-dependent `StaticData.fetchCard()` path in headless qualification;
4. Commander snapshot counting Forge's internal Commander Effect object;
5. mulligan DecisionFrame actor mislabeled through the `firstPlayer` method parameter;
6. downloaded XMage artifact nesting preventing exact reference verification.

All of those defects are terminally closed in the successful final CI run.

No direct Forge Rules defect was established by this work.
No direct XMage Rules defect was established by this work.

---

## Forge Build / Process Evidence

Final workflow:

- workflow: `Finalist convergence Forge`
- run: `33412644529`
- job: `99555650623`
- conclusion: `SUCCESS`

Every required step completed successfully, including:

- exact WS-25 ancestry verification;
- exact v1.0.1 contract mount/hash verification;
- exact pinned Forge source checkout/tree verification;
- Forge Maven build;
- isolated classpath resolution;
- provider overlay generation;
- prohibited Forge AI/GUI dependency check;
- separate GPL-side Java compile;
- protocol handshake;
- exact Starter-18 runtime execution;
- exact XMage artifact download and SHA verification;
- same-record comparator;
- final source lock and checksums;
- evidence artifact upload.

Handshake verdict:

`PASS / provider=forge / real_session_capable=true`

---

## Forge Starter-18 Runtime Result

Exact Forge `STARTER_18_RESULTS.json` SHA256:

`b0661375bb669027a68ef64caee5b35bc5b92ebbbce6e751f62bb9a1f959b9a4`

Counts:

- `PASS = 5`
- `CANONICAL_SETUP_UNSUPPORTED = 13`
- `FAIL = 0`

PASS fixtures:

1. `PLAYER_COUNT_2P`
2. `PLAYER_COUNT_3P`
3. `PLAYER_COUNT_4P`
4. `PLAYER_COUNT_5P`
5. `PILOT_MULLIGAN`

For all five PASS fixtures:

- exact v1.0.1 record digest was used;
- requested semantic state digest equaled normalized native constructed state digest;
- native Commander lifecycle was used;
- each player had 40 life, seven opening cards, 92-card library and exactly one Rograkh commander;
- external semantic starting-player / mulligan decisions were explicit;
- no default/first/random/AI/GUI fallback supplied player discretion.

The other 13 fixtures remain terminal `CANONICAL_SETUP_UNSUPPORTED` at this provider revision. They receive no runtime PASS and no Rules-core FAIL.

---

## XMage Starter-18 Reference Result

Exact XMage result SHA256:

`feb7f8018bffc10e09717a717b468c2306c7ace12a5ac821ed644ad012f43d8c`

Counts:

- `PASS = 5`
- `CANONICAL_SETUP_UNSUPPORTED = 13`
- `FAIL = 0`

The exact five PASS identities match Forge's five natural-start fixtures.

---

## First True Same-Record Differential

Exact comparison artifact SHA256:

`17fdff3c336e396e0809910a0424ef2a8b311f5a52446dd140de18573e4a4c4a`

Comparator input SHA256:

- Forge: `b0661375bb669027a68ef64caee5b35bc5b92ebbbce6e751f62bb9a1f959b9a4`
- XMage: `feb7f8018bffc10e09717a717b468c2306c7ace12a5ac821ed644ad012f43d8c`

Differential counts:

- `DIFFERENTIAL_AGREEMENT_PASS = 5`
- `CANONICAL_SETUP_UNSUPPORTED_BOTH = 13`
- `ENGINE_SEMANTIC_DISAGREEMENT = 0`
- `PROVIDER_DEFECT_FORGE = 0`
- `PROVIDER_DEFECT_XMAGE = 0`
- `PROVIDER_DEFECT_BOTH = 0`
- `CONTRACT_DEFECT = 0`

The five differential agreements are:

1. `PLAYER_COUNT_2P`
2. `PLAYER_COUNT_3P`
3. `PLAYER_COUNT_4P`
4. `PLAYER_COUNT_5P`
5. `PILOT_MULLIGAN`

For each of these five, the comparator verified:

- identical corrected v1.0.1 record digest;
- identical requested semantic-state digest;
- identical normalized native constructed-state digest;
- identical semantic discretionary selections;
- identical terminal semantic state;
- `terminal_postcondition_result = PASS` on both candidates.

The comparator deliberately ignores provider UUIDs, native action IDs, process IDs, raw cross-engine PRNG sequences, and provider callback ordering.

This is the first non-zero exact same-record differential-verified intersection in the project.

---

## Final CI Artifact

Artifact:

- ID: `9765787213`
- name: `finalist-convergence-forge-7e2525c7ee54af2da28aeca0d75e3a4009da2601`
- digest: `sha256:f699e06a94d6acb068d16a9e1d22168e706eb3cc9b53e9bd145ae215237fddd7`

Key SHA256SUMS:

- `HANDSHAKE_PROOF.json`: `de9c6044512ceb251b4729693812720558580e218d30b044710ab0214c9fedfc`
- `STARTER_18_RESULTS.json`: `b0661375bb669027a68ef64caee5b35bc5b92ebbbce6e751f62bb9a1f959b9a4`
- `SAME_RECORD_COMPARISON.json`: `17fdff3c336e396e0809910a0424ef2a8b311f5a52446dd140de18573e4a4c4a`
- `SOURCE_LOCK.json`: `70b52a22d5302fd311858a0294749ffd04480b9a57e836af3cf52faa230161b1`
- `XMAGE_REFERENCE_LOCK.json`: `c31862f3d544787e8179dfb4334624c358a783763622346e62d777228e27fae6`
- `generator-summary.json`: `ece92aea05855fce6b3410c6de0320ec0afffbc5e1fd01977a51e56809ed6f74`
- `generated/finalist_forge_provider_mapping.json`: `783184c528526783f92acecba84d5394dac5c2872616b1642bdaa9597e01be83`
- exact XMage reference result: `feb7f8018bffc10e09717a717b468c2306c7ace12a5ac821ed644ad012f43d8c`

---

## Completed Audit Inputs Integrated

The separately completed `FINALIST_CONVERGENCE_AUDIT_COMPLETE_REVERIFIED.md` remains binding. Its five audit axes are complete and must not be redone merely for completeness.

Important downstream constraints retained:

1. XMage hidden card handles have a confirmed deterministic card/deck-derived side channel and must be replaced with opaque non-inferable actor-facing handles before production AF05 admission.
2. Forge native Netplay is not an admissible external pilot boundary; continue using a dedicated actor-entitled GPL-side provider projection.
3. Both pinned engines expose JVM-global Rules RNG authority; until per-session RNG is proved, use one active simulation session per engine process/JVM.
4. Forge state loading is `PARTIAL_BROAD / NOT_FULL`; XMage WS-26 state loading is `PARTIAL_NARROW / NOT_FULL`.
5. Unsupported canonical state dimensions fail closed; they are not emulated in pilot code.
6. No audit source finding creates runtime PASS by itself.

---

## Completed POST-135 Design Integrated

The separate Post-135 Card Qualification Design is accepted as:

`COMPLETE / PASS_CLOSED / DESIGN_ONLY`

It must not be redesigned unless its source lock/invalidation model changes.

It supplies future runtime-prioritization inputs, including:

- 1,385-card authoritative production domain;
- operational singleton diagnostic set: 18 cards;
- authority-only singleton set-cover: 15 cards;
- high-risk pairwise augmented diagnostic set: 27 cards;
- High-Risk 100 tier;
- physical representative tier;
- RogShai 87;
- Kaervek 77;
- full 1,385 target.

Representative tiers are diagnostic/prioritization tools only and never confer FULL card functionality to unexecuted cards.

---

## PASS / FAIL / UNKNOWN

| Question | Verdict |
|---|---|
| Neutral v1.0.1 Starter-18 contract | `PASS / 18/18 executable` |
| Forge build | `PASS` |
| Forge isolated sidecar compile | `PASS` |
| Forge protocol handshake | `PASS` |
| Forge Starter-18 terminal accounting | `PASS / COMPLETE: 5 PASS + 13 UNSUPPORTED + 0 FAIL` |
| XMage Starter-18 terminal accounting | `PASS / COMPLETE: 5 PASS + 13 UNSUPPORTED + 0 FAIL` |
| Exact same-record comparator execution | `PASS` |
| Differential agreement | `5` |
| Differential unsupported both | `13` |
| Engine semantic disagreements | `0` |
| Direct Forge Rules defects established | `0` |
| Direct XMage Rules defects established | `0` |
| Starter-18 convergence requested in this segment | `COMPLETE / PASS_CLOSED` |
| Union-50 | `NOT_RUN on corrected same-record program` |
| Full 135 candidate execution | `NOT_RUN / contract has 63 semantic-executability defects` |
| Architecture Freeze | `NO / UNFROZEN` |
| Production Provider | `NONE / UNKNOWN` |
| Holdout | `NOT_CONSUMED` |

---

## Remaining Blockers

1. Both candidates support only 5/18 corrected Starter-18 records today; 13 are still setup/provider unsupported on both.
2. Corrected Known-PASS Union-50 has not yet been executed same-record.
3. Only 72/135 v1.0.1 records are semantic-executable; 63 remain explicit contract defects and cannot be used for runtime credit until neutral correction with a new immutable digest/version.
4. AF04–AF08 remain incomplete for both finalists.
5. XMage actor-facing hidden-ID side channel remains a production AF05 blocker.
6. Forge actor-safe observation must continue through dedicated provider projection, not native Netplay.
7. Process isolation remains the deterministic Rules-RNG baseline for both engines.
8. The 29 current authoritative card fixtures still require real candidate runtime execution beyond the already supported subset.
9. No Architecture Freeze decision is justified from five lifecycle/mulligan agreements alone.

---

## Dependencies Unblocked

The following work may now proceed without repeating Starter-18 lifecycle reconstruction or the completed audits:

1. extend both existing provider translators for the 13 remaining Starter-18 semantic dimensions;
2. remediate XMage hidden actor-facing object identity before claiming hidden-info production safety;
3. execute and differential the corrected Known-PASS Union-50 using generic provider mappings;
4. expand through the 72 currently executable v1.0.1 records by AF decision value;
5. neutral-repair the remaining 63 contract-defective records only when needed, with a new immutable version/digest and dual-provider reruns for changed records;
6. rerun the frozen 29 actual-card corpus under WS-31 authority;
7. after sufficient AF/common closure, consume the already-complete POST-135 tier design for broad real-card runtime qualification.

---

## Exact Next Action

Continue the same Finalist Convergence Program from this handoff, not from historical WS-25/26 counts.

First priority is to turn the 13 currently `CANONICAL_SETUP_UNSUPPORTED_BOTH` Starter-18 rows into comparable native executions by extending the existing Forge and XMage provider/state translators without moving Rules semantics into Commander Lab.

Do this in decision-value order:

1. `PILOT_PRIORITY` + `PILOT_TARGET` — native cast/target/legal-action plumbing;
2. `HIDDEN_01` + `HIDDEN_02` — exact actor-safe projection, including XMage opaque-ID remediation;
3. `MICRO_STACK` — fully-cast stack/native response state;
4. `MICRO_REPLACEMENT` — native causal replacement/combat-damage path;
5. `WS05-MP-COMBAT-4` — exact native 4P multi-defender attack declaration;
6. replay/RNG five — explicit native shuffle/cast path, process-isolated replay;
7. `CARD_02` — exact native command-zone Rograkh cast / cast-count transition.

After each capability family is native and constructed-state equality passes, execute it on both candidates and update the same-record comparator. Do not wait until all 13 are implemented to preserve minimized defect evidence.

Once Starter-18 reaches materially broader comparable coverage and both candidates remain viable, execute the corrected Union-50 automatically. Then continue toward the 72 currently executable v1.0.1 records and AF04–AF08 closure.

No winner is selected by this handoff.
