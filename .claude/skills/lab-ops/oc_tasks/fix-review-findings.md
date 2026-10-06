<!-- Fill the <...> values only. This is the task delta; Foundry already injects global policy.
oc_dispatch.py adds the fixed safety/evidence footer. -->

**Objective.** Close the review findings below at the current head, without weakening anything.

**Source lock / ownership.** `<repo>@<40-hex SHA>`; branch/worktree `<...>`; owner `<workstream/baton>`.

**Dependencies / hard gates.** <dependencies, authority/ownership gates, and what must already be true>

**Evidence required.** <exact tests/readbacks/controls; no inference may substitute for observation>

**Stop condition.** <Semantic Completion condition or exact fail-closed blocker>

**Expected handoff.** Source Lock; Work Completed; New Findings; Changes; Tests/Evidence; PASS/FAIL/UNKNOWN; Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.

**Exact next action.** <the first concrete action after reading this packet>

**Findings.**
- P1 `<file:line>` — <wrong behavior> → <required repair; name the wrong-reason test>
- P2 `<file:line>` — <wrong behavior> → <required repair>
- P3 `<file:line>` — <note> → <repair or explain why none>

**Constraints.** Repair the cause, not the assertion. No expected value, denominator or check may
be relaxed; behavior outside the findings stays unchanged unless the repair necessarily touches it.

**Validation.** Paste real exit code + summary for each command:
`rm -rf src/*.egg-info; PYTHONPATH=$PWD/src python3 -m pytest -q -p no:cacheprovider <paths>`
and `ruff check <paths> && ruff format --check <paths>`.

**Out of scope.** <branches, workstreams or evidence files this task must not touch>
