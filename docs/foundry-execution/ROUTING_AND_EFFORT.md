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
   - committed/default and preferred: `space-bunny` =
     `opencode-go/space-bunny-free` at native `max`;
   - explicit alternate only: `muse` =
     `opencode-go/muse-spark-1.3-contributor` at native `xhigh`.
   Muse HIGH is not an active project lane.
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

## Execution identity policy

Active project work has exactly two supported execution identities:

- `space-bunny` → `opencode-go/space-bunny-free` → native `max`.
  This is the default and preferred executor for implementation, debugging,
  qualification, integration, CI remediation, evidence generation and long campaigns.
- `muse` → `opencode-go/muse-spark-1.3-contributor` → native `xhigh`.
  This is an explicit alternate for deliberate cross-model work, difficult technical
  adjudication, or continuation where Muse is specifically desired.

The launcher fails closed on mismatched pairs. In particular, Space Bunny with `xhigh`
or Muse with `high`/`max` is invalid. There is no active-work HIGH lane.

Root `opencode.json` is Space Bunny MAX by default and exposes Muse only at XHIGH.
The GitHub OpenCode lane is also Space Bunny MAX. No executor fallback occurs on quota,
auth, catalog or child failure.

## Technical decision authority

Authoritative model:
`docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md`. Summary:

- Space Bunny MAX: preferred new-work execution profile. Autonomous implementation,
  debugging, qualification, evidence generation, tool use and technical decisions
  within the bounded workstream contract. Native reasoning remains `max`.
- Muse XHIGH: explicit alternate/continuation execution profile. XHIGH owns difficult nonlocal technical adjudication
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
questions become `AUTHORITY_GATE`. Executor changes are explicit handoffs, not silent escalation.

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
