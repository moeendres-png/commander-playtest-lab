# Commander Simulation Foundry — Workstream State

> Copy this file to `.foundry/WORKSTREAM_STATE.md` on a substantial workstream branch.
> This file is a resumability checkpoint, **not Source Authority**. Fresh Git/current-source evidence wins on conflict.

## Identity

- Workstream: `[WS-NN / name]`
- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `[branch]`
- State updated at commit: `[sha or UNCOMMITTED_CHECKPOINT]`
- State updated UTC: `[timestamp]`
- Status: `[IN_PROGRESS | COMPLETE | FAIL | TERMINAL_BLOCKED]`

## Terminal Objective

[One primary objective copied/summarized from the active Workstream Contract.]

## Active Authority / Immutable Inputs

- Workstream Contract: `[path + commit/digest]`
- Canonical materialization/protocol: `[identity + digest]`
- Engine/source pin(s): `[repo@commit]`
- Rules/Oracle authority lock when material: `[identity/date]`

## Current Verified Source Lock

- Commander Lab head: `[sha]`
- Relevant engine/fork head: `[sha]`
- Relevant tree/build identity: `[value]`
- Last fresh verification: `[timestamp / evidence path]`

## Completed Milestones

1. `[milestone]`
   - commit: `[sha]`
   - validation: `[command/result]`
   - evidence: `[path/run/artifact]`
2. `[...]`

## Active Work

- Current sub-objective: `[one concrete action]`
- Files currently relevant:
  - `[path]`
  - `[path]`
- Current hypothesis/diagnosis: `[short, evidence-grounded statement]`

## Last Authoritative Validation

```text
[command]
[result]
```

- Result classification: `[PASS | FAIL | UNKNOWN | NOT_RUN]`
- Evidence path/run ID: `[value]`

## Current Failure / Blocker

- Classification: `[NONE | REMEDIABLE | CONTRACT_DEFECT | PROVIDER_DEFECT | ENGINE_DEFECT | AUTHORITY_BLOCKED | TOOLING_BLOCKED | TERMINAL_BLOCKER]`
- Exact failing command/path: `[value]`
- Short failure evidence: `[value]`
- Why it is/is not terminal: `[value]`

## Uncommitted State

- `git status` summary: `[clean / files]`
- Safe to resume directly: `[YES/NO]`
- If NO, exact recovery action: `[value]`

## Exact Next Action

[Single next technical action. Do not write a vague roadmap here.]

## Do Not Redo Unless Invalidated

- `[validated work]`
- `[validated work]`

## Handoff Notes for Another Harness / Model

- Facts that must be freshly reverified: `[list]`
- Important implementation constraints not obvious from code: `[list]`
- No conversation transcript is required beyond this state + contract + Git evidence.
