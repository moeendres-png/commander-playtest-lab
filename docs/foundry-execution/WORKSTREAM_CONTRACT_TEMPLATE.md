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
