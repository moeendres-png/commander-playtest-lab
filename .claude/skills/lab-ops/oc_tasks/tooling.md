<!-- Fill the <...> values only. This is the task delta; Foundry already injects global policy.
oc_dispatch.py adds the fixed safety/evidence footer. -->

**Objective.** <tooling or routing-doc surface to add/fix>

**Source lock / ownership.** `<repo>@<40-hex SHA>`; branch/worktree `<...>`; owner `<workstream/baton>`.

**Dependencies / hard gates.** <dependencies, authority/ownership gates, and what must already be true>

**Evidence required.** <exact tests/readbacks/controls; no inference may substitute for observation>

**Stop condition.** <Semantic Completion condition or exact fail-closed blocker>

**Expected handoff.** Source Lock; Work Completed; New Findings; Changes; Tests/Evidence; PASS/FAIL/UNKNOWN; Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.

**Exact next action.** <the first concrete action after reading this packet>

**Deliverable.** <file(s) to create or change>

**Interface.** `<command with arguments>` → <compact output contract>

**Behavior to preserve.** <existing commands/policy/evidence semantics that must not change>

**Tests.** `<tests/unit/test_...>` covers <limits/failure modes>; mock `gh api`, no network.

**Validation.** Paste real exit code + summary:
`rm -rf src/*.egg-info; PYTHONPATH=$PWD/src python3 -m pytest -q -p no:cacheprovider tests/unit`
and `ruff check <paths> && ruff format --check <paths>`.

**Out of scope.** <policy, gate or evidence surfaces this task must not change>
