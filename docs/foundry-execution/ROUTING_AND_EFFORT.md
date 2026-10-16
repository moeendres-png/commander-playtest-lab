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
2. OpenCode Foundry — primary execution tier with one executor per run. Since the Owner
   instruction of 2026-10-16 that executor is always `deepseek` =
   `opencode/deepseek-v4.1-flash-free` (DeepSeek V4.1 Flash on OpenCode Zen) at its highest
   native variant `max` (every lane, agent and subagent; free Zen tier; no other OpenCode
   model is used). Step 5 Preview left the Zen catalog and was retired on 2026-10-16.
   Logical `deepseek` resolves only after live pinned-CLI catalog inspection
   (`opencode models opencode`): the Zen id `opencode/deepseek-v4.1-flash-free` must be
   listed, else fail closed. No retired executor or other provider/model may substitute, and
   there is no second logical executor. A runtime, auth, quota or catalog failure after
   selection is a blocked run, never a re-resolution.
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
fail-closed and never falls back to another model.
A completed/terminated writer releases the existing writer lock, after which a fresh run may
resume the same workstream from the same branch + explicit state + evidence.
Concurrent writers on the same worktree, branch, or semantic surface remain forbidden;
parallel profiles require independent worktrees/ownership.

Legacy provider overrides are retired and always refused. Historical executor/model
receipts remain provenance only. They are not migration targets and must not generate a
routing/governance issue by themselves. Changing the allowlist requires a new direct user instruction. See `EXECUTION_PROVIDER_OVERRIDE.md`.

## Execution identity policy

Active OpenCode Foundry work has exactly one supported launcher execution identity:

- `deepseek` → `opencode/deepseek-v4.1-flash-free` → native `max` (models.dev lists
  low/high/max; `max` is the pin and nothing below `high` is ever configured).
  The default and only executor for implementation, debugging, qualification,
  integration, CI remediation, evidence generation, audits, reviews and long campaigns.

A second ACTIVE profile exists for the Token Harbor lane (`/oc-th`, Owner instruction 2026-10-16):

- `deepseek-th` -> `tokenharbor/deepseek-v4.1-flash` -> provider default. Same model, served by
  Token Harbor (OpenAI-compatible, key only via `{env:TOKENHARBOR_API_KEY}`). The provider
  exposes no reasoning-effort control, so `max`/`high` cannot be pinned and no variant is faked.
  Free routes may be logged and used for improvement: no Owner data, credentials or private
  collection data in an `/oc-th` task.

`/oc` (default; Zen, zero-retention, daily Zen request cap) and `/oc-th` (higher rate limit, 60
req/min) are chosen per dispatch; each run pins exactly one profile and there is no automatic
fallback between them. `/assure` and `/ro-review` stay on Zen `deepseek`. Because both profiles
are the same model, `deepseek-th` adds provider independence only: a `deepseek-th`
implementation reviewed by Zen `deepseek` is cross-provider review, and self-review is refused
only when an ACTIVE profile of a different model family exists.

The launcher rejects any profile outside the ACTIVE set, and rejects every provider override,
so no mismatched or retired pair is reachable. There is no active-work native lane below
the executor's highest native level; the project-level `--effort` field describes task/authority routing only and never
lowers the executor's native level.

This highest-native-level rule binds the OpenCode profiles only. A Claude Opus 5.5 campaign runs
at `medium` or `high` effort, and its read-only helpers use the effort pinned in their own
frontmatter (`log-scanner` Sonnet `low`, `ci-triage` Sonnet `medium`, `evidence-reviewer`
Opus `high`); never Haiku. Those subagents are read-only helpers inside the campaign, not
Foundry executors, and hold no write, adjudication or merge authority.

Root `opencode.json` enables only the Zen provider `opencode` and whitelists only
`deepseek-v4.1-flash-free` at native `max` for `model` and `small_model`. All three GitHub OpenCode lanes pin `MODEL=opencode/deepseek-v4.1-flash-free`
and `VARIANT=max`; they differ by agent: `/oc` and `/opencode` run `foundry-implementer`, `/assure`
runs `assurance-verifier`, `/ro-review` runs the read-only `foundry-reviewer`. Claude sessions start DeepSeek through the
`opencode` CLI (the external `opencode-subagent` MCP plugin defaults to a retired Go id, so every call must pass the model explicitly).
How to write prompts for this model: `EXECUTOR_PROMPTING.md`.

Lane postures (all DeepSeek V4.1 Flash at native `max`):
- `/oc` (`foundry-implementer`) spends reasoning freely but economises input: capsule first, the
  shared `lab-ops` scripts for status and logs, bounded reads, narrow validation while iterating
  and the full required suites once before a push.
- `/assure` (`assurance-verifier`) spends tokens on assurance: every reported claim is established by two
  independent routes with a wrong-reason control, the complete affected validation runs, and a
  fresh-context `assurance-auditor` reviews the diff. It saves wall-clock time by running long checks
  first and independent checks in parallel subagents. No executor
fallback occurs on quota, auth, catalog or child failure.

## Cross-executor review gate (MATERIAL workstreams, Foundry tooling)

This is a Foundry tooling gate, not a change to Rules, evidence semantics or
qualification credit: `tools/foundry/review_gate.py` refuses to certify a
`PR_READY`/`COMPLETE` claim for a MATERIAL workstream unless the record carries a PASS
from the trusted read-only review lane on the exact validated implementation SHA
**and** TREE. It never relabels a review as Rules validation, qualification credit,
production-provider evidence or Architecture Freeze.

- Canonical structure and validator: `tools/foundry/review_gate.py`; canonical review
  records live under `.foundry/reviews/`.
- The only admissible reviewer is the top-level `foundry-reviewer` agent of the
  `/ro-review` lane: DeepSeek V4.1 Flash MAX, structurally read-only (`mode: all`,
  `edit: deny`, bash default-deny, `task: deny`). While DeepSeek is the only ACTIVE profile it may
  review DeepSeek implementation work (same-model review; the Owner approval of
  2026-10-10 for the single-executor case, restated 2026-10-16); its independence then rests on the fresh context and the read-only lane.
  As soon as a second profile is ACTIVE that counts as self-review and is refused. A writable
  top-level verifier (`assurance-verifier`), a subagent attestation (`assurance-auditor`),
  a self-review, or an unknown/blocked/partial/fail/stale verdict never satisfies the
  gate.
- A PASS record is only admissible with independently verifiable GitHub evidence
  (`tools/foundry/review_evidence.py`): a trusted trigger comment, the successful
  trusted `/ro-review` workflow run and expected job, the workflow file fetched at
  the run's exact `head_sha` pinning canonical DeepSeek V4.1 Flash MAX and the
  `foundry-reviewer` agent, the structurally read-only reviewer agent file, and the
  OpenCode bot result comment carrying the machine-parseable
  `DIRECT_READ_ONLY_REVIEW` receipt with the exact reviewed SHA/TREE/verdict.
  The receipt is bound to its run: the result comment must fall inside the run's
  `run_started_at..updated_at` window, the trigger comment must be the newest issue
  comment created before the run started, and the comment's own run footer link must
  be the last run link in the body. Self-declared record fields can never fabricate a
  review; network/API/parse failures fail closed.
- `REVIEWER_MODEL`, `REVIEWER_VARIANT` and `READ_ONLY` in the receipt are
  self-reported by the reviewing agent text. They are checked for exact equality with
  the record and the pinned run, but they are not themselves independent observation.
  The independently observed facts are the run/job identity and conclusions, the
  workflow and agent files fetched at the run's `head_sha`, and the comment/run
  binding. The workflow pin verified at `head_sha` must be canonical
  `opencode/deepseek-v4.1-flash-free`, so a review recorded on another id (including the retired
  Step and OpenCode Go ids) cannot satisfy the evidence gate.
- Issue-comment lanes are evaluated from the default branch, so the `/ro-review`
  lane is only reachable after it is merged to main.
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

- DeepSeek V4.1 Flash MAX: the only active OpenCode execution profile. Autonomous implementation,
  debugging, qualification, evidence generation, tool use and technical decisions within
  the bounded workstream contract. Native reasoning remains `max`.
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

The OpenCode profile and an explicitly authorized Claude Opus 5.5 campaign use the
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
