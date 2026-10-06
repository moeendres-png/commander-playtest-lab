<!-- Fill the <...> values only. This is the task delta; Foundry already injects global policy.
oc_dispatch.py adds the fixed safety/evidence footer. -->

**Objective.** Make the red check below green by repairing its cause, never by weakening it.

**Source lock / ownership.** `<repo>@<40-hex SHA>`; branch/worktree `<...>`; owner `<workstream/baton>`.

**Dependencies / hard gates.** <dependencies, authority/ownership gates, and what must already be true>

**Evidence required.** <exact tests/readbacks/controls; no inference may substitute for observation>

**Stop condition.** <Semantic Completion condition or exact fail-closed blocker>

**Expected handoff.** Source Lock; Work Completed; New Findings; Changes; Tests/Evidence; PASS/FAIL/UNKNOWN; Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.

**Exact next action.** <the first concrete action after reading this packet>

**Red check.** `<check name>` on `<repo>#<number>` (job `<job id>`); failing lines:
```
<paste only the gh_ops.py errors JOB_ID lines>
```

**Diagnosis.** <THIS_PR / BASE_BRANCH / INFRA_BEFORE_TESTS / BY_DESIGN and one-line reason>

**Required repair.** <smallest change that makes the failing path correct>

**Evidence it is not a flake.** <reproduction/control proving the diagnosis>

**Validation.** Paste real exit code + summary for the local equivalent of the check, plus
`ruff check <paths> && ruff format --check <paths>` for changed Python.

**Out of scope.** <branches, workstreams or evidence files this task must not touch>
