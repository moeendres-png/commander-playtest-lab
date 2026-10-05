---
name: lab-ops
description: Token- and time-efficient operations for Commander Playtest Lab sessions — one-line PR/CI status and open review threads, failing-job log extraction, CI/workflow waiting, PB-03 packet download and AF00-AF11 summary, and real-engine row runs (mid-game, cardinality, scripted pregame, AF04) without ad-hoc scripts. Use whenever you check PRs or CI, wait on checks, diagnose a red job, read a PB-03 run, or validate rows against the real XMage/Forge engines.
---

# Lab ops

Scripts in `scripts/`. They print compact lines, never raw API JSON, and they do not
change GitHub state. Run them from the Lab worktree root.

| Need | Command |
|---|---|
| PR head, merge state, red/pending checks, open threads | `scripts/gh_ops.py status 544 537` |
| Every open PR in Lab, mage and forge, one line each | `scripts/gh_ops.py queue` |
| Unresolved review threads (comment id to reply to) | `scripts/gh_ops.py threads 544` |
| Why a job is red (failure lines with context) | `scripts/gh_ops.py errors JOB_ID` |
| Re-run only jobs that died on infrastructure (runner never acquired, operation canceled; no failed step) | `scripts/gh_ops.py rerun-cancelled [--dry-run] 559 552` |
| Wait for CI on PRs / for one workflow run | `scripts/gh_ops.py wait 544` · `scripts/gh_ops.py run RUN_ID` (background) |
| PB-03 packet: identity, sha256 check, AF00-AF11 per candidate | `scripts/pb03_packet.py RUN_ID OUT [--into .]` |
| Seal an epoch (packet + manifests + the required secret scan, before any push) | `scripts/seal.py RUN_ID [--replace OLD_EPOCH]` on a fresh branch from main |
| Real-engine rows | `scripts/real_rows.py build` then `midgame FIX…`, `cardinality CAND`, `pregame CAND`, `af04 CAND PKG` (Forge: `--forge PATH`, `xvfb-run -a`) |

`gh_ops.py` uses `gh api`: REST plus the CCR thread route
`repos/{o}/{r}/pulls/{n}/ccr/review_threads`. GraphQL is not available in Claude
Code sessions. The same CCR prefix also serves `…/ccr/comments/{id}/resolve` and
`…/ccr/auto_merge`. `ci-definition-integrity-shadow` is reported as red by design (CI-02). Hosted runners are often
never acquired for this account's jobs. Such a job shows `cancelled` with no steps and the annotation
"not acquired by Runner". Use `rerun-cancelled` instead of diagnosing each job by hand. The repo-admin
API (rulesets, branch protection) is not writable from a cloud session (proxy 403): hand the Owner the
exact `gh api` command instead of retrying.
`status`/`wait` report one verdict per check name. A cancelled duplicate run never hides
a run of the same check that reached a result. A re-triggered workflow leaves such
duplicates, and the raw check list then shows false red.

## Local test environment

A fresh container has no project venv. Create one outside the worktree and point
it at the worktree under test:

```
uv venv -q -p 3.12 "$SCRATCH/venv" && VIRTUAL_ENV="$SCRATCH/venv" uv pip install -q -e ".[dev]"
rm -rf src/*.egg-info   # the editable install writes it into src/; PB-03 trigger tests then fail
PYTHONPATH="$PWD/src" "$SCRATCH/venv/bin/python" -m pytest -q -p no:cacheprovider tests/qualification
```

`PYTHONPATH` keeps another worktree's editable install from shadowing this one. The
broad secret scan writes `artifacts/security/`; delete it before committing
(`seal.py` keeps its report in scratch).

## Working efficiently without losing evidence quality

The output of each command decides the next step, so read it all; just don't pull more into context than that decision needs.

- **Status over dumps.** Prefer `gh_ops.py status` / `threads` / `errors` to the MCP `get_check_runs`, `get_review_comments` and `get_job_logs` calls. Those return 5–15k tokens where one line answers the question. Use MCP for writes: replies, resolves, merges, PRs.
- **Wait in the background.** Run `gh_ops.py wait` / `run` or long suites with `run_in_background`, then continue other work. Never poll in the foreground and never use bare `sleep`.
- **Test narrow first, then wide, once.**
  - While iterating: the changed module's tests and `ruff`/`mypy` on the changed files.
  - Before the push: the full `tests/qualification` suite once, and `tests/unit` when `src/` changed.
  - Java bridge suites (XMage about 25 min, Forge about 27 min): once per Java change, in the background.
- **Real engines only where the change reaches.** Re-run the affected rows with `real_rows.py`, not the whole 60-minute mid-game regression. A row change still needs its local real-producer run plus wrong-reason controls (AGENTS.md); `real_rows.py` makes that one command.
- **Read narrowly.**
  - `grep -n` the symbol, then read a `sed -n A,Bp` window. Do not re-read a file you just edited.
  - Summarize big JSON with a short `python3 -c` filter instead of printing it.
- **Batch independent calls in one message.** This covers status checks across PRs, replies plus resolves, and reads of unrelated files.
- **Delegate mechanical sweeps.** A broad search over many files or logs goes to a subagent that returns the conclusion, not the file dumps: `log-scanner` for logs and evidence JSON, `ci-triage` for a red check, `Explore` for code location. Every subagent runs on at least Sonnet at `high` effort; never Haiku. Judgement, evidence adjudication and CR reasoning stay in the main session.
- **Keep the stack moving.**
  - After a base PR merges, retarget stacked PRs to `main` and merge `origin/main` into every open head in one loop.
  - Regenerate hash manifests with `scripts/regenerate_hash_manifests.py`; never resolve `WS17_SHA256SUMS` by hand.
  - Commit WIP before running `tests/unit`: tree-hashing tests fail on a dirty worktree.
- **Never trade evidence for speed.** UNKNOWN ≠ PASS, LOCAL_OBSERVED is not credit, and no option or default is fabricated. A shortcut that skips a gate the policy requires is not an efficiency.
