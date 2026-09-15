# WS223 Dependency Lock Contract

## Artifacts

- Input: `requirements/lock.in` (26 direct inputs mirroring `pyproject.toml`
  ranges + audit tools + `jsonschema` provenance note + build backend +
  win32 conditionals).
- Output: `requirements/lock.txt` = pip-compile region (115 pins) +
  delimited platform appendix (2 pins). 117 pins, 1945 hashes total.
- Provenance: `requirements/LOCK_PROVENANCE.json` (tool versions, commands,
  digests).
- Generator: `pip-tools==7.6.1` (pinned), `--generate-hashes
  --resolver=backtracking --strip-extras --allow-unsafe`.
- Appendix generator: `scripts/generate_lock_appendix.py` (index-digest
  hashes, no downloads).
- Verifier: `scripts/verify_dependency_lock.py` (offline always;
  `--with-network` for requires-python/closure/drift).

## Install semantic (all locked lanes)

```
python -m pip install --require-hashes -r requirements/lock.txt
python -m pip install --no-deps --no-build-isolation -e .
```

- `--require-hashes`: any index byte that disagrees with the lock fails the
  install (no silent substitution).
- `--no-deps --no-build-isolation`: the local project adds no resolution;
  the pinned setuptools/wheel build backend performs zero network fetch.
- Extras (`dev`/`api`/`openai`) need no separate install: the lock is the
  union, so presence == availability.

## Scope

Locked: every ubuntu lane with a `setup-python` step. Documented exception:
`windows-runtime.yml` (4-file portability slice keeps a range install; the
lock still carries the win32 closure and the receipt records its resolved
set). `opencode.yml` runs no Python.

## Offline / drift semantics

- LOCKED BUT UNCACHED (`--no-index`): explicit
  `No matching distribution found` — a missing artifact fails, never
  substitutes (proven 2026-09-15).
- DRIFT (index bytes change under a pin): install-time hash mismatch fails;
  `verify_dependency_lock.py --with-network` detects appendix drift
  statically.
