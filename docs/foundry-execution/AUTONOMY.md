# Foundry Autonomous Workstream Orchestration (WS198)

Canonical operating model so future OpenCode/Muse workstreams run through
Semantic Completion without bespoke operator addenda ("continue overnight",
"make your own technical decisions", "use XHIGH when difficult"). Normative
rules live here plus the cited static layers; machine-checkable values live in
the state schema (`continuation_policy`, `successor_plan`, `rotation_guidance`)
and `tools/foundry/autonomy.py`. Dynamic prompts carry values only, never this
prose.

`TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT` (default).
`NEW_WORKSTREAM_EXECUTION = COORDINATOR_GATE` (default; plan-only otherwise).
`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.

## 1. Autonomous technical execution

Muse independently runs: inspect → hypothesize → challenge → validate →
adjudicate technically → implement when authorized → test → diagnose → repair →
validate → persist → continue. Routine technical questions are never bounced to
the Coordinator. HIGH owns ordinary execution; XHIGH owns difficult technical
root-cause, provenance, qualification, failure-class, and repair-DAG
adjudication **within already-defined project policy** — never Rules,
evidence-policy, architecture, scope, provider, or freeze questions (those are
`AUTHORITY_GATE` for Sol High).

## 2. Strong Semantic Completion

Do not voluntarily stop because the first test failed, one scenario passed, the
first blocker appeared while independent in-scope work remains, compilation
succeeded, the initial artifact was written, the obvious repair succeeded, or
the primary subgoal completed while required evidence/hardening remains.
Continue until the entire authorized scope is COMPLETE or a genuine terminal
Authority Gate, Scope Gate, ownership conflict, infrastructure blocker, or
correctness/privacy failure condition exists.

## 3. Early-completion utilization

When primary work finishes early, spend remaining in-scope capacity, in order,
on: impacted validation; evidence completeness; provenance and hash binding;
contract-required adversarial/negative controls; final-diff semantic audit;
replay/resumability checks where relevant; dependency/unblocking analysis;
successor planning. Never invent unrelated work to stay busy.

## 4. Conditional continuation inside one workstream

`continuation_policy` (state; default `EXACT_NEXT_ACTION_ONLY`): execute exactly
the binding `exact_next_action`, checkpoint, stop. `BOUNDED_IN_SCOPE`
(explicit, Coordinator-visible opt-in) permits advancing through declared
`remaining_scope` items that are each inside `in_scope`, outside
`out_of_scope`, unblocked by `authority_gates`, and free of
branch/worktree-creation, remote-mutation, or provider-switch shapes — with a
state checkpoint per milestone. The first bound violation stops that line
fail-closed. This is never silent scope expansion: bounds are the original
repository, worktree, ownership surface, and explicit contract.

Failure-class DAG: harness/fixture/evidence/infra defects → bounded HIGH
repair; provider-adapter defects → XHIGH adjudication, adapter translation
only; **engine/Rules-semantic failure → fail closed at the engine boundary,
never remediated via harness/adapter/fixture edits**; ambiguous
engine-vs-adapter-vs-harness stays `UNKNOWN`; Rules-meaning disputes freeze
that line into an `AUTHORITY_GATE`.

## 5. Cross-workstream boundary

A worker may fully design a successor but must never create a branch/worktree,
mutate another repository, merge, rebase, or start a new epoch on its own
authority. No preauthorization mode exists yet: any `AUTHORIZED` successor still
requires a fresh explicit Coordinator/operator launch. There is no implicit
activation path (malformed autonomy fields fail closed; `preauthorized: true`
plus a named authorization record are both required).

## 6. Execution-ready successor planning

Terminal planning may propose at most 3 successors as a separate validated
artifact (JSON validated by `autonomy.validate_successor_set`: objective,
repository, proposed branch/worktree, source-lock basis, inputs, ownership,
dependencies, in/out of scope, hard gates, forbidden shortcuts, evidence
requirements, recommended HIGH/XHIGH lane, stop conditions, rationale, exact
initial prompt, executability). The state carries only a pointer + sha256.
Each proposal is classed `IMMEDIATE` / `DEPENDENCY_BLOCKED` /
`COORDINATOR_DECISION`. Never fabricate future SHAs: a 40-hex SHA needs
`sha_provenance` naming the existing commit it was read from.

## 7. Session rotation (evidence-honest)

WS78B's natural baseline contributed structural guidance only; token/cache
figures remain `UNKNOWN` without an `opencode export` aggregate, and no
token-based rotation threshold exists anywhere. WS199 provides the bounded
exact-session capture (`tools/foundry/session_capture.py`; exact OpenCode
session ID required, raw `LOCAL_ONLY`, aggregates `AUTOCAPTURED`, telemetry
fail-open) so future workstreams can accumulate export-proven aggregates
naturally; it introduces no threshold, no automatic rotation, no kill/reset,
and no model/provider change. `rotation_guidance` is advisory:
`NO_ROTATION` / `REVIEW_PROMPT` / `ROTATE_TO_FRESH_CONTINUATION` (checkpoint,
then recommend a fresh compact continuation from the exact resumable state —
never kill/reset the live process, never change model/provider). Non-`NONE`
guidance without export provenance carries the export-missing hygiene reminder.

## 8. Compact continuation

`/work` + the derived capsule resume the autonomous contract without another
mega-prompt: the capsule carries `technical_decision_authority`,
`continuation_policy`, `remaining_scope`/`do_not_rerun` counts,
`completion_ready`, `successor_plan` status, and rotation advisory (values
only, ≤4 KB). Counts without content mean escalate to `--full`/file read.
Static prose is never pasted into dynamic prompts.

## 9. TUI/headless prompt semantics (pinned CLI 1.18.30, DIRECTLY_VERIFIED)

Headless and TUI prompt injection are explicitly distinct:

- headless: `opencode run --auto <bare message>` (`run [message..]`).
- TUI: `opencode --auto --prompt "<task>"` (`[project]` positional; `--prompt`
  carries the initial message). Launcher spelling: `-- --prompt "<task>"`.

Bare positional text is NEVER prompt input for TUI: the CLI binds it to the
project path, fails instantly (`Error: Failed to change directory ...`), and
still returns child exit 0 — certifying a session in which no agent executed.
The launcher refuses that shape at construction
(`canonicalize_tui_extras` → `LAUNCH_REFUSED`); post-hoc detection without
heuristic stderr parsing is not reliable, so prevention plus `ui_mode` run
telemetry is the systemic answer. `LAUNCH_END: exit=0` certifies process exit,
never engineering success.

## 10. Compatibility

Schema 2.0 additive: old valid states parse unchanged and resolve to
`EXACT_NEXT_ACTION_ONLY` / `NONE` / `NO_ROTATION`. Malformed autonomy fails
closed. Completion-readiness never retro-invalidates legacy states.
`TOKEN_ECONOMY_BENCHMARK = NOT_RUN`, `COMPACTION_HOOK = DEFERRED`,
`SESSION_ROTATION_THRESHOLD = MODELED` stand unchanged.
