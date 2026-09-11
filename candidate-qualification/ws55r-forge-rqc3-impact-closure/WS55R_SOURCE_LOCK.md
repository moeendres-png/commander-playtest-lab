# WS55R — Source Lock

## CPL worktree (this workstream)

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree: `/home/moeen/code/ws55r-forge-rqc3-impact-closure`
- Branch: `ws55r/forge-rqc3-impact-closure-20260911`
- Starting HEAD: `47a1e714903a91d8929f48df6451365e8b7a7996` (WS55 terminal)
- Starting TREE: `8028eafca996021d2fdc667d9bee735c83081419`
- Parent workstream: WS55 Forge Mandatory Decision-Breadth
  (`FORGE_MANDATORY_DECISION_BREADTH_PARTIAL`, 20/22 kinds, 11 READY + 1 CONDITIONAL + 3 NOT_READY)
- Verified 2026-09-11: `git rev-parse HEAD` = starting HEAD;
  `git rev-parse HEAD^{tree}` = starting TREE; working tree clean except
  untracked `candidate-qualification/ws55r-forge-rqc3-impact-closure/` output directory itself.

## Forge engine pin (READ-ONLY, do not update / patch / fork)

- Forge checkout: `/tmp/ws55-forge-src`
- Required HEAD: `66caae16015bd403bc0a52fa6689afb5508f74d0`
- Required TREE: `40fc8f29ce4de31a964972461db2b48b4221e07f`
- Verified 2026-09-11 via `git --git-dir=/tmp/ws55-forge-src/.git rev-parse HEAD`
  and `HEAD^{tree}`: both match exactly.
- Build cache (prebuilt classes, read-only consumption):
  `/home/moeen/.ws48-r1e/forge-66caae16015bd403bc0a52fa6689afb5508f74d0`
  (identical source; `PlayerController.java` diff empty).

## Binding corrected authority RQ-C3 (READ-ONLY requirements input)

- Branch: `research/rules-authority-closure-rq-c3-20260910`
- HEAD: `897d72f0b57bb8febe045870acaa3d2dba4bde56`
- TREE: `1b8c8a46f1b81277f73a0ec808055dde25fadbe5`
- Verified 2026-09-11 via `git cat-file -t` (commit) and
  `git rev-parse <ref>^{tree}`: both match.
- Consumed (decision-surface requirements ONLY, via read-only `git show`):
  `RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json`,
  `RQ_C3_DECISION_REQUIREMENT_DELTA.json`,
  `RQ_C3_FIRST_WAVE_EXECUTION_PACK.json`,
  plus `RQ_C3_HIDDEN_INFO_EXPECTATIONS.json`, `RQ_C3_SETUP_BOUNDARIES.json`,
  `RQ_C3_SOURCE_LOCK.md`, per-scenario files for A03/A04/C01/E02/G04.
- NOT consumed as Rules truth for candidate behavior: RQ-C3 expected Magic
  outcomes remain `EXTERNALLY_RULE_VALIDATED` authority; no candidate behavior
  is executed for credit here (`BEHAVIOR_CREDIT = 0/107`).

## Mechanical denominator (triple-agree, script-rerunnable)

- Script: `ws55r_derive_rqc3.py` (reads RQ-C3 only via read-only `git show`
  of the locked ref; fails loud on any divergence).
- Result: `WS55R_CORRECTED_DENOMINATOR.json`
- `CORRECTED_FIRST_WAVE_REQUIRED_DECISION_KINDS = 20`, 15 scenarios,
  requirements x delta x execution-pack triple-agree.
- Binding delta vs RQ-C1: `may` REMOVED (A03), generic `ordering` REMOVED
  (E02), `hidden-zone selection` EXTENDED to C01+F01; alternate cost, combat
  damage assignment, replacement ordering, concession RETAINED.

## Standing project state (preserved exactly)

- `ARCHITECTURE_FREEZE = NOT CLAIMED`
- `PRODUCTION_PROVIDER = NOT SELECTED`
- `BEHAVIOR_CREDIT = 0/107`
- `FULL107 = NOT_RUN`
- Forge remains provisional leader. WS55R does not select a Provider.
- WS55R grants no behavior credit; no Full107 claim; no candidate comparison.
- Forge source remains strictly READ-ONLY. No engine edits. No pin changes.
