# Commander Studio — Claude Code entrypoint

@AGENTS.md

`AGENTS.md` above is the binding policy for every agent. This file holds only what is specific to
Claude Code; if the two seem to disagree, `AGENTS.md` governs.

## Start of a session

- Run `python3 .claude/skills/lab-ops/scripts/gh_ops.py brief`, then read the issue or PR you own.
- Studio work: `docs/STUDIO_CHARTA_V2.md` and the decision register
  `docs/OWNER_DECISIONS_STUDIO_20261118.md` (older part `..._20261112.md`). Owner-deck work: Chulane
  only (`docs/OWNER_DECK_FOCUS_CURRENT.md`). Claims and shared files:
  `docs/STUDIO_AGENT_ONBOARDING.md` and the claim table of #1167.
- When the workstream changes materially, record the handoff on GitHub and start a fresh session
  (`/clear`) instead of growing one giant context.

## Models and helpers

The Owner picks the main session's model and effort (project default `high` in
`.claude/settings.json`, Owner 2026-11-28); there is no automatic fallback between models. The
main session keeps planning, Rules and evidence adjudication, gate and merge decisions, and the
final check of helper output (`AGENTS.md` §7). Helpers get their own context, so their tool output
stays out of the main one. Each tier below follows Anthropic's guidance: Haiku for simple
read-only jobs, Sonnet for most coding, Opus for review and hard judgement.

| Helper | Model / effort | Use for | Writes |
|---|---|---|---|
| `scout` | Haiku / low | lookups, filtered command output, CI/test/PB-03 log digestion | no |
| `ci-triage` | Sonnet / medium | root cause of one red check | no |
| `builder` | Sonnet / high | one bounded change from a complete brief, tests first | commits |
| `reviewer` | Opus / high | fresh-context review before merge, all evidence-, Rules-, policy-sensitive diffs | no |
| built-in `Explore` / `Plan` | inherit | broad read-only search / plan research when grep is not enough | no |

- Deterministic first: `lab-ops` scripts, `grep`, a focused test or a packet reader beats any
  helper. Use a helper only when its output would flood the main context or the work is a
  bounded, parallel side task; iterative back-and-forth stays in the main session.
- One helper per PR-sized objective, with a complete brief (objective, source lock, files, rules
  to hold, tests first, exact commands, stop condition, report limit). Run independent helpers in
  parallel. Paste what one helper found into the next brief instead of having it rediscover it.
- Consume a helper's report first; reopen raw logs, diffs or evidence only for an authority
  decision, a contradiction, an unusual security/qualification claim or a required independent
  check. A `scout` fact that decides a gate or a merge is checked against the source.
- The fresh-context review of a MATERIAL change (`AGENTS.md` §10) always runs on `reviewer`,
  never on a lower tier: Opus at `high` or the main session's effort, whichever is higher (pass
  the higher effort on the invocation when the main session runs above `high`).
- A helper's fixed model and effort change only together with this table and
  `tests/unit/test_claude_routing_policy.py`, in a reviewed PR; never silently raised or lowered.
- Helpers are flat: no helper has the `Agent` tool, so none spawns children. No agent teams or
  recursive coordinator/worker trees for normal work.
- `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` (`.claude/settings.json`) is only the default for helpers
  without a `model:` field (for example `general-purpose`). `scout` and `ci-triage` set
  `omitClaudeMd: true` because they need no policy; `builder` and `reviewer` load it. No custom
  cache TTL without benchmark evidence.

## Token habits

- Test narrow while iterating; run the full suite once at the integration boundary.
- No background load (game series, builds) while helpers run test suites.
- Long Java suites, PB-03 runs and CI waits run in the background (`run_in_background` or
  `gh_ops.py wait`), never as repeated polls or bare `sleep`.
- Long command output goes to a file; read the tail or the matching lines.
- Helper reports ≤40 lines; routine status to the Owner ≤8 lines.
- No third review round for wording; a re-review checks only the delta.
- `gh_ops.py brief|status|queue|threads|wait|run|errors|rerun-cancelled` covers PRs, CI and logs.
  GitHub GraphQL is unavailable here: use `gh api` REST. A GitHub 429 gets one attempt, then stop
  and record it in the issue.

## Repo specifics Claude tends to miss

- The PostToolUse hook runs `ruff --fix` and `ruff format` after every edit; re-read a file only
  if a later edit fails to match.
- A skipped real-engine test is `NOT_RUN`; report it as such.
- `WS17_SHA256SUMS`: regenerate its digest line (`python scripts/regenerate_hash_manifests.py`)
  only within a change to `.github/workflows/production-qualification.yml` (`AGENTS.md` §8).
- Open CI points: `docs/CI_GATES_IMPROVEMENT_PLAN_20261112.md` (a plan, not a gate).
