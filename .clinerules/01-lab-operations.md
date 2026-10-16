# Cline operating notes

The binding rules are in the repository-root `AGENTS.md`, which Cline loads natively.
Cline is a worker (`AGENTS.md` §6): own branch `cline/<topic>`, draft PR, never merge,
no Owner-only decisions, no edits to sealed evidence under `qualification/`.

Practical points an outside agent does not know:
- Setup (Python 3.12): `pip install --require-hashes -r requirements/lock.txt`, then
  `pip install --no-deps -e .`. Java 17 + Maven only for `engine-bridge/` work.
- Before every push: `ruff check`, `ruff format --check` and the affected tests
  (`python -m pytest -q <path>`).
- Commit before running tests: on a dirty tree some tests fail with "stale canonical inputs".
- A change to `.github/workflows/production-qualification.yml` needs its digest updated in
  `WS17_SHA256SUMS` (`tests/qualification/test_ws17_qualification.py`).
- CI `ci-definition-integrity-shadow` is red by design when gate tests or workflows change;
  required checks are `quality`, `security`, `infrastructure`.
- Report only what you ran yourself; a red test is reported with its output, never skipped.
