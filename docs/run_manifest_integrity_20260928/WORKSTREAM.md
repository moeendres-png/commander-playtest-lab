# Run-manifest verification integrity

Objective: make storage run verification reject malformed or incomplete artifact
inventories instead of returning valid or raising an unhandled parsing exception.

Authority: direct user request for additional important code defect detection,
repair and publication. One bounded storage-integrity workstream.

Source lock: main `7890aed0f692e67052dd51925575380828996ab4`, tree
`32b7a20115ccfe7ad89409ff3ac71f9697a5d1ae` (includes merged Astra PR #280).
Branch: `astra/run-manifest-integrity-20260928`, exclusively owned by this session.
Reuse the now-free dedicated Astra checkout; no foreign worktree access.

Owned: `src/commander_lab/storage/run_integrity.py`, a new focused regression test
module, and this evidence directory. Existing acceptance and CLI consumers are
validated without modifying their implementation. No overlap with published
sbmax/full-completion or WSR27 branches, checked against their merge bases.

Out of scope: provider/Rules/replay semantics, launcher/routing, qualification
artifacts, cache identity, concurrent hostile filesystem security, signatures or
external attestation. Hash integrity is not simulation correctness or authenticity.

Reuse gate: inspected storage atomic writer, current manifest producer/verifier,
CLI and Phase10 consumers, existing tests and repository history. No compatible
sealed donor repair found; the similarly named calibration patch is unrelated.
Reuse the existing atomic writer; do not introduce another artifact format.

Hard gates: reproduce against source-locked main before repair; keep schema v1
valid producer output interoperable; reject invalid inputs explicitly; preserve
existing manifests when creation fails; no foreign mutation or evidence promotion.
An explicit `.quarantine` subtree remains excluded; only the root manifest itself
is excluded from ordinary artifact coverage.

Persistence: commit failing-before test evidence, then validated repairs, then
publish a dedicated PR with exact-head CI and a Sol integration handoff. No need
to repeat the already completed governance campaign or provider qualification.

Required evidence: negative reproduction, positive producer/verifier round trip,
existing storage/CLI/acceptance regression, Ruff/format, strict mypy, compileall,
current source/ownership readback and exact PR head. Missing runtime coverage
stays NOT_RUN; stop for genuine source/ownership/authority gates.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED

## Junction follow-up after PR #282 integration

Current base: `3910040b3ca4eb276f8895fa4c9801af3550f123`, tree
`a28d98b29c84342056e5658f8f4423f927999108`. Owned follow-up branch:
`astra/run-manifest-junction-20260928`. The original source lock above remains
historical provenance. PR #282 is merged, including the reviewed finite-float fix.

Remaining defect: Windows directory junctions are traversed by os.walk despite
followlinks=False and are not reported by is_symlink(). Reject is_junction()
before descent; preserve the existing seal on failure. The new actual-junction
regression fails before the guard and passes after it. Reuse pathlib on the
project-required Python >=3.12; no new dependency or manifest schema.

Additional owned surface: `.github/workflows/run-manifest-integrity.yml`, a
bounded Windows test gate. Existing windows-runtime.yml is foreign-active, so
it remains untouched. The new gate executes the actual junction test, which
Linux cannot exercise. Published active storage surfaces were checked before edits.

Validation: 56 passed / 5 skipped (four unavailable Windows symlink privileges
and POSIX FIFO), 14 workflow-contract tests passed; affected Ruff, formatting,
strict mypy and compileall passed. Linux coverage remains an exact-head CI gate.
No authenticity, concurrent hostile-writer safety, Rules or qualification claim.

Exact next action for normal Sol: inspect the published follow-up head and target,
all CI including windows-manifest-integrity, and current review findings; repair
only attributable failures, then normal merge with --match-head-commit and no
admin bypass. Persist resulting main HEAD/TREE. Do not merge PR #282 again.
