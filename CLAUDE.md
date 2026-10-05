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
When `CLAUDE_OPUS_COORDINATOR_AUTHORITY = DELEGATED_BY_OWNER` applies, the Opus 5.5 main
session resolves Coordinator-tier authority gates itself under `AGENTS.md` §8, records the
decision with evidence and rationale, and continues without a routine Sol/Owner round-trip.

Historical documents that state this repository had no `CLAUDE.md` remain provenance of
their own earlier source locks; they are not current instruction surfaces.

## Efficient operation (Claude sessions)

**New session:** start with `docs/claude/SESSION_PLAYBOOK.md` (environment, GitHub-from-session
limits, sealing, engine-fork and security-change practice). The SessionStart hook
(`.claude/hooks/session-start.sh`) builds the project venv in cloud sessions.

Tooling only; it changes no policy, gate or evidence rule above.

- **Skill `lab-ops`** (`.claude/skills/lab-ops/`): one-line PR/CI/thread status, failing-job lines, CI waiting, PB-03 packet + AF00–AF11 summary, real-engine row runs. Prefer it to raw MCP check/comment/log dumps; use MCP for writes (replies, resolves, merges, PRs).
- **Skill `piv-validate`**: this repository's real validation commands.
- **Subagents** (`.claude/agents/`): every subagent runs on at least Sonnet at `high` effort; judgement stays on the main model.
  - `log-scanner` (Sonnet, high) digests large logs and evidence JSON.
  - `ci-triage` (Sonnet, high) classifies a red check.
  - `evidence-reviewer` (main model, high) reviews a qualification diff adversarially before a push, especially when no external review is available.
  - `log-scanner` and `ci-triage` are read-only reporters inside an authorized Claude campaign. They are not Foundry executors (`docs/foundry-execution/ROUTING_AND_EFFORT.md`) and hold no write, adjudication or merge authority.
  - Evidence adjudication, Rules/CR reasoning and merge decisions are never delegated to a smaller model.
- **Effort.** Claude Opus 5.5 sessions run at `medium` or `high` effort; no Claude subagent runs below Sonnet at `high`. `.claude/settings.json` sets `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` for subagents without their own model; when starting a built-in one (`Explore`, `general-purpose`), pass `model: "sonnet"` or leave it to inherit the main model, never `haiku`. The native-`max` rule in `docs/foundry-execution/ROUTING_AND_EFFORT.md` applies to the OpenCode profiles only.
- **Hook** (`.claude/settings.json`): `ruff --fix` + `ruff format` run on every edited Python file under `src/`, `tests/`, `scripts/`, `.claude/`. Unfixable findings come back in the same turn.
- **Long runs** (Java suites, PB-03, CI waits): start them in the background and keep working. Test narrow while iterating, then run the full suite once before the push.
