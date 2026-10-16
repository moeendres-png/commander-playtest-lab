# Writing prompts for DeepSeek V4.1 Flash MAX

Status: CANONICAL guidance (Owner instruction 2026-10-16). DeepSeek V4.1 Flash MAX
(`opencode/deepseek-v4.1-flash-free` on OpenCode Zen, native variant `max`) is the only OpenCode
model this project uses. Zen lists it free, zero-retention and not trained on; models.dev lists
effort values low/high/max, context 200000, output 32000. It runs every lane: `/oc`
(`foundry-implementer`), `/assure` (`assurance-verifier`), `/ro-review` (read-only
`foundry-reviewer`), the Foundry launcher and Claude-side runs through the `opencode` CLI
(`opencode run -m opencode/deepseek-v4.1-flash-free --variant max`). Step 5 Preview left the Zen
catalog and was retired on 2026-10-16; never name another model as a target, fallback or
"cheaper" option.

Always native `max`; no variant below `high` is configured anywhere and the launcher refuses a
caller `--variant`/`--model`. Do not write "think less" or "be quick" into a task: save tokens on
input, never on reasoning or verification.

Derived from this repository's lane contracts, evidence rules and recorded run failures (step
timeouts, token expiry, hung CLIs, quota refusals), not from vendor internals. Authority stays
with `AGENTS.md` and `docs/CURRENT_EXECUTION_AUTHORITY.md`; this file only says how to phrase a task.

## 1. Pick the lane before writing the prompt

| Need | Lane | Agent | Writes? |
|---|---|---|---|
| Implement, fix, CI repair, tooling, evidence production | `/oc` | `foundry-implementer` | yes, own branch + PR |
| Maximum-assurance task (two-route proof, full suites, auditor) | `/assure` | `assurance-verifier` | only when the task says so |
| MATERIAL review gate on an exact SHA/TREE | `/ro-review` | `foundry-reviewer` | never |
| Bounded side task from a Claude session | `opencode` CLI / MCP | per call | per permission mode |

### `/oc` (Zen) or `/oc-th` (Token Harbor)

Same model, same `foundry-implementer` agent, same trust gate; the Coordinator picks the
provider per dispatch and never falls back from one to the other.

- `/oc` (default): Zen, zero-retention, no training; capped by the daily Zen request limit.
- `/oc-th`: Token Harbor free plan (`tokenharbor/deepseek-v4.1-flash:free`; the paid base id is
  never called), 60 req/min and
  1800 req/h, a rolling 7-day allowance. The provider documents no reasoning-effort control, so
  the model runs at its provider default (`max` cannot be pinned). Free routes may be logged and
  used for improvement: never put Owner data, credentials or private collection data in an
  `/oc-th` task. Post it with `oc_dispatch.py post --lane oc-th`.

The model is the same everywhere; the lane sets permissions and posture. Never ask an `/oc` run to
review itself: the gate only accepts the separate `/ro-review` run.

## 2. Phrase the task: one objective, exact lock, exact commands

Start from `.claude/skills/lab-ops/oc_tasks/<template>.md` and post with
`python3 .claude/skills/lab-ops/scripts/oc_dispatch.py post`. Fill only the delta; AGENTS.md,
permissions and evidence semantics are already injected, and repeating them dilutes the task.

The lane command must be the first token of the comment (`/oc task…`, `/oc-th task…`,
`/assure task…`, `/ro-review task…`, or the command alone): a lane fires only on a leading
command, never on a command named later in the task text, and `oc_dispatch.py post` writes it first.

- **Objective**: one sentence, one outcome. Two outcomes are two dispatches.
- **Source lock / ownership**: repo, 40-hex SHA, branch, owner. State which facts are observed and
  which inferred; paste the failing line with file:line, not the chat that found it.
- **Claim first, method second**: "after the change X holds and Y is unchanged"; require a red
  command first, then the green one, with real exit codes.
- **Exact commands**: the one test command, the lint command, the readback. Never "make sure it works".
- **Evidence**: what to paste, plus the wrong-reason control each change must kill.
- **Read surface**: name the 3 to 10 files that matter and the scripts to use. "Explore the repo" burns the time box.
- **Stop conditions**: the Semantic Completion condition or the exact fail-closed blocker. Verdicts
  are `PASS / FAIL / UNKNOWN / BLOCKED`; `UNKNOWN != PASS`; a local run is not CI credit.
- **Handoff format**: commits (SHA + subject), files changed, commands with exit codes, UNKNOWN and
  BLOCKED items, exact next action; at most 40 lines.
- **Out of scope**: files, branches and sealed evidence it must not touch; one owner per surface.
- **Time box**: a GitHub lane step ends at 55 minutes and the action token lives one hour. Size the
  dispatch inside that, start long suites first, push a checkpoint before any long wait.
- Quota, auth, catalog or permission failures end the run (`BLOCKED_SERVICE`); never ask it to retry
  on another model or provider. Keep identifiers, commands and paths verbatim; one language per field.

## 3. Use tools and skills, do not improvise

Run deterministic scripts before reasoning, and load a skill before a matching task (name it in the
first message so the run is auditable). Project skills live in `.opencode/skills/<name>/SKILL.md`:

| Skill | Load it WHEN |
|---|---|
| `workstream-bootstrap` | starting a new workstream: repo identity, source lock, worktree inventory, branch ownership, dirty tree |
| `continuation` | resuming after session loss, compaction or handoff: Git plus the state file win over memory |
| `test-impact` | deciding which tests/evidence a change affects; uncertain impact means requalify |
| `component-change-review` | reviewing a changed tool/config/doc before it earns validation credit; no weakened assertions |
| `failure-classification` | a test, CI or run failed: assign one canonical class, `UNKNOWN` stays `UNKNOWN` |
| `evidence-seal` | recording commands, runs, hashes and verdicts as a structured seal; nothing inferred or backfilled |
| `rules-authority-escalation` | a task turns on what Magic rules MEAN rather than what code does: freeze the question and write an `AUTHORITY_GATE`, do not decide |
| `lab-ops` | any PR/CI/log/PB-03/real-engine question: use the scripts below instead of raw API JSON or whole logs |

Scripts (`.claude/skills/lab-ops/scripts/`, run from the worktree root, compact output):

- `gh_ops.py brief` is the one-screen lane status (open PRs, running `/oc`/`/assure` runs, PB-03, newest epoch);
  also `status PR…`, `threads PR`, `errors JOB_ID`, `wait PR…`, `run RUN_ID`.
- `oc_dispatch.py post|watch|rescue` builds a dispatch from a task file plus the fixed footer, watches
  the outcome in at most 15 lines (run `watch` in the background), and recovers a failed run's bundle.
- `pb03_packet.py RUN_ID OUT` downloads a PB-03 packet and prints the AF00-AF11 verdicts per candidate.
- `real_rows.py build|midgame|cardinality|pregame|af04` runs rows on the real XMage engine
  (LOCAL_OBSERVED only, never credit).

Also prefer `tools/foundry/` helpers (`source_lock.py`, `test_impact.py`, `cluster_failures.py`,
`evidence.py`) over hand-rolled checks. Use the editor, grep and glob tools over ad-hoc shell parsing.

## 4. Request-budget discipline (free tier)

The free Zen tier is request-capped; user reports say about 200 requests per day (unverified).
Spend requests like money:

- Batch reads: open several files or one `grep -n` per step, not one file per step.
- Fewer, bigger steps: edit a file completely in one write; do not narrate or re-read what you just wrote.
- Run tests with one command per surface (`python3 -m pytest -q -p no:cacheprovider <paths>`), narrow
  while iterating, the full suite once at the integration boundary; long suites in the background.
- One job at a time: never run parallel free runs and never fan out subagents.
- A quota refusal or a hung run is `BLOCKED_SERVICE`: write a checkpoint (state, branch, next action),
  stop, and resume the next day. Do not retry in a loop and do not switch model or provider.
- The lane watchdog detects both the Go `GoUsageLimitError` and the Zen free-tier
  `FreeUsageLimitError` (HTTP 429 from the `opencode` provider) and stops the run as
  `BLOCKED_SERVICE` instead of waiting out the CLI's retries.

## 5. Review prompts (`/ro-review`)

With one ACTIVE profile the reviewer is the same model as the implementer (single-executor review,
Owner approval 2026-10-10, restated 2026-10-16). If a second profile is ever ACTIVE, same-model
self-review is refused. The only independence left is a fresh context, so protect it:

- Give the reviewer the exact SHA, TREE, PR link and acceptance claim; not the implementer's
  reasoning or "why this is correct".
- Ask adversarially: "find the input, state or ordering that makes this wrong", with the
  wrong-reason controls to try, not "confirm the fix".
- Require the machine-parseable receipt (`DIRECT_READ_ONLY_REVIEW`) and the P1/P2/P3 split. A
  MATERIAL change after the review makes it STALE.
- For Rules, evidence, containment or security decisions add the Claude `evidence-reviewer` (Opus
  `high`) as a different-model second reviewer.

## 6. Claude-side calls

`.claude/settings.json` sets `OPENCODE_SUBAGENT_MODEL=opencode/deepseek-v4.1-flash-free`. Pass
`model: "opencode/deepseek-v4.1-flash-free"` on every `opencode-subagent` `agent` call so a stale
plugin default (the external plugin still defaults to a retired Go id) can never select another
model. Brief it like a dispatch and add "do not call `mcp__hearthbot__` tools".

## 7. Minimal example (`/oc`)

```text
/oc **Objective.** Make `tools/foundry/review_gate.py` reject a review record whose reviewed_tree
does not match the validated tree (issue #NNN item 2).

**Source lock / ownership.** `moeendres-png/commander-playtest-lab@<sha>`; branch
`fix/review-tree-<date>` from main; owner: this dispatch. Load skills: component-change-review, test-impact.

**Evidence required.** New test in `tests/foundry/test_review_gate.py`, red on <sha>, green after;
`PYTHONPATH=$PWD/src python3 -m pytest -q -p no:cacheprovider tests/foundry` exit 0;
`ruff check tools/foundry tests/foundry && ruff format --check tools/foundry tests/foundry`.

**Stop condition.** PR open with red and green outputs pasted, or a named blocker.

**Exact next action.** Read `review_gate.py` lines 95-140 and write the red test.

**Out of scope.** `.foundry/reviews/**`, any other open PR's branch.
```
