# WS55 — Source Lock

## CPL worktree (this workstream)

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree: `/home/moeen/code/ws55-forge-mandatory-decision-breadth`
- Branch: `ws55/forge-mandatory-decision-breadth-20260910`
- Starting HEAD: `9493bb562efb9bcb7e14bf652b564f74b3f3b600`
- Starting TREE: `077769865f2224304c2365d85020de57e637cd20`
- Parent workstream: WS53 Forge Convergence + Native Progression Replacement
- WS53 terminal disposition: `FORGE_CONVERGENCE_NATIVE_PROGRESSION_PASS`
- Verified 2026-09-10: `git rev-parse HEAD` = starting HEAD; `git rev-parse HEAD^{tree}` = starting TREE.

## Forge engine pin (READ-ONLY, do not update / patch / fork)

- Forge checkout: `/tmp/ws55-forge-src`
- Required HEAD: `66caae16015bd403bc0a52fa6689afb5508f74d0`
- Required TREE: `40fc8f29ce4de31a964972461db2b48b4221e07f`
- Verified 2026-09-10 via `git --git-dir=/tmp/ws55-forge-src/.git rev-parse HEAD`
  and `HEAD^{tree}`: both match exactly.

## Candidate-neutral requirement donor RQ-C1 (READ-ONLY requirements input)

- Branch: `research/candidate-neutral-architecture-reverser-corpus-rq-c1-20260910`
- HEAD: `714ad417c1c090eb4ddf1ccd0828a2e869a80a74`
- TREE: `709a5944c9826dbaaa433052f3538425c8f0573b`
- Verified 2026-09-10 via `git rev-parse <ref>` and `<ref>^{tree}`: both match.
- Consumed (decision-surface requirements + architecture-pressure metadata ONLY):
  `RQ_C1_SCENARIO_MANIFEST.json`, `RQ_C1_DECISION_SURFACE_MATRIX.csv`,
  `RQ_C1_CANDIDATE_EXECUTION_CONTRACT.md`, the 15 first-wave scenario files,
  `RQ_C1_HIDDEN_INFO_EXPECTATIONS.json`, `RQ_C1_NATIVE_SETUP_BOUNDARIES.json`.
- NOT consumed as Rules truth: RQ-C1 expected Magic outcomes (its Rules
  Authority Queue is not yet fully Sol-adjudicated). No RQ-C1 expected-outcome
  assertion is used as independent Rules truth in WS55.

## Mechanical denominator (triple-agree, script-rerunnable)

- Script: `ws55_derive_first_wave.py` (reads RQ-C1 only via read-only
  `git show` of the locked ref; fails loud on any divergence).
- Result: `WS55_FIRST_WAVE_DECISION_REQUIREMENTS.json`
- `FIRST_WAVE_REQUIRED_DECISION_KINDS = 22`, 15 first-wave scenarios,
  manifest JSON x matrix CSV x scenario files triple-agree.

## Standing project state (preserved exactly)

- `ARCHITECTURE_FREEZE = NOT CLAIMED`
- `PRODUCTION_PROVIDER = NOT SELECTED`
- `BEHAVIOR_CREDIT = 0/107`
- `FULL107 = NOT_RUN`
- Forge remains provisional leader. WS55 does not select a Provider.
- WS55 grants no behavior credit; no Full107 claim; no candidate comparison.
