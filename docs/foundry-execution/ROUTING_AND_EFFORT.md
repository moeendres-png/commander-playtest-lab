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
   - committed/default and preferred: `deepseek` =
     `opencode-go/deepseek-v4.1-flash` at native `max`;
   - explicit secondary only: `space-bunny` =
     `opencode-go/space-bunny` at native `max`, for bounded, mechanical,
     token-heavy, bulk and background work.
   Logical `space-bunny` resolves only after live pinned-CLI catalog inspection
   (`opencode models opencode-go`): canonical `opencode-go/space-bunny` first, else the
   admitted legacy runtime alias `opencode-go/space-bunny-free` (`LEGACY_ALIAS`, the
   SAME logical profile), else fail closed. No Longcat, DeepSeek or other
   provider/model may substitute, and there is no third logical executor. A runtime,
   auth, quota or catalog failure after selection is a blocked run, never a re-resolution.
   No other OpenCode executor is selectable under current authority.
3. Claude Opus 5.5 — explicitly authorized direct engineering/campaign executor when a
   session declares its campaign objective and writable ownership surface(s). It may own
   long autonomous campaigns and continuous in-objective task selection under the same
   Rules/Evidence/Privacy/Git gates; it is not a Foundry launcher profile. By direct Owner
   delegation, an explicitly launched Opus 5.5 main session also holds the Coordinator tier's
   decision authority under `AGENTS.md` §8; the Owner-only reservations there remain reserved.
4. ChatGPT Work / Astra — exceptional only, after `WORK_NECESSITY = PASS`.

Executor choice is explicit and auditable. The launcher never changes model because of
quota, credentials, catalog availability, child failure, or retry. A DeepSeek failure is
fail-closed; running another executor afterwards is an explicit task-rerouting decision.
A completed/terminated writer releases the existing writer lock, after which the other
profile may resume the same workstream from the same branch + explicit state + evidence.
Concurrent writers on the same worktree, branch, or semantic surface remain forbidden;
parallel profiles require independent worktrees/ownership.

Legacy provider overrides are retired and always refused. Historical executor/model
receipts remain provenance only. They are not migration targets and must not generate a
routing/governance issue by themselves. Changing the two-profile allowlist requires a new
direct user instruction. See `EXECUTION_PROVIDER_OVERRIDE.md`.

## Execution identity policy

Active OpenCode Foundry work has exactly two supported launcher execution identities:

- `deepseek` → `opencode-go/deepseek-v4.1-flash` → native `max`.
  This is the default and preferred executor for implementation, debugging,
  qualification, integration, CI remediation, evidence generation and long campaigns.
- `space-bunny` → `opencode-go/space-bunny` → native `max`.
  This is the explicit secondary for bounded, mechanical, token-heavy, bulk and
  background work, and for deliberately authorized cross-model checks.

The launcher rejects any profile outside this set, and rejects every provider override,
so no mismatched or retired pair is reachable. There is no active-work native lane below
`max`; the project-level `--effort` field describes task/authority routing only and never
lowers either executor's native level.

This native-`max` rule binds the OpenCode profiles only. A Claude Opus 5.5 campaign runs
at `medium` or `high` effort, and its read-only helpers use the effort pinned in their own
frontmatter (`log-scanner` Sonnet `low`, `ci-triage` Sonnet `medium`, `evidence-reviewer`
Opus `high`); never Haiku. Those subagents are read-only helpers inside the campaign, not
Foundry executors, and hold no write, adjudication or merge authority.

Root `opencode.json` is DeepSeek MAX by default and exposes Space Bunny MAX as the only
other whitelisted model. The GitHub OpenCode lane is also DeepSeek MAX by default (`/oc`,
`/opencode`); an explicit `/bunny` comment from a trusted author starts the separate Space Bunny MAX
job with the `bunny-verifier` agent. That is an explicit selection of the secondary profile, never a
fallback: a failed DeepSeek run is not retried on Space Bunny.

Profile postures (both at native `max`):
- DeepSeek MAX spends reasoning freely but economises input: capsule first, the shared `lab-ops`
  scripts for status and logs, bounded reads, narrow validation while iterating and the full
  required suites once before a push.
- Space Bunny MAX spends tokens on assurance: every reported claim is established by two
  independent routes with a wrong-reason control, the complete affected validation runs, and a
  fresh-context `bunny-auditor` reviews the diff. It saves wall-clock time by running long checks
  first and independent checks in parallel subagents. No executor
fallback occurs on quota, auth, catalog or child failure.

## Cross-executor review gate (MATERIAL workstreams)

DeepSeek MAX remains the default implementation executor. For every MATERIAL
implementation workstream, a fresh-context READ-ONLY Space Bunny MAX reviewer must review
the exact validated implementation SHA **and** TREE before the workstream may claim
`PR_READY` or `COMPLETE`.

- Canonical structure and validator: `tools/foundry/review_gate.py`; canonical review
  records live under `.foundry/reviews/`.
- The reviewer must resolve to an admitted Space Bunny runtime id (canonical or the
  legacy alias) and run read-only: `foundry-reviewer` (Space Bunny MAX, `edit: deny`,
  bash default-deny, `task: deny`) or the read-only `bunny-auditor`. A DeepSeek review,
  a writable verifier, a self-review, or an unknown/blocked/partial/fail/stale verdict
  never satisfies the gate.
- A PASS record is only admissible with independently verifiable GitHub evidence
  (`tools/foundry/review_evidence.py`): a trusted trigger comment, the successful
  trusted Space Bunny workflow run and expected job, the workflow file fetched at the
  run's exact `head_sha` pinning Space Bunny MAX and the expected agent, the
  structurally read-only reviewer agent file, and the OpenCode bot result comment
  carrying the machine-parseable receipt marker and exact reviewed SHA/TREE/verdict.
  Self-declared Space Bunny fields in a record the implementation executor wrote are
  never sufficient; network/API/parse failures fail closed.
- The current carriers are the trusted `/bunny` bootstrap lane with a read-only
  `bunny-auditor` subreview receipt (`BUNNY_AUDITOR_SUBAGENT_REVIEW`) and the direct
  bypass lane `/bunny-review` with `foundry-reviewer`
  (`BUNNY_DIRECT_READ_ONLY_REVIEW`). Issue-comment lanes are evaluated from the
  default branch, so a new lane is only reachable after it is merged to main.
- Any MATERIAL change after the review (including an evidenced P1/P2 repair) makes the
  prior review STALE and requires exact new-SHA/TREE re-review. A generated-state-only
  receipt/checkpoint commit is NON_MATERIAL and preserves the reviewed validated
  implementation identity without claiming the later state commit was reviewed.
- Materiality is fail-safe: implementation, executable tooling, schemas/contracts, CI,
  tests that alter acceptance semantics, evidence/qualification semantics and every
  ordinary `docs/**` change are MATERIAL. The only documentation exemption is a narrow,
  explicitly named closeout report under `docs/` (basename contains `closeout`, and no
  policy/authority/mission/qualification/evidence/routing/security keyword). A
  NON_MATERIAL claim is verified against the Git change set, and an empty/self-rebound
  change set cannot grant an exemption.
- Remote milestone persistence reuses the Foundry state file, `tools/foundry/safe_push.py`
  and `tools/foundry/remote_checkpoint.py`: state update -> focused commit -> safe push
  -> remote HEAD equality verification. A pushed WIP is never qualification PASS, and a
  remote HEAD mismatch blocks remote resumability.

## Technical decision authority

Authoritative model:
`docs/CURRENT_EXECUTION_AUTHORITY.md`. Summary:

- DeepSeek MAX: preferred new-work execution profile. Autonomous implementation,
  debugging, qualification, evidence generation, tool use and technical decisions
  within the bounded workstream contract. Native reasoning remains `max`.
- Space Bunny MAX: explicit secondary execution profile for bounded, mechanical,
  token-heavy and background work, and for deliberately authorized cross-model
  technical adjudication within already-defined policy.
- Claude Opus 5.5: direct campaign executor when explicitly authorized. It may challenge
  technical assumptions, take adjacent high-value work inside the same objective and
  continue selecting unowned milestones without routine user round-trips. A bounded
  integration campaign may span multiple disjoint explicitly owned surfaces; all other
  surfaces remain read-only. By direct Owner delegation, an explicitly launched Opus 5.5
  main session also holds the Coordinator tier's Rules, evidence-policy, qualification,
  gate, shared-architecture, cross-workstream and ownership-arbitration authority defined
  in `AGENTS.md` §8.
- Sol High: Coordinator and adjudication tier for project-wide evidence semantics,
  qualification policy, ambiguous MTG Rules interpretation, shared Rules/Decision
  architecture, cross-workstream authority conflicts, material scope expansion,
  Source-Truth hierarchy changes and Rules-authority-boundary changes. Under the Owner
  delegation, an explicitly launched Claude Opus 5.5 main session holds the same delegated
  Coordinator-tier authority. Production Provider selection, Architecture Freeze,
  Production Repository creation, setting or rotating secrets, paid services and changing
  the delegation remain Owner-only under `AGENTS.md` §8.

Both OpenCode profiles and an explicitly authorized Claude Opus 5.5 campaign use the
same Rules/Evidence/Privacy/Semantic-Completion policy. None is a lower-authority coding
assistant inside its declared surface: each must use available tools, investigate root
causes, repair in-objective defects, test, validate, persist evidence and continue
autonomously until COMPLETE or a genuine authority/permission/source gate.

A technical decision is never an authority decision. Only genuine authority-policy
questions become `AUTHORITY_GATE`. An explicitly launched Claude Opus 5.5 main session
holding the Owner delegation resolves Coordinator-tier `AUTHORITY_GATE` questions itself
under `AGENTS.md` §8; Owner-only reservations remain gates. Executor changes are explicit
handoffs, not silent escalation.

## Work necessity gate

Work is forbidden for ordinary tasks the normal paths can perform. Before any Work
use, record `WORK_NECESSITY = PASS` or `FAIL`. PASS requires: the exact missing
capability is identified; normal Sol High cannot perform it; neither supported OpenCode Foundry executor nor
an available authorized Claude campaign can perform it; the capability is genuinely required; the assignment
is the smallest possible operation. Otherwise `WORK_NECESSITY = FAIL` and Work must not be used.

## Parallelism and persistence

Parallelism only across independent surfaces: verify branch ownership, remote head,
active worker, touched files, semantic surface, active runs, and expected output first.
Every workstream persists Git plus its explicit dedicated state file (the exact
`--state` path; there is no implicit active repository-root state) plus sealed
evidence so any qualified worker resumes after interruption.
