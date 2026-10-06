<!-- Fill only the <...> lines: 5-10 task-specific lines. oc_dispatch.py adds the
/rules footer, so do not repeat trailers, evidence rules or branch boilerplate. -->

**Objective.** Make the red check below green by repairing its cause, never by weakening it.

**Red check.** `<check name>` on `<repo>#<number>` (job `<job id>`); failing lines:
```
<paste the gh_ops.py errors JOB_ID lines>
```

**Diagnosis.** <THIS_PR / BASE_BRANCH / INFRA_BEFORE_TESTS / BY_DESIGN and the one-line reason>

**Required repair.** <the smallest change that makes the failing path correct>

**Evidence it is not a flake.** <where the same failure reproduces, or the control that proves the fix>

**Validation.** Paste the real summary line for the local equivalent of the check, plus
`ruff check <paths> && ruff format --check <paths>` for changed Python.

**Out of scope.** <branches, workstreams or evidence files this task must not touch>
