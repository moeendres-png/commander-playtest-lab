# Foundry Execution Policy — Routing and Effort (Canonical)

Status: CANONICAL. This file plus root `AGENTS.md` plus `opencode.json` is the single
current execution policy. Older routing instructions in historical handoffs, chats, and
superseded PRs are provenance only.

OpenCode V2 instruction-loading note: root `AGENTS.md` is the durable model-visible
project instruction source. V2 currently accepts an `instructions` array in the config
schema but does not resolve those files into model instructions, so `opencode.json` must
not be relied on to inject this document. Stable rules that must reach every worker belong
in `AGENTS.md`; this document remains the canonical detailed routing reference.

## Execution paths

1. Normal ChatGPT with GPT-5.6 Sol High — Coordinator and adjudication tier.
2. OpenCode Foundry — primary execution tier with one explicit executor per run:
   - preferred for new substantial work: `space-bunny` =
     `opencode-go/space-bunny-free`, pinned to native `max` reasoning by the
     run-specific injected config;
   - committed/default and fully supported alternate: `muse` =
     `opencode-go/muse-spark-1.3-contributor`, retained for reproducibility,
     continuation and deliberate cross-model review.
3. ChatGPT Work / Astra — exceptional only, after `WORK_NECESSITY = PASS`.

Executor choice is explicit and auditable. The launcher never changes model because of
quota, credentials, child failure, or retry. A completed/terminated writer releases the
existing writer lock, after which the other profile may resume the same workstream from
the same branch + explicit state + evidence. Concurrent writers on the same worktree,
branch, or semantic surface remain forbidden; parallel profiles require independent
worktrees/ownership.

The existing `--execution-provider zen` remains a compatibility override for
`opencode/muse-spark-1.3-contributor-free`. It is separate from
`--execution-profile space-bunny`; conflicting selections fail closed. See
`EXECUTION_PROVIDER_OVERRIDE.md` for exact resolution.

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

Machine enforcement: root `opencode.json` remains Muse-default, disables the
`none`, `off`, `minimal`, `low`, and `medium` variants, sets Muse default reasoning
to `high`, and restricts providers to `opencode-go`. The launcher may construct a
run-specific, single-model `space-bunny` bundle that pins
`opencode-go/space-bunny-free` to native `max`; it does not widen the committed
canonical allowlist or create fallback behavior. The GitHub lane
(`.github/workflows/opencode.yml`) remains Muse HIGH by default unless separately
changed and qualified.

## Technical decision authority

Authoritative model:
`docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md`. Summary:

- Space Bunny MAX: preferred new-work execution profile. Autonomous implementation,
  debugging, qualification, evidence generation, tool use and technical decisions
  within the bounded workstream contract. Native reasoning remains `max`.
- Muse HIGH/XHIGH: fully supported alternate/continuation execution profile. HIGH owns
  ordinary bounded engineering; XHIGH owns difficult nonlocal technical adjudication
  within already-defined policy.
- Sol High: final authority only for project-wide evidence-semantics or
  qualification-policy changes, ambiguous MTG Rules interpretation, new shared
  Rules/Decision architecture, cross-workstream authority conflicts, material scope
  expansion, Source-Truth hierarchy changes, Rules-authority-boundary changes,
  Production Provider selection, and Architecture Freeze.

Both OpenCode profiles use the same Rules/Evidence/Privacy/Semantic-Completion policy.
Neither profile is a lower-authority coding assistant: each must use available tools,
investigate root causes, repair in-scope defects, test, validate, persist evidence and
continue autonomously until COMPLETE or a genuine authority/permission/source gate.

A technical decision is never an authority decision. Only genuine authority-policy
questions become `AUTHORITY_GATE`. HIGH→XHIGH escalation is not failure.

## Work necessity gate

Work is forbidden for ordinary tasks the normal paths can perform. Before any Work
use, record `WORK_NECESSITY = PASS` or `FAIL`. PASS requires: the exact missing
capability is identified; normal Sol High cannot perform it; neither supported OpenCode Foundry executor can
perform it; the capability is genuinely required; the assignment is the smallest
possible operation. Otherwise `WORK_NECESSITY = FAIL` and Work must not be used.

## Parallelism and persistence

Parallelism only across independent surfaces: verify branch ownership, remote head,
active worker, touched files, semantic surface, active runs, and expected output first.
Every workstream persists Git plus its explicit dedicated state file (the exact
`--state` path; there is no implicit active repository-root state) plus sealed
evidence so any qualified worker resumes after interruption.
