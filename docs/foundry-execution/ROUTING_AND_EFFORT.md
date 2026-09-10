# Foundry Execution Policy — Routing and Effort (Canonical)

Status: CANONICAL. This file plus root `AGENTS.md` plus `opencode.json` is the single
current execution policy. Older routing instructions in historical handoffs, chats, and
superseded PRs are provenance only.

## Execution paths

1. Normal ChatGPT with GPT-5.6 Sol High — Coordinator and adjudication tier.
2. OpenCode Go with `opencode-go/muse-spark-1.3-contributor` — primary execution tier.
3. ChatGPT Work / Astra — exceptional only, after `WORK_NECESSITY = PASS`.

`muse-spark-1.3-contributor` is one model identity. Never split it into separate
Muse and Spark routings, and never substitute another provider or model without an
explicit user instruction and a matching policy and config update.

## Effort policy

Allowed project efforts: `high`, `xhigh`. Minimum: `high`. Default: `high`.

- `high`: normal implementation, repository edits, builds, tests, ordinary debugging,
  CI remediation, qualification, evidence generation, normal build-test-fix loops,
  long but well-scoped workstreams, repetitive mechanical evidence work.
- `xhigh`: escalation for difficult nonlocal reasoning, unclear
  engine-vs-provider-vs-harness-vs-fixture causality, complex multi-subsystem
  remediation, deep debugging chains, identity/state/lifecycle problems, and
  architecture-adjacent implementation.

Never use `medium`, `low`, `minimal`, `none`, or `off` for active project work.
Do not use XHIGH merely because a task is large. Do not restart valid work solely to
change effort. Preserve Source Lock and durable state across escalation.

Machine enforcement: root `opencode.json` disables the `none`, `off`, `minimal`,
`low`, and `medium` variants, sets the model default reasoning effort to `high`,
pins the `build` agent variant to `high`, and restricts providers to `opencode-go`.
The GitHub lane (`.github/workflows/opencode.yml`) runs at `VARIANT: high` by default;
per-run escalation to `xhigh` remains available with a recorded justification.

## Technical decision authority

Authoritative model:
`docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md`. Summary:

- Muse HIGH: autonomous bounded engineering execution plus ordinary local technical
  decisions inside the workstream contract. Agents: `foundry-implementer`.
- Muse XHIGH: autonomous difficult engineering plus technical adjudication
  (root-cause class, first-failing boundary, evidence provenance, repair DAG)
  within already-defined project policy. Agents: `foundry-adjudicator`
  (read/test-first, narrower mutation permissions than the implementer).
- Sol High: final authority only for project-wide evidence-semantics or
  qualification-policy changes, ambiguous MTG Rules interpretation, new shared
  Rules/Decision architecture, cross-workstream authority conflicts, material scope
  expansion, Source-Truth hierarchy changes, Rules-authority-boundary changes,
  Production Provider selection, and Architecture Freeze.

A technical decision is never an authority decision. Only genuine authority-policy
questions become `AUTHORITY_GATE`. HIGH→XHIGH escalation is not failure.

## Work necessity gate

Work is forbidden for ordinary tasks the normal paths can perform. Before any Work
use, record `WORK_NECESSITY = PASS` or `FAIL`. PASS requires: the exact missing
capability is identified; normal Sol High cannot perform it; OpenCode+Muse cannot
perform it; the capability is genuinely required; the assignment is the smallest
possible operation. Otherwise `WORK_NECESSITY = FAIL` and Work must not be used.

## Parallelism and persistence

Parallelism only across independent surfaces: verify branch ownership, remote head,
active worker, touched files, semantic surface, active runs, and expected output first.
Every workstream persists Git plus `.foundry/WORKSTREAM_STATE.yaml` plus sealed
evidence so any qualified worker resumes after interruption.
