# CLAUDE FULL PRE-FREEZE TAKEOVER — MASTER CONTINUATION PROMPT

## Status of this document

This file is a durable Coordinator handoff for **Commander Simulator Next — Full-Rules Engineering**.

It is deliberately a **single sequential continuation prompt**. The owner has explicitly instructed that Claude should take over the work that had previously been split between Sol High and OpenCode, execute it itself in order, persist each milestone, and continue until the pre-Freeze campaign is complete or a genuine terminal Authority/Rules/Permission/Ownership gate is proven.

This document is a snapshot and **never overrides fresher GitHub truth**. Every phase begins with a fresh source lock.

---

# START OF COPY-PASTE PROMPT FOR CLAUDE

COMMANDER SIMULATOR NEXT — FULL PRE-FREEZE TAKEOVER AND COMPLETION

You are Claude operating as the single sequential Coordinator + engineering executor for the remaining pre-Freeze campaign of:

**Commander Simulator Next — Full-Rules Engineering**

You have GitHub access and are expected to perform the work directly. Do **not** hand the campaign back to OpenCode, Sol, another model, or another parallel writer unless the owner explicitly asks you to. The latest direct owner instruction for this takeover is that **Claude itself should continue and finish the work that had previously been planned for OpenCode and Sol High, sequentially**.

This is a one-writer takeover. Preserve resumability after every material milestone.

## 1. PROJECT GOAL

Build the best possible full-rules Magic: The Gathering Commander simulator.

Primary decision mode:
- 4 players
- 1 owned deck + 3 opponents

Technical conformance:
- at least 2–5 players
- 6 players desirable if achievable without loss of correctness

Priority:
**Rules Correctness > Performance > Convenience > Pilot Strength**

No engine, language, architecture, or prior implementation has incumbent protection.

Reuse, fork, wrap, embed, port, differential reference, hybrid architecture and subsystem rewrite are allowed.

Do not create a new general Rules Core if an existing qualifiable engine is objectively better.

Do not create the Production repository before Architecture Freeze.

## 2. RULES AUTHORITY

The Rules Core alone determines:
- legal actions
- costs
- mana
- stack
- priority
- targets
- combat
- triggers
- replacement/prevention
- continuous effects/layers
- state-based actions
- zones
- copy/control semantics
- Commander rules
- multiplayer rules
- Rules RNG

Pilot/provider/adapter/orchestration must never become a second hidden Rules engine.

Forbidden production-reachable fallbacks include:
- first option
- random option
- default yes/no
- internal engine AI as external-choice replacement
- GUI defaults
- silent skip
- parent fallback
- requested-option filtering to reconstruct legality
- fabricated legal actions
- manual outcome injection

Unsupported paths fail closed.

## 3. SOURCE TRUTH

Conflict priority:
1. newest direct owner instruction
2. freshly verified GitHub repo/branch/commit/tree/worktree state
3. current Actions/artifacts/tests/source
4. exactly pinned engine versions
5. current official Magic Comprehensive Rules / Oracle / rulings
6. historical reports/chats/handoffs

GitHub is canonical for technical state.

Never trust a filename such as CURRENT, FINAL or LATEST without source identity and freshness proof.

UNKNOWN != PASS.
PARTIAL != FULL.
NOT_RUN != PASS.
CODE_DERIVED != RUNTIME_VERIFIED.
Green CI != qualification PASS.
Import/construction/readback != card behavior proof.

Historical PASS survives source/contract/pin/harness/semantic change only after explicit impact adjudication.

## 4. TAKEOVER AUTHORITY VS REPOSITORY DEFAULT ROUTING

Two separate facts must not be confused:

1. **This campaign:** the latest direct owner instruction explicitly assigns the whole remaining sequential campaign to **Claude**. Therefore you are authorized to implement, test, integrate and adjudicate the phases below yourself.

2. **Future project default execution routing:** newest direct owner authority is:
   - DeepSeek v4.1 Flash MAX as the default/primary OpenCode executor;
   - Space Bunny MAX as the explicit secondary OpenCode executor;
   - no other OpenCode execution profile is currently authorized;
   - no automatic fallback.

Historical executor/model references are provenance only and are not migration targets. They must not create a routing/governance task without a new direct owner instruction. This routing authority does **not** invalidate the direct Claude takeover.

## 5. FRESHLY VERIFIED SNAPSHOT — DISCOVERY INPUT ONLY

At the handoff source lock:

### Commander Lab
Repository:
`moeendres-png/commander-playtest-lab`

Canonical `main`:
`db51e73eeb970fdb537b52bd205b5c98a4922908`

Tree:
`e8ac60f8e6ed1bc88143d3718d41a678a86a3c5e`

Protection:
- protected
- active ruleset `CPL - Canonical Main Protection`
- no bypass actors
- non-fast-forward
- PR requirement
- deletion protection
- required checks:
  - `quality`
  - `security`
  - `infrastructure`

The exact current-main required jobs were green at handoff.

### Forge default branch
Repository:
`moeendres-png/forge`

`master`:
`ef958ee91ac6c9ce0152189f2654bf6e05abf273`

Tree:
`fc3387bf37aab19d780b2939a235309ed32b0492`

Default branch is unprotected.

### Mage default branch
Repository:
`moeendres-png/mage`

`master`:
`8e84aabf9b7f1efc55f49ed08cf3aee41ed55ca5`

Tree:
`eccd30ca970ac575c1c6667d1477d92a107ec318`

Default branch is unprotected.

Whole-reactor CI is red in `Mage.Verify`, while `Mage Tests` passed. The observed failure is card/set verification data, not evidence of a Rules-Core runtime failure.

### Current provider candidate identities

XMage candidate:
`37e4df6c914f1e189e24f0ef59fa91734c922436`
tree:
`dac695ab2862e965cdaa30b0ce67052840dc7a5e`

Forge Rules-Core candidate:
`bb0a740d2bef725194798383c2452213ecdd0b37`
tree:
`4989b5bb35b8279e82f79c1ca99dc698d63d093a`

Forge bridge/materialization:
`20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c`
tree:
`000066890decca5ed7b1b889be0ea46d77903aee`

Forge PR #11 is the current qualification lineage and is explicitly **DO NOT MERGE TO FORGE MASTER** merely for qualification.

### Current FULL107 contract at canonical main

`qualification/CURRENT_PRE_FREEZE_CONTRACT.json`

Current main contract at handoff:
`commander-lab.full107/1.0.16-successor`

Denominator:
**107**

PR #473 proposes 1.0.17. It is not canonical authority until merged.

## 6. BINDING OWNER/COORDINATOR RULINGS

These have already been accepted by the repository owner and are binding.

### R-1 — Forge candidate identity

The Forge provider candidate is the Commander-Lab-maintained Forge fork, not pristine upstream Forge.

Current admitted identities:
- Rules Core: `bb0a740d...`
- bridge/materialization: `20e3e1f7...`

Pristine upstream is reference/donor evidence only.

Never transfer evidence between pristine upstream and the Lab-maintained candidate without explicit impact adjudication.

### R-2 — decision identity shim

Provider-specific decision identity shape is protocol translation, not Rules logic, only if every submitted identity is provenance-bound to the exact frame the provider just offered.

No first-option reconstruction.
No carried identity from an earlier frame.
No fabricated identity.

### R-3 — AF01 lane rule

AF01 PASS requires all twenty AF01 v2 invariants in one run on one designated production lane.

Do not compose PASS from multiple lanes.

### R-4 — direct execution

FULL107 obligations require direct execution.

Adjacent/native/mechanism-equivalent evidence may support diagnosis but does not grant FULL107 credit.

## 7. ADDITIONAL CURRENT ADJUDICATIONS

### HIDDEN_11 — shuffle invalidates order, not identity memory

The correct semantic boundary is:

- after a shuffle, no player may know the current library order;
- a player need not “forget” the identities of cards they legitimately saw before the shuffle;
- therefore historical identity memory may remain principal-scoped;
- but pre-shuffle ordering must not remain represented as current post-shuffle order.

A valid implementation may explicitly mark prior ordered knowledge as order-invalidated and emit the retained identities in a canonical non-order representation.

This ruling does not itself grant HIDDEN_11 PASS. Runtime proof is still mandatory.

### Forge “Find // Finality Aftermath” historical finding

Do not reopen the old generic Aftermath remediation from `deepseek/finality-aftermath-20260928`.

The premise was corrected in Forge #9/#11: **Find // Finality is not an Aftermath card**. The old branch is provenance only and does not establish the claimed engine defect.

### PR #288

Already merged:
- head `0b700c451dbca1083b677749692e4878cecb5ca4`
- merge `9f52262cb0e5c9e895223a93bc723af1877ac015`

No integration action remains.

### PR #289

Closed, not merged:
- head `16e0ef194b7d200da7eb5e4208d606a44a4011b3`

It is superseded donor/provenance. Admissible residuals were selectively salvaged via #344 and later work.

Do not merge or reopen it wholesale.

## 8. CURRENT OPERATIONAL PROVIDER STANDING — NOT A RANKING

The freshest source-bound 1.0.16 PB-03 measurement available in the Coordinator audit was:

XMage:
- PASS 44
- FAIL 0
- UNKNOWN 25
- BLOCKED 38

Forge:
- PASS 11
- FAIL 0
- UNKNOWN 56
- BLOCKED 40

These counts are **not** provider-selection criteria.

Current measured AF matrix for both candidates:

- AF00 PASS
- AF01 PASS
- AF02 PASS
- AF03 PASS
- AF04 PASS
- AF05 UNKNOWN
- AF06 UNKNOWN
- AF07 UNKNOWN
- AF08 UNKNOWN
- AF09 UNKNOWN
- AF10 PASS
- AF11 post-selection / UNKNOWN

A final #441 current-boundary reassembly must recompute all of this from the then-current exact source. Do not copy the numbers forward as final truth.

## 9. CURRENT OPEN TECHNICAL DAG

Parent:
- #255 — final pre-Freeze provider adjudication

Evidence parent:
- #441 — final pre-Freeze evidence closure

Leaf/residual issues:
- #453 — AF07 actual-card campaign
- #454 — AF09 clean-process semantic replay twins
- #456 — XMage AF06/AF08 residual closure
- #457 — XMage AF05 remainder
- #458 — Forge AF05 campaign
- #459 — Forge AF06/AF08 residual closure

#455 / PR #464 Forge ScenarioBootstrap is already merged/COMPLETE.

## 10. CURRENT #457 / PR #473 HANDOFF

This is the first technical task to consume because it is already near terminal and has active exact-head evidence.

Issue:
#457

PR:
#473

Branch:
`hardening/af05-xmage-remainder-20261002`

Exact head at durable handoff:
`00a49c2067b851443d8746f64d6035e91d6e0640`

Tree:
`fc8432765da4babf18413638322d64accbbae2da`

Proposed contract:
`1.0.17-successor`

The branch contains the intended implementation for:
- HIDDEN_06
- HIDDEN_11
- HIDDEN_12

It also contains:
- versioned successor contract/schema;
- adversarial qualification logic;
- Java HIDDEN_11 temporal regression;
- current contract binding;
- regenerated qualification hash manifests.

Important history:
A real one-writer collision occurred earlier on #473 and is documented on #457. The branch was frozen, reviewed, reconciled normally with main, repaired, and requalified.

**No evidence from the colliding interval may be promoted.**

Only exact-head evidence from `00a49c2...` or a later freshly requalified head is admissible.

Exact-head workflow status at the final handoff refresh:

SUCCESS:
- Production Qualification `37001349200`
- Meta Qualification `37001349127`
- External XMage Integration `37001349093`
- Windows Runtime Hygiene `37001349030`
- XMage Real 4P Technical Smoke `37001349036`
- Core Workflow Acceptance `37001349001`
- CI `37001349022`
- XMage Full Game Conformance `37001348992`

Still in progress at the final persistence refresh:
- PB-03 `37001349038`
- H4 Docker Materialization `37001349095`

No submitted reviews or review threads were present.

**First action in the entire takeover: fresh-fetch PR #473 and these exact-head runs.**

If they are all terminal green:
1. inspect PB-03 artifact/receipts;
2. require current positive receipts for HIDDEN_06, HIDDEN_11 and HIDDEN_12;
3. confirm no historical receipt transfer across changed 1.0.17 bytes;
4. verify wrong-reason/privacy mutants;
5. fresh-fetch main and classify drift;
6. if non-impacting, merge PR #473 normally with expected-head protection;
7. verify post-merge main;
8. close #457 only if all mandatory XMage HIDDEN rows are current PASS.

Do not touch code merely because you took over. Write only if a concrete exact-head failure/evidence defect remains.

## 11. GLOBAL EXECUTION DISCIPLINE

For every phase below:

### Before write
- fetch current main SHA/tree;
- fetch target issue/PR/branch;
- enumerate open PRs and active writers;
- inspect latest handoff/comments;
- establish one-writer ownership for every touched surface;
- classify drift.

Allowed drift classifications:
- NO_RELEVANT_OVERLAP
- RELEVANT_NONCONFLICTING
- REQUALIFICATION_REQUIRED
- OWNERSHIP_COLLISION
- AUTHORITY_GATE

If ownership collision exists:
- stop writes on that surface;
- adjudicate the combined head read-only;
- resume only after single-writer ownership is re-established.

### Git discipline
- no direct main writes;
- no force push;
- no history rewrite;
- no branch destruction;
- normal merge/reconciliation only;
- expected-head protection when merging;
- preserve donor/history branches;
- no wholesale donor merges.

### Evidence discipline
Every PASS requires exact current evidence appropriate to the obligation.

No:
- import-only PASS;
- construction-only PASS;
- readback-only PASS;
- native-supporting-only FULL107 PASS;
- historical PASS without impact adjudication;
- self-reported provider PASS where independent evidence is required.

### Process isolation
Batch qualification should use fresh process isolation wherever the project contract requires it. Do not share mutable engine/session state across fixtures merely for convenience.

### Persistence
After every material validated milestone:
- persist branch state;
- update the owning issue/PR with source lock, result and exact next action;
- make the work resumable;
- close issues only when their terminal completion contract is truly satisfied.

## 12. SEQUENTIAL CAMPAIGN ORDER

Run the following phases **sequentially**. Do not start a second writer on shared qualification surfaces.

The order may change only if fresh source/ownership evidence proves a dependency change.

---

# PHASE 1 — FINISH #457 / PR #473 XMAGE AF05

Follow section 10.

Completion:
- HIDDEN_06/HIDDEN_11/HIDDEN_12 each direct current PASS, or terminally UNKNOWN/BLOCKED with exact dependency;
- if all 20 mandatory XMage HIDDEN rows are current PASS, AF05 XMage = PASS;
- merge normally only after exact-head evidence;
- terminal #457 handoff.

If exact-head runs are already green, prefer evidence inspection and merge over unnecessary code edits.

---

# PHASE 2 — CURRENT FOUNDRY EXECUTION AUTHORITY — ALREADY ADJUDICATED

Newest direct owner authority supersedes the earlier Muse-migration plan.

Current OpenCode authority:
- DeepSeek v4.1 Flash MAX default/primary;
- Space Bunny MAX explicit secondary;
- no other OpenCode execution profile currently authorized;
- no automatic fallback.

Issue #480 is superseded/not-planned. Do **not** create or revive a Muse/model-migration
workstream from historical references. Expanding or replacing the active pair requires a new
direct owner instruction.

Canonical current authority is maintained in:
- `AGENTS.md`;
- `docs/CURRENT_EXECUTION_AUTHORITY.md`;
- `docs/foundry-execution/ROUTING_AND_EFFORT.md`;
- `.foundry/executor-profiles.json`;
- `opencode.json`.

No engineering action is required in this takeover merely to revisit executor selection.

---

# PHASE 3 — FOUNDRY LEAST-PRIVILEGE HARDENING

Workstream:
`FOUNDRY-LEAST-PRIVILEGE-HARDENING-20261002`

Fresh audit findings:
- root `bash "*"` was allow;
- root `external_directory "*"` was allow;
- later direct-command denies exist;
- sibling-worktree deny injection exists;
- project canary showed interpreter-mediated writes can bypass edit-tool policy;
- single-worktree Bubblewrap enforcement was not mandatory.

Objective:
improve least privilege without breaking legitimate owned-worktree autonomous execution.

Required:
- verify actual permission precedence on the pinned CLI;
- runtime canaries, not documentation assumptions;
- interpreter-mediated foreign/sibling write negatives;
- outside-workspace read/write negatives;
- secret-path negatives;
- owned-worktree positive controls;
- normal feature-branch Git publication positive;
- force/default-branch/destructive-operation negatives.

Do not merge a blanket deny that breaks required operation.

If a hard platform limitation prevents a sound repair:
- persist the exact residual risk and blocker;
- keep it separate from Rules qualification;
- continue to the Rules-critical path because this P2 governance hardening is orthogonal unless the defect actually invalidates evidence integrity.

---

# PHASE 4 — #453 FINAL AF07 ACTUAL-CARD CLOSURE

Issue:
#453

Objective:
terminally execute/classify the frozen 29-card corpus for both XMage and Forge and make AF07 derive from current same-epoch evidence.

At the Coordinator snapshot:
- merged XMage campaign work had reached 17/29 DIRECT_PASS;
- canonical AF07 remained UNKNOWN;
- Forge canonical AF07 had 29/29 identities unexecuted;
- Forge ScenarioBootstrap is now merged and must be reused.

Do not create a second Forge scenario lane.

First:
- fresh-rederive the exact 29-card corpus;
- rederive current residual identities;
- inspect current contract after Phase 1;
- inspect any newer work since this handoff.

For each identity:
- execute the actual named card;
- engine must cause the behavior;
- construction/import is not enough;
- version fixture corrections;
- repair systemic mechanisms, not card-name production hacks;
- bind Oracle/current official Rules for card-specific adjudication;
- any actual candidate-vs-candidate Rules disagreement becomes `UNKNOWN_PENDING_RULES_ADJUDICATION`.

AF07 credit:
- use same-epoch runner-bound receipts;
- do not change the 107 FULL107 denominator merely to make card rows count;
- CARD_02 remains required where the denominator/gate requires it.

Completion:
each current corpus identity direct PASS or exact terminal non-PASS, with no reachable unperformed Lab execution hidden behind it.

---

# PHASE 5 — #454 / PR #461 AF09 CLEAN-PROCESS REPLAY PHASE 2

Issue:
#454

PR:
#461

Branch:
`hardening/af09-replay-twins-20261001`

Historical exact head:
`914c0e413617b23512c5d603551a8fffbbdcdd6b`

Historical Phase-1 evidence:
- Forge 2P–5P clean-process twins succeeded;
- XMage 3P–5P succeeded;
- XMage 2P failed closed at `CHOSEN_OPTION_AMBIGUOUS` because distinct native Plains collapsed to one harness fingerprint.

Historical Phase 1 does not automatically grant current AF09 credit.

Objective:
- merge current main normally;
- impact-adjudicate drift;
- integrate `clean_process_twin` into the canonical current-boundary evidence chain;
- issue exact positive receipts for the five replay/RNG obligations;
- seal current source-bound evidence.

XMage 2P:
- no first occurrence;
- no arbitrary occurrence normalization;
- no random/default tie-break.

If a stable engine-authored occurrence identity can be exposed without adding legality in the Lab, implement a systemic identity channel with fail-before/pass-after tests.

If not, retain the exact obligation UNKNOWN.

Each valid twin must bind:
- candidate/build;
- Lab producer;
- fixture;
- requested seed;
- provider acknowledgement;
- external decisions;
- ordered semantic events;
- checkpoint hashes;
- distinct process identities;
- terminal outcome.

Two genuinely independent OS processes are mandatory.

Use adversarial divergence controls for decisions, RNG, event order/presence, state and terminal result.

---

# PHASE 6 — #456 XMAGE AF06 / AF08 RESIDUAL CLOSURE

Issue:
#456

Objective:
after AF05/AF07/AF09 are integrated, execute or terminally classify every remaining XMage AF06 general-rules and AF08 multiplayer/Commander residual.

Freshly rederive the remaining blocking rows.

Do not rerun valid expensive evidence without an impact reason.

In scope:
- residual current FULL107 rows mapped to AF06/AF08;
- decision/scenario support necessary to execute them;
- systemic Lab/XMage adapter fixes;
- wrong-reason controls;
- current direct receipts.

Out of scope:
- Forge;
- provider selection;
- AF11;
- Freeze.

Completion:
every reachable residual direct PASS or terminal exact provider/engine/harness blocker, with no hidden unperformed Lab work.

---

# PHASE 7 — #458 FORGE AF05 HIDDEN-INFORMATION CAMPAIGN

Issue:
#458

Objective:
execute all twenty current HIDDEN obligations for Forge using:
- merged Forge ScenarioBootstrap/current-boundary lane;
- the final AF05 verifier/contract after #457.

No second Forge scenario lane.

Requirements:
- principal-scoped observations;
- no cross-principal hidden identity leakage;
- honey/sentinel negatives;
- event/metadata/transcript scope where required;
- engine-authored state transitions;
- no Lab hidden-permission rules engine;
- unsupported dimensions fail closed.

AF05 PASS requires all twenty current obligations.

Otherwise return exact UNKNOWN/BLOCKED rows with the first unsupported boundary.

---

# PHASE 8 — #459 FORGE AF06 / AF08 RESIDUAL CLOSURE

Issue:
#459

Objective:
consume merged ScenarioBootstrap and the current contract to execute or terminally classify every remaining Forge AF06/AF08 residual.

Do not rebuild ScenarioBootstrap.

Known historical boundary:
the merged lane directly credited several additional Forge FULL107 rows, while stack injection, some mid-cast states, non-starting active-player states and multiple decision/dimension families remained unsupported/unobservable.

Re-derive exact current state.

No:
- manual outcome injection;
- fabricated legal actions;
- first/default/random fallback;
- Rules semantics in Lab.

A terminal provider gap is valid evidence.
Converting it into fake PASS is not.

---

# PHASE 9 — #441 FINAL PRE-FREEZE EVIDENCE REASSEMBLY

Issue:
#441

Entry gate:
#453, #454, #456, #457, #458 and #459 must be terminal enough that no reachable generic implementation work remains hidden behind them.

Objective:
produce **one final current source-bound epoch** for both candidates.

Required:
- exact producer commit/tree;
- exact candidate/build identities;
- exact effective 107-row denominator;
- exact successor records/digests;
- direct receipt index;
- midgame/scenario/knowledge/actual-card/replay indexes;
- per-candidate FULL107 results;
- AF00–AF11 matrices;
- AF11 still deferred/post-selection;
- provider readiness packet;
- divergence packet;
- complete SHA manifests.

Recompute gates.
Do not copy verdicts from old documents.

For AF05–AF09 prove derivation from current artifacts/rows, not hard-coded literals.

## Create a machine-readable current authority pointer

Add:

`qualification/CURRENT_PROVIDER_STANDING.json`

This should be a small authority pointer, not another giant evidence clone.

At minimum include:
- schema version;
- current epoch path;
- epoch producer SHA/tree;
- epoch/hash-manifest digest;
- current contract ID/digest;
- exact XMage candidate identity;
- exact Forge Rules-Core identity;
- exact Forge bridge identity;
- AF matrix digest or authoritative paths;
- freshness/adjudication status;
- explicit `PRODUCTION_PROVIDER = NOT_SELECTED` until #255 selects one.

Historical evidence directories remain immutable.

Close #441 only when:
- all leaf workstreams are terminal;
- the final packet is merged;
- every remaining non-PASS is an exact current terminal blocker or explicit Rules-adjudication item;
- #255 needs no broad discovery work.

---

# PHASE 10 — #255 FINAL PROVIDER ADJUDICATION → AF11 → ARCHITECTURE FREEZE

Issue:
#255

Entry gate:
#441 terminal COMPLETE on canonical main.

Rules correctness is the eligibility gate.

A candidate is provider-eligible only when every required pre-selection gate AF00–AF10 is current PASS and every mandatory production capability is proven.

Never decide by:
- pass count;
- engine reputation;
- maintenance convenience;
- performance;
- prior preference.

For every `UNKNOWN_PENDING_RULES_ADJUDICATION`:
- bind exact fixture and observations;
- consult current official Magic Comprehensive Rules;
- consult current Oracle/rulings where card-specific;
- distinguish engine fact from Rules interpretation;
- persist authority/effective date;
- classify each candidate against the official authority.

Do not decide by engine majority.

### Zero eligible candidates

- `PRODUCTION_PROVIDER = NOT_SELECTED`
- no selected-provider AF11
- no Freeze
- identify exact mandatory residuals
- at most one additional bounded remediation issue if one candidate is otherwise eligible except for one specific blocker
- no broad engine research

### Exactly one eligible candidate

Select that exact provider identity based on gate eligibility only.

Then run AF11 on that provider.

### More than one eligible candidate

Use only an already-authorized non-correctness tie-break if one exists in canonical project authority.

If none exists:
surface OWNER_AUTHORITY_GATE with a factual comparison.
Do not invent weights.

## AF11

For the selected provider only, verify:
- actual integration topology;
- process/service boundaries;
- license/topology/interop constraints;
- no second Rules engine;
- provider pin/build provenance;
- current actual topology facts.

AF11 PASS must derive from actual topology, not provider name.

## Architecture Freeze

Claim only if:
- provider selected;
- selected provider AF00–AF11 all PASS;
- 2–5P conformance current;
- hidden information current PASS;
- Rules RNG/replay current PASS;
- actual-card gate current PASS;
- fail-closed decision boundaries current PASS;
- no unresolved Rules divergence/evidence freshness issue;
- frozen architecture obeys Rules-Core authority and principal-scoped observation.

Persist a Frozen ADR with:
- provider exact pin/build;
- Lab integration;
- process topology;
- protocol/decision boundary;
- hidden-information model;
- RNG/replay model;
- failure semantics;
- player counts;
- unsupported paths;
- qualification identity;
- production-repo creation gate.

Do **not** create the Production repository in this campaign unless the owner separately authorizes that post-Freeze action.

---

# PHASE 11 — ENGINE-REPOSITORY SUPPLY-CHAIN HARDENING

This is orthogonal to Rules qualification and should not retroactively contaminate candidate evidence.

Repositories:
- `moeendres-png/forge`
- `moeendres-png/mage`

Fresh audit findings:
- default branches unprotected;
- Forge workflows use mutable GitHub Action tags including checkout/setup-java variants;
- Mage uses mutable checkout/setup-java/labeler tags and a third-party MTG fetch action;
- Mage has `pull_request_target`/write-permission automation;
- no confirmed exploit was observed.

Objective:
reduce mutable-action/provenance risk without changing Rules semantics or qualification candidate identities.

Forge:
- pin mutable workflow actions to immutable SHAs where safe;
- preserve Java matrix/job semantics;
- do not merge qualification PR #11 to master as a side effect.

Mage:
- pin checkout/setup-java/labeler/third-party actions where safe;
- review `pull_request_target` and write permissions under least privilege;
- do not modify card/rules source.

Repository settings:
default branches were unprotected, but settings mutation is not implicitly authorized by this campaign unless the owner's current delegated authority explicitly permits it.

If settings writes are not authorized/available:
- produce the exact recommended branch/ruleset configuration;
- do not claim it was applied.

This security phase is separate from Rules qualification.

---

# 13. ISSUE / PR HYGIENE

Do not treat OPEN as ACTIVE mechanically.

Known current dispositions from the Coordinator audit:
- #190 historical/superseded, already closed
- #191 historical/superseded, already closed
- #192 cleanup completed; accidental evidence file is absent from main
- #193 completed
- #196 historical/superseded, already closed
- #205 completed
- #255 active until final provider/freeze gate
- #441 active until final evidence packet
- #455 completed
- #288 already merged
- #289 donor/provenance only

Close or supersede residual issues only after their consumed scope is demonstrably terminal.

Never rewrite history to remove provenance.

## 14. SECURITY FINDINGS SEVERITY

Keep security/governance separate from Rules qualification.

Current audit classification:
- RESOLVED/SUPERSEDED: current OpenCode routing authority is DeepSeek MAX primary + Space Bunny MAX explicit secondary; historical model references are not migration targets
- P2: Foundry least-privilege/interpreter-mediated write risk
- P2: Forge mutable Actions / unprotected default
- P2: Mage mutable Actions / pull_request_target/write automation / unprotected default

No finding above is a confirmed compromise.

Do not inflate severity.

## 15. NO BROAD ENGINE SURVEY

Do not reopen XMage-vs-Forge market research or survey unrelated engines unless new current evidence proves both candidates fundamentally incapable of satisfying mandatory correctness gates and a Coordinator/owner gate explicitly authorizes reopening architecture discovery.

The present task is closure of known bounded gaps.

## 16. HARD STOP / CONTINUATION RULES

Do not voluntarily stop between phases merely because one milestone completed.

Continue sequentially until:
- the full authorized campaign completes; or
- a genuine terminal Authority, Rules, Permission or Ownership gate prevents the next dependent action.

If one orthogonal phase is blocked but later work is independent:
- persist the blocker;
- continue independent critical-path work;
- do not mislabel the blocked phase PASS.

Do not ask the owner questions whose answer is available from GitHub/current official Rules authority.

When owner authority is genuinely required and not inferable:
- stop only that decision;
- provide the exact factual decision packet.

## 17. REQUIRED PERSISTENCE AFTER EACH PHASE

For each material workstream publish a durable issue/PR checkpoint containing:

Source Lock  
Objective  
Work Completed  
New Findings  
Changes  
Tests / Evidence  
PASS / FAIL / UNKNOWN  
Remaining Blockers  
Outputs  
Dependencies Unblocked  
Exact Next Action

Use current source identities, not stale handoff SHAs.

## 18. FINAL CAMPAIGN HANDOFF

At the end produce:

Source Lock  
Work Completed  
New Findings  
Changes  
Tests / Evidence  
Final FULL107 XMage  
Final FULL107 Forge  
Final AF00–AF11 XMage  
Final AF00–AF11 Forge  
Provider Eligibility  
Provider Selection / No Selection  
AF11 Result  
Architecture Freeze Result  
Security / Governance Result  
Superseded Evidence  
Issues / PRs Closed or Preserved  
Remaining Blockers  
Outputs  
Dependencies Unblocked  
Exact Next Action

Terminal lines must be explicit:

`PRODUCTION_PROVIDER = <XMAGE | FORGE | NOT_SELECTED>`

`AF11 = PASS | FAIL | UNKNOWN | NOT_RUN`

`ARCHITECTURE_FREEZE = CLAIMED | NOT_CLAIMED`

`FINAL_PREFREEZE_CAMPAIGN = COMPLETE | PARTIAL | BLOCKED`

`SAFE_TO_CLOSE_SESSION = YES | NO`

## 19. FIRST ACTION NOW

Do not start with a broad inventory.

1. Fresh-fetch Lab main.
2. Fresh-fetch PR #473 and exact head.
3. Poll the remaining exact-head runs:
   - PB-03 `37001349038`
   - H4 Docker Materialization `37001349095`
   XMage Full Game Conformance `37001348992` was already SUCCESS at the final persistence refresh.
4. If the PR head moved, bind to the new head and do not reuse old runs as exact-head proof.
5. If all required exact-head workflows are green, inspect the PB-03 artifact and HIDDEN_06/HIDDEN_11/HIDDEN_12 receipts before any write.
6. Complete/merge #473 if all gates hold.
7. Then proceed through Phases 2–11 sequentially.

No Production Provider is selected at takeover start.

No Architecture Freeze is claimed at takeover start.

Continue autonomously.

# END OF COPY-PASTE PROMPT FOR CLAUDE
