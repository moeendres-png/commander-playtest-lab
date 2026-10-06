<!-- Fill only the <...> lines: 5-10 task-specific lines. oc_dispatch.py adds the
/rules footer, so do not repeat trailers, evidence rules or branch boilerplate. -->

**Objective.** <the tooling or routing-doc surface to add or fix>

**Deliverable.** <file(s) to create or change>

**Interface.** `<command with arguments>` → <one-line output contract: line count, fields>

**Behavior to preserve.** <existing commands/policy text that must not change>

**Tests.** `<tests/unit/test_...>` must cover <the limits and failure modes>, with `gh api`
mocked by monkeypatch; no network in tests.

**Validation.** Paste the real summary line:
`rm -rf src/*.egg-info; PYTHONPATH=$PWD/src python -m pytest -q -p no:cacheprovider tests/unit`
and `ruff check <paths> && ruff format --check <paths>`.

**Out of scope.** <policy, gate or evidence files this task must not change>
