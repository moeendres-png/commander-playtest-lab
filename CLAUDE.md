# Commander Simulator Next — Claude entrypoint

Read and follow the repository-root `AGENTS.md` first: it is the canonical durable agent
policy. This file adds Claude-specific operating notes and is not an independent policy
source; if they seem to disagree, `AGENTS.md` governs. Also read the active workstream
contract or checkpoint. When the Owner delegation applies, follow `AGENTS.md` §8 and
`docs/CURRENT_EXECUTION_AUTHORITY.md`.

An explicitly authorized Claude Opus 5.5 engineering session applies the campaign and
Coordinator authority of `AGENTS.md` §8: challenge assumptions, use fresh repository
evidence, finish owned milestones end to end and continue to the next unowned task without
routine user round-trips, within the Owner-only reservations, ownership, Git safety and
protected branches.

## Efficient operation

**Deck focus.** For new owner-deck evaluation/deckbuilding assignments, read `docs/OWNER_DECK_FOCUS_CURRENT.md`: Chulane only. RogShai remains historical/regression data, not active optimization. Do not read `data/collections/**` in this lane.

**Studio.** For Studio work (deck building, simulating, playing) read
`docs/OWNER_DECISIONS_STUDIO_20261112.md` (the Owner decisions) and
`docs/STUDIO_ROADMAP_20261112.md` (plan with recommendations). Other agents work in parallel:
before touching an issue or pull request, check that no other agent holds it.

**Cold start.** Read `docs/claude/state/HANDOFF.md` (regenerate it when stale), the active
lane contract, then run `python3 .claude/skills/lab-ops/scripts/gh_ops.py brief`.
Git/GitHub, tests and sealed evidence are Source Truth; HANDOFF is only a continuation
index. When the workstream changes materially, checkpoint and start a fresh session from
HANDOFF instead of growing one giant conversation.

**Cheapest sufficient path.**
1. Deterministic scripts first (`lab-ops`, grep, focused tests, packet readers).
2. Hand implementation, debugging, test/fix loops, CI repair and long engineering work to
   the worker the Owner selected for the session; the Opus session stays
   coordinator/planner/adjudicator. Write OpenCode prompts per
   `docs/foundry-execution/EXECUTOR_PROMPTING.md`; run OpenCode jobs one at a time.
3. No automatic fallback between models for failure, quota or convenience.
4. Claude subagents for bounded side work: `log-scanner` (Sonnet, low), `ci-triage`
   (Sonnet, medium), built-in `Explore` for read-only lookups. Claude Sonnet may also be an
   implementation worker; the evidence and review rules apply to it.

**Model tiers** (`AGENTS.md` §7, Owner instruction 2026-11-12). The lead session keeps
understanding, planning, adjudication and merge decisions. Hand implementation, review
passes, log/CI digestion and check-watching to a helper on a smaller model at its declared level
(`ci-triage`, `log-scanner`, a Sonnet worker in its own worktree), with a bounded brief, and
check the result before relying on it. This does not replace the worker the Owner selected
for a session, and it never replaces the independent review a MATERIAL change needs
(`AGENTS.md` §10); Rules, evidence, containment and security changes also get
`evidence-reviewer`.

**Spend the quota where it decides something** (Owner instruction 2026-11-13).
- One helper per PR-sized objective, with a complete brief: objective, files to read (named,
  not "explore"), rules to hold, tests to write first, exact commands, report limit. The
  brief contains the review checklist, so the first review finds little.
- One independent review per head. After fixes the SAME reviewer re-checks only the delta.
  No third round for wording.
- Level by task: status, CI and log digestion on the smallest model at low effort;
  implementation and ordinary review on Sonnet at medium; statistics, concurrency,
  security and anything a wrong number would hide behind at high; the `evidence-reviewer`
  only for Rules, evidence, gate and policy text.
- Nothing may be lost to a usage limit: helpers commit a work-in-progress state after every
  milestone and append findings to a file as they go. Resume a stopped helper instead of
  starting a new one.
- Waiting is a shell loop in the background, never a model poll. No background load (game
  series, builds) while helpers run test suites.
- Reuse what a helper already found: paste its facts into the next brief instead of having
  the next helper rediscover them.

Custom Claude helpers are flat: their tool allowlists contain no `Agent` tool, so they must not
spawn children. Do not create agent teams or recursive coordinator/worker trees for normal work.

**Delegation discipline.** A worker's handoff is the first source after delegation. Do not automatically re-read
the same logs, files, diffs, tests or evidence in Opus; reopen raw material only for an
authority-sensitive decision, contradictory or insufficient evidence, an unusual
security/qualification claim, or a required independent verification. Dispatches carry
the task delta, not chat history: objective, source lock, repository, branch/ownership,
scope, dependencies, hard gates, required evidence, forbidden shortcuts, stop conditions,
expected handoff, next action. Do not micromanage a complete dispatch unless an
authority/ownership gate appears, canonical source changes, the packet was incomplete, or
the run ends without resumable state.

**Merging.** Merge your own merge-ready PRs yourself (`AGENTS.md` §10, "Owner-delegated
self-merge") and report the merge in one line with the PR link. Fork pushes, repins and
changes to signed or sealed qualification records wait for the Owner's explicit go.

**Habits.**
- `gh_ops.py brief` is the one-screen lane status; `oc_dispatch.py post`/`watch` build and
  read `/oc`/`/assure` dispatches.
- Helper reports ≤40 lines; routine user status ≤8 lines.
- Test narrow while iterating; run the full suite once at the integration boundary.
  Commit before running tests: a dirty tree fails with "stale canonical inputs".
- Long Java suites, PB-03 and CI waits run in the background, never as repeated polls.
- GitHub GraphQL is unavailable: use `gh api` REST and the CCR routes.
- `ci-definition-integrity-shadow` is red by design when gate tests or workflows change; it
  is not required (required: `quality`, `security`, `infrastructure`); never weaken it.
  A change to `.github/workflows/production-qualification.yml` needs its digest updated in
  `WS17_SHA256SUMS`.
- CI findings and recommendations: `docs/CI_GATES_IMPROVEMENT_PLAN_20261112.md`. It is a plan;
  a change to a required check or gate definition is an Owner decision.
- `.claude/settings.json` sets `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` only as the default for
  unassigned helpers; agent frontmatter wins. `log-scanner` and `ci-triage` use
  `omitClaudeMd: true` on purpose; `evidence-reviewer` keeps project context. No custom
  cache TTL without benchmark evidence.
