# Commander Simulator Next — Claude entrypoint

Read and follow the repository-root `AGENTS.md` first: it is the canonical durable agent
policy. This file adds Claude-specific operating notes and is not an independent policy
source; if they seem to disagree, `AGENTS.md` governs. Lead, Coordinator and campaign
authority, the Owner-only reservations and the merge gate are in `AGENTS.md` §8 and §10.

## Efficient operation

**Focus.** Owner-deck work: Chulane only (`docs/OWNER_DECK_FOCUS_CURRENT.md`); RogShai is
historical/regression data. Studio work (deck building, simulating, playing): read the binding
scope `docs/STUDIO_SCOPE.md` and the Owner decisions `docs/OWNER_DECISIONS_STUDIO_20261118.md`
and `docs/OWNER_DECISIONS_STUDIO_20261112.md`, then `docs/STUDIO_PLAN_SIMULATOR.md` (bridge-gate
reference set); the roadmap stays as planning history, and where it differs the scope wins.
Who holds which Studio surface is in the claim table of #1167. Before touching an issue or pull
request, check that no other agent holds it (`AGENTS.md` §11, parallel agents).
Abarbeitung: `docs/STUDIO_SCOPE.md` §Abarbeitung. Shared files and the entry page for other
agents: `docs/STUDIO_AGENT_ONBOARDING.md`.

**Cold start.** Run `python3 .claude/skills/lab-ops/scripts/gh_ops.py brief`, then read the
issue or pull request you own. Git/GitHub, tests and sealed evidence are Source Truth. When the
workstream changes materially, record the handoff in its issue or PR and start a fresh session
instead of growing one giant conversation.

**Cheapest sufficient path.**
1. Deterministic scripts first (`lab-ops`, grep, focused tests, packet readers).
2. Hand implementation, debugging, test/fix loops, CI repair and long engineering work to
   the worker the Owner selected for the session; the lead session stays
   coordinator/planner/adjudicator.
3. No automatic fallback between models for failure, quota or convenience.
4. Claude subagents for bounded side work: `log-scanner` (Sonnet, low), `ci-triage`
   (Sonnet, medium), built-in `Explore` for read-only lookups. Claude Sonnet may also be an
   implementation worker; the evidence and review rules apply to it.

**Model tiers and quota** (`AGENTS.md` §7). Helpers and reviewers inherit the lead's model and
effort unless the Owner says otherwise; the lead may lower them only for status, CI and log
digestion (`log-scanner`, `ci-triage`). The defaults in `.claude/settings.json` and the fixed
levels in `.claude/agents/*.md` are Owner-set exceptions to this inheritance; the lead may not
raise or lower them silently. `evidence-reviewer` reviews Rules, evidence,
containment, security, gate and policy text. A brief
contains the review checklist, so the first review finds little. No third review round for
wording. No background load (game series, builds) while helpers run test suites. Paste what a
helper already found into the next brief instead of having the next helper rediscover it.

Custom Claude helpers are flat: their tool allowlists contain no `Agent` tool, so they must not
spawn children. Do not create agent teams or recursive coordinator/worker trees for normal work.

**Delegation discipline.** A worker's handoff is the first source after delegation.
Do not automatically re-read the same logs, files, diffs, tests or evidence in the lead
session; reopen raw material only for an authority-sensitive decision, contradictory or insufficient
evidence, an unusual security/qualification claim, or a required independent verification.
Dispatches carry the task delta, not chat history. Do not micromanage a complete dispatch
unless an authority/ownership gate appears, canonical source changes, the packet was
incomplete, or the run ends without resumable state.

**Habits.**
- `gh_ops.py brief` is the one-screen status; `status`, `queue`, `threads`, `wait`, `run`,
  `errors` and `rerun-cancelled` cover single PRs, CI and logs.
- Helper reports ≤40 lines; routine user status ≤8 lines.
- Test narrow while iterating; run the full suite once at the integration boundary (local
  testing: `AGENTS.md` §10).
- Long Java suites, PB-03 and CI waits run in the background, never as repeated polls.
- GitHub GraphQL is unavailable: use `gh api` REST and the CCR routes.
- GitHub 429: one attempt, then stop and record it in the issue.
- A skipped real-engine test is `NOT_RUN`; report it as such.
- `WS17_SHA256SUMS`: regenerating its digest line (`python scripts/regenerate_hash_manifests.py`)
  is allowed only within a change to `.github/workflows/production-qualification.yml`; any
  other change to it needs the Owner's go (`AGENTS.md` §8).
- Open CI points: `docs/CI_GATES_IMPROVEMENT_PLAN_20261112.md` (a plan, not a gate).
- `.claude/settings.json` sets `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` only as the default for
  unassigned helpers; agent frontmatter wins. `log-scanner` and `ci-triage` use
  `omitClaudeMd: true` on purpose; `evidence-reviewer` keeps project context. No custom
  cache TTL without benchmark evidence.
