# Commander Simulator Next — Claude entrypoint

Before doing project work, read and follow the repository-root `AGENTS.md`.

`AGENTS.md` is the canonical durable agent policy. This file is only the Claude-specific
entrypoint and is **not an independent policy source**. If this file and `AGENTS.md`
appear to disagree, `AGENTS.md` governs.

Also read the current execution-authority document referenced by `AGENTS.md` and the
active workstream/campaign contract or durable checkpoint for the session.

For an explicitly authorized **Claude Opus 5.5** engineering campaign, apply the
autonomous campaign authority defined in `AGENTS.md`: challenge technical assumptions,
use fresh repository evidence, complete owned milestones end to end, and continue to the
next high-value unowned task inside the same campaign objective without routine user
round-trips.

Fresh repository state outranks historical handoffs. Project-wide read access does not
imply project-wide write authority. Respect active ownership, Rules/evidence/privacy
boundaries, Git safety, protected branches and the Owner-only reservations in `AGENTS.md` §8.
When the Owner delegation applies, follow `AGENTS.md` §8 'Claude Opus 5.5 Coordinator authority' and `docs/CURRENT_EXECUTION_AUTHORITY.md`.

Historical documents that state this repository had no `CLAUDE.md` remain provenance of
their own earlier source locks; they are not current instruction surfaces.

## Efficient operation (Claude sessions)

**Cold start.** Read `docs/claude/state/HANDOFF.md`, regenerate it when stale, read the active
lane contract, then run `python3 .claude/skills/lab-ops/scripts/gh_ops.py brief`. Git/GitHub,
tests and sealed evidence remain Source Truth; HANDOFF is only a compact continuation index.
When the lane or workstream changes materially, checkpoint and start a fresh session from
HANDOFF instead of preserving one giant coordinator conversation.

**Quota-aware routing.** Use the cheapest path that preserves the required authority and evidence:

1. Prefer deterministic scripts (`lab-ops`, grep, focused test runners, packet readers) when they
   can answer the question without model judgement.
2. Route implementation, debugging, test/fix loops, CI remediation, qualification execution,
   evidence production, multi-file edits and long autonomous engineering work to Step 5 Preview on OpenCode Zen
   (`opencode/step-5-preview-free`, native `high`; GitHub lanes `/oc` implementer, `/assure` verifier,
   `/ro-review` read-only reviewer) or to a Claude Sonnet 5.5 worker in the session.
   Step 5 Preview is the only active OpenCode model; DeepSeek V4.1 Flash on OpenCode Go (`opencode-go/deepseek-v4.1-flash`) is SUSPENDED. Never select any other OpenCode model.
   From a Claude session start it with `opencode run -m opencode/step-5-preview-free --variant high`: the Zen free tier refuses
   the `opencode-subagent` MCP bridge. A Zen rate limit or refusal is BLOCKED_SERVICE; run OpenCode jobs one at a time.
   Write every OpenCode prompt per `docs/foundry-execution/EXECUTOR_PROMPTING.md`.
3. Keep the Opus 5.5 main session as coordinator/planner/adjudicator. Project default effort is `medium`;
   raise to `high` for complex Rules/CR reasoning, qualification, architecture arbitration, or gate decisions.
4. There is no automatic fallback between models for failure, quota or convenience; reactivating DeepSeek needs a new direct Owner instruction.
5. Use Claude subagents for bounded side work that would pollute the main context:
   `log-scanner` = Sonnet `low`; `ci-triage` = Sonnet `medium`; built-in `Explore` for scoped read-only lookups.
   Claude Sonnet 5.5 may also be an implementation worker (Owner decision); the evidence-producing and review rules still apply to it.

Custom Claude helpers are flat: their tool allowlists contain no `Agent` tool, so they must not
spawn children. Do not create agent teams or recursive coordinator/worker trees for normal work.

**Delegation discipline.** A worker handoff is the first source to consume after delegation.
Do not automatically re-read the same logs, files, diffs, tests, comments or evidence JSON in
Opus. Re-open raw material only for an authority-sensitive decision, contradictory or
insufficient evidence, an unusual security/qualification claim, or a contractually required
independent verification.

OpenCode dispatches carry the task delta, not chat history: objective, source lock, repository,
branch/worktree and ownership, scope, dependencies, hard gates, required evidence, forbidden
shortcuts, stop conditions, expected handoff and exact next action. After a complete dispatch,
do not micromanage the worker unless an authority/ownership gate appears, canonical source state
changes, the packet was objectively incomplete, or the run terminates without resumable state.

- `gh_ops.py brief` is the one-screen lane status; prefer it to raw API/check/comment dumps.
- `oc_dispatch.py post` builds `/oc` or `/assure` comments from the compact task skeletons;
  `oc_dispatch.py watch` consumes the compact result.
- Every helper report is ≤40 lines; routine user status messages are ≤8 lines.
- Test narrow while iterating; run the full required suite once at the integration boundary.
- Long Java suites, PB-03 and CI waits belong in background execution, not repeated foreground polls.
- `.claude/settings.json` keeps `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` only as the default for
  otherwise-unassigned helpers; explicit agent `model`/`effort` frontmatter wins.
- `log-scanner` and `ci-triage` intentionally use `omitClaudeMd: true` because their complete
  narrow contracts live in their own prompts. `evidence-reviewer` keeps project context.
  Do not add a custom cache TTL without benchmark evidence; the short helpers use Claude Code's
  normal cache policy.

The native-variant requirement above applies to the OpenCode profiles only. It does not imply
Claude `max` effort.
