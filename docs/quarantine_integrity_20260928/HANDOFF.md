# Run quarantine path integrity

Objective: reject invalid quarantine requests before mutation and preserve existing
destination entries. Direct user authority: find small useful fixes, persist each
validated milestone, and publish a complete PR.

Source lock: main `3910040b3ca4eb276f8895fa4c9801af3550f123`, tree
`a28d98b29c84342056e5658f8f4423f927999108`.
Owned branch: `astra/quarantine-path-integrity-20260928` in the reused dedicated
Astra clone. Owned surface: `quarantine_run` in storage/run_integrity.py,
`tests/unit/test_run_quarantine.py`, and this evidence directory.

Scope: source-directory validation, destination ancestry validation, occupied-name
handling. Reuse pathlib, os.path.lexists and the existing shutil.move operation.
No new dependency, format, engine behavior, or qualification evidence change.
No real run is moved during this work: tests exclusively use temporary fixtures.

Ownership: published active #289/#285/#284/#287 and Muse donor inspected; no
quarantine function changes. Own PR #288 changes directory inventory elsewhere in
the same module; this branch is independently based on main and preserves its
integration path. Storage cache/hash and Foundry candidates overlap published
foreign deletion surfaces and are intentionally not modified.

Baseline on unchanged main: 5 failures, 1 pass, 1 skip in the new tests. Invalid
descendant requests can create directories in the source before shutil rejects
the move. A missing source creates a destination; a file source is moved despite
the run-directory contract. A dangling-link regression is included but requires
Linux CI because this Windows session lacks symlink privilege.

Hard gates: existing run contents and occupied destination entries preserved;
normal directory quarantine still works; errors raised before creating invalid
targets. Tests, affected lint/format/type checks, exact-head CI and reviews before
integration. No claim of atomic exclusion against concurrent filesystem writers
or rollback after a cross-filesystem copy failure. Exclusive/quiescent paths are
required, as before.

Checkpoint 1: cdf0c940 persists failing-before tests and source lock, pushed.
Checkpoint 2: production repair implemented. Real dangling Windows junction also
reproduced against the original main function (1 failed) and now passes.
Focused storage tests: 57 passed, 6 platform skips. Affected Ruff/format/strict
mypy/compileall pass. Initial broader acceptance attempt: 2 failures because its
source-integrity gate correctly rejects uncommitted tracked changes; rerun on the
clean committed checkpoint is required. No acceptance PASS is claimed yet.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED

## Validated completion and integration handoff

Repair checkpoint: `ccb961ec` (pushed). Clean-checkout rerun: **62 passed,
6 skipped** in 31.46s across the new quarantine tests, manifest tests, existing
atomic-storage tests and Phase10 acceptance. Five skips require unavailable
Windows symlink privilege; one requires POSIX FIFO. The actual dangling Windows
junction test ran and passed. The earlier two acceptance failures were solely
the expected dirty-source gate and are resolved by the committed rerun.
Affected Ruff, format, strict mypy and compileall passed.

Only nine production lines changed in quarantine_run; no provider, Rules,
launcher or qualification artifacts changed. The new PR is independent of #288;
its earlier inventory guard remains a separate integration item.

Final remote readback before publication: main remains source-locked above.
Active refs checked: sbmax/final-pre-freeze `2ec0759c377d6c490f142e678c3796e722aeb43f`,
sbmax/full-completion `b4ea775137c9d0538ca85f8c8b56383650111745`,
sol/final-integration-salvage `20e3d2caf357defd87a9c7217f17246919819f79`,
docs/final-adversarial-audit `ecf673f465f5b3ca4d10b562900e0e42a872bc01`.

PASS: bounded local repair and affected validation. NOT_YET_VERIFIED: published
exact-head Linux CI and current PR review. No broader project completion claim.
Exact next action for Sol: inspect new PR head/target, exact-head checks and review
findings; resolve attributable failures; merge normally with --match-head-commit
only after gates pass, then persist merged main HEAD/TREE. No admin bypass,
force push, branch deletion, or mutation of another worker's campaign.
