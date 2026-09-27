# WSR24 — Architecture Freeze and Production Bootstrap Readiness

## Status

READY_FOR_EXECUTION

- Primary executor: `opencode-go/muse-spark-1.3-contributor`
- Project effort: `xhigh`
- Primary issue: #267
- Primary branch: `wsr24/freeze-production-bootstrap-readiness-20260927`
- Audit base SHA: `b786fbf2956c9bacca20cb75864e8dcd1974274a`
- Audit base tree: `e97dd131b965d6097ca77f60630d428a218b583a`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`

## Objective

Prepare the provider-neutral Architecture Freeze decision packet and the immediate
post-Freeze production-bootstrap package so that, after Coordinator adjudication of the
current WSR22 provider evidence, Commander Simulator Next can move directly into the
smallest required remediation (if any), Architecture Freeze, and production implementation
without another broad planning or architecture-research cycle.

This workstream does **not** select a provider and does **not** claim Freeze.

## Project End State

Commander Simulator Next targets complete, reproducible Full-Rules Commander games using
real 100-card decks. The selected Rules Core must remain the sole authority for legal
actions, costs, mana, stack, priority, targets, combat, triggers, replacement/prevention,
continuous effects/layers, state-based actions, zones, copy/control, Commander/multiplayer
rules, and Rules randomness.

The surrounding production system may expose principal-scoped observations and
authoritative Decision Options and submit externally chosen discretionary decisions. It
must not contain a second hidden Rules Engine, fabricated legality, silent fallback, or
manual outcome injection.

Primary decision mode is 4P (one controlled deck + three opponents). Technical conformance
requires 2P–5P; bounded 6P is desirable where already supported.

## Source Truth

Current canonical Lab source:

- main/audit base: `b786fbf2956c9bacca20cb75864e8dcd1974274a`
- tree: `e97dd131b965d6097ca77f60630d428a218b583a`
- current qualification boundary: `commander-lab.pre-freeze-qualification/2.0.0`
- protocol: `2.0.0`

Current provider evidence is WSR22 PR #269, read-only:

- branch: `wsr22/final-current-boundary-freeze-qualification-20260927`
- published head at dispatch: `208341c6124674046787f3a4b1d699c98c286a27`
- PR #269 MUST NOT be merged or modified by WSR24.

Before any material work, fresh-fetch and reverify these identities. If current main or
PR #269 moved, perform impact adjudication rather than blindly inheriting this file.

## Authorities

### Coordinator-only

GPT-5.6 Sol High retains exclusive authority for:

- provider selection;
- Architecture Freeze;
- ambiguous MTG Rules adjudication;
- project-wide evidence/qualification-policy changes;
- shared architecture changes;
- material scope expansion.

### WSR24 technical authority

Muse XHIGH is autonomous within this contract for:

- repository/source inspection;
- evidence ingestion and consistency checking;
- mapping current evidence to freeze-gate/schema requirements;
- provider-neutral ADR/template design;
- post-Freeze repository/bootstrap design;
- validation/test implementation for WSR24-owned artifacts;
- root-cause analysis of WSR24-owned tooling/docs/tests;
- build/test/debug/fix loops.

Do not ask for routine decisions that are resolved by current source, schemas, tests, or
WSR22 evidence.

## Inputs

Canonical current inputs include:

- `qualification/CURRENT_PRE_FREEZE_CONTRACT.json`
- `qualification/pre-freeze-successor/architecture_freeze_gate_catalog_v2.json`
- `qualification/pre-freeze-successor/architecture_freeze_contract_v2.schema.json`
- `qualification/pre-freeze-successor/AF01_QUALIFICATION_BOUNDARY_V2.json`
- Protocol 2.0 schema/config
- current Rules-authority receipt
- WSR22 PR #269 current-boundary evidence, especially:
  - `FINAL_HANDOFF.md`
  - `PROVIDER_BLOCKERS.json`
  - `AF00_AF11_XMAGE.json`
  - `AF00_AF11_FORGE.json`
  - `SOURCE_LOCK.json`
  - current-boundary comparison/divergence artifacts.

At dispatch WSR22 reports no Rules-visible divergence, but neither candidate has all
AF00–AF11 PASS. That fact must be mapped honestly, not normalized away.

## In Scope

1. Verify current Freeze gate/schema semantics.
2. Ingest the exact WSR22 provider evidence as read-only input.
3. Produce candidate-specific **freeze-readiness mappings** without ranking candidates.
4. Map every AF00–AF11 non-PASS verdict to:
   - exact evidence;
   - exact missing proof/capability;
   - whether a Coordinator decision alone can close it;
   - or the smallest bounded remediation required.
5. Preserve WSR22 blocker identities such as PB-03/PB-06/PB-07/PB-08 where still current.
6. Prepare the provider-neutral Architecture Freeze ADR template binding:
   - RULES_CORE;
   - PRODUCTION_PROVIDER;
   - ENGINE_PIN / build identity;
   - adapter/bridge architecture;
   - supported player counts;
   - hidden-information model;
   - legal-action contract;
   - decision contract;
   - Rules RNG contract;
   - replay contract;
   - failure semantics;
   - process isolation;
   - interop/license topology;
   - Source Lock;
   - supported/unsupported paths.
7. Prepare exact post-Freeze private production-repository bootstrap instructions and
   validation gates without creating that repository.
8. Define the first post-Freeze production vertical slice:
   - real provider process;
   - real 4P Commander game;
   - real 100-card deck import;
   - authoritative engine legal options;
   - external discretionary decisions only;
   - principal-scoped observations;
   - deterministic Rules RNG binding;
   - semantic replay;
   - terminal-game evidence;
   - fail-closed unsupported paths.
9. Add tests/validators ensuring:
   - all 12 AF gates appear exactly once;
   - `freeze_eligible=true` cannot be generated while any gate is non-PASS;
   - missing required capabilities prevent eligibility;
   - provider choice cannot be silently defaulted;
   - templates contain every required architecture binding;
   - no historical PASS is promoted automatically.
10. Produce the smallest candidate-specific remediation DAGs required after Coordinator
    provider adjudication, without selecting which DAG to execute.
11. Persist a terminal handoff sufficient for the Coordinator to select the next exact
    action immediately.

## Out of Scope

- provider selection or ranking;
- Architecture Freeze claim;
- creating the private production repo;
- editing `config/rules_engines.json` to select a provider;
- XMage or Forge production Rules changes;
- rerunning FULL107;
- repeating WSR22 qualification;
- generic engine research;
- performance/pilot/deckbuilding optimization;
- changing the Freeze gate catalog/schema;
- treating UNKNOWN/PARTIAL/NOT_RUN/FAIL as PASS.

## Dependencies

Read-only active dependency:

- WSR22 / PR #269.

WSR23 may run independently on project hygiene/integration. Do not write its branch or
mutation surface.

## Hard Gates

1. All Freeze-readiness claims use the current gate catalog/schema.
2. `freeze_eligible=true` requires schema-conformant all-PASS evidence; never fabricate it.
3. No provider winner/score/tier/ranking.
4. No second Rules Engine in any proposed production architecture.
5. No silent provider/model/action fallback.
6. No production repo before Coordinator Freeze.
7. No Rules or qualification re-execution merely for reassurance.
8. WSR22 historical/runtime evidence remains accurately classified.
9. Any true Rules ambiguity becomes a Coordinator gate rather than a Muse verdict.
10. Unsupported production paths remain explicit/fail-closed.

## Required Deliverables

Persist under:

`docs/architecture_freeze_readiness_20260927/`

Required:

- `SOURCE_LOCK.json`
- `WSR22_EVIDENCE_INGEST.json`
- `XMAGE_FREEZE_READINESS.json`
- `FORGE_FREEZE_READINESS.json`
- `FREEZE_GATE_BINDING_MAP.json`
- `COORDINATOR_DECISION_SLOTS.md`
- `ARCHITECTURE_FREEZE_ADR_TEMPLATE.md`
- `SELECTED_PROVIDER_IMPACT_TEMPLATE.md`
- `POST_FREEZE_BOOTSTRAP_PLAN.md`
- `PRODUCTION_REPOSITORY_CONTRACT.md`
- `FIRST_PRODUCTION_VERTICAL_SLICE_CONTRACT.md`
- `REMEDIATION_DAG_XMAGE.md`
- `REMEDIATION_DAG_FORGE.md`
- `VALIDATION.md`
- `SELF_REVIEW.md`
- `FINAL_HANDOFF.md`

Add a compact machine-readable validator/test surface under WSR24 ownership where useful.

## Evidence Requirements

- exact file/commit/blob references for current contract/schema;
- exact WSR22 PR/head/artifact identities;
- no copied verdict without provenance;
- no candidate comparison score;
- tests must exercise invalid/non-PASS template cases, not only happy path;
- actual runtime qualification is not part of WSR24 and must not be claimed.

## Persistence

After each material validated milestone, commit locally and persist:

- current HEAD/tree;
- inputs used;
- tests run;
- decisions made;
- rejected hypotheses;
- exact next action.

Do not rely on chat context.

## Publication

When terminal and validated, safely publish only the WSR24 branch and open exactly one PR
to current main. Do not merge it.

Raw force push, branch deletion, repository settings, tags, provider repin and production
repo creation remain unauthorized.

## Stop Conditions

Complete only when the Coordinator can take WSR24 + WSR22 and immediately do one of:

1. authorize exactly one bounded selected-provider remediation; or
2. if all current required gates are later proven PASS, execute the formal Architecture
   Freeze adjudication and then the prepared production bootstrap.

Terminal exact next action:

`COORDINATOR_FREEZE_OR_SINGLE_REMEDIATION_ADJUDICATION_READY`

Maintain throughout:

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
