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

Checkpoint: failing-before tests persisted; production repair pending.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
