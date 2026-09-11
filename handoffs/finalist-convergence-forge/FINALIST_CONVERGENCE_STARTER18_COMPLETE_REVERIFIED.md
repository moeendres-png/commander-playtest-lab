# COMMANDER SIMULATION FOUNDRY
# FINALIST CONVERGENCE — STARTER-18 COMPLETE / REVERIFIED HANDOFF

## Status

`STARTER18_CONVERGENCE = COMPLETE / PASS_CLOSED`

`FINALIST_CONVERGENCE_PROGRAM = CONTINUE`

`ARCHITECTURE_FREEZE = NO / UNFROZEN`

`PRODUCTION_PROVIDER = NONE`

`HOLDOUT_CONSUMED = NO`

This handoff closes the corrected-canonical Starter-18 execution and first true same-record Forge/XMage comparison. It does **not** claim Union-50, full-135, Architecture Freeze, or production admission are complete.

---

## Source Lock

### Neutral canonical contract

- contract branch: `program/finalist-convergence-contract`
- exact frozen contract head: `9a8b8f5f5961466514eae6103be2d227324a27a8`
- schema: `commander-lab.semantic-fixture-materialization/1.0.1`
- canonical bundle digest: `ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee`
- all-135 semantic executability: `72 PASS / 63 SEMANTIC_EXECUTABILITY_DEFECT`
- Starter-18 contract records: `18 / 18 executable`
- v1.0.0 remains immutable provenance.

### Forge finalist

- repository: `moeendres-png/commander-playtest-lab`
- direct WS-25 base: `09cfad8a24be12a87761e6645c48577387f0521b`
- branch: `program/finalist-convergence-forge`
- exact revalidated runtime head: `6e37a9a2188375c5a938b90a95586a85be501259`
- runtime tree: `805e80c3348c32a896692e9165803e5fd534dde8`
- pinned Forge: `Card-Forge/forge@1e604105f9e279331063824943b9222b6589f5d8`
- pinned Forge tree: `994976e06aaf99b807646b60b1aa2ac9f7703df4`
- Forge version: `2.0.15-SNAPSHOT`
- Forge source modified: `false`
- historical WS-23 bootstrap modified: `false`
- finalist bootstrap overlay generated: `true`
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

1. Reconstructed the Forge convergence branch directly from the exact WS-25 runtime base.
2. Preserved the WS-23/25 separate-GPL-JVM architecture and strict external `PlayerController` authority.
3. Preserved pinned unmodified Forge source.
4. Reused native Commander construction via `RegisteredPlayer.forCommander`.
5. Materialized canonical natural-start decks as Rograkh plus 99 Mountains per player.
6. Preserved Rules RNG authority through Forge `MyRandom` for the supported natural-start paths.
7. Added semantic starting-player labels instead of positional/default choice.
8. Repaired headless Forge card loading using Forge-native lazy loading without GUI/image dependencies.
9. Repaired Commander snapshot projection to use actual player Commander state rather than Forge's internal Commander Effect object.
10. Repaired mulligan actor identity by binding the decision to the controller-owned player instead of the `firstPlayer` callback argument.
11. Isolated all finalist bootstrap changes into a generated qualification overlay so the historical WS-23 bootstrap remains byte-identical to the WS-25 base.
12. Built pinned Forge successfully.
13. Compiled the generated GPL-side sidecar successfully.
14. Proved the protocol handshake over a separate Forge process.
15. Executed all 18 exact v1.0.1 Starter records with terminal status.
16. Downloaded and SHA-verified the exact successful XMage Starter-18 artifact.
17. Executed the neutral exact same-record comparator.
18. Materialized exact source locks and SHA256SUMS in CI.

No main merge occurred. No holdout was consumed.

---

## Harness / Provider Defects Repaired

The convergence effort encountered and terminally repaired qualification/provider defects without assigning Rules-core blame:

1. generator import-anchor multiplicity;
2. headless card-store lazy-load failure;
3. image-dependent `StaticData.fetchCard()` path unsuitable for the headless qualification process;
4. Commander projection counting Forge's internal Commander Effect object;
5. mulligan DecisionFrame actor mislabeled through the `firstPlayer` method parameter;
6. downloaded XMage artifact nesting preventing exact reference verification;
7. provenance hardening: finalist bootstrap changes were moved out of the historical bootstrap and into a generated qualification overlay.

No direct Forge Rules defect was established by this convergence slice.
No direct XMage Rules defect was established by this convergence slice.

---

## Revalidated Forge Build / CI Evidence

Workflow: `Finalist convergence Forge`

Exact revalidation:

- run: `33427527049`
- job: `99604635310`
- head: `6e37a9a2188375c5a938b90a95586a85be501259`
- conclusion: `SUCCESS`

Every required step completed successfully:

- exact WS-25 ancestry verification;
- historical bootstrap provenance verification;
- exact v1.0.1 contract mount/hash verification;
- exact pinned Forge checkout/tree verification;
- Forge Maven build;
- isolated classpath resolution;
- sidecar + bootstrap overlay generation;
- prohibited Forge AI/GUI dependency check;
- separate GPL-side Java compile;
- protocol handshake;
- exact Starter-18 runtime execution;
- exact XMage artifact download and SHA verification;
- neutral same-record comparator;
- source-lock/checksum materialization;
- evidence artifact upload.

Handshake:

`PASS / provider=forge / real_session_capable=true`

---

## Forge Starter-18 Runtime Result

Exact Forge `STARTER_18_RESULTS.json` SHA256:

`89df3df49fa975444091a7cc07219b0e2a97d6053c348cdbc5b4dcfe58f3a314`

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
- requested semantic-state digest equals normalized native constructed-state digest;
- native Commander lifecycle was used;
- each player has 40 life, seven opening cards, 92-card library and one Rograkh commander;
- starting-player and mulligan decisions are explicit external semantic selections;
- no first/random/default/AI/GUI fallback supplied player discretion.

The other 13 fixtures are terminally `CANONICAL_SETUP_UNSUPPORTED` at this provider revision. They receive no runtime PASS and no Rules-core FAIL.

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

Exact `SAME_RECORD_COMPARISON.json` SHA256:

`3fc3581c3784db1cf26c4261a2458716c65720aac66b7fcdfe88291f938af843`

Comparator inputs:

- Forge result SHA256: `89df3df49fa975444091a7cc07219b0e2a97d6053c348cdbc5b4dcfe58f3a314`
- XMage result SHA256: `feb7f8018bffc10e09717a717b468c2306c7ace12a5ac821ed644ad012f43d8c`

Counts:

- `DIFFERENTIAL_AGREEMENT_PASS = 5`
- `CANONICAL_SETUP_UNSUPPORTED_BOTH = 13`
- `ENGINE_SEMANTIC_DISAGREEMENT = 0`
- provider defects in the final comparator = `0`
- contract defects in the final comparator = `0`

Differential agreements:

1. `PLAYER_COUNT_2P`
2. `PLAYER_COUNT_3P`
3. `PLAYER_COUNT_4P`
4. `PLAYER_COUNT_5P`
5. `PILOT_MULLIGAN`

For each agreement the comparator verified:

- identical corrected v1.0.1 record digest;
- identical requested semantic-state digest;
- identical normalized native constructed-state digest;
- identical semantic discretionary selections;
- identical terminal semantic state;
- terminal postcondition PASS on both engines.

The comparator intentionally ignores provider UUIDs, raw native action IDs, process IDs, raw cross-engine PRNG sequences, and provider callback ordering.

This remains the first non-zero exact same-record differential-verified intersection in the project.

---

## Revalidated CI Artifact

- artifact ID: `9771341427`
- name: `finalist-convergence-forge-6e37a9a2188375c5a938b90a95586a85be501259`
- artifact digest: `sha256:2dcfa7d3a8678fd3b177a6ff42812e7ba8c9eea0502c52e601de1d498b6584c6`
- artifact size: `129694` bytes

The downloaded artifact ZIP independently hashes to the same SHA256.

### Artifact SHA256SUMS

- `HANDSHAKE_PROOF.json`: `de9c6044512ceb251b4729693812720558580e218d30b044710ab0214c9fedfc`
- `STARTER_18_RESULTS.json`: `89df3df49fa975444091a7cc07219b0e2a97d6053c348cdbc5b4dcfe58f3a314`
- `SAME_RECORD_COMPARISON.json`: `3fc3581c3784db1cf26c4261a2458716c65720aac66b7fcdfe88291f938af843`
- `SOURCE_LOCK.json`: `03dd1ea8006051fe3d7b5e987373e28925b5f2d3495ddec6faa05b7648614d90`
- `XMAGE_REFERENCE_LOCK.json`: `c31862f3d544787e8179dfb4334624c358a783763622346e62d777228e27fae6`
- `generator-summary.json`: `ece92aea05855fce6b3410c6de0320ec0afffbc5e1fd01977a51e56809ed6f74`
- `generated/finalist_forge_provider_mapping.json`: `783184c528526783f92acecba84d5394dac5c2872616b1642bdaa9597e01be83`
- exact XMage reference result: `feb7f8018bffc10e09717a717b468c2306c7ace12a5ac821ed644ad012f43d8c`

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
| Exact same-record comparator | `PASS` |
| Differential agreement | `5` |
| Differential unsupported both | `13` |
| Engine semantic disagreements | `0` |
| Direct Forge Rules defects established | `0` |
| Direct XMage Rules defects established | `0` |
| Requested Starter-18 convergence segment | `COMPLETE / PASS_CLOSED` |
| Corrected Union-50 | `NOT_RUN` |
| Full 135 candidate execution | `NOT_RUN`; contract has `63` semantic-executability defects |
| Architecture Freeze | `NO / UNFROZEN` |
| Production Provider | `NONE / UNKNOWN` |
| Holdout | `NOT_CONSUMED` |

---

## Remaining Blockers

1. Both finalists currently execute only 5/18 corrected Starter-18 records; 13 are provider/setup unsupported on both.
2. Corrected same-record Union-50 has not run.
3. Only 72/135 v1.0.1 contract records are semantic-executable; 63 remain explicit contract defects and cannot earn runtime credit until neutral correction under a new immutable digest/version.
4. AF04–AF08 remain incomplete for both finalists.
5. The completed Finalist Deep-Risk Audit identified an XMage actor-facing hidden-ID side channel that remains a production AF05 blocker until remediated.
6. Forge actor-safe observation must remain a dedicated provider projection rather than native Netplay.
7. The completed Deep-Risk Audit requires one active simulation session per engine process/JVM until per-session RNG authority is proved because both pinned engines expose JVM-global Rules RNG state.
8. The 29 authority-ready card fixtures still require real candidate runtime execution beyond already supported paths.
9. Five lifecycle/mulligan differential agreements are insufficient for Architecture Freeze.

---

## Dependencies Unblocked

Without repeating this closed Starter-18 lifecycle work, the continuation may now:

1. extend both existing provider translators for the 13 remaining Starter-18 semantic dimensions;
2. remediate the XMage hidden actor-facing object-identity side channel before AF05 production admission;
3. execute and differential the corrected Known-PASS Union-50 using the generic provider mappings;
4. expand through the 72 currently executable v1.0.1 records by AF decision value;
5. repair the remaining 63 neutral contract defects only under a new immutable contract version/digest and rerun changed records on both finalists;
6. execute the frozen 29 actual-card corpus under WS-31 authority;
7. later consume the completed POST-135 qualification design for broader real-card runtime coverage.

---

## Exact Next Action

Continue the same Finalist Convergence Program from these exact locks.

First priority is **not** another lifecycle rerun. Implement the missing provider dimensions shared by both finalists in this order because they unlock the highest-value Starter-18/AF evidence:

1. `PILOT_PRIORITY` / `PILOT_TARGET` native cast + target path;
2. `HIDDEN_01` / `HIDDEN_02` actor-safe knowledge projection, with the XMage opaque-handle remediation included before claiming PASS;
3. `MICRO_STACK` native stack resume/cast/resolve;
4. `MICRO_REPLACEMENT` native combat-damage replacement path;
5. `WS05-MP-COMBAT-4` native multi-defender attack declaration;
6. replay/RNG five via native explicit shuffle + cast + fresh-process semantic replay;
7. `CARD_02` native command-zone cast + resolve.

After the 13 remaining Starter-18 records have terminal candidate results, rerun the same-record comparator. If both finalists remain viable and no decisive correctness defect appears, proceed automatically to corrected Union-50 and then the broader currently-executable v1.0.1 corpus.

Do not select a production Rules Core from the current five agreements.
