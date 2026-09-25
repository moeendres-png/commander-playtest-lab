# COMMANDER SIMULATION FOUNDRY — WS-28 FINAL HANDOFF

## Source Lock

**Workstream:** WS-28 — XMAGE / FORGE FINALIST DIFFERENTIAL + CROSS-MATERIALIZATION  
**Date:** 2026-08-30  
**Repository:** `moeendres-png/commander-playtest-lab`  
**Neutral branch:** `ws28/finalist-differential`  
**Neutral base:** `main@c83e52ae79ff2242578757c0f517badbb1a2621c`  
**Architecture winner selected:** **NO**  
**Production Rules Core selected:** **NO / OUT OF SCOPE**

The requested WS-27 overlap files were not discoverable through the connected Drive/repository search during WS-28. WS-28 therefore reconstructed the starting finalist sets independently from exact WS-25 and WS-26 evidence and verified the contract values:

- Forge PASS = **34**
- XMage PASS = **34**
- shared independent PASS = **18**
- Forge-only PASS = **16**
- XMage-only PASS = **16**
- PASS union = **50**
- neither PASS = **85**

The reconstructed sets exactly match the WS-28 input contract.

### Neutral WS-28 repository provenance

- initial neutral orchestration commit: `b731e6492192c7393474aefa086ac3d0d64969a8`
- self-reference repair commit: `6dfaa53acec01a03d6a5d0ca70ee716715bd836d`
- standalone-test isolation commit / canonical CI orchestration head: `a93748470f2fac79ca94fe7ec770e65051ff32da`
- successful neutral WS-28 GitHub Actions run: `33329759026`
- successful neutral WS-28 job: `99306107781`
- reproducible evidence materialization commit produced by that run: `ebcbe83a36502235a091d3f21be8959f52d22a0d`
- Draft PR: `#143` — `ws28/finalist-differential` → `main`

Superseded infrastructure attempts are preserved as provenance only:

- run `33329634698`: superseded before closeout after detecting a handoff/evidence self-reference cycle in the initial orchestration design;
- run `33329691306`, job `99305932012`: source locks, artifact hashes and rebuild succeeded, but standalone WS-28 pytest collection was incorrectly affected by repository-global `tests/conftest.py` and failed on missing `pydantic`; no semantic WS-28 gate failed. This was repaired by explicit standalone test collection.

## Forge Source Lock

- Commander Lab branch: `ws25/forge-broad-behavioral-qualification`
- exact Commander Lab runtime head: `09cfad8a24be12a87761e6645c48577387f0521b`
- Draft PR: `#140`
- Forge repository: `Card-Forge/forge`
- Forge commit: `1e604105f9e279331063824943b9222b6589f5d8`
- Forge tree: `994976e06aaf99b807646b60b1aa2ac9f7703df4`
- fresh exact-head provider run: `33305749438`
- fresh job: `99302608566`
- fresh artifact: `9736955576`
- artifact SHA256: `1958a9c985033e24c3ed4c8ee8e9e032d6cec7afccd5bce3ce8abcdd9e0a4a31`
- result: **SUCCESS**

The fresh Forge run verified exact source identity, built the pinned unmodified Forge source, preserved the separate GPL JVM topology, reran 2P–5P lifecycle/Gate-D/replay evidence, regenerated complete 135-row accounting and hashed its evidence.

## XMage Source Lock

- Commander Lab branch: `ws26/xmage-scenario-replay-viability`
- canonical behavioral head: `a53c2312983384eb0870746132e281bbed2f5a1d`
- Draft PR: `#141`
- later documentation/evidence-only PR-head movement was not used as behavioral authority
- XMage repository: `moeendres-png/mage`
- XMage commit: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`
- XMage tree: `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`
- fresh exact-behavioral-head provider run: `33320954360`
- fresh job: `99302619591`
- fresh artifact: `9737051836`
- artifact SHA256: `efdff404483822a04bd66de3ab03ba6bd38fe1f69d4bc16c1fb18ef3056d7b64`
- result: **SUCCESS**

The fresh XMage run verified exact source identity, rebuilt the pinned engine with the deterministic qualification transform, reran native representative Rules fixtures, WS-22 regressions, WS-26 scenario materialization and clean-process replay.

## Frozen Differential Contract

- protocol: `commander-lab.rules-service/1.1.0`
- common denominator: **135**
- common manifest SHA256: `e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`
- fixture IDs: unchanged
- semantic expectations: unchanged
- player counts: unchanged
- denominator: unchanged
- AF requirements: unchanged
- holdout: not consumed
- PR #140 / #141: not merged
- candidate implementations: not merged together
- no cross-import of internal Forge/XMage classes

The central contract finding is that the 135-row manifest is sufficient as a qualification-obligation catalog but does not itself fully materialize one provider-neutral semantic starting state and decision transcript for the 50 known-PASS union. Therefore `same fixture ID + independent PASS` is necessary but not sufficient for differential equivalence.

## Initial 18 Shared Fixtures

The starting independent shared-PASS corpus was exactly:

`PLAYER_COUNT_2P`, `PLAYER_COUNT_3P`, `PLAYER_COUNT_4P`, `PLAYER_COUNT_5P`, `PILOT_MULLIGAN`, `PILOT_PRIORITY`, `PILOT_TARGET`, `HIDDEN_01`, `HIDDEN_02`, `MICRO_STACK`, `MICRO_REPLACEMENT`, `WS05-MP-COMBAT-4`, `RNG_RULES_TAPE`, `REPLAY_DECISION_TAPE`, `REPLAY_EVENT_TAPE`, `REPLAY_CLEAN_PROCESS`, `REPLAY_STATE_HASHES`, `CARD_02`.

## Strict Differential Results

All 18 received a terminal WS-28 classification.

- `DIFFERENTIAL_AGREEMENT_PASS`: **0**
- `ENGINE_SEMANTIC_DISAGREEMENT`: **0**
- `PROVIDER_MAPPING_DISAGREEMENT`: **0**
- `SETUP_NONISOMORPHIC`: **18**
- `DECISION_NONISOMORPHIC`: **0 as primary verdict**; setup equivalence already failed first
- `AUTHORITY_BLOCKED`: **0** among the 18
- `CANDIDATE_UNSUPPORTED`: **0** among the 18

Representative non-isomorphisms include:

- `PLAYER_COUNT_*`: Forge and XMage candidate evidence use different lifecycle initial conditions, including starting-life/deck state;
- `MICRO_REPLACEMENT`: Forge candidate evidence exercises a commander-zone replacement path while XMage native evidence exercises Rest in Peace graveyard-to-exile replacement;
- `MICRO_STACK`: Forge and XMage use different response sequences/postconditions;
- `WS05-MP-COMBAT-4`: attacker/defender materializations differ;
- replay/RNG fixtures: Forge replays its Gate-D compound scenario while XMage replays the WS-26 Goblin Bomb scenario;
- `CARD_02`: both execute Rograkh behavior but through different initial zone paths and discriminator sets.

This does **not** prove an engine disagreement. It proves the current shared-ID evidence is not yet a valid provider-neutral differential experiment.

## Forge → XMage Cross-Materialization

The 16 Forge-only PASS IDs were all attempted on the exact XMage finalist accounting.

- attempted: **16/16**
- new exact cross-materialized PASS: **0**
- `CANDIDATE_UNSUPPORTED`: **16**
- direct XMage Rules defect demonstrated: **0**

Classification: provider/fixture materialization gap (`PROVIDER_DEFECT_XMAGE`), not `XMAGE_RULES_DEFECT`.

WS-28 did not silently promote Forge's compound provider-specific Gate-D construction into the canonical semantic fixture. Doing so would have altered/resolved missing frozen semantics without authority.

## XMage → Forge Cross-Materialization

The 16 XMage-only PASS IDs were all attempted on the exact Forge finalist accounting.

- attempted: **16/16**
- new exact cross-materialized PASS: **0**
- `CANDIDATE_UNSUPPORTED`: **16** at WS-28 differential level
- direct Forge Rules defect demonstrated: **0**

`CARD_04` and `CARD_24` have direct official Wizards authority already reverified in WS-28; their remaining blocker is Forge fixture/provider materialization, not authority.

Classification: provider/fixture materialization gap (`PROVIDER_DEFECT_FORGE`), not `FORGE_RULES_DEFECT`.

## Final Comparable Intersection

- starting independent PASS intersection: **18**
- newly cross-materialized Forge → XMage: **0**
- newly cross-materialized XMage → Forge: **0**
- final independent PASS intersection: **18**
- final **differential-verified identical semantic intersection: 0**

The nominal 18 must not be represented as `DIFFERENTIAL_VERIFIED`.

## Semantic Agreements

No shared fixture cleared the semantic-isomorphism prerequisites required for cross-engine agreement.

`DIFFERENTIAL_AGREEMENT_PASS = 0`.

Independent candidate PASS evidence remains valid only within its own materialized fixture execution.

## Semantic Disagreements

No `ENGINE_SEMANTIC_DISAGREEMENT` was established because no shared fixture cleared setup equivalence first.

Accordingly, WS-28 performs no Rules-Core winner adjudication and no majority voting.

## Direct Rules Defects

- `XMAGE_RULES_DEFECT`: **0 established**
- `FORGE_RULES_DEFECT`: **0 established**
- `BOTH_RULES_DEFECT`: **0 established**

`0 established Rules defects` is **not** a Rules-correctness PASS. Comparable execution was not reached.

## Provider / Setup Defects

- 18/18 starting shared PASS fixtures: `SETUP_NONISOMORPHIC`
- 16 Forge-only PASS IDs on XMage: exact provider/materialization gaps
- 16 XMage-only PASS IDs on Forge: exact provider/materialization gaps

A separate reproducibility observation remains recorded: the XMage clean-process replay scenario is stable, while one non-replay 5P lifecycle semantic transcript hash differed across exact-head workflow attempts despite the same PASS and decision count. WS-28 does not classify that as a Rules defect because the artifact does not preserve enough normalized transcript detail to minimize the cause.

## Authority-Blocked Cases

Direct Wizards authority was reverified for:

- `CARD_02` — Rograkh, Son of Rohgahh
- `CARD_04` — Kediss, Emberclaw Familiar
- `CARD_24` — Warstorm Surge

The remaining **26** actual-card fixtures are `AUTHORITY_BLOCKED_PENDING_WS29`.

No authority-pending fixture is counted as semantic differential PASS.

## Differential Coverage Matrix

Canonical machine-readable matrix:

`artifacts/ws28/WS28_FINALIST_MATRIX_135.json`

Strict 135-row verdict counts:

- `SETUP_NONISOMORPHIC`: **18**
- `CANDIDATE_UNSUPPORTED`: **91**
- `AUTHORITY_BLOCKED`: **26**
- `DIFFERENTIAL_AGREEMENT_PASS`: **0**
- `ENGINE_SEMANTIC_DISAGREEMENT`: **0**
- total: **135**

The matrix records, per fixture, Forge/XMage status and exact source identities, dual-execution state, setup/decision equivalence, comparison result, differential verdict, authority state, direct-defect classification and evidence hashes.

## Neutral CI / Reproducibility Evidence

Canonical successful neutral run:

- orchestration commit: `a93748470f2fac79ca94fe7ec770e65051ff32da`
- GitHub Actions run: `33329759026`
- job: `99306107781`
- conclusion: **SUCCESS**
- evidence commit produced by CI: `ebcbe83a36502235a091d3f21be8959f52d22a0d`

The successful job independently:

1. checked out the exact Forge candidate commit;
2. checked out the exact XMage behavioral candidate commit;
3. checked out the exact Forge engine commit/tree;
4. checked out the exact XMage engine commit/tree;
5. verified both candidate copies of the frozen common manifest SHA256;
6. downloaded the two immutable fresh provider evidence ZIPs and verified their SHA256 values;
7. rebuilt the WS-28 machine evidence;
8. ran the standalone WS-28 hard-gate test suite successfully;
9. ran `sha256sum -c WS28_SHA256SUMS` successfully;
10. verified that no candidate implementation path was vendored or merged into the neutral branch;
11. committed the reproducible machine evidence to the neutral branch.

Committed evidence manifest at `ebcbe83...`:

- `WS28_AUTHORITY_DEPENDENCY_REGISTER.json`: `4e7b4c8262d49fc87273d2374ee9fad21316a3f3bddbbc41210676716df41a74`
- `WS28_CROSS_MATERIALIZATION_RESULTS.json`: `f2ae4fd6f27c8f06bd07ad46a81ba78721d3e2162d2cea7c9e1972b7121f8681`
- `WS28_DIRECT_RULES_DEFECT_REGISTER.json`: `34005bf75026a2ca96be7bf2b0fd83d17f1e33cc9b6a544b51a8cbf935ae0195`
- `WS28_FINALIST_MATRIX_135.json`: `1ff7c70701ac75119117f449ab6c24616a0aaadfd8a9bd487d6d75d011f75a8f`
- `WS28_NORMALIZED_SEMANTIC_TRANSCRIPTS.json`: `87a7e30005d6840ee3a8566210e8cc98aecbf5e600faaf57b9f63000cfc96510`
- `WS28_PROVIDER_DISAGREEMENT_REGISTER.json`: `eb654e1daa39b4ffae8bf8a4cd927aa6da09e7fec710e7754f45175c27ac4029`
- `WS28_REPLAY_CHECKPOINT_EVIDENCE.json`: `46eb70114f6c23ff8ad83aec74035606f3e526ac7d262d6dda27d3fb25f7a4b7`
- `WS28_SEMANTIC_DISAGREEMENT_REGISTER.json`: `fc216942df0d4745dabc52e1efa5e36201421b8929081926bed335faf2e1fc65`
- `WS28_SOURCE_LOCK.json`: `985bfc9a03b8941a22ef447fb38037bed990d9d25b7f8832de30af59f9503922`
- `WS28_STRICT_18_DIFFERENTIAL.json`: `951bb4891e95b729819a392f823158e10f90db0c5e42d100237fe93d58b3f807`
- `WS28_SUMMARY.json`: `f4528193af30e1d8966230766aabd8e54efaa11627b2e33b173fe2cf862d0d30`

`WS28_FINAL_HANDOFF.md` is intentionally not part of this machine-evidence hash cycle because it must record the final CI/PR provenance after the evidence run. Its repository commit is separate provenance rather than a self-referential evidence hash.

## PASS / FAIL / UNKNOWN

| Gate | Result |
|---|---|
| starting overlap reconstruction | **PASS** |
| exact Forge source/build lock | **PASS** |
| exact XMage source/build lock | **PASS** |
| frozen protocol/135/manifest lock | **PASS** |
| fresh Forge provider rerun | **PASS** |
| fresh XMage provider rerun | **PASS** |
| 18/18 shared fixtures terminally classified | **PASS** |
| 32/32 asymmetric fixtures attempted opposite | **PASS** |
| semantic setup equivalence for nominal shared corpus | **FAIL — 0/18** |
| new exact cross-materialization | **FAIL — 0/32** |
| differential-verified semantic intersection | **FAIL — 0** |
| neutral WS-28 orchestration CI | **PASS** |
| result artifact/hash verification | **PASS** |
| no candidate implementation merged/vendored | **PASS** |
| direct engine Rules-defect adjudication | **UNKNOWN / NOT REACHED** |
| remaining 26 card authority states | **UNKNOWN — pending WS-29** |
| WS-28 stop conditions / workstream completion | **PASS / FULLY CLOSED** |
| final production Rules Core | **UNKNOWN / OUT OF SCOPE** |

## Finalist Implications

1. Raw `34 vs 34` PASS counts cannot select the Rules Core.
2. The nominal 18-fixture overlap is an identifier/outcome overlap, not yet a provider-neutral differential corpus.
3. The first-order blocker is missing provider-neutral semantic materialization, not a demonstrated Forge-vs-XMage Rules disagreement.
4. Any Architecture Freeze decision that treats the nominal 18 as differential agreement would violate `INDEPENDENT_PASS != DIFFERENTIAL_VERIFIED`.
5. WS-28 selects no winner.

## Remaining Blockers

### B1 — Provider-neutral scenario materialization

Before a final Rules-Core comparison, freeze a provider-neutral semantic materialization containing at minimum complete initial state, seat mapping, zones/card identities, starting life, rules seed, externally supplied discretionary decisions, semantic offered choices, checkpoints, terminal/postcondition assertions and normalization rules for provider object identity.

### B2 — WS-29 authority

26 actual-card authority states remain pending.

### B3 — Optional 5P reproducibility follow-up

If 5P lifecycle determinism becomes admission-critical, preserve enough normalized transcript evidence to explain the observed same-PASS transcript-hash drift.

## Outputs

Committed neutral WS-28 outputs include:

- `.github/workflows/ws28-finalist-differential.yml`
- `scripts/ws28_build_finalist_matrix.py`
- `tests/qualification/test_ws28_finalist_differential.py`
- `artifacts/ws28/WS28_SOURCE_LOCK.json`
- `artifacts/ws28/WS28_STRICT_18_DIFFERENTIAL.json`
- `artifacts/ws28/WS28_CROSS_MATERIALIZATION_RESULTS.json`
- `artifacts/ws28/WS28_FINALIST_MATRIX_135.json`
- `artifacts/ws28/WS28_NORMALIZED_SEMANTIC_TRANSCRIPTS.json`
- `artifacts/ws28/WS28_REPLAY_CHECKPOINT_EVIDENCE.json`
- `artifacts/ws28/WS28_SEMANTIC_DISAGREEMENT_REGISTER.json`
- `artifacts/ws28/WS28_PROVIDER_DISAGREEMENT_REGISTER.json`
- `artifacts/ws28/WS28_DIRECT_RULES_DEFECT_REGISTER.json`
- `artifacts/ws28/WS28_AUTHORITY_DEPENDENCY_REGISTER.json`
- `artifacts/ws28/WS28_SUMMARY.json`
- `artifacts/ws28/WS28_SHA256SUMS`
- `handoffs/ws28/WS28_FINAL_HANDOFF.md`

Raw provider evidence remains referenced by immutable Actions artifact IDs and SHA256 values rather than vendored into the neutral branch.

## Draft PR

- Draft PR: **#143**
- title: `WS-28: finalist differential and cross-materialization`
- base: `main`
- head: `ws28/finalist-differential`
- initial PR head at creation: `ebcbe83a36502235a091d3f21be8959f52d22a0d`
- state: **OPEN / DRAFT**
- merged: **NO**

The PR contains only neutral orchestration, tests, comparison evidence and this handoff. It does not merge PR #140 or #141 and does not select a final Rules Core.

## Dependencies Unblocked

WS-28 now provides a reproducible Architecture-Freeze input establishing that the next valid finalist comparison must use a newly frozen, fully materialized provider-neutral semantic corpus.

WS-29 can independently close the remaining card-authority ledger. A subsequent integration/Architecture-Freeze workstream can consume WS-28 + WS-29 without reopening the raw-count comparison.

## Exact Next Action

Coordinator/integration should consume this completed WS-28 handoff together with WS-29 when available, freeze the missing provider-neutral semantic materialization for the highest-value finalist corpus (starting with the nominal shared 18), and then execute that identical materialization on both finalists before any final Rules-Core selection.

**WS-28 itself is complete and closed. Do not select Forge or XMage as the production Rules Core from WS-28 raw PASS counts.**
