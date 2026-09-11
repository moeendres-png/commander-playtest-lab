# WS-19 — FORGE ISOLATED PROVIDER + WS-10R REQUALIFICATION
## FINAL POST-WS17R HANDOFF — COMPLETE

**Project:** COMMANDER SIMULATION FOUNDRY  
**Target repository:** `moeendres-png/commander-playtest-lab`  
**Workstream:** WS-19  
**Final workstream status:** `COMPLETE`  
**Candidate:** Forge  
**Candidate classification:** `REMEDIATION_REQUIRED`  
**Freeze eligibility:** `NO`  
**Final Rules Core selection:** `NOT PERFORMED`  
**Merge authorization:** `NONE`  
**Canonical evidence generation baseline:** post-WS17R only

> All pre-WS17R WS-19 candidate qualification evidence is invalidated for current admission purposes. Candidate code was salvaged only through controlled review; canonical runtime evidence was regenerated on the healthy post-WS17R baseline.

---

# Source Lock

## Commander Lab baseline

Canonical WS-19 baseline:

- repository: `moeendres-png/commander-playtest-lab`
- commit: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- tree: `551c0d55a171508618d2b7d29e0f49b19893f886`
- license: `LicenseRef-Proprietary`
- baseline status: `COMMON_QUALIFICATION_BASELINE_HEALTHY`

Canonical WS-19 runtime-bearing candidate code identity:

- branch: `ws19/forge-isolated-provider-requalification-v2`
- runtime code commit: `d06fe667e5bc432709cf9244ea2188a543386c91`
- runtime code tree: `8a81a89d2b75c684d649437131448ef30c710265`

Documentation-only closure commits occur after the runtime-bearing code commit. They do not supersede or rewrite the canonical runtime result.

## WS-10R / common contract lock

- protocol: `commander-lab.rules-service/1.1.0`
- WS-10R bundle SHA-256: `2f002a4d020e99e44270239fd3a894e9be6f08eddf9fdd233b81ba8d3f070577`
- common fixture manifest SHA-256: `e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`
- obligation catalog SHA-256: `df3b354858d5e01cdb899ac24cdbf5f269fb81c0bf495b1bcb4129b1498dd963`

WS-19 did not change common WS-10R semantics, the common fixture manifest, the obligation catalog, denominator manifests, or the WS-17R exact-main repair.

---

# Healthy Baseline Verification

The coordinator-approved healthy baseline was independently reproduced before new Forge qualification evidence was generated.

Authoritative exact-main repair verification:

- workflow: `Production Qualification`
- run: `33262473086`
- event: `push`
- branch: `main`
- head: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- tree: `551c0d55a171508618d2b7d29e0f49b19893f886`
- workflow conclusion: `SUCCESS`

WS-19 baseline reproduction on the V2 branch then executed:

1. `tests/qualification`;
2. common fixture schema / frozen hash validation;
3. provider-absence common harness;
4. provider-absence aggregate.

Observed baseline reproduction result:

- harness process: `SUCCESS`
- required fixtures: `135`
- provider-absence fixture verdicts: `135/135 NOT_RUN`
- missing fixture IDs: `0`
- `PRODUCTION_ADMISSION = FAIL`

This is the expected healthy provider-absence state. The baseline reproduction gate therefore passed.

**Gate:** `PASS`

---

# Old Branch / PR Provenance

The pre-WS17R WS-19 branch is retained only as provenance.

- old branch: `ws19/forge-isolated-provider-requalification`
- old base: `9665c9d5dc5e720240b99f88300176c7a4a0f4fa`
- old head: `3e4e5b4da27c46638dfbf14bba9c03bcca3ddefd`
- old head tree: `ff9744728f49230bfdf32a22cb9133b7f7f074b8`
- commits ahead of old base: `16`
- exact commit range: `9665c9d5dc5e720240b99f88300176c7a4a0f4fa..3e4e5b4da27c46638dfbf14bba9c03bcca3ddefd`
- old Draft PR: `#132`
- old PR state: `DRAFT / OPEN / UNMERGED`
- disposition: `PROVENANCE ONLY — DO NOT MERGE AS-IS`

Old changed paths at the frozen old head:

- `.github/workflows/ws19-forge-qualification.yml`
- `artifacts/ws19/forge/README.md`
- `artifacts/ws19/forge/WS19_EXPECTED_SOURCE_LOCK.json`
- `scripts/ws19_generate_forge_probe.py`
- `scripts/ws19_run_forge_provider.py`
- `scripts/ws19_summarize_forge_results.py`
- `tests/qualification/test_ws19_forge_isolation.py`

No pre-WS17R runtime or AF verdict is admissible for the current WS-19 qualification.

All historical Action artifacts, transient common results, generated AF results, candidate matrices, aggregate results and stale source-lock outputs from the old baseline are classified:

`PROVISIONAL_PRE_WS17R_NOT_ADMISSIBLE`

---

# Controlled Salvage Matrix

The V2 implementation was created from the exact healthy baseline and used manual controlled transplantation rather than a blind rebase/cherry-pick.

| Path | Classification | Final runtime Git blob |
|---|---|---|
| `scripts/ws19_generate_forge_probe.py` | `SALVAGE_CANDIDATE_CODE` | `f5ef79a6e7e600b2d126d577379c80908080b3af` |
| `scripts/ws19_run_forge_provider.py` | `SALVAGE_CANDIDATE_CODE` | `56665947908795e51bee7a3aa4d78242dc73aa9f` |
| `scripts/ws19_summarize_forge_results.py` | `SALVAGE_CANDIDATE_CODE_REEXECUTE_ONLY` | `bdf16e2fcfeda5460600cc68b39c4b954502a594` |
| `tests/qualification/test_ws19_forge_isolation.py` | `SALVAGE_TEST` | `a721a2f216de95dcc5ab611774e09bb0f32ea869` |
| `.github/workflows/ws19-forge-qualification.yml` | `REWRITE_FOR_NEW_BASELINE` | `7ec6b69c3d98a044680c4969fff7efe61a8969d7` |
| `artifacts/ws19/forge/WS19_EXPECTED_SOURCE_LOCK.json` | `REWRITE_FOR_NEW_BASELINE` | `c7630841c0219aa189302dedd71a9f65489806f2` |
| `artifacts/ws19/forge/README.md` | `REWRITE_FOR_NEW_BASELINE` | `8547b16d0162091e058a9d82223c34ca1967753c` |

Deterministic salvage runtime-path manifest:

- algorithm: SHA-256 over sorted UTF-8 lines of `<git_blob>  <path>\n`
- SHA-256: `59c3f5ca0684e72eda00fe99c5f65d484ae3ebe3ad1d2ff4ba2ee88191109a58`

Final provenance manifest:

`handoffs/ws19/WS-19_CONTROLLED_SALVAGE_FINAL.json`

Explicitly **not transplanted**:

- pre-WS17R AF outputs;
- pre-WS17R `COMMON_RESULTS`;
- pre-WS17R candidate matrices;
- pre-WS17R Production Admission outputs;
- pre-WS17R aggregate evidence;
- stale runtime source-lock outputs;
- any common WS-10R semantic change;
- any common fixture-manifest change;
- any obligation-catalog change;
- any denominator-manifest change;
- any WS-17R repair modification.

`shared_infrastructure_changes_transplanted = false`

**Controlled salvage:** `PASS`

---

# Forge Source Lock

Fresh post-WS17R Forge lock:

- repository: `Card-Forge/forge`
- branch: `master`
- commit: `1e604105f9e279331063824943b9222b6589f5d8`
- tree: `994976e06aaf99b807646b60b1aa2ac9f7703df4`
- version: `2.0.15-SNAPSHOT`
- toolchain: Maven / Java 17
- license classification for this project: `GPL-3.0-or-later`
- LICENSE Git blob: `e72bfddabc15be5718a7cc061ac10e47741d8219`
- `PlayerController.java` Git blob: `192ef8737ecd645b75d50782693d5eab948d43a7`
- `RemoteClientGuiGame.java` Git blob: `768faa260fd3d8049258f38419e48704e257a490`

Fresh relock comparison against the pre-stop Forge lock:

- Forge commit changed: `false`
- Forge tree changed: `false`
- PlayerController blob changed: `false`
- RemoteClientGuiGame blob changed: `false`

The prior candidate source identity therefore remained current, but all runtime qualification evidence was regenerated anyway.

**Forge source lock:** `PASS`

---

# License / Process Boundary

WS-09 remains binding.

Required topology:

```text
proprietary Commander Lab
        |
        | WS-10R
        v
separate Forge-side GPL-compatible provider process
        |
        v
Forge Rules Core
```

Implemented qualification topology:

- proprietary launcher is Python and does not import/link Forge Java classes;
- Forge is checked out into a separate workspace;
- Forge is built unmodified;
- generated GPL-side Java sources are produced separately;
- generated provider classes are compiled separately against Forge game/core outputs;
- provider is launched as a separate JVM process;
- proprietary side communicates only through the WS-10R transport;
- no Forge card scripts are copied into proprietary canonical data;
- Forge AI and stock GUI modules are excluded from the qualification provider classpath.

The handshake runtime additionally reported:

- `ai_module_present = false`
- `stock_remote_gui_present = false`
- `strict_controller_direct_superclass = true`

**License/process-boundary qualification:** `PASS`

This is an engineering/license-compatibility conclusion under the project contract, not legal advice.

---

# Provider Implementation

Implemented proprietary-side components:

### `scripts/ws19_run_forge_provider.py`

Fail-closed transport launcher:

- requires explicit `COMMANDER_LAB_FORGE_PROVIDER_CMD`;
- creates a separate subprocess;
- validates WS-10R protocol identity;
- validates request/response IDs;
- passes provider payloads without constructing legal actions;
- does not filter/rank/reinterpret Forge legality;
- missing provider command fails nonzero.

### `scripts/ws19_generate_forge_probe.py`

Generates GPL-side qualification source from fresh Forge source:

- mechanically enumerates abstract `PlayerController` callbacks;
- generates a direct strict `PlayerController` subclass;
- every unimplemented callback throws a typed `UnsupportedOperationException`;
- generates the separate Forge-loaded WS-10R probe provider;
- records callback/source hashes;
- records prohibited stock remote fallback findings.

### Generated Forge-side probe

Fresh runtime handshake result:

- provider: `forge`
- protocol: `commander-lab.rules-service/1.1.0`
- handshake verdict: `PASS`
- evidence class: `RUNTIME_VERIFIED`
- generated abstract count: `109`
- runtime abstract count: `109`
- Forge commit/tree/version match source lock
- `rules_core_fixture_execution = UNSUPPORTED`

The provider is therefore a valid isolated, fail-closed qualification shell.

It is **not** a complete Forge Full-Rules provider.

Not implemented:

- persistent real game/session lifecycle;
- real Forge state materialization for WS-10R fixtures;
- legal-action / DecisionFrame export;
- exact DecisionFrame submission;
- priority decision routing;
- combat decision routing;
- trigger ordering/selection routing;
- mana/payment decision routing;
- replacement/prevention choices;
- Commander choices;
- actor-safe observation serialization;
- event tape;
- rules RNG tape;
- DecisionTape;
- replay checkpoints and clean-process semantic replay.

**Provider shell:** `PASS`  
**Full-Rules provider implementation:** `UNSUPPORTED / REMEDIATION_REQUIRED`

---

# Decision-Surface Closure

Fresh Forge `PlayerController` census:

- abstract callbacks: `109`
- generated strict overrides: `109`
- runtime abstract callbacks observed by reflection: `109`

Stock `RemoteClientGuiGame` prohibited defaults found:

1. line 436: `return result != null ? result : defaultYes;`
2. line 442: `return result != null ? result : defaultOption;`
3. line 453: `return result != null ? result : defaultIsYes;`

The qualification provider does **not** load the stock remote GUI path and does **not** load Forge AI.

This proves that the qualification shell mechanically traps the identified abstract decision surface and avoids the known stock fallback route.

It does **not** prove complete production decision support because the provider does not translate all production-reachable Forge decisions into externally owned WS-10R DecisionFrames. A throwing shell is fail-closed infrastructure, not full support.

**Decision-surface closure:** `PARTIAL`

No production qualification credit is given for throwing rather than implementing a decision.

---

# Changes

Post-WS17R V2 branch candidate/runtime paths before documentation closure:

- `.github/workflows/ws19-forge-qualification.yml`
- `artifacts/ws19/forge/CONTROLLED_SALVAGE.json`
- `artifacts/ws19/forge/README.md`
- `artifacts/ws19/forge/WS19_EXPECTED_SOURCE_LOCK.json`
- `scripts/ws19_generate_forge_probe.py`
- `scripts/ws19_run_forge_provider.py`
- `scripts/ws19_summarize_forge_results.py`
- `tests/qualification/test_ws19_forge_isolation.py`

Documentation/provenance closure adds:

- `handoffs/ws19/WS-19_CONTROLLED_SALVAGE_FINAL.json`
- `handoffs/ws19/WS-19_FINAL_HANDOFF_COMPLETE.md`

No common qualification semantic file was changed.

---

# Tests Executed

Canonical runtime workflow:

- workflow: `WS-19 Forge Post-WS17R Requalification`
- run: `33265726473`
- event: `push`
- branch: `ws19/forge-isolated-provider-requalification-v2`
- head: `d06fe667e5bc432709cf9244ea2188a543386c91`
- conclusion: `SUCCESS`

Successful steps included:

1. checkout post-WS17R branch;
2. verify exact healthy baseline and frozen common semantics;
3. install committed qualification runtime;
4. run qualification tests;
5. reproduce provider-absence common harness and aggregate;
6. checkout exact Forge source;
7. verify Forge source and GPL boundary lock;
8. verify Forge Maven version;
9. generate strict GPL-side controller/provider;
10. build pinned unmodified Forge modules;
11. resolve Forge compile classpath;
12. compile generated provider separately;
13. execute WS-10R handshake;
14. execute all 135 common fixtures;
15. summarize candidate execution;
16. validate candidate-result schema;
17. hash the WS-19 artifact bundle;
18. upload the WS-19 artifact bundle.

Canonical artifact:

- artifact ID: `9718602687`
- name: `ws19-post-ws17r-d06fe667e5bc432709cf9244ea2188a543386c91`
- artifact SHA-256: `89511fbfcf5dd6b853f020956827845da123841a463e377fd391a5ac1b161a41`
- internal SHA-256 manifest entries: `22`
- internal manifest validation: `PASS`, `0` mismatches/missing files

Additional PR-triggered checks associated with the same runtime code commit were also successful:

- `Production Qualification`: `SUCCESS`
- `Windows Runtime Hygiene`: `SUCCESS`
- `WS-19 Forge Post-WS17R Requalification`: `SUCCESS`
- `CI`: `SUCCESS`

---

# Tests Not Run

The harness invocation itself covered all 135 mandatory fixtures, but the current provider intentionally returned typed `UNSUPPORTED` before executing real Forge game semantics.

Therefore the following are **not runtime-qualified semantic executions**:

- real 2P game lifecycle;
- real 3P game lifecycle;
- real 4P game lifecycle;
- real 5P game lifecycle;
- APNAP / multiplayer rules behavior;
- Commander rules behavior;
- legal-action correctness;
- priority and stack behavior through real Forge sessions;
- combat behavior;
- trigger behavior;
- mana/payment behavior;
- replacement/prevention behavior;
- actor-safe hidden-information serialization;
- deterministic rules RNG recording;
- DecisionTape/EventTape;
- checkpoint/clean-process replay;
- behavioral execution of the 29-card corpus.

These are not silently treated as `PASS`.

They remain `UNSUPPORTED`.

---

# 2P–5P Matrix

All manifest fixtures reached the isolated provider process. No semantic Forge game route was implemented.

| Player count | Manifest fixtures carrying that player count | Result |
|---|---:|---|
| 2P | 4 | `4 UNSUPPORTED` |
| 3P | 10 | `10 UNSUPPORTED` |
| 4P | 115 | `115 UNSUPPORTED` |
| 5P | 6 | `6 UNSUPPORTED` |

The dedicated player-count fixture category contains four mandatory fixtures and all four are `UNSUPPORTED`.

**2P–5P engine-backed qualification:** `UNSUPPORTED`

---

# Multiplayer / Commander

Common category:

- fixtures: `36`
- verdicts: `36 UNSUPPORTED`

The isolated provider did not execute:

- APNAP behavior;
- multiplayer priority;
- simultaneous multiplayer choices;
- Commander-specific zone/replacement choices;
- commander tax/casting semantics;
- Commander damage / elimination interactions;
- other frozen multiplayer/Commander obligations.

No engine-backed multiplayer/Commander PASS is claimed.

**Multiplayer / Commander:** `UNSUPPORTED`

---

# Observation / Hidden Information

Common hidden-information category:

- fixtures: `20`
- verdicts: `20 UNSUPPORTED`

Actor-scoped Forge observation serialization is not implemented.

The provider therefore does not yet demonstrate:

- legal actor-specific information boundaries;
- opponent hand/library secrecy;
- hidden-object identity control;
- honeycard sentinel protection;
- observation stability across DecisionFrames.

**Observation / Hidden Information:** `UNSUPPORTED`

---

# Replay / RNG

Common replay/RNG category:

- fixtures: `5`
- verdicts: `5 UNSUPPORTED`

Not implemented:

- rules RNG tape;
- DecisionTape;
- EventTape;
- state checkpoints;
- clean-process replay;
- semantic replay hash equivalence.

Forge's native randomness behavior is not accepted as a substitute for WS-10R replay qualification.

**Replay / RNG:** `UNSUPPORTED`

---

# 29-Card Corpus

The authoritative common 29-card denominator was executed through the common harness.

- denominator size: `29`
- fixture IDs: `CARD_01` through `CARD_29`
- results present: `29/29`
- missing: `0`
- verdict: `29/29 UNSUPPORTED`

Every card result carries the fresh Forge source lock and the typed fail-closed reason:

`WS19_FAIL_CLOSED: Forge rules/DecisionFrame fixture route is not implemented; no AI/default/GUI fallback used`

Static Forge card implementation presence is not promoted to behavioral proof.

**29-card behavioral corpus:** `UNSUPPORTED`

---

# WS-10R / Common Harness

Canonical common run:

- required fixtures: `135`
- fixture results returned: `135`
- missing fixtures: `0`
- runtime verdict counts:
  - `UNSUPPORTED: 135`

Category breakdown:

| Category | Count | Verdict |
|---|---:|---|
| actual card | 29 | `29 UNSUPPORTED` |
| hidden information | 20 | `20 UNSUPPORTED` |
| micro rules | 17 | `17 UNSUPPORTED` |
| multiplayer / Commander | 36 | `36 UNSUPPORTED` |
| pilot boundary | 17 | `17 UNSUPPORTED` |
| pilot-boundary negative | 7 | `7 UNSUPPORTED` |
| player count | 4 | `4 UNSUPPORTED` |
| replay / RNG | 5 | `5 UNSUPPORTED` |
| **Total** | **135** | **135 UNSUPPORTED** |

Handshake is separately `PASS` because the isolated process, exact source identity and strict fail-closed shell were runtime verified.

The handshake explicitly states:

`rules_core_fixture_execution = UNSUPPORTED`

Thus denominator completeness does not imply rules correctness.

---

# AF00–AF11

| Gate | Verdict | Basis |
|---|---|---|
| AF00 | `PASS` | Pinned Forge source/tree/version, generated GPL-side source identity and provider identity recorded. |
| AF01 | `PASS` | Exact WS-10R 1.1 handshake executed and truthfully reports semantic fixture execution unsupported. |
| AF02 | `UNSUPPORTED` | 2P–5P common fixtures reach shell but no Forge game lifecycle/DecisionFrame route exists. |
| AF03 | `UNSUPPORTED` | No real Forge rules execution for common fixtures; sole Rules-Core authority is not runtime-qualified. |
| AF04 | `PARTIAL` | 109 abstract callbacks mechanically trapped and AI/stock GUI absent, but external DecisionFrame route is not implemented. |
| AF05 | `UNSUPPORTED` | Actor-scoped observation serialization/honeycard behavior not implemented. |
| AF06 | `UNSUPPORTED` | Micro-rules fixtures fail closed before semantic Forge execution. |
| AF07 | `UNSUPPORTED` | 29-card denominator complete but no Forge card semantics executed. |
| AF08 | `UNSUPPORTED` | Commander/multiplayer denominator complete but no semantic rules execution. |
| AF09 | `UNSUPPORTED` | RNG tape, DecisionTape, EventTape, checkpoints and clean-process semantic replay not implemented. |
| AF10 | `PASS` | All 135 fixtures return explicit typed results; no missing fixture, crash, silent skip or fallback. |
| AF11 | `PASS` | Separate JVM topology; proprietary launcher imports no Forge classes; AI/stock GUI excluded from provider classpath. |

Mandatory non-PASS obligations remain.

---

# PASS / FAIL / UNKNOWN

## PASS

- post-WS17R baseline source lock;
- healthy exact-main baseline reproduction;
- frozen WS-10R/common hashes;
- fresh Forge source lock;
- pristine Forge build;
- separate-process GPL boundary;
- strict provider compilation/start;
- WS-10R handshake;
- denominator-complete explicit reporting for 135/135 fixtures;
- fail-closed handling instead of AI/default/GUI/silent fallback;
- runtime artifact hashing;
- general CI/security/runtime-hygiene checks at the runtime code head;
- controlled salvage provenance.

## PARTIAL

- strict decision-surface closure: abstract callbacks are trapped, but a complete external DecisionFrame implementation does not exist.

## UNSUPPORTED

- engine-backed 2P–5P;
- full Rules-Core authority;
- observation/hidden information;
- micro-rules;
- 29-card behavioral corpus;
- multiplayer/Commander;
- replay/RNG;
- real legal-action/DecisionFrame execution.

## FAIL

Expected provider-absence baseline aggregate:

- `PRODUCTION_ADMISSION = FAIL`

This is the required healthy-baseline reproduction result when no provider command is configured; it is not a Forge semantic failure verdict.

## UNKNOWN / BLOCKED AUTHORITY

The candidate result preserves:

`authority_status = BLOCKED_ORACLE_AND_BYTE_EXACT_CR`

This common authority blocker is not converted to PASS by WS-19. It is also not necessary to reject Freeze eligibility here because Forge already has mandatory `UNSUPPORTED`/`PARTIAL` gates.

---

# Freeze Eligibility

Hard-pass rule:

Any mandatory `FAIL`, `UNKNOWN`, `PARTIAL`, `NOT_RUN`, or `UNSUPPORTED` blocks Freeze eligibility.

Current mandatory non-PASS Forge gates include:

- AF02 `UNSUPPORTED`
- AF03 `UNSUPPORTED`
- AF04 `PARTIAL`
- AF05 `UNSUPPORTED`
- AF06 `UNSUPPORTED`
- AF07 `UNSUPPORTED`
- AF08 `UNSUPPORTED`
- AF09 `UNSUPPORTED`

Therefore:

`FORGE_FREEZE_ELIGIBLE = NO`

`FORGE_CLASSIFICATION = REMEDIATION_REQUIRED`

No Architecture Freeze is granted.

No final Rules Core is selected.

---

# Remaining Blockers

If Forge is pursued further, the next Forge-specific implementation must provide a genuine GPL-compatible companion service with real engine-backed behavior.

Mandatory blockers:

1. persistent Forge game/session lifecycle;
2. deterministic 2P–5P session creation;
3. lossless actor-safe observation serialization;
4. legal-action / DecisionFrame extraction from Forge authority;
5. exact DecisionFrame submission into Forge;
6. full external routing for every production-reachable discretionary decision;
7. no AI, first-option, random-option, default yes/no, GUI fallback, inherited fallback or silent skip;
8. priority/stack integration;
9. combat decision integration;
10. trigger routing;
11. mana/payment routing;
12. replacement/prevention choices;
13. Commander-specific decisions;
14. normalized event output;
15. rules RNG provenance;
16. DecisionTape/EventTape/checkpoints;
17. clean-process replay;
18. real semantic execution of all 135 common fixtures;
19. real semantic execution of all 29 card fixtures;
20. resolution of common Oracle/byte-exact Comprehensive Rules authority if still globally blocked when production admission is attempted.

No proprietary-side reconstruction of Forge legality is an acceptable workaround.

---

# GPL Companion / Packaging Requirements

A production Forge path should use a separately distributed GPL-compatible provider/companion.

Minimum packaging requirements:

- separate process boundary from proprietary Commander Lab;
- Forge source/version/commit/tree pinned;
- GPL license and required notices preserved;
- provider source distributed under a GPL-compatible model appropriate to the derivative Forge integration;
- deterministic provider build identity;
- provider binary/source artifact digests;
- explicit WS-10R version compatibility;
- no proprietary in-process linkage;
- no Forge Java object graph as proprietary normative protocol;
- no Forge card scripts copied into proprietary canonical data;
- no hidden fallback from provider failure to Forge AI/GUI/default controller behavior;
- fail-closed startup and protocol mismatch handling.

The current generated CI probe is qualification infrastructure, not the required durable production companion package.

---

# Outputs

Committed candidate/runtime outputs:

- `.github/workflows/ws19-forge-qualification.yml`
- `artifacts/ws19/forge/CONTROLLED_SALVAGE.json`
- `artifacts/ws19/forge/README.md`
- `artifacts/ws19/forge/WS19_EXPECTED_SOURCE_LOCK.json`
- `scripts/ws19_generate_forge_probe.py`
- `scripts/ws19_run_forge_provider.py`
- `scripts/ws19_summarize_forge_results.py`
- `tests/qualification/test_ws19_forge_isolation.py`

Final closure outputs:

- `handoffs/ws19/WS-19_CONTROLLED_SALVAGE_FINAL.json`
- `handoffs/ws19/WS-19_FINAL_HANDOFF_COMPLETE.md`

Canonical runtime artifact contents include:

- baseline `COMMON_RESULTS.json`
- baseline `PRODUCTION_ADMISSION.json/.md`
- current `COMMON_RESULTS.json`
- provider handshake
- Forge build log
- callback inventory
- generated-source manifest
- 29-card matrix
- common execution summary/report
- candidate AF result
- SHA-256 manifests

Canonical runtime artifact:

- Action run: `33265726473`
- artifact ID: `9718602687`
- SHA-256: `89511fbfcf5dd6b853f020956827845da123841a463e377fd391a5ac1b161a41`

---

# New Draft PR

Post-WS17R PR:

- PR: `#135`
- title: `WS-19: Forge isolated provider requalification (post-WS17R)`
- branch: `ws19/forge-isolated-provider-requalification-v2`
- base: `main`
- original PR base SHA: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- state: `DRAFT`
- merged: `false`
- required marker: `POST_WS17R_REQUALIFICATION`

PR #132 remains pre-WS17R provenance and is not to be merged as-is.

No merge is authorized for PR #135 by this workstream.

---

# Dependencies Unblocked

WS-19 now provides the Coordinator with a canonical, post-WS17R Forge result:

- isolation/build/handshake infrastructure is viable;
- the current Forge provider shell is not a Full-Rules provider;
- Forge is not Freeze-eligible;
- all pre-WS17R WS-19 qualification evidence is superseded for admission purposes;
- the exact remediation boundary is known;
- no final candidate selection has been made.

This unblocks coordinator comparison/integration against the other candidate qualification workstreams without treating Forge's broad native card/rules implementation as proof of WS-10R compliance.

---

# Exact Next Action

Coordinator action:

1. ingest this handoff as the canonical WS-19 result;
2. retain Forge as `REMEDIATION_REQUIRED` and `NOT FREEZE-ELIGIBLE`;
3. do not merge PR #132;
4. do not merge PR #135 without a later explicit integration decision;
5. do not select Forge as final Rules Core solely from WS-19;
6. compare this result against the other candidate workstreams under the common Architecture Freeze contract.

If the Coordinator later authorizes Forge remediation, open a **new dedicated workstream** for the durable GPL Forge companion service and full engine-backed WS-10R DecisionFrame/session/observation/replay implementation. That remediation must rerun all mandatory common evidence after implementation.

No further action is required inside WS-19.

---

# Final Workstream Verdict

`WS-19_WORKSTREAM = COMPLETE`

`COMMON_BASELINE_REPRODUCTION = PASS`

`FORGE_SOURCE_LOCK = PASS`

`GPL_PROCESS_ISOLATION = PASS`

`WS10R_HANDSHAKE = PASS`

`COMMON_FIXTURE_DENOMINATOR = 135/135 EXECUTED`

`COMMON_SEMANTIC_RESULT = 135/135 UNSUPPORTED`

`29_CARD_BEHAVIORAL_RESULT = 29/29 UNSUPPORTED`

`DECISION_SURFACE_CLOSURE = PARTIAL`

`FORGE_FREEZE_ELIGIBLE = NO`

`FORGE_PRODUCTION_QUALIFIED = NO`

`FINAL_RULES_CORE_SELECTION = NOT PERFORMED`

**WS-19 is formally and technically closed.**
