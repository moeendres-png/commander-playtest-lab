# Writing prompts for Space Bunny MAX

Status: CANONICAL guidance (Owner directive 2026-10-10). Space Bunny MAX
(`opencode/space-bunny-free` on OpenCode Zen, native `max`) is the only active OpenCode executor;
the OpenCode Go ids are retired because they share the exhausted Go monthly quota. It runs every
lane: `/oc` (`foundry-implementer`), `/bunny` (`bunny-verifier`), `/bunny-review` (read-only
`foundry-reviewer`), the Foundry launcher and the Claude-side `opencode-subagent` MCP tools.
DeepSeek is SUSPENDED; never name it as a target, a fallback or a "cheaper" option.

This guide is derived from this repository's lane contracts, its evidence rules and the run
failures it has recorded (step timeouts, token expiry, hung CLIs, quota refusals). It is not
vendor documentation about the model's internals. Authority stays with `AGENTS.md` and
`docs/CURRENT_EXECUTION_AUTHORITY.md`; this file only says how to phrase a task well.

## 1. Pick the lane before writing the prompt

| Need | Lane | Agent | Writes? |
|---|---|---|---|
| Implement, fix, CI repair, tooling, evidence production | `/oc` | `foundry-implementer` | yes, own branch + PR |
| Maximum-assurance task (two-route proof, full suites, auditor) | `/bunny` | `bunny-verifier` | yes, only when the task says so |
| MATERIAL review gate on an exact SHA/TREE | `/bunny-review` | `foundry-reviewer` | never |
| Bounded side task from a Claude session | `opencode-subagent` MCP | per call | per permission mode |

The model is the same everywhere; the lane decides permissions and posture. Do not ask an `/oc`
run to "also review itself": the review gate only accepts the separate `/bunny-review` run.

## 2. Use the skeletons, fill only the delta

Start from `.claude/skills/lab-ops/oc_tasks/<template>.md` and post with
`python3 .claude/skills/lab-ops/scripts/oc_dispatch.py post`. The skeleton fields are the
contract Space Bunny works best with, because each one removes a guess:

- **Objective**: one sentence, one outcome. Two outcomes are two dispatches.
- **Source lock / ownership**: repo, 40-hex SHA, branch, owner. The model re-checks it before
  reporting; a vague lock produces a vague report.
- **Dependencies / hard gates**: what must already be true, and which gates stop the run.
- **Evidence required**: exact commands, tests, readbacks and the wrong-reason control each change
  must kill. Name the command; never write "make sure it works".
- **Stop condition**: the Semantic Completion condition or the exact fail-closed blocker.
- **Exact next action**: the first concrete step, so the run does not spend its budget orienting.
- **Out of scope**: branches, workstreams and evidence files it must not touch.

The global policy (AGENTS.md, permissions, evidence semantics) is already injected. Do not paste
it again; repeated policy dilutes the task delta.

## 3. Prompt rules that matter for this model

1. **Give facts, not history.** Paste the failing line, the file:line and the SHA, not the chat
   that found them. Say which facts are observed and which are inferred.
2. **State the claim to establish before the method.** "After the change, X holds and Y is
   unchanged" lets the model choose a route and still be checked against the claim.
3. **Ask for reproduce-then-repair.** Require a red command first, then the green one, with real
   exit codes in the handoff.
4. **Bound the read surface.** Name the 3 to 10 files that matter and the `lab-ops` scripts to use
   for status and logs. Unbounded "explore the repo" burns the run's time box.
5. **Fit the time box.** A GitHub lane step ends at 55 minutes and the action token lives one
   hour. Size each dispatch to finish well inside that, start long suites first, and require a
   pushed checkpoint before any long wait. Split anything larger.
6. **Name the verdict vocabulary.** `PASS / FAIL / UNKNOWN / BLOCKED`; `UNKNOWN != PASS`;
   a local run is not CI credit. Ask for a certainty ledger line per claim on `/bunny`.
7. **Make blockers terminal.** Quota (`BLOCKED_SERVICE`), auth, catalog or permission failures end
   the run with a report. Never ask it to retry on another model or provider.
8. **One owner per surface.** If another thread or PR owns a file, say so and forbid edits there.
9. **German or English, never mixed inside one field.** Keep identifiers, commands and paths
   verbatim.

## 4. Review prompts (`/bunny-review`) while one model does both jobs

With DeepSeek suspended the reviewer is the same model as the implementer (explicit Owner approval,
2026-10-10). The only independence left is a fresh context, so protect it:

- Give the reviewer the exact SHA, TREE, PR link and the acceptance claim. Do not paste the
  implementer's reasoning, handoff narrative or "why this is correct".
- Ask adversarially: "find the input, state or ordering that makes this wrong", with the
  wrong-reason controls it must try, not "confirm the fix".
- Require the machine-parseable receipt the gate reads (`BUNNY_DIRECT_READ_ONLY_REVIEW`) and the
  P1/P2/P3 finding split. A MATERIAL change after the review makes it STALE.
- For Rules, evidence, containment or security decisions, add the Claude `evidence-reviewer`
  (Opus `high`) as a second, different-model reviewer.

## 5. `opencode-subagent` MCP calls from Claude

`.claude/settings.json` sets `OPENCODE_SUBAGENT_MODEL=opencode/space-bunny-free`, the plugin
default. Still pass `model: "opencode/space-bunny-free"` on every `agent` call so a stale plugin
default can never select another model. Brief it like a dispatch: objective, files, exact
validation command, stop condition, and "do not call `mcp__hearthbot__` tools".

## 6. Minimal example (`/oc`)

```text
/oc **Objective.** Make `tools/foundry/review_gate.py` reject a review record whose reviewed_tree
does not match the validated tree (issue #NNN item 2).

**Source lock / ownership.** `moeendres-png/commander-playtest-lab@<sha>`; branch
`fix/review-tree-<date>` from main; owner: this dispatch.

**Evidence required.** New test in `tests/foundry/test_review_gate.py` that is red on <sha> and
green after; `PYTHONPATH=$PWD/src python3 -m pytest -q -p no:cacheprovider tests/foundry` exit 0;
`ruff check tools/foundry tests/foundry && ruff format --check tools/foundry tests/foundry`.

**Stop condition.** PR open with both red and green outputs pasted, or a named blocker.

**Exact next action.** Read `review_gate.py` lines 95-140 and write the red test.

**Out of scope.** `.foundry/reviews/**`, any other open PR's branch.
```
