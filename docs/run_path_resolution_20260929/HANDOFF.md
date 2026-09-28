# Fail-closed run path resolution

Objective/authority: direct user continuation to find, test, persist and publish
small useful integrity repairs. One bounded storage workstream.

Source lock: main `3910040b3ca4eb276f8895fa4c9801af3550f123`, tree
`a28d98b29c84342056e5658f8f4423f927999108`.
Branch: `astra/run-path-loop-20260929`, owned by this session in the dedicated
Astra clone. Owned: root resolution inside verify_run, the new focused
test_run_path_resolution.py module and this handoff.

Finding: Python 3.12 pathlib raises RuntimeError on a cyclic run-root link, which
escapes verify_run's structured failure boundary. Worse, non-strict resolution
can mask a cyclic parent of a missing child as an ordinary incomplete run.
Actual Windows junction-cycle tests on unchanged main: 2 failed, 1 passed.
The positive control preserves ordinary missing-run classification. Tests use
real POSIX symlinks on Linux and actual Windows junctions, not mocked exceptions.
Installed Python 3.12 pathlib source and strict-resolution behavior inspected.

Reuse: use pathlib strict resolution and the existing failure envelope. No new
dependency or schema. Scope excludes CLI argument semantics, Rules/provider
qualification, evidence promotion and concurrent hostile filesystem guarantees.
Published active campaign diffs checked, including new #291: no overlap. Own
#288 and #290 touch different functions in the same module and remain independent.
Do not modify the foreign-active cache/Foundry/dependency-verifier surfaces.

Hard gates: cycles produce corrupt/valid=false with no raw path in errors;
ordinary missing roots/manifests remain incomplete; valid runs still verify;
no unrelated RuntimeError may be silently swallowed. Focused tests, storage
regression, affected quality checks and exact-head CI/review before integration.
No real run or external directory is modified; only temporary fixtures are used.

Checkpoint 1: failing-before tests captured; repair pending.
ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
