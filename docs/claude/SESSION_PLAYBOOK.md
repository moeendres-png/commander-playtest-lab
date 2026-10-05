# Claude session playbook (Commander Playtest Lab)

Operational know-how for a fresh Claude Code session working on this repository and its
engine forks (`moeendres-png/mage`, `moeendres-png/forge`). It is tooling guidance only:
`AGENTS.md` stays the policy source, and current lane state lives in the GitHub issues, never here.

## First ten minutes

1. Read `AGENTS.md`, `CLAUDE.md` and the latest checkpoint or handoff of your lane:
   - #441 / #255: provider qualification and eligibility evidence;
   - #479: the CI / Check / Gate lane.
   The newest issue comment wins over any older text.
2. The SessionStart hook has built `~/.cache/commander-lab-venv` (CI's hash-pinned lock plus an
   editable install) and put it first on `PATH`.
   - In a git worktree, run tests with `PYTHONPATH=$PWD/src` so the worktree's sources win.
   - Delete `src/*.egg-info` if an editable install recreates it. The PB-03 trigger-completeness
     tests count it as an unlisted input.
3. Load the `lab-ops` skill before touching GitHub or CI. Its scripts answer in one line what raw
   API dumps answer in 10k tokens.

## GitHub from a Claude Code session

- **GraphQL is unavailable.** `gh pr view/checks` fail; use REST (`gh api repos/...`) or the
  MCP GitHub tools.
- **Review threads, auto-merge and draft state** go through the CCR routes:
  - `repos/{o}/{r}/pulls/{n}/ccr/review_threads`;
  - `…/ccr/comments/{id}/resolve`;
  - `…/ccr/auto_merge`.
- **Comments:** post them with the MCP `add_issue_comment` tool. Raw curl POSTs return 415.
- **Secrets cannot be set from a session.** The Actions secrets API returns 403 through the
  proxy. Ask the Owner to set them in the repository settings, and never echo a secret into a
  file, commit or comment.
- **Merging your own PR may be refused by the auto-mode classifier.** Ask the Owner to merge or
  to enable auto-merge, and don't route around the refusal.
- **Duplicate check runs.** A re-triggered or cancelled run leaves a duplicate of the same check.
  `gh_ops.py status` reports one decisive verdict per check name; a raw check list can show
  false red.
- **CI-02.** `ci-definition-integrity-shadow` is red by design. Comment once per PR, never weaken
  it, and expect it to flag PRs that change a required workflow.
- **Codex review** is often out of quota. Without an external review, run the `evidence-reviewer`
  agent, or a fresh-context adversarial review agent on the main model, before pushing
  qualification or security code.

## Evidence work

- **Real-engine rows:** `lab-ops/scripts/real_rows.py`.
- **PB-03 packets:** `lab-ops/scripts/pb03_packet.py RUN_ID OUT`.
- **Sealing an epoch:** use `lab-ops/scripts/seal.py RUN_ID [--replace OLD]` on a fresh branch
  from main. It runs the broad secret scan before any push. The required `security` check scans
  every tracked file, so a packet that trips it would turn main red.
  - Fix the producer at its source; never add exclusions for evidence values.
  - Example: #550 renamed `keyed_digest` to `hmac_sha256` after gitleaks flagged 88 digests.
- **PB-03 dispatch:** PB-03 has no push trigger. Dispatch `pb03-runtime-qualification.yml` on
  `main` and wait with `gh_ops.py run RUN_ID` in the background (about 60 minutes).
- **Non-claims:** UNKNOWN is never PASS, LOCAL_OBSERVED is never credit, and
  `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Engine forks (Mage C12, Forge D17)

- **JDK version for local runs.** The trusted-qualification containment is a SecurityManager.
  - JDK 18+ refuses it unless `-Djava.security.manager=allow` is passed, and CI pins Java 17.
  - For local selftests, download Temurin 17 (api.adoptium.net), stage it root-owned under
    `/var/lib/c12-controls/jdk`, and run the selftest as the workflow does:
    `--sandbox-user c12cand`, root-owned JDK and Maven first on `PATH`.
  - `--smoke-honest` runs CTRL-01 in minutes.
- **Containment changes are security changes.**
  - Get explicit Owner approval before loosening any denial. The auto-mode classifier enforces
    this.
  - Prove every admission with negative probes that fail without the containment.
  - Get a fresh-context adversarial review before pushing.
- **Unfinished security work is never pushed onto a PR branch.** Park it on a `handoff/*-wip-*`
  branch and say so in the lane issue.
- **Agents and rate limits.** Subagents can be cut off by the session rate limit. Check their
  worktrees for uncommitted work before reusing or reporting it.

## Working efficiently without losing quality

- Long jobs (Java suites, PB-03, CI waits, selftests) run in the background. Keep working
  meanwhile; never poll in the foreground and never use bare `sleep`.
- Test narrow while iterating, then run the full required suite once before the push.
- Use read-only subagents (`log-scanner`, `ci-triage`, `Explore`) for broad sweeps. Every
  subagent runs on at least Sonnet at `high` effort. Judgement, Rules reasoning and merge
  decisions stay in the main session.
- One worktree per branch. Commit WIP before switching. No force push, no history rewrite, no
  push to `main`/`master`.
- End every session with a checkpoint comment on the lane issue: the state of each item, exact
  heads, the next step, and any parked WIP branch.
