<!-- Fill the <...> values only. This is the task delta; Foundry already injects global policy.
oc_dispatch.py adds the fixed safety/evidence footer. -->

**Objective.** <one sentence: batch and issue item it closes>

**Source lock / ownership.** `<repo>@<40-hex SHA>`; branch/worktree `<...>`; owner `<workstream/baton>`.

**Dependencies / hard gates.** <dependencies, authority/ownership gates, and what must already be true>

**Evidence required.** <exact tests/readbacks/controls; no inference may substitute for observation>

**Stop condition.** <Semantic Completion condition or exact fail-closed blocker>

**Expected handoff.** Source Lock; Work Completed; New Findings; Changes; Tests/Evidence; PASS/FAIL/UNKNOWN; Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.

**Exact next action.** <the first concrete action after reading this packet>

**Items.**
1. <file/module — exact behavior to implement>
2. <file/module — exact behavior to implement>
3. <test module — wrong-reason/red test each item must kill>

**Build.** <where each change goes; alternatives only when the choice is non-obvious>

**Validation.** Paste real exit code + summary:
`rm -rf src/*.egg-info; PYTHONPATH=$PWD/src python3 -m pytest -q -p no:cacheprovider <test paths>`
and `ruff check <paths> && ruff format --check <paths>`.

**Out of scope.** <branches, workstreams or evidence files this task must not touch>
