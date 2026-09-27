# Foundry Execution Policy — Model Routing and Effort (Canonical)

Status: CANONICAL. Root `AGENTS.md`, root `opencode.json`, this file, and
`EXECUTION_MODEL_ROUTING.md` define the current execution layer. Historical handoffs,
research reports and superseded PRs retain their original model identities as provenance.

## Routing

1. GPT-5.6 Sol High — Coordinator, Source Truth, MTG Rules adjudication, cross-workstream
   integration, Production Provider selection and Architecture Freeze.
2. Space Bunny Free MAX — preferred OpenCode execution lane for new engineering work.
3. Muse Spark 1.3 Contributor XHIGH — supported alternate OpenCode execution lane for
   continuation, independent comparison, second-pass review/remediation, or explicit
   operator selection.
4. ChatGPT Work / Astra — exceptional only after `WORK_NECESSITY = PASS`.

Exact model IDs and invocation rules live in
`docs/foundry-execution/EXECUTION_MODEL_ROUTING.md`.

Exact OpenCode model IDs:
- preferred: `opencode-go/space-bunny-free`
- alternate: `opencode-go/muse-spark-1.3-contributor`

## Effort policy

- Space Bunny: `max` only.
- Muse Spark: `xhigh` only.
- No silent downgrade, provider substitution, model fallback or agent fallback.
- Missing credentials, quota or unavailable model/variant is a fail-closed execution gate.
- Token cost is not an optimization objective; relevance, Rules Correctness and evidence
  rigor still bound what should be read or rerun.

## Sequential and parallel use

One workstream owns one branch/worktree/mutation surface at a time. A Bunny↔Muse handoff
on the same workstream requires a persisted checkpoint, verified HEAD/tree/state, and
exclusive writer transfer. Two writers never operate on the same worktree or branch.

Parallel model use is allowed only on independent mutation surfaces or read-only review.
Cross-model agreement is engineering evidence, never independent MTG Rules authority.

## Technical decision authority

Both OpenCode lanes operate under `AUTONOMOUS_WITHIN_CONTRACT`. They decide ordinary
technical questions from source/tests/runtime evidence and continue. Only genuine Rules,
evidence-policy, architecture, scope, provider-selection or Freeze questions return to
Sol High.

## Work necessity gate

ChatGPT Work/Astra is forbidden for ordinary tasks the normal Sol/OpenCode lanes can
perform. Before Work use, record `WORK_NECESSITY = PASS` with the missing capability,
why Sol is insufficient, why both OpenCode lanes are insufficient, and the smallest
required Work scope.

## Persistence

Every workstream persists Git + its explicit state file + sealed evidence. Model changes
do not invalidate evidence by themselves; relevant code/pin/contract/harness/semantic
changes still require impact adjudication.
