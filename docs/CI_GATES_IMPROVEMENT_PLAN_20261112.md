# CI, checks and gates: findings and recommendations, 2026-11-12

Planning document for a CI improvement lane. It changes no workflow and no gate. Every
recommendation that touches a required check, a gate test or
`.github/workflows/production-qualification.yml` is an Owner decision and goes through its own
pull request with the existing integrity checks (`ci-definition-integrity-shadow`,
`repository-tree-integrity`, `WS17_SHA256SUMS`). Nothing here weakens a gate: no skipped,
disabled or quarantined test, and `UNKNOWN` never becomes PASS.

## What was measured

Source: the GitHub Actions run list of this repository, the 200 most recent `pull_request`
runs as of 2026-11-12 (19 runs of the CI workflow), and the step times of the `quality` job.
Counts are from that sample only.

| Workflow | Runs | Median | Sum (minutes) | Result |
|---|---:|---:|---:|---|
| CI (`quality`, `security`) | 19 | 10.9 min | 208 | 8 success, 7 failure, 3 cancelled, 1 running |
| PB-03 runtime qualification | 6 | 18.8 min | 78 | 2 success, 4 cancelled |
| Production Qualification (`infrastructure`) | 19 | 4.4 min | 72 | 16 success, 3 cancelled |
| H4 Docker Materialization | 19 | 0.7 min | 49 | 15 success, 4 cancelled |
| all other pull-request workflows together | 137 | under 5 min each | 150 | no failure |

- The required contexts are `quality`, `security` and `infrastructure`. `quality` sets the
  waiting time of every pull request: about 11 minutes, of which the test suite is about 9
  (four shards on a four-core runner).
- Six failed CI runs were looked at by step: 5 failed in "Test suite" and 1 in "Mypy strict",
  so in a check step and not in the infrastructure. Their causes were not analysed here.
- One `quality` job failed although every check step had passed: the step
  `actions/upload-artifact` ran for 11 minutes and then failed. The required context turned
  red because of an evidence upload.
- `ci-definition-integrity-shadow` is red on every pull request that adds or changes a test
  file. It is not required and red by design, but it sends a failure notification each time.
- Every issue or pull-request comment starts three workflows with six jobs (`opencode`,
  `opencode-assure`, `opencode-ro-review`, `oc-zai`, `oc-zai-review`, `gemini-review`) that
  end as skipped when the comment is not a command.
- A change to documents only runs the same required jobs as a code change.
- Locally the full suite does not finish inside the time limit of an agent session, and
  `tests/unit/test_packaging_smoke` errors in an environment without `pip`. Agents therefore
  rely on CI for the full run.
- One Studio test depends on Java being installed (noted in pull request #1207).

## Recommendations

Ordered by benefit against risk. "Gate" says whether a required check or gate definition is
touched.

| # | Recommendation | Benefit | Gate |
|---|---|---|---|
| 1 | Make the evidence upload at the end of `quality` unable to hang the job: a step timeout of two to three minutes and one retry. Keep the failure visible when the upload still fails. | Removes a red required check that no code caused, and an 11-minute wait. | yes: step in `ci.yml` |
| 2 | Let `ci-definition-integrity-shadow` end neutral with its report attached when it only found added or changed tests, and red only for the classes that need an Owner look (removed test, weakened assertion, changed required context). | Red then means something again; fewer failure notifications per pull request. | yes: its own definition; Owner decision |
| 3 | A fast path for changes to documents only: one first job classifies the diff; for `docs/**` and `*.md` without workflow, config or data changes the heavy steps are skipped inside the same required jobs, which still report. Document tests (link and privacy checks) keep running. | A document pull request waits about 1 minute instead of 11. | yes: `ci.yml` and `production-qualification.yml`, with digest update |
| 4 | Order the `quality` steps so that cheap ones fail first: lint, format, compile and secret scan before the test suite, and mypy in a parallel job instead of in front of the tests. | A lint or type error is reported after one minute instead of ten. | yes: `ci.yml` |
| 5 | Split the test suite by ownership into two required-context jobs running in parallel (for example the Studio tests and the rest), each with its own shards, both feeding `quality`. Refresh the shard weight table from the JUnit times that CI already writes. | Wall time of `quality` goes down by the smaller half; an uneven shard table is corrected by data. | yes: `ci.yml` and the ownership test |
| 6 | Remove the Java dependence from the unit suite: tests that need a JVM declare it with one shared marker and are skipped with a named reason locally, while CI sets a variable that turns a skip into a failure. | Same result locally and in CI, and no silent skip in CI. | no gate weakened; test hygiene |
| 7 | A local command `scripts/check_fast.sh` that runs exactly what `quality` runs before the tests, plus the tests of the changed area chosen from the ownership table. Document it in `CLAUDE.md` and `AGENTS.md` as the step before every push. | Fewer red CI runs: a failure in lint, types or the tests of the changed area shows before the push. | no |
| 8 | Stop the comment-triggered workflows from creating jobs for ordinary comments: one small dispatcher job reads the first token and starts a lane through `workflow_call` only for a command. | Six skipped jobs less per comment in the checks list of every head. | no required check |
| 9 | Make `test_packaging_smoke` independent of the local environment (create its virtual environment with `python -m venv` and report a clear skip reason when `ensurepip` is missing). | The full suite can run in an agent session. | no gate weakened |
| 10 | Record in the pull-request template the three lines an integrator needs: exact head, required checks on that head, review verdict. | Merges of several agents become comparable (`AGENTS.md` §10). | no |

## Suggested order of work

1. Recommendations 7, 6 and 9 first: they need no gate decision and reduce red runs at once.
2. Recommendation 1 as a small pull request of its own.
3. Recommendations 4 and 5 together, measured before and after on the same head.
4. Recommendations 2, 3 and 8 after the Owner's decision, each alone, because each changes
   what a green or red check means.

## Implemented: parallel `quality` graph (2026-11-14, Owner-approved)

`quality` is now a gate job (`if: always()`, `needs: [changes, lint, tests, packaging]`, decision in
`scripts/ci_gate.py`). `changes` classifies the diff (`scripts/ci_change_scope.py`); `lint` runs
ruff, format, mypy, compile, the secret scan and the wheel build; `tests` is a matrix of four
runners (`python -m tests.pytest_shards matrix`), each with `--shards=4`; `packaging` runs on a
push to `main` and on a pull request that changes a packaging input. A document-only pull request
runs one `tests` slot with the documentation tests (`tests/pytest_docs_tests.json`, 42 files) and
skips `packaging`. When this was written the tree had 403 test files outside
`tests/qualification`: 402 in the matrix and the packaging test, which only the `packaging` job
runs. The integrity guard (`scripts/verify_required_check_definitions.py`) accepts this gate
pattern by parsing, not by name.

Accepted risk: a pull request that only edits an existing module under `src/` does not run the
`packaging` job (an added or deleted module, a package `__init__.py`, a console-script target and
the packaging inputs do). An edit that breaks the wheel or an entrypoint import is therefore
caught by the `packaging` job of the push to `main`, not before the merge.

## What stays as it is

- The three required contexts and branch protection.
- Path-filtered qualification workflows (PB-03, conformance, real four-player smoke): they
  already run only when their inputs change, and cancelling superseded heads works.
- Hash-pinned actions and the hash-locked install.
- No automatic re-run of failed jobs, no empty commits to restart CI.

## Open Owner decisions

1. Whether `ci-definition-integrity-shadow` may end neutral for added tests (recommendation 2).
2. Whether document-only changes get the fast path (recommendation 3).
3. Whether the lane may change `ci.yml` step order and job split (recommendations 4 and 5).
