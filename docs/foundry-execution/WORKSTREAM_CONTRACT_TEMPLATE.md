# Workstream Contract Template

Copy this template to the workstream handoff or state directory for every
substantial task. Fill every field; nothing stays blank without a reason.
Technical-decision authority defaults to autonomous-within-contract.

## Repository

`moeendres-png/commander-playtest-lab`

## Worktree

[absolute path]

## Branch

[branch name; one workstream ↔ one branch ↔ one worktree]

## Source Lock / AUDIT_BASE_SHA

- audit base SHA:
- audit base tree:
- current HEAD (at contract issue):

## Objective

[one primary objective]

## Inputs

[contracts, pins, runs, artifacts, docs]

## Authority

[newest direct user instruction; Coordinator adjudications; this contract]

## In Scope

[list]

## Out of Scope

[list]

## Ownership

[session/workstream owning the mutation surface]

## Dependencies

[list]

## Hard Gates

[list; include evidence classification required per gate]

## Forbidden Shortcuts

[list; Rules fallbacks, PASS promotion, hidden engines]

## Evidence Requirements

[commands, artifacts, hashes, run IDs, seal location]

## TECHNICAL_DECISION_AUTHORITY

Default: `AUTONOMOUS_WITHIN_CONTRACT`

Muse owns technical in-scope decisions: inspect authoritative evidence, form and
challenge hypotheses, run the smallest permitted validation, adjudicate within
already-defined project policy, persist the decision and evidence, continue.
Reaching and persisting a technical root cause is the job, not an escalation.

## SEMANTIC_COMPLETION

Default: enabled. Do not voluntarily stop at a first failure, a single passing
scenario, a compiled tree, a written artifact, an obvious repair, or a finished
primary subgoal while required evidence/hardening remains. Continue until the
entire authorized scope is COMPLETE or a genuine terminal Authority Gate, Scope
Gate, ownership conflict, infrastructure blocker, or correctness/privacy failure
condition exists. Early primary success spends remaining in-scope capacity, in
order, on: impacted validation; evidence completeness; provenance/hash binding;
contract-required adversarial controls; final-diff audit; replay/resumability;
dependency analysis; successor planning. Never invent unrelated work.

## CONTINUATION_POLICY

Default: `EXACT_NEXT_ACTION_ONLY` (execute exactly the binding
`exact_next_action`, checkpoint, stop). `BOUNDED_IN_SCOPE` (explicit opt-in,
Coordinator-visible in state) permits advancing through declared
`remaining_scope` items inside `in_scope`/`out_of_scope`/`authority_gates`
bounds with per-milestone checkpoints. Never authorizes: new-workstream
execution, branch/worktree creation, remote PR/merge/push, provider/freeze/
Rules decisions, cross-workstream mutation.

## COMPLETION_READINESS

Marking `COMPLETE` requires: non-null ancestry-clean `validated_head`, empty
`remaining_scope`, empty `failed_gates`. Check with
`state.py --state PATH --check-completion --workdir WTROOT`. Otherwise keep
`ACTIVE`/`BLOCKED` and record the blocker. Readiness is advisory for legacy
states, enforced at credit boundaries for new claims.

## SUCCESSOR_PLAN

Default: `NONE` (no successor). Terminal planning may record up to 3
execution-ready proposals as a separate validated artifact (pointer + sha256 in
state). Planning never executes: every successor needs a fresh explicit
Coordinator/operator launch. Statuses: `NONE` / `PROPOSED` / `AUTHORIZED`
(`AUTHORIZED` additionally requires `preauthorized: true` plus a named
authorization record; never inferred from autonomy).

## SESSION_ROTATION

Advisory only, threshold-free. `NO_ROTATION` / `REVIEW_PROMPT` /
`ROTATE_TO_FRESH_CONTINUATION` (preserves the exact resumable state; never
kills/resets the live process, never changes model/provider). Any non-`NONE`
recommendation without an `opencode export` aggregate carries the
export-missing hygiene reminder. No token/cache figures without export
provenance (`UNKNOWN` stays `UNKNOWN`).

## AUTHORITY_GATES

Explicit questions reserved for Sol High (empty only with justification):

- [ ] Rules / evidence-policy / architecture / scope / provider / freeze question,
      if any; otherwise `NONE`

## ESCALATION

HIGH may determine the task has become nonlocal or ambiguous and requires XHIGH
(technical adjudication tier). HIGH→XHIGH escalation is not failure. Persist
state (HEAD, validated gates, current hypothesis, remaining scope, exact next
action) before changing sessions or effort where necessary.

## Persistence

[state file path; commit discipline; handoff sections]

## Stop Conditions

[COMPLETE definition; AUTHORITY_GATE conditions; fail-closed triggers]

## Handoff

[Source Lock; Work Completed; New Findings; Changes; Tests/Evidence with
classifications; PASS/FAIL/UNKNOWN; Remaining Blockers; Outputs;
Dependencies Unblocked; Exact Next Action]
