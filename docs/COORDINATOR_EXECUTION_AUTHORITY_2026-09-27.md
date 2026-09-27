# Commander Simulator Next — Coordinator and Execution Authority

Status: CANONICAL — 2026-09-27

This document supersedes current-routing instructions in
`docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md`. The older file remains
historical provenance and is not rewritten.

## Authority tiers

### GPT-5.6 Sol High — Coordinator

Owns project-wide Source Truth adjudication, MTG Rules interpretation, evidence and
qualification policy, cross-workstream integration, architecture decisions, Production
Provider selection and Architecture Freeze.

Sol is not the routine implementation worker when an OpenCode lane can execute the
bounded engineering task safely.

### Space Bunny Free MAX — preferred OpenCode execution lane

Exact model: `opencode-go/space-bunny-free`
Required variant: `max`

Default for new implementation, repository edits, builds, tests, debugging, CI repair,
qualification execution, evidence generation and long autonomous engineering workstreams.

It has full technical decision authority inside an explicit workstream contract. Token
cost is not an optimization objective. Use additional context/reasoning when it improves
correctness, but never replace relevance discipline with indiscriminate bulk reading.

### Muse Spark 1.3 Contributor XHIGH — supported alternate OpenCode lane

Exact model: `opencode-go/muse-spark-1.3-contributor`
Required variant: `xhigh`

Use for continuation of existing Muse work, an operator-selected alternative, independent
second-pass engineering, or bounded cross-model challenge/review. Muse has the same
technical authority inside the contract as Space Bunny; model choice does not alter
project semantics.

### ChatGPT Work / Astra — exceptional lane

Astra/Work is used only after `WORK_NECESSITY = PASS`: required capability identified,
Sol insufficient, both OpenCode lanes insufficient, capability genuinely required, scope
minimized.

## One-writer rule

One material workstream has one owning branch/worktree/mutation surface and one active
writer. Bunny and Muse may work sequentially on that same workstream only through a
persisted checkpoint and explicit writer handoff. They may operate simultaneously only on
independent mutation surfaces or read-only review.

## Technical autonomy

Both OpenCode lanes must inspect authoritative evidence, form hypotheses, search for
contradictions, validate the smallest discriminating case, decide ordinary technical
questions, implement when authorized, test, debug, repair, persist evidence, and continue.

They do not stop for routine implementation choices merely because the problem is hard.

## Authority gates

Return to Sol only for a genuine MTG Rules ambiguity, project-wide evidence/qualification
policy, Source-Truth hierarchy conflict, shared architecture change, material scope
expansion, cross-workstream ownership conflict, Production Provider selection or
Architecture Freeze.

## No silent execution fallback

A requested model/variant must resolve exactly. Auth, quota, catalog or model-resolution
failure does not authorize another model, lower variant or provider. Fail closed with the
exact execution gate.

## Evidence

Cross-model agreement is useful engineering evidence but is not external Rules
validation. Historical PASS transfers only through the normal impact-adjudication rules.
