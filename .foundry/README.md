# `.foundry/` — Durable Workstream Execution State

This directory is reserved for **branch-local resumability state**, not canonical project authority.

For substantial active workstreams, create:

```text
.foundry/WORKSTREAM_STATE.md
```

from:

```text
docs/agent-workflows/WORKSTREAM_STATE_TEMPLATE.md
```

The state file should be updated after material validated milestones and before a planned or forced execution-lane switch.

## Dual-lane use

The same state file supports:

- ChatGPT Work / Terra -> OpenCode / Muse;
- OpenCode / Muse -> ChatGPT Work / Terra/Sol;
- Muse -> another implementation provider if needed;
- interrupted-session recovery in the same harness.

Current routing uses Muse Spark 1.3 as the primary substantial bounded implementation/test/repair worker, Terra High as the normal Work-side owner/integrator, and Sol High as targeted authority/high-blast-radius escalation. Luna is not part of the active routing policy.

Use:

- `docs/agent-workflows/DUAL_LANE_EXECUTION_PLAYBOOK.md`
- `docs/agent-workflows/DUAL_LANE_TASK_PACKET_TEMPLATE.md`
- `docs/agent-workflows/CHATGPT_WORK_EXECUTION_HANDBOOK.md`
- `docs/agent-workflows/MUSE_SPARK_1_3_OPENCODE_HANDBOOK.md`
- `docs/agent-workflows/MUSE_DATA_BOUNDARY.md`

as operational guidance.

## Muse project-data rule

Muse may use all project-relevant technical data required for Foundry work, including source/tests/docs/configuration, qualification evidence/logs/artifacts, external engine/provider source and Magic card/deck/collection data.

Keep unrelated personal/private user data and raw credential values outside Muse context. Authenticated project tooling may consume configured credentials without printing their values.

## Authority rule

`.foundry/WORKSTREAM_STATE.md` is a resume pointer only.

If it conflicts with:

1. newer direct user instruction;
2. freshly verified Git/source state;
3. current canonical authority;
4. immutable workstream inputs;

then the state file loses.

Do not grant PASS solely because the state file says a gate passed. Reuse only the exact persisted evidence it references.

## Merge rule

Transient branch state should not be merged blindly into long-lived branches. At workstream closeout/reconciliation, decide explicitly whether the state file is retained as provenance, transformed into a final handoff, or omitted from the merge.
