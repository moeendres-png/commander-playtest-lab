# Commander Simulation Foundry — Dual-Lane Task Packet

> Copy/adapt this template for a material engineering unit that may move between ChatGPT Work/Terra/Sol and OpenCode/Muse. Keep it concise. Stable project rules stay in `AGENTS.md`.

## Identity

- Workstream: `[WS-NN / name]`
- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `[branch]`
- Starting head: `[sha | VERIFY_LIVE]`
- Execution profile: `[TERRA_INTEGRATION | SOL_AUTHORITY | MUSE_IMPLEMENTATION | PROVIDER_NEUTRAL]`

## Terminal Objective

[One result.]

## Why / Decision Relevance

[Why this unit exists and what gate/dependency it closes.]

## Authority

- Workstream Contract: `[path + identity]`
- Immutable contract/materialization: `[identity/digest]`
- Rules/Oracle authority if relevant: `[source/date]`
- Engine/source pin if relevant: `[repo@sha]`

## Known Verified Facts

- `[fact + evidence/source]`

Do not repeat background already in `AGENTS.md`.

## In Scope

- `[...]`

## Out of Scope

- `[...]`

## Hard Invariants

- `[must remain true]`
- `[fail-closed boundary]`
- `[semantics that must not move into pilot/harness]`

## Start Here

Read in this order unless fresh evidence invalidates it:

1. `AGENTS.md`
2. `[active Workstream Contract]`
3. `.foundry/WORKSTREAM_STATE.md` if present
4. `[file/test/evidence]`
5. `[file/test/evidence]`

Broaden repository search only to answer a specific unresolved question.

If this runs in Muse, `docs/agent-workflows/MUSE_DATA_BOUNDARY.md` is binding. All project-relevant technical data may be used; unrelated personal/private data and raw credential values stay outside model context.

## Exact Current Reproducer / Blocker

```text
[command / test / observed failure]
```

Classification: `[REMEDIABLE | CONTRACT_DEFECT | PROVIDER_DEFECT | ENGINE_DEFECT | UNKNOWN]`

## Required Work

1. `[...]`
2. `[...]`
3. `[...]`

## Validation Ladder

Run in this order, stopping escalation only when the next broader gate is not required:

1. `[exact reproducer]`
2. `[regression / negative test]`
3. `[neighboring suite]`
4. `[subsystem gate]`
5. `[full required qualification/CI]`

## Acceptance Criteria

- `[executable criterion]`
- `[evidence criterion]`
- no weakened assertions or silent fallback;
- no unrelated semantic changes.

## Persistence

After each material validated milestone:

- update `.foundry/WORKSTREAM_STATE.md` when used;
- persist machine-readable evidence where relevant;
- make a focused local commit;
- record exact resulting head and validation identity.

Do not push/merge unless explicitly authorized.

## Lane-Specific Execution

### If running in Work / Terra High

- verify live source state and mutable authority facts;
- minimize context reads;
- use exact named files/evidence first;
- use the smallest authoritative validation first;
- spend capacity on diagnosis/semantics/high-risk integration/evidence adjudication;
- if remaining work becomes substantial bounded implementation/test iteration, persist state and hand to Muse.

### If running in Sol High

Use only for a bounded genuinely difficult/high-blast-radius question, MTG semantic dispute, foundational architecture, difficult hidden-information/RNG/concurrency reasoning, materially ambiguous provider-vs-engine attribution, or a blocker that survived two materially distinct Terra attempts. Return normal ownership to Terra/Muse afterward.

### If running in OpenCode / Muse

- treat Muse as the primary coding worker once semantics/acceptance criteria are fixed enough;
- continue through remediable implementation/test failures without asking after every ordinary action;
- use all project-relevant source/evidence/logs/engine/card data and normal coding tools needed for the objective;
- keep unrelated personal/private user data and raw credential values outside Muse context;
- authenticated project tooling may consume configured credentials without printing them;
- use broader local exploration when useful but remain within the one terminal objective;
- checkpoint frequently because Free-tier availability is dynamic;
- return to Terra/Sol for unresolved architecture/rules authority or final decision-critical adjudication.

Luna is not part of the active Foundry routing policy.

## Stop Conditions

Only:

- proved terminal blocker;
- required immutable out-of-scope contract change;
- unavailable required authority/tooling;
- unresolved semantic/architecture choice the current lane is not authorized to decide;
- explicit user stop.

## Final Handoff

- Source Lock
- Work Completed
- New Findings
- Changes
- Tests / Evidence
- PASS / FAIL / UNKNOWN
- Remaining Blockers
- Outputs
- Dependencies Unblocked
- Exact Next Action
- Recommended Next Lane: `[TERRA | SOL | MUSE | NONE]`
