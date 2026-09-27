# OpenCode Execution Model Routing

Status: CANONICAL CURRENT ROUTING AUTHORITY

This file defines the exact execution-model lanes for Commander Simulator Next. Root
`AGENTS.md` defines project behavior and authority. Root `opencode.json` enforces the
allowed OpenCode provider/models. The Foundry launcher records the selected lane.

## Roles

| Lane | Exact identity | Required effort | Role |
| --- | --- | --- | --- |
| Coordinator | GPT-5.6 Sol High | High | Source Truth, MTG Rules adjudication, provider/freeze authority |
| Preferred OpenCode | `opencode-go/space-bunny-free` | `max` | New implementation, debugging, tests, qualification, long autonomous execution |
| Alternate OpenCode | `opencode-go/muse-spark-1.3-contributor` | `xhigh` | Muse continuation, second-pass engineering, independent comparison/remediation |
| Exceptional Work | Astra via ChatGPT Work | bounded | Only after `WORK_NECESSITY = PASS` |

## Hard invariants

Space Bunny never runs below `max`. Muse never runs below `xhigh` for active project
engineering. There is no automatic fallback between them and no fallback to another
provider. Model availability, auth or quota failure is reported and stops that launch.

Neither OpenCode model may select the Production Rules Provider or claim Architecture
Freeze. Both inherit the same Rules-authority, privacy, evidence, source-lock and
semantic-completion rules from `AGENTS.md`.

## Preferred lane

New OpenCode work defaults to Space Bunny MAX. Its large context/token budget may be
used aggressively for relevant source, tests, contradictory evidence and validation.
Do not optimize for token cost. Do not bulk-read unrelated history or rerun valid
evidence merely because tokens are free.

## Muse lane

Existing Muse-owned workstreams may finish under Muse XHIGH without migration. Muse XHIGH
also remains available when the operator wants an independent second implementation or
review path. Historical Muse HIGH/XHIGH evidence remains valid provenance subject to the
normal impact-adjudication rules.

## Same-workstream handoff

Bunny and Muse may be used sequentially on the same workstream only when:

1. the current writer reaches a coherent checkpoint;
2. state/handoff records exact HEAD, tree, tests and next action;
3. the first writer releases ownership;
4. the second model verifies branch/HEAD/tree/state before mutation;
5. no valid evidence is rerun without an impact reason.

The model change alone does not authorize scope expansion.

## Parallel use

Both models may run simultaneously only when they own independent branches/worktrees and
non-overlapping mutation surfaces, or when one/both sessions are explicitly read-only.
Never run two writers on the same branch or worktree.

## Cross-model review

A useful pattern is writer → read-only alternate-model reviewer → same writer repairs.
Cross-model agreement is not external Rules validation. Disagreement is resolved from
source/runtime evidence or escalated to Sol only if it reaches a genuine authority gate.

## Foundry launcher selection

Preferred Bunny lane:

```text
--execution-model bunny --effort max
```

Muse lane:

```text
--execution-model muse --effort xhigh
```

The launcher exports the exact resolved identity as `FOUNDRY_EXECUTION_MODEL` and
`FOUNDRY_EXECUTION_LANE`. Persist it at checkpoints; do not infer model identity from
conversation history.

## Prompt header

Every substantial OpenCode assignment should state:

```
EXECUTION_MODEL: SPACE_BUNNY_MAX
MODEL: opencode-go/space-bunny-free
VARIANT: max
```

or

```
EXECUTION_MODEL: MUSE_XHIGH
MODEL: opencode-go/muse-spark-1.3-contributor
VARIANT: xhigh
```

and include: no silent fallback; token-cost optimization disabled; autonomous completion;
contradictory-evidence search; checkpoint persistence; one writer per mutation surface.

## Merge gate for this migration

Before merging the routing migration, locally verify that the installed qualified
OpenCode CLI resolves both exact model IDs and that Space Bunny exposes `max`. If the
catalog differs, update only the execution-model identity/config on this migration branch
and re-run its tooling tests; do not silently substitute another model.
