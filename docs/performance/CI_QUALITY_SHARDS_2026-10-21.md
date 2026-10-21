# CI `quality`: the pytest suite in four parallel shards (2026-10-21)

The required `quality` context was the longest of the three required checks and the one every
pull request waits for: 17:52 min on the runner (job 119084300966), of which the single-process
`pytest` step took 16:34 min. `security` takes 2 min and `infrastructure` 4 min. The runner
(`ubuntu-latest`, public repository) has 4 vCPUs and one pytest process used one of them.

`pytest --shards=4` (`tests/pytest_shards.py`) runs the same selection as four pytest
processes side by side. No dependency is added (`pytest-xdist` would change the hash-locked
`requirements/lock.txt`, which only the Owner reseals) and no test is changed.

## Result

Same 4-core machine, nothing else running, `PYTHONHASHSEED=0`, 3738 tests (tests/qualification
excluded, as in `ci.yml`):

| Run | Wall | Result |
|---|---:|---|
| One process (the command until now) | 22:09 min | 3738 passed, 7 skipped |
| Four shards, one shared checkout | 6:10 min | 1 failed (see below) |
| Four shards, a checkout copy each | 6:11 min | 3738 passed, 7 skipped |
| The workflow command itself (`--shards=4`), shards 328 s each | 6:06 min | 3738 passed, 7 skipped, plus the new tests |

That is 3.6x on the local machine. On the CI runner (`ubuntu-latest`, 4 vCPUs) two runs of the
workflow command on this change gave a `quality` job of 5:58 min and 10:35 min (the single-process
job took 17:52 min). The second run landed on a runner about twice as slow per core; its four shards
were balanced (481, 491 and 524 s), so the spread is the runner, not the plan.

Per test, the sharded run and the one-process run agree: no test of the one-process JUnit
report is missing from the merged sharded report, every shared test has the same outcome, and
the only additional ones are the tests of this change itself.

## How it works

- `--shards=N` makes the pytest process start N pytest children instead of running tests
  itself. Without the option nothing changes (`--shards=1`, a missing or empty weight table, or
  a child process all run ordinarily).
- Shards 1..N-1 get explicit test files from `tests/pytest_shard_weights.json` (measured
  seconds per file, assigned longest-first). The last shard runs the whole selection minus the
  files of the other shards. A test file the table does not know therefore runs in the last
  shard, and a file that left the repository is skipped at plan time: a stale table costs
  balance, never a test.
- Every shard gets the same options (`-q`, `--durations=50`); the exit code is the worst shard
  exit code (a failure or a collection error in any shard fails the step); the per-shard
  JUnit files are merged into `--junitxml`, so the `ci-evidence` artifact keeps its shape and
  gains one log per shard (`pytest-shard-K.log`).
- Only the options the required check uses are accepted with `--shards`; any other option is
  refused instead of guessed (the same rule as `tests/unit/test_required_test_ownership.py`,
  which now also proves that the shards of the workflow command select every quality test file
  exactly once).

## Why a checkout copy per shard

The first sharded run in one checkout failed
`tests/integration/test_opponent_ensemble_tools.py`: `tests/conftest.py` deletes two fixed report
paths under `data/` around every test, and a sibling shard removed the report between the write
and the read. Other tests write into `data/runs/` and `artifacts/` as well. Rather than chasing
each shared path, every shard runs in its own copy of the checkout (about 2 s per copy,
removed when the shard ends), so no shard can touch another's files. The tests see the same
tree and the same `.git`.

## Keeping the table

A table that is out of date only costs balance. After tests are added or slowed down:

```bash
pytest -q --ignore=tests/qualification --junitxml=/tmp/serial.xml
python -m tests.pytest_shards weights /tmp/serial.xml > tests/pytest_shard_weights.json
```

(or take the merged `pytest-junit.xml` of a CI run from the `ci-evidence` artifact). The log of
the slowest shard in `ci-evidence` shows when the shards drift apart.

## Not done

- The longest single file, `tests/unit/test_packaging_smoke.py` (296 s), bounds what file-level
  shards can reach; with 4 cores the ideal is 330 s per shard, so there is almost nothing
  left to gain by splitting inside a file.
- The remaining job time is install, lint and mypy (about 1 min) plus the packaging smoke
  steps (about 30 s).
- To go back: drop `--shards=4` from the `Test suite` step of `ci.yml`.
