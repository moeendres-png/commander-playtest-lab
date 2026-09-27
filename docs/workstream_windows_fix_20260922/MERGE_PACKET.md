# MERGE-READY PACKET — PR #209 (Issue #208 follow-up)

- PR: https://github.com/moeendres-png/commander-playtest-lab/pull/209
- Base: `origin/main` (`069762bc`, post PR #210).
- Head: branch `fix/windows-runtime-jobs-stanza-20260922` (see STATE.yaml).
- Scope: jobs-mapping regression battery
  (`tests/unit/test_workflow_jobs_mapping.py`: top-level jobs mapping +
  runner/steps shape + Issue #208 exact test) + workstream docs.
  The windows-runtime workflow repair itself already merged via PR #210;
  this branch takes main's version verbatim (conflict resolved --theirs).
  No workflow semantics changed here; no test weakened or deleted.
- CI (head ef4fe69d): quality PASS, infrastructure PASS, security PASS,
  exact-main-admission skipping by design. Windows-runtime lane correctly
  idle (PR diff no longer touches the workflow file).
- Real-Windows proof: the repaired bytes executed successfully on a real
  runner in the pre-merge CI cycle (windows-runtime 1m29s PASS on f0c50bde,
  job `windows-runtime` completed success).
- UNKNOWNs: none new. PR207 evidence/seals untouched.
- Merge impact: additive test + docs only. Rollback: revert.
- Verdicts: `ARCHITECTURE_FREEZE = NOT_CLAIMED`;
  `PRODUCTION_PROVIDER = NOT_SELECTED`. Merge by Coordinator.
