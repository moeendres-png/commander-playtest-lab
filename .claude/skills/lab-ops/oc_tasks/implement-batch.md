<!-- Fill only the <...> lines: 5-10 task-specific lines. oc_dispatch.py adds the
/rules footer, so do not repeat trailers, evidence rules or branch boilerplate. -->

**Objective.** <one sentence: the batch, and which issue item it closes>

**Items.**
1. <file or module — exact behavior to implement>
2. <file or module — exact behavior to implement>
3. <test module — the red test each item must kill>

**Build.** <where the change goes, one line per item; name alternatives you rejected only if the choice is non-obvious>

**Validation.** Paste the real summary line:
`rm -rf src/*.egg-info; PYTHONPATH=$PWD/src python -m pytest -q -p no:cacheprovider <test paths>`
and `ruff check <paths> && ruff format --check <paths>`.

**Out of scope.** <branches, workstreams or evidence files this task must not touch>
