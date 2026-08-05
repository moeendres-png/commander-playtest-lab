# Static analysis

- **pytest_collect:** `passed` (return code `0`)
- **pytest:** `passed` (return code `0`)
- **compileall:** `passed` (return code `0`)
- **ruff_check:** `blocked` (return code `n/a`)
  - Blocker: [Errno 2] No such file or directory: 'ruff'
- **ruff_format:** `blocked` (return code `n/a`)
  - Blocker: [Errno 2] No such file or directory: 'ruff'
- **mypy:** `blocked` (return code `n/a`)
  - Blocker: [Errno 2] No such file or directory: 'mypy'

Ruff, mypy and Hypothesis could not be installed in the current sandbox because the configured package index had no matching distributions and external DNS was unavailable.
