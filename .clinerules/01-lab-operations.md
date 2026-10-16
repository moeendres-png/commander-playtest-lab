# Cline operating notes

The binding rules are in the repository-root `AGENTS.md`, which Cline loads natively.
Cline is a worker (`AGENTS.md` §6): own branch `cline/<topic>`, draft PR, never merge,
no Owner-only decisions, no edits to sealed evidence under `qualification/`.

Model and effort (Cline runs DeepSeek V4.1 Flash):
- Use the highest reasoning effort the Cline model settings offer (`max`; never below `high`).
  Cline sets effort in its UI model settings, so this file states the expectation: check it first.
- Use Plan mode to analyse, then Act mode to change. Phrase tasks per
  `docs/foundry-execution/EXECUTOR_PROMPTING.md`.
- Before a matching task load its skill file (`.opencode/skills/<name>/SKILL.md` or
  `.claude/skills/<name>/SKILL.md`) and say which one you loaded.
- Prefer the deterministic scripts over improvising: `python3 .claude/skills/lab-ops/scripts/gh_ops.py brief`
  (lane status), `oc_dispatch.py`, `pb03_packet.py`, `real_rows.py`.
- Request budget (free tier is request-capped): batch reads, fewer bigger steps, one test command per
  surface, one job at a time, no parallel runs. A quota refusal is `BLOCKED_SERVICE`: checkpoint, stop,
  resume the next day; never switch models.

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
