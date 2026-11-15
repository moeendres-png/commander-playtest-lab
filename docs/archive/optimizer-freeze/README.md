# Optimizer development freeze records

`J_P4_DEVELOPMENT_FREEZE.json`, `J_P5_DEVELOPMENT_FREEZE.json`, `J_P4_HOLDOUT_FIRST_EVALUATION.json`
and `J_P5_HOLDOUT_FIRST_EVALUATION.json` are historical notes of the J-phase optimizer development
(phases 4 and 5). They are not sealed qualification evidence and
were moved here from `docs/` with their content unchanged.

The optimizer is a removed product part. The scripts and modules these records name
(`scripts/run_j_p4_development.py`, `run_j_p4_holdout_once.py`, `run_j_p4_sensitivity.py`,
`run_j_p5_holdout_once.py`, and the optimizer, whole-deck, tools and related `src/commander_lab`
packages) were removed on 2026-11-15. They remain in Git history at commit
`585c9e2f2b1917ee1c59c201de74d1620037207d`, the commit before this change.

`qualification/final-current-boundary-20260927/VALIDATION.md` line 117 cites
`src/commander_lab/tools/service.py`; that file was removed in this change and is in git history
at `585c9e2f2b1917ee1c59c201de74d1620037207d`. The sealed record itself is unchanged.

`docs/J_P5_HOLDOUT_SEAL.json` stays in `docs/` (a test still reads it) and names
`docs/J_P5_HOLDOUT_FIRST_EVALUATION.json`, which now lives in this directory. The seal is left untouched, so its line 7 still shows the old path;
nothing machine-reads that line.
