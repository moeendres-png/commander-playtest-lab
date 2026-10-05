---
name: commander-quality-gate
description: >-
  Runs the Commander Simulator Next pre-merge quality gate over a bounded change.
  Use before pushing, opening or merging a material PR; for CI/check/gate hardening;
  after remediation; or when deciding whether an exact reviewed head is safe to
  integrate. Combines fresh source locking, project-native checks, evidence
  classification, differential/adversarial review, patch validation when needed,
  exact-head CI, base-drift adjudication and protected merge discipline.
allowed-tools: Read Write Edit Grep Glob Bash
---

# Commander Quality Gate

Apply this gate under repository-root `AGENTS.md`, the current execution-authority
document and the active workstream contract. Those sources outrank this skill.

The upstream inspiration is preserved byte-for-byte at
[references/upstream-gate-SKILL.md](references/upstream-gate-SKILL.md). This adaptation
keeps its strongest ideas—mechanical checks first, explicit review coverage,
bounded fix waves, no SKIP-as-PASS and learning from escaped defects—while replacing
generic assumptions with Commander Simulator Next evidence and ownership rules.

## Non-negotiable result semantics

- `UNKNOWN` is not PASS.
- `NOT_RUN` is not PASS.
- `PARTIAL` is not FULL.
- A green workflow is not automatically Qualification PASS.
- Source/build/construction/readback evidence is not runtime behavior evidence.
- Candidate-controlled evidence is not silently promoted to trusted evidence.
- Unsupported production-reachable paths fail closed.
- Merge only the exact reviewed head after applicable gates.
- Relevant source/pin/contract/harness/semantic drift requires impact adjudication.
- Never use this skill to select the Production Provider, claim Architecture Freeze,
  create the Production Repository, or expand the active mutation surface.

## Phase 0 — lock authority and scope

Before evaluating the change:

1. Read `AGENTS.md`, current execution authority and the active issue/campaign contract.
2. Record repository, branch, HEAD, TREE and merge base.
3. Record owned mutation surface and verify no active writer overlaps it.
4. Enumerate changed files from Git, not from memory or PR prose.
5. Classify each changed surface:
   - Rules Core / provider semantics;
   - provider adapter / protocol;
   - pilot / hidden-information boundary;
   - replay / RNG / provenance;
   - qualification / CI / workflow;
   - tests / fixtures;
   - documentation / skills only.
6. Identify exact claims the change is supposed to support and claims it must **not**
   support.

If source identity or ownership cannot be established, stop with `UNKNOWN` and an
exact next action.

## Phase 1 — mechanical floor

Run the project's own checks that are relevant to the changed surface before
interpretive review.

Use repository-native definitions such as
`scripts/verify_required_check_definitions.py`, workflow definitions, package build
commands and active workstream-required commands. Do not invent a smaller shadow suite.

For each check record:

| Check | Exact command/run | Source HEAD | Status | Evidence class | Notes |
| --- | --- | --- | --- | --- | --- |

Rules:

- A skipped or missing required check is reported explicitly.
- A cancelled/superseded run is not evidence for the current head.
- A timeout or runner shortage is infrastructure evidence, not semantic FAIL or PASS.
- If a matrix exists, report every required matrix leg separately.
- If a test denominator changed, adjudicate the denominator; do not compare raw totals
  as though the suite were unchanged.
- Never disable or weaken a failing test merely to obtain green CI.

For workflow/check changes, additionally inspect whether the change can create
vacuous green states: path filters, conditionals, `continue-on-error`, `fail-fast`,
missing artifacts, unexecuted matrix legs, stale baselines, ignored exit codes, or
candidate-controlled verifiers.

## Phase 2 — choose the evidence lenses

Apply all lenses that match the change.

### Differential review

Use `differential-review` for material source, workflow, qualification or test changes.
Require:

- locked base vs exact head;
- changed-code context and Git history where relevant;
- blast-radius/caller analysis proportional to risk;
- test-coverage analysis;
- explicit coverage limits;
- adversarial scenarios for high-risk changes;
- a durable review artifact or PR review.

Documentation-only changes can use a bounded content/authority review instead.

### Post-patch validation

Use `post-patch-validation` when the change claims to repair a defect, vulnerability,
gate blind spot or evidence weakness and a meaningful vulnerable baseline exists.

For Commander work, map its evidence contract as follows:

- `control`: benign harness works on both sides;
- `exploit`: original defect is actually reached on base and closed on patch;
- `variant`: independent root-cause variant;
- `behavior`: unaffected behavior preserved;
- `regression`: targeted non-security regression;
- `security`: adjacent safety property not newly broken;
- `suite`: project-native broader suite.

The upstream runner's `PPV_REACHED` marker is particularly useful against vacuous
negative controls. Its `source/build/runtime` levels supplement, but do not replace,
the project's evidence classes.

### Agentic Actions audit

Use `agentic-actions-auditor` when `.github/workflows/**`, reusable actions, AI
review/engineering actions, prompts, permissions or sandbox/tool settings change.

At minimum adjudicate:

- untrusted event data reaching prompts;
- direct GitHub expression injection;
- runtime `gh`/API fetches of attacker-controlled content;
- `pull_request_target` plus untrusted checkout;
- error/log injection;
- shell/subshell expansion;
- execution of AI output;
- dangerous sandbox/tool permissions;
- wildcard allowlists;
- cross-file reusable/composite action resolution.

### Systematic debugging

Use `systematic-debugging` when any relevant check fails unexpectedly. Classify the
failure only after root-cause investigation. Prefer the project's canonical classes
where applicable: engine, provider adapter, harness, fixture, evidence pipeline,
infrastructure, upstream, or unknown.

Do not stack speculative fixes.

### Verification before completion

Always use `verification-before-completion` before saying the gate, fix, PR or
workstream is complete. The proof must be fresh and correspond to the exact claim.

## Phase 3 — evidence integrity review

For every material PASS claim ask:

1. Did the relevant path actually execute?
2. Can the test pass without exercising the intended behavior?
3. Is the oracle independent enough to judge the candidate?
4. Does a negative control fail for the intended reason?
5. Is the evidence bound to exact source/pin/contract/harness identity?
6. Is the result runtime evidence or only source/build/construction evidence?
7. Did hidden information, Rules authority or RNG/replay ownership leak into a
   non-authoritative layer?
8. Did an old PASS survive a relevant change without impact adjudication?
9. Did any fallback silently convert unsupported behavior into success?

For actual-card coverage, prefer systemic fixes and generic decision families over
card-name exceptions.

## Phase 4 — review coverage

Maintain explicit per-file or per-surface coverage.

A review counts as delivered only if its output is present and the reviewed scope is
known. Missing reviewer output is `NOT_RUN`, not implied approval.

At minimum cover:

- correctness / safety;
- integration / wiring;
- regression / backwards compatibility;
- test and negative-control quality;
- evidence/provenance semantics;
- security when trust boundaries or workflows change.

For a large change, split file-local review from cross-file review. Never shard the
cross-file wiring lens so narrowly that multi-site gaps disappear.

## Phase 5 — bounded repair loop

If review finds an in-scope defect:

1. group findings by root hazard;
2. write the minimal fix plan before editing;
3. fix one hazard at a time;
4. re-run targeted evidence;
5. review the **fix wave itself** as new code.

Use a bounded convergence rule inspired by the upstream gate:

- round 1: fix Critical / High / Medium;
- round 2: fix Critical / High introduced by round 1;
- round 3: fix Critical introduced by round 2;
- then stop and hand off remaining findings.

If a repair round introduces more material findings than it closes, classify the gate
as diverging and stop automated repair. Do not let a quality gate become an uncontrolled
rewrite.

Pre-existing out-of-scope findings must be persisted in a durable issue/checkpoint or
reported as not filed with a reason; never silently discard them.

## Phase 6 — exact-head CI and merge gate

Immediately before integration:

1. re-read PR head/base, HEAD/TREE, changed files, reviews and unresolved threads;
2. verify applicable exact-head checks are terminal;
3. verify required check contexts specifically—not merely workflow-level green;
4. adjudicate base drift since the reviewed source lock;
5. determine whether drift overlaps code, pin, contract, test denominator, workflow,
   harness or semantic dependencies;
6. requalify only what the impact adjudication requires;
7. merge with `expected_head_sha` or equivalent exact-head protection;
8. never bypass repository rules to make the merge happen.

If retargeting a stacked PR changes which required checks are emitted, create a clean
successor integration head/PR that gets the required checks. Do not weaken branch
protection.

After merge, read back:

- merge commit;
- resulting `main` HEAD/TREE;
- post-merge checks where the project contract requires them;
- issue/roadmap state that must be updated.

## Phase 7 — terminal handoff

Persist the required handoff:

- Source Lock
- Work Completed
- New Findings
- Changes
- Tests / Evidence
- PASS / FAIL / UNKNOWN
- Remaining Blockers
- Outputs
- Dependencies Unblocked
- Exact Next Action

Also classify material local state as:

- `PERSISTED`;
- `REPRODUCIBLE_AND_DOCUMENTED`;
- `INTENTIONALLY_DISCARDED`;
- `BLOCKED`.

No `LOCAL_ONLY_UNKNOWN` remains.

## Completion status

Use one of:

- `GATE_PASS` — all required evidence/review/merge conditions for the bounded claim
  are satisfied;
- `GATE_FAIL` — a reproduced material defect blocks integration;
- `GATE_BLOCKED` — required evidence is NOT_RUN/UNKNOWN due to a real external or
  authority blocker;
- `REVIEW_REQUIRED` — the change or repair needs unresolved human/independent
  adjudication.

A gate PASS is scoped to the claims and evidence actually evaluated. It is never a
blanket Rules-correctness or Production-eligibility claim.

## Resources

- [references/upstream-gate-SKILL.md](references/upstream-gate-SKILL.md) — provenance
  and comparison copy of the pinned upstream controller. Its separate upstream
  scripts/reference corpus is intentionally not vendored here, so do not rely on
  internal paths from that copy during execution. The active Commander gate above is
  self-contained and remains subordinate to project authority.
