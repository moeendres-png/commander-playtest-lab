# Commander Simulator Next — OpenCode/Muse Technical Decision Authority

POLICY = ACTIVE
EXECUTION_SYSTEM_INTEGRATION = PENDING_PR172_MERGE
Date: 2026-09-10

This document records the current Coordinator authority model for OpenCode Go + Muse Spark 1.3 Contributor. It is governance/coordination only. It does not claim Architecture Freeze or select a Production Provider.

## Core model

OpenCode/Muse is not restricted to code generation. Within an explicitly bounded workstream contract, Muse is expected to inspect, reason, decide technically, implement when authorized, test, diagnose, repair, validate, and produce evidence without routing routine engineering decisions back to the Coordinator.

### Muse HIGH

Default execution tier for bounded engineering work.

Muse HIGH may autonomously:
- inspect repository/source/runtime state;
- make local technical implementation decisions within the workstream contract;
- implement bounded repairs;
- build/test/debug/fix/retest;
- perform test-impact and evidence collection;
- classify straightforward failures;
- choose the smallest conformant local repair;
- continue until COMPLETE or a genuine blocker/authority gate.

### Muse XHIGH

Escalation tier for difficult nonlocal engineering and technical adjudication.

Muse XHIGH may autonomously:
- perform cross-file/subsystem root-cause analysis;
- adjudicate HARNESS vs ADAPTER vs FIXTURE vs ENGINE vs EVIDENCE vs INFRASTRUCTURE defects;
- audit Decision/PlayerController/selector/continuation boundaries;
- adjudicate evidence provenance against an already-defined project contract;
- compare provider-specific technical behavior;
- derive and order repair DAGs;
- select the highest-leverage technical repair within frozen project policy;
- challenge its own hypotheses and continue investigation without coordinator relay.

Muse XHIGH should return to the Coordinator only when the bounded workstream is COMPLETE or a genuine AUTHORITY_GATE remains.

## Coordinator-only authority

GPT-5.6 Sol High retains final authority for:
- changing project-wide evidence semantics or qualification policy;
- ambiguous official MTG Rules adjudication;
- accepting a new shared Rules/Decision architecture or semantic abstraction;
- resolving cross-workstream authority conflicts;
- Production Provider selection;
- Architecture Freeze;
- material scope expansion beyond an authorized workstream;
- redefining Source Truth or Rules-authority boundaries.

Muse may investigate these questions, construct the evidence package, compare options, and recommend a technical answer. It must not silently ratify a project-policy or Architecture authority change.

## Decision boundary

The routing distinction is not "Muse codes, Sol thinks".

The intended model is:

MUSE HIGH = autonomous bounded engineering execution + local technical decisions

MUSE XHIGH = autonomous difficult engineering + technical audit/adjudication + root-cause/evidence/repair decisions

SOL HIGH = project/Rules/evidence-policy authority + cross-workstream gates + provider selection + Architecture Freeze

## Required workstream behavior

Every substantial OpenCode task still requires:
- Repository / Worktree / Branch
- Source Lock / AUDIT_BASE_SHA
- Objective
- Inputs / Authority
- In Scope / Out of Scope
- Ownership / Dependencies
- Hard Gates
- Forbidden Shortcuts
- Evidence Requirements
- Persistence / resumability
- Stop Conditions
- Required Handoff

Muse should not stop merely to ask a routine technical question that can be resolved from source, tests, artifacts, official repository evidence, or bounded experimentation.

For a technical ambiguity inside scope, Muse should:
1. inspect authoritative source/evidence;
2. form hypotheses;
3. search for contradictory evidence;
4. run the smallest permitted validation when necessary;
5. decide technically when project policy already defines the allowed semantics;
6. persist the decision and continue.

Only unresolved policy/Rules/Architecture authority questions should become AUTHORITY_GATE.

## Rules and evidence invariants

Rules Core remains the sole authority for legality, costs, mana, stack, priority, targets, combat, triggers, replacements/prevention, continuous effects/layers/SBAs, zones, copy/control, Commander/multiplayer rules, and Rules RNG.

No pilot/provider/harness/orchestration layer may create a second hidden Rules engine.

Forbidden shortcuts remain forbidden, including first/random/default choices, hidden engine AI, GUI defaults, silent skips, fabricated legal actions, requested-option filtering that changes the authoritative legal set, expected-outcome selection, manual outcome injection, and script-echo counted as independent behavior.

UNKNOWN is not PASS. PARTIAL is not FULL. NOT_RUN is not PASS. CODE_DERIVED is not RUNTIME_VERIFIED. Green CI alone is not qualification.

## OpenCode agent topology target

The execution-system consolidation should provide three explicit roles where supported by current OpenCode schema/runtime:

- foundry-implementer — Muse HIGH, primary autonomous implementation agent;
- foundry-adjudicator — Muse XHIGH, technical audit/adjudication agent with read/test-first posture and no authority to change project policy, select provider, or claim Architecture Freeze;
- foundry-reviewer — Muse HIGH, fresh-context read-only review; same-model review is not independent Rules evidence.

The adjudicator should be able to inspect repository state, Git history, logs, tests and artifacts, and to run non-destructive targeted validation. Mutation permissions should be narrower than the implementer unless a workstream explicitly authorizes remediation after adjudication.

## Current integration state

POLICY = ACTIVE. EXECUTION_SYSTEM_INTEGRATION = PENDING_PR172_MERGE: the
consolidation line below is not canonical on `main` until PR #172 merges.
Do not claim the execution system is canonical on `main` before merge.

This policy is folded into the existing local execution-system consolidation workstream rather than implemented through a competing governance branch.

Expected consolidation line from the latest handoff:
- branch: project/opencode-execution-system-consolidation-20260910
- reported local HEAD: bcce1043c1f882a2785b7c4c4c81459c0405bfb4

That branch was reported local-only at the time of this record. Before integration, reverify its actual current HEAD, diff, OpenCode schema/runtime compatibility, tests, and ownership.

Do not merge predecessor governance PRs merely because this policy exists. Reconcile/supersede them through the consolidation review.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
