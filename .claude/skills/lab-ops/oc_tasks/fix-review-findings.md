<!-- Fill only the <...> lines: 5-10 task-specific lines. oc_dispatch.py adds the
/rules footer, so do not repeat trailers, evidence rules or branch boilerplate. -->

**Objective.** Close the review findings below at the current head, without weakening anything.

**Findings.** <!-- one line per finding; keep severity, file:line and the repair -->
- P1 `<file:line>` — <wrong behavior> → <required repair; name the test that fails before it and passes after>
- P2 `<file:line>` — <wrong behavior> → <required repair>
- P3 `<file:line>` — <note> → <repair or explain why none>

**Constraints.** Repair the cause, not the assertion. No expected value, denominator or
check may be relaxed. Behavior outside the findings stays byte-for-byte identical.

**Validation.** Paste the real summary line for each command:
`rm -rf src/*.egg-info; PYTHONPATH=$PWD/src python -m pytest -q -p no:cacheprovider <paths>`
and `ruff check <paths> && ruff format --check <paths>`.

**Out of scope.** <branches, workstreams or evidence files this task must not touch>
