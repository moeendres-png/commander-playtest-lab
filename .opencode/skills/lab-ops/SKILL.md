---
name: lab-ops
description: Compact PR/CI/review-thread status, failing-job lines, CI and workflow waiting, PB-03 packet summary with AF00-AF11 per candidate, and real-engine row runs, through the shared scripts in .claude/skills/lab-ops/scripts. Use instead of raw API JSON or whole logs.
---

# Lab ops (shared with Claude)

The scripts live in `.claude/skills/lab-ops/scripts/` and are model-neutral; run them from the
Lab worktree root. They print compact lines and never change GitHub state.

| Need | Command |
|---|---|
| PR head, merge state, red/pending checks, open threads | `python3 .claude/skills/lab-ops/scripts/gh_ops.py status PR…` |
| Unresolved review threads | `python3 .claude/skills/lab-ops/scripts/gh_ops.py threads PR` |
| Failing lines of a job | `python3 .claude/skills/lab-ops/scripts/gh_ops.py errors JOB_ID` |
| Wait for PR checks / a workflow run | `python3 .claude/skills/lab-ops/scripts/gh_ops.py wait PR…` / `run RUN_ID` |
| PB-03 packet + AF00-AF11 summary | `python3 .claude/skills/lab-ops/scripts/pb03_packet.py RUN_ID OUT` |
| Real-engine rows | `python3 .claude/skills/lab-ops/scripts/real_rows.py build|midgame|cardinality|pregame|af04 …` |

`ci-definition-integrity-shadow` is red by design (CI-02). Real-engine runs are LOCAL_OBSERVED,
never credit; credit comes only from PB-03 on an exact head plus a sealed epoch.
