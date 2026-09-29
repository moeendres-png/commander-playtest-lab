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

Checkpoint 2: strict root resolution implemented; Python 3.12 loop RuntimeError
is translated only around Path.resolve, not around unrelated verification code.
Focused new tests: 4 passed. Storage regression before adding the unrelated-error
control: 53 passed, 5 platform skips. Affected Ruff/format/strict mypy pass.
Clean-commit integration validation follows this checkpoint.

## Validated completion

Initial clean-commit regression: 59 passed, 5 platform skips (26.25s), including
Phase10 acceptance. Main subsequently advanced to
`2e28866f2bab2981f0b8da2d9a7a493cd3f424cf`, tree
`0c7b0603cdc0f0958add7e9bf9f23c0f023ec1ff`. Its published changes do not touch
the owned paths. Normal merge (no history rewrite) incorporated this base in
`a40a9e4fc200577796d950d58bb225a84188fc6e`; clean regression was repeated.
Affected lint, format, strict mypy and compileall passed. Raw temporary path
identities are absent from structured errors; unrelated RuntimeError still escapes.

Next action: publish exact head; normal Sol checks exact-head CI, current review
threads and target drift, then merges only with --match-head-commit and persists
main HEAD/TREE. No admin bypass or branch deletion. No provider or Rules changes.
The original source lock remains reproduction provenance; it is not current main.
`a40a9e4f` regression outcome: **59 passed, 5 skipped** in 34.00s. Remaining gate: remote exact-head CI/review.
