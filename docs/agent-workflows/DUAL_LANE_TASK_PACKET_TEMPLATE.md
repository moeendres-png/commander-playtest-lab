# Commander Simulation Foundry — Dual-Lane Task Packet

> Copy/adapt this template for a material engineering unit that may move between ChatGPT Work/Codex and OpenCode/Muse. Keep it concise. Stable project rules stay in `AGENTS.md`.

## Identity

- Workstream: `[WS-NN / name]`
- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `[branch]`
- Starting head: `[sha | VERIFY_LIVE]`
- Execution profile: `[WORK_HIGH_CAPABILITY | MUSE_IMPLEMENTATION | PROVIDER_NEUTRAL]`

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
- `[fact + evidence/source]`

Do not repeat background that is already in `AGENTS.md`.

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
4. `[file/test]`
5. `[file/test]`

Broaden repository search only to answer a specific unresolved question.

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

### If running in Work/Codex

- minimize context reads;
- use exact named files first;
- use smallest authoritative validation first;
- spend capacity on diagnosis/semantics/high-risk edits;
- if remaining work becomes bounded mechanical implementation, persist state and hand to Muse.

### If running in OpenCode/Muse

- continue through remediable implementation/test failures without asking after every ordinary action;
- use broader local exploration when useful but remain within the one terminal objective;
- do not impose an artificial small step cap;
- checkpoint frequently because Free-tier availability is dynamic;
- return to Work for unresolved architecture/rules authority or final decision-critical adjudication.

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
- Recommended Next Lane: `[WORK | MUSE | NONE]`
